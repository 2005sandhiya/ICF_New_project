"""Focused tests covering the 13 specified rules for the 3 target removable sections:
1. How Long Will Participation Last?
2. Risks and Discomforts
3. Possible Benefits
"""
import io
import docx
import pytest
import re
from app.models.icf import ICFDraft, ICFSection, FactStatusEnum
from app.models.protocol_facts import ProtocolFacts, TraceableFact
from app.services.template_service import template_service
from app.services.template_renderer import render_template


@pytest.fixture
def default_template_bytes():
    return template_service.read("TEST_TARGET_3", template_service.selection("TEST_TARGET_3"))


def get_full_text(doc_bytes):
    doc = docx.Document(io.BytesIO(doc_bytes))
    p_text = "\n".join(p.text for p in doc.paragraphs)
    t_text = "\n".join(" ".join(c.text for c in r.cells) for t in doc.tables for r in t.rows)
    return p_text + "\n" + t_text


def get_numbered_headings(doc_bytes):
    doc = docx.Document(io.BytesIO(doc_bytes))
    headings = []
    for p in doc.paragraphs:
        if p.text.strip():
            m = re.match(r"^\s*(\d+)\.\s+(.*)$", p.text.strip())
            if m:
                headings.append((int(m.group(1)), m.group(2).strip(), p.text.strip()))
    return headings


# Test 1: Grounded duration content is rendered when available.
def test_1_grounded_duration_rendered(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="duration", title="How Long Will Participation Last?", content="Participation lasts 12 weeks with 4 visits.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    full_text = get_full_text(rendered)
    assert "Participation lasts 12 weeks with 4 visits." in full_text
    headings = get_numbered_headings(rendered)
    assert any("Duration" in h[1] for h in headings)


# Test 2: Missing duration populates explicit evidence-absence statement instead of empty space.
def test_2_missing_duration_populated_with_fallback(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    full_text = get_full_text(rendered)
    headings = get_numbered_headings(rendered)
    assert any("Duration" in h[1] or "How Long" in h[1] for h in headings)
    assert "not provided in the study protocol" in full_text


# Test 3: Grounded risk content is rendered when available.
def test_3_grounded_risks_rendered(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="risks", title="Risks and Discomforts", content="Mild headaches and fatigue were reported in 5% of subjects.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    full_text = get_full_text(rendered)
    assert "Mild headaches and fatigue were reported in 5% of subjects." in full_text
    assert any("Risks and Discomforts" in h[1] for h in get_numbered_headings(rendered))


# Test 4: Missing risks populates explicit evidence-absence statement instead of empty space.
def test_4_missing_risks_populated_with_fallback(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    full_text = get_full_text(rendered)
    headings = get_numbered_headings(rendered)
    assert any("Risks and Discomforts" in h[1] or "Risks and Side Effects" in h[1] for h in headings)
    assert "not provided in the study protocol" in full_text


# Test 5: Grounded benefits content is rendered when available.
def test_5_grounded_benefits_rendered(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="benefits", title="Possible Benefits", content="Potential direct clinical response and improvement of symptoms.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    full_text = get_full_text(rendered)
    assert "Potential direct clinical response and improvement of symptoms." in full_text
    assert any("Possible Benefits" in h[1] or "Potential Benefits" in h[1] for h in get_numbered_headings(rendered))


# Test 6: Missing benefits populates explicit evidence-absence statement instead of empty space.
def test_6_missing_benefits_populated_with_fallback(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    full_text = get_full_text(rendered)
    headings = get_numbered_headings(rendered)
    assert any("Possible Benefits" in h[1] or "Potential Benefits" in h[1] for h in headings)
    assert "not provided in the study protocol" in full_text


# Test 7: No raw [DURATION] bracket token remains in final rendered document.
def test_7_no_duration_placeholder_remains(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    full_text = get_full_text(rendered)
    assert "[DURATION]" not in full_text
    assert "[STUDY_DURATION]" not in full_text
    assert "[HOW_LONG_WILL_PARTICIPATION_LAST]" not in full_text


# Test 8: No raw [BENEFITS] bracket token remains in final rendered document.
def test_8_no_benefits_placeholder_remains(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    full_text = get_full_text(rendered)
    assert "[BENEFITS]" not in full_text
    assert "[POSSIBLE_BENEFITS]" not in full_text
    assert "[POTENTIAL_BENEFITS]" not in full_text


# Test 9: No empty section content remains.
def test_9_no_empty_heading_remains(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    doc = docx.Document(io.BytesIO(rendered))
    p_texts = [p.text.strip() for p in doc.paragraphs]
    for idx, t in enumerate(p_texts):
        if any(h in t.lower() for h in ["how long will participation last", "risks and discomforts", "possible benefits"]):
            following = [p for p in p_texts[idx+1:] if p]
            assert len(following) > 0 and not following[0].startswith("[")


# Test 10: Section numbering remains correct.
def test_10_section_numbering_correct_after_removal(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    headings = get_numbered_headings(rendered)
    numbers = [h[0] for h in headings]
    assert numbers == list(range(1, len(numbers) + 1))


# Test 11: Other sections remain unchanged.
def test_11_other_sections_remain_unchanged(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="voluntary", title="Voluntary Participation", content="Participation is strictly voluntary.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    full_text = get_full_text(rendered)
    assert "Purpose of the Study" in full_text
    assert "Participation is strictly voluntary." in full_text
    headings = get_numbered_headings(rendered)
    assert any("Voluntary Participation" in h[1] for h in headings)


# Test 12: Ordinary user form fields remain unchanged.
def test_12_ordinary_user_form_fields_remain(default_template_bytes):
    from tests.test_custom_template_placeholders import create_docx_with_text
    docx_custom = create_docx_with_text([
        "Participant Consent Document",
        "1. Purpose of the Study",
        "[PURPOSE_OF_STUDY]",
        "Participant Name: [Name]",
        "Date: [Date]",
        "Signature: [Signature]"
    ])
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered_custom = render_template(docx_custom, "TEST_STUDY_CUSTOM", draft, "patient_facing")
    full_text_custom = get_full_text(rendered_custom)
    assert "[Name]" in full_text_custom
    assert "[Date]" in full_text_custom
    assert "[Signature]" in full_text_custom

    rendered_default = render_template(default_template_bytes, "TEST_STUDY_DEFAULT", draft, "patient_facing")
    full_text_default = get_full_text(rendered_default)
    assert "[INVESTIGATOR_SIGNATURE]" in full_text_default


# Test 13: No unsupported clinical information is invented.
def test_13_no_invented_clinical_info(default_template_bytes):
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(default_template_bytes, "TEST_STUDY", draft, "patient_facing")
    full_text = get_full_text(rendered)
    assert "Guaranteed cure" not in full_text
    assert "Severe internal bleeding" not in full_text


# Test 14: "Information for participants: [DURATION]" with no duration -> populated with fallback statement.
def test_14_information_for_participants_duration_populated_when_ungrounded():
    from tests.test_custom_template_placeholders import create_docx_with_text
    docx_bytes = create_docx_with_text([
        "Participant Information and Consent Document",
        "1. Purpose of the Study",
        "[PURPOSE_OF_STUDY]",
        "How Long Will Participation Last?",
        "Information for participants: [DURATION]",
        "Participant Name: [Name]",
    ])
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(docx_bytes, "TEST_INFO_DUR", draft, "patient_facing")
    full_text = get_full_text(rendered)
    assert "How Long Will Participation Last" in full_text
    assert "not provided in the study protocol" in full_text
    assert "[DURATION]" not in full_text
    assert "[Name]" in full_text


# Test 15: "Information for participants: [BENEFITS]" with no benefits -> populated with fallback statement.
def test_15_information_for_participants_benefits_populated_when_ungrounded():
    from tests.test_custom_template_placeholders import create_docx_with_text
    docx_bytes = create_docx_with_text([
        "Participant Information and Consent Document",
        "1. Purpose of the Study",
        "[PURPOSE_OF_STUDY]",
        "Possible Benefits",
        "Information for participants: [BENEFITS]",
        "Participant Name: [Name]",
    ])
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(docx_bytes, "TEST_INFO_BEN", draft, "patient_facing")
    full_text = get_full_text(rendered)
    assert "Possible Benefits" in full_text
    assert "not provided in the study protocol" in full_text
    assert "[BENEFITS]" not in full_text
    assert "[Name]" in full_text


# Test 16: Grounded duration/benefit content remains.
def test_16_grounded_duration_and_benefit_content_remains():
    from tests.test_custom_template_placeholders import create_docx_with_text
    docx_bytes = create_docx_with_text([
        "Participant Information and Consent Document",
        "1. Purpose of the Study",
        "[PURPOSE_OF_STUDY]",
        "How Long Will Participation Last?",
        "Information for participants: [DURATION]",
        "Possible Benefits",
        "Information for participants: [BENEFITS]",
    ])
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="duration", title="How Long Will Participation Last?", content="Study duration is 6 months.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="benefits", title="Possible Benefits", content="Direct symptom improvement.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(docx_bytes, "TEST_GROUNDED_DUR_BEN", draft, "patient_facing")
    full_text = get_full_text(rendered)
    assert "How Long Will Participation Last" in full_text
    assert "Study duration is 6 months." in full_text
    assert "Possible Benefits" in full_text
    assert "Direct symptom improvement." in full_text


# Test 17: Other sections remain unchanged.
def test_17_other_sections_remain_unchanged_when_duration_benefits_removed():
    from tests.test_custom_template_placeholders import create_docx_with_text
    docx_bytes = create_docx_with_text([
        "Participant Information and Consent Document",
        "1. Purpose of the Study",
        "[PURPOSE_OF_STUDY]",
        "How Long Will Participation Last?",
        "Information for participants: [DURATION]",
        "2. Voluntary Participation",
        "[VOLUNTARY_PARTICIPATION]",
    ])
    draft = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="Grounded purpose text.", status=FactStatusEnum.SUPPORTED),
        ICFSection(section_id="voluntary", title="Voluntary Participation", content="Participation is optional.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered = render_template(docx_bytes, "TEST_OTHER_SECS", draft, "patient_facing")
    full_text = get_full_text(rendered)
    assert "How Long Will Participation Last" in full_text
    assert "not provided in the study protocol" in full_text
    assert "Voluntary Participation" in full_text
    assert "Participation is optional." in full_text


# Test 18: Specific regression test verifying unsupported risks, benefits, and duration receive evidence-absence statements.
def test_18_unsupported_sections_populated_with_fallback_and_form_fields_preserved():
    from tests.test_custom_template_placeholders import create_docx_with_text
    docx_bytes = create_docx_with_text([
        "Informed Consent Document",
        "1. Purpose of the Study",
        "[PURPOSE_OF_STUDY]",
        "2. How Long Will Participation Last?",
        "Information for participants: [DURATION]",
        "3. Risks and Side Effects",
        "[RISKS_AND_SIDE_EFFECTS]",
        "4. Potential Benefits",
        "[POTENTIAL_BENEFITS_TO_PARTICIPANT]",
        "5. Pregnancy, Breastfeeding and Fertility",
        "[PREGNANCY_RISK_STATEMENT]",
        "Participant Name: [Name]",
        "Date: [Date]",
        "Signature: [Signature]"
    ])
    draft_unsupported = ICFDraft(sections=[
        ICFSection(section_id="purpose", title="Purpose of the Study", content="This study evaluates drug X.", status=FactStatusEnum.SUPPORTED),
    ])
    rendered_a = render_template(docx_bytes, "TEST_E2E_UNSUPPORTED", draft_unsupported, "patient_facing")
    full_text_a = get_full_text(rendered_a)

    # 1. Headings are preserved
    assert "How Long Will Participation Last" in full_text_a
    assert "Risks and Side Effects" in full_text_a
    assert "Potential Benefits" in full_text_a

    # 2. Raw bracket placeholders replaced with evidence-absence statements
    assert "[DURATION]" not in full_text_a
    assert "[RISKS_AND_SIDE_EFFECTS]" not in full_text_a
    assert "[POTENTIAL_BENEFITS_TO_PARTICIPANT]" not in full_text_a
    assert "not provided in the study protocol" in full_text_a

    # 3. Form fields preserved
    assert "[Name]" in full_text_a
    assert "[Date]" in full_text_a
    assert "[Signature]" in full_text_a


