import logging
import re
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response
from app.models.icf import ICFGenerationRequest, ICFGenerationResponse, ICFExportRequest
from app.models.human_review import ReviewStatusEnum
from app.services.icf_generation_service import icf_generation_service
from app.services.human_review_service import content_hash, human_review_service
from app.services.pdf_generation_service import PDFConversionError, PDFDependencyMissing, pdf_generation_service
from app.services.template_service import TemplateError, template_service
from app.services.workflow_lock import study_lock

logger = logging.getLogger("icf_generator.icf_routes")
router = APIRouter(tags=["ICF Content Generation"])


@router.post("/icf/generate", response_model=ICFGenerationResponse, summary="Generate and validate both ICF drafts")
def generate_icf_endpoint(request: ICFGenerationRequest):
    raw_id = request.study_id or (
        request.analysis_facts.study_id if request.analysis_facts else ""
    ) or ""
    clean_id = raw_id.strip()
    if not clean_id:
        raise HTTPException(400, "Study ID is required for ICF content generation.")
    if request.previous_icf_draft and not (request.reviewer_feedback or "").strip():
        raise HTTPException(400, "Reviewer feedback is required for targeted ICF regeneration.")
    try:
        return icf_generation_service.generate_icf(request)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.error("ICF generation failed (%s)", type(exc).__name__)
        raise HTTPException(500, "ICF generation could not finish. The previous revision is unchanged. Please retry.") from exc


@router.get("/icf/export-capabilities")
def export_capabilities():
    return {"pdf": pdf_generation_service.status(), "docx": {"available": True}}


@router.get("/icf/revisions/{study_id}")
def revision_history(study_id: str):
    with study_lock(study_id):
        return {"study_id": study_id, "revisions": icf_generation_service.get_history(study_id),
                "reviews": human_review_service.get_history(study_id)}


@router.post("/icf/export/{study_id}", summary="Export the approved Patient-Facing ICF as PDF or editable DOCX")
def export_icf_docx_endpoint(study_id: str, export_type: Optional[str] = Query("patient_facing"),
    request_body: Optional[ICFExportRequest] = None,
    format: str = Query("docx", description="pdf or docx; legacy callers default to docx"),
    revision: Optional[int] = Query(None, ge=1)):
    clean_id = study_id.strip()
    if not clean_id:
        raise HTTPException(400, "Study ID is required for ICF document export.")
    try:
        with study_lock(clean_id):
            review = human_review_service.get_review(clean_id)
            if review.review_status != ReviewStatusEnum.APPROVED:
                raise HTTPException(409, f"Export blocked. Human review status is '{review.review_status.value}'. Must be APPROVED before exporting document.")
            raw_kind = (request_body.export_type if request_body and request_body.export_type else export_type) or "patient_facing"
            if raw_kind not in {"standard", "patient_friendly", "patient_facing"}:
                raise HTTPException(400, "Unsupported export_type. Must be 'patient_facing'.")
            kind = "patient_facing"
            if format not in {"pdf", "docx"}:
                raise HTTPException(400, "Unsupported format. Choose PDF or DOCX.")
            stored = icf_generation_service.get_stored_icf(clean_id)
            if not stored:
                raise HTTPException(404, "No ICF draft found. Generate, validate and review an ICF first.")
            for expected in [revision, request_body.revision if request_body else None]:
                if expected is not None and expected != stored.revision:
                    raise HTTPException(409, "The requested revision is stale. Reload and review the current revision.")
            if (review.approved_revision != stored.revision or review.approved_content_hash != content_hash(stored)
                    or not stored.validation_report or stored.validation_report.get("revision") != stored.revision):
                raise HTTPException(409, "Export blocked. The current revision must be validated and approved again.")
            selected = template_service.selection(clean_id)
            if selected != stored.template or review.approved_template_id != selected.template_id:
                raise HTTPException(409, "The template changed. Generate, validate and review a new revision before export.")
            template_service.read(clean_id, selected)
            if request_body:
                if request_body.icf_draft is not None and request_body.icf_draft != stored.icf_draft:
                    raise HTTPException(409, "Export content does not match the approved stored revision. Reload the current draft.")
            draft = stored.icf_draft
            if draft is None:
                raise HTTPException(404, "Patient-facing ICF draft not available for this study.")
            document = icf_generation_service.get_document(clean_id, stored.revision, kind)
            if not document:
                raise HTTPException(409, "The approved document is unavailable. Regenerate and review the draft again.")
            if format == "pdf":
                document = pdf_generation_service.generate_pdf(document, clean_id, draft, "patient_facing")
            safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", clean_id)[:100]
            filename = f"{safe_id}_Patient_Facing_ICF_v{stored.revision}.{format}"
            media = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            return Response(document, media_type=media, headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition, X-ICF-Revision",
                "X-ICF-Revision": str(stored.revision), "Cache-Control": "no-store"})
    except HTTPException:
        raise
    except PDFDependencyMissing as exc:
        raise HTTPException(503, str(exc)) from exc
    except PDFConversionError as exc:
        raise HTTPException(502, str(exc)) from exc
    except TemplateError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        logger.error("ICF export failed (%s)", type(exc).__name__)
        raise HTTPException(500, "Document export failed. Please retry; the review decision is unchanged.") from exc
