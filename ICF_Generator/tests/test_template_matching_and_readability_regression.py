import pytest
from app.models.icf import ICFDraft, ICFSection
from app.models.protocol_facts import FactStatusEnum
from app.services.validation_agent import validation_agent, ValidationAgent

def test_readability_formula_known_values():
    simple_content = 'This is a short study. You can ask questions at any time. We will help you understand.'
    draft = ICFDraft(
        study_id='TEST-001',
        sections=[ICFSection(section_id='s1', title='Intro', content=simple_content, status=FactStatusEnum.SUPPORTED)]
    )
    res, score = validation_agent._check_readability(draft)
    assert res.status == 'PASS'
    assert score == 98.0
    assert 'Grade 2.1' in res.details
    assert len(res.flagged_items) == 0

def test_readability_formula_warning_behavior():
    complex_content = (
        'The clinical investigation of this pharmaceutical intervention involves administering '
        'investigational pharmacological formulations under strict monitoring parameters and procedures. '
        'Sub-investigators will execute comprehensive neurological assessments continuously throughout participation.'
    )
    draft = ICFDraft(
        study_id='TEST-001',
        sections=[ICFSection(section_id='s1', title='Complex', content=complex_content, status=FactStatusEnum.SUPPORTED)]
    )
    res, score = validation_agent._check_readability(draft)
    assert res.status == 'WARNING'
    assert score == 80.0
    assert len(res.flagged_items) > 0
    assert 'exceeds recommended 8th grade target' in res.flagged_items[0]

def test_readability_label_confirmation():
    simple_content = 'This is a simple text for testing.'
    draft = ICFDraft(
        study_id='TEST-001',
        sections=[ICFSection(section_id='s1', title='Intro', content=simple_content, status=FactStatusEnum.SUPPORTED)]
    )
    res, _ = validation_agent._check_readability(draft)
    assert res.details.startswith('Estimated reading level: Grade')
    assert 'proves patient-friendly' not in res.details.lower()

def test_existing_source_evidence_validation_unchanged():
    draft = ICFDraft(
        study_id='TEST-001',
        sections=[
            ICFSection(section_id='s1', title='Grounded', content='This section has protocol evidence.', status=FactStatusEnum.SUPPORTED, source_evidence_ids=['chunk-1']),
            ICFSection(section_id='s2', title='Ungrounded', content='This section lacks evidence.', status=FactStatusEnum.SUPPORTED, source_evidence_ids=[])
        ]
    )
    res, score = validation_agent._check_traceability(draft)
    assert res.status == 'WARNING'
    assert score == 50.0
    assert len(res.flagged_items) == 1
    assert 'marked SUPPORTED but has empty source_evidence_ids' in res.flagged_items[0]

def test_template_compatibility_logic_simulation():
    def check_template_matches(icf_template_id, selected_template_id, has_error=False):
        return bool(icf_template_id) and bool(selected_template_id) and (icf_template_id == selected_template_id) and not has_error

    assert check_template_matches('builtin-v1', 'builtin-v1') is True
    assert check_template_matches('builtin-v1', 'custom-v2') is False
    assert check_template_matches(None, 'builtin-v1') is False
    assert check_template_matches('builtin-v1', None) is False
    assert check_template_matches('builtin-v1', 'builtin-v1', has_error=True) is False
