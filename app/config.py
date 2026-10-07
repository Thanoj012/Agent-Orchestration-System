"""Configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from app.constants import ROLES

DEFAULT_MODELS = {
    "supervisor": "anthropic:claude-sonnet-5",
    "research": "anthropic:claude-sonnet-5",
    "analyst": "openai:gpt-4o",
    "writer": "openai:gpt-4o",
    "reviewer": "anthropic:claude-sonnet-5",
}


def _hosts(value: str) -> tuple[str, ...]:
    return tuple(h.strip().lower() for h in value.split(",") if h.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str
    analyst_database_url: str
    redis_url: str
    chroma_host: str
    chroma_port: int
    tavily_api_key: str
    http_allowed_hosts: tuple[str, ...]
    llm_override: str  # "provider:model" - forces every agent onto one model
    max_revisions: int
    max_agent_steps: int
    api_url: str
    models: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MODELS))

    def model_for(self, role: str) -> str:
        """`provider:model` string for a role (supervisor, research, analyst, writer, reviewer)."""
        return self.llm_override or self.models[role]


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "postgresql+psycopg://orchestrai:orchestrai@localhost:5432/orchestrai"),
        analyst_database_url=os.getenv(
            "ANALYST_DATABASE_URL", "postgresql+psycopg://analyst_ro:analyst_ro@localhost:5432/orchestrai"
        ),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        chroma_host=os.getenv("CHROMA_HOST", "localhost"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8001")),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        http_allowed_hosts=_hosts(os.getenv("HTTP_ALLOWED_HOSTS", "")),
        llm_override=os.getenv("LLM_OVERRIDE", "").strip(),
        max_revisions=int(os.getenv("MAX_REVISIONS", "2")),
        max_agent_steps=int(os.getenv("MAX_AGENT_STEPS", "6")),
        api_url=os.getenv("API_URL", "http://localhost:8000"),
        models={role: os.getenv(f"MODEL_{role.upper()}", DEFAULT_MODELS[role]) for role in ROLES},
    )
