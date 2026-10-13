from typing import List
from pydantic import BaseModel, Field


class TemplateSelection(BaseModel):
    study_id: str
    template_id: str = "builtin-v1"
    filename: str = "Default ICF layout"
    kind: str = "default"
    sha256: str = "builtin-v1"
    mapped_sections: List[str] = Field(default_factory=list)
    missing_sections: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
