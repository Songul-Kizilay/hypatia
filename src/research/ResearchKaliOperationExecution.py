"""Bounded execution contract for one reviewed Kali operation.

The application layer may use this contract only after re-validating an exact
operation authorization, a current preview and runtime readiness. Process
output remains untrusted data and is not evidence by itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchKaliOperationPreview import (
    ResearchKaliOperationCommandPlan,
    ResearchKaliOperationKind,
    is_kali_operation_digest,
)

MAX_KALI_OPERATION_OUTPUT_LINES = 50
MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS = 500
MAX_KALI_OPERATION_EVIDENCE_CANDIDATE_LINES = 20
KALI_OPERATION_OUTPUT_TRUST = "untrusted_process_output"


@dataclass(frozen=True, slots=True)
class ResearchKaliOperationProcessResult:
    """Bounded child-process result returned by a reviewed adapter."""

    command_plan: ResearchKaliOperationCommandPlan
    exit_code: int
    stdout_lines: tuple[str, ...]
    stderr_lines: tuple[str, ...] = ()
    timed_out: bool = False
    process_created: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.command_plan, ResearchKaliOperationCommandPlan):
            raise ResearchError("Kali operation process command plan is invalid.")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ResearchError("Kali operation process exit code is invalid.")
        self._validate_lines(self.stdout_lines, "stdout")
        self._validate_lines(self.stderr_lines, "stderr")
        if not isinstance(self.timed_out, bool):
            raise ResearchError("Kali operation process timeout flag is invalid.")
        if self.process_created is not True:
            raise ResearchError("Kali operation process result requires a process.")

    @staticmethod
    def _validate_lines(lines: object, label: str) -> None:
        if not isinstance(lines, tuple):
            raise ResearchError(f"Kali operation process {label} must be immutable.")
        if len(lines) > MAX_KALI_OPERATION_OUTPUT_LINES:
            raise ResearchError(f"Kali operation process {label} has too many lines.")
        for line in lines:
            if (
                not isinstance(line, str)
                or "\x00" in line
                or len(line) > MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS
            ):
                raise ResearchError(f"Kali operation process {label} is invalid.")


@dataclass(frozen=True, slots=True)
class ResearchKaliOperationRun:
    """A completed reviewed operation result, still not accepted evidence."""

    authorization_id: str
    operation_digest: str
    program_id: str
    scope_revision_id: str
    scope_revision_digest: str
    execution_policy_digest: str
    operation_kind: ResearchKaliOperationKind
    command_plan: ResearchKaliOperationCommandPlan
    process_result: ResearchKaliOperationProcessResult
    authorization_consumed: bool = True

    def __post_init__(self) -> None:
        for value, label in (
            (self.authorization_id, "authorization ID"),
            (self.program_id, "program ID"),
            (self.scope_revision_id, "scope revision ID"),
            (self.scope_revision_digest, "scope revision digest"),
            (self.execution_policy_digest, "execution policy digest"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"Kali operation run {label} cannot be empty.")
        if not is_kali_operation_digest(self.operation_digest):
            raise ResearchError("Kali operation run digest is invalid.")
        if not isinstance(self.operation_kind, ResearchKaliOperationKind):
            raise ResearchError("Kali operation run kind is invalid.")
        if not isinstance(self.command_plan, ResearchKaliOperationCommandPlan):
            raise ResearchError("Kali operation run command plan is invalid.")
        if not isinstance(self.process_result, ResearchKaliOperationProcessResult):
            raise ResearchError("Kali operation run process result is invalid.")
        if self.process_result.command_plan != self.command_plan:
            raise ResearchError("Kali operation run result used a different command.")
        if self.authorization_consumed is not True:
            raise ResearchError("Kali operation run requires consumed authorization.")


@dataclass(frozen=True, slots=True)
class ResearchKaliOperationEvidenceCandidate:
    """Review-only observations derived from one Kali operation stdout.

    This model is intentionally not a ResearchEvidenceRecord. It gives the
    operator a bounded candidate view over process output without accepting a
    source, recording evidence, creating a claim or writing memory.
    """

    authorization_id: str
    operation_digest: str
    program_id: str
    scope_revision_id: str
    scope_revision_digest: str
    execution_policy_digest: str
    operation_kind: ResearchKaliOperationKind
    command_plan: ResearchKaliOperationCommandPlan
    candidate_lines: tuple[str, ...]
    exit_code: int
    timed_out: bool
    candidate_lines_truncated: bool = False
    output_trust: str = KALI_OPERATION_OUTPUT_TRUST
    evidence_recorded: bool = False
    claim_created: bool = False
    source_accepted: bool = False
    memory_written: bool = False

    def __post_init__(self) -> None:
        for value, label in (
            (self.authorization_id, "authorization ID"),
            (self.program_id, "program ID"),
            (self.scope_revision_id, "scope revision ID"),
            (self.scope_revision_digest, "scope revision digest"),
            (self.execution_policy_digest, "execution policy digest"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(
                    f"Kali operation evidence candidate {label} cannot be empty."
                )
        if not is_kali_operation_digest(self.operation_digest):
            raise ResearchError("Kali operation evidence candidate digest is invalid.")
        if not isinstance(self.operation_kind, ResearchKaliOperationKind):
            raise ResearchError("Kali operation evidence candidate kind is invalid.")
        if not isinstance(self.command_plan, ResearchKaliOperationCommandPlan):
            raise ResearchError(
                "Kali operation evidence candidate command plan is invalid."
            )
        if not isinstance(self.candidate_lines, tuple):
            raise ResearchError("Kali operation evidence candidate lines are invalid.")
        if len(self.candidate_lines) > MAX_KALI_OPERATION_EVIDENCE_CANDIDATE_LINES:
            raise ResearchError("Kali operation evidence candidate has too many lines.")
        for line in self.candidate_lines:
            if (
                not isinstance(line, str)
                or "\x00" in line
                or len(line) > MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS
            ):
                raise ResearchError(
                    "Kali operation evidence candidate line is invalid."
                )
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ResearchError("Kali operation evidence candidate exit code invalid.")
        if not isinstance(self.timed_out, bool) or not isinstance(
            self.candidate_lines_truncated, bool
        ):
            raise ResearchError("Kali operation evidence candidate flags are invalid.")
        if self.output_trust != KALI_OPERATION_OUTPUT_TRUST:
            raise ResearchError("Kali operation evidence candidate trust is invalid.")
        if (
            self.evidence_recorded is not False
            or self.claim_created is not False
            or self.source_accepted is not False
            or self.memory_written is not False
        ):
            raise ResearchError(
                "Kali operation evidence candidate must not claim writes."
            )


def kali_operation_evidence_candidate_for_run(
    run: ResearchKaliOperationRun,
) -> ResearchKaliOperationEvidenceCandidate:
    """Derive a review-only candidate from one completed Kali operation run."""
    if not isinstance(run, ResearchKaliOperationRun):
        raise ResearchError("Kali operation run is invalid.")
    stdout_lines = run.process_result.stdout_lines
    candidate_lines = stdout_lines[:MAX_KALI_OPERATION_EVIDENCE_CANDIDATE_LINES]
    return ResearchKaliOperationEvidenceCandidate(
        authorization_id=run.authorization_id,
        operation_digest=run.operation_digest,
        program_id=run.program_id,
        scope_revision_id=run.scope_revision_id,
        scope_revision_digest=run.scope_revision_digest,
        execution_policy_digest=run.execution_policy_digest,
        operation_kind=run.operation_kind,
        command_plan=run.command_plan,
        candidate_lines=candidate_lines,
        exit_code=run.process_result.exit_code,
        timed_out=run.process_result.timed_out,
        candidate_lines_truncated=len(stdout_lines) > len(candidate_lines),
    )


class ResearchKaliOperationProcessAdapter:
    """Replaceable adapter for one reviewed operation command plan."""

    def run(
        self,
        command_plan: ResearchKaliOperationCommandPlan,
        *,
        timeout_seconds: float,
    ) -> ResearchKaliOperationProcessResult:
        """Run exactly the supplied command plan."""
        raise NotImplementedError
