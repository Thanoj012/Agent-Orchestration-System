from app.constants import END, FINALIZE, HUMAN_APPROVAL
from app.orchestration.planner import make_plan, validate_plan
from app.orchestration.supervisor import decide


def agents(plan):
    return [s["agent"] for s in plan]


def test_plan_shape_is_always_enforced():
    assert agents(validate_plan(None, "g")) == ["research", "analyst", "writer", "reviewer"]
    only_writer = [{"agent": "writer", "instruction": "x"}]
    assert agents(validate_plan(only_writer, "g")) == ["research", "analyst", "writer", "reviewer"]
    plan = validate_plan([{"agent": "reviewer"}, {"agent": "analyst", "instruction": "sql"}, {"agent": "hacker"},
                          {"agent": "analyst"}, "junk"], "g")
    assert agents(plan) == ["analyst", "writer", "reviewer"]          # reviewer can't jump the queue
    assert plan[0]["instruction"] == "sql" and all(s["status"] == "pending" for s in plan)


def test_make_plan_uses_model_output_or_falls_back():
    class LLM:
        def __init__(self, reply):
            self.reply = reply

        def complete(self, system, messages):
            return self.reply

    good = '{"plan": [{"agent": "research", "instruction": "find news"}]}'
    plan = make_plan(LLM(good), "goal")
    assert agents(plan) == ["research", "writer", "reviewer"] and plan[0]["instruction"] == "find news"
    assert agents(make_plan(LLM("no json at all"), "goal")) == ["research", "analyst", "writer", "reviewer"]


def plan_of(*statuses):
    names = ["research", "analyst", "writer", "reviewer"]
    return [{"agent": n, "instruction": "i", "status": s} for n, s in zip(names, statuses, strict=False)]


def test_decide_walks_the_plan_in_order():
    state = {"plan": plan_of("done", "pending", "pending", "pending"), "status": "running"}
    assert decide(state)["next"] == "analyst"


def test_decide_sends_finished_approved_work_to_the_human():
    state = {"plan": plan_of("done", "done", "done", "done"), "review": {"approved": True}, "status": "running"}
    assert decide(state)["next"] == HUMAN_APPROVAL


def test_decide_revises_then_escalates():
    done = plan_of("done", "done", "done", "done")
    bad = {"approved": False, "issues": ["number wrong"]}
    first = decide({"plan": done, "review": bad, "revision_count": 0, "status": "running"}, max_revisions=2)
    assert first["next"] == "writer" and first["revision_count"] == 1
    assert agents(first["plan"])[-2:] == ["writer", "reviewer"] and "number wrong" in first["plan"][-2]["instruction"]
    last = decide({"plan": done, "review": bad, "revision_count": 2, "status": "running"}, max_revisions=2)
    assert last["next"] == HUMAN_APPROVAL and last["escalated"] and "number wrong" in last["escalation_reason"]


def test_decide_handles_human_decisions_and_terminal_states():
    done = plan_of("done", "done", "done", "done")
    approve = {"plan": done, "approval": {"decision": "approve"}, "status": "running"}
    assert decide(approve)["next"] == FINALIZE
    changes = {"plan": done, "approval": {"decision": "request_changes", "feedback": "shorter"}, "status": "running"}
    out = decide(changes)
    assert out["next"] == "writer" and out["approval"] is None and "shorter" in out["plan"][-2]["instruction"]
    assert decide({"plan": done, "status": "completed"})["next"] == END
    assert decide({"plan": done, "status": "failed"})["next"] == END
