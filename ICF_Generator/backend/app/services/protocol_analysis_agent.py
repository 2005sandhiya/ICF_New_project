import json
import logging
import re
from typing import List, Optional, Dict, Any

from app.models.rag import RAGContextResponse, RAGEvidenceItem
from app.models.protocol_facts import (
    ProtocolFacts,
    TraceableFact,
    FactStatusEnum,
    CategorizedFactList,
    EligibilityFacts
)
from app.services.llm.llm_service import llm_service

logger = logging.getLogger("icf_generator.protocol_analysis_agent")

SYSTEM_PROMPT = """You are an expert Clinical Protocol Analysis Agent.
Your task is to analyze grounded clinical trial protocol evidence chunks and extract structured study facts required for Informed Consent Form (ICF) generation.

STRICT GROUNDING RULES:
1. Extract facts ONLY if directly supported by the retrieved protocol evidence chunks provided in the user prompt.
2. If a field or fact is NOT present or supported in the retrieved evidence, mark its status as "NOT_FOUND" and set its value to null (or empty array []).
3. DO NOT invent, guess, assume, or extrapolate missing protocol details. DO NOT use general medical knowledge to fill missing protocol facts.
4. Distinguish clearly between:
   - Primary vs Secondary Objectives
   - Inclusion vs Exclusion Eligibility Criteria
   - Primary vs Secondary Outcomes / Endpoints
5. OBJECTIVES CLASSIFICATION RULES:
   - ONLY classify a statement as an objective when the source explicitly describes a study objective, aim, purpose, or goal (e.g. "to evaluate...", "to compare...", "the primary objective is to...").
   - DO NOT classify intervention descriptions, treatment-arm descriptions (e.g. "The three treatment regimens are..."), study design, recruitment details, follow-up duration, population descriptions, or procedural information as objectives.
   - DO NOT place the same objective in both primary and secondary lists. Classify objectives strictly according to explicit source hierarchy.
   - If an objective appears across multiple evidence chunks, deduplicate it by merging all supporting chunk IDs in its "source_evidence_ids" array.
   - Route treatment arm and intervention descriptions to "interventions", "comparators", or "additional_facts".
   - If no genuine objective is supported by the retrieved evidence, return empty arrays [] for primary/secondary objectives rather than inventing or misclassifying study descriptions.
6. Every extracted fact MUST reference the exact supporting chunk IDs in its "source_evidence_ids" array (e.g., ["NCT00081328_eligibility_014"]).
7. Output ONLY valid raw JSON conforming strictly to the requested schema below. Do not wrap in extra commentary or prose.

EXPECTED JSON SCHEMA FORMAT:
{
  "study_id": "string",
  "study_title": {"value": "string or null", "status": "SUPPORTED|NOT_FOUND|UNCERTAIN", "source_evidence_ids": ["chunk_id"]},
  "study_type": {"value": "string or null", "status": "SUPPORTED|NOT_FOUND|UNCERTAIN", "source_evidence_ids": ["chunk_id"]},
  "phase": {"value": "string or null", "status": "SUPPORTED|NOT_FOUND|UNCERTAIN", "source_evidence_ids": ["chunk_id"]},
  "condition": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}],
  "population": {"value": "string or null", "status": "SUPPORTED|NOT_FOUND|UNCERTAIN", "source_evidence_ids": ["chunk_id"]},
  "interventions": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}],
  "comparators": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}],
  "objectives": {
    "primary": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}],
    "secondary": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}]
  },
  "eligibility": {
    "inclusion": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}],
    "exclusion": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}]
  },
  "duration": {"value": "string or null", "status": "SUPPORTED|NOT_FOUND|UNCERTAIN", "source_evidence_ids": ["chunk_id"]},
  "procedures": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}],
  "outcomes": {
    "primary": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}],
    "secondary": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}]
  },
  "risks": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}],
  "benefits": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}],
  "additional_facts": [{"value": "string", "status": "SUPPORTED", "source_evidence_ids": ["chunk_id"]}]
}
"""

NON_OBJECTIVE_PATTERNS = [
    r"^the\s+three\s+treatment\s+regimens\s+are",
    r"^treatment\s+regimens?\s+are",
    r"study\s+recruits\s+patients",
    r"follows\s+patients\s+for",
    r"patients\s+are\s+randomized",
    r"sponsored\s+a\s+consortium",
    r"phase\s+[1-4]\s+clinical\s+trial",
    r"multicenter\s+randomized",
    r"inclusion\s+criteria",
    r"exclusion\s+criteria",
]

OBJECTIVE_VERB_PATTERNS = [
    r"\b(to\s+)?(evaluate|compare|determine|assess|investigate|examine|test|measure|study|identify|find|explore)\b",
    r"\b(primary|secondary)\s+(objective|aim|goal|purpose)\b",
    r"\bthe\s+(objective|aim|purpose|goal)\s+of\b",
    r"\baims?\s+to\b",
]

def _is_intervention_or_design_description(text: str) -> bool:
    low = text.lower().strip()
    for pat in NON_OBJECTIVE_PATTERNS:
        if re.search(pat, low):
            return True
    return False

def _is_genuine_objective(text: str) -> bool:
    low = text.lower().strip()
    if _is_intervention_or_design_description(low):
        return False
    for pat in OBJECTIVE_VERB_PATTERNS:
        if re.search(pat, low):
            return True
    return False

def normalize_fact_text(text: Optional[str]) -> str:
    if not text:
        return ""
    t = text.strip()
    # Remove leading bullets, numbers, dashes
    t = re.sub(r"^[-*•\d\.\)]+\s*", "", t).strip()
    # Remove common wrapping prefixes
    t = re.sub(r"^\((?:during\s+)?screening(?:\s+and\s+run-in\s+period)?\):?\s*", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"^(?:inclusion|exclusion)\s+criteria:?\s*", "", t, flags=re.IGNORECASE).strip()
    # Remove trailing semicolons, periods, or conjunctions
    t = re.sub(r"[;,\.]+$", "", t).strip()
    if t.lower().endswith(" and"):
        t = t[:-4].strip()
    return t

def deduplicate_fact_list(facts: List[TraceableFact[str]]) -> List[TraceableFact[str]]:
    if not facts:
        return []

    deduped_store: Dict[str, Dict[str, Any]] = {}

    for item in facts:
        if not item or not item.value:
            continue

        raw_val = item.value.strip()
        norm_key = normalize_fact_text(raw_val).lower()

        if not norm_key or len(norm_key) < 3:
            continue

        # Check if an existing entry is substantially identical
        found_key = None
        for existing_key in deduped_store.keys():
            if norm_key == existing_key:
                found_key = existing_key
                break
            # Near-identical substring containment for longer items (>20 chars)
            if len(norm_key) > 20 and len(existing_key) > 20:
                if norm_key in existing_key or existing_key in norm_key:
                    len_ratio = min(len(norm_key), len(existing_key)) / max(len(norm_key), len(existing_key))
                    if len_ratio > 0.85:
                        found_key = existing_key
                        break

        if found_key is None:
            deduped_store[norm_key] = {
                "value": raw_val,
                "status": item.status,
                "source_evidence_ids": list(item.source_evidence_ids) if item.source_evidence_ids else []
            }
        else:
            entry = deduped_store[found_key]
            for sid in (item.source_evidence_ids or []):
                if sid not in entry["source_evidence_ids"]:
                    entry["source_evidence_ids"].append(sid)
            
            clean_raw = normalize_fact_text(raw_val)
            clean_entry = normalize_fact_text(entry["value"])
            if len(clean_raw) > len(clean_entry) and len(clean_raw) - len(clean_entry) < 30:
                entry["value"] = raw_val

    result = []
    for entry in deduped_store.values():
        result.append(TraceableFact[str](
            value=entry["value"],
            status=entry["status"],
            source_evidence_ids=entry["source_evidence_ids"]
        ))

    return result

def _deduplicate_and_clean_objectives(facts: ProtocolFacts) -> ProtocolFacts:
    if not facts.objectives:
        return facts

    primary_list = facts.objectives.primary or []
    secondary_list = facts.objectives.secondary or []

    if not primary_list and not secondary_list:
        return facts

    obj_store: Dict[str, Dict[str, Any]] = {}

    def _process_item(item: TraceableFact[str], initial_category: str):
        if not item or not item.value:
            return
        norm = normalize_fact_text(item.value).lower()
        if not norm:
            return
        
        low_val = item.value.lower()
        is_explicit_primary = "primary objective" in low_val or "primary aim" in low_val or "primary goal" in low_val
        is_explicit_secondary = "secondary aim" in low_val or "secondary objective" in low_val or "secondary goal" in low_val

        if norm not in obj_store:
            obj_store[norm] = {
                "value": item.value,
                "status": item.status,
                "source_evidence_ids": list(item.source_evidence_ids) if item.source_evidence_ids else [],
                "explicit_primary": is_explicit_primary,
                "explicit_secondary": is_explicit_secondary,
                "assigned_category": initial_category
            }
        else:
            entry = obj_store[norm]
            for sid in (item.source_evidence_ids or []):
                if sid not in entry["source_evidence_ids"]:
                    entry["source_evidence_ids"].append(sid)
            
            if is_explicit_primary:
                entry["explicit_primary"] = True
            if is_explicit_secondary:
                entry["explicit_secondary"] = True

            if len(item.value) > len(entry["value"]):
                entry["value"] = item.value

            if entry["explicit_secondary"] and not entry["explicit_primary"]:
                entry["assigned_category"] = "secondary"
            elif entry["explicit_primary"] and not entry["explicit_secondary"]:
                entry["assigned_category"] = "primary"
            elif initial_category == "secondary" and not entry["explicit_primary"]:
                entry["assigned_category"] = "secondary"

    for fact in primary_list:
        _process_item(fact, "primary")

    for fact in secondary_list:
        _process_item(fact, "secondary")

    clean_primary = []
    clean_secondary = []

    for norm, entry in obj_store.items():
        fact = TraceableFact[str](
            value=entry["value"],
            status=entry["status"],
            source_evidence_ids=entry["source_evidence_ids"]
        )
        if entry["assigned_category"] == "secondary" and not entry["explicit_primary"]:
            clean_secondary.append(fact)
        elif entry["assigned_category"] == "primary":
            clean_primary.append(fact)
        else:
            clean_secondary.append(fact)

    facts.objectives.primary = deduplicate_fact_list(clean_primary)
    facts.objectives.secondary = deduplicate_fact_list(clean_secondary)
    return facts

def deduplicate_all_protocol_facts(facts: ProtocolFacts) -> ProtocolFacts:
    facts = _deduplicate_and_clean_objectives(facts)
    if facts.eligibility:
        facts.eligibility.inclusion = deduplicate_fact_list(facts.eligibility.inclusion)
        facts.eligibility.exclusion = deduplicate_fact_list(facts.eligibility.exclusion)
    facts.interventions = deduplicate_fact_list(facts.interventions)
    facts.comparators = deduplicate_fact_list(facts.comparators)
    facts.procedures = deduplicate_fact_list(facts.procedures)
    facts.risks = deduplicate_fact_list(facts.risks)
    facts.benefits = deduplicate_fact_list(facts.benefits)
    if facts.outcomes:
        facts.outcomes.primary = deduplicate_fact_list(facts.outcomes.primary)
        facts.outcomes.secondary = deduplicate_fact_list(facts.outcomes.secondary)
    facts.additional_facts = deduplicate_fact_list(facts.additional_facts)
    return facts

class ProtocolAnalysisAgent:
    """
    Phase 5 Part 2: Protocol Analysis Agent.
    
    Converts grounded protocol evidence produced by Phase 5 Part 1 RAG context assembly
    into structured study facts with fact-level source traceability.
    """

    def assemble_comprehensive_facts(self, study_id: str) -> ProtocolFacts:
        """
        Assembles comprehensive structured study facts for a given study by executing multi-query RAG retrieval
        across all core protocol dimensions (objectives, eligibility, interventions, procedures, duration, risks, benefits).
        """
        from app.models.rag import RAGRetrieveRequest
        from app.services.context_assembler import context_assembler

        queries = [
            f"What is the official title, study type, phase, condition, and target population for study {study_id}?",
            f"What are the primary and secondary objectives for study {study_id}?",
            f"What are the inclusion criteria and exclusion criteria for study {study_id}?",
            f"What are the treatment interventions and comparators for study {study_id}?",
            f"What are the study procedures, duration, primary outcomes, risks, and potential benefits for study {study_id}?",
        ]

        all_evidence = []
        seen_chunk_ids = set()

        for q in queries:
            req = RAGRetrieveRequest(
                query=q,
                study_id=study_id,
                top_k=5,
                enable_diversity=True
            )
            ctx = context_assembler.assemble_context(req)
            for ev in ctx.evidence:
                if ev.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(ev.chunk_id)
                    all_evidence.append(ev)

        merged_context = RAGContextResponse(
            original_query=f"Comprehensive Protocol Analysis for {study_id}",
            processed_query="comprehensive_protocol_analysis",
            study_id=study_id,
            evidence=all_evidence,
            evidence_count=len(all_evidence),
            retrieval_status="success" if all_evidence else "empty"
        )

        return self.analyze_context(merged_context)

    def analyze_context(self, context: RAGContextResponse) -> ProtocolFacts:
        """
        Analyzes grounded RAG context package and extracts structured study facts.
        
        Args:
            context: RAGContextResponse from Phase 5 Part 1.
            
        Returns:
            ProtocolFacts Pydantic model with fact-level traceability metadata.
        """
        logger.info(f"Analyzing grounded RAG context for study '{context.study_id}' ({context.evidence_count} evidence items)...")

        # Step 1: Format grounded evidence into prompt payload
        evidence_text_blocks = []
        for item in context.evidence:
            block = (
                f"[CHUNK_ID: {item.chunk_id}]\n"
                f"Section: {item.section} (Subsection: {item.subsection or 'N/A'})\n"
                f"Source Field: {item.source.source_field or 'N/A'}\n"
                f"Text:\n{item.text}\n"
            )
            evidence_text_blocks.append(block)

        formatted_evidence = "\n---\n".join(evidence_text_blocks)
        user_prompt = (
            f"Target Study ID: {context.study_id or 'N/A'}\n"
            f"Requirement Query: {context.original_query}\n\n"
            f"GROUNDED PROTOCOL EVIDENCE CHUNKS:\n"
            f"{formatted_evidence}\n\n"
            f"Extract structured protocol facts conforming strictly to the required JSON schema."
        )

        # Step 2: Dispatch to LLM Service Provider Abstraction via LangChain Prompt Templates
        active_provider = llm_service.get_active_provider()
        if active_provider.is_available():
            logger.info(f"Dispatching protocol analysis to LLM Provider '{active_provider.provider_name}' (model: '{active_provider.model_name}')...")
            from app.services.langchain_adapters import create_lcel_chat_prompt
            chat_prompt = create_lcel_chat_prompt(SYSTEM_PROMPT, "{user_prompt}")
            messages = chat_prompt.format_messages(user_prompt=user_prompt)
            sys_content = messages[0].content if isinstance(messages[0].content, str) else str(messages[0].content)
            user_content = messages[1].content if isinstance(messages[1].content, str) else str(messages[1].content)
            raw_response = llm_service.generate_message(
                system_prompt=sys_content,
                user_prompt=user_content,
                temperature=0.0
            )

            if raw_response:
                parsed_facts = self._parse_json_response(raw_response, context.study_id)
                if parsed_facts:
                    return deduplicate_all_protocol_facts(parsed_facts)

        # Step 3: Deterministic Grounded Fallback Extractor for offline / keyless execution
        logger.info("Using deterministic grounded fallback extractor...")
        raw_facts = self._deterministic_grounded_extractor(context)
        return deduplicate_all_protocol_facts(raw_facts)

    def _parse_json_response(self, raw_response: str, study_id: Optional[str]) -> Optional[ProtocolFacts]:
        """
        Parses raw LLM text output into ProtocolFacts Pydantic schema.
        """
        try:
            clean_str = raw_response.strip()
            # Strip markdown fenced code block wrapper if present
            if clean_str.startswith("```"):
                clean_str = re.sub(r"^```(?:json)?", "", clean_str, flags=re.IGNORECASE)
                clean_str = re.sub(r"```$", "", clean_str).strip()

            json_data = json.loads(clean_str)
            if not isinstance(json_data, dict):
                return None

            json_data["study_id"] = study_id or json_data.get("study_id")
            return ProtocolFacts.model_validate(json_data)
        except Exception as e:
            logger.error(f"Failed to parse Claude JSON response: {e}")
            return None

    def _deterministic_grounded_extractor(self, context: RAGContextResponse) -> ProtocolFacts:
        """
        Deterministic grounded fallback extractor for offline test execution.
        Scans retrieved evidence chunks and populates ProtocolFacts with 100% source chunk ID traceability.
        """
        study_id = context.study_id
        facts = ProtocolFacts(study_id=study_id)

        if not context.evidence or len(context.evidence) == 0:
            return facts

        for item in context.evidence:
            sec = item.section.lower() if item.section else ""
            sub = item.subsection.lower() if item.subsection else ""
            chunk_id = item.chunk_id
            text = item.text.strip()

            # 0. Study Identification / Title / Type / Phase
            if "identification" in sec or "title" in sec or "study_id" in sec or "official title:" in text.lower():
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                for line in lines:
                    if line.lower().startswith("official title:"):
                        val = line[len("Official Title:"):].strip()
                        if val:
                            facts.study_title = TraceableFact[str](
                                value=val,
                                status=FactStatusEnum.SUPPORTED,
                                source_evidence_ids=[chunk_id]
                            )
                    elif line.lower().startswith("title:") and facts.study_title.status == FactStatusEnum.NOT_FOUND:
                        val = line[len("Title:"):].strip()
                        if val:
                            facts.study_title = TraceableFact[str](
                                value=val,
                                status=FactStatusEnum.SUPPORTED,
                                source_evidence_ids=[chunk_id]
                            )
                    elif line.lower().startswith("phase:"):
                        val = line[len("Phase:"):].strip()
                        if val:
                            facts.phase = TraceableFact[str](
                                value=val,
                                status=FactStatusEnum.SUPPORTED,
                                source_evidence_ids=[chunk_id]
                            )
                    elif line.lower().startswith("study type:"):
                        val = line[len("Study Type:"):].strip()
                        if val:
                            facts.study_type = TraceableFact[str](
                                value=val,
                                status=FactStatusEnum.SUPPORTED,
                                source_evidence_ids=[chunk_id]
                            )

            # Check for study duration text
            if "follows patients for" in text.lower() or "recruits patients over" in text.lower():
                dur_match = re.search(r"(follows?\s+patients?\s+for\s+[^.\n]+|minimum of\s+[^.\n]+|recruits\s+patients\s+over\s+[^.\n]+)", text, re.IGNORECASE)
                if dur_match and facts.duration.status == FactStatusEnum.NOT_FOUND:
                    facts.duration = TraceableFact[str](
                        value=dur_match.group(0).strip(),
                        status=FactStatusEnum.SUPPORTED,
                        source_evidence_ids=[chunk_id]
                    )

            # 1. Eligibility Criteria
            if "eligibility" in sec:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                is_exclusion = "exclusion" in sub or "exclusion" in text.lower()
                for line in lines:
                    clean_line = re.sub(r"^[-*•\d\.\)]+\s*", "", line).strip()
                    if len(clean_line) < 15 or "criteria" in clean_line.lower():
                        continue
                    
                    fact = TraceableFact[str](
                        value=clean_line,
                        status=FactStatusEnum.SUPPORTED,
                        source_evidence_ids=[chunk_id]
                    )
                    if is_exclusion:
                        facts.eligibility.exclusion.append(fact)
                    else:
                        facts.eligibility.inclusion.append(fact)

            # 2. Interventions
            elif "intervention" in sec or "arm" in sec or "treatment" in sec:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                for line in lines:
                    clean_line = re.sub(r"^[-*•\d\.\)]+\s*", "", line).strip()
                    if len(clean_line) < 10 or "interventions" in clean_line.lower():
                        continue
                    facts.interventions.append(TraceableFact[str](
                        value=clean_line,
                        status=FactStatusEnum.SUPPORTED,
                        source_evidence_ids=[chunk_id]
                    ))

            # 3. Outcomes & Endpoints
            elif "outcome" in sec or "endpoint" in sec:
                is_secondary = "secondary" in sub or "secondary" in text.lower()
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                for line in lines:
                    clean_line = re.sub(r"^[-*•\d\.\)]+\s*", "", line).strip()
                    if len(clean_line) < 15:
                        continue
                    fact = TraceableFact[str](
                        value=clean_line,
                        status=FactStatusEnum.SUPPORTED,
                        source_evidence_ids=[chunk_id]
                    )
                    if is_secondary:
                        facts.outcomes.secondary.append(fact)
                    else:
                        facts.outcomes.primary.append(fact)

            # 4. Objectives & Purpose
            elif "objective" in sec or "purpose" in sec or "description" in sec:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                current_mode = "secondary" if "secondary" in sub else "primary"

                for line in lines:
                    clean_line = re.sub(r"^[-*•\d\.\)]+\s*", "", line).strip()
                    if len(clean_line) < 15:
                        continue

                    # Check if line ends with or contains trailing "secondary aims are to:"
                    has_trailing_sec_header = False
                    if re.search(r"the secondary aims are( to)?:?$", clean_line, re.IGNORECASE):
                        clean_line = re.sub(r"\s*the secondary aims are( to)?:?\s*$", "", clean_line, flags=re.IGNORECASE).strip()
                        has_trailing_sec_header = True

                    low = clean_line.lower()

                    # Skip standalone headers / labels
                    if low.endswith(":") or low in [
                        "primary study objectives",
                        "primary objectives",
                        "secondary objectives",
                        "secondary aims",
                        "the secondary aims are to",
                    ]:
                        if "secondary" in low:
                            current_mode = "secondary"
                        elif "primary" in low:
                            current_mode = "primary"
                        continue

                    # Check if line describes interventions / treatment regimens / study design rather than a genuine objective
                    if _is_intervention_or_design_description(clean_line):
                        if "regimen" in low or "treatment" in low or "intervention" in low or "arm" in low:
                            if not any(f.value == clean_line for f in facts.interventions):
                                facts.interventions.append(TraceableFact[str](
                                    value=clean_line,
                                    status=FactStatusEnum.SUPPORTED,
                                    source_evidence_ids=[chunk_id]
                                ))
                        else:
                            if not any(f.value == clean_line for f in facts.additional_facts):
                                facts.additional_facts.append(TraceableFact[str](
                                    value=clean_line,
                                    status=FactStatusEnum.SUPPORTED,
                                    source_evidence_ids=[chunk_id]
                                ))
                        if has_trailing_sec_header:
                            current_mode = "secondary"
                        continue

                    if _is_genuine_objective(clean_line):
                        fact = TraceableFact[str](
                            value=clean_line,
                            status=FactStatusEnum.SUPPORTED,
                            source_evidence_ids=[chunk_id]
                        )
                        is_sec = current_mode == "secondary" or ("secondary" in low and "primary" not in low)
                        if "primary objective" in low or "primary aim" in low:
                            is_sec = False

                        if is_sec:
                            if not any(f.value == clean_line for f in facts.objectives.secondary):
                                facts.objectives.secondary.append(fact)
                        else:
                            if not any(f.value == clean_line for f in facts.objectives.primary):
                                facts.objectives.primary.append(fact)

                    if has_trailing_sec_header:
                        current_mode = "secondary"

            # 5. Procedures & Assessments
            elif "procedure" in sec or "assessment" in sec or "evaluation" in sec:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                for line in lines:
                    clean_line = re.sub(r"^[-*•\d\.\)]+\s*", "", line).strip()
                    if len(clean_line) < 10:
                        continue
                    if not any(f.value == clean_line for f in facts.procedures):
                        facts.procedures.append(TraceableFact[str](
                            value=clean_line,
                            status=FactStatusEnum.SUPPORTED,
                            source_evidence_ids=[chunk_id]
                        ))

            # 6. Risks & Adverse Events
            elif "risk" in sec or "adverse" in sec or "safety" in sec or "discomfort" in sec:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                for line in lines:
                    clean_line = re.sub(r"^[-*•\d\.\)]+\s*", "", line).strip()
                    if len(clean_line) < 15:
                        continue
                    if not any(f.value == clean_line for f in facts.risks):
                        facts.risks.append(TraceableFact[str](
                            value=clean_line,
                            status=FactStatusEnum.SUPPORTED,
                            source_evidence_ids=[chunk_id]
                        ))

            # 7. Benefits
            elif "benefit" in sec:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                for line in lines:
                    clean_line = re.sub(r"^[-*•\d\.\)]+\s*", "", line).strip()
                    if len(clean_line) < 15:
                        continue
                    if not any(f.value == clean_line for f in facts.benefits):
                        facts.benefits.append(TraceableFact[str](
                            value=clean_line,
                            status=FactStatusEnum.SUPPORTED,
                            source_evidence_ids=[chunk_id]
                        ))

            # 8. Conditions, Design, Population, Contacts & Locations
            elif "design" in sec or "condition" in sec or "population" in sec or "contact" in sec or "location" in sec:
                if ("population" in sec or "design" in sec or "eligibility" in sec) and facts.population.status == FactStatusEnum.NOT_FOUND:
                    facts.population = TraceableFact[str](
                        value=text,
                        status=FactStatusEnum.SUPPORTED,
                        source_evidence_ids=[chunk_id]
                    )
                if "contact" in sec or "location" in sec:
                    facts.additional_facts.append(TraceableFact[str](
                        value=text,
                        status=FactStatusEnum.SUPPORTED,
                        source_evidence_ids=[chunk_id]
                    ))
                facts.condition.append(TraceableFact[str](
                    value=text,
                    status=FactStatusEnum.SUPPORTED,
                    source_evidence_ids=[chunk_id]
                ))

        return facts

protocol_analysis_agent = ProtocolAnalysisAgent()
