import pytest
import io
from docx import Document
from fastapi.testclient import TestClient
from app.main import app
from app.services.human_review_service import human_review_service
from app.services.icf_generation_service import icf_generation_service
from app.models.human_review import ReviewStatusEnum

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_services():
    human_review_service.reset_reviews()
    icf_generation_service.reset_store()
    yield
    human_review_service.reset_reviews()
    icf_generation_service.reset_store()


def test_end_to_end_full_pipeline():
    """
    TASK 1: Full end-to-end integration test of all 9 pipeline stages:
    Study selection -> Protocol canonicalization -> RAG retrieval -> Protocol analysis ->
    ICF generation (v1) -> Validation -> Human Review (CHANGES_REQUESTED) ->
    Regeneration (v2) -> Revalidation -> Approval -> Standard & Patient-Friendly DOCX export.
    """
    study_id = "NCT00081328"

    # Step 1 & 2: Canonical Protocol Processing
    canon_res = client.get(f"/api/studies/{study_id}/canonical")
    assert canon_res.status_code == 200
    canon_data = canon_res.json()
    assert canon_data["status"] == "canonicalized"
    assert canon_data["protocol"]["study_id"] == study_id

    # Step 3: RAG Retrieval
    rag_payload = {
        "query": f"Retrieve protocol evidence for study {study_id}",
        "study_id": study_id,
        "top_k": 5
    }
    rag_res = client.post("/api/rag/retrieve", json=rag_payload)
    assert rag_res.status_code == 200
    rag_data = rag_res.json()
    assert rag_data["study_id"] == study_id
    assert len(rag_data["evidence"]) > 0

    # Step 4: Protocol Analysis
    analysis_payload = {
        "study_id": study_id,
        "query": "Extract structured study facts",
        "top_k": 5
    }
    analysis_res = client.post("/api/protocol/analyze", json=analysis_payload)
    assert analysis_res.status_code == 200
    analysis_data = analysis_res.json()
    facts = analysis_data["facts"]
    assert facts["study_id"] == study_id

    # Step 5: ICF Generation (Initial Draft v1)
    gen_payload = {
        "study_id": study_id,
        "analysis_facts": facts,
        "generate_patient_friendly": True
    }
    gen_res = client.post("/api/icf/generate", json=gen_payload)
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["revision"] == 1
    assert gen_data["icf_draft"]["revision"] == 1
    assert len(gen_data["icf_draft"]["sections"]) > 0

    # Step 6: Initial Validation (v1)
    val_payload = {
        "study_id": study_id,
        "icf_draft": gen_data["icf_draft"],
        "patient_friendly_icf": gen_data["patient_friendly_icf"],
        "protocol_facts": facts
    }
    val_res = client.post("/api/icf/validate", json=val_payload)
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["study_id"] == study_id
    assert val_data["revision"] == 1

    # Step 7: Attempt Export while review is PENDING (Must be blocked with 409)
    exp_pending_res = client.post(f"/api/icf/export/{study_id}?export_type=standard")
    assert exp_pending_res.status_code == 409

    # Step 8: Human Review Request Changes
    rev_comment = "Please clarify intervention dosage and visit schedule details."
    review_req = {
        "review_status": "CHANGES_REQUESTED",
        "reviewer_comment": rev_comment
    }
    rev_res = client.post(f"/api/icf/review/{study_id}", json=review_req)
    assert rev_res.status_code == 200
    assert rev_res.json()["review_status"] == "CHANGES_REQUESTED"

    # Step 9: ICF Regeneration with Reviewer Feedback (Produces v2, resets review to PENDING)
    regen_payload = {
        "study_id": study_id,
        "analysis_facts": facts,
        "generate_patient_friendly": True,
        "reviewer_feedback": rev_comment,
        "previous_icf_draft": gen_data["icf_draft"]
    }
    regen_res = client.post("/api/icf/generate", json=regen_payload)
    assert regen_res.status_code == 200
    regen_data = regen_res.json()
    assert regen_data["revision"] == 2
    assert regen_data["icf_draft"]["revision"] == 2

    # Verify review status was reset to PENDING on backend
    rev_check_res = client.get(f"/api/icf/review/{study_id}")
    assert rev_check_res.status_code == 200
    assert rev_check_res.json()["review_status"] == "PENDING"

    # Step 10: Revalidation on Revised Draft (v2)
    val2_payload = {
        "study_id": study_id,
        "icf_draft": regen_data["icf_draft"],
        "patient_friendly_icf": regen_data["patient_friendly_icf"],
        "protocol_facts": facts
    }
    val2_res = client.post("/api/icf/validate", json=val2_payload)
    assert val2_res.status_code == 200
    assert val2_res.json()["revision"] == 2

    # Step 11: Export Attempt on v2 while PENDING (Must be blocked with 409)
    exp_v2_pending = client.post(f"/api/icf/export/{study_id}?export_type=standard")
    assert exp_v2_pending.status_code == 409

    # Step 12: Human Review Approval
    approve_req = {
        "review_status": "APPROVED",
        "reviewer_comment": "Approved revised v2 ICF draft."
    }
    app_res = client.post(f"/api/icf/review/{study_id}", json=approve_req)
    assert app_res.status_code == 200
    assert app_res.json()["review_status"] == "APPROVED"

    # Step 13: Export Patient-Facing DOCX
    std_exp_res = client.post(f"/api/icf/export/{study_id}?export_type=patient_facing")
    assert std_exp_res.status_code == 200
    assert std_exp_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert "NCT00081328_Patient_Facing_ICF_v2.docx" in std_exp_res.headers["content-disposition"]

    # Verify DOCX binary structure
    std_doc = Document(io.BytesIO(std_exp_res.content))
    assert len(std_doc.paragraphs) > 0

    # Step 14: Export Patient-Facing DOCX (PDF/DOCX single document export)
    pf_exp_res = client.post(f"/api/icf/export/{study_id}?export_type=patient_facing&format=pdf")
    assert pf_exp_res.status_code == 200
    assert "NCT00081328_Patient_Facing_ICF_v2.pdf" in pf_exp_res.headers["content-disposition"]


def test_study_isolation_end_to_end():
    """
    TASK 2: Test study isolation across multiple active studies.
    """
    study_a = "NCT00081328"
    study_b = "NCT000001"

    # Generate & Approve Study A
    gen_a = client.post("/api/icf/generate", json={"study_id": study_a, "generate_patient_friendly": True})
    assert gen_a.status_code == 200
    client.post(f"/api/icf/review/{study_a}", json={"review_status": "APPROVED", "reviewer_comment": "Study A Approved"})

    # Generate Study B (Keep PENDING)
    gen_b = client.post("/api/icf/generate", json={"study_id": study_b, "generate_patient_friendly": True})
    assert gen_b.status_code == 200

    # Verify Study A export succeeds, Study B export fails with 409 Conflict
    exp_a = client.post(f"/api/icf/export/{study_a}?export_type=standard")
    assert exp_a.status_code == 200

    exp_b = client.post(f"/api/icf/export/{study_b}?export_type=standard")
    assert exp_b.status_code == 409


def test_export_consistency_rejects_unapproved():
    """
    TASK 4: Verify export is strictly blocked when review status is not APPROVED.
    """
    study_id = "NCT_UNAPPROVED_TEST"
    client.post("/api/icf/generate", json={"study_id": study_id})
    client.post(f"/api/icf/review/{study_id}", json={"review_status": "CHANGES_REQUESTED", "reviewer_comment": "Needs work"})

    res = client.post(f"/api/icf/export/{study_id}?export_type=standard")
    assert res.status_code == 409
    assert "must be approved" in res.json()["detail"].lower()


def test_error_recovery_multi_step():
    """
    TASK 5: Verify system recovers safely after invalid calls without crashing.
    """
    # Bad request 1: Invalid upload
    bad_up = client.post("/api/protocol/upload", files={"file": ("bad.exe", b"data", "text/plain")})
    assert bad_up.status_code == 400

    # Bad request 2: Export missing study
    bad_exp = client.post("/api/icf/export/NON_EXISTENT_STUDY_999?export_type=standard")
    assert bad_exp.status_code == 409

    # Valid call immediately following errors succeeds cleanly
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
