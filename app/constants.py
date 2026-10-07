"""Shared names and status values."""

AGENTS = ("research", "analyst", "writer", "reviewer")
ROLES = ("supervisor",) + AGENTS

DISPLAY_NAMES = {
    "supervisor": "Supervisor Agent",
    "research": "Research Agent",
    "analyst": "Data Analyst Agent",
    "writer": "Writer Agent",
    "reviewer": "Reviewer Agent",
}

# run statuses
QUEUED = "queued"
RUNNING = "running"
AWAITING_APPROVAL = "awaiting_approval"
COMPLETED = "completed"
FAILED = "failed"
TERMINAL = (COMPLETED, FAILED)

# routing targets used by the supervisor (values of state["next"])
END = "__end__"  # same value as langgraph.graph.END
HUMAN_APPROVAL = "human_approval"
FINALIZE = "finalize"
