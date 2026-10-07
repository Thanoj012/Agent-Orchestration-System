"""Activity log writer. Logging must never be able to crash a run."""
from __future__ import annotations

import logging

from app.db import Event

log = logging.getLogger(__name__)


def make_db_emit(session_factory):
    def emit(run_id: str, agent: str, kind: str, message: str, data: dict | None = None) -> None:
        try:
            with session_factory() as session:
                session.add(Event(run_id=run_id, agent=agent, kind=kind, message=message[:2000], data=data or {}))
                session.commit()
        except Exception:  # noqa: BLE001
            log.exception("failed to write event %s for run %s", kind, run_id)

    return emit
