import os
import logging
from typing import List, Optional
from sentence_transformers import SentenceTransformer

from app.models.chunk import (
    ProtocolChunk,
    ChunkingResponse,
    EmbeddedProtocolChunk,
    EmbeddingResponse
)

logger = logging.getLogger("icf_generator.embedding_service")

DEFAULT_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
DEFAULT_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

class EmbeddingService:
    """
    Local Semantic Embedding Service (Phase 4 Part 2).
    Generates semantic embedding vectors for protocol chunks using local sentence-transformers models.
    """

    def __init__(
        self,
        default_model_name: str = DEFAULT_MODEL_NAME,
        default_batch_size: int = DEFAULT_BATCH_SIZE
    ):
        self.default_model_name = default_model_name
        self.default_batch_size = default_batch_size
        self._model_cache = {}

    def get_model(self, model_name: Optional[str] = None) -> SentenceTransformer:
        """
        Loads and caches the target local SentenceTransformer model instance.
        """
        target_model = model_name or self.default_model_name
        if target_model not in self._model_cache:
            logger.info(f"Loading local embedding model '{target_model}' into memory...")
            try:
                model = SentenceTransformer(target_model)
                self._model_cache[target_model] = model
                dim = model.get_embedding_dimension() if hasattr(model, "get_embedding_dimension") else model.get_sentence_embedding_dimension()
                logger.info(f"Model '{target_model}' loaded successfully. Dimension: {dim}")
            except Exception as e:
                logger.error(f"Failed to load local embedding model '{target_model}': {str(e)}")
                raise RuntimeError(f"Embedding model '{target_model}' loading failed: {str(e)}")
        
        return self._model_cache[target_model]

    def get_embedding_dimension(self, model_name: Optional[str] = None) -> int:
        """
        Programmatically retrieves the embedding dimension of the loaded model.
        """
        model = self.get_model(model_name)
        if hasattr(model, "get_embedding_dimension"):
            return model.get_embedding_dimension()
        return model.get_sentence_embedding_dimension()

    def generate_embeddings(
        self,
        chunks: List[ProtocolChunk],
        model_name: Optional[str] = None,
        batch_size: Optional[int] = None
    ) -> List[EmbeddedProtocolChunk]:
        """
        Generates semantic embedding vectors for a list of ProtocolChunk objects.
        """
        if not chunks:
            return []

        target_model_name = model_name or self.default_model_name
        target_batch_size = batch_size or self.default_batch_size
        model = self.get_model(target_model_name)

        texts = [chk.text for chk in chunks]
        
        logger.info(f"Generating embeddings for {len(texts)} chunk(s) using model '{target_model_name}' (batch_size={target_batch_size})...")

        try:
            # Batch encode with normalization enabled for standard cosine similarity
            vectors = model.encode(
                texts,
                batch_size=target_batch_size,
                normalize_embeddings=True,
                show_progress_bar=False
            )
        except Exception as e:
            logger.error(f"Error during batch embedding encoding: {str(e)}")
            raise RuntimeError(f"Batch embedding generation failed: {str(e)}")

        embedded_chunks: List[EmbeddedProtocolChunk] = []
        for chk, vec in zip(chunks, vectors):
            # Convert numpy array vector to python list of floats
            float_vec = vec.tolist() if hasattr(vec, "tolist") else list(vec)
            embedded_chunks.append(
                EmbeddedProtocolChunk(
                    chunk_id=chk.chunk_id,
                    text=chk.text,
                    metadata=chk.metadata,
                    embedding=float_vec
                )
            )

        logger.info(f"Successfully generated {len(embedded_chunks)} embedded chunk(s).")
        return embedded_chunks

    def embed_chunking_response(
        self,
        chunk_response: ChunkingResponse,
        model_name: Optional[str] = None,
        batch_size: Optional[int] = None
    ) -> EmbeddingResponse:
        """
        Wraps a ChunkingResponse into an EmbeddingResponse with generated vectors attached.
        """
        target_model_name = model_name or self.default_model_name
        target_batch_size = batch_size or self.default_batch_size
        
        embedded_chunks = self.generate_embeddings(
            chunks=chunk_response.chunks,
            model_name=target_model_name,
            batch_size=target_batch_size
        )

        dim = self.get_embedding_dimension(target_model_name)

        return EmbeddingResponse(
            status="embedded",
            study_id=chunk_response.study_id,
            source_filename=chunk_response.source_filename,
            source_type=chunk_response.source_type,
            embedding_model=target_model_name,
            embedding_dimension=dim,
            batch_size=target_batch_size,
            total_chunks=len(embedded_chunks),
            embedded_chunks=embedded_chunks,
            message=f"Successfully generated {len(embedded_chunks)} semantic embedding vector(s)."
        )

# Global singleton instance
embedding_service = EmbeddingService()
