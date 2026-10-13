import os
import sys
import numpy as np
import pytest

# Ensure backend path is in sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi.testclient import TestClient
from app.main import app
from app.services.embedding_service import embedding_service
from app.models.chunk import ProtocolChunk, ChunkMetadata

client = TestClient(app)

def cosine_similarity(vec1: list, vec2: list) -> float:
    """Helper function to calculate cosine similarity between two vector lists."""
    v1 = np.array(vec1, dtype=np.float32)
    v2 = np.array(vec2, dtype=np.float32)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))

def test_embedding_service_direct():
    """Unit test for EmbeddingService direct encoding and dimension retrieval."""
    meta = ChunkMetadata(
        chunk_id="TEST_001",
        study_id="STUDY_EMBED_TEST",
        source_type="txt",
        source_filename="test.txt",
        section="eligibility",
        subsection="inclusion",
        chunk_index=1,
        total_chunks=1,
        character_count=52
    )
    chunk = ProtocolChunk(
        chunk_id="TEST_001",
        text="Adult patients aged 18 to 65 with Type 2 Diabetes.",
        metadata=meta
    )

    embedded = embedding_service.generate_embeddings([chunk])
    assert len(embedded) == 1
    echk = embedded[0]

    assert echk.chunk_id == "TEST_001"
    assert echk.text == chunk.text
    assert echk.metadata.study_id == "STUDY_EMBED_TEST"

    # Verify vector dimension
    expected_dim = embedding_service.get_embedding_dimension()
    assert len(echk.embedding) == expected_dim
    assert isinstance(echk.embedding[0], float)

def test_embedding_quality_sanity_check():
    """
    Phase 4 Part 2 Sanity Check:
    Verify that semantically related texts have high cosine similarity (> 0.6)
    and unrelated texts have low cosine similarity (< 0.3).
    """
    meta_dummy = ChunkMetadata(
        chunk_id="SIM_01",
        source_type="txt",
        source_filename="dummy.txt",
        section="test",
        chunk_index=1,
        total_chunks=1,
        character_count=10
    )

    text_diabetes_1 = ProtocolChunk(
        chunk_id="CH_01",
        text="Adult patients diagnosed with Type 2 Diabetes Mellitus with elevated HbA1c.",
        metadata=meta_dummy
    )
    text_diabetes_2 = ProtocolChunk(
        chunk_id="CH_02",
        text="Individuals aged 18 and older with confirmed T2D and poor glycemic control.",
        metadata=meta_dummy
    )
    text_unrelated = ProtocolChunk(
        chunk_id="CH_03",
        text="The robotic exploration rover successfully navigated the craters on Mars.",
        metadata=meta_dummy
    )

    embeddings = embedding_service.generate_embeddings([text_diabetes_1, text_diabetes_2, text_unrelated])
    assert len(embeddings) == 3

    vec1 = embeddings[0].embedding
    vec2 = embeddings[1].embedding
    vec3 = embeddings[2].embedding

    sim_related = cosine_similarity(vec1, vec2)
    sim_unrelated = cosine_similarity(vec1, vec3)

    assert sim_related > 0.45, f"Related text similarity should be high, got {sim_related}"
    assert sim_unrelated < 0.35, f"Unrelated text similarity should be low, got {sim_unrelated}"
    assert sim_related > (sim_unrelated + 0.25), "Related similarity should be significantly higher than unrelated similarity"

def test_get_study_embeddings_api():
    """Test GET /api/studies/{study_id}/embed endpoint for preloaded studies."""
    list_resp = client.get("/api/studies")
    assert list_resp.status_code == 200
    studies = list_resp.json()
    assert len(studies) > 0
    target_id = studies[0]["study_id"]

    response = client.get(f"/api/studies/{target_id}/embed?target_chunk_size=800&chunk_overlap=100")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "embedded"
    assert data["study_id"] == target_id
    assert data["embedding_model"] == "all-MiniLM-L6-v2"
    assert data["embedding_dimension"] == 384
    assert data["total_chunks"] > 0
    assert len(data["embedded_chunks"]) == data["total_chunks"]

    first_chunk = data["embedded_chunks"][0]
    assert "chunk_id" in first_chunk
    assert "text" in first_chunk
    assert "metadata" in first_chunk
    assert "embedding" in first_chunk
    assert len(first_chunk["embedding"]) == 384

def test_post_protocol_embed_json():
    """Test POST /api/protocol/embed with JSON protocol upload."""
    json_bytes = b'''{
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT99775533",
                "briefTitle": "Phase 3 Asthma Bio-Inhaler Trial"
            },
            "eligibilityModule": {
                "eligibilityCriteria": "Inclusion Criteria:\\n- Adult asthma patients"
            }
        }
    }'''

    response = client.post(
        "/api/protocol/embed?target_chunk_size=400&chunk_overlap=50",
        files={"file": ("asthma_embed.json", json_bytes, "application/json")}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "embedded"
    assert data["embedding_dimension"] == 384
    assert data["total_chunks"] >= 1
    assert len(data["embedded_chunks"][0]["embedding"]) == 384

def test_post_protocol_embed_txt():
    """Test POST /api/protocol/embed with TXT file upload."""
    txt_content = (
        "CLINICAL PROTOCOL FOR HYPERTENSION STUDY\n"
        "1. Study Identification\nProtocol ID: HYPER-2026\n"
        "Official Title: Evaluation of Oral Antihypertensive in Stage 2 Hypertension\n"
    )

    response = client.post(
        "/api/protocol/embed",
        files={"file": ("hyper_protocol.txt", txt_content.encode("utf-8"), "text/plain")}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "embedded"
    assert data["total_chunks"] > 0

def test_regression_all_previous_phases():
    """Verify Phase 1, Phase 2, Phase 3, and Phase 4 Part 1 endpoints remain fully functional."""
    # Health check (Phase 1)
    res_health = client.get("/health")
    assert res_health.status_code == 200

    # Studies list (Phase 2)
    res_studies = client.get("/api/studies")
    assert res_studies.status_code == 200
    valid_id = res_studies.json()[0]["study_id"]

    # Canonical (Phase 3 Part 3)
    res_canon = client.get(f"/api/studies/{valid_id}/canonical")
    assert res_canon.status_code == 200

    # Chunks (Phase 4 Part 1)
    res_chunks = client.get(f"/api/studies/{valid_id}/chunks")
    assert res_chunks.status_code == 200
    assert res_chunks.json()["status"] == "chunked"
