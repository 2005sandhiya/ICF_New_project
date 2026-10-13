import os
import sys
import io

# Ensure backend path is in sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import pytest
from pypdf import PdfWriter
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def create_valid_test_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()

def test_health_endpoint_still_works():
    """Phase 1 sanity check."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ICF Generator API"

def test_get_preloaded_studies_list():
    """Phase 2 Test 2: GET /api/studies returns list of study summaries."""
    response = client.get("/api/studies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0, "Preloaded studies list should contain at least one study"
    first_study = data[0]
    assert "study_id" in first_study
    assert "brief_title" in first_study
    assert "source_file" in first_study

def test_get_valid_study_detail():
    """Phase 2 Test 3: GET /api/studies/{study_id} for a valid study."""
    list_resp = client.get("/api/studies")
    assert list_resp.status_code == 200
    studies = list_resp.json()
    valid_id = studies[0]["study_id"]

    detail_resp = client.get(f"/api/studies/{valid_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["study_id"] == valid_id
    assert "raw_protocol" in detail
    assert "brief_title" in detail

def test_get_nonexistent_study_returns_404():
    """Phase 2 Test 4: Requesting a nonexistent study ID returns HTTP 404."""
    response = client.get("/api/studies/NCT99999999_NONEXISTENT")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()

def test_path_traversal_rejection():
    """Security test: Attempting path traversal in study_id returns 400."""
    response = client.get("/api/studies/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code in (400, 404)

def test_upload_valid_protocol_json():
    """Phase 2 Test 5: Uploading a valid JSON protocol document."""
    file_content = b'{"protocolSection": {"identificationModule": {"nctId": "NCT12345678"}}}'
    files = {"file": ("uploaded_protocol.json", file_content, "application/json")}
    response = client.post("/api/protocol/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "uploaded_protocol.json"
    assert data["file_type"] == "json"
    assert data["status"] == "validated"
    assert data["file_size_bytes"] == len(file_content)

def test_upload_valid_protocol_pdf():
    """Phase 2 Test 6: Uploading a valid PDF protocol document."""
    file_content = create_valid_test_pdf()
    files = {"file": ("clinical_protocol.pdf", file_content, "application/pdf")}
    response = client.post("/api/protocol/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "clinical_protocol.pdf"
    assert data["file_type"] == "pdf"
    assert data["status"] == "validated"

def test_upload_unsupported_extension_returns_400():
    """Phase 2 Test 7: Uploading an unsupported file extension returns 400."""
    file_content = b'unsupported script content'
    files = {"file": ("malicious_script.exe", file_content, "application/octet-stream")}
    response = client.post("/api/protocol/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "unsupported file extension" in data["detail"].lower()
