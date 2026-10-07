from app.agents.factory import parse_review
from app.agents.verify import find_urls, unsupported_urls
from app.views import agent_cards


def test_url_verification_is_normalised():
    sources = "Growth (https://example.com/report/) and https://news.org/a."
    draft = "See [report](https://EXAMPLE.com/report) and https://news.org/a, plus https://made-up.io/x."
    assert unsupported_urls(draft, sources) == ["https://made-up.io/x"]
    assert find_urls("no links here") == set()


def test_parse_review_combines_model_verdict_and_source_check():
    ok = parse_review('FINAL {"approved": true, "issues": [], "summary": "fine"}', "See https://a.com", "https://a.com")
    assert ok["approved"] and ok["issues"] == []
    fabricated = parse_review('{"approved": true, "issues": []}', "See https://fake.com", "https://a.com")
    assert not fabricated["approved"] and "fake.com" in fabricated["issues"][0]
    assert not parse_review("total gibberish", "", "")["approved"]
    assert parse_review('```json\n{"approved": false, "issues": ["x"]}\n```', "", "")["issues"] == ["x"]


def test_agent_cards_reflect_progress():
    plan = [
        {"agent": "research", "status": "done"},
        {"agent": "analyst", "status": "pending"},
        {"agent": "writer", "status": "pending"},
        {"agent": "reviewer", "status": "pending"},
    ]
    events = [
        {"agent": "research", "kind": "tool_call", "message": "web_search(...)"},
        {"agent": "research", "kind": "agent_finished", "message": "done"},
    ]
    cards = agent_cards({"plan": plan, "status": "running", "next": "analyst"}, events)
    by_agent = {c["agent"]: c for c in cards}
    assert by_agent["research"]["status"] == "completed" and by_agent["research"]["tool_calls"] == 1
    assert by_agent["analyst"]["status"] == "running"
    assert by_agent["writer"]["status"] == "waiting"
    assert by_agent["research"]["last_message"] == "done"
    assert agent_cards({}, []) == []
