from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.protocol_facts import ProtocolFacts, FactStatusEnum
from app.models.template import TemplateSelection


class ICFSection(BaseModel):
    """
    Model representing an individual section of an Informed Consent Form (ICF) draft.
    """

    section_id: str = Field(
        ..., description="Unique section identifier (e.g., 'purpose', 'procedures')"
    )
    title: str = Field(..., description="Human-readable section title")
    content: str = Field(
        ...,
        description="Draft section text or 'Not provided in the study protocol.' placeholder",
    )
    source_evidence_ids: List[str] = Field(
        default_factory=list, description="List of supporting evidence chunk IDs"
    )
    status: FactStatusEnum = Field(
        default=FactStatusEnum.NOT_FOUND,
        description="Grounding status: SUPPORTED, NOT_FOUND, UNCERTAIN",
    )


class ICFDraft(BaseModel):
    """
    Model representing a complete Informed Consent Form (ICF) draft containing standard sections.
    """

    sections: List[ICFSection] = Field(
        default_factory=list, description="List of 13 standard ICF sections"
    )
    revision: int = Field(default=1, description="Revision version number (e.g. 1, 2, 3)")


class ICFGenerationRequest(BaseModel):
    """
    API Request schema for POST /api/icf/generate.
    """

    study_id: str = Field(default="NCT00081328", description="Target study identifier")
    analysis_facts: Optional[ProtocolFacts] = Field(
        default=None, description="Structured study facts from Phase 5 Part 2"
    )
    generate_patient_friendly: bool = Field(
        default=True,
        description="Deprecated/Default True: Single patient-facing ICF is always generated",
    )
    reviewer_feedback: Optional[str] = Field(
        default=None,
        description="Human reviewer feedback/instructions for targeted draft revision",
    )
    previous_icf_draft: Optional[ICFDraft] = Field(
        default=None, description="Previous ICF draft to be revised"
    )
    revision: Optional[int] = Field(
        default=None, description="Target or previous revision number"
    )
    preferred_length: Optional[str] = Field(
        default=None, description="Preferred document length page range (e.g. '4–6 pages')"
    )
    custom_instructions: Optional[str] = Field(
        default=None, description="Optional user style and formatting instructions"
    )


class ICFGenerationResponse(BaseModel):
    """
    API Response schema for POST /api/icf/generate.
    """

    study_id: str = Field(..., description="Target study identifier")
    template: Optional[TemplateSelection] = None
    document_preview: dict[str, str] = Field(default_factory=dict)
    validation_report: Optional[dict] = None
    icf_draft: ICFDraft = Field(..., description="Patient-Facing Informed Consent Form draft")
    patient_friendly_icf: Optional[ICFDraft] = Field(
        default=None, description="Alias/reference to the Patient-Facing Informed Consent Form draft"
    )
    revision: int = Field(default=1, description="Revision version number (e.g. 1, 2, 3)")
    generation_status: str = Field(
        default="success", description="Status tag: 'success', 'partial', or 'error'"
    )
    message: str = Field(
        default="ICF content generation complete.", description="Explanatory response message"
    )


class ICFExportRequest(BaseModel):
    """
    API Request schema for POST /api/icf/export/{study_id}.
    """

    export_type: Optional[str] = Field(
        default="patient_facing",
        description="Type of document to export: 'patient_facing' (default)",
    )
    icf_draft: Optional[ICFDraft] = Field(
        default=None, description="Optional explicit ICF draft override to export"
    )
    patient_friendly_icf: Optional[ICFDraft] = Field(
        default=None, description="Optional explicit patient-friendly ICF draft override"
    )
    revision: Optional[int] = Field(default=None, ge=1)


