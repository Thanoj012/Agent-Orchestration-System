"""End-to-end behaviour of the LangGraph state machine with fake agents (no LLM, no database)."""
from app.agents.result import AgentResult
from app.orchestration.builder import build_graph
from app.orchestration.planner import validate_plan
from app.orchestration.state import new_state

CONFIG = {"recursion_limit": 100}


class Harness:
    def __init__(self, reviews, fail_agent=None):
        self.calls, self.events, self.saved, self.finalized = [], [], {}, []
        self.reviews = list(reviews)
        self.fail_agent = fail_agent

        def make(name):
            def run(state, step):
                self.calls.append((name, step["instruction"]))
                if name == self.fail_agent:
                    raise RuntimeError("boom")
                if name == "writer":
                    return AgentResult(f"draft v{sum(1 for c in self.calls if c[0] == 'writer')}")
                if name == "reviewer":
                    return AgentResult("verdict", review=self.reviews.pop(0))
                return AgentResult(f"{name} findings", tool_calls=1)

            return run

        def emit(run_id, agent, kind, message, data=None):
            self.events.append((agent, kind))

        self.graph = build_graph(
            planner=lambda goal: validate_plan(None, goal),
            agents={n: make(n) for n in ("research", "analyst", "writer", "reviewer")},
            emit=emit,
            persist=lambda run_id, state: self.saved.__setitem__(run_id, state),
            finalize=self.finalized.append,
            max_revisions=2,
        )

    def run(self, state):
        return self.graph.invoke(state, CONFIG)

    def names(self):
        return [name for name, _ in self.calls]


GOOD = {"approved": True, "issues": []}
BAD = {"approved": False, "issues": ["number is wrong"]}


def test_happy_path_pauses_for_human_then_completes():
    h = Harness([GOOD])
    state = h.run(new_state("r1", "make a report"))
    assert h.names() == ["research", "analyst", "writer", "reviewer"]
    assert state["status"] == "awaiting_approval" and state["draft"] == "draft v1"
    assert h.saved["r1"]["status"] == "awaiting_approval"      # state is persisted for the resume
    assert h.finalized == []

    resumed = h.run({**state, "approval": {"decision": "approve", "feedback": ""}})
    assert resumed["status"] == "completed" and len(h.finalized) == 1
    assert h.names() == ["research", "analyst", "writer", "reviewer"]   # nothing re-ran
    assert ("supervisor", "completed") in h.events


def test_reviewer_rejection_triggers_a_revision_round():
    h = Harness([BAD, GOOD])
    state = h.run(new_state("r2", "goal"))
    assert h.names() == ["research", "analyst", "writer", "reviewer", "writer", "reviewer"]
    assert "number is wrong" in h.calls[4][1]                 # the writer saw the reviewer's issues
    assert state["status"] == "awaiting_approval" and not state["escalated"]
    assert state["draft"] == "draft v2"


def test_persistent_rejection_escalates_to_a_human():
    h = Harness([BAD, BAD, BAD])
    state = h.run(new_state("r3", "goal"))
    assert h.names().count("writer") == 3                     # first draft + 2 automatic revisions
    assert state["escalated"] and "number is wrong" in state["escalation_reason"]
    assert state["status"] == "awaiting_approval"
    assert ("supervisor", "escalation") in h.events


def test_human_can_request_changes_and_the_loop_continues():
    h = Harness([GOOD, GOOD])
    state = h.run(new_state("r4", "goal"))
    changes = {"decision": "request_changes", "feedback": "make it shorter"}
    state = h.run({**state, "approval": changes, "status": "running"})
    assert h.names()[-2:] == ["writer", "reviewer"]
    assert "make it shorter" in h.calls[-2][1]
    assert state["status"] == "awaiting_approval" and state["approval"] is None
    assert state["draft"] == "draft v2"


def test_agent_failure_fails_the_run_cleanly():
    h = Harness([], fail_agent="analyst")
    state = h.run(new_state("r5", "goal"))
    assert state["status"] == "failed" and "boom" in state["error"]
    assert h.names() == ["research", "analyst"]               # nothing after the failure ran
    assert ("analyst", "failed") in h.events


def test_resuming_a_partly_finished_run_skips_completed_steps():
    h = Harness([GOOD])
    fresh = new_state("r6", "goal")
    fresh["plan"] = validate_plan(None, "goal")
    fresh["plan"][0]["status"] = "done"
    fresh["results"] = {"research": "earlier findings"}
    h.run(fresh)
    assert h.names() == ["analyst", "writer", "reviewer"]      # research was not repeated
