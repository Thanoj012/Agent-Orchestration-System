"""Wires everything together for the worker and the CLI (built once per process)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.agents.factory import build_agents
from app.config import Settings, get_settings
from app.db import get_session_factory, init_db, make_engine
from app.events import make_db_emit
from app.llm import get_llm
from app.memory.store import MemoryStore
from app.orchestration.builder import build_graph
from app.orchestration.planner import make_plan
from app.orchestration.runner import finalize_run, save_state
from app.tools.registry import build_tools


@dataclass
class Container:
    settings: Settings
    session_factory: object
    memory: MemoryStore
    graph: object
    emit: object


@lru_cache
def get_container() -> Container:
    settings = get_settings()
    init_db()
    session_factory = get_session_factory()
    memory = MemoryStore(session_factory, settings.chroma_host, settings.chroma_port)
    tools = build_tools(settings, memory, make_engine(settings.analyst_database_url))
    emit = make_db_emit(session_factory)
    graph = build_graph(
        planner=lambda goal: make_plan(get_llm(settings.model_for("supervisor")), goal),
        agents=build_agents(settings, tools, emit),
        emit=emit,
        persist=lambda run_id, state: save_state(session_factory, run_id, state),
        finalize=lambda state: finalize_run(memory, state),
        max_revisions=settings.max_revisions,
    )
    return Container(settings, session_factory, memory, graph, emit)
