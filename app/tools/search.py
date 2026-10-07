"""Web search via the Tavily API (https://tavily.com - free tier available)."""
from __future__ import annotations

from app.tools.base import ToolError


def _tavily_post(query: str, api_key: str, max_results: int) -> dict:
    import httpx

    response = httpx.post(
        "https://api.tavily.com/search",
        json={"query": query, "max_results": max_results},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def make_search_tool(api_key: str, post=_tavily_post):
    def run(args: dict) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            raise ToolError("missing 'query'")
        if not api_key:
            raise ToolError("web search is not configured (TAVILY_API_KEY is missing)")
        max_results = min(max(int(args.get("max_results", 5)), 1), 8)
        results = post(query, api_key, max_results).get("results", [])
        if not results:
            return "(no results)"
        return "\n\n".join(
            f"[{i}] {r.get('title', '')}\nURL: {r.get('url', '')}\n{str(r.get('content', ''))[:500]}"
            for i, r in enumerate(results, start=1)
        )

    return run
