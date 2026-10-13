import io
import logging
from typing import Tuple, List, Optional
from pypdf import PdfReader
from app.models.study import PageContent
from app.services.document_processing.parsers.base_parser import BaseParser
from app.services.document_processing.text_normalizer import text_normalizer

logger = logging.getLogger("icf_generator.pdf_parser")

class PDFParser(BaseParser):
    """
    Parser for PDF documents using pypdf.
    Extracts text page by page, preserving page numbers and page boundaries.
    """

    def parse(self, filename: str, content: bytes) -> Tuple[str, List[PageContent], Optional[int]]:
        try:
            reader = PdfReader(io.BytesIO(content))
            page_count = len(reader.pages)
            pages: List[PageContent] = []
            full_text_blocks: List[str] = []

            for idx, page in enumerate(reader.pages):
                page_num = idx + 1
                try:
                    raw_page_text = page.extract_text() or ""
                except Exception as pe:
                    logger.warning(f"Error extracting text from page {page_num} in '{filename}': {str(pe)}")
                    raw_page_text = ""

                norm_page_text = text_normalizer.normalize_text(raw_page_text)
                pages.append(PageContent(page_number=page_num, text=norm_page_text))

                if norm_page_text:
                    full_text_blocks.append(f"--- Page {page_num} ---\n{norm_page_text}")

            combined_text = "\n\n".join(full_text_blocks)
            full_text = text_normalizer.normalize_text(combined_text)

            return full_text, pages, page_count

        except Exception as e:
            logger.error(f"Failed to parse PDF document '{filename}': {str(e)}")
            raise ValueError(f"PDF text extraction failed: {str(e)}")
