"""Tool abstraction. Tools never raise into the agent loop: failures come back as text."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

MAX_OUTPUT_CHARS = 4000


class ToolError(Exception):
    """A tool failed in a way the agent should be told about (bad input, not allowed, ...)."""


@dataclass
class Tool:
    name: str
    description: str
    input_hint: str
    fn: Callable[[dict], str]

    def run(self, args: dict) -> str:
        try:
            output = str(self.fn(args if isinstance(args, dict) else {}))
        except ToolError as exc:
            return f"ERROR: {exc}"
        except Exception as exc:  # noqa: BLE001 - agents must always get a text observation back
            return f"ERROR: {type(exc).__name__}: {exc}"
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n...[truncated]"
        return output
