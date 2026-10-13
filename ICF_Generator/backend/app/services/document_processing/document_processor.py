import logging
from typing import Dict, Optional
from app.models.study import ExtractedTextResponse, PageContent
from app.services.document_processing.parsers.base_parser import BaseParser
from app.services.document_processing.parsers.pdf_parser import PDFParser
from app.services.document_processing.parsers.docx_parser import DOCXParser
from app.services.document_processing.parsers.txt_parser import TXTParser
from app.services.document_processing.parsers.json_parser import JSONParser
from app.services.metadata_extractor import format_file_size_display

logger = logging.getLogger("icf_generator.document_processor")

class DocumentProcessorService:
    """
    Modular Document Processing Service (Phase 3 Part 2).
    Orchestrates format-specific parsers for PDF, DOCX, TXT, and JSON files,
    producing clean normalized text representations and page-level PDF blocks.
    """

    def __init__(self):
        self._parsers: Dict[str, BaseParser] = {
            "pdf": PDFParser(),
            "docx": DOCXParser(),
            "txt": TXTParser(),
            "json": JSONParser()
        }

    def process_document(
        self,
        filename: str,
        content: bytes,
        file_type: str,
        storage_id: Optional[str] = None,
        provided_page_count: Optional[int] = None
    ) -> ExtractedTextResponse:
        """
        Processes validated protocol document content and extracts clean text representation.
        """
        fmt = file_type.lower().lstrip(".")
        parser = self._parsers.get(fmt)

        if not parser:
            raise ValueError(f"No document parser available for type '{fmt}'.")

        logger.info(f"Processing document '{filename}' of type '{fmt}' ({len(content)} bytes)")
        size_display = format_file_size_display(len(content))

        # Run format-specific parser
        full_text, pages, page_count = parser.parse(filename, content)
        effective_page_count = page_count if page_count is not None else provided_page_count

        # Check if text was successfully extracted
        if not full_text or not full_text.strip():
            logger.warning(f"Document '{filename}' returned no extractable text.")
            return ExtractedTextResponse(
                status="no_extractable_text",
                filename=filename,
                document_type=fmt,
                file_size_display=size_display,
                page_count=effective_page_count,
                full_text="",
                text_preview="",
                character_count=0,
                word_count=0,
                pages=pages,
                storage_id=storage_id,
                message="Document contains no extractable text (scanned or image-only PDF)."
            )

        # Successful text extraction
        char_count = len(full_text)
        word_count = len(full_text.split())
        preview_text = full_text[:2000]

        logger.info(f"Text extraction complete for '{filename}': {char_count} chars, {word_count} words, {len(pages)} pages.")

        return ExtractedTextResponse(
            status="processed",
            filename=filename,
            document_type=fmt,
            file_size_display=size_display,
            page_count=effective_page_count,
            full_text=full_text,
            text_preview=preview_text,
            character_count=char_count,
            word_count=word_count,
            pages=pages,
            storage_id=storage_id,
            message="Text extraction successful."
        )

# Global singleton instance
document_processor_service = DocumentProcessorService()
