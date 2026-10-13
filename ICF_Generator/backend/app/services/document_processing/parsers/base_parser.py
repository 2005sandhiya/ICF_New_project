from abc import ABC, abstractmethod
from typing import Tuple, List, Optional
from app.models.study import PageContent

class BaseParser(ABC):
    """
    Abstract base parser interface for document content extraction.
    """

    @abstractmethod
    def parse(self, filename: str, content: bytes) -> Tuple[str, List[PageContent], Optional[int]]:
        """
        Parses document binary content and extracts text.
        Returns Tuple of (full_text, pages_list, page_count).
        """
        pass
