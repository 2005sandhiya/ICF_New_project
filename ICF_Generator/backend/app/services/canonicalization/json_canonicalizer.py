import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from app.models.canonical_protocol import (
    CanonicalProtocol, 
    ObjectivesInfo, 
    EligibilityInfo, 
    OutcomesInfo, 
    ProtocolSectionItem
)

logger = logging.getLogger("icf_generator.json_canonicalizer")

class JSONCanonicalizer:
    """
    Deterministic mapper from ClinicalTrials.gov JSON structures to CanonicalProtocol objects (Phase 3 Part 3).
    """

    @staticmethod
    def canonicalize(raw_data: Dict[str, Any], filename: str) -> CanonicalProtocol:
        if isinstance(raw_data, list):
            if len(raw_data) > 0 and isinstance(raw_data[0], dict):
                data = raw_data[0]
            else:
                data = {}
        elif isinstance(data := raw_data, dict):
            pass
        else:
            data = {}

        protocol = data.get("protocolSection", {})
        ident = protocol.get("identificationModule", {})
        status_mod = protocol.get("statusModule", {})
        desc_mod = protocol.get("descriptionModule", {})
        cond_mod = protocol.get("conditionsModule", {})
        design_mod = protocol.get("designModule", {})
        arms_mod = protocol.get("armsInterventionsModule", {})
        outcomes_mod = protocol.get("outcomesModule", {})
        elig_mod = protocol.get("eligibilityModule", {})

        # 1. Top-level fields
        study_id = ident.get("nctId") or data.get("study_id") or None
        brief_title = ident.get("briefTitle") or ident.get("officialTitle") or data.get("title") or None
        official_title = ident.get("officialTitle") or None
        overall_status = status_mod.get("overallStatus") or data.get("status") or None
        study_type = design_mod.get("studyType") or data.get("study_type") or None

        raw_phases = design_mod.get("phases") or data.get("phase")
        if isinstance(raw_phases, list):
            phase = ", ".join(str(p) for p in raw_phases)
        elif isinstance(raw_phases, str):
            phase = raw_phases
        else:
            phase = None

        conditions = cond_mod.get("conditions") or data.get("conditions") or []

        # 2. Interventions
        raw_interventions = arms_mod.get("interventions") or data.get("interventions") or []
        interventions: List[Dict[str, Any]] = []
        for inv in raw_interventions:
            if isinstance(inv, dict):
                interventions.append({
                    "name": inv.get("name", "Unspecified"),
                    "type": inv.get("type"),
                    "description": inv.get("description")
                })

        # 3. Outcomes
        primary_outcomes: List[str] = []
        for out in outcomes_mod.get("primaryOutcomes", []):
            if isinstance(out, dict) and out.get("measure"):
                meas = out.get("measure")
                desc = f" ({out.get('description')})" if out.get("description") else ""
                primary_outcomes.append(f"{meas}{desc}")

        secondary_outcomes: List[str] = []
        for out in outcomes_mod.get("secondaryOutcomes", []):
            if isinstance(out, dict) and out.get("measure"):
                meas = out.get("measure")
                desc = f" ({out.get('description')})" if out.get("description") else ""
                secondary_outcomes.append(f"{meas}{desc}")

        # 4. Eligibility
        elig_raw = elig_mod.get("eligibilityCriteria") or data.get("eligibility") or None
        inclusion_pts, exclusion_pts = JSONCanonicalizer._split_eligibility_criteria(elig_raw)

        eligibility = EligibilityInfo(
            inclusion=inclusion_pts,
            exclusion=exclusion_pts,
            raw_text=elig_raw,
            minimum_age=elig_mod.get("minimumAge"),
            maximum_age=elig_mod.get("maximumAge"),
            sex=elig_mod.get("sex"),
            healthy_volunteers=elig_mod.get("healthyVolunteers")
        )

        # 5. Objectives & Description
        brief_summary = desc_mod.get("briefSummary") or ""
        detailed_description = desc_mod.get("detailedDescription") or ""

        objectives = ObjectivesInfo(
            primary=[brief_summary] if brief_summary else [],
            secondary=[detailed_description] if detailed_description else []
        )

        # 6. Source Sections Traceability
        source_sections: List[ProtocolSectionItem] = []
        if brief_summary or detailed_description:
            source_sections.append(ProtocolSectionItem(
                section_name="description",
                heading="Brief Summary & Detailed Description",
                content="\n\n".join(filter(None, [brief_summary, detailed_description])),
                source_metadata={"type": "json", "field_path": "protocolSection.descriptionModule"}
            ))

        # Design & Population Module
        design_text_parts = []
        if study_type:
            design_text_parts.append(f"Study Type: {study_type}")
        if phase:
            design_text_parts.append(f"Phase: {phase}")
        if design_mod.get("designInfo"):
            dinfo = design_mod.get("designInfo")
            if dinfo.get("allocation"):
                design_text_parts.append(f"Allocation: {dinfo.get('allocation')}")
            if dinfo.get("interventionModel"):
                design_text_parts.append(f"Intervention Model: {dinfo.get('interventionModel')}")
            if dinfo.get("primaryPurpose"):
                design_text_parts.append(f"Primary Purpose: {dinfo.get('primaryPurpose')}")
            if dinfo.get("maskingInfo"):
                minfo = dinfo.get("maskingInfo", {})
                if minfo.get("masking"):
                    design_text_parts.append(f"Masking: {minfo.get('masking')}")
        if design_mod.get("enrollmentInfo"):
            einfo = design_mod.get("enrollmentInfo", {})
            if einfo.get("count"):
                design_text_parts.append(f"Enrollment Target: {einfo.get('count')} participants")

        if design_text_parts:
            source_sections.append(ProtocolSectionItem(
                section_name="design",
                heading="Study Design & Population Parameters",
                content="\n".join(design_text_parts),
                source_metadata={"type": "json", "field_path": "protocolSection.designModule"}
            ))

        # Arms & Interventions Module
        interventions_text_parts = []
        for inv in raw_interventions:
            if isinstance(inv, dict):
                inv_name = inv.get("name", "Unspecified")
                inv_type = inv.get("type", "Intervention")
                inv_desc = f": {inv.get('description')}" if inv.get("description") else ""
                interventions_text_parts.append(f"- [{inv_type}] {inv_name}{inv_desc}")

        arms = arms_mod.get("armGroups", [])
        for arm in arms:
            if isinstance(arm, dict):
                arm_label = arm.get("label", "")
                arm_desc = f": {arm.get('description')}" if arm.get("description") else ""
                interventions_text_parts.append(f"- Arm: {arm_label}{arm_desc}")

        if interventions_text_parts:
            source_sections.append(ProtocolSectionItem(
                section_name="interventions",
                heading="Interventions & Regimens",
                content="\n".join(interventions_text_parts),
                source_metadata={"type": "json", "field_path": "protocolSection.armsInterventionsModule"}
            ))

        # Outcomes & Endpoints Module
        outcomes_text_parts = []
        if primary_outcomes:
            outcomes_text_parts.append("Primary Outcome Measures:")
            for po in primary_outcomes:
                outcomes_text_parts.append(f"- {po}")
        if secondary_outcomes:
            outcomes_text_parts.append("\nSecondary Outcome Measures:")
            for so in secondary_outcomes:
                outcomes_text_parts.append(f"- {so}")

        if outcomes_text_parts:
            source_sections.append(ProtocolSectionItem(
                section_name="outcomes",
                heading="Study Outcomes & Endpoints",
                content="\n".join(outcomes_text_parts),
                source_metadata={"type": "json", "field_path": "protocolSection.outcomesModule"}
            ))

        if elig_raw:
            elig_header = []
            if elig_mod.get("minimumAge") or elig_mod.get("maximumAge"):
                elig_header.append(f"Age Range: {elig_mod.get('minimumAge', 'N/A')} to {elig_mod.get('maximumAge', 'N/A')}")
            if elig_mod.get("sex"):
                elig_header.append(f"Sex: {elig_mod.get('sex')}")
            if elig_mod.get("healthyVolunteers") is not None:
                elig_header.append(f"Healthy Volunteers: {elig_mod.get('healthyVolunteers')}")
            
            full_elig_text = "\n".join(elig_header) + "\n\n" + elig_raw if elig_header else elig_raw

            source_sections.append(ProtocolSectionItem(
                section_name="eligibility",
                heading="Eligibility Criteria",
                content=full_elig_text,
                source_metadata={"type": "json", "field_path": "protocolSection.eligibilityModule"}
            ))

        contacts_locations_text_parts = []
        contacts_mod = protocol.get("contactsLocationsModule", {})
        central_contacts = contacts_mod.get("centralContacts", [])
        for c in central_contacts:
            if isinstance(c, dict):
                c_name = c.get("name", "")
                c_role = c.get("role", "")
                c_phone = f" Phone: {c.get('phone')}" if c.get("phone") else ""
                c_email = f" Email: {c.get('email')}" if c.get("email") else ""
                contacts_locations_text_parts.append(f"Contact: {c_name} ({c_role}){c_phone}{c_email}")

        locs = contacts_mod.get("locations", [])
        if locs:
            contacts_locations_text_parts.append(f"Study Facility Locations: {len(locs)} site(s) registered.")
            for loc in locs[:10]:
                if isinstance(loc, dict):
                    facility = loc.get("facility", "")
                    city = loc.get("city", "")
                    state = loc.get("state", "")
                    country = loc.get("country", "")
                    loc_str = ", ".join(filter(None, [facility, city, state, country]))
                    if loc_str:
                        contacts_locations_text_parts.append(f"- {loc_str}")

        if contacts_locations_text_parts:
            source_sections.append(ProtocolSectionItem(
                section_name="contacts_locations",
                heading="Study Contacts & Locations",
                content="\n".join(contacts_locations_text_parts),
                source_metadata={"type": "json", "field_path": "protocolSection.contactsLocationsModule"}
            ))

        # 7. Additional Information
        additional_info: Dict[str, Any] = {}
        if "contactsLocationsModule" in protocol:
            additional_info["contacts_locations"] = protocol["contactsLocationsModule"]
        if "sponsorCollaboratorsModule" in protocol:
            additional_info["sponsor_collaborators"] = protocol["sponsorCollaboratorsModule"]
        if "oversightModule" in protocol:
            additional_info["oversight"] = protocol["oversightModule"]

        return CanonicalProtocol(
            study_id=study_id,
            title=brief_title,
            official_title=official_title,
            study_type=study_type,
            phase=phase,
            overall_status=overall_status,
            conditions=conditions,
            interventions=interventions,
            comparators=[],
            objectives=objectives,
            eligibility=eligibility,
            population=None,
            duration=None,
            procedures=[],
            outcomes=OutcomesInfo(primary=primary_outcomes, secondary=secondary_outcomes),
            risks=[],
            benefits=[],
            source_sections=source_sections,
            additional_information=additional_info
        )

    @staticmethod
    def _split_eligibility_criteria(raw_text: Optional[str]) -> Tuple[List[str], List[str]]:
        if not raw_text:
            return [], []

        inclusion: List[str] = []
        exclusion: List[str] = []

        inc_match = re.search(r"(?i)inclusion\s+criteria\s*:?", raw_text)
        exc_match = re.search(r"(?i)exclusion\s+criteria\s*:?", raw_text)

        if inc_match and exc_match:
            inc_start = inc_match.end()
            exc_start = exc_match.start()
            exc_text_start = exc_match.end()

            inc_block = raw_text[inc_start:exc_start]
            exc_block = raw_text[exc_text_start:]

            inclusion = JSONCanonicalizer._extract_bullet_lines(inc_block)
            exclusion = JSONCanonicalizer._extract_bullet_lines(exc_block)
        elif inc_match:
            inc_block = raw_text[inc_match.end():]
            inclusion = JSONCanonicalizer._extract_bullet_lines(inc_block)
        elif exc_match:
            exc_block = raw_text[exc_match.end():]
            exclusion = JSONCanonicalizer._extract_bullet_lines(exc_block)
        else:
            inclusion = JSONCanonicalizer._extract_bullet_lines(raw_text)

        return inclusion, exclusion

    @staticmethod
    def _extract_bullet_lines(block: str) -> List[str]:
        lines: List[str] = []
        for line in block.split("\n"):
            clean = line.strip()
            if not clean:
                continue
            cleaned = re.sub(r"^(?:[•\-\*\¬\–\—]|\(?\d+[\.\)]|\(?[a-zA-Z][\.\)])\s*", "", clean).strip()
            if cleaned and len(cleaned) > 2:
                lines.append(cleaned)
        return lines

# Global instance
json_canonicalizer = JSONCanonicalizer()
