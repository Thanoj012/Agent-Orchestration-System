from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentResult:
    output: str
    tool_calls: int = 0
    review: dict | None = None
