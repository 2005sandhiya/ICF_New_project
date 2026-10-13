import sys
import os
import json

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.services.study_loader import study_loader_service
from app.services.chunking.chunker import protocol_chunker_service
from app.services.vector_store import vector_store_service
from app.services.context_assembler import context_assembler
from app.services.protocol_analysis_agent import protocol_analysis_agent
from app.services.icf_generation_service import icf_generation_service
from app.models.rag import RAGRetrieveRequest

TARGET_STUDIES = ["NCT00162175", "NCT00081328", "NCT01713764"]

def audit_study(study_id: str):
    print(f"\n=======================================================")
    print(f"AUDITING STUDY: {study_id}")
    print(f"=======================================================")

    # 1. SOURCE JSON
    raw_entry = study_loader_service._studies_cache.get(study_id)
    if not raw_entry:
        print(f"ERROR: {study_id} not found in cache")
        return

    raw_json = raw_entry["raw"]
    protocol_sec = raw_json.get("protocolSection", {})
    
    ident = protocol_sec.get("identificationModule", {})
    status_mod = protocol_sec.get("statusModule", {})
    desc_mod = protocol_sec.get("descriptionModule", {})
    cond_mod = protocol_sec.get("conditionsModule", {})
    design_mod = protocol_sec.get("designModule", {})
    arms_mod = protocol_sec.get("armsInterventionsModule", {})
    outcomes_mod = protocol_sec.get("outcomesModule", {})
    elig_mod = protocol_sec.get("eligibilityModule", {})
    contacts_mod = protocol_sec.get("contactsLocationsModule", {})

    source_fields = {
        "brief_title": bool(ident.get("briefTitle")),
        "official_title": bool(ident.get("officialTitle")),
        "brief_summary": bool(desc_mod.get("briefSummary")),
        "detailed_description": bool(desc_mod.get("detailedDescription")),
        "phase": bool(design_mod.get("phases")),
        "study_type": bool(design_mod.get("studyType")),
        "allocation": bool(design_mod.get("designInfo", {}).get("allocation")),
        "intervention_model": bool(design_mod.get("designInfo", {}).get("interventionModel")),
        "masking": bool(design_mod.get("designInfo", {}).get("maskingInfo")),
        "enrollment": bool(design_mod.get("enrollmentInfo")),
        "interventions": bool(arms_mod.get("interventions")),
        "primary_outcomes": bool(outcomes_mod.get("primaryOutcomes")),
        "secondary_outcomes": bool(outcomes_mod.get("secondaryOutcomes")),
        "eligibility_criteria": bool(elig_mod.get("eligibilityCriteria")),
        "age": bool(elig_mod.get("minimumAge") or elig_mod.get("maximumAge")),
        "sex": bool(elig_mod.get("sex")),
        "locations": bool(contacts_mod.get("locations")),
    }

    print("\n--- 1. SOURCE JSON FIELDS PRESENT ---")
    for field, present in source_fields.items():
        print(f"  {field:22s}: {'PRESENT' if present else 'ABSENT'}")

    # 2. CANONICAL PROTOCOL & SOURCE SECTIONS
    canonical_resp = study_loader_service.get_study_as_canonical_protocol(study_id)
    cp = canonical_resp.protocol

    print(f"\n--- 2. CANONICAL PROTOCOL SOURCE SECTIONS ({len(cp.source_sections)}) ---")
    canonical_sec_names = [sec.section_name for sec in cp.source_sections]
    print(f"  Source Sections in CanonicalProtocol: {canonical_sec_names}")

    # 3. CHUNKING
    chunking_resp = study_loader_service.get_study_chunks(study_id)
    chunks = chunking_resp.chunks if chunking_resp else []
    chunk_sections = [c.section for c in chunks]
    print(f"\n--- 3. CHUNKS GENERATED ({len(chunks)}) ---")
    print(f"  Chunk Sections: {chunk_sections}")

    # 4. RAG RETRIEVAL & CONTEXT
    vector_store_service.clear()
    study_loader_service.get_study_embeddings(study_id)
    rag_req = RAGRetrieveRequest(study_id=study_id, query="informed consent study design interventions procedures objectives eligibility", top_k=5)
    rag_ctx = context_assembler.assemble_context(rag_req)
    print(f"\n--- 4 & 5. RAG RETRIEVAL & CONTEXT ({rag_ctx.evidence_count} evidence chunks) ---")
    for ev in rag_ctx.evidence:
        print(f"  Rank {ev.rank}: chunk_id='{ev.chunk_id}' (section='{ev.section}') score={ev.similarity_score:.4f}")

    # 6 & 7. PROTOCOLFACTS & DETERMINISTIC ICF SECTIONS
    comp_facts = protocol_analysis_agent.assemble_comprehensive_facts(study_id)
    raw_draft = icf_generation_service._deterministic_icf_generator(comp_facts)
    supported_sections = [
        sec for sec in raw_draft.sections
        if sec.status != "NOT_FOUND"
        and sec.content
        and not sec.content.strip().startswith("Not provided in the study protocol.")
    ]
    supported_sec_ids = [s.section_id for s in supported_sections]

    print(f"\n--- 8 & 9. ICF SECTIONS GENERATED vs KEPT AFTER POST-PROCESSING OMISSION ---")
    print(f"  Raw Generated Sections Count (before omission): {len(raw_draft.sections)}")
    print(f"  Supported Sections Kept (after omission filter): {len(supported_sections)}")
    print(f"  KEPT SECTION IDS: {supported_sec_ids}")
    print(f"  DISCARDED/OMITTED SECTION IDS: {[s.section_id for s in raw_draft.sections if s.section_id not in supported_sec_ids]}")

def main():
    for sid in TARGET_STUDIES:
        audit_study(sid)

if __name__ == "__main__":
    main()
