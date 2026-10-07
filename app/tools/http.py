"""Fetch from external APIs - but only from hosts the operator explicitly allow-listed."""
from __future__ import annotations

from urllib.parse import urlparse

from app.tools.base import ToolError


def is_allowed(url: str, hosts: tuple[str, ...]) -> bool:
    parts = urlparse(url)
    return parts.scheme == "https" and (parts.hostname or "").lower() in hosts


def _get(url: str) -> str:
    import httpx

    # redirects are not followed: a redirect could lead away from the allow-list
    response = httpx.get(url, timeout=15, follow_redirects=False, headers={"User-Agent": "orchestrai/0.1"})
    response.raise_for_status()
    return response.text


def make_http_tool(hosts: tuple[str, ...], get=_get):
    def run(args: dict) -> str:
        url = str(args.get("url", "")).strip()
        if not hosts:
            raise ToolError("no external hosts are allowed (operator must set HTTP_ALLOWED_HOSTS)")
        if not is_allowed(url, hosts):
            raise ToolError(f"only https URLs on these hosts are allowed: {', '.join(hosts)}")
        return get(url)

    return run
