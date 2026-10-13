import os
import pytest

from app.services.llm.gemini_provider import GeminiLLMProvider

@pytest.mark.skipif(
    not (os.environ.get("GEMINI_API_KEY") or (os.environ.get("LLM_PROVIDER") == "gemini" and os.environ.get("LLM_API_KEY"))),
    reason="GEMINI_API_KEY is not set in environment"
)
def test_live_gemini_connectivity():
    """
    Live verification test for Gemini API connectivity with primary/fallback models.
    Only runs when GEMINI_API_KEY is present in the environment.
    Sends a harmless non-clinical prompt ("Return the word OK.") to verify API auth and model response.
    """
    provider = GeminiLLMProvider()
    assert provider.is_available() is True, "Gemini provider should be available when key is set"
    assert provider.primary_model is not None
    assert provider.fallback_model is not None

    response = provider.generate_message(
        system_prompt="You are a helpful assistant. Be as concise as possible.",
        user_prompt="Return the word OK.",
        max_tokens=10,
        temperature=0.0
    )

    assert response is not None, "Live Gemini API call returned None"
    assert "OK" in response.upper(), f"Expected 'OK' in live Gemini response, got: '{response}'"
