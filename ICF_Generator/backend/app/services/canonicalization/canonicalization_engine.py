import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from app.models.canonical_protocol import CanonicalProtocol, CanonicalProtocolResponse
from app.models.study import PageContent
from app.services.canonicalization.json_canonicalizer import json_canonicalizer
from app.services.canonicalization.text_canonicalizer import text_canonicalizer

logger = logging.getLogger("icf_generator.canonicalization_engine")

class CanonicalizationEngine:
    """
    Main Canonicalization Engine (Phase 3 Part 3).
    Converts extracted document content or preloaded study JSON into a standardized,
    deterministic CanonicalProtocol object without calling external LLMs.
    """

    def canonicalize_document(
        self,
        filename: str,
        file_type: str,
        content: bytes,
        full_text: str = "",
        pages: Optional[List[PageContent]] = None,
        raw_json: Optional[Dict[str, Any]] = None
    ) -> CanonicalProtocolResponse:
        fmt = file_type.lower().lstrip(".")
        pages_list = pages or []

        logger.info(f"Canonicalizing document '{filename}' of type '{fmt}'")

        if fmt == "json":
            json_dict: Dict[str, Any]
            if raw_json is not None:
                json_dict = raw_json
            else:
                try:
                    parsed = json.loads(content.decode("utf-8"))
                    json_dict = parsed if isinstance(parsed, dict) else {}
                except Exception as e:
                    logger.error(f"Invalid JSON content in canonicalizer: {str(e)}")
                    json_dict = {}
            canonical_protocol = json_canonicalizer.canonicalize(json_dict, filename)
        else:
            canonical_protocol = text_canonicalizer.canonicalize(filename, fmt, full_text, pages_list)

        # Count extracted vs missing fields
        extracted_count, missing_count = self._calculate_field_counts(canonical_protocol)

        logger.info(f"Canonicalization complete for '{filename}': {extracted_count} fields extracted, {missing_count} fields missing/null.")

        return CanonicalProtocolResponse(
            status="canonicalized",
            source={"filename": filename, "type": fmt},
            protocol=canonical_protocol,
            extracted_fields_count=extracted_count,
            missing_fields_count=missing_count,
            message="Canonical protocol extraction successful."
        )

    def _calculate_field_counts(self, protocol: CanonicalProtocol) -> Tuple[int, int]:
        extracted = 0
        missing = 0

        field_values = [
            protocol.study_id,
            protocol.title,
            protocol.official_title,
            protocol.study_type,
            protocol.phase,
            protocol.overall_status,
            protocol.conditions,
            protocol.interventions,
            protocol.comparators,
            protocol.objectives.primary,
            protocol.objectives.secondary,
            protocol.eligibility.inclusion,
            protocol.eligibility.exclusion,
            protocol.population,
            protocol.duration,
            protocol.procedures,
            protocol.outcomes.primary,
            protocol.outcomes.secondary,
            protocol.risks,
            protocol.benefits
        ]

        for val in field_values:
            if val is not None and val != [] and val != "":
                extracted += 1
            else:
                missing += 1

        return extracted, missing

# Global singleton instance
canonicalization_engine = CanonicalizationEngine()
