import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any, Set
import numpy as np
import faiss

from app.models.chunk import (
    EmbeddedProtocolChunk,
    EmbeddingResponse,
    VectorMetadataRecord,
    VectorStoreManifest,
    VectorStoreStatusResponse,
    VectorIndexingResponse
)

logger = logging.getLogger("icf_generator.vector_store")

# Default directory for persistent vector store
DEFAULT_VECTOR_STORE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "vector_store")
)

INDEX_FILENAME = "index.faiss"
METADATA_FILENAME = "metadata.json"
MANIFEST_FILENAME = "index_manifest.json"

class VectorStoreService:
    """
    Phase 4 Part 3: Local Vector Database Service using FAISS.
    
    Provides vector index creation, persistence, loading, metadata mapping,
    and index compatibility verification.
    
    Index Choice: faiss.IndexFlatIP (Inner Product)
    Rationale: SentenceTransformer models such as 'all-MiniLM-L6-v2' generate L2-normalized 
    embeddings (normalize_embeddings=True). For normalized vectors, inner product (IP) is 
    mathematically identical to Cosine Similarity.
    """

    def __init__(self, vector_store_dir: str = DEFAULT_VECTOR_STORE_DIR):
        self.vector_store_dir = vector_store_dir
        self.index_path = os.path.join(self.vector_store_dir, INDEX_FILENAME)
        self.metadata_path = os.path.join(self.vector_store_dir, METADATA_FILENAME)
        self.manifest_path = os.path.join(self.vector_store_dir, MANIFEST_FILENAME)

        self._index: Optional[faiss.Index] = None
        self._metadata_records: List[Dict[str, Any]] = []
        self._chunk_id_map: Dict[str, Dict[str, Any]] = {}
        self._manifest: Optional[Dict[str, Any]] = None

        os.makedirs(self.vector_store_dir, exist_ok=True)
        self.load_vector_store()

    def load_vector_store(self) -> bool:
        """
        Loads the FAISS index, metadata mapping, and manifest from disk if available.
        Returns True if loaded successfully, False if empty/initialized fresh.
        """
        self._metadata_records.clear()
        self._chunk_id_map.clear()
        self._index = None
        self._manifest = None

        if not (os.path.exists(self.index_path) and os.path.exists(self.metadata_path) and os.path.exists(self.manifest_path)):
            logger.info(f"No existing FAISS vector store found in '{self.vector_store_dir}'. Service initialized empty.")
            return False

        try:
            logger.info(f"Loading FAISS index from '{self.index_path}'...")
            self._index = faiss.read_index(self.index_path)

            logger.info(f"Loading metadata store from '{self.metadata_path}'...")
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self._metadata_records = json.load(f)

            for rec in self._metadata_records:
                self._chunk_id_map[rec["chunk_id"]] = rec

            logger.info(f"Loading manifest from '{self.manifest_path}'...")
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self._manifest = json.load(f)

            if self._index is not None and self._manifest is not None:
                logger.info(
                    f"Successfully loaded vector store. Vectors: {self._index.ntotal}, "
                    f"Dimension: {self._index.d}, Model: {self._manifest.get('embedding_model')}"
                )
            return True

        except Exception as e:
            logger.error(f"Failed to load existing FAISS vector store: {str(e)}. Initializing empty state.")
            self._index = None
            self._metadata_records.clear()
            self._chunk_id_map.clear()
            self._manifest = None
            return False

    def save_vector_store(self) -> None:
        """
        Persists the current FAISS index, metadata records, and manifest to disk.
        """
        if self._index is None or self._manifest is None:
            logger.warning("Attempted to save empty/uninitialized vector store.")
            return

        os.makedirs(self.vector_store_dir, exist_ok=True)

        try:
            # Write FAISS index
            faiss.write_index(self._index, self.index_path)

            # Write metadata json
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(self._metadata_records, f, indent=2, ensure_ascii=False)

            # Write manifest json
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(self._manifest, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved FAISS index, metadata, and manifest to '{self.vector_store_dir}'.")

        except Exception as e:
            logger.error(f"Failed to save vector store to disk: {str(e)}")
            raise RuntimeError(f"Vector store persistence failed: {str(e)}")

    def add_embeddings(self, embedding_response: EmbeddingResponse) -> VectorIndexingResponse:
        """
        Adds semantic embedding vectors and chunk metadata to the FAISS vector store.
        
        Handles:
        1. Dynamic dimension detection and validation.
        2. Index compatibility verification with existing stored vectors.
        3. Deterministic duplicate chunk skipping.
        4. Vector ID assignment and metadata mapping persistence.
        """
        if not embedding_response.embedded_chunks:
            return VectorIndexingResponse(
                status="indexed",
                embedding_model=embedding_response.embedding_model,
                embedding_dimension=embedding_response.embedding_dimension,
                index_type="IndexFlatIP",
                vectors_added=0,
                total_vectors=self.get_total_vectors(),
                studies_indexed=self.get_studies_indexed(),
                message="No embedded chunks provided to index."
            )

        target_model = embedding_response.embedding_model
        input_dim = embedding_response.embedding_dimension

        # Filter out duplicate chunks already present in metadata store
        new_chunks: List[EmbeddedProtocolChunk] = []
        for chk in embedding_response.embedded_chunks:
            if chk.chunk_id not in self._chunk_id_map:
                new_chunks.append(chk)

        if not new_chunks:
            logger.info(f"All {len(embedding_response.embedded_chunks)} chunk(s) are already indexed. Skipping duplicates.")
            return VectorIndexingResponse(
                status="indexed",
                embedding_model=target_model,
                embedding_dimension=input_dim,
                index_type="IndexFlatIP",
                vectors_added=0,
                total_vectors=self.get_total_vectors(),
                studies_indexed=self.get_studies_indexed(),
                message="Duplicate chunks skipped. No new vectors added."
            )

        # Validate vector dimension across input chunks
        raw_vectors = []
        for chk in new_chunks:
            if len(chk.embedding) != input_dim:
                raise ValueError(
                    f"Chunk '{chk.chunk_id}' vector dimension ({len(chk.embedding)}) does not match expected dimension ({input_dim})."
                )
            raw_vectors.append(chk.embedding)

        np_vectors = np.array(raw_vectors, dtype=np.float32)

        # Initialize or validate existing FAISS index
        if self._index is None:
            logger.info(f"Creating new FAISS IndexFlatIP with dimension {input_dim}...")
            self._index = faiss.IndexFlatIP(input_dim)
            now_iso = datetime.now().isoformat()
            self._manifest = {
                "embedding_model": target_model,
                "embedding_dimension": input_dim,
                "index_type": "IndexFlatIP",
                "total_vectors": 0,
                "created_at": now_iso,
                "updated_at": now_iso,
                "source_studies": []
            }
        else:
            # Compatibility check
            if self._index.d != input_dim:
                raise ValueError(
                    f"Incompatible embedding dimension! Store index dimension is {self._index.d}, "
                    f"but provided embeddings have dimension {input_dim}."
                )
            if self._manifest and self._manifest.get("embedding_model") != target_model:
                logger.warning(
                    f"Embedding model mismatch: Store used '{self._manifest.get('embedding_model')}', "
                    f"new embeddings created with '{target_model}'."
                )

        # Add vectors to FAISS index
        start_vec_id = self._index.ntotal
        self._index.add(np_vectors)
        added_count = len(new_chunks)

        # Add metadata records with assigned vector IDs
        for i, chk in enumerate(new_chunks):
            vector_id = start_vec_id + i
            meta_dict = {
                "vector_id": vector_id,
                "chunk_id": chk.chunk_id,
                "text": chk.text,
                "study_id": chk.metadata.study_id,
                "source_type": chk.metadata.source_type,
                "source_filename": chk.metadata.source_filename,
                "section": chk.metadata.section,
                "subsection": chk.metadata.subsection,
                "page_number": chk.metadata.page_number,
                "source_reference": getattr(chk.metadata, "source_reference", None) or f"{chk.metadata.section} (page {chk.metadata.page_number})" if chk.metadata.page_number else chk.metadata.section,
                "source_field": chk.metadata.source_field,
                "chunk_index": chk.metadata.chunk_index,
                "total_chunks": chk.metadata.total_chunks
            }
            self._metadata_records.append(meta_dict)
            self._chunk_id_map[chk.chunk_id] = meta_dict

        # Update manifest
        if self._manifest is None:
            now_iso = datetime.now().isoformat()
            self._manifest = {
                "embedding_model": target_model,
                "embedding_dimension": input_dim,
                "index_type": "IndexFlatIP",
                "total_vectors": 0,
                "created_at": now_iso,
                "updated_at": now_iso,
                "source_studies": []
            }

        current_studies = set(self._manifest.get("source_studies", []))
        if embedding_response.study_id:
            current_studies.add(embedding_response.study_id)
        for chk in new_chunks:
            if chk.metadata.study_id:
                current_studies.add(chk.metadata.study_id)

        assert self._index is not None
        self._manifest["total_vectors"] = self._index.ntotal
        self._manifest["source_studies"] = sorted(list(current_studies))
        self._manifest["updated_at"] = datetime.now().isoformat()

        # Save state to disk
        self.save_vector_store()

        logger.info(f"Successfully added {added_count} vector(s) to FAISS store. Total vectors: {self._index.ntotal}.")

        return VectorIndexingResponse(
            status="indexed",
            embedding_model=self._manifest.get("embedding_model", target_model),
            embedding_dimension=self._manifest.get("embedding_dimension", input_dim),
            index_type=self._manifest.get("index_type", "IndexFlatIP"),
            vectors_added=added_count,
            total_vectors=self._index.ntotal,
            studies_indexed=self._manifest.get("source_studies", []),
            message=f"Successfully indexed {added_count} vector(s) into local FAISS vector store."
        )

    def build_index(self, embedding_response: EmbeddingResponse) -> VectorIndexingResponse:
        """Alias for add_embeddings."""
        return self.add_embeddings(embedding_response)

    def get_total_vectors(self) -> int:
        """Returns total vector count in index."""
        return self._index.ntotal if self._index is not None else 0

    def get_studies_indexed(self) -> List[str]:
        """Returns list of unique study IDs indexed."""
        return self._manifest.get("source_studies", []) if self._manifest else []

    def get_metadata_by_vector_id(self, vector_id: int) -> Optional[VectorMetadataRecord]:
        """
        Retrieves chunk metadata by FAISS 0-indexed position.
        """
        if 0 <= vector_id < len(self._metadata_records):
            record = self._metadata_records[vector_id]
            return VectorMetadataRecord(**record)
        return None

    def get_metadata_by_chunk_id(self, chunk_id: str) -> Optional[VectorMetadataRecord]:
        """
        Retrieves metadata record by chunk_id.
        """
        record = self._chunk_id_map.get(chunk_id)
        if record:
            return VectorMetadataRecord(**record)
        return None

    def get_status(self) -> VectorStoreStatusResponse:
        """
        Returns structured status summary of the local FAISS vector store.
        """
        is_persisted = (
            os.path.exists(self.index_path) and
            os.path.exists(self.metadata_path) and
            os.path.exists(self.manifest_path)
        )

        total_vectors = self.get_total_vectors()
        status_str = "indexed" if total_vectors > 0 else "empty"

        model_name = (self._manifest.get("embedding_model") if self._manifest else None) or "all-MiniLM-L6-v2"
        dimension = (self._manifest.get("embedding_dimension") if self._manifest else None) or 384
        index_type = (self._manifest.get("index_type") if self._manifest else None) or "IndexFlatIP"
        studies = self.get_studies_indexed()

        return VectorStoreStatusResponse(
            status=status_str,
            embedding_model=str(model_name),
            embedding_dimension=int(dimension),
            index_type=str(index_type),
            total_vectors=total_vectors,
            studies_indexed=studies,
            storage_directory=self.vector_store_dir,
            is_persisted=is_persisted
        )

    def clear_store(self) -> None:
        """
        Resets and clears vector store files from disk and memory.
        """
        self._index = None
        self._metadata_records.clear()
        self._chunk_id_map.clear()
        self._manifest = None

        for filepath in [self.index_path, self.metadata_path, self.manifest_path]:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception as e:
                    logger.warning(f"Could not remove store file '{filepath}': {str(e)}")

        logger.info("Cleared local FAISS vector store.")

# Global singleton instance
vector_store_service = VectorStoreService()
