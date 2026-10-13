import os
import logging
from typing import Optional

from app.services.llm.base_provider import BaseLLMProvider

logger = logging.getLogger("icf_generator.llm.gemini_provider")

DEFAULT_GEMINI_PRIMARY_MODEL = "gemini-3.8-flash"
DEFAULT_GEMINI_FALLBACK_MODEL = "gemini-2.5-flash"

class GeminiLLMProvider(BaseLLMProvider):
    """
    Google Gemini LLM Provider implementation using official google-genai SDK
    with automatic primary -> fallback model switching.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None
    ):
        # Priority: explicit arg > LLM_API_KEY > GEMINI_API_KEY
        self.api_key = (
            api_key or os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
        ).strip()
        
        self._primary_model = (
            model
            or os.environ.get("GEMINI_PRIMARY_MODEL")
            or os.environ.get("LLM_MODEL")
            or os.environ.get("GEMINI_MODEL")
            or DEFAULT_GEMINI_PRIMARY_MODEL
        ).strip()

        self._fallback_model = (
            fallback_model
            or os.environ.get("GEMINI_FALLBACK_MODEL")
            or DEFAULT_GEMINI_FALLBACK_MODEL
        ).strip()

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._primary_model

    @property
    def primary_model(self) -> str:
        return self._primary_model

    @property
    def fallback_model(self) -> str:
        return self._fallback_model

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _sanitize_error(self, error: Exception) -> str:
        error_msg = str(error)
        if self.api_key and self.api_key in error_msg:
            error_msg = error_msg.replace(self.api_key, "[REDACTED_API_KEY]")
        return error_msg

    def generate_message(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.0
    ) -> Optional[str]:
        if not self.is_available():
            logger.info("Gemini API key is not set (GEMINI_API_KEY or LLM_API_KEY). Skipping live Gemini API call.")
            return None

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                max_output_tokens=max_tokens,
                temperature=temperature,
            )

            # --- Step 1: Attempt Primary Gemini Model ---
            try:
                logger.info(f"Calling Primary Gemini API (provider=gemini, model={self._primary_model})...")
                response = client.models.generate_content(
                    model=self._primary_model,
                    contents=user_prompt,
                    config=config,
                )
                if response and response.text:
                    logger.info(f"Primary Gemini model succeeded (model={self._primary_model}).")
                    return response.text
                
                logger.warning(
                    f"Primary Gemini model returned empty response (model={self._primary_model}). "
                    f"Attempting fallback model ({self._fallback_model})..."
                )
            except Exception as primary_exc:
                safe_err = self._sanitize_error(primary_exc)
                logger.warning(
                    f"Primary Gemini API call failed (model={self._primary_model}): {safe_err}. "
                    f"Switching to fallback model ({self._fallback_model})..."
                )

            # --- Step 2: Attempt Fallback Gemini Model ---
            try:
                logger.info(f"Calling Fallback Gemini API (provider=gemini, model={self._fallback_model})...")
                fallback_response = client.models.generate_content(
                    model=self._fallback_model,
                    contents=user_prompt,
                    config=config,
                )
                if fallback_response and fallback_response.text:
                    logger.info(f"Fallback Gemini model succeeded (model={self._fallback_model}).")
                    return fallback_response.text

                logger.error(
                    f"Fallback Gemini model returned empty response (model={self._fallback_model}). "
                    f"Both primary and fallback models failed."
                )
                return None
            except Exception as fallback_exc:
                safe_err = self._sanitize_error(fallback_exc)
                logger.error(
                    f"Fallback Gemini API call failed (model={self._fallback_model}): {safe_err}. "
                    f"Both primary and fallback models failed.",
                    exc_info=False
                )
                return None

        except Exception as outer_exc:
            safe_err = self._sanitize_error(outer_exc)
            logger.error(f"Unexpected error in GeminiLLMProvider: {safe_err}", exc_info=False)
            return None
