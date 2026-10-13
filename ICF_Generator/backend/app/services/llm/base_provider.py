from abc import ABC, abstractmethod
from typing import Optional

class BaseLLMProvider(ABC):
    """
    Phase 5 Part 2: Abstract Base Class for LLM Providers.
    
    Decouples ProtocolAnalysisAgent from specific LLM vendors (Anthropic, OpenAI, Mock).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the canonical provider name (e.g. 'anthropic', 'openai', 'mock')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the configured LLM model name (e.g. 'claude-3-5-sonnet-20241022', 'gpt-4o')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the required API key / environment credentials are set."""
        pass

    @abstractmethod
    def generate_message(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.0
    ) -> Optional[str]:
        """
        Generates a completion message response from the configured LLM provider.
        
        Args:
            system_prompt: High-priority system instructions.
            user_prompt: User prompt content.
            max_tokens: Maximum token length for response.
            temperature: Sampling temperature (default: 0.0 for deterministic output).
            
        Returns:
            Raw response text string or None if generation failed / provider unavailable.
        """
        pass
