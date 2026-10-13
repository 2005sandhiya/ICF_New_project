from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Body
from app.models.chunk import SimilaritySearchRequest, SimilaritySearchResponse
from app.services.search_service import search_service

router = APIRouter(tags=["Semantic Similarity Search"])

@router.post("/search", response_model=SimilaritySearchResponse)
def perform_similarity_search_post(
    payload: SimilaritySearchRequest = Body(...)
):
    """
    Phase 4 Part 4 Endpoint: POST /api/search
    Encodes natural language query into 384-dimensional normalized embedding vector using all-MiniLM-L6-v2,
    searches FAISS IndexFlatIP vector database, and returns top-K ranked protocol chunks with metadata traceability.
    """
    if not payload or not payload.query or not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")

    try:
        response = search_service.search_vector_store(
            query=payload.query,
            top_k=payload.top_k or 5,
            study_id=payload.study_id,
            enable_diversity=payload.enable_diversity,
            diversity_penalty=payload.diversity_penalty
        )
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similarity search failed: {str(e)}")

@router.get("/search", response_model=SimilaritySearchResponse)
def perform_similarity_search_get(
    query: str = Query(..., min_length=1, description="Natural language query string"),
    top_k: int = Query(default=5, ge=1, le=100, description="Top-K results count"),
    study_id: Optional[str] = Query(default=None, description="Optional study ID filter"),
    enable_diversity: bool = Query(default=True, description="Enable section diversity re-ranking"),
    diversity_penalty: float = Query(default=0.06, ge=0.0, le=0.5, description="Section repetition penalty factor")
):
    """
    Phase 4 Part 4 Endpoint: GET /api/search
    GET-based helper endpoint for performing semantic similarity search queries.
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")

    try:
        response = search_service.search_vector_store(
            query=query,
            top_k=top_k or 5,
            study_id=study_id,
            enable_diversity=enable_diversity,
            diversity_penalty=diversity_penalty
        )

        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similarity search failed: {str(e)}")
