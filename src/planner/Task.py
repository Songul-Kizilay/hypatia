"""Task model used by the first Hypatia Planner implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from core.Exceptions import PlannerError


class TaskStatus(StrEnum):
    """Lifecycle states available to a planned task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Task:
    """One ordered, stateful unit of work in a plan."""

    title: str
    order: int
    task_id: str = field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        if not self.title:
            raise PlannerError("Task title cannot be empty.")
        if self.order < 1:
            raise PlannerError("Task order must be at least 1.")

    def set_status(self, status: TaskStatus) -> None:
        """Update the task lifecycle state and modification timestamp."""
        self.status = status
        self.updated_at = datetime.now(UTC)
