"""Deterministic source checking - the reviewer never has to be trusted blindly."""
from __future__ import annotations

import re

_URL_RE = re.compile(r"https?://[^\s<>\")\]]+")


def _normalize(url: str) -> str:
    return url.rstrip(".,;:!?)").rstrip("/").lower()


def find_urls(text: str) -> set[str]:
    return {_normalize(u) for u in _URL_RE.findall(text or "")}


def unsupported_urls(draft: str, sources: str) -> list[str]:
    """URLs cited in the draft that never appeared in the research findings."""
    return sorted(find_urls(draft) - find_urls(sources))
