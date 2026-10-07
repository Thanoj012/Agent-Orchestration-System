"""Assemble the LangGraph state machine.

    START -> supervisor -> {research | analyst | writer | reviewer} -> supervisor -> ...
                        -> human_approval -> END   (waits for a human; run resumes later)
                        -> finalize       -> END
"""
from __future__ import annotations

from langgraph.graph import END as LG_END
from langgraph.graph import START, StateGraph

from app.agents.result import AgentResult
from app.constants import END, FINALIZE, HUMAN_APPROVAL, RUNNING, TERMINAL
from app.orchestration.state import RunState
from app.orchestration.supervisor import decide


def build_graph(*, planner, agents: dict, emit, persist, finalize, max_revisions: int = 2):
    """
    planner(goal) -> plan            agents[name](state, step) -> AgentResult
    emit(run_id, agent, kind, message, data=None)
    persist(run_id, state)           called after every node so progress survives crashes
    finalize(state)                  called once when a human approves (e.g. save to memory)
    """

    def persisted(fn):
        def node(state):
            updates = fn(state)
            persist(state["run_id"], {**state, **updates})
            return updates

        return node

    def supervisor(state):
        run_id, view, updates = state["run_id"], dict(state), {}
        if not view.get("plan"):
            plan = planner(view["goal"])
            updates["plan"] = view["plan"] = plan
            emit(run_id, "supervisor", "plan", "Plan: " + " -> ".join(s["agent"] for s in plan), {"plan": plan})
        if view.get("status") not in TERMINAL:
            updates["status"] = view["status"] = RUNNING
        decision = decide(view, max_revisions)
        updates.update(decision)
        if "plan" in decision:
            kind = "human" if decision.get("approval", 1) is None else "reviewer"
            emit(run_id, "supervisor", "revision", f"Revision requested by {kind}", {})
        nxt = decision["next"]
        if nxt in agents:
            step = next(s for s in updates.get("plan", view["plan"]) if s["agent"] == nxt and s["status"] == "pending")
            emit(run_id, "supervisor", "delegation", f"Delegated to {nxt}: {step['instruction'][:300]}", {"agent": nxt})
        return updates

    def make_agent_node(name):
        def node(state):
            run_id = state["run_id"]
            plan = [dict(step) for step in state["plan"]]
            index = next(i for i, s in enumerate(plan) if s["agent"] == name and s["status"] == "pending")
            emit(run_id, name, "agent_started", plan[index]["instruction"][:500])
            try:
                result: AgentResult = agents[name](state, plan[index])
            except Exception as exc:  # noqa: BLE001 - any agent failure fails the run with a clear message
                emit(run_id, name, "failed", f"{type(exc).__name__}: {exc}")
                return {"status": "failed", "error": f"{name} agent failed: {exc}"}
            plan[index]["status"] = "done"
            updates = {"plan": plan, "results": {**state.get("results", {}), name: result.output}}
            if name == "writer":
                updates["draft"], updates["review"] = result.output, None
            if name == "reviewer":
                updates["review"] = result.review
                verdict = "approved" if (result.review or {}).get("approved") else "found issues"
                emit(run_id, name, "review", f"Reviewer {verdict}", result.review or {})
            emit(run_id, name, "agent_finished", result.output[:300], {"tool_calls": result.tool_calls})
            return updates

        return node

    def human_approval(state):
        run_id = state["run_id"]
        if state.get("escalated"):
            emit(run_id, "supervisor", "escalation", state.get("escalation_reason", "Escalated to a human"), {})
        emit(run_id, "supervisor", "approval_requested", "Draft is ready for human approval", {})
        return {"status": "awaiting_approval"}

    def finalize_node(state):
        try:
            finalize(state)
        except Exception as exc:  # noqa: BLE001 - failing to save memory must not undo an approval
            emit(state["run_id"], "supervisor", "warning", f"Could not save to memory: {exc}", {})
        emit(state["run_id"], "supervisor", "completed", "Run completed", {})
        return {"status": "completed"}

    graph = StateGraph(RunState)
    graph.add_node("supervisor", persisted(supervisor))
    for name in agents:
        graph.add_node(name, persisted(make_agent_node(name)))
    graph.add_node(HUMAN_APPROVAL, persisted(human_approval))
    graph.add_node(FINALIZE, persisted(finalize_node))

    graph.add_edge(START, "supervisor")
    routes = {name: name for name in agents}
    routes.update({HUMAN_APPROVAL: HUMAN_APPROVAL, FINALIZE: FINALIZE, END: LG_END})
    graph.add_conditional_edges("supervisor", lambda state: state["next"], routes)
    for name in agents:
        graph.add_edge(name, "supervisor")
    graph.add_edge(HUMAN_APPROVAL, LG_END)
    graph.add_edge(FINALIZE, LG_END)
    return graph.compile()
