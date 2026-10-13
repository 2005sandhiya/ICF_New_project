import os
import sys
import io
import json
import zipfile
from docx import Document
import pytest
from pypdf import PdfWriter

# Ensure backend path is in sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Helper function to generate PDF with dummy text
def create_test_pdf_with_text(page_count: int = 2) -> bytes:
    writer = PdfWriter()
    for i in range(page_count):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()

# Helper function to generate test DOCX with paragraphs
def create_test_docx_with_text(paragraphs: list) -> bytes:
    buf = io.BytesIO()
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    document.save(buf)
    return buf.getvalue()

def test_1_actual_clinical_protocol_pdf_or_pdf_extraction():
    """Test 1: PDF process endpoint extracts pages and full text."""
    pdf_bytes = create_test_pdf_with_text(page_count=3)
    files = {"file": ("protocol_doc.pdf", pdf_bytes, "application/pdf")}
    response = client.post("/api/protocol/process", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "protocol_doc.pdf"
    assert data["document_type"] == "pdf"
    assert data["page_count"] == 3
    # If no text in blank pages, status is no_extractable_text or processed
    assert data["status"] in ("processed", "no_extractable_text")

def test_2_docx_text_extraction():
    """Test 2: Real DOCX processing extracts paragraph text."""
    parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    real_docx_path = os.path.join(parent_path, "data", "templates", "ethics-informedconsent-clinicalstudies.docx")
    
    if os.path.exists(real_docx_path):
        with open(real_docx_path, "rb") as f:
            docx_bytes = f.read()
    else:
        docx_bytes = create_test_docx_with_text(["Clinical Trial Protocol Paragraph 1", "Eligibility Criteria Paragraph 2"])

    files = {"file": ("ICF_Clinical_Study_Template_FINAL.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    response = client.post("/api/protocol/process", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["document_type"] == "docx"
    assert len(data["full_text"]) > 0
    assert "informed consent form" in data["full_text"].lower() or "clinical trial protocol" in data["full_text"].lower()
    assert data["character_count"] > 0
    assert data["word_count"] > 0

def test_3_txt_text_extraction():
    """Test 3: Plain text file processing extracts normalized text."""
    txt_content = "Study Protocol Title: Phase 2 Evaluation of Drug XYZ\n\nStudy Objectives:\n1. Safety\n2. Efficacy"
    files = {"file": ("study_protocol.txt", txt_content.encode("utf-8"), "text/plain")}
    response = client.post("/api/protocol/process", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["document_type"] == "txt"
    assert "Phase 2 Evaluation of Drug XYZ" in data["full_text"]
    assert data["character_count"] == len(data["full_text"])

def test_4_valid_json_study_processing():
    """Test 4: Valid JSON study file processing extracts structured text."""
    json_bytes = b'{"protocolSection": {"identificationModule": {"nctId": "NCT01713764", "briefTitle": "Diabetes Study"}}}'
    files = {"file": ("ctg_study.json", json_bytes, "application/json")}
    response = client.post("/api/protocol/process", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["document_type"] == "json"
    assert "NCT01713764" in data["full_text"]
    assert "Diabetes Study" in data["full_text"]

def test_5_invalid_json_processing_rejection():
    """Test 5: Malformed JSON file returns 400 error."""
    files = {"file": ("malformed.json", b'{"protocolSection": {invalid_json', "application/json")}
    response = client.post("/api/protocol/process", files=files)
    
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "invalid json" in data["detail"].lower() or "malformed" in data["detail"].lower()

def test_6_unsupported_file_rejection():
    """Test 6: Unsupported file extension returns 400."""
    files = {"file": ("binary_exec.exe", b"binary bytes", "application/octet-stream")}
    response = client.post("/api/protocol/process", files=files)
    
    assert response.status_code == 400

def test_7_empty_file_rejection():
    """Test 7: Empty file (0 bytes) returns 400."""
    files = {"file": ("empty_file.txt", b"", "text/plain")}
    response = client.post("/api/protocol/process", files=files)
    
    assert response.status_code == 400

def test_8_scanned_no_text_pdf_handling():
    """Test 8: Blank PDF with no extractable text returns status 'no_extractable_text'."""
    blank_pdf = create_test_pdf_with_text(page_count=2)
    files = {"file": ("scanned_protocol.pdf", blank_pdf, "application/pdf")}
    response = client.post("/api/protocol/process", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_extractable_text"
    assert data["document_type"] == "pdf"
    assert data["page_count"] == 2
    assert "no extractable text" in data["message"].lower()

def test_9_health_endpoint_still_works():
    """Test 9: Phase 1 GET /health endpoint sanity check."""
    response = client.get("/health")
    assert response.status_code == 200

def test_10_studies_endpoint_still_works():
    """Test 10: Phase 2 GET /api/studies endpoint sanity check."""
    response = client.get("/api/studies")
    assert response.status_code == 200
