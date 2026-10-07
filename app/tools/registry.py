"""Build the concrete tool set. Needs the heavy dependencies, so only the worker imports it."""
from __future__ import annotations

from app.config import Settings
from app.tools.base import Tool
from app.tools.calculator import calculator_tool
from app.tools.catalog import TOOL_CATALOG
from app.tools.http import make_http_tool
from app.tools.memory_tools import make_memory_tools
from app.tools.search import make_search_tool
from app.tools.sql import make_schema_tool, make_sql_tool


def build_tools(settings: Settings, memory, analyst_engine) -> dict[str, Tool]:
    memory_search, memory_save = make_memory_tools(memory)
    functions = {
        "web_search": make_search_tool(settings.tavily_api_key),
        "http_get": make_http_tool(settings.http_allowed_hosts),
        "memory_search": memory_search,
        "memory_save": memory_save,
        "describe_schema": make_schema_tool(analyst_engine),
        "sql_query": make_sql_tool(analyst_engine),
        "calculator": calculator_tool,
    }
    return {
        name: Tool(name, meta["description"], meta["input"], functions[name])
        for name, meta in TOOL_CATALOG.items()
    }
