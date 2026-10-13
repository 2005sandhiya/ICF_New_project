from enum import Enum
from typing import List, Optional, Generic, TypeVar, Any, Dict
from pydantic import BaseModel, Field

T = TypeVar('T')

class FactStatusEnum(str, Enum):
    """
    Grounding status tag for an extracted study fact.
    """
    SUPPORTED = "SUPPORTED"
    NOT_FOUND = "NOT_FOUND"
    UNCERTAIN = "UNCERTAIN"

class TraceableFact(BaseModel, Generic[T]):
    """
    Generic model for an individual extracted protocol fact with source evidence traceability.
    """
    value: Optional[T] = Field(default=None, description="Extracted fact value or None if not found")
    status: FactStatusEnum = Field(default=FactStatusEnum.NOT_FOUND, description="Grounding status: SUPPORTED, NOT_FOUND, UNCERTAIN")
    source_evidence_ids: List[str] = Field(default_factory=list, description="List of supporting chunk IDs (e.g. NCT00081328_eligibility_014)")
    notes: Optional[str] = Field(default=None, description="Optional explanatory notes or contextual details")

class CategorizedFactList(BaseModel):
    """
    Fact structure for objectives or outcomes categorized into primary vs secondary.
    """
    primary: List[TraceableFact[str]] = Field(default_factory=list, description="Primary items")
    secondary: List[TraceableFact[str]] = Field(default_factory=list, description="Secondary items")

class EligibilityFacts(BaseModel):
    """
    Fact structure for eligibility criteria categorized into inclusion vs exclusion.
    """
    inclusion: List[TraceableFact[str]] = Field(default_factory=list, description="Inclusion criteria")
    exclusion: List[TraceableFact[str]] = Field(default_factory=list, description="Exclusion criteria")

class ProtocolFacts(BaseModel):
    """
    Comprehensive structured study facts schema extracted from grounded protocol evidence.
    """
    study_id: Optional[str] = Field(default=None, description="Target study identifier")
    study_title: TraceableFact[str] = Field(default_factory=lambda: TraceableFact[str](status=FactStatusEnum.NOT_FOUND), description="Official study title")
    study_type: TraceableFact[str] = Field(default_factory=lambda: TraceableFact[str](status=FactStatusEnum.NOT_FOUND), description="Study type (e.g., Interventional, Observational)")
    phase: TraceableFact[str] = Field(default_factory=lambda: TraceableFact[str](status=FactStatusEnum.NOT_FOUND), description="Clinical trial phase (e.g., Phase 3)")
    condition: List[TraceableFact[str]] = Field(default_factory=list, description="Target medical condition(s)")
    population: TraceableFact[str] = Field(default_factory=lambda: TraceableFact[str](status=FactStatusEnum.NOT_FOUND), description="Target patient population description")
    interventions: List[TraceableFact[str]] = Field(default_factory=list, description="Interventions or treatments studied")
    comparators: List[TraceableFact[str]] = Field(default_factory=list, description="Comparator or control arms")
    objectives: CategorizedFactList = Field(default_factory=CategorizedFactList, description="Categorized primary and secondary objectives")
    eligibility: EligibilityFacts = Field(default_factory=EligibilityFacts, description="Categorized inclusion and exclusion eligibility criteria")
    duration: TraceableFact[str] = Field(default_factory=lambda: TraceableFact[str](status=FactStatusEnum.NOT_FOUND), description="Total study duration or treatment period")
    procedures: List[TraceableFact[str]] = Field(default_factory=list, description="Key study procedures and evaluations")
    outcomes: CategorizedFactList = Field(default_factory=CategorizedFactList, description="Categorized primary and secondary endpoints/outcomes")
    risks: List[TraceableFact[str]] = Field(default_factory=list, description="Possible study risks, adverse events, or side effects")
    benefits: List[TraceableFact[str]] = Field(default_factory=list, description="Anticipated direct or indirect study benefits")
    additional_facts: List[TraceableFact[str]] = Field(default_factory=list, description="Other grounded protocol facts")

class ProtocolAnalysisRequest(BaseModel):
    """
    API Request schema for POST /api/protocol/analyze.
    """
    study_id: str = Field(default="NCT00081328", description="Target study identifier")
    query: str = Field(default="Analyze protocol evidence for ICF generation", description="Natural language analysis requirement")
    top_k: int = Field(default=5, description="Number of evidence chunks to retrieve from RAG context")

class ProtocolAnalysisResponse(BaseModel):
    """
    API Response schema for POST /api/protocol/analyze.
    """
    study_id: str = Field(..., description="Target study identifier")
    facts: ProtocolFacts = Field(..., description="Extracted grounded protocol facts")
    evidence_used_count: int = Field(..., description="Count of RAG evidence chunks supplied to analysis agent")
    analysis_status: str = Field(default="success", description="Status tag: 'success', 'partial', or 'error'")
    message: str = Field(default="Protocol analysis complete.", description="Explanatory detail message")
