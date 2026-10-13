import re
from typing import List, Dict, Tuple, Optional

# Mapping of section category keys to regex patterns for common heading variations
SECTION_PATTERNS: Dict[str, str] = {
    "inclusion": r"(?i)^(?:[0-9\.\s]*)(?:inclusion\s+criteria|inclusive\s+criteria|subject\s+inclusion\s+criteria)\b",
    "exclusion": r"(?i)^(?:[0-9\.\s]*)(?:exclusion\s+criteria|exclusive\s+criteria|subject\s+exclusion\s+criteria)\b",
    "eligibility": r"(?i)^(?:[0-9\.\s]*)(?:eligibility(?:\s+criteria)?|inclusion\s+and\s+exclusion\s+criteria|criteria\s+for\s+eligibility)\b",
    "primary_objective": r"(?i)^(?:[0-9\.\s]*)(?:primary\s+objectives?|primary\s+purpose|primary\s+aims?)\b",
    "secondary_objective": r"(?i)^(?:[0-9\.\s]*)(?:secondary\s+objectives?|secondary\s+aims?)\b",
    "objectives": r"(?i)^(?:[0-9\.\s]*)(?:study\s+objectives?|objectives?|purpose(?:\s+of\s+the\s+study)?|study\s+purpose)\b",
    "primary_outcome": r"(?i)^(?:[0-9\.\s]*)(?:primary\s+(?:endpoint|outcome|efficacy\s+endpoint)s?)\b",
    "secondary_outcome": r"(?i)^(?:[0-9\.\s]*)(?:secondary\s+(?:endpoint|outcome)s?)\b",
    "outcomes": r"(?i)^(?:[0-9\.\s]*)(?:study\s+endpoints?|outcomes?|endpoints?|primary\s+and\s+secondary\s+endpoints?)\b",
    "procedures": r"(?i)^(?:[0-9\.\s]*)(?:study\s+procedures?|procedures?|schedule\s+of\s+activities|study\s+visits?|study\s+design\s+and\s+procedures)\b",
    "risks": r"(?i)^(?:[0-9\.\s]*)(?:risks(?:\s+and\s+discomforts)?|discomforts|safety\s+considerations|adverse\s+events|potential\s+risks)\b",
    "benefits": r"(?i)^(?:[0-9\.\s]*)(?:potential\s+benefits?|benefits?|direct\s+benefits)\b"
}

class SectionDetector:
    """
    Deterministic heading matching and section segmenter.
    Uses regex pattern matching to identify clinical protocol section boundaries.
    """

    @staticmethod
    def identify_section_category(heading: str) -> Optional[str]:
        """
        Maps a heading line to a canonical section category.
        """
        clean_heading = heading.strip()
        for category, pattern in SECTION_PATTERNS.items():
            if re.match(pattern, clean_heading):
                return category
        return None

    @staticmethod
    def split_into_sections(full_text: str) -> List[Tuple[str, str, str]]:
        """
        Splits full document text into (section_category, heading_text, content_text) tuples.
        """
        if not full_text:
            return []

        lines = full_text.split("\n")
        sections: List[Tuple[str, str, str]] = []
        
        current_category = "general"
        current_heading = "General Protocol Text"
        current_content_lines: List[str] = []

        for line in lines:
            line_str = line.strip()
            # Check if line looks like a section heading
            if len(line_str) > 0 and len(line_str) < 100:
                matched_category = SectionDetector.identify_section_category(line_str)
                if matched_category:
                    # Save previous section if it has content
                    if current_content_lines:
                        sections.append((
                            current_category, 
                            current_heading, 
                            "\n".join(current_content_lines).strip()
                        ))
                    current_category = matched_category
                    current_heading = line_str
                    current_content_lines = []
                    continue

            current_content_lines.append(line)

        if current_content_lines:
            sections.append((
                current_category, 
                current_heading, 
                "\n".join(current_content_lines).strip()
            ))

        return sections

    @staticmethod
    def extract_bullet_points(text_block: str) -> List[str]:
        """
        Extracts bulleted or numbered items from a text block.
        """
        if not text_block:
            return []

        points: List[str] = []
        lines = text_block.split("\n")
        
        for line in lines:
            clean = line.strip()
            if not clean:
                continue
            # Strip bullet prefixes e.g. '•', '-', '*', '1.', 'a)'
            cleaned_item = re.sub(r"^(?:[•\-\*\¬\–\—]|\(?\d+[\.\)]|\(?[a-zA-Z][\.\)])\s*", "", clean).strip()
            if cleaned_item:
                points.append(cleaned_item)

        return points

# Global singleton instance
section_detector = SectionDetector()
