import logging
from fastapi import APIRouter, HTTPException, status

from app.models.validation import ICFValidationRequest, ICFValidationReport
from app.services.validation_agent import validation_agent
from app.services.icf_generation_service import icf_generation_service
from app.services.workflow_lock import study_lock
from app.models.validation import ValidationCheckResult

logger = logging.getLogger("icf_generator.validation_routes")

router = APIRouter(tags=["ICF Compliance & Validation"])

@router.post(
    "/icf/validate",
    response_model=ICFValidationReport,
    summary="Validate ICF Draft Compliance & Groundedness",
    description="Consumes generated ICF draft and protocol facts to execute multi-dimensional compliance, groundedness, completeness, readability, and traceability validation."
)
def validate_icf_endpoint(request: ICFValidationRequest) -> ICFValidationReport:
    """
    POST /api/icf/validate
    
    Performs multi-dimensional compliance validation on generated ICF draft.
    """
    try:
        if not request.icf_draft or not request.icf_draft.sections or len(request.icf_draft.sections) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid ICF draft with sections is required for validation."
            )

        logger.info(f"Received ICF validation request for study '{request.study_id}'")
        with study_lock(request.study_id):
            stored = icf_generation_service.get_stored_icf(request.study_id)
            if stored and (request.icf_draft != stored.icf_draft or
                    (request.patient_friendly_icf is not None and request.patient_friendly_icf != stored.patient_friendly_icf)):
                raise HTTPException(409, "Validation content does not match the current stored revision.")
            if request.protocol_facts and request.protocol_facts.study_id != request.study_id:
                raise HTTPException(400, "Protocol facts belong to a different study.")
            if stored:
                request = request.model_copy(update={"patient_friendly_icf": stored.patient_friendly_icf,
                    "protocol_facts": icf_generation_service._facts.get(request.study_id)})
            report = validation_agent.validate_icf(request)
            report.revision = request.icf_draft.revision
            if stored and stored.template and stored.template.warnings:
                report.checks.append(ValidationCheckResult(check_id="template_structure", check_name="Template structure and retained wording",
                    status="WARNING", details=" ".join(stored.template.warnings), flagged_items=stored.template.missing_sections))
                report.recommendations.extend(stored.template.warnings)
                if report.overall_status == "PASSED":
                    report.overall_status = "REQUIRES_REVIEW"
            icf_generation_service.set_validation(request.study_id, report)
            return report

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ICF validation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during ICF validation: {str(e)}"
        )
