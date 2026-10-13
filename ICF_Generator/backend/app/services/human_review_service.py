from datetime import datetime, timezone
import logging
import hashlib
import json
from typing import Dict
from app.services.workflow_lock import study_lock


def content_hash(response):
    payload = {"study_id": response.study_id, "revision": response.revision,
               "template": response.template.model_dump() if response.template else None,
               "icf_draft": response.icf_draft.model_dump()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

from app.models.human_review import (
    HumanReviewState,
    HumanReviewUpdateRequest,
    ReviewStatusEnum,
)

logger = logging.getLogger("icf_generator.human_review_service")


class HumanReviewService:
    """
    Phase 6 Part 1: Service for managing Human Review workflow states per study.
    Maintains study-isolated review state using an in-memory repository.
    """

    def __init__(self):
        self._reviews: Dict[str, HumanReviewState] = {}
        self._history = {}

    def get_review(self, study_id: str) -> HumanReviewState:
        """
        Retrieves current review state for a given study_id.
        If no review exists yet for this study, returns an initial PENDING state.
        """
        clean_id = (study_id or "").strip()
        if clean_id in self._reviews:
            return self._reviews[clean_id]

        return HumanReviewState(
            study_id=clean_id,
            review_status=ReviewStatusEnum.PENDING,
            reviewer_comment=None,
            reviewed_at=None,
        )

    def update_review(
        self, study_id: str, request: HumanReviewUpdateRequest
    ) -> HumanReviewState:
        with study_lock(study_id):
            return self._update_review_locked(study_id, request)

    def _update_review_locked(self, study_id, request):
        """
        Updates review status and optional comments for a specific study.
        Sets reviewed_at timestamp when status is APPROVED or CHANGES_REQUESTED.
        """
        clean_id = (study_id or "").strip()
        from app.services.icf_generation_service import icf_generation_service
        stored = icf_generation_service.get_stored_icf(clean_id)
        expected_revision = getattr(request, "revision", None)
        if expected_revision is not None and (not stored or stored.revision != expected_revision):
            raise ValueError("Review revision is stale. Reload and review the current draft.")
        if stored and request.review_status == ReviewStatusEnum.APPROVED:
            from app.services.template_service import template_service
            selected_template = template_service.selection(clean_id)
            if not stored.template or stored.template.template_id != selected_template.template_id:
                raise ValueError("The selected template differs from this draft. Generate a new revision before approval.")
            if stored.template and stored.template.kind == "custom" and not getattr(request, "template_reviewed", False):
                raise ValueError("Review the populated template and confirm that retained wording was checked against the protocol before approval.")
            if not stored.validation_report or stored.validation_report.get("revision") != stored.revision:
                raise ValueError("Validate the current revision before approving it.")
            if stored.validation_report.get("overall_status") == "FAILED":
                raise ValueError("The current revision failed validation checks. Address validation issues before approving.")
            icf_generation_service.prepare_approved_documents(clean_id)

        if request.review_status == ReviewStatusEnum.PENDING:
            reviewed_at = None
        else:
            reviewed_at = datetime.now(timezone.utc).isoformat()

        updated_state = HumanReviewState(
            study_id=clean_id,
            review_status=request.review_status,
            reviewer_comment=request.reviewer_comment,
            reviewed_at=reviewed_at,
            revision=stored.revision if stored else None,
            approved_revision=stored.revision if stored and request.review_status == ReviewStatusEnum.APPROVED else None,
            approved_template_id=stored.template.template_id if stored and stored.template and request.review_status == ReviewStatusEnum.APPROVED else None,
            approved_content_hash=content_hash(stored) if stored and request.review_status == ReviewStatusEnum.APPROVED else None,
        )

        self._reviews[clean_id] = updated_state
        self._history.setdefault(clean_id, []).append(updated_state.model_copy(deep=True))
        logger.info(
            f"Updated review state for study '{clean_id}': status='{request.review_status.value}'"
        )
        return updated_state

    def reset_reviews(self):
        """
        Helper method to reset in-memory reviews for testing.
        """
        self._reviews.clear()
        self._history.clear()

    def get_history(self, study_id):
        return [review.model_copy(deep=True) for review in self._history.get(study_id.strip(), [])]


human_review_service = HumanReviewService()
