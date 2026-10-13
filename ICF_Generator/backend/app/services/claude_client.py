import logging
from typing import Optional

from app.services.llm.llm_service import llm_service

logger = logging.getLogger("icf_generator.claude_client")

class ClaudeClient:
    """
    Backward-compatibility wrapper delegating to LLMService provider abstraction.
    """

    def is_available(self) -> bool:
        provider = llm_service.get_active_provider()
        return provider.is_available()

    def generate_message(
        self,
        system_prompt: str,
        user_prompt: str,
        model_name: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0
    ) -> Optional[str]:
        return llm_service.generate_message(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

claude_client = ClaudeClient()
