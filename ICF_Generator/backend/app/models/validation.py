from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.models.icf import ICFDraft
from app.models.protocol_facts import ProtocolFacts

class ValidationCheckResult(BaseModel):
    """
    Model representing the result of an individual validation check.
    """
    check_id: str = Field(..., description="Unique check identifier (e.g., 'groundedness', 'omission', 'not_found_integrity', 'readability', 'traceability')")
    check_name: str = Field(..., description="Human-readable check title")
    status: str = Field("PASS", description="Check status: 'PASS', 'FAIL', or 'WARNING'")
    score: float = Field(100.0, description="Check score percentage (0.0 to 100.0)")
    details: str = Field("", description="Detailed findings or summary explanation")
    flagged_items: List[str] = Field(default_factory=list, description="List of specific flagged issues or ungrounded statements")

class ICFValidationReport(BaseModel):
    """
    Comprehensive validation report model for an Informed Consent Form (ICF) draft.
    """
    study_id: str = Field(..., description="Target study identifier")
    revision: int = Field(1, description="Draft revision number validated")
    overall_status: str = Field("PASSED", description="Overall validation status: 'PASSED', 'FAILED', or 'REQUIRES_REVIEW'")
    overall_score: float = Field(100.0, description="Overall compliance score percentage (0.0 to 100.0)")
    groundedness_score: float = Field(100.0, description="Groundedness and hallucination-free score (0.0 to 100.0)")
    completeness_score: float = Field(100.0, description="Fact completeness and coverage score (0.0 to 100.0)")
    readability_score: float = Field(100.0, description="Patient readability score (0.0 to 100.0)")
    traceability_score: float = Field(100.0, description="Source evidence traceability score (0.0 to 100.0)")
    checks: List[ValidationCheckResult] = Field(default_factory=list, description="List of individual validation check results")
    recommendations: List[str] = Field(default_factory=list, description="List of actionable recommendations for ICF refinement")

class ICFValidationRequest(BaseModel):
    """
    API Request schema for POST /api/icf/validate.
    """
    study_id: str = Field("NCT00081328", description="Target study identifier")
    icf_draft: ICFDraft = Field(..., description="Structured baseline ICF draft to validate")
    patient_friendly_icf: Optional[ICFDraft] = Field(None, description="Optional patient-friendly ICF draft to validate")
    protocol_facts: Optional[ProtocolFacts] = Field(None, description="Structured study facts from Phase 5 Part 2")
