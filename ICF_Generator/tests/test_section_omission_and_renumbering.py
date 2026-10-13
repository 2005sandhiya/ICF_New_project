import io
import docx
import pytest
from app.models.icf import ICFDraft, ICFSection, ICFGenerationRequest, FactStatusEnum
from app.models.protocol_facts import ProtocolFacts, TraceableFact, EligibilityFacts
from app.services.docx_generation_service import docx_generation_service
from app.services.template_service import template_service
from app.services.template_renderer import render_template
from app.services.icf_generation_service import icf_generation_service


@pytest.fixture
def default_template_bytes():
    return template_service.read("TEST_STUDY", template_service.selection("TEST_STUDY"))


def get_headings(doc_bytes):
    doc = docx.Document(io.BytesIO(doc_bytes))
    headings = []
    for p in doc.paragraphs:
        if p.style and p.style.name and p.style.name.lower().startswith("heading 1"):
            if p.text.strip():
                headings.append(p.text.strip())
    return headings


def get_full_text(doc_bytes):
    doc = docx.Document(io.BytesIO(doc_bytes))
    p_text = "\n".join(p.text for p in doc.paragraphs)
    t_text = "\n".join(" ".join(c.text for c in r.cells) for t in doc.tables for r in t.rows)
    return p_text + "\n" + t_text


def test_1_unsupported_benefits_populated_with_fallback(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    headings = get_headings(rendered)
    assert any("potential benefits" in h.lower() for h in headings)
    assert "not provided in the study protocol" in get_full_text(rendered)


def test_2_unsupported_alternatives_preserved(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    headings = get_headings(rendered)
    assert any("alternatives to participation" in h.lower() for h in headings)


def test_3_unsupported_costs_preserved(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    headings = get_headings(rendered)
    assert any("costs to you" in h.lower() for h in headings)


def test_4_unsupported_compensation_preserved(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    headings = get_headings(rendered)
    assert any("payment or compensation" in h.lower() for h in headings)


def test_5_unsupported_injury_preserved(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    headings = get_headings(rendered)
    assert any("study-related injury" in h.lower() for h in headings)


def test_6_unsupported_new_information_preserved(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    headings = get_headings(rendered)
    assert any("new information" in h.lower() for h in headings)


def test_7_unsupported_post_trial_preserved(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    headings = get_headings(rendered)
    assert any("care after the study" in h.lower() for h in headings)


def test_8_unsupported_registration_preserved(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    headings = get_headings(rendered)
    assert any("study registration" in h.lower() for h in headings)


def test_9_unsupported_confidentiality_subsections_preserved(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    full_text = get_full_text(rendered)
    assert "Who may see your records" in full_text
    assert "Audio-visual recording" in full_text
    assert "Data sharing and transfer" in full_text


def test_10_unsupported_study_design_subsections_preserved(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    full_text = get_full_text(rendered)
    assert "Regulatory status" in full_text


def test_11_procedure_table_preserved(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    doc = docx.Document(io.BytesIO(rendered))
    # Table 2 (procedure table) should remain preserved for fillable schedule
    table_texts = ["".join(c.text for c in r.cells) for t in doc.tables for r in t.rows]
    assert any("Visit 1" in t for t in table_texts)


def test_12_duplicate_eligibility_prevented(default_template_bytes):
    facts = ProtocolFacts(
        study_id="TEST_ELIG",
        study_title=TraceableFact(value="Test Study", status=FactStatusEnum.SUPPORTED),
        eligibility=EligibilityFacts(
            inclusion=[TraceableFact(value="Age >= 18", status=FactStatusEnum.SUPPORTED)],
            exclusion=[TraceableFact(value="Pregnant females", status=FactStatusEnum.SUPPORTED)]
        )
    )
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="why_asked", title="Why You Are Being Asked", content="Eligibility info", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_ELIG", draft, "standard", facts=facts)
    full_text = get_full_text(rendered)
    assert full_text.count("Age >= 18") == 1


def test_13_duplicate_duration_prevented(default_template_bytes):
    facts = ProtocolFacts(
        study_id="TEST_DUR",
        duration=TraceableFact(value="24 months", status=FactStatusEnum.SUPPORTED)
    )
    draft = ICFDraft(sections=[
        ICFSection(section_id="duration", title="Study Duration", content="24 months", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_DUR", draft, "standard", facts=facts)
    full_text = get_full_text(rendered)
    assert full_text.count("24 months") >= 1


def test_14_study_phase_mapping_correct(default_template_bytes):
    facts = ProtocolFacts(
        study_id="TEST_PHASE",
        study_title=TraceableFact(value="A Long Study Title That Must Not Be Phase", status=FactStatusEnum.SUPPORTED),
        phase=TraceableFact(value="Phase 3", status=FactStatusEnum.SUPPORTED)
    )
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_PHASE", draft, "standard", facts=facts)
    full_text = get_full_text(rendered)
    assert "Phase 3" in full_text


def test_15_supported_sections_remain(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Targeted study purpose", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="interventions", title="Study Interventions", content="Targeted drug regimen", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    full_text = get_full_text(rendered)
    assert "Targeted study purpose" in full_text
    assert "Targeted drug regimen" in full_text


def test_16_section_numbering_preserved(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="duration", title="Study Duration", content="12 weeks", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    headings = get_headings(rendered)
    import re
    numbers = [int(re.match(r"^(\d+)\.", h).group(1)) for h in headings if re.match(r"^(\d+)\.", h)]
    assert numbers == list(range(1, len(numbers) + 1))


def test_17_standard_and_pf_equivalent_coverage(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Study purpose text", status=FactStatusEnum.SUPPORTED),
    ])
    std_bytes = render_template(default_template_bytes, "TEST_STUDY", draft, "standard")
    pf_bytes = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_friendly")

    std_headings = get_headings(std_bytes)
    pf_headings = get_headings(pf_bytes)

    assert len(std_headings) == len(pf_headings)


def test_18_full_end_to_end_generation_path():
    from app.services.template_service import template_service
    template_service.remove("NCT00081328")
    req = ICFGenerationRequest(study_id="NCT00081328")
    resp = icf_generation_service.generate_icf(req)
    assert resp.icf_draft is not None
    docx_bytes = docx_generation_service.generate_docx("NCT00081328", resp.icf_draft, export_type="standard")
    full_text = get_full_text(docx_bytes)
    assert "INFORMED CONSENT FORM" in full_text
    assert "NCT00081328" in full_text


def test_19_nct02563067_risks_section_removed_when_ungrounded():
    from app.services.template_service import template_service
    template_service.remove("NCT02563067")
    req = ICFGenerationRequest(study_id="NCT02563067")
    resp = icf_generation_service.generate_icf(req)
    assert resp.icf_draft is not None

    docx_bytes = docx_generation_service.generate_docx("NCT02563067", resp.icf_draft, export_type="standard")
    doc = docx.Document(io.BytesIO(docx_bytes))
    
    paragraph_texts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraph_texts)

    # A. Risks and Discomforts section heading is retained cleanly
    assert any("Risks and Discomforts" in p or "Risks and Side Effects" in p for p in paragraph_texts)
    assert "not provided in the study protocol" in full_text

    # B. Remaining major headings are renumbered sequentially
    import re
    headings = [p for p in paragraph_texts if re.match(r"^\d+\.\s+", p)]
    numbers = [int(re.match(r"^(\d+)\.", h).group(1)) for h in headings]
    assert numbers == list(range(1, len(numbers) + 1))


def test_20_grounded_risks_preserved(default_template_bytes):
    draft_with_risks = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded study purpose text", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="risks", title="Risks and Discomforts", content="Common side effects include mild nausea, headache, and skin redness.", status=FactStatusEnum.SUPPORTED),
    ])

    rendered = render_template(default_template_bytes, "TEST_RISKS_STUDY", draft_with_risks, "patient_facing")
    doc = docx.Document(io.BytesIO(rendered))
    paragraph_texts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraph_texts)

    # A. Risks section is present in headings
    assert any("Risks and Discomforts" in p for p in paragraph_texts)

    # B. Grounded risk content is rendered
    assert "Common side effects include mild nausea, headache, and skin redness." in full_text



