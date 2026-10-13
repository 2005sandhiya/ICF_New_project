import logging
from typing import List, Optional, Set

from app.models.rag import (
    RAGRetrieveRequest,
    RAGEvidenceItem,
    RAGSourceMetadata,
    RAGContextResponse
)
from app.services.query_processor import query_processor
from app.services.search_service import search_service

logger = logging.getLogger("icf_generator.context_assembler")

class ContextAssembler:
    """
    Phase 5 Part 1: RAG Context Assembly Service.
    
    Retrieves relevant protocol evidence chunks using the existing FAISS SimilaritySearchService,
    applies evidence filtering (deduplication, empty text removal, study_id safety, minimum score thresholding),
    and packages the grounded evidence into a structured context package for downstream LLM generation.
    """

    def assemble_context(self, request: RAGRetrieveRequest) -> RAGContextResponse:
        """
        Executes end-to-end RAG retrieval and context assembly for an information requirement.
        
        Args:
            request: RAGRetrieveRequest containing query, target study_id, top_k, threshold, etc.
            
        Returns:
            RAGContextResponse containing assembled grounded evidence and source traceability metadata.
        """
        # Step 1: Process and normalize natural language query
        original_query, processed_query = query_processor.process_query(request.query)

        # Step 2: Retrieve relevant candidate chunks using existing SimilaritySearchService
        search_res = search_service.search_vector_store(
            query=processed_query,
            top_k=request.top_k,
            study_id=request.study_id,
            enable_diversity=request.enable_diversity,
            diversity_penalty=request.diversity_penalty
        )

        # Step 3: Evidence Filtering (Deduplication, Empty text removal, Study consistency)
        seen_chunk_ids: Set[str] = set()
        filtered_items = []

        for item in search_res.results:
            # Check empty text
            clean_text = item.text.strip() if item.text else ""
            if not clean_text:
                continue

            # Check duplicate chunk_id
            if item.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(item.chunk_id)

            # Check study_id consistency if requested
            if request.study_id and item.study_id and item.study_id != request.study_id:
                continue

            filtered_items.append(item)

        # Step 4: Minimum Score Thresholding & Fallback Handling
        retrieval_status = "success"
        warning_message: Optional[str] = None

        if request.min_score_threshold > 0.0 and filtered_items:
            # Check items meeting threshold using similarity_score or reranking_score
            threshold_items = [
                it for it in filtered_items 
                if (it.reranking_score if it.reranking_score is not None else it.similarity_score) >= request.min_score_threshold
            ]
            
            if not threshold_items:
                # Fallback: All retrieved results fell below configured threshold
                retrieval_status = "fallback_below_threshold"
                top_score = round(filtered_items[0].similarity_score, 4)
                warning_message = (
                    f"All retrieved candidates fell below minimum similarity threshold {request.min_score_threshold:.2f}. "
                    f"Returning best available candidate(s) (highest similarity: {top_score})."
                )
                # Keep original filtered items so we return best available instead of empty set
            else:
                filtered_items = threshold_items

        if not filtered_items:
            retrieval_status = "empty"
            warning_message = "No relevant protocol evidence chunks were found for the query."

        # Step 5: Assemble RAG Evidence Items with Complete Source Traceability
        evidence_list: List[RAGEvidenceItem] = []
        for rank_idx, item in enumerate(filtered_items, 1):
            source_meta = RAGSourceMetadata(
                filename=item.source_filename,
                page_number=item.page_number,
                source_reference=item.source_reference,
                source_field=item.source_field,
                study_id=item.study_id,
                chunk_index=item.chunk_index
            )

            evidence_item = RAGEvidenceItem(
                rank=rank_idx,
                chunk_id=item.chunk_id,
                section=item.section,
                subsection=item.subsection,
                text=item.text,
                similarity_score=item.similarity_score,
                reranking_score=item.reranking_score,
                source=source_meta
            )
            evidence_list.append(evidence_item)

        logger.info(
            f"Context assembly complete for query '{original_query}': "
            f"{len(evidence_list)} evidence item(s) packaged (status: {retrieval_status})."
        )

        return RAGContextResponse(
            original_query=original_query,
            processed_query=processed_query,
            study_id=request.study_id,
            evidence=evidence_list,
            evidence_count=len(evidence_list),
            retrieval_status=retrieval_status,
            warning_message=warning_message
        )

context_assembler = ContextAssembler()
