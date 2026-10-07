"""Supervisor routing logic - a pure function of the run state.

Because the decision depends only on the saved state, a run can be stopped at the
human-approval gate (for minutes or days), survive a worker restart, and continue
exactly where it left off.
"""
from __future__ import annotations

from app.constants import END, FINALIZE, HUMAN_APPROVAL, TERMINAL


def revision_steps(source: str, feedback: str) -> list[dict]:
    return [
        {
            "agent": "writer",
            "instruction": f"Revise the previous draft. Address ALL of this {source} feedback:\n{feedback}",
            "status": "pending",
        },
        {"agent": "reviewer", "instruction": "Re-review the revised draft.", "status": "pending"},
    ]


def decide(state: dict, max_revisions: int = 2) -> dict:
    """Return the state updates for the supervisor node, including `next`."""
    if state.get("status") in TERMINAL:
        return {"next": END}

    plan = state.get("plan") or []
    pending = next((step for step in plan if step["status"] == "pending"), None)
    if pending:
        return {"next": pending["agent"]}

    # -- the plan is finished: consider the human's decision, then the reviewer's -------------
    approval = state.get("approval")
    if approval:
        if approval.get("decision") == "approve":
            return {"next": FINALIZE}
        feedback = approval.get("feedback") or "Improve the report."
        return {
            "plan": plan + revision_steps("human", feedback),
            "approval": None,
            "revision_count": 0,
            "escalated": False,
            "escalation_reason": "",
            "next": "writer",
        }

    review = state.get("review") or {}
    if review and not review.get("approved"):
        issues = "; ".join(review.get("issues") or ["quality below the bar"])
        count = state.get("revision_count", 0)
        if count < max_revisions:
            return {"plan": plan + revision_steps("reviewer", issues), "revision_count": count + 1, "next": "writer"}
        return {
            "escalated": True,
            "escalation_reason": f"The reviewer still reported issues after {count} revision(s): {issues}",
            "next": HUMAN_APPROVAL,
        }
    return {"next": HUMAN_APPROVAL}
