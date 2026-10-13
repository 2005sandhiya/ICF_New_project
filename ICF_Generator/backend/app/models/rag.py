from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class RAGRetrieveRequest(BaseModel):
    """
    Request schema for Phase 5 Part 1 RAG context retrieval endpoint POST /api/rag/retrieve.
    """
    query: str = Field(..., description="Natural language information requirement query")
    study_id: Optional[str] = Field(default="NCT00081328", description="Target clinical study identifier for evidence filtering")
    top_k: int = Field(default=5, description="Number of top relevant protocol evidence chunks to retrieve (default: 5)")
    min_score_threshold: float = Field(default=0.0, description="Optional minimum similarity score threshold (0.0 to 1.0)")
    enable_diversity: bool = Field(default=True, description="Enable section diversity re-ranking to prevent single section dominance")
    diversity_penalty: float = Field(default=0.06, description="Section repetition penalty factor for re-ranking")

class RAGSourceMetadata(BaseModel):
    """
    Source traceability metadata schema attached to each evidence item in RAG context.
    """
    filename: str = Field(..., description="Source document filename")
    page_number: Optional[int] = Field(default=None, description="Page number for PDF documents")
    source_reference: Optional[str] = Field(default=None, description="Human-readable section/field reference")
    source_field: Optional[str] = Field(default=None, description="JSON path or header reference")
    study_id: Optional[str] = Field(default=None, description="Study identifier")
    chunk_index: int = Field(..., description="1-indexed sequence number of chunk")

class RAGEvidenceItem(BaseModel):
    """
    Single grounded evidence chunk item inside the assembled RAG context package.
    """
    rank: int = Field(..., description="1-indexed rank of this evidence item in assembled context")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    section: str = Field(..., description="Protocol section name (e.g., eligibility, outcomes, description)")
    subsection: Optional[str] = Field(default=None, description="Subsection name if available")
    text: str = Field(..., description="Cleaned, grounded text snippet of protocol chunk")
    similarity_score: float = Field(..., description="Raw FAISS Inner-Product similarity score")
    reranking_score: Optional[float] = Field(default=None, description="Score after section diversity re-ranking")
    source: RAGSourceMetadata = Field(..., description="Complete source traceability metadata")

class RAGContextResponse(BaseModel):
    """
    API Response schema for POST /api/rag/retrieve.
    Represents the assembled grounded context package ready for downstream consumption.
    """
    original_query: str = Field(..., description="Original user query input string")
    processed_query: str = Field(..., description="Normalized search query string used for retrieval")
    study_id: Optional[str] = Field(default=None, description="Target study identifier")
    evidence: List[RAGEvidenceItem] = Field(default_factory=list, description="Assembled list of grounded protocol evidence chunks")
    evidence_count: int = Field(..., description="Total count of evidence chunks in assembled context")
    retrieval_status: str = Field(default="success", description="Status tag: 'success', 'fallback_below_threshold', 'empty', or 'error'")
    warning_message: Optional[str] = Field(default=None, description="Explanatory warning message if fallback or issue occurred")
