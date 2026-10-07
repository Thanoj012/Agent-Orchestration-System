"""Supervisor planning: the LLM proposes a plan, code enforces its shape.

Whatever the model returns, the final plan is always
    [research and/or analyst (at least one)]  ->  writer  ->  reviewer
so a malformed or adversarial plan can never skip writing or review.
"""
from __future__ import annotations

from app.jsonparse import extract_json

WORKERS = ("research", "analyst")

PLANNER_SYSTEM = """You are the Supervisor of a team of AI agents that produces business reports.

Team:
- research: searches the web and memory for facts (news, competitors, market trends)
- analyst: queries the company PostgreSQL database and does calculations
- writer: writes the report from the findings
- reviewer: fact-checks the draft

Plan the work for the user's goal. Include only the workers (research, analyst) that are needed,
then always writer and reviewer. Give each agent a specific instruction.

Reply with ONLY a JSON object:
{"plan": [{"agent": "research", "instruction": "..."}, {"agent": "analyst", "instruction": "..."},
          {"agent": "writer", "instruction": "..."}, {"agent": "reviewer", "instruction": "..."}]}"""


def default_instruction(agent: str, goal: str) -> str:
    return {
        "research": f"Find current, sourced facts relevant to: {goal}",
        "analyst": f"Query the company database for the numbers relevant to: {goal}",
        "writer": f"Write a structured Markdown report for: {goal}",
        "reviewer": "Verify every claim and number in the draft against the findings and data.",
    }[agent]


def validate_plan(raw, goal: str) -> list[dict]:
    instructions: dict[str, str] = {}
    workers: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        agent = str(item.get("agent", "")).strip().lower()
        if agent in WORKERS and agent not in workers:
            workers.append(agent)
        if agent in (*WORKERS, "writer", "reviewer"):
            instructions.setdefault(agent, str(item.get("instruction") or "").strip())
    order = (workers or list(WORKERS)) + ["writer", "reviewer"]
    return [
        {"agent": a, "instruction": instructions.get(a) or default_instruction(a, goal), "status": "pending"}
        for a in order
    ]


def make_plan(llm, goal: str) -> list[dict]:
    """Ask the supervisor model for a plan. API/config errors propagate; bad output falls back."""
    reply = llm.complete(PLANNER_SYSTEM, [{"role": "user", "content": f"Goal: {goal}"}])
    try:
        raw = extract_json(reply).get("plan")
    except ValueError:
        raw = None
    return validate_plan(raw, goal)
