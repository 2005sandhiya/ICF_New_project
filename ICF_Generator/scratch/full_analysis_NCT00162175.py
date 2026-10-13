import sys
import os
import json

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.services.study_loader import study_loader_service
from app.services.canonicalization.json_canonicalizer import JSONCanonicalizer
from app.services.canonicalization.canonicalization_engine import canonicalization_engine
from app.services.chunking.chunker import protocol_chunker_service
from app.services.vector_store import vector_store_service
from app.services.context_assembler import context_assembler
from app.services.protocol_analysis_agent import protocol_analysis_agent
from app.services.icf_generation_service import icf_generation_service
from app.models.rag import RAGRetrieveRequest

def main():
    study_id = "NCT00162175"
    raw_entry = study_loader_service._studies_cache.get(study_id)
    raw_json = raw_entry["raw"]
    protocol_sec = raw_json.get("protocolSection", {})

    print("=== FIELD COMPARISON TABLE ANALYSIS FOR NCT00162175 ===")
    
    # 1. Source JSON check
    json_has = {
        "Study purpose": bool(protocol_sec.get("descriptionModule", {}).get("briefSummary")),
        "Study phase": bool(protocol_sec.get("designModule", {}).get("phases")),
        "Study design": bool(protocol_sec.get("designModule", {}).get("designInfo")),
        "Enrollment": bool(protocol_sec.get("designModule", {}).get("enrollmentInfo")),
        "Intervention": bool(protocol_sec.get("armsInterventionsModule", {}).get("interventions")),
        "Outcomes": bool(protocol_sec.get("outcomesModule", {}).get("primaryOutcomes")),
        "Eligibility": bool(protocol_sec.get("eligibilityModule", {}).get("eligibilityCriteria")),
        "Age": bool(protocol_sec.get("eligibilityModule", {}).get("minimumAge")),
        "Sex": bool(protocol_sec.get("eligibilityModule", {}).get("sex")),
        "Locations": bool(protocol_sec.get("contactsLocationsModule", {}).get("locations")),
    }

    # 2. CanonicalProtocol check
    canonical_resp = study_loader_service.get_study_as_canonical_protocol(study_id)
    cp = canonical_resp.protocol

    # 3. Chunks & Vector Store check
    chunking_resp = study_loader_service.get_study_chunks(study_id)
    chunks = chunking_resp.chunks if chunking_resp else []
    vector_store_service.clear()
    study_loader_service.get_study_embeddings(study_id)
    
    # Check indexed text in chunks
    indexed_text = "\n".join([c.text for c in chunks])

    # 4. RAG Context check
    comp_facts = protocol_analysis_agent.assemble_comprehensive_facts(study_id)
    
    # 5. Deterministic ICF Draft & Section Omission check
    raw_draft = icf_generation_service._deterministic_icf_generator(comp_facts)
    supported_sections = [
        sec for sec in raw_draft.sections
        if sec.status != "NOT_FOUND"
        and sec.content
        and not sec.content.strip().startswith("Not provided in the study protocol.")
    ]
    supported_sec_ids = [s.section_id for s in supported_sections]

    print(f"\nSource Sections created in CanonicalProtocol ({len(cp.source_sections)}):")
    for ss in cp.source_sections:
        print(f"  - '{ss.section_name}': {ss.heading}")

    print(f"\nChunk count generated from CanonicalProtocol: {len(chunks)}")
    for c in chunks:
        print(f"  - Chunk ID: {c.chunk_id} (Section: '{c.section}')")

    print("\n--- STAGE COMPARISON ---")
    print(f"JSON Purpose present: {json_has['Study purpose']}")
    print(f"JSON Phase: {protocol_sec.get('designModule', {}).get('phases')}")
    print(f"JSON DesignInfo: {protocol_sec.get('designModule', {}).get('designInfo')}")
    print(f"JSON Enrollment: {protocol_sec.get('designModule', {}).get('enrollmentInfo')}")
    print(f"JSON Interventions: {protocol_sec.get('armsInterventionsModule', {}).get('interventions')}")
    print(f"JSON Outcomes: {protocol_sec.get('outcomesModule', {}).get('primaryOutcomes')}")
    print(f"JSON Eligibility: {bool(protocol_sec.get('eligibilityModule', {}).get('eligibilityCriteria'))}")
    print(f"JSON Age: min={protocol_sec.get('eligibilityModule', {}).get('minimumAge')}, max={protocol_sec.get('eligibilityModule', {}).get('maximumAge')}")
    print(f"JSON Sex: {protocol_sec.get('eligibilityModule', {}).get('sex')}")

    print("\n--- ProtocolFacts Values Extracted ---")
    print(f"ProtocolFacts title: {comp_facts.study_title.value}")
    print(f"ProtocolFacts phase: {comp_facts.phase.value}")
    print(f"ProtocolFacts population: {comp_facts.population.value}")
    print(f"ProtocolFacts duration: {comp_facts.duration.value}")
    print(f"ProtocolFacts interventions ({len(comp_facts.interventions)}): {[i.value for i in comp_facts.interventions]}")
    print(f"ProtocolFacts inclusion ({len(comp_facts.eligibility.inclusion if comp_facts.eligibility else [])}): {[i.value for i in (comp_facts.eligibility.inclusion if comp_facts.eligibility else [])]}")
    print(f"ProtocolFacts exclusion ({len(comp_facts.eligibility.exclusion if comp_facts.eligibility else [])}): {[e.value for e in (comp_facts.eligibility.exclusion if comp_facts.eligibility else [])]}")

    print("\n--- Final Kept ICF Sections ({len(supported_sec_ids)}) ---")
    for s in supported_sections:
        print(f"  [{s.section_id}] {s.title}:\n{s.content[:150]}\n")

if __name__ == "__main__":
    main()
