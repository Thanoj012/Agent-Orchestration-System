import pytest

from app.config import get_settings
from app.llm import LLM, LLMError, parse_spec


def test_parse_spec():
    assert parse_spec("anthropic:claude-sonnet-5") == ("anthropic", "claude-sonnet-5")
    assert parse_spec("OpenAI:gpt-4o") == ("openai", "gpt-4o")
    for bad in ["gpt-4o", "google:gemini", "openai:", ""]:
        with pytest.raises(LLMError):
            parse_spec(bad)


def test_missing_api_key_gives_a_clear_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        LLM("anthropic:x").complete("s", [{"role": "user", "content": "hi"}])
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        LLM("openai:x").complete("s", [{"role": "user", "content": "hi"}])


def test_model_routing_and_override(monkeypatch):
    monkeypatch.delenv("LLM_OVERRIDE", raising=False)
    get_settings.cache_clear()
    s = get_settings()
    assert s.model_for("analyst").startswith("openai:") and s.model_for("reviewer").startswith("anthropic:")
    monkeypatch.setenv("LLM_OVERRIDE", "openai:gpt-4o")
    get_settings.cache_clear()
    assert get_settings().model_for("reviewer") == "openai:gpt-4o"
    get_settings.cache_clear()
