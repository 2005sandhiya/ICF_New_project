import logging
from typing import Tuple, List, Optional
from app.models.study import PageContent
from app.services.document_processing.parsers.base_parser import BaseParser
from app.services.document_processing.text_normalizer import text_normalizer

logger = logging.getLogger("icf_generator.txt_parser")

class TXTParser(BaseParser):
    """
    Parser for plain text documents.
    Handles UTF-8, UTF-8-SIG, and Latin-1 text encodings safely.
    """

    def parse(self, filename: str, content: bytes) -> Tuple[str, List[PageContent], Optional[int]]:
        raw_text = None
        for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                raw_text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if raw_text is None:
            raise ValueError(f"Failed to decode text document '{filename}'. Unrecognized text encoding.")

        full_text = text_normalizer.normalize_text(raw_text)
        return full_text, [], None
