import logging
from fastapi import APIRouter, HTTPException, status

from app.models.human_review import (
    HumanReviewState,
    HumanReviewUpdateRequest,
    ReviewStatusEnum,
)
from app.services.human_review_service import human_review_service

logger = logging.getLogger("icf_generator.review_routes")

router = APIRouter(tags=["Human Review Workflow"])


@router.get(
    "/icf/review/{study_id}",
    response_model=HumanReviewState,
    summary="Get Human Review State for a Study",
    description="Fetches current review status, optional reviewer comments, and UTC review timestamp for the specified study_id.",
)
def get_human_review_endpoint(study_id: str) -> HumanReviewState:
    """
    GET /api/icf/review/{study_id}
    Returns current human review state for requested study.
    """
    clean_id = (study_id or "").strip()
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A non-empty study_id path parameter is required.",
        )

    return human_review_service.get_review(clean_id)


@router.post(
    "/icf/review/{study_id}",
    response_model=HumanReviewState,
    summary="Update Human Review State for a Study (POST)",
    description="Updates review status (PENDING, APPROVED, CHANGES_REQUESTED) and reviewer comments for the specified study_id.",
)
@router.put(
    "/icf/review/{study_id}",
    response_model=HumanReviewState,
    summary="Update Human Review State for a Study (PUT)",
    description="Updates review status (PENDING, APPROVED, CHANGES_REQUESTED) and reviewer comments for the specified study_id.",
)
def update_human_review_endpoint(
    study_id: str, request: HumanReviewUpdateRequest
) -> HumanReviewState:
    """
    POST / PUT /api/icf/review/{study_id}
    Updates human review status and comments for requested study.
    """
    clean_id = (study_id or "").strip()
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A non-empty study_id path parameter is required.",
        )

    if request.review_status == ReviewStatusEnum.CHANGES_REQUESTED:
        if not request.reviewer_comment or not request.reviewer_comment.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reviewer comment is required when status is CHANGES_REQUESTED.",
            )

    try:
        return human_review_service.update_review(clean_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

