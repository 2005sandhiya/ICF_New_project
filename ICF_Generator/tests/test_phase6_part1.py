"""
Phase 6 Part 1 - Human Review Backend Foundation Tests
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.human_review_service import human_review_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_review_store():
    human_review_service.reset_reviews()
    yield
    human_review_service.reset_reviews()


def test_new_study_returns_pending_review():
    response = client.get("/api/icf/review/NCT11111111")
    assert response.status_code == 200
    data = response.json()
    assert data["study_id"] == "NCT11111111"
    assert data["review_status"] == "PENDING"
    assert data["reviewer_comment"] is None
    assert data["reviewed_at"] is None


def test_study_a_approval_and_reviewed_at_timestamp():
    payload = {
        "review_status": "APPROVED",
        "reviewer_comment": "Protocol requirements fully verified by IRB.",
    }
    response = client.post("/api/icf/review/NCT_STUDY_A", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["study_id"] == "NCT_STUDY_A"
    assert data["review_status"] == "APPROVED"
    assert data["reviewer_comment"] == "Protocol requirements fully verified by IRB."
    assert data["reviewed_at"] is not None
    assert "T" in data["reviewed_at"]  # ISO timestamp format check


def test_study_isolation_study_b_remains_pending():
    # Approve Study A
    client.post(
        "/api/icf/review/STUDY_A",
        json={
            "review_status": "APPROVED",
            "reviewer_comment": "Approved A",
        },
    )

    # Check Study B
    response_b = client.get("/api/icf/review/STUDY_B")
    assert response_b.status_code == 200
    data_b = response_b.json()
    assert data_b["study_id"] == "STUDY_B"
    assert data_b["review_status"] == "PENDING"
    assert data_b["reviewer_comment"] is None
    assert data_b["reviewed_at"] is None


def test_status_change_to_changes_requested():
    payload = {
        "review_status": "CHANGES_REQUESTED",
        "reviewer_comment": "Please revise the dosage explanation in section 3.",
    }
    response = client.put("/api/icf/review/STUDY_A", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["study_id"] == "STUDY_A"
    assert data["review_status"] == "CHANGES_REQUESTED"
    assert (
        data["reviewer_comment"]
        == "Please revise the dosage explanation in section 3."
    )
    assert data["reviewed_at"] is not None


def test_no_hardcoded_nct00081328_fallback():
    # Query a custom study ID and ensure it is preserved without defaulting to NCT00081328
    response = client.get("/api/icf/review/CUSTOM_STUDY_999")
    assert response.status_code == 200
    data = response.json()
    assert data["study_id"] == "CUSTOM_STUDY_999"
    assert data["study_id"] != "NCT00081328"


def test_invalid_review_status_rejected():
    payload = {
        "review_status": "INVALID_STATUS_VALUE",
        "reviewer_comment": "Testing invalid status",
    }
    response = client.post("/api/icf/review/STUDY_TEST", json=payload)
    assert response.status_code == 422  # Unprocessable Entity for invalid enum value


def test_review_decision_independent_and_study_switching_isolation():
    # Study A is marked CHANGES_REQUESTED
    res_a = client.post(
        "/api/icf/review/STUDY_A",
        json={
            "review_status": "CHANGES_REQUESTED",
            "reviewer_comment": "Revise section 2 dosage instructions.",
        },
    )
    assert res_a.status_code == 200

    # Study B is APPROVED
    res_b = client.post(
        "/api/icf/review/STUDY_B",
        json={
            "review_status": "APPROVED",
            "reviewer_comment": "Looks good to proceed.",
        },
    )
    assert res_b.status_code == 200

    # Switch back & verify Study A retains CHANGES_REQUESTED
    check_a = client.get("/api/icf/review/STUDY_A").json()
    assert check_a["study_id"] == "STUDY_A"
    assert check_a["review_status"] == "CHANGES_REQUESTED"
    assert check_a["reviewer_comment"] == "Revise section 2 dosage instructions."
    assert check_a["reviewed_at"] is not None

    # Switch to Study B & verify Study B retains APPROVED
    check_b = client.get("/api/icf/review/STUDY_B").json()
    assert check_b["study_id"] == "STUDY_B"
    assert check_b["review_status"] == "APPROVED"
    assert check_b["reviewer_comment"] == "Looks good to proceed."
    assert check_b["reviewed_at"] is not None

