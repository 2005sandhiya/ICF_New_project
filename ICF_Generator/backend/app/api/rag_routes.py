import logging
from fastapi import APIRouter, HTTPException, status

from app.models.rag import RAGRetrieveRequest, RAGContextResponse
from app.services.context_assembler import context_assembler

logger = logging.getLogger("icf_generator.rag_routes")

router = APIRouter(
    tags=["RAG Retrieval & Context Assembly"]
)

@router.post(
    "/rag/retrieve",
    response_model=RAGContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Grounded Protocol Evidence & Assemble RAG Context",
    description="Phase 5 Part 1: Takes a natural language requirement, retrieves relevant protocol evidence using FAISS, filters duplicates, applies threshold safety, and packages grounded context."
)
def retrieve_rag_context(request: RAGRetrieveRequest) -> RAGContextResponse:
    """
    RAG Context Retrieval Endpoint.
    
    Returns structured context package with evidence items and 100% source traceability metadata.
    """
    try:
        return context_assembler.assemble_context(request)
    except ValueError as ve:
        logger.warning(f"Validation error in RAG retrieve: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error assembling RAG context: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve and assemble RAG context: {str(e)}"
        )
