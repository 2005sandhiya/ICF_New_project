import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.study_loader import study_loader_service
from app.services.context_assembler import context_assembler
from app.services.protocol_analysis_agent import protocol_analysis_agent
from app.models.rag import RAGRetrieveRequest, RAGContextResponse, RAGEvidenceItem, RAGSourceMetadata
from app.models.protocol_facts import (
    ProtocolFacts,
    ProtocolAnalysisRequest,
    ProtocolAnalysisResponse,
    FactStatusEnum
)

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_vector_index():
    """
    Ensures study NCT00081328 is indexed before Phase 5 Part 2 tests.
    """
    study_loader_service.index_study_vectors("NCT00081328")

def test_protocol_analysis_agent_eligibility_extraction():
    """
    Verifies ProtocolAnalysisAgent extracts eligibility facts and attaches source_evidence_ids.
    """
    rag_req = RAGRetrieveRequest(
        query="What are the eligibility requirements?",
        study_id="NCT00081328",
        top_k=5
    )
    rag_context = context_assembler.assemble_context(rag_req)
    assert rag_context.evidence_count > 0

    facts = protocol_analysis_agent.analyze_context(rag_context)
    assert isinstance(facts, ProtocolFacts)
    assert facts.study_id == "NCT00081328"

    # Verify eligibility facts are present and grounded
    total_eligibility = len(facts.eligibility.inclusion) + len(facts.eligibility.exclusion)
    assert total_eligibility > 0, "No eligibility criteria were extracted!"

    # Check fact-level source traceability
    first_fact = (facts.eligibility.inclusion + facts.eligibility.exclusion)[0]
    assert first_fact.status == FactStatusEnum.SUPPORTED
    assert len(first_fact.source_evidence_ids) > 0
    assert first_fact.source_evidence_ids[0].startswith("NCT00081328_")

def test_protocol_analysis_agent_interventions_extraction():
    """
    Verifies extraction of intervention facts from grounded RAG context.
    """
    rag_req = RAGRetrieveRequest(
        query="What treatments or interventions are being studied?",
        study_id="NCT00081328",
        top_k=5
    )
    rag_context = context_assembler.assemble_context(rag_req)
    facts = protocol_analysis_agent.analyze_context(rag_context)

    assert len(facts.interventions) > 0
    for item in facts.interventions:
        assert item.status == FactStatusEnum.SUPPORTED
        assert len(item.source_evidence_ids) > 0

def test_negative_grounding_unsupported_facts():
    """
    CRITICAL NEGATIVE GROUNDING TEST:
    Verifies that when evidence DOES NOT support a fact (e.g. direct study benefits),
    the agent returns status=NOT_FOUND or empty list instead of inventing information.
    """
    # Create a synthetic restricted RAG context that only contains inclusion criteria text
    restricted_context = RAGContextResponse(
        original_query="What are the direct financial benefits for pediatric organ transplant donors?",
        processed_query="What are the direct financial benefits for pediatric organ transplant donors?",
        study_id="NCT00081328",
        evidence=[
            RAGEvidenceItem(
                rank=1,
                chunk_id="NCT00081328_eligibility_014",
                section="eligibility",
                subsection="exclusion",
                text="Exclusion Criteria: Participating in another interventional research study protocol in the past 30 days.",
                similarity_score=0.45,
                source=RAGSourceMetadata(
                    filename="ctg-studies.json",
                    source_reference="eligibility",
                    study_id="NCT00081328",
                    chunk_index=14
                )
            )
        ],
        evidence_count=1,
        retrieval_status="success"
    )

    facts = protocol_analysis_agent.analyze_context(restricted_context)

    # Benefits must be empty or marked NOT_FOUND because no evidence supports financial donor benefits
    assert len(facts.benefits) == 0 or all(f.status == FactStatusEnum.NOT_FOUND for f in facts.benefits)
    # Procedures must be empty or NOT_FOUND
    assert len(facts.procedures) == 0 or all(f.status == FactStatusEnum.NOT_FOUND for f in facts.procedures)
    # Duration must be NOT_FOUND
    assert facts.duration.status == FactStatusEnum.NOT_FOUND
    assert facts.duration.value is None

def test_analyze_protocol_api_endpoint():
    """
    Verifies POST /api/protocol/analyze API endpoint.
    """
    response = client.post(
        "/api/protocol/analyze",
        json={
            "study_id": "NCT00081328",
            "query": "What are the possible risks of this study?",
            "top_k": 5
        }
    )
    assert response.status_code == 200
    data = response.json()

    assert data["study_id"] == "NCT00081328"
    assert data["evidence_used_count"] == 5
    assert data["analysis_status"] == "success"
    assert "facts" in data
    assert "eligibility" in data["facts"]

def test_objective_extraction_and_non_objective_filtering():
    """
    Verifies that:
    1. Duplicate objectives appearing across multiple evidence chunks are deduplicated.
    2. The same objective does NOT appear in both primary and secondary lists.
    3. Genuine primary objectives remain primary.
    4. Genuine secondary objectives (e.g. safety, pathophysiology) remain secondary.
    5. source_evidence_ids are preserved and merged across supporting chunks.
    6. Intervention descriptions (e.g. 'The three treatment regimens are...') do NOT become objectives.
    7. Missing objectives remain empty lists when unsupported.
    """
    mixed_context = RAGContextResponse(
        original_query="What are the objectives of the study?",
        processed_query="What are the objectives of the study?",
        study_id="NCT00081328",
        evidence=[
            RAGEvidenceItem(
                rank=1,
                chunk_id="NCT00081328_objectives_004",
                section="objectives",
                subsection="primary",
                text=(
                    "Primary Study Objectives:\n"
                    "The primary objective of the TODAY trial is to compare the efficacy of three treatment arms on time to treatment failure based on glycemic control.\n"
                    "The secondary aims are to:\n"
                    "* compare and evaluate the safety of the three treatment arms;\n"
                    "* compare the effects of the three treatments on the pathophysiology of type 2 diabetes;\n"
                    "* evaluate the influence of individual and family behaviors on treatment response; and\n"
                    "* compare the relative cost effectiveness of the three treatment arms."
                ),
                similarity_score=0.88,
                source=RAGSourceMetadata(
                    filename="ctg-studies.json",
                    source_reference="objectives",
                    study_id="NCT00081328",
                    chunk_index=4
                )
            ),
            RAGEvidenceItem(
                rank=2,
                chunk_id="NCT00081328_objectives_005",
                section="objectives",
                subsection="primary",
                text=(
                    "evaluate the influence of individual and family behaviors on treatment response; and\n"
                    "* compare the relative cost effectiveness of the three treatment arms.\n\n"
                    "The three treatment regimens are: (1) metformin alone, (2) metformin plus rosiglitazone, and (3) metformin plus an intensive lifestyle intervention called the TODAY Lifestyle Program (TLP). "
                    "The study recruits patients over a three-year period and follows patients for a minimum of two years. Patients are randomized within two years of the diagnosis of T2D."
                ),
                similarity_score=0.85,
                source=RAGSourceMetadata(
                    filename="ctg-studies.json",
                    source_reference="objectives",
                    study_id="NCT00081328",
                    chunk_index=5
                )
            )
        ],
        evidence_count=2,
        retrieval_status="success"
    )

    facts = protocol_analysis_agent.analyze_context(mixed_context)

    # 1. Primary Objectives: Genuine primary objective present
    primary_values = [o.value for o in facts.objectives.primary]
    assert len(primary_values) == 1, f"Expected exactly 1 primary objective, got {primary_values}"
    assert "compare the efficacy of three treatment arms" in primary_values[0]

    # 2. Secondary Objectives: Genuine secondary objectives present (safety, pathophysiology, cost, behavior)
    secondary_values = [o.value for o in facts.objectives.secondary]
    assert len(secondary_values) == 4, f"Expected 4 secondary objectives, got {len(secondary_values)}"
    assert any("safety of the three treatment arms" in v for v in secondary_values)
    assert any("pathophysiology of type 2 diabetes" in v for v in secondary_values)
    assert any("evaluate the influence of individual" in v for v in secondary_values)
    assert any("compare the relative cost effectiveness" in v for v in secondary_values)

    # 3. NO OVERLAP: Same objective must NOT appear in both primary and secondary
    for p_val in primary_values:
        for s_val in secondary_values:
            assert p_val.strip().lower() != s_val.strip().lower(), f"Objective '{p_val}' appears in both primary and secondary!"

    # 4. MERGED CHUNK IDs: source_evidence_ids preserved and merged across chunks 004 and 005
    behavior_obj = next(o for o in facts.objectives.secondary if "evaluate the influence" in o.value)
    assert "NCT00081328_objectives_004" in behavior_obj.source_evidence_ids
    assert "NCT00081328_objectives_005" in behavior_obj.source_evidence_ids

    # 5. INTERVENTION / STUDY DESIGN FILTERING
    all_obj_values = primary_values + secondary_values
    for val in all_obj_values:
        assert "The three treatment regimens are:" not in val, f"Intervention description misclassified as objective: {val}"
        assert "The study recruits patients" not in val, f"Study design description misclassified as objective: {val}"
        assert "Patients are randomized" not in val, f"Procedural description misclassified as objective: {val}"

    # 6. Missing Objectives empty when context has no objectives
    no_obj_context = RAGContextResponse(
        original_query="What are the eligibility criteria?",
        processed_query="What are the eligibility criteria?",
        study_id="NCT00081328",
        evidence=[
            RAGEvidenceItem(
                rank=1,
                chunk_id="NCT00081328_eligibility_014",
                section="eligibility",
                subsection="inclusion",
                text="Inclusion Criteria: Age 10-17 years old at diagnosis of type 2 diabetes.",
                similarity_score=0.90,
                source=RAGSourceMetadata(
                    filename="ctg-studies.json",
                    source_reference="eligibility",
                    study_id="NCT00081328",
                    chunk_index=14
                )
            )
        ],
        evidence_count=1,
        retrieval_status="success"
    )
    no_obj_facts = protocol_analysis_agent.analyze_context(no_obj_context)
    assert len(no_obj_facts.objectives.primary) == 0
    assert len(no_obj_facts.objectives.secondary) == 0

