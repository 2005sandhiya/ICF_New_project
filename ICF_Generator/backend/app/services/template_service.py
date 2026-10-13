"""Validated, study-isolated template storage. Template text never enters RAG or LLM prompts."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

import docx
from lxml import etree

from app.models.template import TemplateSelection
from app.services.workflow_lock import study_lock

MAX_TEMPLATE_BYTES = 10 * 1024 * 1024
TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "data" / "templates" / "custom"
DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "data" / "templates" / "ICF_Clinical_Study_Template_FINAL.docx"

SECTION_TITLES = {
    "study_title": "Study Title", "invitation": "Invitation to Participate",
    "purpose": "Purpose of the Study", "why_asked": "Why You Are Being Asked",
    "procedures": "Study Procedures", "duration": "Study Duration",
    "interventions": "Study Interventions / Treatments", "risks": "Risks and Discomforts",
    "benefits": "Potential Benefits", "alternatives": "Alternatives to Participation",
    "voluntary": "Voluntary Participation", "confidentiality": "Confidentiality",
    "questions_contact": "Questions / Contact Information",
}
TOKEN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}|\[([A-Za-z0-9_ ]+)\]")
METADATA_FIELDS = {
    "study_id", "revision", "document_type", "ICF_VERSION", "ICF_VERSION_DATE",
    "STUDY_ID", "REGISTRATION_NUMBER", "STUDY_TITLE", "STUDY_PHASE", "INVESTIGATIONAL_PRODUCT",
    "SPONSOR", "INVESTIGATOR", "INVESTIGATOR_PHONE", "EMERGENCY_CONTACT_NAME_AND_PHONE",
    "ETHICS_COMMITTEE_NAME", "ETHICS_COMMITTEE_PHONE_EMAIL",
    "SITE_NAME_ADDRESS", "ETHICS_COMMITTEE_NAME_AND_APPROVAL_NO"
}
SIGNATURE_FIELDS = {
    "PARTICIPANT_NAME", "PARTICIPANT_SIGNATURE_OR_THUMB_IMPRESSION", "PARTICIPANT_SIGN_DATE",
    "LAR_NAME", "LAR_RELATIONSHIP", "LAR_SIGNATURE", "LAR_SIGN_DATE",
    "WITNESS_NAME", "WITNESS_SIGNATURE", "WITNESS_SIGN_DATE",
    "PERSON_OBTAINING_CONSENT_NAME", "CONSENT_TAKER_ROLE", "PERSON_OBTAINING_CONSENT_SIGNATURE", "CONSENT_DATE",
    "INVESTIGATOR_SIGNATURE", "INVESTIGATOR_SIGN_DATE",
}
BRACKET_TO_CANONICAL = {
    "STUDY_TITLE": "study_title", "INVITATION_INTRODUCTION": "invitation", "PURPOSE_OF_STUDY": "purpose",
    "WHY_YOU_ARE_BEING_ASKED": "why_asked", "INCLUSION_SUMMARY": "why_asked", "EXCLUSION_SUMMARY": "why_asked",
    "TREATMENT_DESCRIPTION": "interventions", "REGULATORY_STATUS_OF_PRODUCT": "interventions",
    "RANDOMIZATION_EXPLANATION": "interventions", "BLINDING_EXPLANATION": "interventions",
    "PLACEBO_COMPARATOR_EXPLANATION": "interventions", "GROUPS_AND_ALLOCATION_RATIO": "interventions",
    "STUDY_PROCEDURES_OVERVIEW": "procedures", "RESEARCH_ONLY_PROCEDURES": "procedures",
    "STANDARD_CARE_PROCEDURES": "procedures", "PARTICIPATION_DURATION": "duration",
    "FOLLOW_UP_DURATION": "duration", "NUMBER_OF_PARTICIPANTS_TOTAL": "invitation",
    "NUMBER_OF_PARTICIPANTS_SITE": "invitation", "PARTICIPANT_RESPONSIBILITIES": "voluntary",
    "IP_RISKS_COMMON": "risks", "IP_RISKS_SERIOUS_OR_RARE": "risks", "PROCEDURE_RISKS": "risks",
    "UNKNOWN_RISKS_STATEMENT": "risks", "EMERGENCY_REACTION_INSTRUCTIONS": "risks",
    "PREGNANCY_RISK_STATEMENT": "pregnancy", "CONTRACEPTION_REQUIREMENTS": "pregnancy",
    "PREGNANCY_REPORTING_AND_FOLLOW_UP": "pregnancy", "POTENTIAL_BENEFITS_TO_PARTICIPANT": "benefits",
    "POTENTIAL_BENEFITS_TO_SOCIETY": "benefits", "ALTERNATIVES_TO_PARTICIPATION": "alternatives",
    "SAMPLE_TYPES_AND_AMOUNTS": "biological_samples", "SAMPLE_STORAGE_LOCATION_AND_DURATION": "biological_samples",
    "GENETIC_TESTING_AND_INCIDENTAL_FINDINGS": "biological_samples",
    "FUTURE_RESEARCH_USE_AND_SAMPLE_DESTRUCTION": "biological_samples",
    "VOLUNTARY_PARTICIPATION": "voluntary", "WITHDRAWAL_PROCEDURE_AND_SAFETY_FOLLOW_UP": "voluntary",
    "DATA_RETAINED_AFTER_WITHDRAWAL": "voluntary", "INVESTIGATOR_SPONSOR_TERMINATION_REASONS": "voluntary",
    "CONFIDENTIALITY_PRIVACY": "confidentiality", "RECORD_ACCESS_PARTIES": "confidentiality",
    "AUDIO_VISUAL_RECORDING_STATEMENT": "confidentiality", "DATA_SHARING_AND_INTERNATIONAL_TRANSFER": "confidentiality",
    "RECORD_RETENTION_PERIOD": "confidentiality", "COSTS_TO_PARTICIPANT": "costs",
    "COMPENSATION_PAYMENT": "compensation", "RESEARCH_RELATED_INJURY_MEDICAL_CARE": "injury",
    "INJURY_COMPENSATION_PROVIDER_AND_INSURANCE": "injury", "NEW_INFORMATION_FINDINGS": "new_information",
    "POST_TRIAL_ACCESS_AND_FOLLOW_UP_CARE": "post_trial_care", "STUDY_REGISTRATION_STATEMENT": "study_registration",
    "RESULTS_SHARING_STATEMENT": "study_registration", "INVESTIGATOR": "questions_contact",
    "INVESTIGATOR_PHONE": "questions_contact", "EMERGENCY_CONTACT_NAME_AND_PHONE": "questions_contact",
    "ETHICS_COMMITTEE_NAME": "questions_contact", "ETHICS_COMMITTEE_PHONE_EMAIL": "questions_contact",
    "OPTIONAL_CONSENT_1_SAMPLE_STORAGE": "biological_samples", "OPTIONAL_CONSENT_2_GENETIC_TESTING": "biological_samples",
    "OPTIONAL_CONSENT_3_FUTURE_CONTACT": "voluntary", "KEY_INFO_SUMMARY": "purpose",
    "WHO_TO_CONTACT": "questions_contact",
    "VISIT_1_NAME": "procedures", "VISIT_1_TIMING": "procedures", "VISIT_1_PROCEDURES": "procedures",
    "VISIT_2_NAME": "procedures", "VISIT_2_TIMING": "procedures", "VISIT_2_PROCEDURES": "procedures",
    "VISIT_N_NAME": "procedures", "VISIT_N_TIMING": "procedures", "VISIT_N_PROCEDURES": "procedures",
    "STUDY_OVERVIEW": "purpose", "STUDY_DESIGN": "interventions", "ELIGIBILITY": "why_asked",
    "ELIGIBILITY_CRITERIA": "why_asked", "COSTS_AND_PAYMENT": "compensation", "COSTS_AND_PAYMENTS": "compensation",
    "NEW_INFORMATION": "new_information", "POST_STUDY_CARE": "post_trial_care", "POST_TRIAL_CARE": "post_trial_care",
    "WHY_ASKED": "why_asked", "ELIGIBILITY_SUMMARY": "why_asked",
    "INTERVENTIONS": "interventions", "PROCEDURES": "procedures",
    "ALTERNATIVES": "alternatives", "CONFIDENTIALITY": "confidentiality",
    "VOLUNTARY": "voluntary", "STUDY_REGISTRATION_AND_RESULTS": "study_registration",
    "CONTACT_INFORMATION": "questions_contact", "COMPENSATION_FOR_STUDY_RELATED_INJURY": "injury",
    "VISIT_1_ACTIVITIES": "VISIT_1_PROCEDURES", "VISIT_2_ACTIVITIES": "VISIT_2_PROCEDURES",
    "RISKS": "risks", "RISKS_AND_SIDE_EFFECTS": "risks", "SIDE_EFFECTS": "risks",
    "RISKS_AND_DISCOMFORTS": "risks", "RISKS_DISCOMFORTS": "risks", "DISCOMFORTS": "risks",
    "SIDE_EFFECTS_AND_RISKS": "risks",
    "DURATION": "duration", "STUDY_DURATION": "duration", "HOW_LONG_WILL_PARTICIPATION_LAST": "duration",
    "BENEFITS": "benefits", "POSSIBLE_BENEFITS": "benefits", "POTENTIAL_BENEFITS": "benefits",
}
SUPPORTED_TOPICS = set(SECTION_TITLES).union({
    "pregnancy", "biological_samples", "costs", "compensation", "injury",
    "new_information", "post_trial_care", "study_registration"
})
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class TemplateError(ValueError):
    pass


def normalize_heading(value):
    return re.sub(r"[^a-z]+", " ", re.sub(r"^\s*[\d.()]+\s*", "", value.lower())).strip()


HEADINGS = {normalize_heading(v): k for k, v in SECTION_TITLES.items()}
HEADINGS.update({normalize_heading(k.replace("_", " ")): k for k in SECTION_TITLES})
HEADINGS.update({
    "why is this study being done": "purpose", "what will happen during the study": "procedures",
    "how long will the study take": "duration", "risks": "risks", "benefits": "benefits",
    "it is your choice to take part in the study": "voluntary",
    "who can i contact with questions": "questions_contact",
    "introduction": "invitation",
    "purpose of the research": "purpose",
    "type of research intervention": "interventions",
    "participant selection": "why_asked",
    "voluntary participation": "voluntary",
    "information on the trial drug intervention": "interventions",
    "procedures and protocol": "procedures",
    "unfamiliar procedures": "procedures",
    "description of the process": "procedures",
    "duration": "duration",
    "side effects": "risks",
    "side effects and risks": "risks",
    "risks and discomforts": "risks",
    "potential benefits": "benefits",
    "reimbursements": "compensation",
    "confidentiality": "confidentiality",
    "sharing the results": "study_registration",
    "risks side effects": "risks",
    "risks and side effects": "risks",
    "who to contact": "questions_contact",
    "study design": "interventions",
    "trial design": "interventions",
    "pregnancy breastfeeding and fertility": "pregnancy",
    "pregnancy breastfeeding fertility": "pregnancy",
    "pregnancy": "pregnancy",
    "risks to pregnancy breastfeeding and fertility": "pregnancy",
    "eligibility": "why_asked",
    "eligibility criteria": "why_asked",
    "who can take part": "why_asked",
    "who cannot take part": "why_asked",
    "regulatory status": "interventions",
    "randomisation": "interventions",
    "randomization": "interventions",
    "blinding": "interventions",
    "placebo comparator": "interventions",
    "placebo": "interventions",
    "comparator": "interventions",
    "number of groups and chance of assignment": "interventions",
    "groups and allocation": "interventions",
    "procedures done only for research": "procedures",
    "procedures that are part of your routine care": "procedures",
    "risks of the study treatment": "risks",
    "risks of study procedures": "risks",
    "unknown risks": "risks",
    "allergic reactions and emergencies": "risks",
    "if you decide to withdraw": "voluntary",
    "if the investigator or sponsor ends your participation": "voluntary",
    "who may see your records": "confidentiality",
    "audio visual recording of the consent process": "confidentiality",
    "data sharing and transfer": "confidentiality",
    "how long records are kept": "confidentiality",
    "biological samples genetic testing and future use": "biological_samples",
    "other choices alternatives": "alternatives",
    "alternatives to participation": "alternatives",
    "costs and payment": "compensation",
    "costs and payments": "compensation",
    "new information": "new_information",
    "new findings": "new_information",
    "post study care": "post_trial_care",
    "post trial care": "post_trial_care",
    "why asked": "why_asked",
    "eligibility summary": "why_asked",
    "interventions": "interventions",
    "procedures": "procedures",
    "alternatives": "alternatives",
    "confidentiality": "confidentiality",
    "voluntary": "voluntary",
    "study registration and results": "study_registration",
    "contact information": "questions_contact",
    "compensation for study related injury": "injury",
    "visit 1 activities": "procedures",
    "visit 2 activities": "procedures",
    "follow up timing": "duration",
    "follow up activities": "procedures",
    "how long will participation last": "duration",
    "how long will participation take": "duration",
    "possible benefits": "benefits",
    "invitation and introduction": "invitation",
    "why you are being asked to participate": "why_asked",
    "study treatment investigational product": "interventions",
    "study procedures and visit schedule": "procedures",
    "duration of participation and number of participants": "duration",
    "participant responsibilities": "participant_responsibilities",
    "risks to pregnancy breastfeeding and fertility": "pregnancy",
    "biological samples genetic testing and future use": "biological_samples",
    "voluntary participation and withdrawal": "voluntary",
    "confidentiality and data protection": "confidentiality",
    "costs to you": "costs",
    "payment or compensation for participation": "compensation",
    "compensation and treatment for study related injury": "injury",
    "care after the study": "post_trial_care",
    "participant consent statement": "consent_statement",
    "signatures": "signatures",
})

WHO_GUIDANCE_PATTERNS = [
    r"^\s*\(?example:",
    r"^\s*example of question",
    r"^\s*examples of question",
    r"notes? to researchers?",
    r"include this section only if",
    r"briefly state who you are",
    r"explain in lay terms",
    r"describe or explain the exact procedures",
    r"describe to the participant what will happen",
    r"include a statement about the time commitments",
    r"potential participants should be told",
    r"explain and describe any possible",
    r"mention only those activities",
    r"state clearly what you will provide",
    r"explain how the research team will maintain",
    r"where it is relevant, your plan for sharing",
    r"this is a reconfirmation that participation",
    r"provide the name and contact information",
    r"this proposal has been reviewed and approved by",
    r"you can ask me any more questions about any part",
    r"this section should be written in the first person",
    r"a literate witness must sign",
    r"participants who are illiterate should include",
    r"\[name of ", r"\[name, address", r"\[informed consent form for",
    r"\[amount"
]


def is_who_guidance_text(text):
    t = text.strip()
    if not t:
        return False
    if t.upper() in ["OR", "A.", "B."]:
        return True
    for pat in WHO_GUIDANCE_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return True
    return False


def is_who_guidance_placeholder(raw, paragraph_text):
    raw_lower = raw.lower().strip()
    if raw_lower in ["amount"] or raw_lower.startswith("name of") or raw_lower.startswith("name, address") or raw_lower.startswith("informed consent form"):
        return True
    return is_who_guidance_text(paragraph_text)


def paragraphs(document):
    """All body paragraphs, including nested tables, in document order."""
    from docx.text.paragraph import Paragraph
    return [Paragraph(element, document) for element in document.element.body.iter(W + "p")]


def template_map(document):
    body = paragraphs(document)
    slots = {}
    all_app_placeholders = (
        set(SIGNATURE_FIELDS)
        .union(METADATA_FIELDS)
        .union(BRACKET_TO_CANONICAL)
        .union(SECTION_TITLES)
        .union(SUPPORTED_TOPICS)
    )

    for paragraph in body:
        for match in TOKEN.finditer(paragraph.text):
            raw = match.group(1) or match.group(2)
            name = raw.removeprefix("icf.") if raw else ""
            canonical = BRACKET_TO_CANONICAL.get(name, name)

            is_explicit_icf_namespace = bool(match.group(1)) and raw.startswith("icf.")
            is_known_app_token = (
                name in all_app_placeholders
                or canonical in all_app_placeholders
                or name in SIGNATURE_FIELDS
                or name in METADATA_FIELDS
                or canonical in METADATA_FIELDS
            )

            if is_explicit_icf_namespace:
                if canonical not in SECTION_TITLES and canonical not in SUPPORTED_TOPICS and name not in SIGNATURE_FIELDS and name not in METADATA_FIELDS and canonical not in METADATA_FIELDS:
                    raise TemplateError("Unsupported template placeholder: " + raw)
                if canonical in SECTION_TITLES:
                    if canonical in slots:
                        raise TemplateError("Duplicate template section: " + name)
                    slots.setdefault(canonical, ("token", paragraph))
            elif is_known_app_token:
                if name in SIGNATURE_FIELDS or name in METADATA_FIELDS or canonical in METADATA_FIELDS:
                    continue
                if canonical in SECTION_TITLES:
                    slots.setdefault(canonical, ("token", paragraph))
            else:
                # Custom template layout wording / arbitrary headings (e.g. [STUDY_OVERVIEW], {{ STUDY_OVERVIEW }}, [Name], [Signature])
                # Retain intact as unverified template wording without validation failure or converting to clinical evidence.
                continue

    # Scan heading titles for any canonical section titles not bound by explicit tokens
    from docx.oxml import OxmlElement
    from docx.text.paragraph import Paragraph
    for idx, paragraph in enumerate(body):
        text = paragraph.text.strip()
        if (text.startswith("[") and text.endswith("]")) or (text.startswith("{{") and text.endswith("}}")):
            continue
        name = HEADINGS.get(normalize_heading(text))
        if name and name in SECTION_TITLES and name not in slots:
            target_p = None
            if idx + 1 < len(body):
                next_p = body[idx + 1]
                if not (next_p.style and next_p.style.name and next_p.style.name.lower().startswith("heading")):
                    target_p = next_p
            if target_p is None:
                new_p = OxmlElement(W + "p")
                paragraph._p.addnext(new_p)
                target_p = Paragraph(new_p, paragraph._parent)
            slots[name] = ("heading", target_p)
    if not slots:
        raise TemplateError("No ICF sections recognized. Add a placeholder such as {{icf.purpose}} or a heading such as 'Purpose of the Study'.")
    return slots


def inspect_docx(content):
    if not content or len(content) > MAX_TEMPLATE_BYTES:
        raise TemplateError("Upload a non-empty DOCX template no larger than 10 MB.")
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(names) != len(set(names)) or len(entries) > 2000:
                raise TemplateError("The DOCX package has duplicate or too many parts.")
            if not {"[Content_Types].xml", "word/document.xml", "_rels/.rels"}.issubset(names):
                raise TemplateError("The uploaded file is not a complete DOCX document.")
            if sum(entry.file_size for entry in entries) > 50 * 1024 * 1024:
                raise TemplateError("The expanded template exceeds the 50 MB limit.")
            for entry in entries:
                path = PurePosixPath(entry.filename.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts or entry.flag_bits & 1:
                    raise TemplateError("Unsafe or encrypted DOCX package.")
                lowered = entry.filename.lower()
                if any(part in lowered for part in ["vbaproject", "embeddings/", "activex/"]):
                    raise TemplateError("Templates with macros or embedded executable objects are not supported.")
                if entry.file_size > max(entry.compress_size, 1) * 300:
                    raise TemplateError("The DOCX package has an unsafe compression ratio.")
                if lowered.endswith((".xml", ".rels")):
                    raw = archive.read(entry)
                    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                        raise TemplateError("XML entities are not supported in templates.")
                    xml = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))
                    if lowered.endswith(".rels"):
                        for rel in xml:
                            if rel.get("TargetMode") == "External" and not (
                                rel.get("Type", "").endswith("/hyperlink")
                                and rel.get("Target", "").startswith(("https://", "http://", "mailto:"))
                            ):
                                raise TemplateError("External images, linked documents and remote templates are not supported.")
                    if lowered.startswith("word/"):
                        unsupported = {W + name for name in ["altChunk", "object", "ins", "del"]}
                        if any(element.tag in unsupported for element in xml.iter()):
                            raise TemplateError("Remove text boxes, embedded content and tracked changes before uploading this template.")
                        for element in xml.iter(W + "instrText"):
                            if re.search(r"\b(DDE|INCLUDETEXT|INCLUDEPICTURE|LINK)\b", element.text or "", re.I):
                                raise TemplateError("Linked document fields are not supported.")
        document = docx.Document(io.BytesIO(content))
        slots = template_map(document)
        return document, slots
    except TemplateError:
        raise
    except Exception as exc:
        raise TemplateError("The DOCX template is invalid or corrupted. Open and save it as DOCX, then try again.") from exc


class TemplateService:
    def __init__(self, root=TEMPLATE_DIR):
        self.root = Path(root)

    def _folder(self, study_id):
        if not study_id or not study_id.strip() or len(study_id) > 200:
            raise TemplateError("A study ID of 1 to 200 characters is required.")
        return self.root / hashlib.sha256(study_id.strip().encode()).hexdigest()

    def selection(self, study_id):
        manifest = self._folder(study_id) / "selection.json"
        if not manifest.exists():
            return TemplateSelection(study_id=study_id.strip(), mapped_sections=list(SECTION_TITLES))
        try:
            selected = TemplateSelection.model_validate_json(manifest.read_text(encoding="utf-8"))
            if selected.study_id != study_id.strip() or not re.fullmatch(r"[a-f0-9]{32}", selected.template_id):
                raise ValueError("Invalid selection")
            self.read(study_id, selected)
            return selected
        except Exception as exc:
            raise TemplateError("The selected template is missing or invalid. Replace it or explicitly remove it to use the default.") from exc

    def read(self, study_id, selected):
        if selected.study_id != study_id.strip():
            raise TemplateError("Template study mismatch.")
        if selected.kind == "default":
            if selected.template_id != "builtin-v1":
                raise TemplateError("Unknown default template version.")
            if DEFAULT_TEMPLATE_PATH.is_file():
                return DEFAULT_TEMPLATE_PATH.read_bytes()
            return None
        if not re.fullmatch(r"[a-f0-9]{32}", selected.template_id):
            raise TemplateError("Invalid template identifier.")
        try:
            content = (self._folder(study_id) / (selected.template_id + ".docx")).read_bytes()
        except OSError as exc:
            raise TemplateError("The selected template is missing. Replace it or explicitly remove it to use the default.") from exc
        if hashlib.sha256(content).hexdigest() != selected.sha256:
            raise TemplateError("The selected template has changed unexpectedly. Upload it again before generating a new revision.")
        return content

    def upload(self, study_id, filename, content):
        clean_name = (filename or "").replace("\\", "/").split("/")[-1]
        clean_name = re.sub(r"[\x00-\x1f\x7f]", "", clean_name)[:180]
        if Path(clean_name).suffix.lower() != ".docx":
            raise TemplateError("Only DOCX templates are supported.")
        _, slots = inspect_docx(content)
        missing = [key for key in SECTION_TITLES if key not in slots]
        warnings = ["Unmapped template text is retained as unverified template wording. Review it for sample clinical claims before approval."]
        if missing:
            warnings.append("Missing template sections will not be added to the custom layout: " + ", ".join(missing) + ".")
        selected = TemplateSelection(
            study_id=study_id.strip(), template_id=uuid4().hex, filename=clean_name,
            kind="custom", sha256=hashlib.sha256(content).hexdigest(),
            mapped_sections=list(slots), missing_sections=missing, warnings=warnings,
        )
        with study_lock(study_id):
            folder = self._folder(study_id)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (selected.template_id + ".docx")).write_bytes(content)
            temporary = folder / (uuid4().hex + ".json.tmp")
            temporary.write_text(selected.model_dump_json(indent=2), encoding="utf-8")
            os.replace(temporary, folder / "selection.json")
        return selected

    def remove(self, study_id):
        with study_lock(study_id):
            (self._folder(study_id) / "selection.json").unlink(missing_ok=True)
            # Immutable template versions remain available to revision history.
            return self.selection(study_id)


template_service = TemplateService()
