import io
import os
import sys
import pytest
from docx import Document

sys.path.insert(0, os.path.abspath("backend"))

from app.models.icf import ICFDraft, ICFSection
from app.models.protocol_facts import ProtocolFacts, TraceableFact, FactStatusEnum
from app.services.template_renderer import render_template
from app.services.template_service import DEFAULT_TEMPLATE_PATH

def create_subset_docx_template():
    """
    Creates a custom DOCX template containing ONLY 4 placeholders:
    [STUDY_TITLE], [PURPOSE_OF_STUDY], [RISKS], [BENEFITS]
    Omits duration, procedures, alternatives, voluntary, study registration, etc.
    """
    doc = Document()
    doc.add_heading("Custom Study Consent Form", level=1)
    
    doc.add_heading("Study Title", level=2)
    doc.add_paragraph("[STUDY_TITLE]")
    
    doc.add_heading("Purpose of the Study", level=2)
    doc.add_paragraph("[PURPOSE_OF_STUDY]")
    
    doc.add_heading("Risks and Discomforts", level=2)
    doc.add_paragraph("[RISKS]")
    
    doc.add_heading("Potential Benefits", level=2)
    doc.add_paragraph("[BENEFITS]")
    
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def test_1_protocol_matching_topics_are_rendered():
    template_bytes = create_subset_docx_template()
    draft = ICFDraft(sections=[
        ICFSection(section_id="study_title", title="Study Title", content="BioX Phase 2 Trial", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Evaluate efficacy of BioX.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="risks", title="Risks and Discomforts", content="Mild headache and fatigue.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="benefits", title="Potential Benefits", content="Potential reduction in symptoms.", status=FactStatusEnum.SUPPORTED),
    ])
    facts = ProtocolFacts(
        study_id="TEST-MAP-001",
        study_title=TraceableFact(value="BioX Phase 2 Trial", status=FactStatusEnum.SUPPORTED)
    )
    rendered_bytes = render_template(template_bytes, "TEST-MAP-001", draft, "patient_facing", facts=facts)
    rendered_doc = Document(io.BytesIO(rendered_bytes))
    full_text = "\n".join([p.text for p in rendered_doc.paragraphs])
    
    assert "BioX Phase 2 Trial" in full_text
    assert "Evaluate efficacy of BioX." in full_text
    assert "Mild headache and fatigue." in full_text
    assert "Potential reduction in symptoms." in full_text

def test_2_extra_unmapped_topics_are_not_rendered_and_no_new_sections_created():
    template_bytes = create_subset_docx_template()
    # Draft includes extra topics: study_registration, biological_samples, procedures, duration
    draft = ICFDraft(sections=[
        ICFSection(section_id="study_title", title="Study Title", content="BioX Phase 2 Trial", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Evaluate efficacy of BioX.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="risks", title="Risks and Discomforts", content="Mild headache and fatigue.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="benefits", title="Potential Benefits", content="Potential reduction in symptoms.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="study_registration", title="Study Registration and Results", content="Registered on ClinicalTrials.gov NCT99999999.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="biological_samples", title="Biological Samples", content="Blood samples stored for 5 years.", status=FactStatusEnum.SUPPORTED),
    ])
    facts = ProtocolFacts(
        study_id="TEST-MAP-002",
        study_title=TraceableFact(value="BioX Phase 2 Trial", status=FactStatusEnum.SUPPORTED)
    )
    rendered_bytes = render_template(template_bytes, "TEST-MAP-002", draft, "patient_facing", facts=facts)
    rendered_doc = Document(io.BytesIO(rendered_bytes))
    full_text = "\n".join([p.text for p in rendered_doc.paragraphs])
    
    # Extra topics must NOT be rendered
    assert "Registered on ClinicalTrials.gov NCT99999999" not in full_text
    assert "Blood samples stored for 5 years" not in full_text
    assert "Study Registration and Results" not in full_text
    assert "Biological Samples" not in full_text
    
    # Paragraph count should equal original template structure (no new headings or paragraphs added)
    orig_doc = Document(io.BytesIO(template_bytes))
    assert len(rendered_doc.paragraphs) == len(orig_doc.paragraphs)

def test_3_extra_protocol_info_not_inserted_into_unrelated_sections():
    template_bytes = create_subset_docx_template()
    draft = ICFDraft(sections=[
        ICFSection(section_id="study_title", title="Study Title", content="BioX Phase 2 Trial", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Evaluate efficacy of BioX.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="risks", title="Risks and Discomforts", content="Mild headache and fatigue.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="benefits", title="Potential Benefits", content="Potential reduction in symptoms.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="study_registration", title="Study Registration and Results", content="EXTRA_UNMAPPED_DATA_999", status=FactStatusEnum.SUPPORTED),
    ])
    facts = ProtocolFacts(study_id="TEST-MAP-003")
    rendered_bytes = render_template(template_bytes, "TEST-MAP-003", draft, "patient_facing", facts=facts)
    rendered_doc = Document(io.BytesIO(rendered_bytes))
    full_text = "\n".join([p.text for p in rendered_doc.paragraphs])
    
    # Unmapped data must NOT appear anywhere in the document (including risks, benefits, purpose)
    assert "EXTRA_UNMAPPED_DATA_999" not in full_text

def test_4_existing_custom_demo_templates_continue_to_work():
    for template_name in ["ICF_Custom_Template_A_Simple.docx", "ICF_Custom_Template_B_Modern.docx"]:
        path = os.path.join("data/templates/custom_demo", template_name)
        assert os.path.exists(path)
        with open(path, "rb") as f:
            template_bytes = f.read()
        draft = ICFDraft(sections=[
            ICFSection(section_id="study_title", title="Study Title", content="Custom Demo Study", status=FactStatusEnum.SUPPORTED),
            ICFSection(section_id="purpose", title="Purpose of the Study", content="Demo purpose.", status=FactStatusEnum.SUPPORTED),
        ])
        facts = ProtocolFacts(study_id="DEMO-TEST")
        rendered = render_template(template_bytes, "DEMO-TEST", draft, "patient_facing", facts=facts)
        assert len(rendered) > 0

def test_5_default_production_template_behavior_unchanged():
    assert DEFAULT_TEMPLATE_PATH.is_file()
    template_bytes = DEFAULT_TEMPLATE_PATH.read_bytes()
    draft = ICFDraft(sections=[
        ICFSection(section_id="study_title", title="Study Title", content="Default Production Study", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Production purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    facts = ProtocolFacts(
        study_id="PROD-TEST",
        study_title=TraceableFact(value="Default Production Study", status=FactStatusEnum.SUPPORTED)
    )
    rendered = render_template(template_bytes, "PROD-TEST", draft, "patient_facing", facts=facts)
    assert len(rendered) > 0
    from app.services.template_renderer import document_text
    full_text = document_text(rendered)
    assert "Default Production Study" in full_text

def test_6_grounding_safety_behavior_unchanged():
    template_bytes = create_subset_docx_template()
    # Section marked as NOT_FOUND
    draft = ICFDraft(sections=[
        ICFSection(section_id="study_title", title="Study Title", content="BioX Phase 2 Trial", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Not provided in the study protocol.", status=FactStatusEnum.NOT_FOUND),
    ])
    facts = ProtocolFacts(study_id="SAFETY-TEST")
    rendered_bytes = render_template(template_bytes, "SAFETY-TEST", draft, "patient_facing", facts=facts)
    rendered_doc = Document(io.BytesIO(rendered_bytes))
    full_text = "\n".join([p.text for p in rendered_doc.paragraphs])
    
    # Missing/NOT_FOUND purpose should use deterministic fallback text, not hallucinated clinical claims
    assert "Specific details regarding the study purpose were not provided in the study protocol." in full_text
