"""Populate known DOCX slots without interpreting template text as study facts."""
from copy import deepcopy
from datetime import datetime, timezone
import io
import re

from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

from app.models.icf import FactStatusEnum
from app.services.template_service import (
    BRACKET_TO_CANONICAL, HEADINGS, METADATA_FIELDS, SECTION_TITLES, SIGNATURE_FIELDS,
    SUPPORTED_TOPICS, TOKEN, W, TemplateError, inspect_docx, normalize_heading, paragraphs,
)


def replace_text(paragraph, text):
    properties = deepcopy(paragraph.runs[0]._r.rPr) if paragraph.runs and paragraph.runs[0]._r.rPr is not None else None
    paragraph.clear()
    run = paragraph.add_run(text)
    if properties is not None:
        run._r.insert(0, properties)


def replace_tokens(paragraph, values):
    for match in reversed(list(TOKEN.finditer(paragraph.text))):
        raw = match.group(1) or match.group(2)
        name = raw.removeprefix("icf.") if raw else ""
        if name in SIGNATURE_FIELDS:
            continue
        canonical = BRACKET_TO_CANONICAL.get(name, name)

        name_upper = name.upper()
        canonical_upper = canonical.upper()

        replacement = None
        if name in values:
            replacement = values[name]
        elif name_upper in values:
            replacement = values[name_upper]
        elif canonical in values:
            replacement = values[canonical]
        elif canonical_upper in values:
            replacement = values[canonical_upper]
        elif canonical in SECTION_TITLES or name in METADATA_FIELDS or canonical_upper in SECTION_TITLES or name_upper in METADATA_FIELDS:
            replacement = ""

        if replacement is None:
            continue

        offset = 0
        affected = []
        for run in paragraph.runs:
            end = offset + len(run.text)
            if end > match.start() and offset < match.end():
                affected.append((run, offset, end))
            offset = end
        if not affected:
            continue
        first, start, _ = affected[0]
        last, last_start, _ = affected[-1]
        prefix = first.text[:match.start() - start]
        suffix = last.text[match.end() - last_start:]
        if first is last:
            first.text = prefix + replacement + suffix
        else:
            first.text = prefix + replacement
            for run, _, _ in affected[1:-1]:
                run.text = ""
            last.text = suffix


def is_heading(paragraph):
    text = paragraph.text.strip()
    if not text:
        return False
    if (text.startswith("[") and text.endswith("]")) or (text.startswith("{{") and text.endswith("}}")):
        return False
    if paragraph.style and paragraph.style.name and paragraph.style.name.lower().startswith("heading"):
        return True
    if re.match(r"^\s*\d+\.\s+", text):
        return True
    norm = normalize_heading(text)
    if norm in HEADINGS:
        return True
    return False


def populate_heading(paragraph, content):
    if not content or not content.strip():
        paragraph.clear()
        return
    candidates = [paragraph]
    for sibling in paragraph._p.itersiblings():
        if sibling.tag != W + "p":
            break
        candidate = Paragraph(sibling, paragraph._parent)
        norm = normalize_heading(candidate.text)
        if candidate.style and candidate.style.name and candidate.style.name.lower().startswith("heading"):
            break
        if norm in HEADINGS or any(h in norm for h in ["part i", "part ii", "certificate of consent", "signatures"]):
            break
        candidates.append(candidate)
    replace_text(candidates[0], content)
    for c in candidates[1:]:
        c.clear()


def clean_phase(phase_raw):
    if not phase_raw:
        return ""
    p = phase_raw.strip()
    if p.lower().startswith("phase "):
        return "Phase " + p[6:].strip()
    return p


def format_bullet_list(items):
    clean_items = []
    for item in items:
        text = getattr(item, "value", item)
        if text and text.strip():
            clean_items.append(f"- {text[0].upper() + text[1:] if len(text) > 1 else text}")
    return "\n".join(clean_items)


def is_who_guidance_text(text):
    if not text or not text.strip():
        return False
    t = text.strip()
    if t.startswith("[") and t.endswith("]"):
        return True
    WHO_GUIDANCE_PATTERNS = [
        r"provide\s+a\s+brief\s+summary",
        r"explain\s+why\s+the\s+participant",
        r"describe\s+all\s+procedures",
        r"specify\s+the\s+total\s+duration",
        r"list\s+all\s+known\s+risks",
        r"describe\s+any\s+direct\s+benefits",
        r"state\s+whether\s+alternative",
        r"explain\s+how\s+confidentiality",
        r"state\s+that\s+participation\s+is\s+voluntary",
        r"include\s+contact\s+information",
    ]
    for pat in WHO_GUIDANCE_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return True
    return False


def _is_absence_text(text):
    if not text or not str(text).strip():
        return True
    t = str(text).strip().lower()
    return (
        t.startswith("not provided")
        or t.startswith("specific details regarding")
        or t.startswith("specific information about")
        or "was not provided in the study protocol" in t
        or "were not provided in the study protocol" in t
    )


def has_grounded_section_content(section_id, draft, facts=None, values=None):
    if values and values.get(section_id):
        if not _is_absence_text(values[section_id]):
            return True

    if draft and hasattr(draft, "sections"):
        for sec in draft.sections:
            if sec.section_id == section_id:
                if sec.status != FactStatusEnum.NOT_FOUND and sec.content:
                    if not _is_absence_text(sec.content):
                        return True

    if facts and hasattr(facts, section_id):
        attr = getattr(facts, section_id)
        if attr:
            if isinstance(attr, list):
                for item in attr:
                    val = getattr(item, "value", item)
                    stat = getattr(item, "status", None)
                    if val and stat != FactStatusEnum.NOT_FOUND and not _is_absence_text(val):
                        return True
            else:
                val = getattr(attr, "value", attr)
                stat = getattr(attr, "status", None)
                if val and stat != FactStatusEnum.NOT_FOUND and not _is_absence_text(val):
                    return True

    return False


def has_grounded_risks(draft, facts=None, values=None):
    return has_grounded_section_content("risks", draft, facts=facts, values=values)


def remove_target_unsupported_sections_and_renumber(document, draft, facts=None, values=None, is_custom=False):
    removable_sections = set()

    # 1. Biological samples if ungrounded
    has_bio = False
    if values and values.get("biological_samples"):
        val = str(values["biological_samples"])
        if val and not ("not provided" in val.lower() or "specific details" in val.lower()):
            has_bio = True
    if not has_bio:
        removable_sections.add("biological_samples")

    # 2. Alternatives if explicitly NOT_FOUND in draft
    if draft and hasattr(draft, "sections"):
        for sec in draft.sections:
            if sec.section_id == "alternatives":
                if sec.status == FactStatusEnum.NOT_FOUND or (sec.content and sec.content.strip().startswith("Not provided in the study protocol.")):
                    removable_sections.add("alternatives")

    # 3. Custom templates and built-in templates share identical evidence-grounded section rules.

    body_elements = list(document.element.body)
    to_remove = []
    current_unsupported_heading = False
    seen_major_sections = set()

    for elem in body_elements:
        tag = elem.tag.rsplit("}", 1)[-1] if "}" in elem.tag else elem.tag
        if tag == "p":
            p = Paragraph(elem, document)
            text = p.text.strip()
            if not text:
                continue

            if is_who_guidance_text(text):
                to_remove.append(elem)
                continue

            m = re.match(r"^\s*(\d+)\.\s+(.*)$", text)
            heading_title = m.group(2).strip() if m else text
            norm = normalize_heading(heading_title)
            matched_sec = HEADINGS.get(norm) or HEADINGS.get(normalize_heading(text))
            if not matched_sec:
                clean_norm = re.sub(r"^[0-9.]+\s*", "", norm)
                if (is_heading(p) or m) and ("biological" in clean_norm or "specimen" in clean_norm or clean_norm.startswith("sample collection") or clean_norm.startswith("sample storage")):
                    matched_sec = "biological_samples"

            # Check for duplicate section heading
            is_duplicate = False
            if m and matched_sec and matched_sec in SECTION_TITLES:
                if matched_sec in seen_major_sections and matched_sec not in ["study_title", "invitation"]:
                    is_duplicate = True
                else:
                    seen_major_sections.add(matched_sec)

            if is_duplicate or (matched_sec and matched_sec in removable_sections):
                current_unsupported_heading = True
                to_remove.append(elem)
            elif matched_sec and matched_sec not in removable_sections:
                current_unsupported_heading = False
            elif current_unsupported_heading and not m:
                to_remove.append(elem)
        elif current_unsupported_heading:
            to_remove.append(elem)

    removed_any_major_heading = False
    for elem in to_remove:
        tag = elem.tag.rsplit("}", 1)[-1] if "}" in elem.tag else elem.tag
        if tag == "p":
            p = Paragraph(elem, document)
            if re.match(r"^\s*\d+\.\s+", p.text.strip()):
                removed_any_major_heading = True
        parent = elem.getparent()
        if parent is not None:
            parent.remove(elem)

    if removed_any_major_heading:
        renumber_major_headings(document)


def renumber_major_headings(document):
    current_number = 1
    for p in paragraphs(document):
        text = p.text.strip()
        if not text:
            continue
        if is_heading(p) or (p.style and p.style.name and p.style.name.lower().startswith("heading")):
            m = re.match(r"^\s*(\d+)\.\s+(.*)$", text)
            if m:
                heading_title = m.group(2).strip()
                norm = normalize_heading(heading_title)
                matched_sec = HEADINGS.get(norm) or HEADINGS.get(normalize_heading(text))
                if not matched_sec:
                    clean_norm = re.sub(r"^[0-9.]+\s*", "", norm)
                    if "pregnancy" in clean_norm or "breastfeeding" in clean_norm or "fertility" in clean_norm:
                        matched_sec = "pregnancy"
                    elif "voluntary" in clean_norm:
                        matched_sec = "voluntary"
                    elif "confidential" in clean_norm:
                        matched_sec = "confidentiality"
                    elif "contact" in clean_norm or "questions" in clean_norm:
                        matched_sec = "questions_contact"
                if True:
                    new_text = f"{current_number}. {heading_title}"
                    if p.runs:
                        p.runs[0].text = new_text
                        for r in p.runs[1:]:
                            r.text = ""
                    else:
                        p.text = new_text
                    current_number += 1


def prune_subsections_and_empty_blocks(document, values=None):
    body_elements = list(document.element.body)
    to_remove = []
    for elem in body_elements:
        tag = elem.tag.rsplit("}", 1)[-1] if "}" in elem.tag else elem.tag
        if tag == "p":
            p = Paragraph(elem, document)
            if not p.text.strip():
                to_remove.append(elem)
    for elem in to_remove:
        parent = elem.getparent()
        if parent is not None:
            parent.remove(elem)


def grounded_or_fallback(val, topic_label):
    if val and val.strip() and not val.strip().startswith("Not provided in the study protocol."):
        return val.strip()
    if "purpose" in topic_label:
        return "Specific details regarding the study purpose were not provided in the study protocol."
    return f"Specific information about {topic_label} was not provided in the study protocol."


def build_placeholder_values(draft, study_id, export_type, facts=None):
    sections = {sec.section_id: sec for sec in draft.sections}
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    label = "Patient-Friendly ICF" if export_type == "patient_friendly" else "Standard ICF"

    values = {}
    for key, sec in sections.items():
        if sec.status != FactStatusEnum.NOT_FOUND and sec.content and not sec.content.strip().startswith("Not provided in the study protocol."):
            values[key] = sec.content
        else:
            values[key] = ""

    title_val = (facts.study_title.value if facts and facts.study_title and facts.study_title.status != FactStatusEnum.NOT_FOUND else None) or values.get("study_title") or f"Clinical Trial Protocol {study_id}"
    purpose_val = values.get("purpose") or grounded_or_fallback(None, "study purpose")
    interventions_val = values.get("interventions") or ""
    duration_val = values.get("duration") or ""

    phase_val = ""
    if facts and facts.phase and facts.phase.status != FactStatusEnum.NOT_FOUND and facts.phase.value:
        phase_val = clean_phase(facts.phase.value)

    inc_text = ""
    exc_text = ""
    why_asked_intro = ""
    if facts and facts.eligibility:
        if facts.eligibility.inclusion:
            inc_text = format_bullet_list(facts.eligibility.inclusion)
        if facts.eligibility.exclusion:
            exc_text = format_bullet_list(facts.eligibility.exclusion)

    why_asked_val = values.get("why_asked") or "You are being asked to participate in this study because you meet the eligibility criteria for the study population."

    randomization_val = ""
    blinding_val = ""
    comparator_val = ""
    groups_val = ""

    if facts:
        all_text = " ".join(
            [i.value for i in facts.interventions if i.value] +
            [af.value for af in facts.additional_facts if af.value] +
            [c.value for c in facts.comparators if c.value]
        )
        all_lower = all_text.lower()

        if "randomiz" in all_lower or "randomly" in all_lower:
            m = re.search(r"([^.]*randomiz[^.]*\.)", all_text, re.IGNORECASE)
            randomization_val = m.group(1).strip() if m else "Participants are randomly assigned to study treatment groups."

        if "blind" in all_lower:
            m = re.search(r"([^.]*(?:double-blind|single-blind|open-label|blinded)[^.]*\.)", all_text, re.IGNORECASE)
            blinding_val = m.group(1).strip() if m else "Study treatment assignment blinding information."
        elif "open-label" in all_lower or "open label" in all_lower:
            blinding_val = "This study is an open-label clinical trial."

        if facts.comparators:
            comparator_val = "The study compares the following treatment arms: " + ", ".join([c.value for c in facts.comparators if c.value])
        elif "comparator" in all_lower or "placebo" in all_lower or "regimens" in all_lower:
            m = re.search(r"([^.]*(?:three treatment regimens|treatment arms|placebo|comparator)[^.]*\.)", all_text, re.IGNORECASE)
            comparator_val = m.group(1).strip() if m else ""

        if "group" in all_lower or "arm" in all_lower or "allocation" in all_lower:
            m = re.search(r"([^.]*(?:three treatment|treatment arms|assigned to|groups)[^.]*\.)", all_text, re.IGNORECASE)
            groups_val = m.group(1).strip() if m else ""

    part_dur = ""
    follow_dur = ""
    if facts and facts.duration and facts.duration.status != FactStatusEnum.NOT_FOUND and facts.duration.value:
        part_dur = f"Your total participation in this study is expected to last: {facts.duration.value}"

    key_info = f"Study Title: {title_val}\n\nStudy Purpose: {purpose_val}\n\nMain Interventions: {interventions_val}\n\nDuration: {duration_val}".strip()

    risks_display = grounded_or_fallback(values.get("risks"), "risks and side effects")
    dur_display = grounded_or_fallback(values.get("duration"), "study duration")
    ben_display = grounded_or_fallback(values.get("benefits"), "potential benefits")
    post_care_val = (values.get("post_trial_care") or values.get("post_trial")) if (values.get("post_trial_care") or values.get("post_trial")) else "Care after completion of the study as described in the protocol."
    investigator_phone = values.get("INVESTIGATOR_PHONE") or ""
    emergency_contact = values.get("EMERGENCY_CONTACT_NAME_AND_PHONE") or ""
    ethics_val = values.get("ETHICS_COMMITTEE_NAME") or ""
    ethics_phone_email = values.get("ETHICS_COMMITTEE_PHONE_EMAIL") or ""

    values.update({
        "study_id": study_id,
        "STUDY_ID": study_id,
        "REGISTRATION_NUMBER": study_id,
        "revision": str(draft.revision),
        "ICF_VERSION": f"Revision {draft.revision}",
        "ICF_VERSION_DATE": now_str,
        "document_type": label,
        "STUDY_TITLE": title_val,
        "KEY_INFO_SUMMARY": key_info,
        "STUDY_PHASE": phase_val,
        "INVESTIGATIONAL_PRODUCT": interventions_val,
        "SPONSOR": "Study Sponsor",
        "SITE_NAME_ADDRESS": "Clinical Study Site",
        "ETHICS_COMMITTEE_NAME_AND_APPROVAL_NO": "Ethics Committee / Institutional Review Board",
        "INVITATION_INTRODUCTION": values.get("invitation") or "You are invited to take part in this research study.",
        "PURPOSE_OF_STUDY": purpose_val,
        "WHY_YOU_ARE_BEING_ASKED": why_asked_val,
        "INCLUSION_SUMMARY": inc_text,
        "EXCLUSION_SUMMARY": exc_text,
        "TREATMENT_DESCRIPTION": interventions_val or grounded_or_fallback(values.get("procedures"), "study procedures"),
        "REGULATORY_STATUS_OF_PRODUCT": "Investigational product evaluated under clinical trial protocols.",
        "RANDOMIZATION_EXPLANATION": randomization_val,
        "BLINDING_EXPLANATION": blinding_val,
        "PLACEBO_COMPARATOR_EXPLANATION": comparator_val,
        "GROUPS_AND_ALLOCATION_RATIO": groups_val,
        "STUDY_PROCEDURES_OVERVIEW": values.get("procedures") or grounded_or_fallback(values.get("procedures"), "study procedures"),
        "RESEARCH_ONLY_PROCEDURES": "Research-specific procedures as detailed in the study protocol.",
        "STANDARD_CARE_PROCEDURES": "Standard clinical care procedures provided per medical guidelines.",
        "PARTICIPATION_DURATION": dur_display,
        "FOLLOW_UP_DURATION": "Follow-up period as specified in the study protocol.",
        "NUMBER_OF_PARTICIPANTS_TOTAL": "Total number of participants as specified in the study protocol.",
        "NUMBER_OF_PARTICIPANTS_SITE": "Number of participants enrolled at this study site.",
        "PARTICIPANT_RESPONSIBILITIES": "Follow study instructions, attend scheduled visits, and report any symptoms or side effects.",
        "IP_RISKS_COMMON": risks_display,
        "IP_RISKS_SERIOUS_OR_RARE": "Serious or rare risks as described in the investigator brochure.",
        "PROCEDURE_RISKS": "Procedure-related risks as specified in the study protocol.",
        "UNKNOWN_RISKS_STATEMENT": "As with any research study, there may be unknown or unexpected risks.",
        "EMERGENCY_REACTION_INSTRUCTIONS": "In case of emergency, contact the study team immediately.",
        "PREGNANCY_RISK_STATEMENT": "Risks to pregnancy, breastfeeding, or fertility as specified in the study protocol.",
        "CONTRACEPTION_REQUIREMENTS": "Contraception requirements must be followed during participation if specified in the protocol.",
        "PREGNANCY_REPORTING_AND_FOLLOW_UP": "Promptly notify the study team if pregnancy occurs during the study.",
        "POTENTIAL_BENEFITS_TO_PARTICIPANT": ben_display,
        "POTENTIAL_BENEFITS_TO_SOCIETY": "Information gained from this study may help advance medical knowledge for future patients.",
        "ALTERNATIVES_TO_PARTICIPATION": grounded_or_fallback(values.get("alternatives"), "alternatives to participation"),
        "SAMPLE_TYPES_AND_AMOUNTS": "Biological samples collected as specified in the study protocol.",
        "SAMPLE_STORAGE_LOCATION_AND_DURATION": "Samples stored securely in accordance with regulatory guidelines.",
        "GENETIC_TESTING_AND_INCIDENTAL_FINDINGS": "Genetic testing procedures as detailed in the study protocol.",
        "FUTURE_RESEARCH_USE_AND_SAMPLE_DESTRUCTION": "Future sample storage or destruction per regulatory and ethical standards.",
        "VOLUNTARY_PARTICIPATION": grounded_or_fallback(values.get("voluntary"), "voluntary participation"),
        "WITHDRAWAL_PROCEDURE_AND_SAFETY_FOLLOW_UP": "You may withdraw from the study at any time without penalty or loss of benefits.",
        "DATA_RETAINED_AFTER_WITHDRAWAL": "Data collected prior to withdrawal will be retained for safety and regulatory compliance.",
        "INVESTIGATOR_SPONSOR_TERMINATION_REASONS": "The study may be stopped early by the sponsor, investigator, or regulatory authority.",
        "CONFIDENTIALITY_PRIVACY": grounded_or_fallback(values.get("confidentiality"), "confidentiality and data protection"),
        "RECORD_ACCESS_PARTIES": "Authorised representatives of the sponsor, Ethics Committee, and regulatory authorities.",
        "AUDIO_VISUAL_RECORDING_STATEMENT": "Audio-visual recordings, if any, made with participant consent.",
        "DATA_SHARING_AND_INTERNATIONAL_TRANSFER": "Data shared in compliance with applicable data privacy regulations.",
        "RECORD_RETENTION_PERIOD": "Records retained for the duration required by applicable regulatory standards.",
        "COSTS_TO_PARTICIPANT": "Study-related procedures and investigational products are provided at no cost to you.",
        "COMPENSATION_PAYMENT": grounded_or_fallback(values.get("compensation"), "payment or compensation for participation"),
        "RESEARCH_RELATED_INJURY_MEDICAL_CARE": "Medical treatment will be provided for study-related injuries in accordance with regulations.",
        "INJURY_COMPENSATION_PROVIDER_AND_INSURANCE": "Compensation and insurance coverage for study-related injuries provided per applicable guidelines.",
        "NEW_INFORMATION_FINDINGS": "You will be informed promptly of any new information that may affect your willingness to participate.",
        "POST_TRIAL_ACCESS_AND_FOLLOW_UP_CARE": post_care_val,
        "POST_STUDY_CARE": post_care_val, "post_trial_care": post_care_val, "post_study_care": post_care_val,
        "POST_TRIAL_CARE": post_care_val,
        "RISKS": risks_display, "risks": risks_display,
        "RISKS_AND_SIDE_EFFECTS": risks_display,
        "SIDE_EFFECTS": risks_display,
        "RISKS_AND_DISCOMFORTS": risks_display,
        "STUDY_REGISTRATION_STATEMENT": "This clinical study is registered on a public trial registry.",
        "RESULTS_SHARING_STATEMENT": grounded_or_fallback(values.get("study_registration"), "study results sharing"),
        "questions_contact": values.get("questions_contact") or "Contact information was not provided in the study protocol.",
        "WHO_TO_CONTACT": values.get("questions_contact") or "Questions or concerns should be directed to the Principal Investigator or Ethics Committee.",
        "INVESTIGATOR_PHONE": investigator_phone or "Phone number provided by study site.",
        "EMERGENCY_CONTACT_NAME_AND_PHONE": emergency_contact or "24-hour emergency contact provided by study site.",
        "ETHICS_COMMITTEE_NAME": ethics_val or "Ethics Committee / IRB",
        "ETHICS_COMMITTEE_PHONE_EMAIL": ethics_phone_email or "Contact info provided by Ethics Committee.",
        "OPTIONAL_CONSENT_1_SAMPLE_STORAGE": "I consent to the storage of my biological samples for future research.",
        "OPTIONAL_CONSENT_2_GENETIC_TESTING": "I consent to genetic testing on my biological samples for this study.",
        "OPTIONAL_CONSENT_3_FUTURE_CONTACT": "I consent to being contacted in the future about other research studies.",
        "STUDY_OVERVIEW": key_info_summary if 'key_info_summary' in locals() else key_info,
        "STUDY_DESIGN": interventions_val or grounded_or_fallback(values.get("procedures"), "study procedures"),
        "ELIGIBILITY": why_asked_val,
        "ELIGIBILITY_CRITERIA": why_asked_val,
        "COSTS_AND_PAYMENT": grounded_or_fallback(values.get("compensation"), "payment or compensation for participation"),
        "COSTS_AND_PAYMENTS": grounded_or_fallback(values.get("compensation"), "payment or compensation for participation"),
        "NEW_INFORMATION": "You will be informed promptly of any new information that may affect your willingness to participate.",
        "POST_STUDY_CARE": post_care_val,
        "POST_TRIAL_CARE": post_care_val,
        "WHY_ASKED": why_asked_val,
        "ELIGIBILITY_SUMMARY": why_asked_val,
        "INTERVENTIONS": interventions_val or grounded_or_fallback(values.get("procedures"), "study procedures"),
        "PROCEDURES": grounded_or_fallback(values.get("procedures"), "study procedures"),
        "ALTERNATIVES": grounded_or_fallback(values.get("alternatives"), "alternatives to participation"),
        "CONFIDENTIALITY": grounded_or_fallback(values.get("confidentiality"), "confidentiality and data protection"),
        "VOLUNTARY": grounded_or_fallback(values.get("voluntary"), "voluntary participation"),
        "STUDY_REGISTRATION_AND_RESULTS": grounded_or_fallback(values.get("study_registration"), "study results sharing"),
        "CONTACT_INFORMATION": values.get("questions_contact") or "Questions or concerns should be directed to the Principal Investigator or Ethics Committee.",
        "COMPENSATION_FOR_STUDY_RELATED_INJURY": "Medical treatment will be provided for study-related injuries in accordance with regulations.",
        "VISIT_1_NAME": values.get("VISIT_1_NAME") or "Visit 1",
        "VISIT_1_TIMING": values.get("VISIT_1_TIMING") or "Day 1",
        "VISIT_2_NAME": values.get("VISIT_2_NAME") or "Visit 2",
        "VISIT_2_TIMING": values.get("VISIT_2_TIMING") or "As Scheduled",
        "VISIT_N_NAME": values.get("VISIT_N_NAME") or "Follow-up Visit",
        "VISIT__TIMING": values.get("VISIT_N_TIMING") or "Study Completion",
        "VISIT_1_ACTIVITIES": values.get("VISIT_1_PROCEDURES") or grounded_or_fallback(values.get("procedures"), "visit 1 procedures"),
        "VISIT_2_ACTIVITIES": values.get("VISIT_2_PROCEDURES") or grounded_or_fallback(values.get("procedures"), "visit 2 procedures"),
        "FOLLOW_UP_TIMING": (grounded_or_fallback(part_dur, "follow-up duration") if (part_dur and part_dur.strip()) else None) or values.get("FOLLOW_UP_DURATION") or "Follow-up period as specified in the study protocol.",
        "FOLLOW_UP_ACTIVITIES": values.get("VISIT_N_PROCEDURES") or grounded_or_fallback(values.get("procedures"), "follow-up procedures"),
        "RISKS": risks_display,
        "RISKS_AND_SIDE_EFFECTS": risks_display,
        "SIDE_EFFECTS": risks_display,
        "RISKS_AND_DISCOMFORTS": risks_display,
        "RISKS_DISCOMFORTS": risks_display,
        "DISCOMFORTS": risks_display,
        "SIDE_EFFECTS_AND_RISKS": risks_display,
        "DURATION": dur_display, "duration": dur_display,
        "STUDY_DURATION": dur_display,
        "HOW_LONG_WILL_PARTICIPATION_LAST": dur_display,
        "BENEFITS": ben_display, "benefits": ben_display,
        "POSSIBLE_BENEFITS": ben_display,
        "POTENTIAL_BENEFITS": ben_display,
    })

    return values


def render_template(content, study_id, draft, export_type, facts=None, is_custom=False):
    document, slots = inspect_docx(content)
    sections = {section.section_id: section for section in draft.sections}
    if len(sections) != len(draft.sections):
        raise TemplateError("The generated draft contains duplicate sections.")

    if facts is None:
        try:
            from app.services.icf_generation_service import icf_generation_service
            facts = icf_generation_service.get_facts(study_id)
        except Exception:
            facts = None

    label = "Patient-Facing ICF"

    values = build_placeholder_values(draft, study_id, export_type, facts=facts)

    for paragraph in paragraphs(document):
        replace_tokens(paragraph, values)

    visited = set()
    for section in document.sections:
        for region in [section.header, section.footer, section.first_page_header, section.first_page_footer, section.even_page_header, section.even_page_footer]:
            if region.part in visited:
                continue
            visited.add(region.part)
            for element in region._element.iter(W + "p"):
                replace_tokens(Paragraph(element, region), values)

    for name, (mode, paragraph) in slots.items():
        if mode == "heading":
            sec = sections.get(name)
            val = values.get(name, "")
            if val:
                populate_heading(paragraph, val)
            elif sec and sec.content:
                populate_heading(paragraph, sec.content)

    remove_target_unsupported_sections_and_renumber(document, draft, facts, values, is_custom=is_custom)
    prune_subsections_and_empty_blocks(document, values)

    document.core_properties.title = f"{study_id} {label} Revision {draft.revision}"
    document.core_properties.subject = f"Study {study_id}; Revision {draft.revision}; {export_type}"
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def document_text(content):
    import docx
    document = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in paragraphs(document) if p.text.strip())
