from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ReviewStatusEnum(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class HumanReviewState(BaseModel):
    study_id: str = Field(..., description="Target study identifier")
    review_status: ReviewStatusEnum = Field(
        ReviewStatusEnum.PENDING, description="Current human review status"
    )
    reviewer_comment: Optional[str] = Field(
        None, description="Optional reviewer notes or feedback"
    )
    reviewed_at: Optional[str] = Field(
        None, description="ISO 8601 UTC timestamp of review action"
    )
    revision: Optional[int] = None
    approved_revision: Optional[int] = None
    approved_template_id: Optional[str] = None
    approved_content_hash: Optional[str] = None


class HumanReviewUpdateRequest(BaseModel):
    review_status: ReviewStatusEnum = Field(..., description="Target review status")
    reviewer_comment: Optional[str] = Field(
        None, description="Optional reviewer feedback or comments"
    )
    revision: Optional[int] = Field(None, ge=1)
    template_reviewed: bool = False
