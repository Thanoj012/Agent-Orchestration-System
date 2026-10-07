"""Command line tools:  python -m app.cli {init-db | seed-memory | run "<goal>"}

`run` executes a whole run in this process (no Celery / API needed) and asks for the
human approval in the terminal - handy for trying the system without the dashboard.
"""
from __future__ import annotations

import argparse

from app.config import get_settings
from app.constants import AWAITING_APPROVAL, COMPLETED

DEMO_MEMORIES = [
    ("Q2_2025_Product_Insight", "Product",
     "Beacon was the fastest-growing product in Q2 2025 while Compass lost users for a third quarter in a row. "
     "Atlas remains the largest product by revenue with steadily improving churn."),
    ("Competitor_Analysis_Notes", "Research",
     "Competitors are bundling AI assistants into their core products. Pricing pressure is strongest in the "
     "mid-market segment where Compass competes."),
    ("User_Growth_Trends", "Analytics",
     "Growth is concentrated in newer products. Churn is the key risk metric to watch for Compass."),
    ("Meeting_Summary_April", "General",
     "Leadership asked for quarterly product reports to include churn, support load and concrete recommendations."),
]


def _init_db(_args) -> None:
    from app.db import init_db

    init_db()
    print("Tables created.")


def _seed_memory(_args) -> None:
    from app.db import get_session_factory, init_db
    from app.memory.store import MemoryStore

    init_db()
    s = get_settings()
    store = MemoryStore(get_session_factory(), s.chroma_host, s.chroma_port)
    for title, category, content in DEMO_MEMORIES:
        print(f"saved memory #{store.save(title, content, category, source='seed')}: {title}")


def _run(args) -> None:
    from app.container import get_container
    from app.orchestration.runner import advance_run, load_state
    from app.service import apply_decision, create_run

    c = get_container()
    run_id = create_run(c.session_factory, args.goal, requested_by="cli")
    print(f"Run {run_id} started...\n")
    while True:
        status = advance_run(run_id, session_factory=c.session_factory, graph=c.graph, emit=c.emit)
        _, state = load_state(c.session_factory, run_id)
        if status != AWAITING_APPROVAL:
            break
        print("=" * 72, "\nDRAFT FOR APPROVAL\n" + "=" * 72)
        print(state.get("draft", ""))
        review = state.get("review") or {}
        if review:
            print(f"\nReviewer: approved={review.get('approved')} issues={review.get('issues')}")
        if state.get("escalated"):
            print(f"ESCALATED: {state.get('escalation_reason')}")
        choice = input("\n[a]pprove / [c]hanges / [q]uit > ").strip().lower()
        if choice.startswith("a"):
            apply_decision(c.session_factory, run_id, "approve")
        elif choice.startswith("c"):
            apply_decision(c.session_factory, run_id, "request_changes", input("What should change? > "))
        else:
            print("Left awaiting approval; resume from the dashboard.")
            return
    print(f"\nFinished with status: {status}")
    if status == COMPLETED:
        print("The approved report was saved to persistent memory.")
    elif state.get("error"):
        print(f"Error: {state['error']}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="create the PostgreSQL tables").set_defaults(func=_init_db)
    sub.add_parser("seed-memory", help="add a few demo memories").set_defaults(func=_seed_memory)
    p = sub.add_parser("run", help="run one goal end-to-end in this process")
    p.add_argument("goal")
    p.set_defaults(func=_run)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
