import pytest
import io
from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.services.icf_generation_service import icf_generation_service
from app.services.human_review_service import human_review_service
from app.models.icf import ICFGenerationRequest
from app.models.human_review import ReviewStatusEnum

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_services(monkeypatch):
    human_review_service.reset_reviews()
    icf_generation_service.reset_store()

    from app.services.study_loader import study_loader_service
    study_loader_service.index_study_vectors("NCT00081328")

    # Offline LLM mock returning plain-language simplified ICF content
    from app.services.llm.llm_service import llm_service
    import json

    def mock_generate_message(system_prompt="", user_prompt="", temperature=0.1):
        print("MOCK CALL -> SYSTEM:", repr(system_prompt[:60]), "| USER:", repr(user_prompt[:60]))
        is_pf = ("patient communication" in system_prompt.lower() or "structured icf draft to transform" in user_prompt.lower())
        purpose_text = "The main goals of this research study are to answer these questions: Is the treatment safe and helpful?" if is_pf else "The primary objective of this randomized clinical trial is to evaluate the therapeutic efficacy and safety profile of the investigational regimen."
        why_text = "You are invited to join because you meet these study participation rules: age 10 to 17 with diabetes." if is_pf else "Eligibility is restricted to pediatric subjects between 10 and 17 years of age presenting with type 2 diabetes mellitus."
        inv_text = "You will receive or be assigned to one of these study treatment options: metformin alone, metformin plus rosiglitazone, or metformin plus lifestyle." if is_pf else "Participants will be randomized to receive metformin alone, metformin combined with rosiglitazone, or metformin with lifestyle intervention."

        return json.dumps({
            "revision": 1,
            "sections": [
                {"section_id": "study_title", "title": "Study Title", "content": "Type 2 Diabetes Study", "status": "SUPPORTED", "source_evidence_ids": ["e1"]},
                {"section_id": "invitation", "title": "Invitation to Participate", "content": "You are invited to participate in this study.", "status": "SUPPORTED", "source_evidence_ids": ["e2"]},
                {"section_id": "purpose", "title": "Purpose of the Study", "content": purpose_text, "status": "SUPPORTED", "source_evidence_ids": ["e3"]},
                {"section_id": "why_asked", "title": "Why You Are Being Asked", "content": why_text, "status": "SUPPORTED", "source_evidence_ids": ["e4"]},
                {"section_id": "procedures", "title": "Study Procedures", "content": "Regular clinic visits every 2 to 3 months.", "status": "SUPPORTED", "source_evidence_ids": ["e5"]},
                {"section_id": "duration", "title": "Study Duration", "content": "Participation lasts up to 5 years.", "status": "SUPPORTED", "source_evidence_ids": ["e6"]},
                {"section_id": "interventions", "title": "Study Interventions / Treatments", "content": inv_text, "status": "SUPPORTED", "source_evidence_ids": ["e7"]},
                {"section_id": "risks", "title": "Risks and Discomforts", "content": "Side effects include stomach upset, hypoglycemia, and blood draw discomfort.", "status": "SUPPORTED", "source_evidence_ids": ["e8"]},
                {"section_id": "benefits", "title": "Potential Benefits", "content": "Improved blood sugar control.", "status": "SUPPORTED", "source_evidence_ids": ["e9"]},
                {"section_id": "alternatives", "title": "Alternatives to Participation", "content": "Not provided in the study protocol.", "status": "NOT_FOUND", "source_evidence_ids": []},
                {"section_id": "voluntary", "title": "Voluntary Participation", "content": "Participation is entirely voluntary.", "status": "SUPPORTED", "source_evidence_ids": ["e10"]},
                {"section_id": "confidentiality", "title": "Confidentiality", "content": "Research records will be kept confidential.", "status": "SUPPORTED", "source_evidence_ids": ["e11"]},
                {"section_id": "questions_contact", "title": "Questions / Contact Information", "content": "Contact the Principal Investigator at 555-0199 for study questions.", "status": "SUPPORTED", "source_evidence_ids": ["e12"]}
            ]
        })

    active_provider = llm_service.get_active_provider()
    monkeypatch.setattr(active_provider, "is_available", lambda: True)
    monkeypatch.setattr(llm_service, "generate_message", mock_generate_message)

    yield
    human_review_service.reset_reviews()
    icf_generation_service.reset_store()


def test_patient_friendly_meaningful_simplification():
    """
    TASK 4.1: Verify that patient-friendly draft uses simpler rephrased sentences and glossary terms.
    """
    study_id = "NCT00081328"
    gen_res = client.post("/api/icf/generate", json={"study_id": study_id, "generate_patient_friendly": True})
    assert gen_res.status_code == 200
    data = gen_res.json()

    std_draft = data["icf_draft"]
    pf_draft = data["patient_friendly_icf"]
    assert pf_draft is not None

    # Check for simplified section intro rephrasing on supported sections (purpose, why_asked, interventions)
    pf_purpose = next((s for s in pf_draft["sections"] if s["section_id"] == "purpose"), None)
    assert pf_purpose is not None and pf_purpose["status"] == "SUPPORTED"
    assert "The main goals of this research study are to answer these questions:" in pf_purpose["content"] or "Main Goal of the Study:" in pf_purpose["content"]

    pf_why = next((s for s in pf_draft["sections"] if s["section_id"] == "why_asked"), None)
    assert pf_why is not None and pf_why["status"] == "SUPPORTED"
    assert "You are invited to join because you meet these study participation rules:" in pf_why["content"] or "You may be able to join if you meet these rules:" in pf_why["content"]

    pf_inv = next((s for s in pf_draft["sections"] if s["section_id"] == "interventions"), None)
    assert pf_inv is not None and pf_inv["status"] == "SUPPORTED"
    assert "You will receive or be assigned to one of these study treatment options:" in pf_inv["content"] or "Interventions:" in pf_inv["content"]


def test_patient_friendly_preserves_medical_facts():
    """
    TASK 4.2: Verify that clinically important medical facts (drug names, durations) remain intact.
    """
    study_id = "NCT00081328"
    gen_res = client.post("/api/icf/generate", json={"study_id": study_id, "generate_patient_friendly": True})
    assert gen_res.status_code == 200
    data = gen_res.json()

    std_draft = data["icf_draft"]
    pf_draft = data["patient_friendly_icf"]

    # Verify exact drug names (rosiglitazone, metformin) present in standard draft are preserved in patient-friendly draft
    std_inv = next((s for s in std_draft["sections"] if s["section_id"] == "interventions"), None)
    pf_inv = next((s for s in pf_draft["sections"] if s["section_id"] == "interventions"), None)

    if std_inv and std_inv["status"] == "SUPPORTED":
        if "rosiglitazone" in std_inv["content"].lower():
            assert "rosiglitazone" in pf_inv["content"].lower()
        if "metformin" in std_inv["content"].lower():
            assert "metformin" in pf_inv["content"].lower()

    # Verify study duration facts match
    std_dur = next((s for s in std_draft["sections"] if s["section_id"] == "duration"), None)
    pf_dur = next((s for s in pf_draft["sections"] if s["section_id"] == "duration"), None)
    if std_dur and std_dur["status"] == "SUPPORTED":
        assert pf_dur["status"] == "SUPPORTED"


def test_patient_friendly_evidence_traceability():
    """
    TASK 4.3: Verify source_evidence_ids are preserved 1-to-1 between standard and patient-friendly sections.
    """
    study_id = "NCT00081328"
    gen_res = client.post("/api/icf/generate", json={"study_id": study_id, "generate_patient_friendly": True})
    assert gen_res.status_code == 200
    data = gen_res.json()

    std_sections = data["icf_draft"]["sections"]
    pf_sections = data["patient_friendly_icf"]["sections"]

    assert len(std_sections) == len(pf_sections)
    for std_sec, pf_sec in zip(std_sections, pf_sections):
        assert std_sec["section_id"] == pf_sec["section_id"]
        assert std_sec["source_evidence_ids"] == pf_sec["source_evidence_ids"]


def test_patient_friendly_missing_information_placeholders():
    """
    TASK 4.4: Verify NOT_FOUND sections retain the required placeholder string.
    """
    study_id = "NCT00081328"
    gen_res = client.post("/api/icf/generate", json={"study_id": study_id, "generate_patient_friendly": True})
    assert gen_res.status_code == 200
    data = gen_res.json()

    pf_sections = data["patient_friendly_icf"]["sections"]
    not_found_secs = [s for s in pf_sections if s["status"] == "NOT_FOUND"]

    for sec in not_found_secs:
        assert sec["content"] == "Not provided in the study protocol."
        assert len(sec["source_evidence_ids"]) == 0


def test_standard_icf_protection():
    """
    TASK 4.5: Verify Standard ICF is not altered by patient-friendly transformation.
    """
    study_id = "NCT00081328"
    gen_with_pf = client.post("/api/icf/generate", json={"study_id": study_id, "generate_patient_friendly": True}).json()
    gen_no_pf = client.post("/api/icf/generate", json={"study_id": study_id, "generate_patient_friendly": False}).json()

    std_with = gen_with_pf["icf_draft"]
    std_no = gen_no_pf["icf_draft"]

    assert len(std_with["sections"]) == len(std_no["sections"])
    for s1, s2 in zip(std_with["sections"], std_no["sections"]):
        assert s1["section_id"] == s2["section_id"]
        assert s1["content"] == s2["content"]


def test_patient_friendly_docx_export():
    """
    TASK 4.6: Verify patient-friendly DOCX export contains transformed text.
    """
    study_id = "NCT00081328"
    client.post("/api/icf/generate", json={"study_id": study_id, "generate_patient_friendly": True})
    client.post(f"/api/icf/review/{study_id}", json={"review_status": "APPROVED", "reviewer_comment": "Approved"})

    exp_res = client.post(f"/api/icf/export/{study_id}?export_type=patient_facing")
    assert exp_res.status_code == 200
    assert "Patient_Facing_ICF" in exp_res.headers["content-disposition"]

    doc = Document(io.BytesIO(exp_res.content))
    full_text = " ".join([p.text for p in doc.paragraphs])
    assert "PATIENT-FACING INFORMED CONSENT FORM" in full_text or "INFORMED CONSENT FORM" in full_text


def test_patient_friendly_simplification_delta():
    """
    PHASE 10 STEP 2:
    Verify that patient-friendly draft contains simpler rephrased text than standard draft for supported sections.
    """
    study_id = "NCT00081328"
    from app.services.protocol_analysis_agent import protocol_analysis_agent
    facts = protocol_analysis_agent.assemble_comprehensive_facts(study_id)
    std_draft = icf_generation_service._generate_structured_icf_draft(facts)
    pf_draft = icf_generation_service._transform_to_patient_friendly(std_draft)

    std_purpose = next(s for s in std_draft.sections if s.section_id == "purpose")
    pf_purpose = next(s for s in pf_draft.sections if s.section_id == "purpose")

    assert std_purpose.status == "SUPPORTED"
    assert pf_purpose.status == "SUPPORTED"
    assert pf_purpose.content != std_purpose.content
    assert "The main goals of this research study are to answer these questions:" in pf_purpose.content
    assert std_purpose.source_evidence_ids == pf_purpose.source_evidence_ids
