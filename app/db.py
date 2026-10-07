"""PostgreSQL models (SQLAlchemy 2.0) and session helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import JSON, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Run(Base):
    """One orchestration run. `state` is the full graph state, saved after every step."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True, default="queued")
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    requested_by: Mapped[str] = mapped_column(String(64), default="user")
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Event(Base):
    """Append-only activity log: delegations, tool calls, reviews, approvals..."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    agent: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Memory(Base):
    """Source of truth for persistent memory; ChromaDB holds the embeddings for semantic recall."""

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(64), default="General")
    source: Mapped[str] = mapped_column(String(64), default="agent")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def make_engine(url: str):
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def get_engine():
    return make_engine(get_settings().database_url)


@lru_cache
def get_session_factory() -> sessionmaker:
    return sessionmaker(get_engine(), expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(get_engine())
