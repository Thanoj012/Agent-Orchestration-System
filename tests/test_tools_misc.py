from app.tools.base import MAX_OUTPUT_CHARS, Tool
from app.tools.catalog import AGENT_TOOLS, TOOL_CATALOG
from app.tools.http import is_allowed, make_http_tool
from app.tools.search import make_search_tool


def test_search_formats_results_and_needs_a_key():
    def fake(query, key, n):
        return {"results": [{"title": "T", "url": "https://a.com/x", "content": "hello"}]}

    tool = Tool("web_search", "", "", make_search_tool("key", post=fake))
    out = tool.run({"query": "anything"})
    assert "URL: https://a.com/x" in out and "hello" in out
    assert Tool("s", "", "", make_search_tool("", post=fake)).run({"query": "x"}).startswith("ERROR")
    assert tool.run({}).startswith("ERROR")


def test_http_allowlist():
    hosts = ("api.github.com",)
    assert is_allowed("https://api.github.com/repos/x", hosts)
    assert not is_allowed("http://api.github.com/x", hosts)             # not https
    assert not is_allowed("https://evil.com/api.github.com", hosts)     # host must match exactly
    assert not is_allowed("https://api.github.com.evil.com/x", hosts)
    tool = Tool("http_get", "", "", make_http_tool(hosts, get=lambda url: "ok:" + url))
    assert tool.run({"url": "https://api.github.com/x"}) == "ok:https://api.github.com/x"
    assert tool.run({"url": "https://evil.com"}).startswith("ERROR")
    assert Tool("h", "", "", make_http_tool((), get=lambda u: "x")).run({"url": "https://a.com"}).startswith("ERROR")


def test_tool_output_is_truncated_and_exceptions_become_text():
    assert len(Tool("t", "", "", lambda a: "x" * 10_000).run({})) < MAX_OUTPUT_CHARS + 50
    assert Tool("t", "", "", lambda a: 1 / 0).run({}).startswith("ERROR: ZeroDivisionError")


def test_every_agent_tool_exists_and_reviewer_has_none():
    assert all(name in TOOL_CATALOG for names in AGENT_TOOLS.values() for name in names)
    assert AGENT_TOOLS["reviewer"] == []
    assert "sql_query" not in AGENT_TOOLS["research"] + AGENT_TOOLS["writer"]  # least privilege
