import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.protocol_facts import (
    ProtocolFacts,
    TraceableFact,
    FactStatusEnum,
    CategorizedFactList,
    EligibilityFacts
)
from app.models.icf import ICFGenerationRequest, ICFGenerationResponse, ICFDraft, ICFSection
from app.services.icf_generation_service import icf_generation_service
from app.services.protocol_analysis_agent import protocol_analysis_agent, deduplicate_fact_list, deduplicate_all_protocol_facts
from app.services.context_assembler import context_assembler
from app.models.rag import RAGRetrieveRequest

client = TestClient(app)

@pytest.fixture
def sample_protocol_facts_with_duplicates():
    """
    Creates a sample ProtocolFacts instance with overlapping / duplicate facts across retrieved chunks.
    """
    return ProtocolFacts(
        study_id="NCT00081328",
        study_title=TraceableFact[str](
            value="Treatment Options for Type 2 Diabetes in Adolescents and Youth (TODAY) Clinical Trial",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["NCT00081328_study_identification_001"]
        ),
        population=TraceableFact[str](
            value="Adolescents and youth aged 10-17 with type 2 diabetes",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["NCT00081328_eligibility_013"]
        ),
        interventions=[
            TraceableFact[str](
                value="Metformin 1000 mg bid",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_inv_001"]
            ),
            TraceableFact[str](
                value="Metformin 1000 mg bid;",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_inv_002"]
            ),
            TraceableFact[str](
                value="Rosiglitazone 4 mg bid",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_inv_003"]
            )
        ],
        objectives=CategorizedFactList(
            primary=[
                TraceableFact[str](
                    value="compare the efficacy of three treatment arms on time to treatment failure based on glycemic control",
                    status=FactStatusEnum.SUPPORTED,
                    source_evidence_ids=["chunk_obj_001"]
                ),
                TraceableFact[str](
                    value="compare the efficacy of three treatment arms on time to treatment failure based on glycemic control",
                    status=FactStatusEnum.SUPPORTED,
                    source_evidence_ids=["chunk_obj_002"]
                )
            ],
            secondary=[
                TraceableFact[str](
                    value="compare and evaluate the safety of the three treatment arms",
                    status=FactStatusEnum.SUPPORTED,
                    source_evidence_ids=["chunk_obj_003"]
                )
            ]
        ),
        eligibility=EligibilityFacts(
            inclusion=[
                TraceableFact[str](
                    value="Age 10 to 17 years at diagnosis of type 2 diabetes",
                    status=FactStatusEnum.SUPPORTED,
                    source_evidence_ids=["chunk_inc_001"]
                ),
                TraceableFact[str](
                    value="Age 10 to 17 years at diagnosis of type 2 diabetes;",
                    status=FactStatusEnum.SUPPORTED,
                    source_evidence_ids=["chunk_inc_002"]
                ),
                TraceableFact[str](
                    value="Duration since diagnosis less than two years by date of randomization",
                    status=FactStatusEnum.SUPPORTED,
                    source_evidence_ids=["chunk_inc_003"]
                )
            ],
            exclusion=[
                TraceableFact[str](
                    value="Participating in another interventional research study protocol in the past 30 days",
                    status=FactStatusEnum.SUPPORTED,
                    source_evidence_ids=["chunk_exc_001"]
                ),
                TraceableFact[str](
                    value="Participating in another interventional research study protocol in the past 30 days.",
                    status=FactStatusEnum.SUPPORTED,
                    source_evidence_ids=["chunk_exc_002"]
                )
            ]
        ),
        duration=TraceableFact[str](
            value="recruits patients over a three-year period and follows patients for a minimum of two years",
            status=FactStatusEnum.SUPPORTED,
            source_evidence_ids=["chunk_dur_001"]
        ),
        procedures=[
            TraceableFact[str](
                value="DXA scan to assess body composition and bone density",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_proc_001"]
            ),
            TraceableFact[str](
                value="DXA scan to assess body composition and bone density",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_proc_002"]
            )
        ],
        risks=[
            TraceableFact[str](
                value="Gastrointestinal side effects such as nausea or diarrhea",
                status=FactStatusEnum.SUPPORTED,
                source_evidence_ids=["chunk_risk_001"]
            )
        ],
        benefits=[],
        additional_facts=[]
    )

def test_1_duplicate_eligibility_facts_removed(sample_protocol_facts_with_duplicates):
    """
    Test 1: Duplicate eligibility criteria are deduplicated while preserving all unique source_evidence_ids.
    """
    deduped = deduplicate_all_protocol_facts(sample_protocol_facts_with_duplicates)
    assert len(deduped.eligibility.inclusion) == 2
    assert len(deduped.eligibility.exclusion) == 1

    age_fact = next(i for i in deduped.eligibility.inclusion if "Age 10 to 17" in i.value)
    assert "chunk_inc_001" in age_fact.source_evidence_ids
    assert "chunk_inc_002" in age_fact.source_evidence_ids

def test_2_duplicate_objectives_removed(sample_protocol_facts_with_duplicates):
    """
    Test 2: Duplicate primary/secondary objectives are deduplicated and source evidence IDs merged.
    """
    deduped = deduplicate_all_protocol_facts(sample_protocol_facts_with_duplicates)
    assert len(deduped.objectives.primary) == 1
    primary_obj = deduped.objectives.primary[0]
    assert "chunk_obj_001" in primary_obj.source_evidence_ids
    assert "chunk_obj_002" in primary_obj.source_evidence_ids

def test_3_duplicate_interventions_removed(sample_protocol_facts_with_duplicates):
    """
    Test 3: Duplicate intervention descriptions are deduplicated.
    """
    deduped = deduplicate_all_protocol_facts(sample_protocol_facts_with_duplicates)
    assert len(deduped.interventions) == 2
    met_fact = next(i for i in deduped.interventions if "Metformin" in i.value)
    assert "chunk_inv_001" in met_fact.source_evidence_ids
    assert "chunk_inv_002" in met_fact.source_evidence_ids

def test_4_different_facts_not_merged(sample_protocol_facts_with_duplicates):
    """
    Test 4: Genuinely different criteria or interventions are NOT accidentally merged.
    """
    deduped = deduplicate_all_protocol_facts(sample_protocol_facts_with_duplicates)
    inc_values = [i.value for i in deduped.eligibility.inclusion]
    assert any("Age 10 to 17" in v for v in inc_values)
    assert any("Duration since diagnosis" in v for v in inc_values)

    inv_values = [i.value for i in deduped.interventions]
    assert any("Metformin" in v for v in inv_values)
    assert any("Rosiglitazone" in v for v in inv_values)

def test_5_multiple_source_evidence_ids_preserved(sample_protocol_facts_with_duplicates):
    """
    Test 5: Multiple source evidence IDs are merged cleanly without duplicates.
    """
    res = icf_generation_service.generate_icf(ICFGenerationRequest(
        study_id="NCT00081328",
        analysis_facts=sample_protocol_facts_with_duplicates
    ))
    why_sec = next(s for s in res.icf_draft.sections if s.section_id == "why_asked")
    assert "chunk_inc_001" in why_sec.source_evidence_ids
    assert "chunk_inc_002" in why_sec.source_evidence_ids
    assert len(why_sec.source_evidence_ids) == len(set(why_sec.source_evidence_ids))

def test_6_purpose_language_natural_and_faithful(sample_protocol_facts_with_duplicates):
    """
    Test 6: Purpose section language is natural, participant-facing, and factually faithful without awkward phrases.
    """
    res = icf_generation_service.generate_icf(ICFGenerationRequest(
        study_id="NCT00081328",
        analysis_facts=sample_protocol_facts_with_duplicates
    ))
    purpose_sec = next(s for s in res.icf_draft.sections if s.section_id == "purpose")
    assert purpose_sec.status == FactStatusEnum.SUPPORTED
    assert "Primary Objectives:" in purpose_sec.content or "Main Goal" in purpose_sec.content
    assert "compare how well" in purpose_sec.content.lower() or "compare the efficacy" in purpose_sec.content.lower() or "effectiveness" in purpose_sec.content.lower()
    assert "; and;" not in purpose_sec.content

def test_7_patient_friendly_language_faithful(sample_protocol_facts_with_duplicates):
    """
    Test 7: Patient-friendly language simplifies terms without creating awkward phrases like 'compare the how well...'.
    """
    res = icf_generation_service.generate_icf(ICFGenerationRequest(
        study_id="NCT00081328",
        analysis_facts=sample_protocol_facts_with_duplicates,
        generate_patient_friendly=True
    ))
    assert res.patient_friendly_icf is not None
    pf_purpose_sec = next(s for s in res.patient_friendly_icf.sections if s.section_id == "purpose")
    assert "compare the how well" not in pf_purpose_sec.content
    assert "compare how well" in pf_purpose_sec.content or "effectiveness" in pf_purpose_sec.content or "blood sugar control" in pf_purpose_sec.content

def test_8_not_found_sections_remain_not_found(sample_protocol_facts_with_duplicates):
    """
    Test 8: Unsupported sections remain marked NOT_FOUND or are omitted.
    """
    res = icf_generation_service.generate_icf(ICFGenerationRequest(
        study_id="NCT00081328",
        analysis_facts=sample_protocol_facts_with_duplicates,
        generate_patient_friendly=True
    ))
    ben_sec = next((s for s in res.icf_draft.sections if s.section_id == "benefits"), None)
    assert ben_sec is None or ben_sec.status == FactStatusEnum.NOT_FOUND or "not provided" in ben_sec.content.lower()
    if res.patient_friendly_icf:
        pf_ben_sec = next((s for s in res.patient_friendly_icf.sections if s.section_id == "benefits"), None)
        assert pf_ben_sec is None or pf_ben_sec.status == FactStatusEnum.NOT_FOUND or "not provided" in pf_ben_sec.content.lower()

def test_9_no_unsupported_info_generated(sample_protocol_facts_with_duplicates):
    """
    Test 9: No unsupported information or fabricated contact details are generated.
    """
    res = icf_generation_service.generate_icf(ICFGenerationRequest(
        study_id="NCT00081328",
        analysis_facts=sample_protocol_facts_with_duplicates
    ))
    contact_sec = next((s for s in res.icf_draft.sections if s.section_id == "questions_contact"), None)
    assert contact_sec is None or contact_sec.status == FactStatusEnum.NOT_FOUND or "not provided" in contact_sec.content.lower()
