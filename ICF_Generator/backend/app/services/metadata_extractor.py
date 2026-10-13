from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.models.study import ProtocolMetadataResponse

def format_file_size_display(bytes_count: int) -> str:
    """
    Formats byte count into human-readable display string e.g. '120.6 KB', '1.5 MB'.
    """
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.1f} GB"

class MetadataExtractor:
    """
    Backend service for basic metadata extraction (Phase 3 Part 1).
    Extracts filename, format, size in bytes/display, page count, storage ID, and timestamp.
    """

    def extract_metadata(
        self,
        sanitized_filename: str,
        file_type: str,
        content: bytes,
        storage_id: str,
        page_count: Optional[int] = None
    ) -> ProtocolMetadataResponse:
        """
        Constructs a structured ProtocolMetadataResponse object.
        """
        size_bytes = len(content) if content else 0
        size_display = format_file_size_display(size_bytes)
        timestamp = datetime.now(timezone.utc).isoformat()

        return ProtocolMetadataResponse(
            valid=True,
            filename=sanitized_filename,
            file_type=file_type,
            file_size_bytes=size_bytes,
            file_size_display=size_display,
            page_count=page_count,
            uploaded_at=timestamp,
            storage_id=storage_id,
            status="validated",
            message="File validation successful"
        )

# Global singleton instance
metadata_extractor_service = MetadataExtractor()
