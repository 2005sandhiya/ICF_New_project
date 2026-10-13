import os
import uuid
import logging
from app.models.study import ProtocolMetadataResponse
from app.services.file_validator import file_validator_service
from app.services.metadata_extractor import metadata_extractor_service

logger = logging.getLogger("icf_generator.upload_service")

# Path to uploads directory
UPLOADS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "uploads")
)

class UploadService:
    """
    Service for validating, saving, and extracting metadata from uploaded protocol documents (Phase 3 Part 1).
    """

    def __init__(self, uploads_dir: str = UPLOADS_DIR):
        self.uploads_dir = uploads_dir
        os.makedirs(self.uploads_dir, exist_ok=True)

    def process_protocol_upload(self, original_filename: str, content: bytes) -> ProtocolMetadataResponse:
        """
        Executes file validation, safe storage, and metadata extraction pipeline.
        """
        # 1. Validation (extension, size, empty check, format integrity, page count)
        sanitized_filename, file_type, page_count = file_validator_service.validate_file(
            original_filename, content
        )

        # 2. Safe local storage
        unique_prefix = str(uuid.uuid4())[:8]
        storage_id = f"{unique_prefix}_{sanitized_filename}"
        destination_path = os.path.join(self.uploads_dir, storage_id)

        # Security check: ensure path remains within UPLOADS_DIR
        if not os.path.abspath(destination_path).startswith(self.uploads_dir):
            raise ValueError("Security violation: Invalid storage path.")

        with open(destination_path, "wb") as f:
            f.write(content)

        logger.info(f"Saved uploaded file '{sanitized_filename}' ({len(content)} bytes) -> {storage_id}")

        # 3. Metadata Extraction
        metadata = metadata_extractor_service.extract_metadata(
            sanitized_filename=sanitized_filename,
            file_type=file_type,
            content=content,
            storage_id=storage_id,
            page_count=page_count
        )

        return metadata

# Global singleton instance
upload_service = UploadService()
