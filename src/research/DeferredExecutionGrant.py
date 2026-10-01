"""Durable permission for one exact task to be considered automatically later.

Every other named authority domain in this codebase (``ResearchPlanAuthorization``,
``ResearchKaliOperationAuthorization``) carries a hard expiry, because a stale
approval for a sensitive action is a liability even when nobody misuses it on
purpose. This one is the odd member out despite authorizing the highest-stakes
case of the three: fully unattended execution with no human present to notice
anything wrong. ``expires_at`` closes that gap. It is deliberately a derived
property of ``granted_at``, never a stored field: a persisted value could be
set arbitrarily far in the future by whatever wrote the document, while a
value computed from an already-validated, already-immutable timestamp cannot
be engineered to outlive the one fixed rule everyone is held to, including
every grant already on disk before this rule existed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from core.Exceptions import ResearchError
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchPlanDigest import is_plan_digest
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

MAX_DEFERRED_GRANT_ID_CHARACTERS = 200

#: Chosen to match this codebase's one existing consumer's own scheduling
#: horizon (``TrustedOneShotDeferredExecutionScheduler.MAX_ONE_SHOT_DEFERRED_DELAY``,
#: also seven days): a grant is never the reason a one-shot run that was
#: otherwise valid to schedule turns out unrunnable. A structural test asserts
#: the two constants stay in that relationship so they cannot silently drift
#: apart.
MAX_DEFERRED_EXECUTION_GRANT_VALIDITY = timedelta(days=7)


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
    #: What the granted plan already said, written down so a grant can be read
    #: without rebuilding the plan behind its digest.
    #:
    #: ``None`` is not "no restrictions" — it means this record never recorded
    #: them, which is the only truthful reading of a grant written before this
    #: field existed. Typed restrictions arrived one release earlier, so such a
    #: grant may well have covered a restricted plan; claiming it approved none
    #: would be inventing history. An empty frozenset is the different, positive
    #: statement that a grant was made and had none.
    approved_restrictions: frozenset[ResearchPlanRestriction] | None = None
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
        if self.approved_restrictions is not None:
            if not isinstance(self.approved_restrictions, frozenset):
                raise ResearchError(
                    "Deferred execution grant restrictions are invalid."
                )
            if not all(
                isinstance(value, ResearchPlanRestriction)
                for value in self.approved_restrictions
            ):
                raise ResearchError("Deferred execution grant restriction is invalid.")
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

    @property
    def expires_at(self) -> datetime:
        """Return when this exact grant stops being able to authorize anything.

        Computed from ``granted_at``, never stored and never settable: a
        restart that reloads this record computes the identical answer it
        would have given the moment it was granted, so resuming a process
        can neither revive nor extend a grant past its original window.
        """
        return self.granted_at + MAX_DEFERRED_EXECUTION_GRANT_VALIDITY

    def has_expired_at(self, moment: datetime) -> bool:
        """Return whether this grant's validity window has passed."""
        if not isinstance(moment, datetime) or moment.utcoffset() is None:
            raise ResearchError(
                "Deferred execution grant expiry check requires an aware time."
            )
        return moment >= self.expires_at

    @property
    def approved_restrictions_text(self) -> str:
        """Name what this grant records, keeping unknown distinct from none.

        Owned by the grant rather than by any one screen, so every place that
        shows an existing grant says the same thing about it. "none" is the
        claim that a grant was made and carried no restriction; a grant written
        before restrictions were recorded cannot make that claim and says so.
        """
        if self.approved_restrictions is None:
            return "unavailable for legacy grant"
        return (
            ", ".join(sorted(value.value for value in self.approved_restrictions))
            or "none"
        )

    @property
    def records_restrictions(self) -> bool:
        """Return whether this grant states what it was granted under."""
        return self.approved_restrictions is not None

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
