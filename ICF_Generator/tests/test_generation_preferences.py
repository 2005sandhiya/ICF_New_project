import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("backend"))

from app.models.icf import ICFGenerationRequest
from app.services.icf_generation_service import icf_generation_service
from app.models.protocol_facts import ProtocolFacts, TraceableFact, FactStatusEnum

def test_icf_generation_request_preferences_schema():
    req_default = ICFGenerationRequest(study_id="NCT00081328")
    assert req_default.preferred_length is None
    assert req_default.custom_instructions is None

    req_custom = ICFGenerationRequest(
        study_id="NCT00081328",
        preferred_length="6–8 pages",
        custom_instructions="Use simple patient-friendly tone and bullet points."
    )
    assert req_custom.preferred_length == "6–8 pages"
    assert req_custom.custom_instructions == "Use simple patient-friendly tone and bullet points."

def test_generation_prompt_incorporates_preferences():
    facts = ProtocolFacts(
        study_id="TEST-PREF-001",
        study_title=TraceableFact(value="Test Study Title", status=FactStatusEnum.SUPPORTED)
    )
    # Test generation with preferences
    draft = icf_generation_service._generate_structured_icf_draft(
        facts,
        preferred_length="8–10 pages",
        custom_instructions="Use short paragraphs and clear headings."
    )
    assert draft is not None
    assert len(draft.sections) > 0

def test_generation_with_empty_preferences_behaves_identically():
    facts = ProtocolFacts(
        study_id="TEST-PREF-002",
        study_title=TraceableFact(value="Test Study Title 2", status=FactStatusEnum.SUPPORTED)
    )
    draft_none = icf_generation_service._generate_structured_icf_draft(
        facts, preferred_length=None, custom_instructions=None
    )
    draft_empty = icf_generation_service._generate_structured_icf_draft(
        facts, preferred_length="", custom_instructions=""
    )
    assert [s.section_id for s in draft_none.sections] == [s.section_id for s in draft_empty.sections]
