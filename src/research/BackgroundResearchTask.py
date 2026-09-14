"""One approved background research task.

A task is scheduling bookkeeping around an already-approved execution. It owns
no research content: the execution owns its steps and the research run owns
every source, evidence record, assessment, claim, and contradiction.

Every transition returns a new immutable task and refuses an invalid one, so a
cancelled task can never restart and a completed task can never be re-run.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from core.Exceptions import ResearchError
from research.BackgroundResearchTaskStatus import BackgroundResearchTaskStatus
from research.ResearchAutonomyBudget import ResearchAutonomyBudget

MAX_BACKGROUND_TASK_ID_CHARACTERS = 200
MAX_BACKGROUND_TASK_RETRIES = 5
MAX_BACKGROUND_TASK_CAUSE_CHARACTERS = 200


@dataclass(frozen=True, slots=True)
class BackgroundResearchTask:
    """Scheduling state for one approved execution."""

    task_id: str
    execution_id: str
    budget: ResearchAutonomyBudget
    created_at: datetime
    updated_at: datetime
    status: BackgroundResearchTaskStatus = BackgroundResearchTaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 1
    outcome: str = ""
    failure_cause: str = ""

    def __post_init__(self) -> None:
        for value, label in (
            (self.task_id, "task ID"),
            (self.execution_id, "execution ID"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"Background task {label} cannot be empty.")
            if len(value.strip()) > MAX_BACKGROUND_TASK_ID_CHARACTERS:
                raise ResearchError(f"Background task {label} is too long.")
        if not isinstance(self.budget, ResearchAutonomyBudget):
            raise ResearchError("Background task budget is invalid.")
        if not isinstance(self.status, BackgroundResearchTaskStatus):
            raise ResearchError("Background task status is invalid.")
        for count, count_label in (
            (self.retry_count, "retry count"),
            (self.max_retries, "retry limit"),
        ):
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ResearchError(
                    f"Background task {count_label} must be a non-negative integer."
                )
            if count > MAX_BACKGROUND_TASK_RETRIES:
                raise ResearchError(
                    f"Background task {count_label} exceeds its ceiling."
                )
        if self.retry_count > self.max_retries:
            raise ResearchError("Background task retry count exceeds its limit.")
        for value, label in (
            (self.outcome, "outcome"),
            (self.failure_cause, "failure cause"),
        ):
            if not isinstance(value, str):
                raise ResearchError(f"Background task {label} must be text.")
            if len(value.strip()) > MAX_BACKGROUND_TASK_CAUSE_CHARACTERS:
                raise ResearchError(f"Background task {label} is too long.")
        for moment, moment_label in (
            (self.created_at, "creation time"),
            (self.updated_at, "update time"),
        ):
            if not isinstance(moment, datetime) or moment.utcoffset() is None:
                raise ResearchError(
                    f"Background task {moment_label} must be timezone-aware."
                )
        object.__setattr__(self, "task_id", self.task_id.strip())
        object.__setattr__(self, "execution_id", self.execution_id.strip())
        object.__setattr__(self, "outcome", self.outcome.strip())
        object.__setattr__(self, "failure_cause", self.failure_cause.strip())

    @property
    def retries_remaining(self) -> int:
        return max(self.max_retries - self.retry_count, 0)

    def started(self, at: datetime) -> BackgroundResearchTask:
        """Claim a pending task for one worker cycle."""
        self._require(BackgroundResearchTaskStatus.PENDING, "started")
        return replace(
            self,
            status=BackgroundResearchTaskStatus.RUNNING,
            updated_at=at,
        )

    def completed(self, outcome: str, at: datetime) -> BackgroundResearchTask:
        """Record a task whose execution finished."""
        self._require(BackgroundResearchTaskStatus.RUNNING, "completed")
        return replace(
            self,
            status=BackgroundResearchTaskStatus.COMPLETED,
            outcome=outcome,
            updated_at=at,
        )

    def failed(
        self,
        outcome: str,
        at: datetime,
        failure_cause: str = "",
    ) -> BackgroundResearchTask:
        """Record a task that stopped for a non-retryable reason."""
        self._require(BackgroundResearchTaskStatus.RUNNING, "failed")
        return replace(
            self,
            status=BackgroundResearchTaskStatus.FAILED,
            outcome=outcome,
            failure_cause=failure_cause,
            updated_at=at,
        )

    def retry_scheduled(self, outcome: str, at: datetime) -> BackgroundResearchTask:
        """Return a running task to pending for one more bounded attempt."""
        self._require(BackgroundResearchTaskStatus.RUNNING, "retried")
        if self.retries_remaining == 0:
            raise ResearchError("Background task has no retries remaining.")
        return replace(
            self,
            status=BackgroundResearchTaskStatus.PENDING,
            retry_count=self.retry_count + 1,
            outcome=outcome,
            updated_at=at,
        )

    def paused(self, at: datetime) -> BackgroundResearchTask:
        """Stop scheduling a pending task until a human resumes it."""
        self._require(BackgroundResearchTaskStatus.PENDING, "paused")
        return replace(
            self,
            status=BackgroundResearchTaskStatus.PAUSED,
            updated_at=at,
        )

    def resumed(self, at: datetime) -> BackgroundResearchTask:
        """Return a paused task to the queue."""
        self._require(BackgroundResearchTaskStatus.PAUSED, "resumed")
        return replace(
            self,
            status=BackgroundResearchTaskStatus.PENDING,
            updated_at=at,
        )

    def cancelled(self, at: datetime) -> BackgroundResearchTask:
        """Close a task permanently; a cancelled task never restarts."""
        if self.status.terminal:
            raise ResearchError("Background task is already in a terminal status.")
        return replace(
            self,
            status=BackgroundResearchTaskStatus.CANCELLED,
            updated_at=at,
        )

    def interrupted(self, at: datetime) -> BackgroundResearchTask:
        """Record that the process died while this task was running."""
        if self.status is not BackgroundResearchTaskStatus.RUNNING:
            raise ResearchError("Only a running background task can be interrupted.")
        return replace(
            self,
            status=BackgroundResearchTaskStatus.INTERRUPTED,
            updated_at=at,
        )

    def _require(
        self,
        status: BackgroundResearchTaskStatus,
        action: str,
    ) -> None:
        if self.status is not status:
            raise ResearchError(
                f"Background task cannot be {action} from " f"'{self.status.value}'."
            )
