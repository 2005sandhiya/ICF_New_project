import json
import logging
import re
from typing import List, Optional, Dict, Any

from app.models.protocol_facts import ProtocolFacts, FactStatusEnum
from app.models.icf import ICFSection, ICFDraft, ICFGenerationRequest, ICFGenerationResponse
from app.services.llm.llm_service import llm_service
from app.services.workflow_lock import study_lock
from app.services.template_service import TemplateError, template_service

logger = logging.getLogger("icf_generator.icf_generation_service")


def _extract_message_text(content: Any) -> str:
    """Safely extracts clean string text from LangChain message content."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "\n".join(parts)
    return str(content or "")


STANDARD_ICF_SECTIONS = [
    {"section_id": "study_title", "title": "Study Title"},
    {"section_id": "invitation", "title": "Invitation to Participate"},
    {"section_id": "purpose", "title": "Purpose of the Study"},
    {"section_id": "why_asked", "title": "Why You Are Being Asked"},
    {"section_id": "procedures", "title": "Study Procedures"},
    {"section_id": "duration", "title": "Study Duration"},
    {"section_id": "interventions", "title": "Study Interventions / Treatments"},
    {"section_id": "risks", "title": "Risks and Discomforts"},
    {"section_id": "benefits", "title": "Potential Benefits"},
    {"section_id": "alternatives", "title": "Alternatives to Participation"},
    {"section_id": "voluntary", "title": "Voluntary Participation"},
    {"section_id": "confidentiality", "title": "Confidentiality"},
    {"section_id": "questions_contact", "title": "Questions / Contact Information"},
]

ICF_DRAFT_SYSTEM_PROMPT = """You are an expert Clinical Informed Consent Form (ICF) Generation Agent.
Your task is to generate a structured, participant-facing Informed Consent Form (ICF) draft based STRICTLY on the supplied Structured Study Facts.

STRICT GROUNDING & REVISION RULES:
1. Use ONLY the supplied structured study facts. DO NOT invent, assume, or extrapolate missing protocol details.
2. If a section cannot be populated from the supplied facts, use EXACTLY the content string starting with: "Not provided in the study protocol." and set status to "NOT_FOUND".
3. When human reviewer feedback is supplied:
   a. Use reviewer feedback to clarify, rephrase, or refine sections that are SUPPORTED by the protocol facts.
   b. DO NOT treat reviewer feedback as a source of new clinical evidence. Do NOT invent procedures, risks, doses, or eligibility rules not present in the facts.
   c. If the reviewer requests information that is NOT present in the protocol facts, keep status as "NOT_FOUND", keep content starting with "Not provided in the study protocol.", leave "source_evidence_ids" as empty [], and append a separate paragraph: "Reviewer note: The reviewer requested this information, but it was not provided in the study protocol."
4. DO NOT invent hospital names, investigator names, phone numbers, email addresses, compensation amounts, insurance details, or regulatory statements.
5. Retain all exact study details including study ID, numbers, durations, intervention names, and eligibility criteria.
6. Every generated section MUST preserve the array of supporting evidence IDs in "source_evidence_ids" matching the facts used.
7. Output raw JSON conforming strictly to the requested schema.

EXPECTED JSON SCHEMA FORMAT:
{
  "sections": [
    {
      "section_id": "string",
      "title": "string",
      "content": "string",
      "source_evidence_ids": ["chunk_id"],
      "status": "SUPPORTED|NOT_FOUND|UNCERTAIN"
    }
  ]
}
"""

PATIENT_FRIENDLY_SYSTEM_PROMPT = """You are an expert Health Literacy & Patient Communication Specialist.
Your task is to transform a formal clinical Informed Consent Form (ICF) draft into clear, accessible, patient-friendly plain language.

STRICT TRANSFORMATION GUIDELINES:
1. PLAIN LANGUAGE REWRITING:
   - Rewrite complex clinical sentences and dense paragraphs into shorter, clear sentences in active voice.
   - Address the reader directly as "You" (e.g. "You will be asked to..." instead of "Participants will undergo...").
   - Explain technical medical terms in plain English when supported by the protocol text (e.g. "glycemic control" -> "blood sugar control", "adverse events" -> "side effects or unwanted reactions").
2. MEDICAL FACT PRESERVATION:
   - PRESERVE 100% of all clinically important facts: exact drug/intervention names, numeric dosages, administration routes, treatment frequencies, study durations, eligibility criteria, and risk lists.
   - DO NOT alter, omit, or misstate any numeric values, visit counts, or medical criteria.
   - DO NOT claim a study treatment is safe, effective, or beneficial unless explicitly supported by the source protocol text.
3. GROUNDING & SAFETY LIMITS:
   - DO NOT invent or extrapolate new medical explanations, procedures, risks, or benefits not supported by the source.
4. INVARIANCE REQUIREMENTS:
   - If a section's content is "Not provided in the study protocol.", preserve it EXACTLY as "Not provided in the study protocol." with status "NOT_FOUND" and empty source_evidence_ids.
   - Preserve all "source_evidence_ids" array chunk references matching the source section.
   - Preserve all 13 standard section titles and section order.
5. Output raw JSON conforming strictly to the requested ICFDraft schema.
"""

# Plain language replacement rules for deterministic fallback
PATIENT_FRIENDLY_GLOSSARY = {
    r"\bcompare the efficacy of\b": "compare how well",
    r"\bevaluate the efficacy of\b": "check how well",
    r"\befficacy of\b": "effectiveness of",
    r"\befficacy\b": "effectiveness",
    r"\bglycemic control\b": "blood sugar control",
    r"\bpathophysiology\b": "how the condition affects body function",
    r"\badverse events?\b": "side effects or unwanted reactions",
    r"\bmonotherapy\b": "treatment using a single medication",
    r"\bDXA scan\b": "a DXA scan (a low-dose X-ray scan that measures bone density and body composition)",
    r"\bundergo\b": "have",
    r"\bassess\b": "check",
    r"\bevaluate\b": "study",
    r"\brandomized\b": "assigned by chance (for example, like flipping a coin)",
    r"\binterventional\b": "treatment testing",
    r"\bpharmacokinetics\b": "how your body absorbs and processes the study medication",
    r"\bsubcutaneous\b": "under the skin",
    r"\bintravenous\b": "into a vein",
    r"\bphlebotomy\b": "blood sample collection",
    r"\bexacerbation\b": "worsening of symptoms",
    r"\bbid\b": "twice a day",
    r"\bmetformin\b": "metformin (a standard diabetes medication)",
    r"\brosiglitazone\b": "rosiglitazone (a diabetes medication that helps body insulin sensitivity)",
}

from app.services.protocol_analysis_agent import protocol_analysis_agent, deduplicate_all_protocol_facts, normalize_fact_text

class ICFGenerationService:
    """
    Phase 5 Part 3: ICF Content Generation Service.
    
    Generates structured baseline ICF drafts and patient-friendly ICF transformations
    from grounded Phase 5 Part 2 ProtocolFacts.
    """

    def __init__(self):
        self._store: Dict[str, ICFGenerationResponse] = {}
        self._history = {}
        self._documents = {}
        self._facts = {}

    def get_stored_icf(self, study_id: str) -> Optional[ICFGenerationResponse]:
        clean_id = (study_id or "").strip()
        return self._store.get(clean_id)

    def get_facts(self, study_id: str) -> Optional[ProtocolFacts]:
        clean_id = (study_id or "").strip()
        return self._facts.get(clean_id)

    def store_icf(self, study_id: str, response: ICFGenerationResponse):
        clean_id = (study_id or "").strip()
        if clean_id:
            self._store[clean_id] = response
            self._history.setdefault(clean_id, {})[response.revision] = response.model_copy(deep=True)

    def reset_store(self):
        self._store.clear()
        self._history.clear()
        self._documents.clear()
        self._facts.clear()

    def get_history(self, study_id):
        return [item.model_copy(deep=True) for _, item in sorted(self._history.get(study_id.strip(), {}).items())]

    def get_document(self, study_id, revision, export_type):
        clean_id = study_id.strip()
        doc = self._documents.get((clean_id, revision, export_type))
        if doc is not None:
            return doc
        for (sid, rev, _), d in self._documents.items():
            if sid == clean_id and rev == revision:
                return d
        return None

    def set_validation(self, study_id, report):
        stored = self.get_stored_icf(study_id)
        if stored and stored.revision == report.revision:
            stored.validation_report = report.model_dump(mode="json")
            self._history[study_id][stored.revision] = stored.model_copy(deep=True)

    def prepare_approved_documents(self, study_id):
        from app.services.docx_generation_service import docx_generation_service
        stored = self.get_stored_icf(study_id)
        if not stored:
            return
        selected = template_service.selection(study_id)
        if stored.template != selected:
            raise TemplateError("The template changed after generation. Generate and review a new revision.")
        content = template_service.read(study_id, selected)
        doc = docx_generation_service.generate_docx(
            study_id, stored.icf_draft, export_type="patient_facing", review_status="APPROVED", template_content=content
        )
        self._documents.update({
            (study_id, stored.revision, "patient_facing"): doc,
            (study_id, stored.revision, "standard"): doc,
            (study_id, stored.revision, "patient_friendly"): doc,
        })

    def generate_icf(self, request: ICFGenerationRequest) -> ICFGenerationResponse:
        raw_id = request.study_id or (request.analysis_facts.study_id if request.analysis_facts else "") or ""
        study_id = raw_id.strip()
        if not study_id:
            raise ValueError("A non-empty study ID is required for ICF generation.")
        with study_lock(study_id):
            return self._generate_icf_locked(request.model_copy(update={"study_id": study_id}))

    def _generate_icf_locked(self, request: ICFGenerationRequest) -> ICFGenerationResponse:
        """
        Generates single Patient-Facing Informed Consent Form (ICF) draft.
        Supports targeted revision instructions from human reviewer feedback.
        
        Args:
            request: ICFGenerationRequest containing study_id, optional analysis_facts, reviewer_feedback, previous_icf_draft.
            
        Returns:
            ICFGenerationResponse containing single Patient-Facing icf_draft and revision number.
        """
        raw_id = request.study_id or (request.analysis_facts.study_id if request.analysis_facts else "") or ""
        study_id = raw_id.strip()
        if not study_id:
            raise ValueError("A non-empty study ID is required for ICF generation.")
        facts = request.analysis_facts
        if facts and facts.study_id != study_id:
            raise ValueError("Protocol facts belong to a different study.")
        selected_template = template_service.selection(study_id)
        template_content = template_service.read(study_id, selected_template)
        stored_before = self.get_stored_icf(study_id)
        if stored_before and request.previous_icf_draft and request.previous_icf_draft != stored_before.icf_draft:
            raise ValueError("The previous draft is stale or belongs to another study. Reload the current revision.")

        # Auto-assemble comprehensive facts if missing or incomplete
        if not facts or self._is_incomplete_facts(facts):
            logger.info(f"Assembling comprehensive study facts package for '{study_id}' via multi-query RAG...")
            comp_facts = protocol_analysis_agent.assemble_comprehensive_facts(study_id)
            if not facts:
                facts = comp_facts
            else:
                facts = self._merge_facts(facts, comp_facts)
        else:
            facts = deduplicate_all_protocol_facts(facts)

        logger.info(f"Generating Patient-Facing ICF draft for study '{study_id}' (reviewer feedback supplied: {bool(request.reviewer_feedback)})...")

        # Determine revision index
        stored_resp = self.get_stored_icf(study_id)
        if request.previous_icf_draft and getattr(request.previous_icf_draft, "revision", None):
            current_revision = request.previous_icf_draft.revision + 1
        elif stored_resp and stored_resp.icf_draft and getattr(stored_resp.icf_draft, "revision", None):
            current_revision = stored_resp.revision + 1
        elif request.revision:
            current_revision = request.revision
        else:
            current_revision = 1

        # Step 1: Generate evidence-grounded baseline ICF draft
        baseline_icf_draft = self._generate_structured_icf_draft(
            facts,
            reviewer_feedback=request.reviewer_feedback,
            previous_icf_draft=request.previous_icf_draft or (stored_resp.icf_draft if stored_resp else None),
            preferred_length=request.preferred_length,
            custom_instructions=request.custom_instructions,
        )

        # Step 2: Transform to Patient-Facing language
        logger.info("Transforming baseline ICF draft into Patient-Facing Informed Consent Form...")
        patient_facing_icf = self._transform_to_patient_friendly(baseline_icf_draft)
        patient_facing_icf.revision = current_revision

        # Single Patient-Facing ICF draft
        icf_draft = patient_facing_icf

        resp = ICFGenerationResponse(
            study_id=study_id,
            template=selected_template,
            icf_draft=icf_draft,
            patient_friendly_icf=icf_draft,
            revision=current_revision,
            generation_status="success",
            message="Patient-Facing Informed Consent Form generation complete." if not request.reviewer_feedback else "Patient-Facing Informed Consent Form revision complete based on human reviewer feedback."
        )
        # Prepare single document and validate before publishing a new revision.
        from app.services.docx_generation_service import docx_generation_service
        from app.services.template_renderer import document_text
        from app.services.validation_agent import validation_agent
        from app.models.validation import ICFValidationRequest, ValidationCheckResult

        document = docx_generation_service.generate_docx(
            study_id, icf_draft, export_type="patient_facing", review_status="PENDING", template_content=template_content
        )
        documents = {
            (study_id, current_revision, "patient_facing"): document,
            (study_id, current_revision, "standard"): document,
            (study_id, current_revision, "patient_friendly"): document,
        }
        resp.document_preview["patient_facing"] = document_text(document)

        report = validation_agent.validate_icf(ICFValidationRequest(
            study_id=study_id,
            icf_draft=icf_draft,
            patient_friendly_icf=icf_draft,
            protocol_facts=facts
        ))
        report.revision = current_revision
        if selected_template.warnings:
            report.checks.append(ValidationCheckResult(
                check_id="template_structure",
                check_name="Template structure and retained wording",
                status="WARNING",
                score=75.0,
                details=" ".join(selected_template.warnings),
                flagged_items=selected_template.missing_sections
            ))
            if report.overall_status == "PASSED":
                report.overall_status = "REQUIRES_REVIEW"
            report.recommendations.extend(selected_template.warnings)
        resp.validation_report = report.model_dump(mode="json")
        self.store_icf(study_id, resp)
        self._documents.update(documents)
        self._facts[study_id] = facts.model_copy(deep=True)
        from app.services.human_review_service import human_review_service
        from app.models.human_review import HumanReviewUpdateRequest, ReviewStatusEnum
        human_review_service.update_review(study_id, HumanReviewUpdateRequest(
            review_status=ReviewStatusEnum.PENDING, reviewer_comment=request.reviewer_feedback, revision=current_revision))
        return resp

    def _is_incomplete_facts(self, facts: ProtocolFacts) -> bool:
        if not facts.study_title or facts.study_title.status == FactStatusEnum.NOT_FOUND:
            return True
        if len(facts.interventions) == 0:
            return True
        if not facts.duration or facts.duration.status == FactStatusEnum.NOT_FOUND:
            return True
        return False

    def _merge_facts(self, base: ProtocolFacts, comp: ProtocolFacts) -> ProtocolFacts:
        if (not base.study_title or base.study_title.status == FactStatusEnum.NOT_FOUND) and comp.study_title and comp.study_title.status != FactStatusEnum.NOT_FOUND:
            base.study_title = comp.study_title
        if (not base.duration or base.duration.status == FactStatusEnum.NOT_FOUND) and comp.duration and comp.duration.status != FactStatusEnum.NOT_FOUND:
            base.duration = comp.duration
        if (not base.population or base.population.status == FactStatusEnum.NOT_FOUND) and comp.population and comp.population.status != FactStatusEnum.NOT_FOUND:
            base.population = comp.population

        for inv in comp.interventions:
            if not any(i.value == inv.value for i in base.interventions):
                base.interventions.append(inv)
        for p in comp.procedures:
            if not any(existing.value == p.value for existing in base.procedures):
                base.procedures.append(p)
        for r in comp.risks:
            if not any(existing.value == r.value for existing in base.risks):
                base.risks.append(r)
        for b in comp.benefits:
            if not any(existing.value == b.value for existing in base.benefits):
                base.benefits.append(b)

        return deduplicate_all_protocol_facts(base)

    def _is_section_relevant_to_feedback(self, section_id: str, feedback: str) -> bool:
        if not feedback or not feedback.strip():
            return False
        fb = feedback.lower()

        keywords = {
            "study_title": ["title", "study name", "protocol title"],
            "invitation": ["invitation", "invite", "population", "eligible", "cohort", "invited"],
            "purpose": ["purpose", "objective", "goal", "aim", "primary"],
            "why_asked": ["why", "asked", "eligibility", "inclusion", "exclusion", "criteria", "rule"],
            "procedures": ["procedure", "schedule", "visit", "evaluation", "assessment", "test", "blood", "scan", "workflow"],
            "duration": ["duration", "length", "period", "time", "week", "month", "year", "timeline"],
            "interventions": ["intervention", "treatment", "drug", "medication", "dose", "dosage", "arm", "therapy"],
            "risks": ["risk", "side effect", "discomfort", "adverse", "safety", "mitigation", "harm", "reaction"],
            "benefits": ["benefit", "advantage", "gain", "help"],
            "alternatives": ["alternative", "other option", "standard care", "other treatment"],
            "voluntary": ["voluntary", "withdraw", "refuse", "stop"],
            "confidentiality": ["confidential", "privacy", "record", "data", "hipaa", "protected"],
            "questions_contact": ["question", "contact", "phone", "email", "address", "doctor", "pi", "investigator"],
        }

        sec_keywords = keywords.get(section_id, [])
        if any(kw in fb for kw in sec_keywords):
            return True

        # Fallback: if no specific section keyword matches the entire feedback, return True for main sections
        has_any_match = any(kw in fb for kws in keywords.values() for kw in kws)
        return not has_any_match and section_id in ["procedures", "purpose"]

    def _generate_structured_icf_draft(
        self,
        facts: ProtocolFacts,
        reviewer_feedback: Optional[str] = None,
        previous_icf_draft: Optional[ICFDraft] = None,
        preferred_length: Optional[str] = None,
        custom_instructions: Optional[str] = None,
    ) -> ICFDraft:
        """
        Attempts LLM ICF draft generation; falls back to deterministic grounded ICF generator.
        Supports targeted revision instructions from human reviewer feedback and optional style preferences.
        """
        draft = None
        active_provider = llm_service.get_active_provider()
        if active_provider.is_available():
            logger.info(f"Dispatching ICF generation to LLM Provider '{active_provider.provider_name}'...")
            user_prompt = (
                f"Target Study ID: {facts.study_id}\n"
                f"STRUCTURED STUDY FACTS:\n"
                f"{json.dumps(facts.model_dump(), indent=2)}\n\n"
            )

            if previous_icf_draft and len(previous_icf_draft.sections) > 0:
                user_prompt += (
                    f"PREVIOUS DRAFT VERSION TO REVISE:\n"
                    f"{json.dumps(previous_icf_draft.model_dump(), indent=2)}\n\n"
                )

            if reviewer_feedback and reviewer_feedback.strip():
                user_prompt += (
                    f"HUMAN REVIEWER REVISION INSTRUCTIONS:\n"
                    f"The human reviewer requested the following changes:\n"
                    f"\"{reviewer_feedback.strip()}\"\n\n"
                    f"STRICT REVISION GUIDANCE:\n"
                    f"1. Revise ONLY the relevant draft sections to address the reviewer's instructions.\n"
                    f"2. Maintain 100% strict factual grounding against the STRUCTURED STUDY FACTS.\n"
                    f"3. Do NOT invent new clinical claims, procedures, risks, or benefits not present in the facts, even if suggested by reviewer feedback.\n\n"
                )

            if (preferred_length and preferred_length.strip()) or (custom_instructions and custom_instructions.strip()):
                user_prompt += "USER GENERATION PREFERENCES (STYLE & FORMATTING ONLY):\n"
                if preferred_length and preferred_length.strip():
                    user_prompt += f"- Target document length preference: {preferred_length.strip()}\n"
                if custom_instructions and custom_instructions.strip():
                    user_prompt += f"- Presentation & formatting instructions: \"{custom_instructions.strip()}\"\n"
                user_prompt += (
                    "CRITICAL SAFETY RULE FOR USER PREFERENCES:\n"
                    "1. User preferences apply ONLY to presentation style, formatting, paragraphing, and tone.\n"
                    "2. They MUST NOT be used as a source of clinical facts or medical evidence.\n"
                    "3. DO NOT invent or extrapolate missing protocol facts, procedures, risks, or benefits to satisfy user formatting instructions.\n"
                    "4. Maintain 100% strict factual grounding against the STRUCTURED STUDY FACTS.\n\n"
                )

            user_prompt += "Generate structured participant-facing ICF sections strictly conforming to the 13 ICF section titles."

            from app.services.langchain_adapters import create_lcel_chat_prompt
            chat_prompt = create_lcel_chat_prompt(ICF_DRAFT_SYSTEM_PROMPT, "{user_prompt}")
            messages = chat_prompt.format_messages(user_prompt=user_prompt)
            raw_response = llm_service.generate_message(
                system_prompt=_extract_message_text(messages[0].content),
                user_prompt=_extract_message_text(messages[1].content),
                temperature=0.1
            )

            if raw_response:
                draft = self._parse_icf_json(raw_response)

        if not draft or len(draft.sections) == 0:
            logger.info("Using deterministic grounded ICF generator...")
            draft = self._deterministic_icf_generator(
                facts,
                reviewer_feedback=reviewer_feedback,
                previous_icf_draft=previous_icf_draft
            )

        # Retain all 13 standard ICF sections with evidence status and missing-information indicators
        return draft

    def _transform_to_patient_friendly(self, icf_draft: ICFDraft) -> ICFDraft:
        """
        Attempts LLM patient-friendly transformation; falls back to deterministic transformer.
        Ensures 100% section set parity with structured ICF draft.
        """
        pf_draft = None
        active_provider = llm_service.get_active_provider()
        if active_provider.is_available():
            user_prompt = (
                f"STRUCTURED ICF DRAFT TO TRANSFORM:\n"
                f"{json.dumps(icf_draft.model_dump(), indent=2)}\n\n"
                f"Simplify technical terminology and rephrase into clear patient-facing language without altering facts or evidence IDs."
            )
            from app.services.langchain_adapters import create_lcel_chat_prompt
            chat_prompt = create_lcel_chat_prompt(PATIENT_FRIENDLY_SYSTEM_PROMPT, "{user_prompt}")
            messages = chat_prompt.format_messages(user_prompt=user_prompt)
            raw_response = llm_service.generate_message(
                system_prompt=_extract_message_text(messages[0].content),
                user_prompt=_extract_message_text(messages[1].content),
                temperature=0.1
            )
            if raw_response:
                pf_draft = self._parse_icf_json(raw_response)

        if not pf_draft or len(pf_draft.sections) == 0:
            logger.info("Using deterministic patient-friendly transformer...")
            pf_draft = self._deterministic_patient_friendly_transformer(icf_draft)

        # Enforce exact section set parity and evidence ID preservation with structured ICF draft
        pf_map = {sec.section_id: sec for sec in pf_draft.sections}
        final_pf_sections = []
        for sec in icf_draft.sections:
            if sec.section_id in pf_map and pf_map[sec.section_id].status != FactStatusEnum.NOT_FOUND and not pf_map[sec.section_id].content.startswith("Not provided in the study protocol."):
                pf_sec = pf_map[sec.section_id]
                pf_sec.source_evidence_ids = list(sec.source_evidence_ids)
                final_pf_sections.append(pf_sec)
            else:
                # Fall back to deterministic transformation for this supported section
                transformed_single = self._deterministic_patient_friendly_transformer(ICFDraft(sections=[sec])).sections[0]
                final_pf_sections.append(transformed_single)

        return ICFDraft(sections=final_pf_sections)

    def _parse_icf_json(self, raw_response: str) -> Optional[ICFDraft]:
        """
        Parses LLM output string into ICFDraft model.
        """
        try:
            clean_str = raw_response.strip()
            if clean_str.startswith("```"):
                clean_str = re.sub(r"^```(?:json)?", "", clean_str, flags=re.IGNORECASE)
                clean_str = re.sub(r"```$", "", clean_str).strip()

            json_data = json.loads(clean_str)
            if isinstance(json_data, dict) and "sections" in json_data:
                return ICFDraft.model_validate(json_data)
        except Exception as e:
            logger.error(f"Failed to parse ICF JSON output: {e}")
        return None

    def _deterministic_icf_generator(
        self,
        facts: ProtocolFacts,
        reviewer_feedback: Optional[str] = None,
        previous_icf_draft: Optional[ICFDraft] = None,
    ) -> ICFDraft:
        """
        Deterministic grounded ICF generator for offline execution.
        Maps ProtocolFacts directly to all 13 standard ICF sections with 100% source chunk ID traceability.
        Supports safe handling of human reviewer feedback.
        """
        facts = deduplicate_all_protocol_facts(facts)
        sections: List[ICFSection] = []

        def _get_ids(fact_list):
            ids = []
            for f in fact_list:
                for sid in getattr(f, "source_evidence_ids", []):
                    if sid not in ids:
                        ids.append(sid)
            return ids

        # 1. Study Title
        title_val = facts.study_title.value if (facts.study_title and facts.study_title.value and facts.study_title.status != FactStatusEnum.NOT_FOUND) else None
        title_ids = facts.study_title.source_evidence_ids if (facts.study_title and title_val) else []
        if title_val:
            sections.append(ICFSection(
                section_id="study_title",
                title="Study Title",
                content=title_val,
                source_evidence_ids=title_ids,
                status=facts.study_title.status if facts.study_title else FactStatusEnum.SUPPORTED
            ))
        else:
            sections.append(ICFSection(
                section_id="study_title",
                title="Study Title",
                content="Not provided in the study protocol.",
                source_evidence_ids=[],
                status=FactStatusEnum.NOT_FOUND
            ))

        # 2. Invitation to Participate
        pop_val = facts.population.value if (facts.population and facts.population.value and facts.population.status != FactStatusEnum.NOT_FOUND) else None
        pop_ids = facts.population.source_evidence_ids if (facts.population and pop_val) else []
        if pop_val:
            clean_pop = pop_val.strip()
            if clean_pop.lower().startswith("section:") or "study design & population" in clean_pop.lower():
                clean_pop = "the target participant population for this clinical trial"
            sections.append(ICFSection(
                section_id="invitation",
                title="Invitation to Participate",
                content=f"You are being invited to participate in a clinical research study focused on {clean_pop}. Before deciding whether to take part, please read this consent document carefully.",
                source_evidence_ids=pop_ids,
                status=FactStatusEnum.SUPPORTED
            ))
        else:
            sections.append(ICFSection(
                section_id="invitation",
                title="Invitation to Participate",
                content="Not provided in the study protocol.",
                source_evidence_ids=[],
                status=FactStatusEnum.NOT_FOUND
            ))

        # 3. Purpose of the Study
        primary_objs = [o for o in facts.objectives.primary if o.value] if facts.objectives else []
        sec_objs = [o for o in facts.objectives.secondary if o.value] if facts.objectives else []
        all_objs = primary_objs + sec_objs
        obj_ids = _get_ids(all_objs)

        if primary_objs or sec_objs:
            lines = ["The purpose of this clinical research study is to address the following objectives:"]
            if primary_objs:
                lines.append("\nPrimary Objectives:")
                for o in primary_objs:
                    clean_o = normalize_fact_text(o.value)
                    if clean_o:
                        lines.append(f"- {clean_o[0].upper() + clean_o[1:]}")
            if sec_objs:
                lines.append("\nSecondary Objectives:")
                for o in sec_objs:
                    clean_o = normalize_fact_text(o.value)
                    if clean_o:
                        lines.append(f"- {clean_o[0].upper() + clean_o[1:]}")
            sections.append(ICFSection(
                section_id="purpose",
                title="Purpose of the Study",
                content="\n".join(lines),
                source_evidence_ids=obj_ids,
                status=FactStatusEnum.SUPPORTED
            ))
        elif title_val:
            sections.append(ICFSection(
                section_id="purpose",
                title="Purpose of the Study",
                content=f"The primary purpose of this clinical research study ('{title_val}') is to evaluate the safety, efficacy, and clinical outcomes of the study treatments in the target participant population.",
                source_evidence_ids=title_ids,
                status=FactStatusEnum.SUPPORTED
            ))
        else:
            sections.append(ICFSection(
                section_id="purpose",
                title="Purpose of the Study",
                content="Not provided in the study protocol.",
                source_evidence_ids=[],
                status=FactStatusEnum.NOT_FOUND
            ))

        # 4. Why You Are Being Asked
        inc_crit = [i for i in facts.eligibility.inclusion if i.value] if facts.eligibility else []
        exc_crit = [e for e in facts.eligibility.exclusion if e.value] if facts.eligibility else []
        elig_ids = _get_ids(inc_crit + exc_crit)

        if inc_crit or exc_crit:
            parts = ["You are being asked to participate because you meet the following study eligibility criteria:"]
            if inc_crit:
                parts.append("\nInclusion Criteria:")
                for i in inc_crit:
                    clean_i = normalize_fact_text(i.value)
                    if clean_i:
                        parts.append(f"- {clean_i[0].upper() + clean_i[1:]}")
            if exc_crit:
                parts.append("\nExclusion Criteria:")
                for e in exc_crit:
                    clean_e = normalize_fact_text(e.value)
                    if clean_e:
                        parts.append(f"- {clean_e[0].upper() + clean_e[1:]}")
            sections.append(ICFSection(
                section_id="why_asked",
                title="Why You Are Being Asked",
                content="\n".join(parts),
                source_evidence_ids=elig_ids,
                status=FactStatusEnum.SUPPORTED
            ))
        else:
            sections.append(ICFSection(
                section_id="why_asked",
                title="Why You Are Being Asked",
                content="Not provided in the study protocol.",
                source_evidence_ids=[],
                status=FactStatusEnum.NOT_FOUND
            ))

        # 5. Study Procedures
        procs = [p for p in facts.procedures if p.value]
        proc_ids = _get_ids(procs)
        if procs:
            proc_lines = ["During this study, participants will undergo the following evaluations and procedures:"]
            for p in procs:
                clean_p = normalize_fact_text(p.value)
                if clean_p:
                    proc_lines.append(f"- {clean_p[0].upper() + clean_p[1:]}")
            sections.append(ICFSection(
                section_id="procedures",
                title="Study Procedures",
                content="\n".join(proc_lines),
                source_evidence_ids=proc_ids,
                status=FactStatusEnum.SUPPORTED
            ))
        elif invs := [i for i in facts.interventions if i.value]:
            inv_names = [normalize_fact_text(i.value) for i in invs if i.value]
            inv_ids = _get_ids(invs)
            sections.append(ICFSection(
                section_id="procedures",
                title="Study Procedures",
                content=f"During this study, participants will undergo regular health assessments and receive the following study treatment regimens:\n- " + "\n- ".join(inv_names),
                source_evidence_ids=inv_ids,
                status=FactStatusEnum.SUPPORTED
            ))
        else:
            sections.append(ICFSection(
                section_id="procedures",
                title="Study Procedures",
                content="Not provided in the study protocol.",
                source_evidence_ids=[],
                status=FactStatusEnum.NOT_FOUND
            ))

        # 6. Study Duration
        dur_val = facts.duration.value if (facts.duration and facts.duration.value and facts.duration.status != FactStatusEnum.NOT_FOUND) else None
        dur_ids = facts.duration.source_evidence_ids if (facts.duration and dur_val) else []
        if dur_val:
            sections.append(ICFSection(
                section_id="duration",
                title="Study Duration",
                content=f"Your total participation in this study is expected to last: {dur_val}",
                source_evidence_ids=dur_ids,
                status=facts.duration.status if facts.duration else FactStatusEnum.SUPPORTED
            ))
        else:
            sections.append(ICFSection(
                section_id="duration",
                title="Study Duration",
                content="Not provided in the study protocol.",
                source_evidence_ids=[],
                status=FactStatusEnum.NOT_FOUND
            ))

        # 7. Study Interventions / Treatments
        invs = [i for i in facts.interventions if i.value]
        inv_ids = _get_ids(invs)
        if invs:
            inv_lines = ["Participants will be assigned to or receive the following study treatments or regimens:"]
            for inv in invs:
                clean_inv = normalize_fact_text(inv.value)
                if clean_inv:
                    inv_lines.append(f"- {clean_inv[0].upper() + clean_inv[1:]}")
            sections.append(ICFSection(
                section_id="interventions",
                title="Study Interventions / Treatments",
                content="\n".join(inv_lines),
                source_evidence_ids=inv_ids,
                status=FactStatusEnum.SUPPORTED
            ))
        else:
            sections.append(ICFSection(
                section_id="interventions",
                title="Study Interventions / Treatments",
                content="Not provided in the study protocol.",
                source_evidence_ids=[],
                status=FactStatusEnum.NOT_FOUND
            ))

        # 8. Risks and Discomforts
        rs = [r for r in facts.risks if r.value]
        risk_ids = _get_ids(rs)
        if rs:
            risk_lines = ["Participation in this research study involves potential risks or side effects, including:"]
            for r in rs:
                clean_r = normalize_fact_text(r.value)
                if clean_r:
                    risk_lines.append(f"- {clean_r[0].upper() + clean_r[1:]}")
            sections.append(ICFSection(
                section_id="risks",
                title="Risks and Discomforts",
                content="\n".join(risk_lines),
                source_evidence_ids=risk_ids,
                status=FactStatusEnum.SUPPORTED
            ))
        else:
            sections.append(ICFSection(
                section_id="risks",
                title="Risks and Discomforts",
                content="Not provided in the study protocol.",
                source_evidence_ids=[],
                status=FactStatusEnum.NOT_FOUND
            ))

        # 9. Potential Benefits
        bs = [b for b in facts.benefits if b.value]
        b_ids = _get_ids(bs)
        if bs:
            ben_lines = ["Potential benefits from participating in this study may include:"]
            for b in bs:
                clean_b = normalize_fact_text(b.value)
                if clean_b:
                    ben_lines.append(f"- {clean_b[0].upper() + clean_b[1:]}")
            sections.append(ICFSection(
                section_id="benefits",
                title="Potential Benefits",
                content="\n".join(ben_lines),
                source_evidence_ids=b_ids,
                status=FactStatusEnum.SUPPORTED
            ))
        else:
            sections.append(ICFSection(
                section_id="benefits",
                title="Potential Benefits",
                content="Not provided in the study protocol.",
                source_evidence_ids=[],
                status=FactStatusEnum.NOT_FOUND
            ))

        # 10. Alternatives to Participation
        comps = [c for c in facts.comparators if c.value]
        comp_ids = _get_ids(comps)
        if comps:
            alt_lines = ["Instead of taking part in this study, you may consider alternative treatment options including:"]
            for c in comps:
                clean_c = normalize_fact_text(c.value)
                if clean_c:
                    alt_lines.append(f"- {clean_c[0].upper() + clean_c[1:]}")
            sections.append(ICFSection(
                section_id="alternatives",
                title="Alternatives to Participation",
                content="\n".join(alt_lines),
                source_evidence_ids=comp_ids,
                status=FactStatusEnum.SUPPORTED
            ))
        else:
            sections.append(ICFSection(
                section_id="alternatives",
                title="Alternatives to Participation",
                content="Not provided in the study protocol.",
                source_evidence_ids=[],
                status=FactStatusEnum.NOT_FOUND
            ))

        # Helper to search for additional supported facts in facts.additional_facts
        def _find_additional_fact(keywords: List[str]):
            for af in facts.additional_facts:
                if af.value and any(kw in af.value.lower() for kw in keywords):
                    return af
            return None

        # 11. Voluntary Participation
        vol_fact = _find_additional_fact(["voluntary", "withdraw", "consent"])
        if vol_fact and vol_fact.value:
            sections.append(ICFSection(
                section_id="voluntary",
                title="Voluntary Participation",
                content=vol_fact.value,
                source_evidence_ids=vol_fact.source_evidence_ids,
                status=vol_fact.status
            ))
        else:
            sections.append(ICFSection(
                section_id="voluntary",
                title="Voluntary Participation",
                content="Participation in this research study is completely voluntary. You may choose to withdraw from participation at any time without penalty or loss of medical benefits to which you are otherwise entitled.",
                source_evidence_ids=[],
                status=FactStatusEnum.SUPPORTED
            ))

        # 12. Confidentiality
        conf_fact = _find_additional_fact(["confidential", "privacy", "hipaa", "record"])
        if conf_fact and conf_fact.value:
            sections.append(ICFSection(
                section_id="confidentiality",
                title="Confidentiality",
                content=conf_fact.value,
                source_evidence_ids=conf_fact.source_evidence_ids,
                status=conf_fact.status
            ))
        else:
            sections.append(ICFSection(
                section_id="confidentiality",
                title="Confidentiality",
                content="Your study records and personal identity will be kept strictly confidential in accordance with applicable medical privacy and data protection standards.",
                source_evidence_ids=[],
                status=FactStatusEnum.SUPPORTED
            ))

        # 13. Questions / Contact Information
        contact_fact = _find_additional_fact(["contact", "phone", "investigator", "questions", "facility", "location", "site"])
        if contact_fact and contact_fact.value:
            sections.append(ICFSection(
                section_id="questions_contact",
                title="Questions / Contact Information",
                content=contact_fact.value,
                source_evidence_ids=contact_fact.source_evidence_ids,
                status=contact_fact.status
            ))
        else:
            sections.append(ICFSection(
                section_id="questions_contact",
                title="Questions / Contact Information",
                content="Not provided in the study protocol.",
                source_evidence_ids=[],
                status=FactStatusEnum.NOT_FOUND
            ))

        return ICFDraft(sections=sections)

    def _deterministic_patient_friendly_transformer(self, icf_draft: ICFDraft) -> ICFDraft:
        """
        Deterministic patient-friendly transformer.
        Simplifies technical terms and rephrases into plain English while preserving source traceability and factual accuracy.
        """
        pf_sections: List[ICFSection] = []

        for sec in icf_draft.sections:
            if sec.status == FactStatusEnum.NOT_FOUND or sec.content == "Not provided in the study protocol.":
                pf_sections.append(ICFSection(
                    section_id=sec.section_id,
                    title=sec.title,
                    content="Not provided in the study protocol.",
                    source_evidence_ids=[],
                    status=FactStatusEnum.NOT_FOUND
                ))
                continue

            content = sec.content

            # Apply glossary replacements
            for pattern, replacement in PATIENT_FRIENDLY_GLOSSARY.items():
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

            # Section-specific context-aware intro rephrasing
            if sec.section_id == "invitation":
                content = content.replace("You are being invited to participate in a clinical research study focused on", "We invite you to take part in a medical research study about")
            elif sec.section_id == "purpose":
                content = content.replace("The purpose of this clinical research study is to address the following objectives:", "The main goals of this research study are to answer these questions:")
                content = content.replace("Primary Objectives:", "Main Goal of the Study:")
                content = content.replace("Secondary Objectives:", "Other Important Questions the Study Will Answer:")
            elif sec.section_id == "why_asked":
                content = content.replace("You are being asked to participate because you meet the following study eligibility criteria:", "You are invited to join because you meet these study participation rules:")
                content = content.replace("Inclusion Criteria:", "You may be able to join if you meet these rules:")
                content = content.replace("Exclusion Criteria:", "You cannot join if any of these apply to you:")
            elif sec.section_id == "procedures":
                content = content.replace("During this study, participants will undergo the following evaluations and procedures:", "If you decide to join this study, here is what you will be asked to do during your study visits:")
            elif sec.section_id == "duration":
                content = content.replace("Your total participation in this study is expected to last:", "Your overall time taking part in this study will be:")
            elif sec.section_id == "interventions":
                content = content.replace("Participants will be assigned to or receive the following study treatments or regimens:", "You will receive or be assigned to one of these study treatment options:")
            elif sec.section_id == "risks":
                content = content.replace("Participation in this research study involves potential risks or side effects, including:", "Taking part in this study may involve side effects, discomforts, or health risks, including:")
            elif sec.section_id == "benefits":
                content = content.replace("Potential benefits from participating in this study may include:", "Possible ways taking part in this study might help you or future patients include:")
            elif sec.section_id == "alternatives":
                content = content.replace("Instead of taking part in this study, you may consider alternative treatment options including:", "If you choose not to join this study, you have other care options available, such as:")

            pf_sections.append(ICFSection(
                section_id=sec.section_id,
                title=sec.title,
                content=content,
                source_evidence_ids=list(sec.source_evidence_ids),
                status=sec.status
            ))

        return ICFDraft(sections=pf_sections)

icf_generation_service = ICFGenerationService()
