import os
import pytest
from app.services.vector_store import vector_store_service, VectorStoreService
from app.services.study_loader import study_loader_service
from app.models.chunk import EmbeddingResponse, EmbeddedProtocolChunk, ChunkMetadata

@pytest.fixture(autouse=True)
def setup_and_teardown_vector_store():
    """
    Resets the global vector store before each test in Phase 4 Part 3 test suite.
    """
    vector_store_service.clear_store()
    yield
    # Cleanup after test if needed
    vector_store_service.clear_store()

def test_faiss_index_creation_and_empty_state():
    """
    Verifies that a freshly initialized vector store reports an empty status.
    """
    status = vector_store_service.get_status()
    assert status.status == "empty"
    assert status.total_vectors == 0
    assert status.studies_indexed == []
    assert status.index_type == "IndexFlatIP"
    assert status.embedding_dimension == 384

def test_index_preloaded_study():
    """
    Verifies indexing a preloaded study (NCT00081328) into FAISS.
    """
    indexing_res = study_loader_service.index_study_vectors("NCT00081328")
    assert indexing_res is not None
    assert indexing_res.status == "indexed"
    assert indexing_res.vectors_added > 0
    assert indexing_res.total_vectors == indexing_res.vectors_added
    assert indexing_res.embedding_dimension == 384
    assert indexing_res.index_type == "IndexFlatIP"
    assert "NCT00081328" in indexing_res.studies_indexed

def test_vector_count_and_chunk_count_match():
    """
    Verifies that the total vectors stored matches the total chunks generated for the study.
    """
    chunks_res = study_loader_service.get_study_chunks("NCT00081328")
    assert chunks_res is not None
    expected_chunk_count = chunks_res.total_chunks

    indexing_res = study_loader_service.index_study_vectors("NCT00081328")
    assert indexing_res is not None
    assert indexing_res.total_vectors == expected_chunk_count
    assert vector_store_service.get_total_vectors() == expected_chunk_count

def test_vector_id_mapping_and_metadata():
    """
    Verifies stable 0-indexed vector IDs and complete metadata records.
    """
    study_loader_service.index_study_vectors("NCT00081328")
    total_vecs = vector_store_service.get_total_vectors()

    for vec_id in range(total_vecs):
        record = vector_store_service.get_metadata_by_vector_id(vec_id)
        assert record is not None
        assert record.vector_id == vec_id
        assert isinstance(record.chunk_id, str) and len(record.chunk_id) > 0
        assert isinstance(record.text, str) and len(record.text) > 0
        assert record.study_id == "NCT00081328"
        assert record.source_type == "json"
        assert record.source_filename in ["ctg-studies.json", "NCT00081328.json"]
        assert isinstance(record.section, str) and len(record.section) > 0
        assert record.chunk_index == vec_id + 1
        assert record.total_chunks == total_vecs

def test_disk_persistence_and_reload():
    """
    Verifies that index.faiss, metadata.json, and index_manifest.json are saved to disk
    and correctly reloaded by a new VectorStoreService instance.
    """
    study_loader_service.index_study_vectors("NCT00081328")
    original_total = vector_store_service.get_total_vectors()

    assert os.path.exists(vector_store_service.index_path)
    assert os.path.exists(vector_store_service.metadata_path)
    assert os.path.exists(vector_store_service.manifest_path)

    # Instantiate fresh VectorStoreService pointing to same directory
    reloaded_service = VectorStoreService(vector_store_dir=vector_store_service.vector_store_dir)
    assert reloaded_service.get_total_vectors() == original_total
    assert reloaded_service.get_studies_indexed() == ["NCT00081328"]

    # Check vector_id 0 in reloaded service
    record_0 = reloaded_service.get_metadata_by_vector_id(0)
    assert record_0 is not None
    assert record_0.vector_id == 0
    assert record_0.study_id == "NCT00081328"

def test_duplicate_chunk_handling():
    """
    Verifies that re-indexing the same study skips duplicate chunks safely.
    """
    res_1 = study_loader_service.index_study_vectors("NCT00081328")
    assert res_1 is not None
    first_added = res_1.vectors_added

    # Re-index same study
    res_2 = study_loader_service.index_study_vectors("NCT00081328")
    assert res_2 is not None
    assert res_2.vectors_added == 0
    assert res_2.total_vectors == first_added

def test_manual_traceability_mapping():
    """
    IMPORTANT TRACEABILITY TEST:
    Verifies 1-to-1 mapping from vector_id = 0 -> chunk_id -> chunk text -> section -> study_id -> source document -> page/source field.
    """
    study_loader_service.index_study_vectors("NCT00081328")

    rec_0 = vector_store_service.get_metadata_by_vector_id(0)
    assert rec_0 is not None
    assert rec_0.vector_id == 0
    assert rec_0.chunk_id == "NCT00081328_study_identification_001"
    assert rec_0.study_id == "NCT00081328"
    assert rec_0.source_filename in ["ctg-studies.json", "NCT00081328.json"]
    assert rec_0.source_type == "json"
    assert rec_0.section == "study_identification"
    assert rec_0.source_field is not None
    assert len(rec_0.text) > 0

    # Also test mapping via chunk_id
    rec_by_chunk = vector_store_service.get_metadata_by_chunk_id("NCT00081328_study_identification_001")
    assert rec_by_chunk is not None
    assert rec_by_chunk.vector_id == 0
    assert rec_by_chunk.text == rec_0.text

def test_dimension_compatibility_check():
    """
    Verifies that attempting to add vectors of incompatible dimension raises a ValueError.
    """
    study_loader_service.index_study_vectors("NCT00081328") # Store initialized with 384 dim

    incompatible_chunk = EmbeddedProtocolChunk(
        chunk_id="test_bad_dim_001",
        text="Sample text",
        metadata=ChunkMetadata(
            chunk_id="test_bad_dim_001",
            study_id="TEST",
            source_type="txt",
            source_filename="test.txt",
            section="test",
            chunk_index=1,
            total_chunks=1,
            character_count=11
        ),
        embedding=[0.1] * 128  # 128 dimension instead of 384
    )

    incompatible_response = EmbeddingResponse(
        status="embedded",
        study_id="TEST",
        source_filename="test.txt",
        source_type="txt",
        embedding_model="custom-128-model",
        embedding_dimension=128,
        batch_size=32,
        total_chunks=1,
        embedded_chunks=[incompatible_chunk],
        message="Test response with incompatible dimension"
    )

    with pytest.raises(ValueError, match="Incompatible embedding dimension"):
        vector_store_service.add_embeddings(incompatible_response)
