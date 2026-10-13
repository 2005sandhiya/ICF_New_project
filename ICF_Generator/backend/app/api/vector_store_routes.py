from fastapi import APIRouter, HTTPException
from app.models.chunk import VectorStoreStatusResponse
from app.services.vector_store import vector_store_service

router = APIRouter(tags=["Local Vector Store"])

@router.get("/vector-store/status", response_model=VectorStoreStatusResponse)
def get_vector_store_status():
    """
    Phase 4 Part 3 Endpoint: GET /api/vector-store/status
    Returns status summary of local FAISS vector store including total vectors,
    dimension, index type, and indexed studies list.
    """
    try:
        return vector_store_service.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch vector store status: {str(e)}")
