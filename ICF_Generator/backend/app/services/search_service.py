import logging
from typing import List, Optional
import numpy as np

from app.models.chunk import (
    SimilaritySearchResultItem,
    SimilaritySearchRequest,
    SimilaritySearchResponse
)
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store_service

logger = logging.getLogger("icf_generator.search_service")

class SearchService:
    """
    Phase 4 Part 4: Semantic Similarity Search Service.
    
    Generates L2-normalized query vector using existing EmbeddingService (all-MiniLM-L6-v2),
    queries the local FAISS IndexFlatIP vector index, ranks matches by inner product (cosine similarity),
    and maps FAISS vector IDs back to 100% complete chunk metadata for source traceability.
    """

    def __init__(self):
        pass

    def search_vector_store(
        self,
        query: str,
        top_k: int = 5,
        study_id: Optional[str] = None,
        model_name: Optional[str] = None,
        enable_diversity: bool = True,
        diversity_penalty: float = 0.06
    ) -> SimilaritySearchResponse:

        """
        Executes semantic similarity search over the FAISS vector database.
        
        Args:
            query: Natural language query string.
            top_k: Number of top matching chunks to retrieve (default: 5).
            study_id: Optional filter for study identifier.
            model_name: Optional override for embedding model.
            
        Returns:
            SimilaritySearchResponse with ranked matching results and metadata traceability.
        """
        clean_query = query.strip() if query else ""
        if not clean_query:
            raise ValueError("Query string cannot be empty.")

        total_vectors = vector_store_service.get_total_vectors()
        if total_vectors == 0:
            vector_store_service.load_vector_store()
            total_vectors = vector_store_service.get_total_vectors()

        if total_vectors == 0:
            raise ValueError("Vector store is empty. Please index a protocol document before performing similarity search.")

        if top_k <= 0:
            raise ValueError("top_k must be a positive integer greater than 0.")

        target_model_name = model_name or embedding_service.default_model_name
        model = embedding_service.get_model(target_model_name)
        expected_dim = embedding_service.get_embedding_dimension(target_model_name)

        logger.info(f"Encoding query string '{clean_query[:50]}...' using model '{target_model_name}' (normalize_embeddings=True)...")

        try:
            # Batch encode query string with normalize_embeddings=True matching chunk embeddings
            raw_query_vector = model.encode(
                [clean_query],
                batch_size=1,
                normalize_embeddings=True,
                show_progress_bar=False
            )
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {str(e)}")
            raise RuntimeError(f"Query embedding generation failed: {str(e)}")

        np_query_vec = np.array(raw_query_vector, dtype=np.float32)

        # Validate vector dimension matches index dimension (384)
        if np_query_vec.shape[1] != expected_dim:
            raise ValueError(f"Query vector dimension ({np_query_vec.shape[1]}) does not match expected model dimension ({expected_dim}).")

        index = vector_store_service._index
        if index is None:
            raise ValueError("FAISS index is not initialized.")

        if index.d != np_query_vec.shape[1]:
            raise ValueError(f"Query vector dimension ({np_query_vec.shape[1]}) does not match FAISS index dimension ({index.d}).")

        # Fetch a broader candidate pool from FAISS to enable section diversity re-ranking
        candidate_k = min(max(top_k * 4, 20), total_vectors)

        logger.info(f"Searching FAISS IndexFlatIP (total_vectors={total_vectors}, top_k={top_k}, candidate_k={candidate_k})...")

        # Perform inner product search on FAISS IndexFlatIP
        distances, indices = index.search(np_query_vec, candidate_k)

        raw_scores = distances[0]
        raw_vec_ids = indices[0]

        # Step 1: Collect valid candidate records
        candidate_items = []
        for dist, vec_id in zip(raw_scores, raw_vec_ids):
            if vec_id < 0:
                continue

            metadata_record = vector_store_service.get_metadata_by_vector_id(int(vec_id))
            if metadata_record is None:
                continue

            if study_id and metadata_record.study_id != study_id:
                continue

            raw_sim = round(float(dist), 4)
            candidate_items.append({
                "vector_id": int(vec_id),
                "similarity_score": raw_sim,
                "metadata": metadata_record,
                "section": metadata_record.section
            })

        # Step 2: Apply Section Diversity Re-ranking if enabled
        selected_candidates = []
        if enable_diversity and candidate_items:
            unselected = list(candidate_items)
            section_counts = {}

            target_count = min(top_k, len(unselected))
            for _ in range(target_count):
                best_candidate = None
                best_rerank_score = -999.0
                best_idx = -1

                for idx, item in enumerate(unselected):
                    sec = item["section"]
                    sec_count = section_counts.get(sec, 0)
                    # Apply penalty for repeated sections
                    adjusted_score = item["similarity_score"] - (sec_count * diversity_penalty)

                    if adjusted_score > best_rerank_score:
                        best_rerank_score = adjusted_score
                        best_candidate = item
                        best_idx = idx

                if best_candidate and best_idx != -1:
                    chosen = unselected.pop(best_idx)
                    chosen["reranking_score"] = round(best_rerank_score, 4)
                    sec = chosen["section"]
                    section_counts[sec] = section_counts.get(sec, 0) + 1
                    selected_candidates.append(chosen)
        else:
            selected_candidates = candidate_items[:top_k]
            for c in selected_candidates:
                c["reranking_score"] = c["similarity_score"]

        # Step 3: Format final response items
        results: List[SimilaritySearchResultItem] = []
        for rank_idx, item in enumerate(selected_candidates, start=1):
            meta = item["metadata"]
            results.append(
                SimilaritySearchResultItem(
                    rank=rank_idx,
                    similarity_score=item["similarity_score"],
                    reranking_score=item.get("reranking_score"),
                    vector_id=item["vector_id"],
                    chunk_id=meta.chunk_id,
                    text=meta.text,
                    study_id=meta.study_id,
                    source_type=meta.source_type,
                    source_filename=meta.source_filename,
                    section=meta.section,
                    subsection=meta.subsection,
                    page_number=meta.page_number,
                    source_reference=meta.source_reference,
                    source_field=meta.source_field,
                    chunk_index=meta.chunk_index
                )
            )

        logger.info(f"Similarity search complete. Returned {len(results)} matching chunk(s).")

        return SimilaritySearchResponse(
            status="success",
            query=clean_query,
            top_k=top_k,
            total_vectors_searched=total_vectors,
            embedding_model=target_model_name,
            results_count=len(results),
            results=results
        )


# Global singleton instance
search_service = SearchService()
