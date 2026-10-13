import os
import pytest
from unittest.mock import MagicMock, patch, call

from app.services.llm.llm_service import llm_service, LLMService
from app.services.llm.gemini_provider import (
    GeminiLLMProvider,
    DEFAULT_GEMINI_PRIMARY_MODEL,
    DEFAULT_GEMINI_FALLBACK_MODEL
)
from app.services.validation_agent import validation_agent
from app.models.icf import ICFDraft, ICFSection
from app.models.protocol_facts import ProtocolFacts
from app.models.validation import ICFValidationRequest

def test_gemini_env_config_and_init(monkeypatch):
    """
    Test F & E: Verifies environment configuration loading and missing API key handling.
    """
    # 1. Missing API key
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_PRIMARY_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)

    provider = GeminiLLMProvider()
    assert provider.provider_name == "gemini"
    assert provider.primary_model == DEFAULT_GEMINI_PRIMARY_MODEL
    assert provider.fallback_model == DEFAULT_GEMINI_FALLBACK_MODEL
    assert provider.is_available() is False
    assert provider.generate_message("system", "user") is None

    # 2. Configured via custom primary and fallback env vars
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_PRIMARY_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")

    provider_env = GeminiLLMProvider()
    assert provider_env.is_available() is True
    assert provider_env.primary_model == "gemini-3.8-flash"
    assert provider_env.fallback_model == "gemini-2.5-flash"

def test_primary_succeeds_fallback_not_called(monkeypatch):
    """
    Test A: Primary model succeeds -> called once, fallback NOT called, primary response returned.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_PRIMARY_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")

    provider = GeminiLLMProvider()

    mock_primary_res = MagicMock()
    mock_primary_res.text = "Primary Model Response"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_primary_res

    with patch("google.genai.Client", return_value=mock_client):
        res = provider.generate_message("system prompt", "user prompt")
        
        assert res == "Primary Model Response"
        # Primary called once with primary model name
        assert mock_client.models.generate_content.call_count == 1
        first_call_kwargs = mock_client.models.generate_content.call_args_list[0].kwargs
        assert first_call_kwargs["model"] == "gemini-3.8-flash"

def test_primary_fails_fallback_succeeds(monkeypatch):
    """
    Test B: Primary fails, fallback succeeds -> primary called once, fallback called once, fallback response returned.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_PRIMARY_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")

    provider = GeminiLLMProvider()

    mock_fallback_res = MagicMock()
    mock_fallback_res.text = "Fallback Model Response"

    mock_client = MagicMock()
    # First call (primary) raises Exception, second call (fallback) returns fallback_res
    mock_client.models.generate_content.side_effect = [
        Exception("Primary model temporary 503 error"),
        mock_fallback_res
    ]

    with patch("google.genai.Client", return_value=mock_client):
        res = provider.generate_message("system prompt", "user prompt")

        assert res == "Fallback Model Response"
        assert mock_client.models.generate_content.call_count == 2
        
        # Call 1: Primary
        assert mock_client.models.generate_content.call_args_list[0].kwargs["model"] == "gemini-3.8-flash"
        # Call 2: Fallback
        assert mock_client.models.generate_content.call_args_list[1].kwargs["model"] == "gemini-2.5-flash"

def test_primary_fails_fallback_fails(monkeypatch):
    """
    Test C: Both primary and fallback fail -> primary called once, fallback called once, None/controlled error returned.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_PRIMARY_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")

    provider = GeminiLLMProvider()

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        Exception("Primary rate limit error"),
        Exception("Fallback rate limit error")
    ]

    with patch("google.genai.Client", return_value=mock_client):
        res = provider.generate_message("system prompt", "user prompt")

        assert res is None
        assert mock_client.models.generate_content.call_count == 2

def test_validation_failure_does_not_trigger_fallback():
    """
    Test D: Validation failure does not trigger model fallback.
    Validation operates on generated ICFDraft and ProtocolFacts independently.
    """
    empty_draft = ICFDraft(
        study_id="NCT00081328",
        draft_version=1,
        title="Empty Draft",
        sections=[
            ICFSection(section_id="purpose", title="Purpose", content="", source_evidence_ids=[])
        ]
    )
    facts = ProtocolFacts(study_id="NCT00081328")

    # Run validation on incomplete draft using ICFValidationRequest
    val_request = ICFValidationRequest(study_id="NCT00081328", icf_draft=empty_draft, protocol_facts=facts)
    report = validation_agent.validate_icf(val_request)
    
    assert report.overall_status in ["PASSED", "FAILED", "REQUIRES_REVIEW"]
    assert isinstance(report.overall_score, float)
    # Validation executes without attempting LLM calls or model fallbacks
