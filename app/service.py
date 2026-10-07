"""Run lifecycle operations shared by the API and the CLI."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.constants import AWAITING_APPROVAL, QUEUED, RUNNING
from app.db import Event, Run, utcnow

DECISIONS = ("approve", "request_changes")


class ApprovalError(Exception):
    """The approval could not be applied (wrong state, missing feedback...)."""


def create_run(session_factory, goal: str, priority: str = "normal", requested_by: str = "user") -> str:
    run_id = str(uuid.uuid4())
    with session_factory() as session:
        session.add(Run(id=run_id, goal=goal.strip(), status=QUEUED, priority=priority, requested_by=requested_by, state={}))
        session.commit()
    return run_id


def apply_decision(session_factory, run_id: str, decision: str, feedback: str = "") -> None:
    """Record the human's decision and flip the run back to `running`.

    The row is locked (SELECT ... FOR UPDATE) so a double click or two reviewers
    cannot apply two decisions to the same approval request.
    """
    if decision not in DECISIONS:
        raise ApprovalError(f"decision must be one of {DECISIONS}")
    if decision == "request_changes" and not feedback.strip():
        raise ApprovalError("feedback is required when requesting changes")

    with session_factory() as session:
        run = session.execute(select(Run).where(Run.id == run_id).with_for_update()).scalar_one_or_none()
        if run is None:
            raise LookupError(f"run {run_id} not found")
        if run.status != AWAITING_APPROVAL:
            raise ApprovalError(f"run is '{run.status}', not awaiting approval")
        state = dict(run.state or {})
        state["approval"] = {"decision": decision, "feedback": feedback.strip()}
        state["status"] = RUNNING
        run.state, run.status, run.updated_at = state, RUNNING, utcnow()
        message = "Approved the draft" if decision == "approve" else f"Requested changes: {feedback.strip()}"
        session.add(Event(run_id=run_id, agent="human", kind="approval", message=message[:2000], data={"decision": decision}))
        session.commit()
