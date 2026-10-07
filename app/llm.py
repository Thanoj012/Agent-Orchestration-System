"""Provider-agnostic LLM wrapper (Anthropic Claude / OpenAI GPT).

Every agent is assigned a `provider:model` string, e.g. `anthropic:claude-sonnet-5`
or `openai:gpt-4o`, so different agents can run on different vendors.
"""
from __future__ import annotations

import os
from functools import lru_cache

PROVIDERS = ("anthropic", "openai")


class LLMError(RuntimeError):
    """Raised when the provider configuration is unusable (bad spec, missing API key)."""


def parse_spec(spec: str) -> tuple[str, str]:
    provider, _, model = spec.partition(":")
    provider = provider.strip().lower()
    if provider not in PROVIDERS or not model.strip():
        raise LLMError(f"Invalid model spec {spec!r}; expected 'anthropic:<model>' or 'openai:<model>'")
    return provider, model.strip()


class LLM:
    def __init__(self, spec: str, max_tokens: int = 4096):
        self.provider, self.model = parse_spec(spec)
        self.max_tokens = max_tokens
        self._client = None

    def complete(self, system: str, messages: list[dict]) -> str:
        """messages: [{"role": "user"|"assistant", "content": str}, ...]"""
        return self._anthropic(system, messages) if self.provider == "anthropic" else self._openai(system, messages)

    def _anthropic(self, system: str, messages: list[dict]) -> str:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise LLMError("ANTHROPIC_API_KEY is not set")
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(timeout=120)
        response = self._client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system, messages=messages
        )
        return "".join(block.text for block in response.content if block.type == "text")

    def _openai(self, system: str, messages: list[dict]) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            raise LLMError("OPENAI_API_KEY is not set")
        if self._client is None:
            import openai

            self._client = openai.OpenAI(timeout=120)
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "system", "content": system}, *messages],
        )
        return response.choices[0].message.content or ""


@lru_cache
def get_llm(spec: str) -> LLM:
    return LLM(spec)
