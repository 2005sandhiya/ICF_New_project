import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from app.models.study import PageContent
from app.models.canonical_protocol import (
    CanonicalProtocol, 
    ObjectivesInfo, 
    EligibilityInfo, 
    OutcomesInfo, 
    ProtocolSectionItem
)
from app.services.canonicalization.section_detector import section_detector

logger = logging.getLogger("icf_generator.text_canonicalizer")

class TextCanonicalizer:
    """
    Deterministic text-to-canonical protocol extractor (Phase 3 Part 3).
    Extracts sections and structured clinical fields from unstructured text (PDF/DOCX/TXT)
    without using generative LLMs. Preserves page-level source traceability for PDFs.
    """

    @staticmethod
    def canonicalize(
        filename: str, 
        file_type: str, 
        full_text: str, 
        pages: List[PageContent]
    ) -> CanonicalProtocol:
        if not full_text or not full_text.strip():
            return CanonicalProtocol()

        # 1. Regex Header Extraction (Title, Study ID, Phase, Type)
        study_id = TextCanonicalizer._extract_regex(
            full_text, r"(?i)\b(?:NCT\d{8}|protocol\s*(?:id|no|number)\s*[:\-]\s*([a-zA-Z0-9\-_]+))"
        )
        title = TextCanonicalizer._extract_regex(
            full_text, r"(?i)\b(?:study|protocol)\s+title\s*[:\-]\s*(.+)"
        )
        phase = TextCanonicalizer._extract_regex(
            full_text, r"(?i)\bphase\s*[:\-]?\s*(phase\s*[1-4I|V|X]+|1/2|2/3|0|early\s*phase\s*1)\b"
        )
        study_type = TextCanonicalizer._extract_regex(
            full_text, r"(?i)\b(?:study\s+type|study\s+design)\s*[:\-]\s*(interventional|observational)\b"
        )

        # 2. Section Segmentation
        raw_sections = section_detector.split_into_sections(full_text)
        source_sections: List[ProtocolSectionItem] = []

        inclusion_list: List[str] = []
        exclusion_list: List[str] = []
        primary_objs: List[str] = []
        secondary_objs: List[str] = []
        primary_outs: List[str] = []
        secondary_outs: List[str] = []
        procedures_list: List[str] = []
        risks_list: List[str] = []
        benefits_list: List[str] = []

        for category, heading, content in raw_sections:
            if not content.strip():
                continue

            # Determine page location for PDF source traceability
            page_num = TextCanonicalizer._find_page_number(heading, content, pages)
            source_meta: Dict[str, Any] = {"type": file_type, "heading": heading}
            if page_num:
                source_meta["page"] = page_num
                source_meta["location"] = f"Page {page_num}"

            # Store section block
            source_sections.append(ProtocolSectionItem(
                section_name=category,
                heading=heading,
                content=content,
                source_metadata=source_meta
            ))

            # Categorize section content into canonical fields
            points = section_detector.extract_bullet_points(content)

            if category == "inclusion":
                inclusion_list.extend(points)
            elif category == "exclusion":
                exclusion_list.extend(points)
            elif category == "eligibility":
                inc, exc = TextCanonicalizer._split_text_eligibility(content)
                inclusion_list.extend(inc)
                exclusion_list.extend(exc)
            elif category == "primary_objective":
                primary_objs.extend(points if points else [content])
            elif category == "secondary_objective":
                secondary_objs.extend(points if points else [content])
            elif category == "objectives":
                primary_objs.extend(points if points else [content])
            elif category == "primary_outcome":
                primary_outs.extend(points if points else [content])
            elif category == "secondary_outcome":
                secondary_outs.extend(points if points else [content])
            elif category == "outcomes":
                primary_outs.extend(points if points else [content])
            elif category == "procedures":
                procedures_list.extend(points if points else [content])
            elif category == "risks":
                risks_list.extend(points if points else [content])
            elif category == "benefits":
                benefits_list.extend(points if points else [content])

        eligibility = EligibilityInfo(
            inclusion=inclusion_list,
            exclusion=exclusion_list,
            raw_text=full_text if not (inclusion_list or exclusion_list) else None
        )

        return CanonicalProtocol(
            study_id=study_id,
            title=title,
            official_title=None,
            study_type=study_type,
            phase=phase,
            overall_status=None,
            conditions=[],
            interventions=[],
            comparators=[],
            objectives=ObjectivesInfo(primary=primary_objs, secondary=secondary_objs),
            eligibility=eligibility,
            population=None,
            duration=None,
            procedures=procedures_list,
            outcomes=OutcomesInfo(primary=primary_outs, secondary=secondary_outs),
            risks=risks_list,
            benefits=benefits_list,
            source_sections=source_sections,
            additional_information={}
        )

    @staticmethod
    def _extract_regex(text: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, text)
        if match:
            # Return group 1 if available, else group 0
            if match.groups() and match.group(1):
                return match.group(1).strip()
            return match.group(0).strip()
        return None

    @staticmethod
    def _find_page_number(heading: str, content: str, pages: List[PageContent]) -> Optional[int]:
        if not pages:
            return None
        # Check which page contains heading or snippet
        snippet = heading[:30] if len(heading) > 30 else heading
        for page in pages:
            if snippet and snippet in page.text:
                return page.page_number
        return None

    @staticmethod
    def _split_text_eligibility(text: str) -> Tuple[List[str], List[str]]:
        inc_match = re.search(r"(?i)inclusion\s+criteria\s*:?", text)
        exc_match = re.search(r"(?i)exclusion\s+criteria\s*:?", text)

        if inc_match and exc_match:
            inc_block = text[inc_match.end():exc_match.start()]
            exc_block = text[exc_match.end():]
            return section_detector.extract_bullet_points(inc_block), section_detector.extract_bullet_points(exc_block)
        elif inc_match:
            return section_detector.extract_bullet_points(text[inc_match.end():]), []
        elif exc_match:
            return [], section_detector.extract_bullet_points(text[exc_match.end():])
        else:
            return section_detector.extract_bullet_points(text), []

# Global instance
text_canonicalizer = TextCanonicalizer()
