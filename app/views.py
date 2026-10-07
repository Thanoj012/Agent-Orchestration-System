"""Turn raw run state + events into what the dashboard shows (agent cards)."""
from __future__ import annotations

from app.constants import AGENTS, DISPLAY_NAMES


def agent_cards(state: dict, events: list[dict]) -> list[dict]:
    plan = state.get("plan") or []
    cards = []
    for agent in AGENTS:
        steps = [s for s in plan if s["agent"] == agent]
        if not steps:
            continue
        done = sum(1 for s in steps if s["status"] == "done")
        if done == len(steps):
            status = "completed"
        elif state.get("status") == "running" and state.get("next") == agent:
            status = "running"
        else:
            status = "waiting"
        mine = [e for e in events if e.get("agent") == agent]
        cards.append(
            {
                "agent": agent,
                "title": DISPLAY_NAMES[agent],
                "status": status,
                "steps_done": done,
                "steps_total": len(steps),
                "tool_calls": sum(1 for e in mine if e.get("kind") == "tool_call"),
                "last_message": mine[-1]["message"] if mine else "",
            }
        )
    return cards
