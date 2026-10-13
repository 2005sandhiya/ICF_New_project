import io
import docx
import logging
from typing import Tuple, List, Optional
from app.models.study import PageContent
from app.services.document_processing.parsers.base_parser import BaseParser
from app.services.document_processing.text_normalizer import text_normalizer

logger = logging.getLogger("icf_generator.docx_parser")

class DOCXParser(BaseParser):
    """
    Parser for Word DOCX documents using python-docx.
    Extracts paragraphs and table cell contents in sequence.
    """

    def parse(self, filename: str, content: bytes) -> Tuple[str, List[PageContent], Optional[int]]:
        try:
            doc = docx.Document(io.BytesIO(content))
            extracted_blocks: List[str] = []

            # 1. Extract paragraphs
            for p in doc.paragraphs:
                p_text = p.text.strip()
                if p_text:
                    extracted_blocks.append(p_text)

            # 2. Extract table cell contents
            for t_idx, table in enumerate(doc.tables):
                table_rows: List[str] = []
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        table_rows.append(" | ".join(row_cells))
                if table_rows:
                    extracted_blocks.append(f"\n--- Table {t_idx + 1} ---\n" + "\n".join(table_rows))

            combined_raw = "\n\n".join(extracted_blocks)
            full_text = text_normalizer.normalize_text(combined_raw)

            return full_text, [], None

        except Exception as e:
            logger.error(f"Failed to parse DOCX document '{filename}': {str(e)}")
            raise ValueError(f"DOCX text extraction failed: {str(e)}")
