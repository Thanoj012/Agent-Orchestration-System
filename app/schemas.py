"""Request bodies for the HTTP API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    goal: str = Field(min_length=10, max_length=2000)
    priority: Literal["low", "normal", "high"] = "normal"
    requested_by: str = Field(default="user", max_length=64)


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "request_changes"]
    feedback: str = Field(default="", max_length=4000)
