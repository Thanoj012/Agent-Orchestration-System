"""Static metadata about tools and which agent may use which (no heavy imports)."""

TOOL_CATALOG = {
    "web_search": {
        "description": "Search the web for current information (news, competitors, market data).",
        "input": '{"query": "search text"}',
    },
    "http_get": {
        "description": "GET a JSON/text resource from an allow-listed external API or website.",
        "input": '{"url": "https://..."}',
    },
    "memory_search": {
        "description": "Semantic search over persistent memory (past reports, notes, insights).",
        "input": '{"query": "what to look for"}',
    },
    "memory_save": {
        "description": "Save a note to persistent memory so future runs can reuse it.",
        "input": '{"title": "short title", "content": "text", "category": "Research"}',
    },
    "describe_schema": {
        "description": "List the tables and columns of the company database.",
        "input": "{}",
    },
    "sql_query": {
        "description": "Run ONE read-only SQL SELECT against the company PostgreSQL database.",
        "input": '{"sql": "SELECT ..."}',
    },
    "calculator": {
        "description": (
            "Evaluate a math expression. Supports + - * / ** %, round, abs, min, max, sum, mean, "
            "sqrt, log and pct_change(old, new)."
        ),
        "input": '{"expression": "pct_change(120, 150)"}',
    },
}

# Least privilege: each agent only sees the tools it needs.
AGENT_TOOLS = {
    "research": ["web_search", "http_get", "memory_search", "memory_save"],
    "analyst": ["describe_schema", "sql_query", "calculator"],
    "writer": ["memory_search"],
    "reviewer": [],
}
