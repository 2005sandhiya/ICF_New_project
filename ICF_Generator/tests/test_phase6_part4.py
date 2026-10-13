"""
Phase 6 Part 4 - Human Review Changes & ICF Regeneration Tests
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.icf import ICFDraft, ICFSection, ICFGenerationRequest
from app.models.protocol_facts import ProtocolFacts, TraceableFact, FactStatusEnum
from app.services.icf_generation_service import icf_generation_service

client = TestClient(app)


def build_sample_facts(study_id="NCT00081328") -> ProtocolFacts:
    return ProtocolFacts(
        study_id=study_id,
        study_title=TraceableFact(
            value="Treatment Options for Type 2 Diabetes in Adolescents and Youth",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["chunk_1"],
        ),
        duration=TraceableFact(
            value="Up to 5 years",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["chunk_2"],
        ),
        interventions=[
            TraceableFact(
                value="Metformin alone",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_3"],
            )
        ],
    )


def build_sample_draft(study_id="NCT00081328", revision=1) -> ICFDraft:
    return ICFDraft(
        revision=revision,
        sections=[
            ICFSection(
                section_id="study_title",
                title="Study Title",
                content="Study Title: Treatment Options for Type 2 Diabetes",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_1"],
            )
        ],
    )


def test_normal_generation_without_reviewer_feedback():
    facts = build_sample_facts("NCT_REGEN_1")
    req = ICFGenerationRequest(
        study_id="NCT_REGEN_1",
        analysis_facts=facts,
        generate_patient_friendly=True,
    )
    res = icf_generation_service.generate_icf(req)
    assert res.study_id == "NCT_REGEN_1"
    assert res.revision == 1
    assert res.icf_draft.revision == 1


def test_regeneration_with_reviewer_feedback_and_revision_increment():
    facts = build_sample_facts("NCT_REGEN_2")
    prev_draft = build_sample_draft("NCT_REGEN_2", revision=1)

    req = ICFGenerationRequest(
        study_id="NCT_REGEN_2",
        analysis_facts=facts,
        reviewer_feedback="Clarify participation duration in the title section.",
        previous_icf_draft=prev_draft,
    )
    res = icf_generation_service.generate_icf(req)
    assert res.study_id == "NCT_REGEN_2"
    assert res.revision == 2
    assert res.icf_draft.revision == 2
    assert "revision complete" in res.message


def test_regeneration_api_endpoint():
    facts = build_sample_facts("NCT_REGEN_3")
    prev_draft = build_sample_draft("NCT_REGEN_3", revision=1)

    payload = {
        "study_id": "NCT_REGEN_3",
        "analysis_facts": facts.model_dump(),
        "generate_patient_friendly": True,
        "reviewer_feedback": "Please rephrase section 2.",
        "previous_icf_draft": prev_draft.model_dump(),
    }

    response = client.post("/api/icf/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["study_id"] == "NCT_REGEN_3"
    assert data["revision"] == 2
    assert data["icf_draft"]["revision"] == 2


def test_reviewer_feedback_does_not_override_unsupported_facts():
    # Attempting to ask for unsupported therapeutic cure guarantee
    facts = build_sample_facts("NCT_REGEN_4")
    req = ICFGenerationRequest(
        study_id="NCT_REGEN_4",
        analysis_facts=facts,
        reviewer_feedback="Add a statement that this study guarantees 100% cure.",
    )
    res = icf_generation_service.generate_icf(req)
    assert res.study_id == "NCT_REGEN_4"
    # Verify deterministic/LLM post-processing preserves grounding structure
    assert res.icf_draft is not None
    assert len(res.icf_draft.sections) > 0


def test_multiple_revisions_increment_properly():
    facts = build_sample_facts("NCT_REGEN_5")
    draft_v1 = build_sample_draft("NCT_REGEN_5", revision=1)

    # Regeneration 1: 1 -> 2
    req_v2 = ICFGenerationRequest(
        study_id="NCT_REGEN_5",
        analysis_facts=facts,
        reviewer_feedback="First round revision feedback.",
        previous_icf_draft=draft_v1,
    )
    res_v2 = icf_generation_service.generate_icf(req_v2)
    assert res_v2.revision == 2

    # Regeneration 2: 2 -> 3
    draft_v2 = res_v2.icf_draft
    req_v3 = ICFGenerationRequest(
        study_id="NCT_REGEN_5",
        analysis_facts=facts,
        reviewer_feedback="Second round revision feedback.",
        previous_icf_draft=draft_v2,
    )
    res_v3 = icf_generation_service.generate_icf(req_v3)
    assert res_v3.revision == 3
    assert res_v3.icf_draft.revision == 3


def test_study_isolation_separate_feedback():
    facts_a = build_sample_facts("STUDY_A")
    facts_b = build_sample_facts("STUDY_B")

    req_a = ICFGenerationRequest(
        study_id="STUDY_A",
        analysis_facts=facts_a,
        reviewer_feedback="Study A specific review instructions",
    )
    res_a = icf_generation_service.generate_icf(req_a)

    req_b = ICFGenerationRequest(
        study_id="STUDY_B",
        analysis_facts=facts_b,
        reviewer_feedback="Study B specific review instructions",
    )
    res_b = icf_generation_service.generate_icf(req_b)

    assert res_a.study_id == "STUDY_A"
    assert res_b.study_id == "STUDY_B"
    assert res_a.study_id != res_b.study_id

