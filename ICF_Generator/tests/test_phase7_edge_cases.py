import pytest
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


def test_empty_file_upload_returns_400():
    """TASK 1: Empty file upload returns 400 Bad Request."""
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    response = client.post("/api/protocol/upload", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_unsupported_file_extension_returns_400():
    """TASK 1: Unsupported file extension returns 400 Bad Request."""
    files = {"file": ("malicious.exe", b"binary content", "application/octet-stream")}
    response = client.post("/api/protocol/upload", files=files)
    assert response.status_code == 400
    assert "unsupported" in response.json()["detail"].lower()


def test_corrupted_pdf_document_returns_400():
    """TASK 2: Corrupted PDF file integrity check returns 400 Bad Request."""
    files = {"file": ("corrupt.pdf", b"NOT_A_REAL_PDF_HEADER", "application/pdf")}
    response = client.post("/api/protocol/upload", files=files)
    assert response.status_code == 400
    assert "pdf" in response.json()["detail"].lower() or "malformed" in response.json()["detail"].lower()


def test_missing_study_id_generation_returns_400():
    """TASK 5: Missing study ID during ICF generation returns 400 Bad Request."""
    payload = {
        "study_id": "",
        "analysis_facts": None,
        "generate_patient_friendly": True
    }
    response = client.post("/api/icf/generate", json=payload)
    assert response.status_code == 400
    assert "study id" in response.json()["detail"].lower()


def test_regeneration_without_reviewer_feedback_returns_400():
    """TASK 5: Targeted ICF regeneration without reviewer feedback returns 400 Bad Request."""
    payload = {
        "study_id": "TEST_STUDY_ERR",
        "reviewer_feedback": "",
        "previous_icf_draft": {
            "revision": 1,
            "sections": [
                {
                    "section_id": "study_title",
                    "title": "Study Title",
                    "content": "Test Title",
                    "source_evidence_ids": ["chunk_1"],
                    "status": "SUPPORTED"
                }
            ]
        }
    }
    response = client.post("/api/icf/generate", json=payload)
    assert response.status_code == 400
    assert "reviewer feedback is required" in response.json()["detail"].lower()


def test_update_review_changes_requested_without_comment_returns_400():
    """TASK 7: Setting CHANGES_REQUESTED without reviewer comment returns 400 Bad Request."""
    payload = {
        "review_status": "CHANGES_REQUESTED",
        "reviewer_comment": ""
    }
    response = client.post("/api/icf/review/TEST_STUDY_ERR", json=payload)
    assert response.status_code == 400
    assert "reviewer comment is required" in response.json()["detail"].lower()


def test_export_blocked_when_pending_returns_409():
    """TASK 7: Export attempt when review status is PENDING returns 409 Conflict."""
    response = client.post("/api/icf/export/TEST_STUDY_ERR?export_type=standard")
    assert response.status_code == 409
    assert "must be approved" in response.json()["detail"].lower()


def test_export_invalid_export_type_returns_400():
    """TASK 7: Export attempt with invalid export_type returns 400 Bad Request after approval."""
    # Set to APPROVED
    human_review_service.update_review(
        "TEST_STUDY_ERR",
        type("Req", (), {"review_status": ReviewStatusEnum.APPROVED, "reviewer_comment": "OK"})()
    )
    response = client.post("/api/icf/export/TEST_STUDY_ERR?export_type=invalid_format")
    assert response.status_code == 400
    assert "unsupported export_type" in response.json()["detail"].lower()


def test_validation_request_empty_draft_returns_400():
    """TASK 6: Validation request with empty draft returns 400 Bad Request."""
    payload = {
        "study_id": "TEST_STUDY_ERR",
        "icf_draft": {"sections": []},
        "patient_friendly_icf": None,
        "protocol_facts": None
    }
    response = client.post("/api/icf/validate", json=payload)
    assert response.status_code == 400
    assert "valid icf draft with sections is required" in response.json()["detail"].lower()


def test_rag_empty_vector_store_returns_empty_context():
    """TASK 4: RAG retrieval on unknown study ID returns empty context status without failing."""
    payload = {
        "query": "Find study eligibility",
        "study_id": "NON_EXISTENT_STUDY_999",
        "top_k": 5
    }
    response = client.post("/api/rag/retrieve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["retrieval_status"] == "empty"
    assert len(data["evidence"]) == 0
