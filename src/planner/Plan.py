"""Plan model for the first Hypatia Planner implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from core.Exceptions import PlannerError
from planner.Goal import Goal
from planner.Task import Task, TaskStatus


@dataclass(slots=True)
class Plan:
    """A goal and its ordered list of tasks."""

    goal: Goal
    plan_id: str = field(default_factory=lambda: str(uuid4()))
    tasks: list[Task] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def add_task(self, task: Task) -> None:
        """Add one task to this plan."""
        if not isinstance(task, Task):
            raise PlannerError("Plan tasks must be Task instances.")
        self.tasks.append(task)

    def task_count(self) -> int:
        """Return the number of tasks in this plan."""
        return len(self.tasks)

    def completed_count(self) -> int:
        """Return the number of completed tasks."""
        return sum(task.status is TaskStatus.COMPLETED for task in self.tasks)

    def pending_count(self) -> int:
        """Return the number of pending tasks."""
        return sum(task.status is TaskStatus.PENDING for task in self.tasks)

    def is_completed(self) -> bool:
        """Return True only when the plan has tasks and all are completed."""
        return bool(self.tasks) and self.completed_count() == self.task_count()
