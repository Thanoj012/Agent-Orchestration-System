"""FastAPI backend for the dashboard: create runs, watch them, approve or reject drafts."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import func, select

from app.config import get_settings
from app.constants import AWAITING_APPROVAL, RUNNING
from app.db import Event, Run, get_session_factory, init_db, utcnow
from app.events import make_db_emit
from app.memory.store import MemoryStore
from app.schemas import ApprovalDecision, RunCreate
from app.service import ApprovalError, apply_decision, create_run
from app.tools.catalog import AGENT_TOOLS, TOOL_CATALOG
from app.views import agent_cards

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="OrchestrAI", version="0.1.0", lifespan=lifespan,
              description="Multi-agent orchestration with tools, persistent memory and human approval.")


def _sf():
    return get_session_factory()


def _enqueue(run_id: str) -> None:
    from app.worker import advance_run_task

    advance_run_task.delay(run_id)


def _run_row(run: Run) -> dict:
    return {
        "id": run.id, "goal": run.goal, "status": run.status, "priority": run.priority,
        "requested_by": run.requested_by, "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }


def _event_row(e: Event) -> dict:
    return {"id": e.id, "ts": e.ts.isoformat(), "agent": e.agent, "kind": e.kind, "message": e.message, "data": e.data}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/runs", status_code=201)
def post_run(body: RunCreate) -> dict:
    run_id = create_run(_sf(), body.goal, body.priority, body.requested_by)
    try:
        _enqueue(run_id)
    except Exception as exc:  # noqa: BLE001 - Redis down etc.
        make_db_emit(_sf())(run_id, "supervisor", "failed", f"Could not queue the run: {exc}")
        with _sf()() as session:
            session.get(Run, run_id).status = "failed"
            session.commit()
        raise HTTPException(503, "Task queue unavailable") from exc
    return {"id": run_id, "status": "queued"}


@app.get("/runs")
def list_runs(limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    with _sf()() as session:
        rows = session.execute(select(Run).order_by(Run.created_at.desc()).limit(limit)).scalars().all()
    return [_run_row(r) for r in rows]


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    with _sf()() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise HTTPException(404, "run not found")
        events = session.execute(
            select(Event).where(Event.run_id == run_id).order_by(Event.id).limit(1000)
        ).scalars().all()
        state = dict(run.state or {})
        row = _run_row(run)
    events_out = [_event_row(e) for e in events]
    cards = agent_cards(state, events_out)
    for card in cards:
        card["model"] = settings.model_for(card["agent"])
    return {
        **row,
        "plan": state.get("plan", []),
        "results": state.get("results", {}),
        "draft": state.get("draft", ""),
        "review": state.get("review"),
        "escalated": state.get("escalated", False),
        "escalation_reason": state.get("escalation_reason", ""),
        "error": state.get("error", ""),
        "cards": cards,
        "events": events_out,
    }


@app.post("/runs/{run_id}/approval")
def post_approval(run_id: str, body: ApprovalDecision) -> dict:
    try:
        apply_decision(_sf(), run_id, body.decision, body.feedback)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ApprovalError as exc:
        raise HTTPException(409 if "not awaiting" in str(exc) else 422, str(exc)) from exc
    try:
        _enqueue(run_id)
    except Exception as exc:  # noqa: BLE001 - put the request back so the human can retry
        with _sf()() as session:
            run = session.get(Run, run_id)
            state = dict(run.state or {})
            state.update(approval=None, status=AWAITING_APPROVAL)
            run.state, run.status, run.updated_at = state, AWAITING_APPROVAL, utcnow()
            session.commit()
        raise HTTPException(503, "Task queue unavailable; the request was not applied") from exc
    return {"id": run_id, "status": RUNNING}


@app.get("/approvals")
def list_approvals() -> list[dict]:
    with _sf()() as session:
        rows = session.execute(
            select(Run).where(Run.status == AWAITING_APPROVAL).order_by(Run.updated_at)
        ).scalars().all()
    return [
        {**_run_row(r), "draft": (r.state or {}).get("draft", ""), "review": (r.state or {}).get("review"),
         "escalated": (r.state or {}).get("escalated", False),
         "escalation_reason": (r.state or {}).get("escalation_reason", "")}
        for r in rows
    ]


@app.get("/stats")
def stats() -> dict:
    with _sf()() as session:
        rows = session.execute(select(Run.status, func.count()).group_by(Run.status)).all()
    return {status: count for status, count in rows}


@app.get("/memory")
def get_memory(q: str = "", limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    store = MemoryStore(_sf(), settings.chroma_host, settings.chroma_port)
    try:
        return store.search(q, k=min(limit, 10)) if q.strip() else store.recent(limit)
    except Exception as exc:  # noqa: BLE001 - e.g. ChromaDB not reachable
        raise HTTPException(503, f"Memory search unavailable: {exc}") from exc


@app.get("/tools")
def list_tools() -> list[dict]:
    return [
        {
            "name": name,
            "description": meta["description"],
            "used_by": [agent for agent, names in AGENT_TOOLS.items() if name in names],
            "configured": _tool_configured(name),
        }
        for name, meta in TOOL_CATALOG.items()
    ]


def _tool_configured(name: str) -> bool:
    if name == "web_search":
        return bool(settings.tavily_api_key)
    if name == "http_get":
        return bool(settings.http_allowed_hosts)
    return True
