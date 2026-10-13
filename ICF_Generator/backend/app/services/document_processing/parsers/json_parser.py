import json
import logging
from typing import Tuple, List, Optional
from app.models.study import PageContent
from app.services.document_processing.parsers.base_parser import BaseParser
from app.services.document_processing.text_normalizer import text_normalizer

logger = logging.getLogger("icf_generator.json_parser")

class JSONParser(BaseParser):
    """
    Parser for JSON protocol documents (ClinicalTrials.gov JSON and general protocol JSON).
    Preserves structured data and generates readable normalized text representation.
    """

    def parse(self, filename: str, content: bytes) -> Tuple[str, List[PageContent], Optional[int]]:
        try:
            data = json.loads(content.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to parse JSON content in '{filename}': {str(e)}")
            raise ValueError(f"Invalid JSON document: {str(e)}")

        formatted_blocks: List[str] = []

        # Check if single item or list of objects
        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict):
                raw_obj = data[0]
            else:
                raw_obj = {}
        elif isinstance(data, dict):
            raw_obj = data
        else:
            raise ValueError("Root JSON element must be an object or list.")

        # Extract ClinicalTrials.gov modules if present
        protocol = raw_obj.get("protocolSection", {})
        if protocol:
            ident = protocol.get("identificationModule", {})
            desc = protocol.get("descriptionModule", {})
            elig = protocol.get("eligibilityModule", {})
            arms = protocol.get("armsInterventionsModule", {})

            if ident.get("nctId"):
                formatted_blocks.append(f"Study ID: {ident.get('nctId')}")
            if ident.get("briefTitle"):
                formatted_blocks.append(f"Title: {ident.get('briefTitle')}")
            if desc.get("briefSummary"):
                formatted_blocks.append(f"\n--- Brief Summary ---\n{desc.get('briefSummary')}")
            if desc.get("detailedDescription"):
                formatted_blocks.append(f"\n--- Detailed Description ---\n{desc.get('detailedDescription')}")
            if elig.get("eligibilityCriteria"):
                formatted_blocks.append(f"\n--- Eligibility Criteria ---\n{elig.get('eligibilityCriteria')}")
            if arms.get("interventions"):
                formatted_blocks.append(f"\n--- Interventions ---\n{json.dumps(arms.get('interventions'), indent=2)}")

        # Fallback dump for unparsed fields / general protocol JSON
        raw_json_str = json.dumps(data, indent=2)
        if not formatted_blocks:
            formatted_blocks.append(raw_json_str)
        else:
            formatted_blocks.append(f"\n--- Raw Protocol JSON Data ---\n{raw_json_str}")

        combined_text = "\n\n".join(formatted_blocks)
        full_text = text_normalizer.normalize_text(combined_text)

        return full_text, [], None
