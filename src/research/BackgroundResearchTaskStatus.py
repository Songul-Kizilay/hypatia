"""Lifecycle states for one approved background research task.

These are task states, not execution states. A task can be paused while its
execution is perfectly healthy, and an execution can be blocked while its task
is merely pending. The two vocabularies stay separate on purpose.

`INTERRUPTED`, `PAUSED`, and `BLOCKED` mean different things. Interrupted means
the process died while the task was running and what it achieved is unknown.
Paused means a human stopped it deliberately. Blocked is an execution-level
condition and never a task state.
"""

from enum import StrEnum


class BackgroundResearchTaskStatus(StrEnum):
    """Bounded lifecycle for one background research task."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"

    @property
    def terminal(self) -> bool:
        """Return whether this status closes further scheduling."""
        return self in _TERMINAL_TASK_STATUSES

    @property
    def runnable(self) -> bool:
        """Return whether a worker may pick this task up."""
        return self is BackgroundResearchTaskStatus.PENDING


_TERMINAL_TASK_STATUSES = frozenset(
    {
        BackgroundResearchTaskStatus.COMPLETED,
        BackgroundResearchTaskStatus.FAILED,
        BackgroundResearchTaskStatus.CANCELLED,
    }
)
