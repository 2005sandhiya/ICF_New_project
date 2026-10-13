import logging
from fastapi import APIRouter, HTTPException, status

from app.models.protocol_facts import ProtocolAnalysisRequest, ProtocolAnalysisResponse
from app.models.rag import RAGRetrieveRequest
from app.services.context_assembler import context_assembler
from app.services.protocol_analysis_agent import protocol_analysis_agent

logger = logging.getLogger("icf_generator.analysis_routes")

router = APIRouter(
    tags=["Protocol Analysis Agent"]
)

@router.post(
    "/protocol/analyze",
    response_model=ProtocolAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Grounded Protocol Evidence into Structured Study Facts",
    description="Phase 5 Part 2: Retrieves grounded protocol evidence via RAG context assembly and extracts structured study facts with fact-level source traceability."
)
def analyze_protocol(request: ProtocolAnalysisRequest) -> ProtocolAnalysisResponse:
    """
    Protocol Analysis Endpoint.
    
    1. Obtains grounded evidence context via Phase 5 Part 1 RAG retrieval layer.
    2. Passes evidence context to Protocol Analysis Agent.
    3. Returns structured study facts with grounding status and source chunk ID traceability.
    """
    try:
        # Step 1: Retrieve RAG evidence context
        rag_request = RAGRetrieveRequest(
            query=request.query,
            study_id=request.study_id,
            top_k=request.top_k,
            enable_diversity=True
        )
        rag_context = context_assembler.assemble_context(rag_request)

        # Step 2: Run Protocol Analysis Agent over grounded context
        facts = protocol_analysis_agent.analyze_context(rag_context)

        return ProtocolAnalysisResponse(
            study_id=request.study_id,
            facts=facts,
            evidence_used_count=rag_context.evidence_count,
            analysis_status="success",
            message="Protocol analysis complete."
        )
    except ValueError as ve:
        logger.warning(f"Validation error in protocol analysis: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error during protocol analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Protocol analysis failed: {str(e)}"
        )
