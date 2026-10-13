import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("backend"))

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.prompts import ChatPromptTemplate

from app.models.chunk import ProtocolChunk, ChunkMetadata
from app.models.rag import RAGEvidenceItem, RAGSourceMetadata, RAGContextResponse
from app.models.protocol_facts import ProtocolFacts, TraceableFact, FactStatusEnum
from app.services.langchain_adapters import (
    to_langchain_document,
    ICFLangChainEmbeddings,
    ICFRAGRetriever,
    create_lcel_chat_prompt
)
from app.services.protocol_analysis_agent import protocol_analysis_agent
from app.services.icf_generation_service import icf_generation_service
from app.services.vector_store import vector_store_service
from app.services.study_loader import study_loader_service
from app.services.chunking.chunker import protocol_chunker_service as chunker
from app.services.embedding_service import embedding_service


def _ensure_vector_store_indexed(study_id: str = "NCT00081328"):
    if vector_store_service.get_total_vectors() == 0:
        cp = study_loader_service.get_study_as_canonical_protocol(study_id)
        if cp:
            cr = chunker.chunk_canonical_protocol(cp)
            er = embedding_service.embed_chunking_response(cr)
            vector_store_service.build_index(er)


def test_to_langchain_document_protocol_chunk():
    chk = ProtocolChunk(
        chunk_id="NCT00081328_eligibility_001",
        text="Patients must have histologically confirmed non-small cell lung cancer.",
        metadata=ChunkMetadata(
            chunk_id="NCT00081328_eligibility_001",
            study_id="NCT00081328",
            source_type="json",
            source_filename="NCT00081328.json",
            section="eligibility",
            subsection="inclusion",
            page_number=4,
            chunk_index=1,
            total_chunks=10,
            character_count=71
        )
    )
    doc = to_langchain_document(chk)
    assert isinstance(doc, Document)
    assert doc.page_content == "Patients must have histologically confirmed non-small cell lung cancer."
    assert doc.metadata["chunk_id"] == "NCT00081328_eligibility_001"
    assert doc.metadata["study_id"] == "NCT00081328"
    assert doc.metadata["section"] == "eligibility"
    assert doc.metadata["page_number"] == 4


def test_to_langchain_document_rag_evidence_item():
    ev = RAGEvidenceItem(
        rank=1,
        chunk_id="NCT00081328_risks_005",
        section="risks",
        subsection="adverse_events",
        text="Common side effects include fatigue, nausea, and rash.",
        similarity_score=0.88,
        source=RAGSourceMetadata(
            filename="NCT00081328.json",
            page_number=12,
            study_id="NCT00081328",
            chunk_index=5
        )
    )
    doc = to_langchain_document(ev)
    assert isinstance(doc, Document)
    assert "Common side effects" in doc.page_content
    assert doc.metadata["chunk_id"] == "NCT00081328_risks_005"
    assert doc.metadata["similarity_score"] == 0.88
    assert doc.metadata["study_id"] == "NCT00081328"


def test_icf_langchain_embeddings():
    embeddings = ICFLangChainEmbeddings()
    texts = ["Inclusion criteria for clinical trial.", "Exclusion criteria for clinical trial."]
    vecs = embeddings.embed_documents(texts)
    assert len(vecs) == 2
    assert len(vecs[0]) == 384
    assert len(vecs[1]) == 384

    query_vec = embeddings.embed_query("What are the study risks?")
    assert len(query_vec) == 384


def test_icf_rag_retriever_interface():
    _ensure_vector_store_indexed("NCT00081328")
    retriever = ICFRAGRetriever(study_id="NCT00081328", top_k=3)
    assert isinstance(retriever, BaseRetriever)

    docs = retriever.invoke("What are the eligibility criteria and risks?")
    assert isinstance(docs, list)
    if len(docs) > 0:
        assert isinstance(docs[0], Document)
        assert "chunk_id" in docs[0].metadata
        assert len(docs[0].page_content) > 0


def test_create_lcel_chat_prompt():
    prompt = create_lcel_chat_prompt(
        "You are an AI Clinical Assistant.",
        "Analyze study NCT00081328 with query: risks"
    )
    assert isinstance(prompt, ChatPromptTemplate)
    formatted = prompt.format_messages()
    assert len(formatted) == 2
    assert formatted[0].content == "You are an AI Clinical Assistant."
    assert "NCT00081328" in formatted[1].content


def test_protocol_analysis_agent_with_langchain_prompt():
    ctx = RAGContextResponse(
        original_query="Analyze protocol",
        processed_query="analyze_protocol",
        study_id="NCT00081328",
        evidence=[
            RAGEvidenceItem(
                rank=1,
                chunk_id="NCT00081328_title_001",
                section="title",
                text="Phase 3 Study of Erlotinib in Non-Small Cell Lung Cancer",
                similarity_score=0.92,
                source=RAGSourceMetadata(
                    filename="NCT00081328.json",
                    study_id="NCT00081328",
                    chunk_index=1
                )
            )
        ],
        evidence_count=1,
        retrieval_status="success"
    )
    facts = protocol_analysis_agent.analyze_context(ctx)
    assert isinstance(facts, ProtocolFacts)
    assert facts.study_id == "NCT00081328"


def test_icf_generation_service_with_langchain_prompt():
    facts = ProtocolFacts(
        study_id="NCT00081328",
        study_title=TraceableFact(
            value="Phase 3 Study of Erlotinib in Non-Small Cell Lung Cancer",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["NCT00081328_title_001"]
        )
    )
    draft = icf_generation_service._generate_structured_icf_draft(facts)
    assert draft is not None
    assert len(draft.sections) > 0
    assert any(s.section_id == "study_title" for s in draft.sections)
