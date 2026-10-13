from types import SimpleNamespace

from app.models.protocol_facts import ProtocolFacts
from app.services import icf_workflow_service as workflow_module
from app.services.icf_workflow_service import ICFWorkflowService


class Dumpable:
    def __init__(self, payload):
        self.payload = payload

    def model_dump(self, mode="python"):
        return self.payload


def fake_canonical(study_id=None):
    protocol = SimpleNamespace(study_id=study_id)
    def model_dump(mode="python"):
        return {"protocol": {"study_id": protocol.study_id}, "source": {"filename": "protocol.txt"}}
    return SimpleNamespace(protocol=protocol, model_dump=model_dump)


def configure_generation(monkeypatch, expected_study_id):
    facts = ProtocolFacts(study_id=expected_study_id)
    monkeypatch.setattr(workflow_module.protocol_analysis_agent, "assemble_comprehensive_facts", lambda study_id: facts)
    from app.models.icf import ICFDraft, ICFSection, ICFGenerationResponse
    from app.models.validation import ICFValidationReport
    def generate(request):
        assert request.study_id == expected_study_id
        assert request.analysis_facts.study_id == expected_study_id
        draft = ICFDraft(study_id=expected_study_id, revision=1, sections=[ICFSection(section_id="purpose", title="Purpose", content="Study purpose.")])
        val = ICFValidationReport(study_id=expected_study_id, revision=1, overall_status="PASSED")
        return ICFGenerationResponse(
            study_id=expected_study_id,
            revision=1,
            icf_draft=draft,
            patient_friendly_icf=draft,
            validation_report=val.model_dump(mode="json"),
            generation_status="success",
            message="Generated"
        )
    monkeypatch.setattr(workflow_module.icf_generation_service, "generate_icf", generate)


def test_uploaded_protocol_is_indexed_analyzed_and_generated_as_one_workflow(monkeypatch):
    service = ICFWorkflowService()
    content = b"Study Title: A protocol\nStudy risks: headache"
    expected_id = service._safe_study_id(None, content)
    canonical = fake_canonical()
    indexed = SimpleNamespace(studies_indexed=[expected_id])
    def canonicalize(filename, content, *, on_stage=None):
        if on_stage:
            on_stage("study_loaded", "complete", "Protocol uploaded and verified.")
            on_stage("protocol_parsed", "complete", "Protocol parsed.")
        return canonical
    monkeypatch.setattr(workflow_module.protocol_ingestion_service, "canonicalize_upload", canonicalize)
    def index(canonical_response, *, on_stage=None, **kwargs):
        if on_stage:
            on_stage("text_chunking_completed", "complete", "Text chunking completed.")
            on_stage("embeddings_generated", "complete", "Embeddings generated.")
            on_stage("vector_index_completed", "complete", "FAISS vector index completed.")
        assert canonical_response.protocol.study_id == expected_id
        return canonical_response, indexed
    monkeypatch.setattr(workflow_module.protocol_ingestion_service, "index_canonical", index)
    configure_generation(monkeypatch, expected_id)

    service.start(filename="protocol.txt", protocol_content=content)
    job = next(iter(service._jobs.values()))
    service.run(job["job_id"])
    finished = service.get(job["job_id"])

    assert finished["status"] == "succeeded"
    assert finished["study_id"] == expected_id
    assert finished["result"]["icf_result"]["validation_report"]["revision"] == 1
    assert all(step["status"] == "complete" for step in finished["steps"])


def test_preloaded_study_with_existing_evidence_skips_ingestion(monkeypatch):
    service = ICFWorkflowService()
    study_id = "NCT12345678"
    monkeypatch.setattr(workflow_module.study_loader_service, "get_study_detail", lambda _study_id: object())
    monkeypatch.setattr(workflow_module.study_loader_service, "get_study_as_canonical_protocol", lambda _study_id: fake_canonical(_study_id))
    monkeypatch.setattr(workflow_module.vector_store_service, "get_studies_indexed", lambda: [study_id])
    configure_generation(monkeypatch, study_id)

    job = service.start(study_id=study_id)
    service.run(job["job_id"])
    finished = service.get(job["job_id"])

    assert finished["status"] == "succeeded"
    assert finished["result"]["indexed_studies"] == [study_id]
    assert finished["steps"][1]["status"] == "complete"


def test_invalid_preloaded_study_returns_a_failed_job(monkeypatch):
    service = ICFWorkflowService()
    monkeypatch.setattr(workflow_module.study_loader_service, "get_study_detail", lambda _study_id: None)
    job = service.start(study_id="missing-study")

    service.run(job["job_id"])
    finished = service.get(job["job_id"])

    assert finished["status"] == "failed"
    assert "no longer available" in finished["error"]
    assert finished["result"] is None
