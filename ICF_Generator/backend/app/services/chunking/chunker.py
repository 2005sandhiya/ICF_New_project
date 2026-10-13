import re
import logging
from typing import List, Dict, Any, Optional
from app.models.canonical_protocol import CanonicalProtocol, CanonicalProtocolResponse
from app.models.study import PageContent
from app.models.chunk import ProtocolChunk, ChunkMetadata, ChunkingResponse

logger = logging.getLogger("icf_generator.chunker")

DEFAULT_TARGET_CHUNK_SIZE = 1000  # Target characters per chunk (~150-200 words)
DEFAULT_CHUNK_OVERLAP = 150        # Overlap characters to preserve context boundaries (~20-25 words)
DEFAULT_MIN_CHUNK_SIZE = 100       # Minimum character threshold to prevent tiny chunks

class ProtocolChunkerService:
    """
    Section-Aware Protocol Chunking Service (Phase 4 Part 1).
    Splits protocol content into bounded, meaningful text chunks with rich traceability metadata.
    """

    def __init__(
        self,
        default_target_size: int = DEFAULT_TARGET_CHUNK_SIZE,
        default_overlap: int = DEFAULT_CHUNK_OVERLAP,
        min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE
    ):
        self.default_target_size = default_target_size
        self.default_overlap = default_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_canonical_protocol(
        self,
        canonical_response: CanonicalProtocolResponse,
        target_chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> ChunkingResponse:
        """
        Generates section-aware chunks from a CanonicalProtocolResponse.
        """
        target_size = target_chunk_size or self.default_target_size
        overlap = chunk_overlap if chunk_overlap is not None else self.default_overlap

        protocol = canonical_response.protocol
        source_filename = canonical_response.source.get("filename", "unknown_file")
        source_type = canonical_response.source.get("type", "unknown")
        study_id = protocol.study_id or source_filename

        raw_chunks: List[ProtocolChunk] = []

        # 1. Study Identification Chunk
        ident_parts = [
            f"Study ID: {protocol.study_id}" if protocol.study_id else "",
            f"Title: {protocol.title}" if protocol.title else "",
            f"Official Title: {protocol.official_title}" if protocol.official_title else "",
            f"Phase: {protocol.phase}" if protocol.phase else "",
            f"Study Type: {protocol.study_type}" if protocol.study_type else "",
            f"Status: {protocol.overall_status}" if protocol.overall_status else ""
        ]
        ident_text = "\n".join(filter(None, ident_parts))
        if ident_text:
            raw_chunks.extend(self._create_section_chunks(
                text=ident_text,
                section="study_identification",
                subsection=None,
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field="protocolSection.identificationModule" if source_type == "json" else None,
                target_size=target_size,
                overlap=overlap
            ))

        # 2. Conditions Chunk
        if protocol.conditions:
            cond_text = "Target Conditions / Indications:\n" + "\n".join(f"- {c}" for c in protocol.conditions)
            raw_chunks.extend(self._create_section_chunks(
                text=cond_text,
                section="conditions",
                subsection=None,
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field="protocolSection.conditionsModule" if source_type == "json" else None,
                target_size=target_size,
                overlap=overlap
            ))

        # 3. Interventions Chunk
        if protocol.interventions:
            inv_lines = []
            for inv in protocol.interventions:
                name = inv.get("name", "Unspecified")
                itype = inv.get("type")
                desc = inv.get("description")
                inv_lines.append(f"- {name}" + (f" ({itype})" if itype else "") + (f": {desc}" if desc else ""))
            inv_text = "Study Interventions / Arms:\n" + "\n".join(inv_lines)
            raw_chunks.extend(self._create_section_chunks(
                text=inv_text,
                section="interventions",
                subsection=None,
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field="protocolSection.armsInterventionsModule" if source_type == "json" else None,
                target_size=target_size,
                overlap=overlap
            ))

        # 4. Objectives Chunks
        if protocol.objectives.primary:
            prim_obj_text = "Primary Study Objectives:\n" + "\n".join(f"- {item}" for item in protocol.objectives.primary)
            raw_chunks.extend(self._create_section_chunks(
                text=prim_obj_text,
                section="objectives",
                subsection="primary",
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field="protocolSection.objectivesModule" if source_type == "json" else None,
                target_size=target_size,
                overlap=overlap
            ))

        if protocol.objectives.secondary:
            sec_obj_text = "Secondary Study Objectives:\n" + "\n".join(f"- {item}" for item in protocol.objectives.secondary)
            raw_chunks.extend(self._create_section_chunks(
                text=sec_obj_text,
                section="objectives",
                subsection="secondary",
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field="protocolSection.objectivesModule" if source_type == "json" else None,
                target_size=target_size,
                overlap=overlap
            ))

        # 5. Eligibility Criteria Chunks
        if protocol.eligibility.inclusion:
            inc_text = "Inclusion Criteria:\n" + "\n".join(f"- {item}" for item in protocol.eligibility.inclusion)
            raw_chunks.extend(self._create_section_chunks(
                text=inc_text,
                section="eligibility",
                subsection="inclusion",
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field="protocolSection.eligibilityModule" if source_type == "json" else None,
                target_size=target_size,
                overlap=overlap
            ))

        if protocol.eligibility.exclusion:
            exc_text = "Exclusion Criteria:\n" + "\n".join(f"- {item}" for item in protocol.eligibility.exclusion)
            raw_chunks.extend(self._create_section_chunks(
                text=exc_text,
                section="eligibility",
                subsection="exclusion",
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field="protocolSection.eligibilityModule" if source_type == "json" else None,
                target_size=target_size,
                overlap=overlap
            ))

        # 6. Outcomes Chunks
        if protocol.outcomes.primary:
            prim_out_text = "Primary Outcomes / Endpoints:\n" + "\n".join(f"- {item}" for item in protocol.outcomes.primary)
            raw_chunks.extend(self._create_section_chunks(
                text=prim_out_text,
                section="outcomes",
                subsection="primary",
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field="protocolSection.outcomesModule" if source_type == "json" else None,
                target_size=target_size,
                overlap=overlap
            ))

        if protocol.outcomes.secondary:
            sec_out_text = "Secondary Outcomes / Endpoints:\n" + "\n".join(f"- {item}" for item in protocol.outcomes.secondary)
            raw_chunks.extend(self._create_section_chunks(
                text=sec_out_text,
                section="outcomes",
                subsection="secondary",
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field="protocolSection.outcomesModule" if source_type == "json" else None,
                target_size=target_size,
                overlap=overlap
            ))

        # 7. Procedures Chunks
        if protocol.procedures:
            proc_text = "Study Procedures & Schedule:\n" + "\n".join(f"- {item}" for item in protocol.procedures)
            raw_chunks.extend(self._create_section_chunks(
                text=proc_text,
                section="procedures",
                subsection=None,
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field="protocolSection.designModule" if source_type == "json" else None,
                target_size=target_size,
                overlap=overlap
            ))

        # 8. Risks Chunks
        if protocol.risks:
            risk_text = "Known Risks & Safety Considerations:\n" + "\n".join(f"- {item}" for item in protocol.risks)
            raw_chunks.extend(self._create_section_chunks(
                text=risk_text,
                section="risks",
                subsection=None,
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field=None,
                target_size=target_size,
                overlap=overlap
            ))

        # 9. Benefits Chunks
        if protocol.benefits:
            benefit_text = "Potential Benefits:\n" + "\n".join(f"- {item}" for item in protocol.benefits)
            raw_chunks.extend(self._create_section_chunks(
                text=benefit_text,
                section="benefits",
                subsection=None,
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                source_field=None,
                target_size=target_size,
                overlap=overlap
            ))

        # 10. Source Traceability Section Chunks (Uncaptured sections)
        for sec in protocol.source_sections:
            if sec.content.strip():
                page_num = sec.source_metadata.get("page") if isinstance(sec.source_metadata, dict) else None
                source_field = sec.source_metadata.get("field_path") if isinstance(sec.source_metadata, dict) else None
                sec_text = f"Section: {sec.heading}\n{sec.content}"
                raw_chunks.extend(self._create_section_chunks(
                    text=sec_text,
                    section=sec.section_name or "general_section",
                    subsection=None,
                    study_id=study_id,
                    source_type=source_type,
                    source_filename=source_filename,
                    page_number=page_num,
                    source_field=source_field,
                    target_size=target_size,
                    overlap=overlap
                ))

        # Final sequence numbering and total chunks count
        total_chunks = len(raw_chunks)
        final_chunks: List[ProtocolChunk] = []

        clean_study_id = re.sub(r"[^\w\-]", "_", study_id)

        for idx, chk in enumerate(raw_chunks):
            seq = idx + 1
            chunk_id = f"{clean_study_id}_{chk.metadata.section}_{seq:03d}"
            
            chk.chunk_id = chunk_id
            chk.metadata.chunk_id = chunk_id
            chk.metadata.chunk_index = seq
            chk.metadata.total_chunks = total_chunks
            final_chunks.append(chk)

        logger.info(f"Generated {total_chunks} chunk(s) for study '{study_id}' (target_size={target_size}, overlap={overlap})")

        return ChunkingResponse(
            status="chunked",
            study_id=study_id,
            source_filename=source_filename,
            source_type=source_type,
            total_chunks=total_chunks,
            target_chunk_size=target_size,
            chunk_overlap=overlap,
            chunks=final_chunks,
            message=f"Successfully generated {total_chunks} protocol chunk(s)."
        )

    def _create_section_chunks(
        self,
        text: str,
        section: str,
        subsection: Optional[str],
        study_id: str,
        source_type: str,
        source_filename: str,
        page_number: Optional[int] = None,
        source_field: Optional[str] = None,
        target_size: int = DEFAULT_TARGET_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP
    ) -> List[ProtocolChunk]:
        if not text or not text.strip():
            return []

        text_str = text.strip()
        chunks: List[ProtocolChunk] = []

        # If text is within target_size (with 10% tolerance), create single chunk
        if len(text_str) <= int(target_size * 1.1):
            meta = ChunkMetadata(
                chunk_id="",  # Populated during final index assignment
                study_id=study_id,
                source_type=source_type,
                source_filename=source_filename,
                section=section,
                subsection=subsection,
                page_number=page_number,
                source_field=source_field,
                chunk_index=0,
                total_chunks=0,
                character_count=len(text_str)
            )
            chunks.append(ProtocolChunk(chunk_id="", text=text_str, metadata=meta))
            return chunks

        # Boundary-aware splitting for long sections
        start = 0
        prev_cut_end = 0
        while start < len(text_str):
            target_end = start + target_size
            cut_end = self._find_safe_cut_point(text_str, target_end)

            if cut_end <= prev_cut_end:
                cut_end = min(len(text_str), prev_cut_end + target_size)

            chunk_text = text_str[start:cut_end].strip()

            if len(chunk_text) >= self.min_chunk_size or not chunks:
                meta = ChunkMetadata(
                    chunk_id="",
                    study_id=study_id,
                    source_type=source_type,
                    source_filename=source_filename,
                    section=section,
                    subsection=subsection,
                    page_number=page_number,
                    source_field=source_field,
                    chunk_index=0,
                    total_chunks=0,
                    character_count=len(chunk_text)
                )
                chunks.append(ProtocolChunk(chunk_id="", text=chunk_text, metadata=meta))

            if cut_end >= len(text_str):
                break

            prev_cut_end = cut_end
            desired_start = max(0, cut_end - overlap)
            next_start = self._find_safe_start_point(text_str, desired_start)

            # Ensure start progresses beyond current start
            if next_start <= start:
                start = cut_end
            else:
                start = next_start

        return chunks

    def _find_safe_cut_point(self, text: str, target_end: int, search_back: int = 150, search_forward: int = 50) -> int:
        """
        Finds a safe cut boundary near target_end preferring sentence > line break > word boundary.
        Ensures words are never cut in the middle.
        """
        if target_end >= len(text):
            return len(text)

        min_search = max(0, target_end - search_back)
        max_search = min(len(text), target_end + search_forward)
        window = text[min_search:max_search]

        # 1. Look for sentence endings (e.g., '. ', '.\n', '?\n', '! ')
        sentence_matches = [m.end() for m in re.finditer(r'(?<=[.!?])\s+', window)]
        if sentence_matches:
            target_offset = target_end - min_search
            best_match = min(sentence_matches, key=lambda pos: abs(pos - target_offset))
            cut_idx = min_search + best_match
            if cut_idx > min_search:
                return cut_idx

        # 2. Look for paragraph / line breaks
        line_matches = [m.end() for m in re.finditer(r'\n+', window)]
        if line_matches:
            target_offset = target_end - min_search
            best_match = min(line_matches, key=lambda pos: abs(pos - target_offset))
            cut_idx = min_search + best_match
            if cut_idx > min_search:
                return cut_idx

        # 3. Fallback to word boundary (space/punctuation) backwards from target_end
        for idx in range(target_end, min_search - 1, -1):
            if text[idx].isspace() or text[idx] in (',', ';', ':', ')', ']', '-'):
                return idx + 1 if text[idx].isspace() else idx

        # 4. If no space backwards, search forward for next space
        for idx in range(target_end, min(len(text), target_end + 100)):
            if text[idx].isspace():
                return idx + 1

        return target_end

    def _find_safe_start_point(self, text: str, target_start: int) -> int:
        """
        Adjusts start point so it doesn't begin in the middle of a word.
        """
        if target_start <= 0 or target_start >= len(text):
            return max(0, target_start)

        # If already at space or char before is space
        if text[target_start].isspace() or text[target_start - 1].isspace():
            while target_start < len(text) and text[target_start].isspace():
                target_start += 1
            return target_start

        # If inside a word, search backwards for space
        for idx in range(target_start, max(0, target_start - 50), -1):
            if text[idx].isspace():
                return idx + 1

        return target_start

# Global singleton instance
protocol_chunker_service = ProtocolChunkerService()
