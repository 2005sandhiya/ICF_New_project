from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from app.models.study import ProtocolMetadataResponse, ExtractedTextResponse
from app.models.canonical_protocol import CanonicalProtocolResponse
from app.models.chunk import ChunkingResponse, EmbeddingResponse, VectorIndexingResponse
from app.services.upload_service import upload_service
from app.services.document_processing.document_processor import document_processor_service
from app.services.canonicalization.canonicalization_engine import canonicalization_engine
from app.services.chunking.chunker import protocol_chunker_service
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store_service
from app.services.protocol_ingestion_service import protocol_ingestion_service


router = APIRouter(tags=["Protocol Ingestion & Canonicalization"])

@router.post("/protocol/upload", response_model=ProtocolMetadataResponse)
async def upload_and_validate_protocol(file: UploadFile = File(...)):
    """
    Phase 3 Part 1 Endpoint: POST /api/protocol/upload
    Validates uploaded protocol document (.pdf, .docx, .txt, .json), stores file safely,
    extracts metadata (file size, page count if PDF, timestamp), and returns structured result.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided in upload request.")

    try:
        content = await file.read()
        response = upload_service.process_protocol_upload(file.filename, content)
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Protocol validation failed: {str(e)}")

@router.post("/protocol/process", response_model=ExtractedTextResponse)
async def upload_and_process_protocol(file: UploadFile = File(...)):
    """
    Phase 3 Part 2 Endpoint: POST /api/protocol/process
    Receives protocol file, validates format, saves to data/uploads/,
    runs DocumentProcessor to extract normalized text page-by-page, and returns structured result.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided in process request.")

    try:
        content = await file.read()
        metadata = upload_service.process_protocol_upload(file.filename, content)
        extraction_result = document_processor_service.process_document(
            filename=metadata.filename,
            content=content,
            file_type=metadata.file_type,
            storage_id=metadata.storage_id,
            provided_page_count=metadata.page_count
        )
        return extraction_result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Protocol document processing failed: {str(e)}")

@router.post("/protocol/canonicalize", response_model=CanonicalProtocolResponse)
async def canonicalize_protocol_file(file: UploadFile = File(...)):
    """
    Phase 3 Part 3 Endpoint: POST /api/protocol/canonicalize
    Receives protocol file, validates, extracts text, and maps clinical content into
    a clean, deterministic CanonicalProtocol intermediate representation with source traceability.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided in canonicalize request.")

    try:
        content = await file.read()
        metadata = upload_service.process_protocol_upload(file.filename, content)
        extraction_result = document_processor_service.process_document(
            filename=metadata.filename,
            content=content,
            file_type=metadata.file_type,
            storage_id=metadata.storage_id,
            provided_page_count=metadata.page_count
        )

        canonical_response = canonicalization_engine.canonicalize_document(
            filename=metadata.filename,
            file_type=metadata.file_type,
            content=content,
            full_text=extraction_result.full_text,
            pages=extraction_result.pages
        )

        return canonical_response

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Canonical protocol extraction failed: {str(e)}")

@router.post("/protocol/chunk", response_model=ChunkingResponse)
async def chunk_protocol_file(
    file: UploadFile = File(...),
    target_chunk_size: Optional[int] = Query(default=1000, ge=100, le=5000),
    chunk_overlap: Optional[int] = Query(default=150, ge=0, le=1000)
):
    """
    Phase 4 Part 1 Endpoint: POST /api/protocol/chunk
    Receives protocol file, extracts canonical representation, and splits content into
    section-aware chunks with comprehensive traceability metadata for RAG ingestion.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided in chunk request.")

    try:
        content = await file.read()
        metadata = upload_service.process_protocol_upload(file.filename, content)
        extraction_result = document_processor_service.process_document(
            filename=metadata.filename,
            content=content,
            file_type=metadata.file_type,
            storage_id=metadata.storage_id,
            provided_page_count=metadata.page_count
        )

        canonical_response = canonicalization_engine.canonicalize_document(
            filename=metadata.filename,
            file_type=metadata.file_type,
            content=content,
            full_text=extraction_result.full_text,
            pages=extraction_result.pages
        )

        chunk_response = protocol_chunker_service.chunk_canonical_protocol(
            canonical_response=canonical_response,
            target_chunk_size=target_chunk_size or 1000,
            chunk_overlap=chunk_overlap or 150
        )

        return chunk_response

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Protocol chunking failed: {str(e)}")

@router.post("/protocol/embed", response_model=EmbeddingResponse)
async def embed_protocol_file(
    file: UploadFile = File(...),
    target_chunk_size: Optional[int] = Query(default=1000, ge=100, le=5000),
    chunk_overlap: Optional[int] = Query(default=150, ge=0, le=1000),
    model_name: Optional[str] = Query(default=None, description="Optional local embedding model override"),
    batch_size: Optional[int] = Query(default=32, ge=1, le=256)
):
    """
    Phase 4 Part 2 Endpoint: POST /api/protocol/embed
    Receives protocol file, extracts canonical representation, splits into chunks, and
    generates semantic embedding vectors attached to each chunk.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided in embed request.")

    try:
        content = await file.read()
        metadata = upload_service.process_protocol_upload(file.filename, content)
        extraction_result = document_processor_service.process_document(
            filename=metadata.filename,
            content=content,
            file_type=metadata.file_type,
            storage_id=metadata.storage_id,
            provided_page_count=metadata.page_count
        )

        canonical_response = canonicalization_engine.canonicalize_document(
            filename=metadata.filename,
            file_type=metadata.file_type,
            content=content,
            full_text=extraction_result.full_text,
            pages=extraction_result.pages
        )

        chunk_response = protocol_chunker_service.chunk_canonical_protocol(
            canonical_response=canonical_response,
            target_chunk_size=target_chunk_size or 1000,
            chunk_overlap=chunk_overlap or 150
        )

        embedded_response = embedding_service.embed_chunking_response(
            chunk_response=chunk_response,
            model_name=model_name,
            batch_size=batch_size or 32
        )

        return embedded_response

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Protocol embedding generation failed: {str(e)}")

@router.post("/protocol/index", response_model=VectorIndexingResponse)
async def index_protocol_file(
    file: UploadFile = File(...),
    target_chunk_size: Optional[int] = Query(default=1000, ge=100, le=5000),
    chunk_overlap: Optional[int] = Query(default=150, ge=0, le=1000),
    model_name: Optional[str] = Query(default=None, description="Optional local embedding model override"),
    batch_size: Optional[int] = Query(default=32, ge=1, le=256)
):
    """
    Phase 4 Part 3 Endpoint: POST /api/protocol/index
    Receives protocol file, canonicalizes, chunks, generates semantic embeddings, and stores
    the resulting vectors and metadata in the local FAISS vector database.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided in index request.")

    try:
        content = await file.read()
        _, indexing_response = protocol_ingestion_service.index_upload(
            filename=file.filename,
            content=content,
            target_chunk_size=target_chunk_size or 1000,
            chunk_overlap=chunk_overlap or 150,
            model_name=model_name,
            batch_size=batch_size or 32,
        )
        return indexing_response

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Protocol indexing failed: {str(e)}")



