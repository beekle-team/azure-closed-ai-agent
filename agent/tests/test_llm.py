from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from closed_agent import llm
from closed_agent.settings import settings


def test_backend_is_mock_without_keys(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "")
    monkeypatch.setattr(settings, "azure_openai_api_key", "")
    assert llm.llm_backend() == "mock"
    assert llm.llm_model() == "mock"


def test_production_refuses_openrouter(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "")
    monkeypatch.setattr(settings, "azure_openai_api_key", "")
    assert llm.llm_backend() == "blocked"


def test_backend_prefers_openrouter(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-4o-mini")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://example.openai.azure.com")
    monkeypatch.setattr(settings, "azure_openai_api_key", "azure-key")
    assert llm.llm_backend() == "openrouter"
    assert llm.llm_model() == "openai/gpt-4o-mini"


@pytest.mark.asyncio
async def test_complete_uses_openrouter_client(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-4o-mini")

    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="契約管理部に一声かける。"))],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=7),
    )
    create = AsyncMock(return_value=response)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    with patch("closed_agent.llm.AsyncOpenAI", return_value=fake_client) as ctor:
        result = await llm.complete(system="sys", user="海外出張の保険は誰が見る？")

    ctor.assert_called_once()
    assert ctor.call_args.kwargs["api_key"] == "sk-or-test"
    assert ctor.call_args.kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert create.await_args.kwargs["model"] == "openai/gpt-4o-mini"
    assert result.text == "契約管理部に一声かける。"
    assert result.input_tokens == 12
    assert result.output_tokens == 7
