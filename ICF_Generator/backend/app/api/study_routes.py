import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Path, Query
from app.models.study import StudySummary, StudyDetail
from app.models.canonical_protocol import CanonicalProtocolResponse
from app.models.chunk import ChunkingResponse, EmbeddingResponse, VectorIndexingResponse
from app.services.study_loader import study_loader_service


router = APIRouter(tags=["Studies"])

@router.get("/studies", response_model=List[StudySummary])
def list_preloaded_studies():
    """
    Phase 2 Endpoint: GET /api/studies
    Scans data/studies/ directory and returns summary listing of available preloaded studies.
    """
    try:
        return study_loader_service.get_all_summaries()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load study list: {str(e)}")

@router.get("/studies/{study_id}", response_model=StudyDetail)
def get_study_detail(
    study_id: str = Path(..., description="Target study identifier e.g. NCT01713764")
):
    """
    Phase 2 Endpoint: GET /api/studies/{study_id}
    Returns detailed JSON data for the selected preloaded study.
    Validates study_id against path traversal attacks.
    """
    if ".." in study_id or "/" in study_id or "\\" in study_id:
        raise HTTPException(status_code=400, detail="Invalid study identifier format.")

    detail = study_loader_service.get_study_detail(study_id)
    if not detail:
        raise HTTPException(
            status_code=404, 
            detail=f"Study '{study_id}' not found in preloaded dataset."
        )

    return detail

@router.get("/studies/{study_id}/canonical", response_model=CanonicalProtocolResponse)
def get_study_canonical_protocol(
    study_id: str = Path(..., description="Target study identifier e.g. NCT01713764")
):
    """
    Phase 3 Part 3 Endpoint: GET /api/studies/{study_id}/canonical
    Converts preloaded study record into a clean CanonicalProtocol intermediate representation.
    """
    if ".." in study_id or "/" in study_id or "\\" in study_id:
        raise HTTPException(status_code=400, detail="Invalid study identifier format.")

    canonical_res = study_loader_service.get_study_as_canonical_protocol(study_id)
    if not canonical_res:
        raise HTTPException(
            status_code=404, 
            detail=f"Study '{study_id}' not found for canonicalization."
        )

    return canonical_res

@router.get("/studies/{study_id}/chunks", response_model=ChunkingResponse)
def get_study_chunks(
    study_id: str = Path(..., description="Target study identifier e.g. NCT01713764"),
    target_chunk_size: Optional[int] = Query(default=1000, ge=100, le=5000),
    chunk_overlap: Optional[int] = Query(default=150, ge=0, le=1000)
):
    """
    Phase 4 Part 1 Endpoint: GET /api/studies/{study_id}/chunks
    Chunks a preloaded study JSON into section-aware chunks with metadata traceability.
    """
    if ".." in study_id or "/" in study_id or "\\" in study_id:
        raise HTTPException(status_code=400, detail="Invalid study identifier format.")

    chunks_res = study_loader_service.get_study_chunks(
        study_id,
        target_chunk_size=target_chunk_size or 1000,
        chunk_overlap=chunk_overlap or 150
    )
    if not chunks_res:
        raise HTTPException(
            status_code=404,
            detail=f"Study '{study_id}' not found for chunking."
        )

    return chunks_res

@router.get("/studies/{study_id}/embed", response_model=EmbeddingResponse)
def get_study_embeddings(
    study_id: str = Path(..., description="Target study identifier e.g. NCT01713764"),
    target_chunk_size: Optional[int] = Query(default=1000, ge=100, le=5000),
    chunk_overlap: Optional[int] = Query(default=150, ge=0, le=1000),
    model_name: Optional[str] = Query(default=None, description="Optional local embedding model override"),
    batch_size: Optional[int] = Query(default=32, ge=1, le=256)
):
    """
    Phase 4 Part 2 Endpoint: GET /api/studies/{study_id}/embed
    Generates section-aware chunks and semantic embeddings for a preloaded study.
    """
    if ".." in study_id or "/" in study_id or "\\" in study_id:
        raise HTTPException(status_code=400, detail="Invalid study identifier format.")

    try:
        embedded_res = study_loader_service.get_study_embeddings(
            study_id=study_id,
            target_chunk_size=target_chunk_size or 1000,
            chunk_overlap=chunk_overlap or 150,
            model_name=model_name,
            batch_size=batch_size or 32
        )
        if not embedded_res:
            raise HTTPException(
                status_code=404,
                detail=f"Study '{study_id}' not found for embedding generation."
            )
        return embedded_res

    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Study embedding generation failed: {str(e)}")

@router.post("/studies/{study_id}/index", response_model=VectorIndexingResponse)
@router.get("/studies/{study_id}/index", response_model=VectorIndexingResponse)
def index_study(
    study_id: str = Path(..., description="Target study identifier e.g. NCT01713764"),
    target_chunk_size: Optional[int] = Query(default=1000, ge=100, le=5000),
    chunk_overlap: Optional[int] = Query(default=150, ge=0, le=1000),
    model_name: Optional[str] = Query(default=None, description="Optional local embedding model override"),
    batch_size: Optional[int] = Query(default=32, ge=1, le=256)
):
    """
    Phase 4 Part 3 Endpoint: POST/GET /api/studies/{study_id}/index
    Generates section-aware chunks and embeddings for a preloaded study and indexes them
    into the local FAISS vector database.
    """
    if ".." in study_id or "/" in study_id or "\\" in study_id:
        raise HTTPException(status_code=400, detail="Invalid study identifier format.")

    try:
        indexed_res = study_loader_service.index_study_vectors(
            study_id=study_id,
            target_chunk_size=target_chunk_size or 1000,
            chunk_overlap=chunk_overlap or 150,
            model_name=model_name,
            batch_size=batch_size or 32
        )
        if not indexed_res:
            raise HTTPException(
                status_code=404,
                detail=f"Study '{study_id}' not found for indexing."
            )
        return indexed_res

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Study vector indexing failed: {str(e)}")



