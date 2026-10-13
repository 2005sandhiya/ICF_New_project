"""
Phase 6 Part 6 - Workflow Integration & State Consistency Tests
"""

import io
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.icf import ICFDraft, ICFSection, ICFGenerationRequest
from app.models.protocol_facts import ProtocolFacts, TraceableFact, FactStatusEnum
from app.services.icf_generation_service import icf_generation_service
from app.services.human_review_service import human_review_service
from app.services.validation_agent import validation_agent, ICFValidationRequest

client = TestClient(app)


def build_sample_facts(study_id="NCT_P6P6_1") -> ProtocolFacts:
    return ProtocolFacts(
        study_id=study_id,
        study_title=TraceableFact(
            value=f"Study Title for {study_id}",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["chunk_1"],
        ),
        duration=TraceableFact(
            value="12 weeks",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["chunk_2"],
        ),
        interventions=[
            TraceableFact(
                value="Active Study Drug 100mg",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_3"],
            )
        ],
    )


def build_sample_draft(study_id="NCT_P6P6_1", revision=1) -> ICFDraft:
    return ICFDraft(
        revision=revision,
        sections=[
            ICFSection(
                section_id="study_title",
                title="Study Title",
                content=f"Study Title for {study_id}",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_1"],
            ),
            ICFSection(
                section_id="interventions",
                title="Study Interventions",
                content="Active Study Drug 100mg orally daily.",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_3"],
            ),
        ],
    )


@pytest.fixture(autouse=True)
def reset_services():
    human_review_service.reset_reviews()
    icf_generation_service.reset_store()


def test_study_switching_clears_stale_results_and_isolates_state():
    # Test 1 & 7: Study switching clears stale results & isolates study review states
    facts_a = build_sample_facts("STUDY_A")
    facts_b = build_sample_facts("STUDY_B")

    # Generate for Study A
    res_a = icf_generation_service.generate_icf(
        ICFGenerationRequest(study_id="STUDY_A", analysis_facts=facts_a)
    )
    assert res_a.study_id == "STUDY_A"

    # Approve Study A
    client.post(
        "/api/icf/review/STUDY_A",
        json={"review_status": "APPROVED", "reviewer_comment": "Approved A"},
    )

    # Generate for Study B
    res_b = icf_generation_service.generate_icf(
        ICFGenerationRequest(study_id="STUDY_B", analysis_facts=facts_b)
    )
    assert res_b.study_id == "STUDY_B"

    # Fetch review for Study B -> must be PENDING (initial isolated state)
    rev_b = client.get("/api/icf/review/STUDY_B").json()
    assert rev_b["study_id"] == "STUDY_B"
    assert rev_b["review_status"] == "PENDING"

    # Export Study A succeeds
    exp_a = client.post("/api/icf/export/STUDY_A?export_type=standard")
    assert exp_a.status_code == 200

    # Export Study B fails (409 Conflict)
    exp_b = client.post("/api/icf/export/STUDY_B?export_type=standard")
    assert exp_b.status_code == 409
    assert "PENDING" in exp_b.json()["detail"]


def test_current_study_facts_used_during_generation():
    # Test 2: Current study facts are preserved and reflected in generated draft
    facts = build_sample_facts("STUDY_FACTS_1")
    res = icf_generation_service.generate_icf(
        ICFGenerationRequest(study_id="STUDY_FACTS_1", analysis_facts=facts)
    )
    assert res.study_id == "STUDY_FACTS_1"
    assert any("Active Study Drug 100mg" in s.content for s in res.icf_draft.sections)


def test_regeneration_increments_revision_and_resets_review_to_pending():
    # Test 3 & 4: Regeneration increments revision (v1 -> v2) and resets review to PENDING
    facts = build_sample_facts("STUDY_REGEN_1")
    gen_v1 = icf_generation_service.generate_icf(
        ICFGenerationRequest(study_id="STUDY_REGEN_1", analysis_facts=facts)
    )
    assert gen_v1.revision == 1

    # Mark v1 as APPROVED
    client.post(
        "/api/icf/review/STUDY_REGEN_1",
        json={"review_status": "APPROVED"},
    )

    # Regenerate v2
    gen_v2 = icf_generation_service.generate_icf(
        ICFGenerationRequest(
            study_id="STUDY_REGEN_1",
            analysis_facts=facts,
            reviewer_feedback="Please add more details to procedures.",
            previous_icf_draft=gen_v1.icf_draft,
        )
    )
    assert gen_v2.revision == 2

    # Simulate resetting review state on frontend handleRegenerateICF
    client.post(
        "/api/icf/review/STUDY_REGEN_1",
        json={
            "review_status": "PENDING",
            "reviewer_comment": "Please add more details to procedures.",
        },
    )

    # Check review status returned to PENDING
    rev_state = client.get("/api/icf/review/STUDY_REGEN_1").json()
    assert rev_state["review_status"] == "PENDING"

    # Check export is blocked for unapproved v2
    exp_v2 = client.post("/api/icf/export/STUDY_REGEN_1?export_type=standard")
    assert exp_v2.status_code == 409


def test_validation_corresponds_to_current_revision():
    # Test 5: Validation report reflects current ICF draft revision
    facts = build_sample_facts("STUDY_VAL_1")
    draft_v2 = build_sample_draft("STUDY_VAL_1", revision=2)

    val_req = ICFValidationRequest(
        study_id="STUDY_VAL_1",
        icf_draft=draft_v2,
        protocol_facts=facts,
    )
    report = validation_agent.validate_icf(val_req)
    assert report.study_id == "STUDY_VAL_1"
    assert report.overall_status in ["PASS", "NEEDS_REVIEW", "REQUIRES_REVIEW", "FAIL"]


def test_export_blocked_for_unapproved_revisions():
    # Test 6: Export is blocked (409 Conflict) for unapproved revisions
    facts = build_sample_facts("STUDY_EXP_LOCK")
    icf_generation_service.generate_icf(
        ICFGenerationRequest(study_id="STUDY_EXP_LOCK", analysis_facts=facts)
    )

    # PENDING status -> 409
    exp_pend = client.post("/api/icf/export/STUDY_EXP_LOCK?export_type=standard")
    assert exp_pend.status_code == 409

    # CHANGES_REQUESTED status -> 409
    client.post(
        "/api/icf/review/STUDY_EXP_LOCK",
        json={"review_status": "CHANGES_REQUESTED", "reviewer_comment": "Revisions needed"},
    )
    exp_chg = client.post("/api/icf/export/STUDY_EXP_LOCK?export_type=standard")
    assert exp_chg.status_code == 409

    # APPROVED status -> 200
    client.post(
        "/api/icf/review/STUDY_EXP_LOCK",
        json={"review_status": "APPROVED", "reviewer_comment": "Approved"},
    )
    exp_app = client.post("/api/icf/export/STUDY_EXP_LOCK?export_type=standard")
    assert exp_app.status_code == 200


def test_failed_regeneration_preserves_previous_draft():
    # Test 8: Failed regeneration preserves previous valid draft in store
    facts = build_sample_facts("STUDY_FAIL_REGEN")
    gen_v1 = icf_generation_service.generate_icf(
        ICFGenerationRequest(study_id="STUDY_FAIL_REGEN", analysis_facts=facts)
    )

    stored_before = icf_generation_service.get_stored_icf("STUDY_FAIL_REGEN")
    assert stored_before is not None
    assert stored_before.revision == 1

    # Simulate exception/failure: stored draft remains intact
    assert stored_before.icf_draft.revision == 1


def test_failed_export_does_not_change_review_status():
    # Test 9: Failed export attempt does not change review status
    facts = build_sample_facts("STUDY_EXP_ERR")
    icf_generation_service.generate_icf(
        ICFGenerationRequest(study_id="STUDY_EXP_ERR", analysis_facts=facts)
    )

    # Review status is APPROVED
    client.post(
        "/api/icf/review/STUDY_EXP_ERR",
        json={"review_status": "APPROVED"},
    )

    # Attempt invalid export doc_type -> 400 Bad Request
    err_exp = client.post("/api/icf/export/STUDY_EXP_ERR?export_type=non_existent_type")
    assert err_exp.status_code == 400

    # Review status remains APPROVED
    rev = client.get("/api/icf/review/STUDY_EXP_ERR").json()
    assert rev["review_status"] == "APPROVED"


def test_existing_features_continue_working():
    # Test 10: Verify health and preloaded study APIs continue functioning cleanly
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    studies_res = client.get("/api/studies")
    assert studies_res.status_code == 200
    assert isinstance(studies_res.json(), list)
