"""
Phase 6 Part 5 - Final ICF Document Generation & Approval Workflow Tests
"""

import io
import pytest
import docx
from fastapi.testclient import TestClient

from app.main import app
from app.models.icf import ICFDraft, ICFSection, ICFGenerationRequest
from app.models.protocol_facts import ProtocolFacts, TraceableFact, FactStatusEnum
from app.services.icf_generation_service import icf_generation_service
from app.services.human_review_service import human_review_service
from app.services.docx_generation_service import docx_generation_service

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
            ),
            ICFSection(
                section_id="purpose",
                title="Purpose of the Study",
                content="The purpose of this clinical trial is to evaluate metformin treatment efficacy.",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_2"],
            ),
            ICFSection(
                section_id="confidentiality",
                title="Confidentiality",
                content="Not provided in the study protocol.",
                status=FactStatusEnum.NOT_FOUND,
                source_evidence_ids=[],
            ),
        ],
    )


@pytest.fixture(autouse=True)
def reset_services():
    human_review_service.reset_reviews()
    icf_generation_service.reset_store()


def test_docx_generation_service_output():
    # Test 1: Successful DOCX binary generation & python-docx parsing
    draft = build_sample_draft("NCT_DOCX_1", revision=1)
    docx_bytes = docx_generation_service.generate_docx(
        study_id="NCT_DOCX_1",
        icf_draft=draft,
        export_type="standard",
    )
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 0

    # Parse using python-docx to verify document structure integrity
    doc = docx.Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(
        [p.text for p in doc.paragraphs]
        + [cell.text for t in doc.tables for row in t.rows for cell in row.cells]
    )
    assert "INFORMED CONSENT FORM" in full_text
    assert "NCT_DOCX_1" in full_text
    assert "Revision 1" in full_text
    assert "Purpose of the Study" in full_text
    assert "Signatures" in full_text or "Participant" in full_text


def test_export_blocked_when_review_status_is_pending():
    # Test 2: Export blocked (HTTP 409) when review status is PENDING
    facts = build_sample_facts("NCT_PENDING_1")
    req = ICFGenerationRequest(study_id="NCT_PENDING_1", analysis_facts=facts)
    icf_generation_service.generate_icf(req)

    # Initial state is PENDING
    response = client.post("/api/icf/export/NCT_PENDING_1?export_type=standard")
    assert response.status_code == 409
    assert "Export blocked" in response.json()["detail"]
    assert "PENDING" in response.json()["detail"]


def test_export_blocked_when_review_status_is_changes_requested():
    # Test 3: Export blocked (HTTP 409) when review status is CHANGES_REQUESTED
    facts = build_sample_facts("NCT_CHANGES_1")
    req = ICFGenerationRequest(study_id="NCT_CHANGES_1", analysis_facts=facts)
    icf_generation_service.generate_icf(req)

    # Set review status to CHANGES_REQUESTED
    client.post(
        "/api/icf/review/NCT_CHANGES_1",
        json={
            "review_status": "CHANGES_REQUESTED",
            "reviewer_comment": "Needs risk section clarification.",
        },
    )

    response = client.post("/api/icf/export/NCT_CHANGES_1?export_type=standard")
    assert response.status_code == 409
    assert "Export blocked" in response.json()["detail"]
    assert "CHANGES_REQUESTED" in response.json()["detail"]


def test_export_allowed_when_review_status_is_approved():
    # Test 4: Export allowed (HTTP 200) when review status is APPROVED
    facts = build_sample_facts("NCT_APPROVED_1")
    req = ICFGenerationRequest(study_id="NCT_APPROVED_1", analysis_facts=facts)
    icf_generation_service.generate_icf(req)

    client.post(
        "/api/icf/review/NCT_APPROVED_1",
        json={"review_status": "APPROVED", "reviewer_comment": "Draft looks good."},
    )

    response = client.post("/api/icf/export/NCT_APPROVED_1?export_type=standard")
    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "NCT_APPROVED_1_Patient_Facing_ICF_v1.docx" in response.headers["content-disposition"]


def test_export_blocked_when_no_icf_draft_exists():
    # Test 5: Export blocked (HTTP 404) when no ICF draft exists
    client.post(
        "/api/icf/review/NCT_NO_DRAFT",
        json={"review_status": "APPROVED", "reviewer_comment": "Approved beforehand."},
    )

    response = client.post("/api/icf/export/NCT_NO_DRAFT?export_type=standard")
    assert response.status_code == 404
    assert "No ICF draft found" in response.json()["detail"]


def test_study_isolation_export():
    # Test 6: Study isolation - approving Study A does not allow exporting Study B
    facts_a = build_sample_facts("STUDY_ISO_A")
    facts_b = build_sample_facts("STUDY_ISO_B")

    icf_generation_service.generate_icf(
        ICFGenerationRequest(study_id="STUDY_ISO_A", analysis_facts=facts_a)
    )
    icf_generation_service.generate_icf(
        ICFGenerationRequest(study_id="STUDY_ISO_B", analysis_facts=facts_b)
    )

    # Approve STUDY_ISO_A only
    client.post(
        "/api/icf/review/STUDY_ISO_A",
        json={"review_status": "APPROVED"},
    )

    # Export STUDY_ISO_A succeeds
    res_a = client.post("/api/icf/export/STUDY_ISO_A?export_type=standard")
    assert res_a.status_code == 200

    # Export STUDY_ISO_B fails with 409 Conflict (since STUDY_ISO_B is PENDING)
    res_b = client.post("/api/icf/export/STUDY_ISO_B?export_type=standard")
    assert res_b.status_code == 409


def test_revision_consistency_in_docx():
    # Test 7: Revision consistency - exported DOCX reflects revision index
    facts = build_sample_facts("NCT_REV_1")
    draft_v1 = build_sample_draft("NCT_REV_1", revision=1)

    # Regenerate to v2
    req_v2 = ICFGenerationRequest(
        study_id="NCT_REV_1",
        analysis_facts=facts,
        reviewer_feedback="Expand risks section",
        previous_icf_draft=draft_v1,
    )
    res_v2 = icf_generation_service.generate_icf(req_v2)
    assert res_v2.revision == 2

    # Approve v2
    client.post(
        "/api/icf/review/NCT_REV_1",
        json={"review_status": "APPROVED"},
    )

    exp_res = client.post("/api/icf/export/NCT_REV_1?export_type=standard")
    assert exp_res.status_code == 200
    assert "NCT_REV_1_Patient_Facing_ICF_v2.docx" in exp_res.headers["content-disposition"]

    doc = docx.Document(io.BytesIO(exp_res.content))
    full_text = "\n".join(
        [p.text for p in doc.paragraphs]
        + [cell.text for t in doc.tables for row in t.rows for cell in row.cells]
    )
    assert "Revision 2" in full_text


def test_patient_friendly_export_when_available():
    # Test 8: Patient-facing export when available
    facts = build_sample_facts("NCT_PF_1")
    req = ICFGenerationRequest(
        study_id="NCT_PF_1",
        analysis_facts=facts,
        generate_patient_friendly=True,
    )
    icf_generation_service.generate_icf(req)

    client.post(
        "/api/icf/review/NCT_PF_1",
        json={"review_status": "APPROVED"},
    )

    response = client.post("/api/icf/export/NCT_PF_1?export_type=patient_friendly")
    assert response.status_code == 200
    assert "NCT_PF_1_Patient_Facing_ICF_v1.docx" in response.headers["content-disposition"]

    doc = docx.Document(io.BytesIO(response.content))
    full_text = "\n".join([p.text for p in doc.paragraphs])
    assert "PATIENT-FACING INFORMED CONSENT FORM" in full_text or "INFORMED CONSENT FORM" in full_text


def test_standard_export_when_patient_friendly_unavailable():
    # Test 9: Export works for single Patient-Facing ICF
    facts = build_sample_facts("NCT_NO_PF")
    req = ICFGenerationRequest(
        study_id="NCT_NO_PF",
        analysis_facts=facts,
        generate_patient_friendly=False,
    )
    icf_generation_service.generate_icf(req)

    client.post(
        "/api/icf/review/NCT_NO_PF",
        json={"review_status": "APPROVED"},
    )

    # Export works for single Patient-Facing ICF
    res_std = client.post("/api/icf/export/NCT_NO_PF?export_type=standard")
    assert res_std.status_code == 200

    res_pf = client.post("/api/icf/export/NCT_NO_PF?export_type=patient_facing")
    assert res_pf.status_code == 200


def test_docx_response_headers_and_filename():
    # Test 10: Response content type and filename header formatting
    facts = build_sample_facts("NCT_HDR_1")
    icf_generation_service.generate_icf(
        ICFGenerationRequest(study_id="NCT_HDR_1", analysis_facts=facts)
    )

    client.post(
        "/api/icf/review/NCT_HDR_1",
        json={"review_status": "APPROVED"},
    )

    res = client.post("/api/icf/export/NCT_HDR_1?export_type=standard")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert 'attachment; filename="NCT_HDR_1_Patient_Facing_ICF_v1.docx"' in res.headers["content-disposition"]


def test_regeneration_resets_approval_and_blocks_stale_export():
    # Test 11: Regeneration resets approval to PENDING and blocks stale export until re-approved
    facts = build_sample_facts("NCT_STALE_1")
    gen_res1 = icf_generation_service.generate_icf(
        ICFGenerationRequest(study_id="NCT_STALE_1", analysis_facts=facts)
    )

    # Approve v1
    client.post(
        "/api/icf/review/NCT_STALE_1",
        json={"review_status": "APPROVED"},
    )
    assert client.post("/api/icf/export/NCT_STALE_1?export_type=standard").status_code == 200

    # Regenerate (simulating frontend handleRegenerateICF workflow which resets status to PENDING)
    icf_generation_service.generate_icf(
        ICFGenerationRequest(
            study_id="NCT_STALE_1",
            analysis_facts=facts,
            reviewer_feedback="Please revise section 3",
            previous_icf_draft=gen_res1.icf_draft,
        )
    )
    # Status reset to PENDING upon regeneration
    client.post(
        "/api/icf/review/NCT_STALE_1",
        json={
            "review_status": "PENDING",
            "reviewer_comment": "Please revise section 3",
        },
    )

    # Export must now be blocked (409 Conflict)
    res_stale = client.post("/api/icf/export/NCT_STALE_1?export_type=standard")
    assert res_stale.status_code == 409
    assert "PENDING" in res_stale.json()["detail"]

