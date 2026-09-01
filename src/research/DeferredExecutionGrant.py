"""Durable permission for one exact task to be considered automatically later."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from core.Exceptions import ResearchError
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchPlanDigest import is_plan_digest
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

MAX_DEFERRED_GRANT_ID_CHARACTERS = 200


@dataclass(frozen=True, slots=True)
class DeferredExecutionGrant:
    """Bind trusted-desktop confirmation to existing, narrower authority."""

    grant_id: str
    task_id: str
    execution_id: str
    plan_digest: str
    capabilities: frozenset[ResearchPlanStepCapability]
    task_budget: ResearchAutonomyBudget
    granted_at: datetime
    granted_by: DeferredGrantAuthorizer
    revoked_at: datetime | None = None
    revoked_by: DeferredGrantAuthorizer | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.grant_id, "grant ID"),
            (self.task_id, "task ID"),
            (self.execution_id, "execution ID"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"Deferred execution {label} cannot be empty.")
            if len(value.strip()) > MAX_DEFERRED_GRANT_ID_CHARACTERS:
                raise ResearchError(f"Deferred execution {label} is too long.")
        if not is_plan_digest(self.plan_digest):
            raise ResearchError("Deferred execution grant plan digest is invalid.")
        if not isinstance(self.capabilities, frozenset) or not self.capabilities:
            raise ResearchError("Deferred execution grant capabilities are invalid.")
        if not all(
            isinstance(value, ResearchPlanStepCapability) for value in self.capabilities
        ):
            raise ResearchError("Deferred execution grant capability is invalid.")
        if not isinstance(self.task_budget, ResearchAutonomyBudget):
            raise ResearchError("Deferred execution grant task budget is invalid.")
        if not isinstance(self.granted_by, DeferredGrantAuthorizer):
            raise ResearchError("Deferred execution grant provenance is invalid.")
        self._aware(self.granted_at, "grant time")
        if (self.revoked_at is None) != (self.revoked_by is None):
            raise ResearchError("Deferred execution revocation is incomplete.")
        if self.revoked_at is not None:
            self._aware(self.revoked_at, "revocation time")
            if self.revoked_at < self.granted_at:
                raise ResearchError("Deferred execution revocation predates its grant.")
            if not isinstance(self.revoked_by, DeferredGrantAuthorizer):
                raise ResearchError(
                    "Deferred execution revocation provenance is invalid."
                )
        object.__setattr__(self, "grant_id", self.grant_id.strip())
        object.__setattr__(self, "task_id", self.task_id.strip())
        object.__setattr__(self, "execution_id", self.execution_id.strip())

    @property
    def active(self) -> bool:
        return self.revoked_at is None

    def revoked(
        self,
        at: datetime,
        by: DeferredGrantAuthorizer,
    ) -> DeferredExecutionGrant:
        if not self.active:
            raise ResearchError("Deferred execution grant is already revoked.")
        return replace(self, revoked_at=at, revoked_by=by)

    @staticmethod
    def _aware(value: datetime, label: str) -> None:
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError(f"Deferred execution {label} must be timezone-aware.")
