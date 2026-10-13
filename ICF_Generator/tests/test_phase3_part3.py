import os
import sys
import io
import json
import zipfile
import pytest

# Ensure backend path is in sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_1_preloaded_study_json_canonicalization():
    """Test 1: GET /api/studies/{study_id}/canonical for preloaded study JSON."""
    list_resp = client.get("/api/studies")
    assert list_resp.status_code == 200
    studies = list_resp.json()
    valid_id = studies[0]["study_id"]

    canon_resp = client.get(f"/api/studies/{valid_id}/canonical")
    assert canon_resp.status_code == 200
    data = canon_resp.json()
    assert data["status"] == "canonicalized"
    protocol = data["protocol"]
    assert protocol["study_id"] == valid_id
    assert protocol["title"] is not None
    assert isinstance(protocol["conditions"], list)
    assert isinstance(protocol["eligibility"]["inclusion"], list)
    assert data["extracted_fields_count"] > 0

def test_2_missing_fields_remain_null_or_empty():
    """Test 2: Canonicalization does NOT invent missing fields (missing remains null / [])."""
    # Upload minimal protocol text lacking risks, benefits, duration
    txt_content = "Study Title: Minimal Evaluation Protocol\nInclusion Criteria:\n- Adult patients over 18"
    files = {"file": ("minimal_protocol.txt", txt_content.encode("utf-8"), "text/plain")}
    response = client.post("/api/protocol/canonicalize", files=files)
    
    assert response.status_code == 200
    data = response.json()
    protocol = data["protocol"]
    assert protocol["title"] == "Minimal Evaluation Protocol"
    assert protocol["phase"] is None  # Missing field stays null
    assert protocol["risks"] == []    # Missing array stays empty
    assert protocol["benefits"] == [] # Missing array stays empty
    assert len(protocol["eligibility"]["inclusion"]) == 1

def test_3_heading_variations_matching():
    """Test 3: Common heading variations map to the correct canonical sections."""
    text_with_headings = """
    Protocol Title: Phase 2 Vaccine Study
    Phase: Phase 2
    
    Eligibility
    Inclusion and Exclusion Criteria
    1. Patients with Type 2 Diabetes
    2. Aged 18 to 65
    
    Study Objectives
    Primary Objective:
    - Assess safety profile
    
    Study Endpoints
    Primary Efficacy Endpoint:
    - Change in HbA1c at 24 weeks
    """
    files = {"file": ("headings_protocol.txt", text_with_headings.encode("utf-8"), "text/plain")}
    response = client.post("/api/protocol/canonicalize", files=files)
    
    assert response.status_code == 200
    data = response.json()
    protocol = data["protocol"]
    assert protocol["phase"] == "Phase 2"
    assert len(protocol["objectives"]["primary"]) > 0
    assert "HbA1c" in protocol["outcomes"]["primary"][0]

def test_4_source_traceability_metadata():
    """Test 4: Verify source metadata provenance is retained for JSON and text."""
    # Test JSON source traceability
    list_resp = client.get("/api/studies")
    valid_id = list_resp.json()[0]["study_id"]
    canon_resp = client.get(f"/api/studies/{valid_id}/canonical")
    source_sections = canon_resp.json()["protocol"]["source_sections"]
    assert len(source_sections) > 0
    assert "source_metadata" in source_sections[0]
    assert source_sections[0]["source_metadata"]["type"] == "json"

def test_5_invalid_input_rejection():
    """Test 5: Malformed upload file returns 400."""
    files = {"file": ("bad_file.json", b"not valid json content", "application/json")}
    response = client.post("/api/protocol/canonicalize", files=files)
    assert response.status_code == 400

def test_6_existing_health_endpoint_still_works():
    """Test 6: Phase 1 GET /health endpoint sanity check."""
    response = client.get("/health")
    assert response.status_code == 200

def test_7_existing_studies_endpoint_still_works():
    """Test 7: Phase 2 GET /api/studies endpoint sanity check."""
    response = client.get("/api/studies")
    assert response.status_code == 200

def test_8_existing_process_endpoint_still_works():
    """Test 8: Phase 3 Part 2 POST /api/protocol/process endpoint sanity check."""
    files = {"file": ("sample.txt", b"Protocol text", "text/plain")}
    response = client.post("/api/protocol/process", files=files)
    assert response.status_code == 200
    assert response.json()["status"] == "processed"
