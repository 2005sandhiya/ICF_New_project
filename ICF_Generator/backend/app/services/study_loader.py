import os
import json
import logging
from typing import List, Dict, Optional, Any
from app.models.study import StudySummary, StudyDetail, InterventionInfo
from app.models.canonical_protocol import CanonicalProtocolResponse
from app.models.chunk import ChunkingResponse, EmbeddingResponse, VectorIndexingResponse
from app.services.canonicalization.canonicalization_engine import canonicalization_engine
from app.services.chunking.chunker import protocol_chunker_service
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store_service


logger = logging.getLogger("icf_generator.study_loader")

# Path to preloaded studies directory
STUDIES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "studies")
)

class StudyLoaderService:
    """
    Service for discovering, parsing, and caching preloaded ClinicalTrials.gov study JSON files.
    Discovers files dynamically inside data/studies/ directory.
    """

    def __init__(self, studies_dir: str = STUDIES_DIR):
        self.studies_dir = studies_dir
        self._studies_cache: Dict[str, Dict[str, Any]] = {}
        self.load_studies()

    def load_studies(self) -> None:
        """
        Scans data/studies/ directory for JSON files and populates internal cache.
        Robust to malformed files - skips unparseable JSON without crashing.
        """
        self._studies_cache.clear()

        if not os.path.exists(self.studies_dir):
            logger.warning(f"Studies directory not found: {self.studies_dir}")
            return

        json_files = [f for f in os.listdir(self.studies_dir) if f.lower().endswith(".json")]
        logger.info(f"Discovered {len(json_files)} JSON file(s) in {self.studies_dir}")

        for filename in json_files:
            filepath = os.path.join(self.studies_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = json.load(f)

                # Handle single object or array of study objects
                studies_list = content if isinstance(content, list) else [content]

                for idx, item in enumerate(studies_list):
                    if not isinstance(item, dict):
                        logger.warning(f"Skipping non-dict study item at index {idx} in {filename}")
                        continue

                    # Extract study_id from identificationModule or generate fallback ID
                    protocol = item.get("protocolSection", {})
                    ident = protocol.get("identificationModule", {})
                    study_id = ident.get("nctId") or item.get("study_id") or f"{filename}_{idx}"

                    self._studies_cache[study_id] = {
                        "study_id": study_id,
                        "raw": item,
                        "source_file": filename
                    }

            except json.JSONDecodeError as jde:
                logger.error(f"Malformed JSON file '{filename}': {str(jde)}. Skipping file.")
            except Exception as e:
                logger.error(f"Error reading study file '{filename}': {str(e)}. Skipping file.")

        logger.info(f"Successfully loaded {len(self._studies_cache)} study record(s) into memory cache.")

    def get_all_summaries(self) -> List[StudySummary]:
        """
        Returns summary listings for all loaded studies.
        """
        summaries: List[StudySummary] = []
        for study_id, entry in self._studies_cache.items():
            try:
                summary = self._parse_summary(study_id, entry["raw"], entry["source_file"])
                summaries.append(summary)
            except Exception as e:
                logger.error(f"Failed to parse summary for study '{study_id}': {str(e)}")

        summaries.sort(key=lambda s: s.study_id)
        return summaries

    def get_study_detail(self, study_id: str) -> Optional[StudyDetail]:
        """
        Returns full detailed representation for a specific study by study_id.
        """
        entry = self._studies_cache.get(study_id)
        if not entry:
            return None

        try:
            return self._parse_detail(study_id, entry["raw"], entry["source_file"])
        except Exception as e:
            logger.error(f"Failed to parse detail for study '{study_id}': {str(e)}")
            return None

    def get_study_as_canonical_protocol(self, study_id: str) -> Optional[CanonicalProtocolResponse]:
        """
        Phase 3 Part 3: Canonicalizes a preloaded study by study_id into CanonicalProtocolResponse.
        """
        entry = self._studies_cache.get(study_id)
        if not entry:
            return None

        return canonicalization_engine.canonicalize_document(
            filename=entry["source_file"],
            file_type="json",
            content=b"",
            raw_json=entry["raw"]
        )

    def get_study_chunks(
        self,
        study_id: str,
        target_chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> Optional[ChunkingResponse]:
        """
        Phase 4 Part 1: Generates section-aware chunks for a preloaded study by study_id.
        """
        canonical_resp = self.get_study_as_canonical_protocol(study_id)
        if not canonical_resp:
            return None

        return protocol_chunker_service.chunk_canonical_protocol(
            canonical_response=canonical_resp,
            target_chunk_size=target_chunk_size,
            chunk_overlap=chunk_overlap
        )

    def get_study_embeddings(
        self,
        study_id: str,
        target_chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        model_name: Optional[str] = None,
        batch_size: Optional[int] = None
    ) -> Optional[EmbeddingResponse]:
        """
        Phase 4 Part 2: Generates section-aware chunks and semantic embeddings for a preloaded study by study_id.
        """
        chunks_res = self.get_study_chunks(
            study_id=study_id,
            target_chunk_size=target_chunk_size,
            chunk_overlap=chunk_overlap
        )
        if not chunks_res:
            return None

        return embedding_service.embed_chunking_response(
            chunk_response=chunks_res,
            model_name=model_name,
            batch_size=batch_size
        )

    def index_study_vectors(
        self,
        study_id: str,
        target_chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        model_name: Optional[str] = None,
        batch_size: Optional[int] = None
    ) -> Optional[VectorIndexingResponse]:
        """
        Phase 4 Part 3: Generates embeddings for a preloaded study and stores them in FAISS vector store.
        """
        embeddings_res = self.get_study_embeddings(
            study_id=study_id,
            target_chunk_size=target_chunk_size,
            chunk_overlap=chunk_overlap,
            model_name=model_name,
            batch_size=batch_size
        )
        if not embeddings_res:
            return None

        return vector_store_service.add_embeddings(embeddings_res)


    def _parse_summary(self, study_id: str, raw: dict, source_file: str) -> StudySummary:
        protocol = raw.get("protocolSection", {})
        ident = protocol.get("identificationModule", {})
        status_mod = protocol.get("statusModule", {})
        design_mod = protocol.get("designModule", {})
        cond_mod = protocol.get("conditionsModule", {})

        brief_title = ident.get("briefTitle") or ident.get("officialTitle") or raw.get("title") or "Untitled Study"
        official_title = ident.get("officialTitle")
        overall_status = status_mod.get("overallStatus") or raw.get("status") or "UNKNOWN"
        conditions = cond_mod.get("conditions") or raw.get("conditions") or []
        study_type = design_mod.get("studyType") or raw.get("study_type") or "UNKNOWN"

        raw_phases = design_mod.get("phases") or raw.get("phase")
        if isinstance(raw_phases, list):
            phases = [str(p) for p in raw_phases]
        elif isinstance(raw_phases, str):
            phases = [raw_phases]
        else:
            phases = []

        enrollment_info = design_mod.get("enrollmentInfo", {})
        enrollment = (
            enrollment_info.get("count") 
            if isinstance(enrollment_info, dict) 
            else raw.get("enrollment")
        )

        return StudySummary(
            study_id=study_id,
            brief_title=brief_title,
            official_title=official_title,
            overall_status=overall_status,
            conditions=conditions,
            study_type=study_type,
            phases=phases,
            enrollment=enrollment,
            source_file=source_file
        )

    def _parse_detail(self, study_id: str, raw: dict, source_file: str) -> StudyDetail:
        summary = self._parse_summary(study_id, raw, source_file)

        protocol = raw.get("protocolSection", {})
        desc_mod = protocol.get("descriptionModule", {})
        arms_mod = protocol.get("armsInterventionsModule", {})
        elig_mod = protocol.get("eligibilityModule", {})

        brief_summary = desc_mod.get("briefSummary") or raw.get("summary")
        detailed_description = desc_mod.get("detailedDescription") or raw.get("description")

        raw_interventions = arms_mod.get("interventions") or raw.get("interventions") or []
        parsed_interventions: List[InterventionInfo] = []
        for item in raw_interventions:
            if isinstance(item, dict):
                parsed_interventions.append(
                    InterventionInfo(
                        name=item.get("name") or "Unspecified Intervention",
                        type=item.get("type"),
                        description=item.get("description")
                    )
                )

        eligibility_criteria = elig_mod.get("eligibilityCriteria") or raw.get("eligibility")
        minimum_age = elig_mod.get("minimumAge")
        maximum_age = elig_mod.get("maximumAge")
        sex = elig_mod.get("sex")
        healthy_volunteers = elig_mod.get("healthyVolunteers")

        return StudyDetail(
            **summary.model_dump(),
            brief_summary=brief_summary,
            detailed_description=detailed_description,
            interventions=parsed_interventions,
            eligibility_criteria=eligibility_criteria,
            minimum_age=minimum_age,
            maximum_age=maximum_age,
            sex=sex,
            healthy_volunteers=healthy_volunteers,
            raw_protocol=raw
        )

# Global singleton instance
study_loader_service = StudyLoaderService()
