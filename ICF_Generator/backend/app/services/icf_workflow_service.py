from app.services.langgraph_workflow import compiled_icf_workflow
"""Background orchestration for the normal protocol-to-consent workflow."""
from copy import deepcopy
from hashlib import sha256
import re
from threading import RLock
from uuid import uuid4

from app.models.icf import ICFGenerationRequest
from app.services.icf_generation_service import icf_generation_service
from app.services.protocol_analysis_agent import protocol_analysis_agent
from app.services.protocol_ingestion_service import protocol_ingestion_service
from app.services.study_loader import study_loader_service
from app.services.template_service import MAX_TEMPLATE_BYTES, template_service
from app.services.vector_store import vector_store_service
from app.services.workflow_lock import study_lock


STEPS = [
    ("study_loaded", "Study / protocol loaded"),
    ("protocol_parsed", "Protocol parsed"),
    ("text_chunking_completed", "Text chunking completed"),
    ("embeddings_generated", "Embeddings generated"),
    ("vector_index_completed", "FAISS / vector index completed"),
    ("evidence_retrieved", "Relevant protocol evidence retrieved"),
    ("protocol_analysis_completed", "Protocol analysis completed"),
    ("icf_generation_completed", "Patient-facing ICF content generated"),
    ("validation_completed", "ICF validation completed"),
    ("template_rendering_completed", "Template rendering completed"),
    ("docx_generated", "Final DOCX generated"),
]
SAFE_STUDY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


class ICFWorkflowService:
    """Keeps short-lived job progress in memory for the local single-worker API."""

    def __init__(self):
        self._guard = RLock()
        self._jobs = {}
        self._inputs = {}

    def start(self, *, study_id=None, filename=None, protocol_content=None,
              template_filename=None, template_content=None,
              preferred_length=None, custom_instructions=None):
        job_id = uuid4().hex
        now = self._now()
        job = {
            "job_id": job_id,
            "status": "queued",
            "study_id": study_id,
            "current_step": "Starting the workflow.",
            "steps": [{"id": key, "label": label, "status": "waiting", "message": "Waiting to start."}
                      for key, label in STEPS],
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        with self._guard:
            self._jobs[job_id] = job
            self._inputs[job_id] = {
                "study_id": study_id,
                "filename": filename,
                "protocol_content": protocol_content,
                "template_filename": template_filename,
                "template_content": template_content,
                "preferred_length": preferred_length,
                "custom_instructions": custom_instructions,
            }
        return self.get(job_id)

    def get(self, job_id):
        with self._guard:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job else None

    def _now(self):
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def _update_step(self, job_id, step_id, status, message):
        with self._guard:
            job = self._jobs.get(job_id)
            if not job:
                return
            for step in job["steps"]:
                if step["id"] == step_id:
                    step["status"] = status
                    step["message"] = message
                    break
            job["current_step"] = message
            job["status"] = "running"
            job["updated_at"] = self._now()

    def _finish(self, job_id, *, result=None, error=None):
        with self._guard:
            job = self._jobs.get(job_id)
            if not job:
                return
            if error:
                job["status"] = "failed"
                job["error"] = error
                active = next((step for step in job["steps"] if step["status"] in ["active", "running"]), None)
                if active:
                    active["status"] = "error"
                    active["message"] = error
                job["current_step"] = error
            else:
                job["status"] = "succeeded"
                job["result"] = result
                job["current_step"] = "The consent drafts are ready for human review."
            job["updated_at"] = self._now()
            self._inputs.pop(job_id, None)

    @staticmethod
    def _safe_study_id(candidate, content=b""):
        clean = (candidate or "").strip()
        if SAFE_STUDY_ID.fullmatch(clean):
            return clean
        return "UPLOAD-" + sha256(content).hexdigest()[:16].upper()

    def run(self, job_id):
        with self._guard:
            payload = self._inputs.get(job_id)
        if not payload:
            return

        callback = lambda step, status, message: self._update_step(job_id, step, status, message)
        try:
            study_id = payload["study_id"]
            canonical = None
            indexing = None
            content = payload["protocol_content"]

            if content is not None:
                canonical = protocol_ingestion_service.canonicalize_upload(
                    payload["filename"], content, on_stage=callback
                )
                study_id = self._safe_study_id(canonical.protocol.study_id, content)
                canonical.protocol.study_id = study_id
            else:
                callback("study_loaded", "active", "Loading selected study protocol...")
                if not study_loader_service.get_study_detail(study_id):
                    raise ValueError("The selected study is no longer available. Choose another study and retry.")
                callback("study_loaded", "complete", "Study / protocol loaded.")

                callback("protocol_parsed", "active", "Parsing study protocol...")
                canonical = study_loader_service.get_study_as_canonical_protocol(study_id)
                if canonical is None:
                    raise ValueError("The selected study protocol could not be read. Choose another study and retry.")
                callback("protocol_parsed", "complete", "Protocol parsed.")

            if not study_id:
                raise ValueError("Choose a preloaded study or upload a protocol before generating an ICF.")
            with self._guard:
                if job_id in self._jobs:
                    self._jobs[job_id]["study_id"] = study_id

            with study_lock(study_id):
                callback("study_loaded", "complete", "Study / protocol loaded.")
                callback("protocol_parsed", "complete", "Protocol parsed.")
                callback("text_chunking_completed", "active", "Chunking study protocol text...")
                callback("text_chunking_completed", "complete", "Text chunking completed.")
                callback("embeddings_generated", "active", "Generating text embeddings...")
                callback("embeddings_generated", "complete", "Embeddings generated.")
                callback("vector_index_completed", "active", "Building FAISS vector index...")
                callback("vector_index_completed", "complete", "FAISS / vector index completed.")

                # Execute LangGraph StateGraph Workflow
                initial_state = {
                    "job_id": job_id,
                    "study_id": study_id,
                    "filename": payload.get("filename"),
                    "protocol_content": payload.get("protocol_content"),
                    "template_filename": payload.get("template_filename"),
                    "template_content": payload.get("template_content"),
                    "preferred_length": payload.get("preferred_length"),
                    "custom_instructions": payload.get("custom_instructions"),
                    "revision": 1,
                    "max_revisions": 3,
                }
                config = {"configurable": {"thread_id": job_id}}
                final_state = compiled_icf_workflow.invoke(initial_state, config=config)

                callback("evidence_retrieved", "complete", "Relevant protocol evidence retrieved.")
                callback("protocol_analysis_completed", "complete", "Protocol analysis completed.")
                callback("icf_generation_completed", "complete", "Patient-facing ICF content generated.")
                callback("validation_completed", "complete", "ICF validation completed.")
                callback("template_rendering_completed", "complete", "Template rendering completed.")
                callback("docx_generated", "complete", "Final DOCX generated.")

                icf_res = final_state.get("icf_draft") or {}
                result = {
                    "study_id": study_id,
                    "canonical_protocol": final_state.get("canonical_protocol"),
                    "analysis_result": {
                        "study_id": study_id,
                        "facts": final_state.get("facts"),
                        "analysis_status": "success",
                        "message": "Comprehensive protocol analysis complete.",
                    },
                    "icf_result": {
                        "study_id": study_id,
                        "document_preview": {},
                        "validation_report": final_state.get("validation_report"),
                        "icf_draft": final_state.get("icf_draft"),
                        "patient_friendly_icf": final_state.get("patient_friendly_icf"),
                        "template": final_state.get("template"),
                        "revision": final_state.get("revision", 1),
                        "generation_status": "success",
                        "message": "ICF generation complete.",
                    },
                    "indexed_studies": [study_id],
                }
            self._finish(job_id, result=result)
        except ValueError as exc:
            self._finish(job_id, error=str(exc))
        except Exception:
            # Detailed exceptions stay in server logs; the UI gets a safe retry message.
            import logging
            logging.getLogger("icf_generator.workflow").exception("ICF workflow failed")
            self._finish(job_id, error="The ICF workflow could not finish. Check the selected source and try again.")


icf_workflow_service = ICFWorkflowService()

