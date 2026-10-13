"""
Phase 5 Part 4 - Validation Agent Tests
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.icf import ICFDraft, ICFSection
from app.models.protocol_facts import (
    ProtocolFacts,
    TraceableFact,
    FactStatusEnum,
    CategorizedFactList,
    EligibilityFacts,
)
from app.models.validation import ICFValidationRequest
from app.services.validation_agent import ValidationAgent

client = TestClient(app)


def build_sample_facts() -> ProtocolFacts:
    return ProtocolFacts(
        study_id="NCT00081328",
        study_title=TraceableFact(
            value="Treatment Options for Type 2 Diabetes in Adolescents and Youth",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["chunk_1"],
        ),
        study_type=TraceableFact(
            value="Interventional",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["chunk_1"],
        ),
        phase=TraceableFact(
            value="Phase 3",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["chunk_1"],
        ),
        population=TraceableFact(
            value="Youth aged 10-17 with type 2 diabetes",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["chunk_2"],
        ),
        interventions=[
            TraceableFact(
                value="Metformin alone",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_3"],
            ),
            TraceableFact(
                value="Metformin plus Rosiglitazone",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_3"],
            ),
        ],
        objectives=CategorizedFactList(
            primary=[
                TraceableFact(
                    value="Evaluate influence of behaviors on treatment response",
                    status=FactStatusEnum.SUPPORTED,
                    source_evidence_ids=["chunk_4"],
                )
            ]
        ),
        eligibility=EligibilityFacts(
            inclusion=[
                TraceableFact(
                    value="Age 10-17 years",
                    status=FactStatusEnum.SUPPORTED,
                    source_evidence_ids=["chunk_5"],
                )
            ]
        ),
        duration=TraceableFact(
            value="Up to 5 years",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["chunk_6"],
        ),
    )


def build_sample_valid_icf_draft() -> ICFDraft:
    return ICFDraft(
        study_id="NCT00081328",
        generated_at="2026-09-21T12:00:00Z",
        version="1.0",
        sections=[
            ICFSection(
                section_id="title",
                title="Study Title & Key Information",
                content="Study Title: Treatment Options for Type 2 Diabetes in Adolescents and Youth. Protocol NCT00081328.",
                status="SUPPORTED",
                source_evidence_ids=["chunk_1"],
            ),
            ICFSection(
                section_id="purpose",
                title="Purpose of the Study",
                content="The purpose is to evaluate the influence of behaviors on treatment response.",
                status="SUPPORTED",
                source_evidence_ids=["chunk_4"],
            ),
            ICFSection(
                section_id="procedures",
                title="Study Procedures",
                content="Procedures include blood draws and oral glucose tolerance tests over the study duration.",
                status="SUPPORTED",
                source_evidence_ids=["chunk_3"],
            ),
            ICFSection(
                section_id="risks",
                title="Risks and Discomforts",
                content="Known risks include hypoglycemia, gastrointestinal upset, and weight gain.",
                status="SUPPORTED",
                source_evidence_ids=["chunk_3"],
            ),
            ICFSection(
                section_id="benefits",
                title="Potential Benefits",
                content="Not provided in the study protocol.",
                status="NOT_FOUND",
                source_evidence_ids=[],
            ),
            ICFSection(
                section_id="eligibility",
                title="Eligibility Criteria",
                content="Includes youth aged 10-17 years diagnosed with Type 2 Diabetes.",
                status="SUPPORTED",
                source_evidence_ids=["chunk_5"],
            ),
            ICFSection(
                section_id="duration",
                title="Study Duration",
                content="Participation will last up to 5 years.",
                status="SUPPORTED",
                source_evidence_ids=["chunk_6"],
            ),
        ],
    )


def test_groundedness_check_passed():
    agent = ValidationAgent()
    draft = build_sample_valid_icf_draft()
    facts = build_sample_facts()

    check, score = agent._check_groundedness(draft, facts)
    assert check.status == "PASS"
    assert score == 100.0
    assert len(check.flagged_items) == 0


def test_groundedness_check_failed_hallucinated_phone():
    agent = ValidationAgent()
    draft = build_sample_valid_icf_draft()
    facts = build_sample_facts()

    # Add hallucinated phone number
    draft.sections[0].content += " For questions call 1-800-555-0199."

    check, score = agent._check_groundedness(draft, facts)
    assert check.status in ["FAIL", "WARNING"]
    assert any("phone" in item.lower() or "555-" in item for item in check.flagged_items)


def test_completeness_check():
    agent = ValidationAgent()
    draft = build_sample_valid_icf_draft()
    facts = build_sample_facts()

    check, score = agent._check_completeness(draft, facts)
    assert check.status in ["PASS", "WARNING"]
    assert score >= 70.0


def test_not_found_integrity_check_passed():
    agent = ValidationAgent()
    draft = build_sample_valid_icf_draft()

    check, score = agent._check_not_found_integrity(draft, None)
    assert check.status == "PASS"
    assert score == 100.0
    assert len(check.flagged_items) == 0


def test_not_found_integrity_check_failed():
    agent = ValidationAgent()
    draft = build_sample_valid_icf_draft()

    # Violate NOT_FOUND rules: provide content without exact standard string or provide non-empty evidence IDs
    draft.sections[4].content = "This section has no data from protocol."
    draft.sections[4].source_evidence_ids = ["chunk_invalid"]

    check, score = agent._check_not_found_integrity(draft, None)
    assert check.status == "FAIL"
    assert score < 100.0
    assert len(check.flagged_items) >= 1


def test_traceability_check_passed():
    agent = ValidationAgent()
    draft = build_sample_valid_icf_draft()

    check, score = agent._check_traceability(draft)
    assert check.status == "PASS"
    assert score == 100.0


def test_traceability_check_warning():
    agent = ValidationAgent()
    draft = build_sample_valid_icf_draft()

    # Remove evidence ID from a SUPPORTED section
    draft.sections[1].source_evidence_ids = []

    check, score = agent._check_traceability(draft)
    assert check.status in ["WARNING", "FAIL"]
    assert len(check.flagged_items) >= 1


def test_readability_check():
    agent = ValidationAgent()
    draft = build_sample_valid_icf_draft()

    check, score = agent._check_readability(draft)
    assert score > 0.0
    assert check.status in ["PASS", "WARNING"]


def test_validation_agent_full_evaluation():
    agent = ValidationAgent()
    draft = build_sample_valid_icf_draft()
    facts = build_sample_facts()

    req = ICFValidationRequest(
        study_id="NCT00081328",
        icf_draft=draft,
        protocol_facts=facts,
    )

    report = agent.validate_icf(req)
    assert report.study_id == "NCT00081328"
    assert report.overall_status in ["PASSED", "REQUIRES_REVIEW"]
    assert report.overall_score >= 80.0
    assert len(report.checks) >= 5


def test_validation_api_endpoint(monkeypatch):
    # This endpoint test validates a standalone draft, independent of revisions
    # generated by earlier tests in the same process.
    from app.services.icf_generation_service import icf_generation_service
    monkeypatch.setattr(icf_generation_service, "_store", {})
    draft = build_sample_valid_icf_draft()
    facts = build_sample_facts()

    payload = {
        "study_id": "NCT00081328",
        "icf_draft": draft.model_dump(),
        "protocol_facts": facts.model_dump(),
    }

    response = client.post("/api/icf/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["study_id"] == "NCT00081328"
    assert "overall_status" in data
    assert "overall_score" in data
    assert "checks" in data
    assert "recommendations" in data


def test_completeness_not_100_percent_when_sections_missing():
    agent = ValidationAgent()
    facts = build_sample_facts()
    draft = build_sample_valid_icf_draft()

    # Remove interventions and duration sections from ICF draft
    draft.sections = [s for s in draft.sections if s.section_id not in ["interventions", "duration"]]

    check, score = agent._check_completeness(draft, facts)
    assert score < 100.0
    assert len(check.flagged_items) >= 1
    assert "Protocol facts not supplied" not in check.details


def test_validation_no_missing_facts_message_when_facts_supplied():
    agent = ValidationAgent()
    draft = build_sample_valid_icf_draft()
    facts = build_sample_facts()

    req = ICFValidationRequest(
        study_id="NCT00081328",
        icf_draft=draft,
        protocol_facts=facts,
    )
    report = agent.validate_icf(req)
    completeness_check = next(c for c in report.checks if c.check_id == "omission")
    assert "Protocol facts not supplied" not in completeness_check.details


def test_validation_agent_custom_study_id_propagation():
    agent = ValidationAgent()
    draft = build_sample_valid_icf_draft()
    facts = build_sample_facts()
    facts.study_id = "NCT00999999"

    req = ICFValidationRequest(
        study_id="NCT00999999",
        icf_draft=draft,
        protocol_facts=facts,
    )
    report = agent.validate_icf(req)
    assert report.study_id == "NCT00999999"

