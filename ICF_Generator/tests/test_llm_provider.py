import os
import pytest

from app.services.llm.llm_service import llm_service, LLMService
from app.services.llm.anthropic_provider import AnthropicLLMProvider
from app.services.llm.openai_provider import OpenAILLMProvider
from app.services.llm.mock_provider import MockLLMProvider
from app.services.protocol_analysis_agent import protocol_analysis_agent
from app.models.rag import RAGContextResponse, RAGEvidenceItem, RAGSourceMetadata
from app.models.protocol_facts import FactStatusEnum

def test_provider_switching_via_env(monkeypatch):
    """
    Verifies that changing LLM_PROVIDER in backend environment switches the active provider.
    """
    # 1. Test Mock provider
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    provider = llm_service.get_active_provider()
    assert isinstance(provider, MockLLMProvider)
    assert provider.provider_name == "mock"
    assert provider.is_available() is True

    # 2. Test Anthropic provider
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
    monkeypatch.setenv("LLM_API_KEY", "test-anthropic-key")
    provider = llm_service.get_active_provider()
    assert isinstance(provider, AnthropicLLMProvider)
    assert provider.provider_name == "anthropic"
    assert provider.model_name == "claude-3-5-sonnet-20241022"
    assert provider.is_available() is True

    # 3. Test OpenAI provider
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("LLM_API_KEY", "test-openai-key")
    provider = llm_service.get_active_provider()
    assert isinstance(provider, OpenAILLMProvider)
    assert provider.provider_name == "openai"
    assert provider.model_name == "gpt-4o"
    assert provider.is_available() is True

def test_backend_key_isolation():
    """
    Verifies that API keys are managed in backend configuration and config diagnostics never expose raw keys.
    """
    config = llm_service.get_config()
    assert "api_key" not in config
    assert "provider_name" in config
    assert "model_name" in config
    assert "is_available" in config

def test_agent_uses_llm_abstraction(monkeypatch):
    """
    Verifies that ProtocolAnalysisAgent operates seamlessly through the provider abstraction layer.
    """
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    sample_context = RAGContextResponse(
        original_query="What are the eligibility requirements?",
        processed_query="What are the eligibility requirements?",
        study_id="NCT00081328",
        evidence=[
            RAGEvidenceItem(
                rank=1,
                chunk_id="NCT00081328_eligibility_012",
                section="eligibility",
                subsection="inclusion",
                text="Inclusion Criteria:\n- Age 10-17, with randomization prior to 18th birthday.",
                similarity_score=0.48,
                source=RAGSourceMetadata(
                    filename="ctg-studies.json",
                    source_reference="eligibility",
                    study_id="NCT00081328",
                    chunk_index=12
                )
            )
        ],
        evidence_count=1,
        retrieval_status="success"
    )

    facts = protocol_analysis_agent.analyze_context(sample_context)

    assert facts.study_id == "NCT00081328"
    assert len(facts.eligibility.inclusion) > 0
    assert facts.eligibility.inclusion[0].status == FactStatusEnum.SUPPORTED
    assert facts.eligibility.inclusion[0].source_evidence_ids == ["NCT00081328_eligibility_012"]
    # Verify unsupported duration returns NOT_FOUND
    assert facts.duration.status == FactStatusEnum.NOT_FOUND
    assert facts.duration.value is None
