import os
import sys
import pytest

# Ensure backend path is in sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi.testclient import TestClient
from app.main import app
from app.models.canonical_protocol import (
    CanonicalProtocol,
    CanonicalProtocolResponse,
    EligibilityInfo,
    ObjectivesInfo,
    ProtocolSectionItem
)
from app.services.chunking.chunker import protocol_chunker_service

client = TestClient(app)

def test_chunker_service_direct():
    """Unit test for ProtocolChunkerService with mock canonical protocol."""
    canonical = CanonicalProtocol(
        study_id="TEST_STUDY_001",
        title="Phase 3 Study of Alpha-Drug in Adults with Mild Asthma",
        official_title="A Randomized, Double-Blind Phase 3 Study to Evaluate Efficacy of Alpha-Drug",
        phase="Phase 3",
        eligibility=EligibilityInfo(
            inclusion=["Age 18 to 65 years", "Confirmed diagnosis of mild asthma"],
            exclusion=["History of severe anaphylaxis", "Active smoker within 6 months"]
        ),
        objectives=ObjectivesInfo(
            primary=["To evaluate efficacy of Alpha-Drug in reducing asthma exacerbations"],
            secondary=["To assess safety and tolerability over 24 weeks"]
        ),
        source_sections=[
            ProtocolSectionItem(
                section_name="study_design",
                heading="2. Study Design and Methodology",
                content="This is a prospective 24-week double-blind randomized placebo-controlled study.",
                source_metadata={"page": 3}
            )
        ]
    )

    canon_response = CanonicalProtocolResponse(
        status="canonicalized",
        source={"filename": "test_protocol.pdf", "type": "pdf"},
        protocol=canonical
    )

    result = protocol_chunker_service.chunk_canonical_protocol(
        canonical_response=canon_response,
        target_chunk_size=500,
        chunk_overlap=50
    )

    assert result.status == "chunked"
    assert result.study_id == "TEST_STUDY_001"
    assert result.total_chunks > 0
    assert len(result.chunks) == result.total_chunks

    # Check unique chunk IDs
    chunk_ids = [c.chunk_id for c in result.chunks]
    assert len(chunk_ids) == len(set(chunk_ids))

    # Check metadata fields
    first_chunk = result.chunks[0]
    assert first_chunk.metadata.study_id == "TEST_STUDY_001"
    assert first_chunk.metadata.source_type == "pdf"
    assert first_chunk.metadata.source_filename == "test_protocol.pdf"
    assert first_chunk.metadata.chunk_index == 1
    assert first_chunk.metadata.total_chunks == result.total_chunks

    # Verify primary and secondary objective subsection distinction
    obj_chunks = [c for c in result.chunks if c.metadata.section == "objectives"]
    assert len(obj_chunks) == 2
    subsections = [c.metadata.subsection for c in obj_chunks]
    assert "primary" in subsections
    assert "secondary" in subsections

def test_safe_boundary_no_midword_split():
    """Verify chunker never splits words in the middle when creating chunks."""
    long_text = (
        "The primary objective of this randomized double blind multicenter clinical trial "
        "is to compare the relative cost effectiveness of treatment modalities over a 24 week period. "
        "Patients will undergo baseline laboratory evaluation including complete blood count and metabolic panel. "
        "Exclusion criteria mandate that active tobacco smokers and individuals with uncontrolled hypertension "
        "shall be excluded from enrollment."
    )

    canonical = CanonicalProtocol(
        study_id="NCT_BOUNDARY_TEST",
        source_sections=[
            ProtocolSectionItem(
                section_name="study_description",
                heading="1. Study Description",
                content=long_text,
                source_metadata={"page": 1}
            )
        ]
    )

    canon_response = CanonicalProtocolResponse(
        status="canonicalized",
        source={"filename": "boundary_test.pdf", "type": "pdf"},
        protocol=canonical
    )

    result = protocol_chunker_service.chunk_canonical_protocol(
        canonical_response=canon_response,
        target_chunk_size=120,
        chunk_overlap=30
    )

    assert result.total_chunks > 1

    # Verify no chunk starts or ends in the middle of a word
    for chk in result.chunks:
        text = chk.text
        # First word in chunk should be a complete word (not starting mid-word if original was space)
        first_word = text.split()[0]
        last_word = text.split()[-1]
        
        # Ensure 'effectiveness' or 'modality' is not cut like 'effectivenes' or 'modali'
        assert not first_word.startswith("tiveness")
        assert not last_word.endswith("of t")
        assert not last_word.endswith("effec")

def test_get_study_chunks_api():
    """Test GET /api/studies/{study_id}/chunks endpoint for preloaded studies."""
    list_resp = client.get("/api/studies")
    assert list_resp.status_code == 200
    studies = list_resp.json()
    assert len(studies) > 0
    target_id = studies[0]["study_id"]

    response = client.get(f"/api/studies/{target_id}/chunks?target_chunk_size=800&chunk_overlap=100")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "chunked"
    assert data["study_id"] == target_id
    assert data["total_chunks"] > 0
    assert len(data["chunks"]) == data["total_chunks"]

    # Verify JSON specific metadata rules
    for chunk in data["chunks"]:
        assert chunk["metadata"]["source_type"] == "json"
        assert chunk["metadata"]["page_number"] is None
        assert chunk["metadata"]["study_id"] == target_id
        assert chunk["metadata"]["chunk_index"] is not None
        assert chunk["metadata"]["total_chunks"] == data["total_chunks"]

def test_post_protocol_chunk_json():
    """Test POST /api/protocol/chunk with JSON protocol upload."""
    json_bytes = b'''{
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT99887766",
                "briefTitle": "Phase 2 Study of Beta-Blocker in Hypertension"
            },
            "eligibilityModule": {
                "eligibilityCriteria": "Inclusion Criteria:\\n- Adults aged 18-65\\n- Diagnosed with Stage 1 Hypertension\\nExclusion Criteria:\\n- Severe renal impairment"
            }
        }
    }'''

    response = client.post(
        "/api/protocol/chunk?target_chunk_size=400&chunk_overlap=50",
        files={"file": ("protocol_upload.json", json_bytes, "application/json")}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "chunked"
    assert data["total_chunks"] >= 1
    assert data["chunks"][0]["metadata"]["source_type"] == "json"
    assert data["chunks"][0]["metadata"]["source_filename"] == "protocol_upload.json"
    assert data["chunks"][0]["metadata"]["page_number"] is None
    # Verify exact source field for eligibility
    elig_chunks = [c for c in data["chunks"] if c["metadata"]["section"] == "eligibility"]
    for ec in elig_chunks:
        assert ec["metadata"]["source_field"] == "protocolSection.eligibilityModule"

def test_post_protocol_chunk_txt():
    """Test POST /api/protocol/chunk with TXT upload."""
    txt_content = (
        "CLINICAL PROTOCOL FOR ASTHMA STUDY\n"
        "1. Study Identification\nProtocol ID: ASTHMA-2026\n"
        "Official Title: A Study of Beta-Inhaler in Patients with Chronic Asthma\n\n"
        "2. Eligibility Criteria\n"
        "Inclusion Criteria:\n- Adult patients aged 18 to 70\n- Documented asthma diagnosis\n"
        "Exclusion Criteria:\n- Current smokers\n- Uncontrolled hypertension\n"
    )

    response = client.post(
        "/api/protocol/chunk",
        files={"file": ("asthma_protocol.txt", txt_content.encode("utf-8"), "text/plain")}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "chunked"
    assert data["total_chunks"] > 0

    chunk_ids = [c["chunk_id"] for c in data["chunks"]]
    assert len(chunk_ids) == len(set(chunk_ids))

def test_regression_previous_phases():
    """Verify endpoints from Phase 1, Phase 2, and Phase 3 remain fully functional."""
    # Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    # List studies
    res_studies = client.get("/api/studies")
    assert res_studies.status_code == 200
    assert len(res_studies.json()) >= 1

    # Study detail
    valid_id = res_studies.json()[0]["study_id"]
    res_detail = client.get(f"/api/studies/{valid_id}")
    assert res_detail.status_code == 200
    assert res_detail.json()["study_id"] == valid_id

    # Study canonical
    res_canon = client.get(f"/api/studies/{valid_id}/canonical")
    assert res_canon.status_code == 200
    assert res_canon.json()["status"] == "canonicalized"

    # Protocol upload
    txt_content = b"STUDY TITLE: Regression Protocol Test\nPhase 2 Study."
    res_upload = client.post(
        "/api/protocol/upload",
        files={"file": ("regression_test.txt", txt_content, "text/plain")}
    )
    assert res_upload.status_code == 200
    assert res_upload.json()["filename"] == "regression_test.txt"

    # Protocol process
    res_proc = client.post(
        "/api/protocol/process",
        files={"file": ("regression_test.txt", txt_content, "text/plain")}
    )
    assert res_proc.status_code == 200
    assert "REGRESSION PROTOCOL TEST" in res_proc.json()["full_text"].upper()

    # Protocol canonicalize
    res_canon_file = client.post(
        "/api/protocol/canonicalize",
        files={"file": ("regression_test.txt", txt_content, "text/plain")}
    )
    assert res_canon_file.status_code == 200
    assert res_canon_file.json()["status"] == "canonicalized"
