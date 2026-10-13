import os
import logging
from typing import Optional, Dict, Any

from app.services.llm.base_provider import BaseLLMProvider
from app.services.llm.anthropic_provider import AnthropicLLMProvider
from app.services.llm.gemini_provider import GeminiLLMProvider
from app.services.llm.openai_provider import OpenAILLMProvider
from app.services.llm.mock_provider import MockLLMProvider

logger = logging.getLogger("icf_generator.llm_service")

class LLMService:
    """
    Phase 5 Part 2: Backend LLM Provider Service Factory & Dispatcher.
    
    Reads backend configuration environment variables:
    - LLM_PROVIDER ('anthropic', 'gemini', 'openai', 'mock', 'auto')
    - LLM_MODEL (optional model string override)
    - LLM_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY
    
    Provides vendor-agnostic message generation interface for ProtocolAnalysisAgent.
    """

    def __init__(self):
        self._provider: Optional[BaseLLMProvider] = None
        self._init_provider()

    def _init_provider(self):
        provider_type = os.environ.get("LLM_PROVIDER", "").strip().lower()
        model_name = os.environ.get("LLM_MODEL", "").strip() or None
        api_key = os.environ.get("LLM_API_KEY", "").strip() or None

        if provider_type == "anthropic":
            self._provider = AnthropicLLMProvider(api_key=api_key, model=model_name)
        elif provider_type == "gemini":
            self._provider = GeminiLLMProvider(api_key=api_key, model=model_name)
        elif provider_type == "openai":
            self._provider = OpenAILLMProvider(api_key=api_key, model=model_name)
        elif provider_type == "mock":
            self._provider = MockLLMProvider(model=model_name)
        else:
            # Auto-detection mode: try Anthropic first, then Gemini, then OpenAI, fallback to AnthropicProvider
            anthropic_p = AnthropicLLMProvider(api_key=api_key, model=model_name)
            if anthropic_p.is_available():
                self._provider = anthropic_p
            else:
                gemini_p = GeminiLLMProvider(api_key=api_key, model=model_name)
                if gemini_p.is_available():
                    self._provider = gemini_p
                else:
                    openai_p = OpenAILLMProvider(api_key=api_key, model=model_name)
                    if openai_p.is_available():
                        self._provider = openai_p
                    else:
                        # Default to AnthropicLLMProvider (which handles missing keys gracefully)
                        self._provider = anthropic_p

        logger.info(
            f"Initialized LLMService with Provider: '{self._provider.provider_name}', "
            f"Model: '{self._provider.model_name}', Available: {self._provider.is_available()}"
        )

    def get_active_provider(self) -> BaseLLMProvider:
        """Re-initializes/reads env to return current active provider instance."""
        self._init_provider()
        return self._provider

    def get_config(self) -> Dict[str, Any]:
        """
        Returns active LLM provider configuration metadata for API diagnostics.
        Never exposes raw API keys.
        """
        provider = self.get_active_provider()
        config_dict = {
            "provider_name": provider.provider_name,
            "model_name": provider.model_name,
            "is_available": provider.is_available(),
            "configured_via_env": bool(
                os.environ.get("LLM_PROVIDER")
                or os.environ.get("LLM_API_KEY")
                or os.environ.get("ANTHROPIC_API_KEY")
                or os.environ.get("GEMINI_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
            )
        }
        if hasattr(provider, "primary_model"):
            config_dict["primary_model"] = getattr(provider, "primary_model")
        if hasattr(provider, "fallback_model"):
            config_dict["fallback_model"] = getattr(provider, "fallback_model")
        return config_dict

    def generate_message(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.0
    ) -> Optional[str]:
        """
        Dispatches completion message generation to the active configured LLM provider.
        """
        provider = self.get_active_provider()
        return provider.generate_message(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

llm_service = LLMService()
