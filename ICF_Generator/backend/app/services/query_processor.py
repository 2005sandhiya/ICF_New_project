import logging
from typing import Tuple

logger = logging.getLogger("icf_generator.query_processor")

class QueryProcessor:
    """
    Phase 5 Part 1: Deterministic Natural Language Query Processor.
    
    Validates user query input and normalizes unnecessary whitespace while 
    preserving the original query string for source context traceability.
    No LLM is used.
    """

    def process_query(self, raw_query: str) -> Tuple[str, str]:
        """
        Validates and normalizes the input query.
        
        Args:
            raw_query: Raw user query string.
            
        Returns:
            Tuple of (original_query, processed_search_query)
            
        Raises:
            ValueError: If query is empty or contains only whitespace.
        """
        if raw_query is None:
            raise ValueError("Query string cannot be None.")

        original_query = raw_query.strip()
        if not original_query:
            raise ValueError("Query string cannot be empty or whitespace-only.")

        # Normalize multiple spaces, tabs, and newlines into single spaces
        processed_query = " ".join(original_query.split())

        logger.info(f"Processed query: '{original_query}' -> '{processed_query}'")
        return original_query, processed_query

query_processor = QueryProcessor()
