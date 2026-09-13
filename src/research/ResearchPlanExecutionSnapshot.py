"""Durable snapshot of one research-plan execution.

Deliberately narrower than the in-memory `ResearchPlanExecutionState`. It keeps
what is needed to report and resume honestly — step identity, declared
capability, status, operation identity, `work_performed`, bounded detail, the
plan question, and the bound run identity — and nothing that already lives in
the research run.

Fetched page bodies, source excerpts, authored notes, claim text, and
authorization payloads are never stored here. Duplicating them would create a
second store of facts the run already owns.

A snapshot is a record of what happened, not a running execution. Restoring one
never resumes work by itself, and a step recorded as running when the process
died is restored as interrupted rather than as completed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAttemptRecovery import ResearchAttemptRecovery
from research.ResearchAttemptResolution import ResearchAttemptResolution
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint
from research.ResearchMissionScope import ResearchMissionScope
from research.ResearchPlanDigest import is_plan_digest
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepStatus import ResearchPlanStepStatus

MAX_SNAPSHOT_STEPS = 20
MAX_SNAPSHOT_DETAIL_CHARACTERS = 500
MAX_SNAPSHOT_QUESTION_CHARACTERS = 2_000


@dataclass(frozen=True, slots=True)
class ResearchPlanExecutionStepSnapshot:
    """One durable step record."""

    step_id: str
    capability: ResearchPlanStepCapability
    status: ResearchPlanStepStatus
    detail: str = ""
    operation: str = ""
    work_performed: bool = False
    #: The human ruling, kept durable so a restart restores what an operator
    #: decided rather than asking them to decide it again.
    resolution: ResearchAttemptResolution = ResearchAttemptResolution.NONE
    #: What a person did about an unseen attempt, kept so their decision and
    #: their account of it both survive a restart.
    recovery: ResearchAttemptRecovery | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, str) or not self.step_id.strip():
            raise ResearchError("Execution snapshot step ID cannot be empty.")
        if not isinstance(self.capability, ResearchPlanStepCapability):
            raise ResearchError("Execution snapshot step capability is invalid.")
        if not isinstance(self.status, ResearchPlanStepStatus):
            raise ResearchError("Execution snapshot step status is invalid.")
        if not isinstance(self.detail, str) or not isinstance(self.operation, str):
            raise ResearchError("Execution snapshot step text is invalid.")
        if not isinstance(self.work_performed, bool):
            raise ResearchError("Execution snapshot work flag is invalid.")
        if len(self.detail.strip()) > MAX_SNAPSHOT_DETAIL_CHARACTERS:
            raise ResearchError("Execution snapshot step detail is too long.")
        if self.work_performed and not self.operation.strip():
            raise ResearchError(
                "Recorded work in an execution snapshot must name its operation."
            )
        object.__setattr__(self, "step_id", self.step_id.strip())
        object.__setattr__(self, "detail", self.detail.strip())
        object.__setattr__(self, "operation", self.operation.strip())


@dataclass(frozen=True, slots=True)
class ResearchPlanExecutionSnapshot:
    """One durable execution record."""

    plan_id: str
    question: str
    status: ResearchPlanExecutionStatus
    steps: tuple[ResearchPlanExecutionStepSnapshot, ...]
    recorded_at: datetime
    detail: str = ""
    research_run_id: str | None = None
    allowance: ResearchExecutionAllowance | None = None
    #: Full canonical plan identity, including program, scope and every step.
    #: Legacy snapshots did not record this proof and must not imply one.
    target_plan_digest: str | None = None
    mission_plan_digest: str | None = None
    #: New snapshots retain the exact semantic scope and its non-content
    #: predecessor checkpoint. Older mission snapshots lack these fields and
    #: therefore remain reportable but deliberately cannot auto-resume.
    mission_scope: ResearchMissionScope | None = None
    mission_disclosure: ResearchDisclosure = ResearchDisclosure.NONE
    mission_checkpoint: ResearchMissionRecoveryCheckpoint | None = None

    def __post_init__(self) -> None:
        if self.target_plan_digest is not None and self.mission_plan_digest is not None:
            raise ResearchError(
                "Target and reference mission digests cannot be combined."
            )
        if not isinstance(self.mission_disclosure, ResearchDisclosure):
            raise ResearchError("Execution snapshot mission disclosure is invalid.")
        if self.mission_scope is None:
            if (
                self.mission_disclosure is not ResearchDisclosure.NONE
                or self.mission_checkpoint is not None
            ):
                raise ResearchError("Execution snapshot mission recovery is invalid.")
        elif (
            self.mission_plan_digest is None
            or self.mission_scope.semantic_policy is None
            or self.mission_scope.semantic_policy.disclosure
            is not self.mission_disclosure
            or (
                self.mission_checkpoint is not None
                and not isinstance(
                    self.mission_checkpoint, ResearchMissionRecoveryCheckpoint
                )
            )
        ):
            raise ResearchError("Execution snapshot mission recovery is invalid.")
        if self.mission_plan_digest is not None and not is_plan_digest(
            self.mission_plan_digest
        ):
            raise ResearchError("Execution snapshot mission digest is invalid.")
        if self.target_plan_digest is not None and not is_plan_digest(
            self.target_plan_digest
        ):
            raise ResearchError("Execution snapshot target plan digest is invalid.")
        if not isinstance(self.plan_id, str) or not self.plan_id.strip():
            raise ResearchError("Execution snapshot plan ID cannot be empty.")
        if self.allowance is not None and not isinstance(
            self.allowance, ResearchExecutionAllowance
        ):
            raise ResearchError("Execution snapshot allowance is invalid.")
        if not isinstance(self.question, str) or not self.question.strip():
            raise ResearchError("Execution snapshot question cannot be empty.")
        if len(self.question.strip()) > MAX_SNAPSHOT_QUESTION_CHARACTERS:
            raise ResearchError("Execution snapshot question is too long.")
        if not isinstance(self.status, ResearchPlanExecutionStatus):
            raise ResearchError("Execution snapshot status is invalid.")
        if not isinstance(self.steps, tuple) or not self.steps:
            raise ResearchError("Execution snapshot requires step records.")
        if len(self.steps) > MAX_SNAPSHOT_STEPS:
            raise ResearchError("Execution snapshot has too many steps.")
        if not all(
            isinstance(step, ResearchPlanExecutionStepSnapshot) for step in self.steps
        ):
            raise ResearchError("Execution snapshot contains an invalid step.")
        step_ids = tuple(step.step_id for step in self.steps)
        if len(step_ids) != len(set(step_ids)):
            raise ResearchError("Execution snapshot has duplicate step IDs.")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError("Execution snapshot timestamp must be timezone-aware.")
        if not isinstance(self.detail, str):
            raise ResearchError("Execution snapshot detail is invalid.")
        if len(self.detail.strip()) > MAX_SNAPSHOT_DETAIL_CHARACTERS:
            raise ResearchError("Execution snapshot detail is too long.")
        run_id = self.research_run_id
        if run_id is not None and (not isinstance(run_id, str) or not run_id.strip()):
            raise ResearchError("Execution snapshot run ID cannot be empty.")
        object.__setattr__(self, "plan_id", self.plan_id.strip())
        object.__setattr__(self, "question", self.question.strip())
        object.__setattr__(self, "detail", self.detail.strip())
        if run_id is not None:
            object.__setattr__(self, "research_run_id", run_id.strip())

    @classmethod
    def capture(
        cls,
        state: ResearchPlanExecutionState,
        question: str,
        steps: tuple[ResearchPlanStep, ...],
        recorded_at: datetime,
        research_run_id: str | None = None,
        allowance: ResearchExecutionAllowance | None = None,
        target_plan_digest: str | None = None,
        mission_plan_digest: str | None = None,
        mission_scope: ResearchMissionScope | None = None,
        mission_disclosure: ResearchDisclosure = ResearchDisclosure.NONE,
        mission_checkpoint: ResearchMissionRecoveryCheckpoint | None = None,
    ) -> ResearchPlanExecutionSnapshot:
        """Capture the current state, pairing each step with its capability."""
        capabilities = {step.step_id: step.capability for step in steps}
        return cls(
            plan_id=state.plan_id,
            question=question,
            status=state.status,
            detail=state.detail,
            research_run_id=research_run_id,
            allowance=allowance,
            target_plan_digest=target_plan_digest,
            mission_plan_digest=mission_plan_digest,
            mission_scope=mission_scope,
            mission_disclosure=mission_disclosure,
            mission_checkpoint=mission_checkpoint,
            recorded_at=recorded_at,
            steps=tuple(
                ResearchPlanExecutionStepSnapshot(
                    step_id=step.step_id,
                    capability=capabilities.get(
                        step.step_id,
                        ResearchPlanStepCapability.NONE,
                    ),
                    status=step.status,
                    detail=step.detail,
                    operation=step.operation,
                    work_performed=step.work_performed,
                    resolution=step.resolution,
                    recovery=step.recovery,
                )
                for step in state.steps
            ),
        )

    def restored(self) -> ResearchPlanExecutionSnapshot:
        """Return this snapshot with mid-flight work marked interrupted.

        A step recorded as running did not survive the restart, and what its
        operation actually did is unknown. It becomes interrupted, never
        completed, and its `work_performed` flag is left exactly as recorded
        rather than inferred.
        """
        from dataclasses import replace

        if not any(
            step.status is ResearchPlanStepStatus.RUNNING for step in self.steps
        ):
            return self
        steps = tuple(
            (
                replace(step, status=ResearchPlanStepStatus.INTERRUPTED)
                if step.status is ResearchPlanStepStatus.RUNNING
                else step
            )
            for step in self.steps
        )
        status = (
            ResearchPlanExecutionStatus.INTERRUPTED
            if not self.status.terminal
            else self.status
        )
        return replace(self, steps=steps, status=status)
