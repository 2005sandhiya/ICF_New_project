from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status

from app.services.file_validator import file_validator_service
from app.services.icf_workflow_service import icf_workflow_service
from app.services.template_service import MAX_TEMPLATE_BYTES


router = APIRouter(tags=["ICF Workflow"])


@router.post("/icf/workflow", status_code=status.HTTP_202_ACCEPTED)
async def start_icf_workflow(
    background_tasks: BackgroundTasks,
    study_id: str | None = Form(default=None),
    protocol: UploadFile | None = File(default=None),
    template: UploadFile | None = File(default=None),
    preferred_length: str | None = Form(default=None),
    custom_instructions: str | None = Form(default=None),
):
    if bool((study_id or "").strip()) == bool(protocol):
        raise HTTPException(400, "Choose one preloaded study or upload one protocol.")

    protocol_content = None
    template_content = None
    try:
        if protocol:
            protocol_content = await protocol.read(file_validator_service.max_file_size_bytes + 1)
            if len(protocol_content) > file_validator_service.max_file_size_bytes:
                raise HTTPException(413, "Protocol files must be no larger than 50 MB.")
        if template:
            template_content = await template.read(MAX_TEMPLATE_BYTES + 1)
            if len(template_content) > MAX_TEMPLATE_BYTES:
                raise HTTPException(413, "DOCX templates must be no larger than 10 MB.")

        job = icf_workflow_service.start(
            study_id=(study_id or "").strip() or None,
            filename=protocol.filename if protocol else None,
            protocol_content=protocol_content,
            template_filename=template.filename if template else None,
            template_content=template_content,
            preferred_length=(preferred_length or "").strip() or None,
            custom_instructions=(custom_instructions or "").strip() or None,
        )
        if not job:
            raise HTTPException(500, "Failed to initialize workflow job.")
        background_tasks.add_task(icf_workflow_service.run, job["job_id"])
        return job
    finally:
        if protocol:
            await protocol.close()
        if template:
            await template.close()


@router.get("/icf/workflow/{job_id}")
def get_icf_workflow(job_id: str):
    job = icf_workflow_service.get(job_id)
    if not job:
        raise HTTPException(404, "Workflow status is no longer available. Start the workflow again.")
    return job
