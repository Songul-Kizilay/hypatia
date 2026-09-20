"""`proposal_for` must fail closed and never write anything.

Mirrors `render()`'s exact snapshot/run/stop-reason assembly and
`build_mission_audit`'s fail-closed gate: a missing snapshot, run or
recorded stop reason yields no proposal rather than a partial one, and
generating a proposal reads recorded state without ever writing it.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from cognition.ResearchMissionAuditApplicationService import (
    ResearchMissionAuditApplicationService,
)
from core.Exceptions import ResearchError
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus,
)
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint
from research.ResearchMissionScope import SEMANTIC_POLICY, ResearchMissionScope
from research.ResearchPlanExecutionSnapshot import (
    ResearchPlanExecutionSnapshot,
    ResearchPlanExecutionStepSnapshot,
)
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceRecord import ResearchSourceRecord

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
PLAN_DIGEST = sha256(b"mission-plan-content").hexdigest()


class ExecutionMustNotWrite:
    """Expose only `mission_snapshot`; any other call proves an unwanted read/write."""

    def __init__(self, snapshot: ResearchPlanExecutionSnapshot | None) -> None:
        self._snapshot = snapshot
        self.mission_snapshot_calls: list[str] = []

    def mission_snapshot(self, plan_id: str) -> ResearchPlanExecutionSnapshot | None:
        self.mission_snapshot_calls.append(plan_id)
        return self._snapshot

    def __getattr__(self, name: str) -> object:
        def _forbidden(*args: object, **kwargs: object) -> None:
            raise AssertionError("proposal_for must never write.")

        return _forbidden


class RunManagerMustNotWrite:
    """Expose only `get`; any other call proves an unwanted read/write."""

    def __init__(
        self,
        run: ResearchRun | None = None,
        *,
        raise_missing: bool = False,
    ) -> None:
        self._run = run
        self._raise_missing = raise_missing
        self.get_calls: list[str] = []

    def get(self, run_id: str) -> ResearchRun:
        self.get_calls.append(run_id)
        if self._raise_missing or self._run is None:
            raise ResearchError("No research run with that ID is known.")
        return self._run

    def __getattr__(self, name: str) -> object:
        def _forbidden(*args: object, **kwargs: object) -> None:
            raise AssertionError("proposal_for must never write.")

        return _forbidden


def _scope() -> ResearchMissionScope:
    from research.SemanticMissionPolicy import SemanticMissionPolicy

    return ResearchMissionScope(
        ResearchDiscoveryProviderName.CROSSREF,
        source_policy=SEMANTIC_POLICY,
        max_sources=3,
        semantic_policy=SemanticMissionPolicy(
            "http://127.0.0.1:11434/v1/chat/completions",
            "fixture",
            ResearchDisclosure.LOCAL_ONLY,
        ),
    )


def _snapshot(
    *,
    plan_id: str = "plan-1",
    research_run_id: str | None = "run-1",
    stop_reason: AutonomyStopReason | None = AutonomyStopReason.STEP_INTERRUPTED,
    checkpoint: ResearchMissionRecoveryCheckpoint | None = None,
) -> ResearchPlanExecutionSnapshot:
    return ResearchPlanExecutionSnapshot(
        plan_id=plan_id,
        question="What do the recorded sources support?",
        status=ResearchPlanExecutionStatus.INTERRUPTED,
        steps=(
            ResearchPlanExecutionStepSnapshot(
                step_id="step-1",
                capability=ResearchPlanStepCapability.SOURCE_DISCOVERY,
                status=ResearchPlanStepStatus.COMPLETED,
            ),
        ),
        recorded_at=NOW,
        research_run_id=research_run_id,
        mission_plan_digest=PLAN_DIGEST,
        mission_scope=_scope(),
        mission_disclosure=ResearchDisclosure.LOCAL_ONLY,
        mission_checkpoint=checkpoint,
        mission_stop_reason=stop_reason,
    )


def _agreement_checkpoint(**changes: object) -> ResearchMissionRecoveryCheckpoint:
    values: dict[str, object] = {
        "discovery_id": "discovery-1",
        "acquired_urls": ("https://example.test/1", "https://example.test/2"),
        "body_hashes": ("1" * 64, "2" * 64),
        "inspected_bytes": 600,
        "evidence_ids": ("evidence-1", "evidence-2"),
        "assessment_ids": ("assessment-1", "assessment-2"),
        "semantic_note_id": "note-1",
        "semantic_input_fingerprint": "a" * 64,
        "semantic_relation": "possible_agreement",
    }
    values.update(changes)
    return ResearchMissionRecoveryCheckpoint(**values)  # type: ignore[arg-type]


def _run(*, with_note: bool = False) -> ResearchRun:
    sources = tuple(
        ResearchSourceRecord(
            document_id=f"doc-{number}",
            url=f"https://example.test/{number}",
            title=f"Source {number}",
            content_type="text/plain",
            fetched_at=NOW,
            added_at=NOW,
        )
        for number in (1, 2)
    )
    evidence = tuple(
        ResearchEvidenceRecord(
            evidence_id=f"evidence-{number}",
            source_document_id=f"doc-{number}",
            chunk_id=f"chunk-{number}",
            chunk_index=0,
            excerpt=f"Recorded excerpt {number}.",
            excerpt_truncated=False,
            chunk_sha256=sha256(f"Recorded excerpt {number}.".encode()).hexdigest(),
            note="Grounded excerpt only.",
            recorded_at=NOW,
        )
        for number in (1, 2)
    )
    assessments = tuple(
        ResearchSourceAssessmentRecord(
            assessment_id=f"assessment-{number}",
            source_document_id=f"doc-{number}",
            evidence_ids=(f"evidence-{number}",),
            text="Exact-source grounding only.",
            recorded_at=NOW,
        )
        for number in (1, 2)
    )
    notes = (
        (
            ResearchSourceComparisonNoteRecord(
                note_id="note-1",
                source_document_ids=("doc-1", "doc-2"),
                evidence_ids=("evidence-1", "evidence-2"),
                assessment_ids=("assessment-1", "assessment-2"),
                text="Mission semantic research note.",
                recorded_at=NOW,
            ),
        )
        if with_note
        else ()
    )
    return ResearchRun(
        run_id="run-1",
        question="What do the recorded sources support?",
        status=ResearchRunStatus.COLLECTING,
        sources=sources,
        failures=(),
        created_at=NOW,
        updated_at=NOW,
        evidence=evidence,
        assessments=assessments,
        comparison_notes=notes,
    )


def _service(
    execution: ExecutionMustNotWrite, runs: RunManagerMustNotWrite | None
) -> ResearchMissionAuditApplicationService:
    return ResearchMissionAuditApplicationService(
        execution,  # type: ignore[arg-type]
        runs,  # type: ignore[arg-type]
        None,
        lambda: "0.0.0-test",
    )


class ResearchMissionAuditApplicationServiceProposalTests(unittest.TestCase):
    def test_returns_none_when_snapshot_is_missing(self) -> None:
        execution = ExecutionMustNotWrite(None)
        runs = RunManagerMustNotWrite(raise_missing=True)
        service = _service(execution, runs)

        result = service.proposal_for("no-such-plan")

        self.assertIsNone(result)
        self.assertEqual(execution.mission_snapshot_calls, ["no-such-plan"])
        self.assertEqual(runs.get_calls, [])

    def test_returns_none_when_the_run_is_missing(self) -> None:
        snapshot = _snapshot()
        execution = ExecutionMustNotWrite(snapshot)
        runs = RunManagerMustNotWrite(raise_missing=True)
        service = _service(execution, runs)

        result = service.proposal_for("plan-1")

        self.assertIsNone(result)
        self.assertEqual(runs.get_calls, ["run-1"])

    def test_returns_none_when_no_runs_manager_is_configured(self) -> None:
        snapshot = _snapshot()
        execution = ExecutionMustNotWrite(snapshot)
        service = _service(execution, None)

        result = service.proposal_for("plan-1")

        self.assertIsNone(result)

    def test_returns_none_when_stop_reason_is_unrecorded(self) -> None:
        snapshot = _snapshot(stop_reason=None)
        execution = ExecutionMustNotWrite(snapshot)
        runs = RunManagerMustNotWrite(_run())
        service = _service(execution, runs)

        result = service.proposal_for("plan-1")

        self.assertIsNone(result)

    def test_returns_none_for_an_ineligible_satisfied_outcome(self) -> None:
        snapshot = _snapshot(
            stop_reason=AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
            checkpoint=None,
        )
        execution = ExecutionMustNotWrite(snapshot)
        runs = RunManagerMustNotWrite(_run(with_note=True))
        service = _service(execution, runs)

        result = service.proposal_for("plan-1")

        self.assertIsNone(result)

    def test_returns_a_proposal_for_an_unresolved_outcome(self) -> None:
        checkpoint = _agreement_checkpoint()
        snapshot = _snapshot(
            stop_reason=AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
            checkpoint=checkpoint,
        )
        execution = ExecutionMustNotWrite(snapshot)
        run = _run(with_note=True)
        runs = RunManagerMustNotWrite(run)
        service = _service(execution, runs)

        result = service.proposal_for("plan-1")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.origin_plan_digest, snapshot.mission_plan_digest)
        self.assertEqual(result.origin_run_id, run.run_id)
        self.assertIs(
            result.origin_goal_status, ResearchMissionGoalSatisfactionStatus.UNRESOLVED
        )
        self.assertEqual(execution.mission_snapshot_calls, ["plan-1"])
        self.assertEqual(runs.get_calls, ["run-1"])


if __name__ == "__main__":
    unittest.main()
