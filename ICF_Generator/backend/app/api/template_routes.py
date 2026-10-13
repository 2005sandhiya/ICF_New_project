from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from app.models.human_review import HumanReviewUpdateRequest, ReviewStatusEnum
from app.models.template import TemplateSelection
from app.services.human_review_service import human_review_service
from app.services.template_service import MAX_TEMPLATE_BYTES, TemplateError, template_service
from app.services.workflow_lock import study_lock

router = APIRouter(tags=["ICF Templates"])


@router.get("/icf/template/{study_id}", response_model=TemplateSelection)
def get_template(study_id: str):
    try:
        with study_lock(study_id):
            return template_service.selection(study_id)
    except TemplateError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/icf/template/{study_id}", response_model=TemplateSelection)
async def upload_template(study_id: str, file: UploadFile = File(...)):
    try:
        content = await file.read(MAX_TEMPLATE_BYTES + 1)
        if len(content) > MAX_TEMPLATE_BYTES:
            raise HTTPException(413, "DOCX templates must be no larger than 10 MB.")
        with study_lock(study_id):
            selected = template_service.upload(study_id, file.filename, content)
            human_review_service.update_review(study_id, HumanReviewUpdateRequest(review_status=ReviewStatusEnum.PENDING))
            return selected
    except TemplateError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, "Template storage failed. Please try again.") from exc
    finally:
        await file.close()


@router.delete("/icf/template/{study_id}", response_model=TemplateSelection)
def remove_template(study_id: str):
    try:
        with study_lock(study_id):
            selected = template_service.remove(study_id)
            human_review_service.update_review(study_id, HumanReviewUpdateRequest(review_status=ReviewStatusEnum.PENDING))
            return selected
    except TemplateError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, "Template removal failed. Please try again.") from exc


@router.get("/icf/template/{study_id}/file")
def download_template(study_id: str):
    try:
        with study_lock(study_id):
            selected = template_service.selection(study_id)
            content = template_service.read(study_id, selected)
        if content is None:
            raise HTTPException(404, "The default layout is built into the DOCX generator; it is not an uploaded file.")
        return Response(content, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": 'attachment; filename="ICF_template.docx"'})
    except TemplateError as exc:
        raise HTTPException(409, str(exc)) from exc
