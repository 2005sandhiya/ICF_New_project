from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class SourceReference(BaseModel):
    """
    Source provenance metadata for extracted canonical fields.
    """
    type: str = Field(..., description="Source format: pdf, docx, txt, json")
    location: Optional[str] = Field(default=None, description="Page number e.g. 'Page 4' or JSON field path e.g. 'protocolSection.designModule.phases'")
    section_name: Optional[str] = Field(default=None, description="Heading or section identifier")

class ObjectivesInfo(BaseModel):
    primary: List[str] = Field(default_factory=list, description="Primary study objectives")
    secondary: List[str] = Field(default_factory=list, description="Secondary study objectives")

class EligibilityInfo(BaseModel):
    inclusion: List[str] = Field(default_factory=list, description="Inclusion criteria points")
    exclusion: List[str] = Field(default_factory=list, description="Exclusion criteria points")
    raw_text: Optional[str] = Field(default=None, description="Raw unparsed eligibility criteria text")
    minimum_age: Optional[str] = Field(default=None, description="Minimum age e.g. '18 Years'")
    maximum_age: Optional[str] = Field(default=None, description="Maximum age e.g. '75 Years'")
    sex: Optional[str] = Field(default=None, description="Target sex e.g. ALL, MALE, FEMALE")
    healthy_volunteers: Optional[bool] = Field(default=None, description="Accepts healthy volunteers")

class OutcomesInfo(BaseModel):
    primary: List[str] = Field(default_factory=list, description="Primary outcome measures / endpoints")
    secondary: List[str] = Field(default_factory=list, description="Secondary outcome measures / endpoints")

class ProtocolSectionItem(BaseModel):
    section_name: str = Field(..., description="Canonical section name e.g. 'eligibility', 'procedures', 'risks'")
    heading: str = Field(..., description="Original heading text in document")
    content: str = Field(..., description="Extracted text section content")
    source_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Source page or path metadata")

class CanonicalProtocol(BaseModel):
    """
    Common Internal Protocol Model (Phase 3 Part 3).
    Deterministic intermediate representation for downstream RAG and ICF generation.
    """
    study_id: Optional[str] = Field(default=None, description="NCT ID or protocol ID")
    title: Optional[str] = Field(default=None, description="Brief study title")
    official_title: Optional[str] = Field(default=None, description="Official protocol title")
    study_type: Optional[str] = Field(default=None, description="e.g. Interventional, Observational")
    phase: Optional[str] = Field(default=None, description="Trial phase e.g. Phase 1, Phase 2, Phase 3")
    overall_status: Optional[str] = Field(default=None, description="Recruitment status e.g. COMPLETED, RECRUITING")
    conditions: List[str] = Field(default_factory=list, description="Target conditions/diseases")
    interventions: List[Dict[str, Any]] = Field(default_factory=list, description="Interventions or drugs")
    comparators: List[str] = Field(default_factory=list, description="Comparator arms or placebo controls")
    objectives: ObjectivesInfo = Field(default_factory=ObjectivesInfo)
    eligibility: EligibilityInfo = Field(default_factory=EligibilityInfo)
    population: Optional[str] = Field(default=None, description="Target study population description")
    duration: Optional[str] = Field(default=None, description="Trial duration description")
    procedures: List[str] = Field(default_factory=list, description="Study procedures or visits")
    outcomes: OutcomesInfo = Field(default_factory=OutcomesInfo)
    risks: List[str] = Field(default_factory=list, description="Known risks or discomforts")
    benefits: List[str] = Field(default_factory=list, description="Potential benefits")
    source_sections: List[ProtocolSectionItem] = Field(default_factory=list, description="Extracted section blocks")
    additional_information: Dict[str, Any] = Field(default_factory=dict, description="Preserved extra metadata")

class CanonicalProtocolResponse(BaseModel):
    """
    API Response schema for Phase 3 Part 3 Canonicalization.
    """
    status: str = Field(default="canonicalized", description="Processing status tag")
    source: Dict[str, Any] = Field(..., description="Source file metadata e.g. filename, type")
    protocol: CanonicalProtocol = Field(..., description="Canonical protocol object")
    extracted_fields_count: int = Field(default=0, description="Count of populated canonical fields")
    missing_fields_count: int = Field(default=0, description="Count of null/empty canonical fields")
    message: str = Field(default="Canonical protocol extraction successful.", description="Status message")
