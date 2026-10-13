import io
import pytest
from app.models.icf import ICFDraft, ICFSection, ICFGenerationRequest, FactStatusEnum
from app.models.protocol_facts import ProtocolFacts, TraceableFact, CategorizedFactList, EligibilityFacts
from app.services.icf_generation_service import icf_generation_service
from app.services.template_service import template_service
from app.services.docx_generation_service import docx_generation_service
from app.services.template_renderer import document_text, render_template
from app.services.validation_agent import validation_agent
from app.models.validation import ICFValidationRequest
from app.services.human_review_service import human_review_service, ReviewStatusEnum

@pytest.fixture
def sample_study_facts():
    return ProtocolFacts(
        study_id="NCT00081328",
        study_title=TraceableFact(value="Phase III Trial of Investigational Drug X in Advanced Melanoma", source_evidence_ids=["NCT00081328:chunk1"], status=FactStatusEnum.SUPPORTED),
        phase=TraceableFact(value="Phase III", source_evidence_ids=["NCT00081328:chunk1"], status=FactStatusEnum.SUPPORTED),
        interventions=[
            TraceableFact(value="Investigational Drug X 100mg IV every 3 weeks", source_evidence_ids=["NCT00081328:chunk2"], status=FactStatusEnum.SUPPORTED)
        ],
        procedures=[
            TraceableFact(value="Screening CT scans and baseline blood sampling", source_evidence_ids=["NCT00081328:chunk3"], status=FactStatusEnum.SUPPORTED)
        ],
        duration=TraceableFact(value="12 months", source_evidence_ids=["NCT00081328:chunk4"], status=FactStatusEnum.SUPPORTED),
        risks=[
            TraceableFact(value="Fatigue, nausea, and potential liver enzyme elevation", source_evidence_ids=["NCT00081328:chunk5"], status=FactStatusEnum.SUPPORTED)
        ],
        benefits=[
            TraceableFact(value="Potential tumor shrinkage and prolonged progression-free survival", source_evidence_ids=["NCT00081328:chunk6"], status=FactStatusEnum.SUPPORTED)
        ],
        comparators=[
            TraceableFact(value="Standard Dacarbazine 1000mg/m2 IV", source_evidence_ids=["NCT00081328:chunk7"], status=FactStatusEnum.SUPPORTED)
        ]
    )

def test_builtin_vs_uploaded_template_fact_access(sample_study_facts):
    study_id = "NCT00081328"
    template_service.remove(study_id)
    
    # 1. Builtin generation
    resp_builtin = icf_generation_service.generate_icf(ICFGenerationRequest(study_id=study_id, analysis_facts=sample_study_facts))
    docx_builtin = docx_generation_service.generate_docx(study_id, resp_builtin.icf_draft, export_type="patient_facing")
    text_builtin = document_text(docx_builtin)

    # 2. Custom template generation
    custom_bytes = (template_service.root.parent / "ICF_Clinical_Study_Template_FINAL.docx").read_bytes()
    template_service.upload(study_id, "custom.docx", custom_bytes)

    resp_custom = icf_generation_service.generate_icf(ICFGenerationRequest(study_id=study_id, analysis_facts=sample_study_facts))
    docx_custom = docx_generation_service.generate_docx(study_id, resp_custom.icf_draft, export_type="patient_facing")
    text_custom = document_text(docx_custom)

    assert "Phase III Trial of Investigational Drug X" in text_builtin
    assert "Phase III Trial of Investigational Drug X" in text_custom
    assert len(text_builtin) == len(text_custom)

def test_supported_procedures_populated_in_both(sample_study_facts):
    study_id = "NCT00081328"
    template_service.remove(study_id)
    resp_builtin = icf_generation_service.generate_icf(ICFGenerationRequest(study_id=study_id, analysis_facts=sample_study_facts))
    docx_builtin = docx_generation_service.generate_docx(study_id, resp_builtin.icf_draft, export_type="patient_facing")
    text_builtin = document_text(docx_builtin)

    custom_bytes = (template_service.root.parent / "ICF_Clinical_Study_Template_FINAL.docx").read_bytes()
    template_service.upload(study_id, "custom.docx", custom_bytes)
    resp_custom = icf_generation_service.generate_icf(ICFGenerationRequest(study_id=study_id, analysis_facts=sample_study_facts))
    docx_custom = docx_generation_service.generate_docx(study_id, resp_custom.icf_draft, export_type="patient_facing")
    text_custom = document_text(docx_custom)

    assert "Screening CT scans" in text_builtin
    assert "Screening CT scans" in text_custom
    assert "Investigational Drug X" in text_builtin
    assert "Investigational Drug X" in text_custom

def test_missing_facts_flagged_consistently(sample_study_facts):
    study_id = "NCT00081328"
    template_service.remove(study_id)
    # Contact info is missing in sample_study_facts
    resp_builtin = icf_generation_service.generate_icf(ICFGenerationRequest(study_id=study_id, analysis_facts=sample_study_facts))
    docx_builtin = docx_generation_service.generate_docx(study_id, resp_builtin.icf_draft, export_type="patient_facing")
    text_builtin = document_text(docx_builtin)

    custom_bytes = (template_service.root.parent / "ICF_Clinical_Study_Template_FINAL.docx").read_bytes()
    template_service.upload(study_id, "custom.docx", custom_bytes)
    resp_custom = icf_generation_service.generate_icf(ICFGenerationRequest(study_id=study_id, analysis_facts=sample_study_facts))
    docx_custom = docx_generation_service.generate_docx(study_id, resp_custom.icf_draft, export_type="patient_facing")
    text_custom = document_text(docx_custom)

    assert "Contact information was not provided in the study protocol." in text_builtin
    assert "Contact information was not provided in the study protocol." in text_custom

def test_prevent_duplicated_treatment_in_visit_rows(sample_study_facts):
    study_id = "NCT00081328"
    template_service.remove(study_id)
    custom_bytes = (template_service.root.parent / "ICF_Clinical_Study_Template_FINAL.docx").read_bytes()
    template_service.upload(study_id, "custom.docx", custom_bytes)

    resp_custom = icf_generation_service.generate_icf(ICFGenerationRequest(study_id=study_id, analysis_facts=sample_study_facts))
    docx_custom = docx_generation_service.generate_docx(study_id, resp_custom.icf_draft, export_type="patient_facing")
    text_custom = document_text(docx_custom)

    treatment_str = "Investigational Drug X 100mg IV every 3 weeks"
    occurrences = text_custom.count(treatment_str)
    assert occurrences <= 3, f"Treatment description occurred {occurrences} times, indicating duplication across visit rows."

def test_cross_study_leakage_detected():
    icf_draft = ICFDraft(sections=[
        ICFSection(
            section_id="interventions",
            title="Study Interventions / Treatments",
            content="Treatment details for NCT00081328",
            source_evidence_ids=["NCT99999999:chunk4"],
            status=FactStatusEnum.SUPPORTED
        )
    ])
    report = validation_agent.validate_icf(ICFValidationRequest(study_id="NCT00081328", icf_draft=icf_draft))
    traceability_check = next((c for c in report.checks if c.check_id == "traceability"), None)
    assert traceability_check is not None
    assert any("originates from another study" in item for item in traceability_check.flagged_items)

def test_invented_facts_prevented(sample_study_facts):
    study_id = "NCT00081328"
    template_service.remove(study_id)
    resp = icf_generation_service.generate_icf(ICFGenerationRequest(study_id=study_id, analysis_facts=sample_study_facts))
    for sec in resp.icf_draft.sections:
        if sec.section_id == "questions_contact":
            assert sec.status == FactStatusEnum.NOT_FOUND
            assert sec.content == "Not provided in the study protocol."

def test_first_revision_approval_safeguards_preserved(sample_study_facts):
    study_id = "NCT00081328_COMPLETENESS"
    sample_study_facts.study_id = study_id
    template_service.remove(study_id)
    resp = icf_generation_service.generate_icf(ICFGenerationRequest(study_id=study_id, analysis_facts=sample_study_facts))
    assert resp.revision == 1
    review = human_review_service.get_review(study_id)
    assert review.review_status == ReviewStatusEnum.PENDING
