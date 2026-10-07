"""Run a graph until it finishes or pauses for a human, persisting state in PostgreSQL."""
from __future__ import annotations

import json
import logging

from app.constants import COMPLETED, FAILED, TERMINAL
from app.db import Run, utcnow
from app.orchestration.state import new_state

log = logging.getLogger(__name__)
RECURSION_LIMIT = 100


def save_state(session_factory, run_id: str, state: dict) -> None:
    with session_factory() as session:
        run = session.get(Run, run_id)
        if run is None:
            return
        run.state = json.loads(json.dumps(state, default=str))  # reassign so SQLAlchemy sees the change
        run.status = state.get("status") or run.status
        run.updated_at = utcnow()
        session.commit()


def load_state(session_factory, run_id: str) -> tuple[str, dict]:
    with session_factory() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        return run.goal, dict(run.state or {})


def finalize_run(memory, state: dict) -> None:
    """After human approval, remember the report so future runs can build on it."""
    memory.save(
        title=f"Report: {state['goal'][:120]}",
        content=state.get("draft", ""),
        category="Reports",
        source=f"run:{state['run_id']}",
    )


def advance_run(run_id: str, *, session_factory, graph, emit) -> str:
    """Start a queued run, or resume one after a human decision. Returns the resulting status."""
    goal, state = load_state(session_factory, run_id)
    if state.get("status") in TERMINAL:
        return state["status"]
    if not state:
        state = new_state(run_id, goal)
        emit(run_id, "supervisor", "run_started", f"Started: {goal[:200]}", {})
    else:
        emit(run_id, "supervisor", "run_resumed", "Run resumed", {})
    state["run_id"] = run_id

    try:
        final = graph.invoke(state, {"recursion_limit": RECURSION_LIMIT})
    except Exception as exc:  # noqa: BLE001
        log.exception("run %s failed", run_id)
        emit(run_id, "supervisor", "failed", f"{type(exc).__name__}: {exc}", {})
        _, latest = load_state(session_factory, run_id)
        latest.update(status=FAILED, error=str(exc))
        save_state(session_factory, run_id, latest)
        return FAILED

    save_state(session_factory, run_id, dict(final))
    return final.get("status", COMPLETED)
