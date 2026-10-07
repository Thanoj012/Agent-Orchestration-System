"""Turn role definitions into runnable agents (each with its own model and tool subset)."""
from __future__ import annotations

from app.agents.loop import run_tool_loop
from app.agents.prompts import ROLE_PROMPTS, TASK_BUILDERS, build_system
from app.agents.verify import unsupported_urls
from app.config import Settings
from app.constants import AGENTS
from app.jsonparse import extract_json
from app.llm import get_llm
from app.agents.result import AgentResult
from app.tools.base import Tool
from app.tools.catalog import AGENT_TOOLS


def parse_review(output: str, draft: str, research_text: str) -> dict:
    """Combine the reviewer model's verdict with a deterministic source check."""
    try:
        data = extract_json(output)
    except ValueError:
        data = {"approved": False, "issues": ["The reviewer returned a malformed verdict."], "summary": ""}
    approved = bool(data.get("approved"))
    issues = [str(i) for i in (data.get("issues") or [])]
    bad_urls = unsupported_urls(draft, research_text)
    if bad_urls:
        approved = False
        issues.append("The draft cites URLs that are not in the research findings: " + ", ".join(bad_urls[:5]))
    return {"approved": approved, "issues": issues, "summary": str(data.get("summary", ""))}


def build_agents(settings: Settings, tools: dict[str, Tool], emit, llm_for=get_llm) -> dict:
    def make(role: str):
        role_tools = {name: tools[name] for name in AGENT_TOOLS[role] if name in tools}
        system = build_system(ROLE_PROMPTS[role], role_tools)

        def run(state: dict, step: dict) -> AgentResult:
            run_id = state["run_id"]

            def on_tool(name: str, args: dict, observation: str) -> None:
                emit(run_id, role, "tool_call", f"{name}({str(args)[:200]})", {"tool": name, "input": args, "output": observation[:1500]})

            result = run_tool_loop(
                llm_for(settings.model_for(role)),
                system,
                TASK_BUILDERS[role](state, step),
                role_tools,
                settings.max_agent_steps,
                on_tool,
            )
            if role == "reviewer":
                review = parse_review(result.output, state.get("draft", ""), state.get("results", {}).get("research", ""))
                return AgentResult(result.output, result.tool_calls, review=review)
            return AgentResult(result.output, result.tool_calls)

        return run

    return {role: make(role) for role in AGENTS}
