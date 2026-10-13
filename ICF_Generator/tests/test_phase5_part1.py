import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.query_processor import query_processor
from app.services.context_assembler import context_assembler
from app.services.study_loader import study_loader_service
from app.models.rag import RAGRetrieveRequest, RAGContextResponse

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_vector_index():
    """
    Ensures study NCT00081328 is indexed before Phase 5 Part 1 tests.
    """
    study_loader_service.index_study_vectors("NCT00081328")

def test_query_processor_validation():
    """
    Verifies QueryProcessor input validation and whitespace normalization.
    """
    # Empty query should raise ValueError
    with pytest.raises(ValueError):
        query_processor.process_query("")

    with pytest.raises(ValueError):
        query_processor.process_query("   ")

    # Whitespace normalization
    orig, proc = query_processor.process_query("   What   are   the    possible   risks?   ")
    assert orig == "What   are   the    possible   risks?"
    assert proc == "What are the possible risks?"

def test_context_assembler_basic_retrieval():
    """
    Verifies ContextAssembler retrieves evidence, packages context, and preserves traceability.
    """
    req = RAGRetrieveRequest(
        query="What are the possible risks of this study?",
        study_id="NCT00081328",
        top_k=5
    )
    res = context_assembler.assemble_context(req)

    assert isinstance(res, RAGContextResponse)
    assert res.original_query == "What are the possible risks of this study?"
    assert res.processed_query == "What are the possible risks of this study?"
    assert res.study_id == "NCT00081328"
    assert res.evidence_count == 5
    assert len(res.evidence) == 5
    assert res.retrieval_status == "success"

    # Verify first evidence item and traceability metadata
    item = res.evidence[0]
    assert item.rank == 1
    assert item.chunk_id.startswith("NCT00081328_")
    assert len(item.text.strip()) > 0
    assert item.similarity_score > 0.0
    assert item.source.filename is not None
    assert item.source.chunk_index >= 1

def test_context_assembler_deduplication():
    """
    Verifies that duplicate chunk IDs are filtered out during context assembly.
    """
    req = RAGRetrieveRequest(
        query="What are the eligibility requirements?",
        study_id="NCT00081328",
        top_k=10
    )
    res = context_assembler.assemble_context(req)
    chunk_ids = [item.chunk_id for item in res.evidence]
    assert len(chunk_ids) == len(set(chunk_ids)), "Evidence list contains duplicate chunk IDs!"

def test_context_assembler_threshold_fallback():
    """
    Verifies that setting an impossibly high score threshold triggers fallback warning rather than empty set.
    """
    req = RAGRetrieveRequest(
        query="What are the possible risks?",
        study_id="NCT00081328",
        top_k=5,
        min_score_threshold=0.99  # Impossibly high threshold
    )
    res = context_assembler.assemble_context(req)

    assert res.retrieval_status == "fallback_below_threshold"
    assert res.warning_message is not None
    assert "fell below minimum similarity threshold" in res.warning_message
    assert res.evidence_count > 0  # Returned best available candidates

def test_rag_retrieve_api_endpoint():
    """
    Verifies POST /api/rag/retrieve endpoint.
    """
    response = client.post(
        "/api/rag/retrieve",
        json={
            "query": "What treatments or interventions are being studied?",
            "study_id": "NCT00081328",
            "top_k": 5
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["original_query"] == "What treatments or interventions are being studied?"
    assert data["study_id"] == "NCT00081328"
    assert data["evidence_count"] == 5
    assert len(data["evidence"]) == 5

def test_rag_retrieve_api_empty_query_error():
    """
    Verifies POST /api/rag/retrieve returns HTTP 400 for empty query.
    """
    response = client.post(
        "/api/rag/retrieve",
        json={
            "query": "   ",
            "study_id": "NCT00081328"
        }
    )
    assert response.status_code == 400

@pytest.mark.parametrize("query_text", [
    "What is the purpose of this study?",
    "What are the eligibility requirements?",
    "What treatments or interventions are being studied?",
    "What are the possible risks?",
    "What are the expected outcomes?"
])
def test_all_five_mandatory_queries(query_text):
    """
    Verifies context assembly for all 5 mandatory test queries.
    """
    req = RAGRetrieveRequest(
        query=query_text,
        study_id="NCT00081328",
        top_k=5
    )
    res = context_assembler.assemble_context(req)

    assert res.original_query == query_text
    assert res.evidence_count > 0
    assert res.retrieval_status in ["success", "fallback_below_threshold"]
    for item in res.evidence:
        assert item.chunk_id is not None
        assert item.source.filename is not None
        assert item.similarity_score > 0.0
