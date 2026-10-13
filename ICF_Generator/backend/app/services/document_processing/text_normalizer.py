import re

class TextNormalizer:
    """
    Utility service for basic text normalization (Phase 3 Part 2).
    Standardizes line endings, collapses excessive blank lines, and trims whitespace
    without altering clinical terms, headings, or content meaning.
    """

    @staticmethod
    def normalize_text(raw_text: str) -> str:
        if not raw_text:
            return ""

        # 1. Standardize line endings and special control chars
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\xa0", " ")  # Non-breaking space
        text = text.replace("\v", "\n").replace("\f", "\n")

        # 2. Trim trailing whitespace on each line
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)

        # 3. Collapse 3 or more consecutive newlines into double newlines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 4. Final trim
        return text.strip()

# Global singleton instance
text_normalizer = TextNormalizer()
