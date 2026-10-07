"""Agent-facing wrappers around the persistent memory store."""
from __future__ import annotations

from app.tools.base import ToolError


def make_memory_tools(store):
    def search(args: dict) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            raise ToolError("missing 'query'")
        results = store.search(query, k=4)
        if not results:
            return "(no matching memories)"
        return "\n\n".join(
            f"[memory #{r['id']}] {r['title']} ({r['category']})\n{r['snippet']}" for r in results
        )

    def save(args: dict) -> str:
        title, content = str(args.get("title", "")).strip(), str(args.get("content", "")).strip()
        if not title or not content:
            raise ToolError("both 'title' and 'content' are required")
        memory_id = store.save(title, content, category=str(args.get("category", "Notes")), source="agent")
        return f"saved memory #{memory_id}"

    return search, save
