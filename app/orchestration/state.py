"""The graph state. It is plain JSON so it can be saved to PostgreSQL after every step."""
from typing import Any, TypedDict


class RunState(TypedDict, total=False):
    run_id: str
    goal: str
    plan: list[dict]            # [{"agent", "instruction", "status": "pending"|"done"}]
    results: dict[str, str]     # agent -> latest output
    draft: str                  # latest report draft (from the writer)
    review: dict | None         # {"approved": bool, "issues": [...], "summary": str}
    approval: dict | None       # {"decision": "approve"|"request_changes", "feedback": str}
    revision_count: int         # automatic (reviewer-driven) revisions so far
    escalated: bool             # True if the human is asked because the reviewer never approved
    escalation_reason: str
    status: str                 # queued | running | awaiting_approval | completed | failed
    next: str                   # routing decision of the supervisor
    error: str


def new_state(run_id: str, goal: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "goal": goal,
        "plan": [],
        "results": {},
        "draft": "",
        "review": None,
        "approval": None,
        "revision_count": 0,
        "escalated": False,
        "escalation_reason": "",
        "status": "queued",
        "next": "",
        "error": "",
    }
