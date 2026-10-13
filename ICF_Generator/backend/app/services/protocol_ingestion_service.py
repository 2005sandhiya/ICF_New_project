"""Shared protocol upload and evidence-indexing pipeline."""
from typing import Callable, Optional

from app.models.canonical_protocol import CanonicalProtocolResponse
from app.models.chunk import VectorIndexingResponse
from app.services.canonicalization.canonicalization_engine import canonicalization_engine
from app.services.chunking.chunker import protocol_chunker_service
from app.services.document_processing.document_processor import document_processor_service
from app.services.embedding_service import embedding_service
from app.services.upload_service import upload_service
from app.services.vector_store import vector_store_service


class ProtocolIngestionService:
    def index_upload(
        self,
        filename: str,
        content: bytes,
        *,
        on_stage: Optional[Callable[[str, str, str], None]] = None,
        target_chunk_size: int = 1000,
        chunk_overlap: int = 150,
        model_name: Optional[str] = None,
        batch_size: int = 32,
    ) -> tuple[CanonicalProtocolResponse, VectorIndexingResponse]:
        """Validate, read, canonicalize, chunk, embed, and index one upload."""
        canonical = self.canonicalize_upload(filename, content, on_stage=on_stage)
        return self.index_canonical(
            canonical,
            on_stage=on_stage,
            target_chunk_size=target_chunk_size,
            chunk_overlap=chunk_overlap,
            model_name=model_name,
            batch_size=batch_size,
        )

    def canonicalize_upload(
        self,
        filename: str,
        content: bytes,
        *,
        on_stage: Optional[Callable[[str, str, str], None]] = None,
    ) -> CanonicalProtocolResponse:
        stage = on_stage or (lambda _name, _status, _message: None)
        stage("study_loaded", "active", "Loading and verifying uploaded protocol...")
        metadata = upload_service.process_protocol_upload(filename, content)
        extracted = document_processor_service.process_document(
            filename=metadata.filename,
            content=content,
            file_type=metadata.file_type,
            storage_id=metadata.storage_id,
            provided_page_count=metadata.page_count,
        )
        stage("study_loaded", "complete", "Study / protocol loaded.")
        stage("protocol_parsed", "active", "Parsing protocol document structure...")
        canonical = canonicalization_engine.canonicalize_document(
            filename=metadata.filename,
            file_type=metadata.file_type,
            content=content,
            full_text=extracted.full_text,
            pages=extracted.pages,
        )
        stage("protocol_parsed", "complete", "Protocol parsed.")
        return canonical

    def index_canonical(
        self,
        canonical: CanonicalProtocolResponse,
        *,
        on_stage: Optional[Callable[[str, str, str], None]] = None,
        target_chunk_size: int = 1000,
        chunk_overlap: int = 150,
        model_name: Optional[str] = None,
        batch_size: int = 32,
    ) -> tuple[CanonicalProtocolResponse, VectorIndexingResponse]:
        stage = on_stage or (lambda _name, _status, _message: None)
        stage("text_chunking_completed", "active", "Chunking protocol text...")
        chunks = protocol_chunker_service.chunk_canonical_protocol(
            canonical_response=canonical,
            target_chunk_size=target_chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if not chunks.total_chunks:
            raise ValueError("No readable protocol evidence was found in the selected document.")
        stage("text_chunking_completed", "complete", "Text chunking completed.")
        stage("embeddings_generated", "active", "Generating text embeddings...")
        embedded = embedding_service.embed_chunking_response(
            chunk_response=chunks,
            model_name=model_name,
            batch_size=batch_size,
        )
        stage("embeddings_generated", "complete", "Embeddings generated.")
        stage("vector_index_completed", "active", "Building FAISS vector index...")
        indexed = vector_store_service.add_embeddings(embedded)
        stage("vector_index_completed", "complete", "FAISS / vector index completed.")
        return canonical, indexed


protocol_ingestion_service = ProtocolIngestionService()
