import os
import logging
from typing import Optional
import httpx

from app.services.llm.base_provider import BaseLLMProvider

logger = logging.getLogger("icf_generator.llm.anthropic_provider")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-20241022"

class AnthropicLLMProvider(BaseLLMProvider):
    """
    Anthropic Claude LLM Provider implementation.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        # Priority: explicit arg > LLM_API_KEY > ANTHROPIC_API_KEY
        self.api_key = (api_key or os.environ.get("LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        self._model = (model or os.environ.get("LLM_MODEL") or DEFAULT_CLAUDE_MODEL).strip()

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_message(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.0
    ) -> Optional[str]:
        if not self.is_available():
            logger.info("Anthropic API key is not set. Skipping live Anthropic API call.")
            return None

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        }

        try:
            logger.info(f"Calling Anthropic API ({self._model})...")
            with httpx.Client(timeout=30.0) as client:
                response = client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
                if response.status_code != 200:
                    logger.error(f"Anthropic API Error {response.status_code}: {response.text}")
                    return None

                res_data = response.json()
                content_blocks = res_data.get("content", [])
                if content_blocks and len(content_blocks) > 0:
                    return content_blocks[0].get("text", "")
                return None
        except Exception as e:
            logger.error(f"Exception during Anthropic API call: {e}", exc_info=True)
            return None
