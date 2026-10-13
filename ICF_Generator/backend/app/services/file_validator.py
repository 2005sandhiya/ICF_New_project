import os
import io
import json
import zipfile
import logging
from typing import Tuple, Optional
from pypdf import PdfReader

logger = logging.getLogger("icf_generator.file_validator")

# Default configuration parameters
DEFAULT_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".json"}

class FileValidator:
    """
    Backend service for protocol file validation (Phase 3 Part 1).
    Validates file extension, filename safety, empty status, size limits, and format integrity.
    """

    def __init__(self, max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES):
        self.max_file_size_bytes = max_file_size_bytes

    def validate_file(self, original_filename: str, content: bytes) -> Tuple[str, str, Optional[int]]:
        """
        Executes complete validation pipeline.
        Returns Tuple of (sanitized_filename, detected_file_type, page_count_or_None).
        Raises ValueError with clear error message if validation fails.
        """
        # 1. Filename & Extension Validation
        sanitized_filename, ext = self._validate_filename_and_extension(original_filename)

        # 2. File Size & Empty Check
        self._validate_file_size(content)

        # 3. Format Specific Integrity Check
        page_count = self._validate_format_integrity(ext, content)

        file_type = ext.lstrip(".")
        logger.info(f"Validation successful for '{sanitized_filename}' ({file_type}, {len(content)} bytes, pages={page_count})")

        return sanitized_filename, file_type, page_count

    def _validate_filename_and_extension(self, filename: str) -> Tuple[str, str]:
        if not filename or not filename.strip():
            raise ValueError("Filename cannot be empty.")

        # Sanitize against path traversal attacks
        safe_basename = os.path.basename(filename.strip())
        if not safe_basename or safe_basename in {".", ".."}:
            raise ValueError("Invalid filename.")

        ext = os.path.splitext(safe_basename)[1].lower()
        if not ext or ext not in ALLOWED_EXTENSIONS:
            allowed_str = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ValueError(f"Unsupported file extension '{ext}'. Allowed extensions: {allowed_str}")

        return safe_basename, ext

    def _validate_file_size(self, content: bytes) -> None:
        if content is None or len(content) == 0:
            raise ValueError("Uploaded file is empty (0 bytes).")

        if len(content) > self.max_file_size_bytes:
            max_mb = self.max_file_size_bytes / (1024 * 1024)
            raise ValueError(f"File size exceeds maximum limit of {max_mb:.0f} MB.")

    def _validate_format_integrity(self, ext: str, content: bytes) -> Optional[int]:
        if ext == ".pdf":
            return self._validate_pdf_integrity(content)
        elif ext == ".docx":
            self._validate_docx_integrity(content)
            return None
        elif ext == ".json":
            self._validate_json_integrity(content)
            return None
        elif ext == ".txt":
            self._validate_txt_integrity(content)
            return None
        return None

    def _validate_pdf_integrity(self, content: bytes) -> int:
        if not content.startswith(b"%PDF-"):
            raise ValueError("File content is malformed or unreadable as a PDF document (missing PDF magic header).")

        try:
            reader = PdfReader(io.BytesIO(content))
            page_count = len(reader.pages)
            if page_count < 0:
                raise ValueError("Invalid page count.")
            return page_count
        except Exception as e:
            logger.error(f"PDF integrity check failed: {str(e)}")
            raise ValueError("File content is malformed or unreadable as a PDF document.")

    def _validate_docx_integrity(self, content: bytes) -> None:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                namelist = zf.namelist()
                if "word/document.xml" not in namelist:
                    raise ValueError("Missing word/document.xml structure.")
        except Exception as e:
            logger.error(f"DOCX integrity check failed: {str(e)}")
            raise ValueError("File content is malformed or unreadable as a DOCX document.")

    def _validate_json_integrity(self, content: bytes) -> None:
        try:
            decoded = content.decode("utf-8")
            data = json.loads(decoded)
            if not isinstance(data, (dict, list)):
                raise ValueError("JSON root must be an object or array.")
        except Exception as e:
            logger.error(f"JSON integrity check failed: {str(e)}")
            raise ValueError("File content is malformed or unreadable as a JSON document.")

    def _validate_txt_integrity(self, content: bytes) -> None:
        try:
            # Try decoding as UTF-8 or UTF-16
            decoded = None
            for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
                try:
                    decoded = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if decoded is None:
                raise ValueError("Binary encoding unreadable.")

            # Check for binary null bytes
            if "\x00" in decoded[:1024]:
                raise ValueError("Contains binary null bytes.")

        except Exception as e:
            logger.error(f"TXT integrity check failed: {str(e)}")
            raise ValueError("File content is malformed or unreadable as a plain text document.")

# Global singleton instance
file_validator_service = FileValidator()
