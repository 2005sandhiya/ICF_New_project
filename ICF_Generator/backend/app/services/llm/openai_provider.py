import os
import logging
from typing import Optional
import httpx

from app.services.llm.base_provider import BaseLLMProvider

logger = logging.getLogger("icf_generator.llm.openai_provider")

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4o"

class OpenAILLMProvider(BaseLLMProvider):
    """
    OpenAI LLM Provider implementation for future OpenAI model configuration (e.g. gpt-4o).
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        # Priority: explicit arg > LLM_API_KEY > OPENAI_API_KEY
        self.api_key = (api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
        self._model = (model or os.environ.get("LLM_MODEL") or DEFAULT_OPENAI_MODEL).strip()

    @property
    def provider_name(self) -> str:
        return "openai"

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
            logger.info("OpenAI API key is not set. Skipping live OpenAI API call.")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self._model,
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        }

        try:
            logger.info(f"Calling OpenAI API ({self._model})...")
            with httpx.Client(timeout=30.0) as client:
                response = client.post(OPENAI_API_URL, headers=headers, json=payload)
                if response.status_code != 200:
                    logger.error(f"OpenAI API Error {response.status_code}: {response.text}")
                    return None

                res_data = response.json()
                choices = res_data.get("choices", [])
                if choices and len(choices) > 0:
                    return choices[0].get("message", {}).get("content", "")
                return None
        except Exception as e:
            logger.error(f"Exception during OpenAI API call: {e}", exc_info=True)
            return None
