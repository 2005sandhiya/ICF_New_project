import logging
from typing import Optional

from app.services.llm.base_provider import BaseLLMProvider

logger = logging.getLogger("icf_generator.llm.mock_provider")

class MockLLMProvider(BaseLLMProvider):
    """
    Mock LLM Provider for offline testing or fallback environments without live API keys.
    """

    def __init__(self, model: Optional[str] = "mock-deterministic-v1"):
        self._model = model or "mock-deterministic-v1"

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model

    def is_available(self) -> bool:
        return True

    def generate_message(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.0
    ) -> Optional[str]:
        logger.info("MockLLMProvider invoked for completion message generation.")
        # Returning None instructs ProtocolAnalysisAgent to use its deterministic grounded parser
        return None
