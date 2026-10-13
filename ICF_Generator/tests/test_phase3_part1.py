import os
import sys
import io
import zipfile
import pytest
from pypdf import PdfWriter

# Ensure backend path is in sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Helper function to generate a valid test PDF in memory
def create_test_pdf(pages_count: int = 3) -> bytes:
    writer = PdfWriter()
    for _ in range(pages_count):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()

# Helper function to generate a valid test DOCX in memory
def create_test_docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document><w:body><w:p/></w:body></w:document>")
        zf.writestr("[Content_Types].xml", "<Types></Types>")
    return buf.getvalue()

def test_1_valid_pdf_upload_and_metadata():
    """Test 1: Valid PDF upload returns 200, valid status, size display, and page count."""
    pdf_bytes = create_test_pdf(pages_count=5)
    files = {"file": ("clinical_protocol_test.pdf", pdf_bytes, "application/pdf")}
    response = client.post("/api/protocol/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["filename"] == "clinical_protocol_test.pdf"
    assert data["file_type"] == "pdf"
    assert data["page_count"] == 5
    assert "file_size_display" in data
    assert data["status"] == "validated"
    assert data["message"] == "File validation successful"

def test_2_valid_docx_upload_and_metadata():
    """Test 2: Valid DOCX upload returns 200 and valid status."""
    docx_bytes = create_test_docx()
    files = {"file": ("protocol_template.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    response = client.post("/api/protocol/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["filename"] == "protocol_template.docx"
    assert data["file_type"] == "docx"
    assert data["page_count"] is None
    assert data["status"] == "validated"

def test_3_valid_txt_upload_and_metadata():
    """Test 3: Valid TXT upload returns 200 and valid status."""
    txt_bytes = "Clinical Trial Protocol Summary\nStudy Objective: Evaluate Drug X".encode("utf-8")
    files = {"file": ("summary_protocol.txt", txt_bytes, "text/plain")}
    response = client.post("/api/protocol/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["filename"] == "summary_protocol.txt"
    assert data["file_type"] == "txt"
    assert data["page_count"] is None

def test_4_valid_json_upload_and_metadata():
    """Test 4: Valid JSON upload returns 200 and valid status."""
    json_bytes = b'{"protocolSection": {"identificationModule": {"nctId": "NCT09999999"}}}'
    files = {"file": ("ctg_protocol.json", json_bytes, "application/json")}
    response = client.post("/api/protocol/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["filename"] == "ctg_protocol.json"
    assert data["file_type"] == "json"

def test_5_unsupported_file_extension_rejection():
    """Test 5: Unsupported extension (.exe) returns 400."""
    files = {"file": ("executable_script.exe", b"binary content", "application/octet-stream")}
    response = client.post("/api/protocol/upload", files=files)
    
    assert response.status_code == 400
    data = response.json()
    assert "unsupported file extension" in data["detail"].lower()

def test_6_empty_file_rejection():
    """Test 6: Empty file (0 bytes) returns 400."""
    files = {"file": ("empty_protocol.pdf", b"", "application/pdf")}
    response = client.post("/api/protocol/upload", files=files)
    
    assert response.status_code == 400
    data = response.json()
    assert "empty" in data["detail"].lower()

def test_7_oversized_file_rejection():
    """Test 7: File exceeding 50 MB size limit returns 400."""
    oversized_bytes = b"0" * (50 * 1024 * 1024 + 10)
    files = {"file": ("huge_protocol.pdf", oversized_bytes, "application/pdf")}
    response = client.post("/api/protocol/upload", files=files)
    
    assert response.status_code == 400
    data = response.json()
    assert "exceeds maximum limit" in data["detail"].lower()

def test_8_malformed_unreadable_file_rejection():
    """Test 8: Fake PDF containing invalid bytes returns 400."""
    corrupted_pdf_bytes = b"This is text garbage not a real PDF structure"
    files = {"file": ("corrupted_protocol.pdf", corrupted_pdf_bytes, "application/pdf")}
    response = client.post("/api/protocol/upload", files=files)
    
    assert response.status_code == 400
    data = response.json()
    assert "malformed or unreadable" in data["detail"].lower()

def test_9_existing_health_endpoint_still_works():
    """Test 9: Phase 1 GET /health endpoint sanity check."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_10_existing_studies_endpoint_still_works():
    """Test 10: Phase 2 GET /api/studies endpoint sanity check."""
    response = client.get("/api/studies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_11_real_world_protocol_docx_upload():
    """Test 11: Real-world protocol template upload (Built-in consent docx)."""
    parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    real_docx_path = os.path.join(parent_path, "data", "templates", "ethics-informedconsent-clinicalstudies.docx")
    
    if os.path.exists(real_docx_path):
        with open(real_docx_path, "rb") as f:
            docx_bytes = f.read()
        
        files = {"file": ("NIH_Consent_Template.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = client.post("/api/protocol/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["filename"] == "NIH_Consent_Template.docx"
        assert data["file_type"] == "docx"
        assert data["file_size_bytes"] == len(docx_bytes)
        assert data["status"] == "validated"
