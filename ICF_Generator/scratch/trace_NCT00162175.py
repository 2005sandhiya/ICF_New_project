import sys
import os
import json

# Add backend directory to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.services.study_loader import study_loader_service
from app.services.canonicalization.canonicalization_engine import canonicalization_engine
from app.services.chunking.chunker import protocol_chunker_service
from app.services.vector_store import vector_store_service
from app.services.context_assembler import context_assembler
from app.services.protocol_analysis_agent import protocol_analysis_agent
from app.services.icf_generation_service import icf_generation_service
from app.models.rag import RAGRetrieveRequest

def main():
    study_id = "NCT00162175"
    print("=== DIAGNOSTIC TRACE FOR STUDY NCT00162175 ===")

    # Stage 1: Raw JSON & Study Loader
    print("\n--- STAGE 1: RAW JSON & STUDY LOADER ---")
    raw_entry = study_loader_service._studies_cache.get(study_id)
    if not raw_entry:
        print(f"CRITICAL: Study {study_id} not found in StudyLoader cache!")
        return

    raw_json = raw_entry["raw"]
    protocol_sec = raw_json.get("protocolSection", {})
    print(f"Raw protocolSection modules present: {list(protocol_sec.keys())}")
    
    ident = protocol_sec.get("identificationModule", {})
    design_mod = protocol_sec.get("designModule", {})
    elig_mod = protocol_sec.get("eligibilityModule", {})
    outcomes_mod = protocol_sec.get("outcomesModule", {})
    interventions_mod = protocol_sec.get("armsInterventionsModule", {})
    description_mod = protocol_sec.get("descriptionModule", {})
    contacts_mod = protocol_sec.get("contactsLocationsModule", {})

    print(f"  Title: {ident.get('officialTitle') or ident.get('briefTitle')}")
    print(f"  Brief Summary: {description_mod.get('briefSummary')[:100] if description_mod.get('briefSummary') else None}")
    print(f"  Design Info: {design_mod.get('designInfo')}")
    print(f"  Phases: {design_mod.get('phases')}")
    print(f"  Enrollment: {design_mod.get('enrollmentInfo')}")
    print(f"  Interventions count: {len(interventions_mod.get('interventions', []))}")
    print(f"  Outcomes count: primary={len(outcomes_mod.get('primaryOutcomes', []))}, secondary={len(outcomes_mod.get('secondaryOutcomes', []))}")
    print(f"  Eligibility keys: {list(elig_mod.keys())}")
    print(f"  Locations count: {len(contacts_mod.get('locations', []))}")

    # Stage 2: Canonical Protocol
    print("\n--- STAGE 2: CANONICAL PROTOCOL ---")
    canonical_resp = study_loader_service.get_study_as_canonical_protocol(study_id)
    if not canonical_resp:
        print("CRITICAL: Failed to canonicalize study JSON")
        return
    cp = canonical_resp.protocol
    print(f"Canonical Study ID: {cp.study_id}")
    print(f"Canonical Title: {cp.title}")
    print(f"Canonical Phase: {cp.phase}")
    print(f"Canonical Population: {cp.population}")
    print(f"Canonical Duration: {cp.duration}")
    print(f"Canonical Eligibility inclusion len: {len(cp.eligibility.inclusion)}")
    print(f"Canonical Eligibility exclusion len: {len(cp.eligibility.exclusion)}")
    print(f"Canonical Interventions count: {len(cp.interventions)}")
    print(f"Canonical Outcomes count: primary={len(cp.outcomes.primary)}, secondary={len(cp.outcomes.secondary)}")
    print(f"Canonical Source Sections Count: {len(cp.source_sections)}")
    for sec in cp.source_sections:
        print(f"  Source Section Name: '{sec.section_name}' | Heading: '{sec.heading}' | Content len: {len(sec.content)}")

    # Stage 3: Chunks & Vector Store
    print("\n--- STAGE 3: CHUNKING & FAISS INDEXING ---")
    chunking_resp = study_loader_service.get_study_chunks(study_id)
    print(f"Chunks generated count: {chunking_resp.chunk_count if chunking_resp else 0}")
    if chunking_resp:
        for c in chunking_resp.chunks:
            print(f"  Chunk ID: {c.chunk_id} | Section: '{c.section}' | Sub: '{c.subsection}' | Text len: {len(c.text)}")
    
    # Ensure indexed in vector store
    vector_store_service.clear()
    study_loader_service.get_study_embeddings(study_id)
    indexed_count = vector_store_service.chunk_count
    print(f"FAISS Indexed Chunk Count: {indexed_count}")

    # Stage 4: RAG Context Assembly
    print("\n--- STAGE 4: RAG CONTEXT ASSEMBLY ---")
    rag_req = RAGRetrieveRequest(study_id=study_id, query="informed consent study details eligibility interventions procedures", top_k=5)
    rag_ctx = context_assembler.assemble_context(rag_req)
    print(f"RAG Context Evidence Count (top_k=5): {rag_ctx.evidence_count}")
    for ev in rag_ctx.evidence:
        print(f"  Rank {ev.rank}: {ev.chunk_id} (sec='{ev.section}', sub='{ev.subsection}') score={ev.similarity_score:.4f}")
        print(f"    Snippet: {ev.text[:120]}...")

    # Stage 5 & 6: ProtocolFacts & Comprehensive Facts
    print("\n--- STAGE 5 & 6: PROTOCOL FACTS & COMPREHENSIVE FACTS ---")
    comp_facts = protocol_analysis_agent.assemble_comprehensive_facts(study_id)
    print(f"Comprehensive Facts Study Title: {comp_facts.study_title.value if comp_facts.study_title else None} (status={comp_facts.study_title.status if comp_facts.study_title else None})")
    print(f"Population/Invitation: {comp_facts.population.value if comp_facts.population else None} (status={comp_facts.population.status if comp_facts.population else None})")
    print(f"Objectives count: primary={len(comp_facts.objectives.primary) if comp_facts.objectives else 0}")
    print(f"Eligibility inclusion count: {len(comp_facts.eligibility.inclusion) if comp_facts.eligibility else 0}")
    print(f"Eligibility exclusion count: {len(comp_facts.eligibility.exclusion) if comp_facts.eligibility else 0}")
    print(f"Procedures count: {len(comp_facts.procedures)}")
    print(f"Duration: {comp_facts.duration.value if comp_facts.duration else None} (status={comp_facts.duration.status if comp_facts.duration else None})")
    print(f"Interventions count: {len(comp_facts.interventions)}")
    for idx, inv in enumerate(comp_facts.interventions):
        print(f"  Intervention [{idx}]: {inv.value} (status={inv.status})")

    # Stage 7: ICF Draft Generation & Section Omission
    print("\n--- STAGE 7: ICF GENERATION DRAFT & SECTION FILTERING ---")
    raw_draft = icf_generation_service._deterministic_icf_generator(comp_facts)
    print(f"Raw Generated Sections Count (before filtering): {len(raw_draft.sections)}")
    for s in raw_draft.sections:
        print(f"  Section ID: '{s.section_id:18s}' | Status: {s.status:12s} | Title: '{s.title}' | Content snippet: {s.content[:60]}...")

    supported_sections = [
        sec for sec in raw_draft.sections
        if sec.status != "NOT_FOUND"
        and sec.content
        and not sec.content.strip().startswith("Not provided in the study protocol.")
    ]
    print(f"\nFinal Supported Sections Count (after backend NOT_FOUND filtering): {len(supported_sections)}")
    for s in supported_sections:
        print(f"  KEPT SECTION -> Section ID: '{s.section_id}' | Title: '{s.title}'")

if __name__ == "__main__":
    main()
