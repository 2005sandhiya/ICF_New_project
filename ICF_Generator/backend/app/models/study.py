from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class StudySummary(BaseModel):
    """
    Summary view of a clinical trial study for dropdown listings.
    """
    study_id: str = Field(..., description="Unique study identifier (e.g., NCT ID)")
    brief_title: str = Field(..., description="Short study title")
    official_title: Optional[str] = Field(None, description="Full official protocol title")
    overall_status: Optional[str] = Field("UNKNOWN", description="Current recruitment/study status")
    conditions: List[str] = Field(default_factory=list, description="Target conditions or diseases")
    study_type: Optional[str] = Field("UNKNOWN", description="e.g. Interventional, Observational")
    phases: List[str] = Field(default_factory=list, description="Trial phases e.g. Phase 1, Phase 2")
    enrollment: Optional[int] = Field(None, description="Target participant count")
    source_file: str = Field(..., description="Source JSON filename")

class InterventionInfo(BaseModel):
    name: str = Field(..., description="Intervention or drug name")
    type: Optional[str] = Field(None, description="e.g. DRUG, DEVICE, BEHAVIORAL")
    description: Optional[str] = Field(None, description="Detailed intervention description")

class StudyDetail(StudySummary):
    """
    Detailed protocol view including summary, descriptions, eligibility, and raw protocol JSON.
    """
    brief_summary: Optional[str] = Field(None, description="Brief summary of the study")
    detailed_description: Optional[str] = Field(None, description="Detailed study description")
    interventions: List[InterventionInfo] = Field(default_factory=list, description="List of study interventions")
    eligibility_criteria: Optional[str] = Field(None, description="Raw eligibility criteria text")
    minimum_age: Optional[str] = Field(None, description="Minimum age requirement")
    maximum_age: Optional[str] = Field(None, description="Maximum age requirement")
    sex: Optional[str] = Field(None, description="Sex criteria e.g. ALL, MALE, FEMALE")
    healthy_volunteers: Optional[bool] = Field(None, description="Accepts healthy volunteers")
    raw_protocol: Dict[str, Any] = Field(default_factory=dict, description="Original protocol JSON structure")

class ProtocolMetadataResponse(BaseModel):
    """
    Response schema for Phase 3 Part 1 Protocol Validation & Metadata Extraction.
    """
    valid: bool = Field(True, description="Validation success status")
    filename: str = Field(..., description="Original sanitized filename")
    file_type: str = Field(..., description="Detected file type e.g. pdf, docx, txt, json")
    file_size_bytes: int = Field(..., description="Size of uploaded file in bytes")
    file_size_display: str = Field(..., description="Human-readable file size display")
    page_count: Optional[int] = Field(None, description="Extracted page count for PDF files, null for other formats")
    uploaded_at: str = Field(..., description="ISO 8601 upload timestamp")
    storage_id: str = Field(..., description="Unique safe storage identifier")
    status: str = Field("validated", description="Processing status")
    message: str = Field("File validation successful", description="Status or detail message")

class PageContent(BaseModel):
    """
    Page-level extracted text block for PDF documents.
    """
    page_number: int = Field(..., description="1-indexed page number")
    text: str = Field(..., description="Extracted normalized text for this page")

class ExtractedTextResponse(BaseModel):
    """
    Response schema for Phase 3 Part 2 Document Processing & Text Extraction.
    """
    status: str = Field(..., description="Processing status: 'processed', 'no_extractable_text', or 'error'")
    filename: str = Field(..., description="Original sanitized filename")
    document_type: str = Field(..., description="Document format: pdf, docx, txt, json")
    file_size_display: str = Field(..., description="Human-readable file size")
    page_count: Optional[int] = Field(None, description="Page count for PDF files")
    full_text: str = Field("", description="Full normalized extracted protocol text")
    text_preview: str = Field("", description="Preview snippet (first 2,000 characters) for UI display")
    character_count: int = Field(0, description="Total characters extracted")
    word_count: int = Field(0, description="Total words extracted")
    pages: List[PageContent] = Field(default_factory=list, description="Page-by-page text blocks for PDFs")
    storage_id: Optional[str] = Field(None, description="Storage reference ID")
    message: str = Field("Text extraction successful.", description="User-facing detail message")
