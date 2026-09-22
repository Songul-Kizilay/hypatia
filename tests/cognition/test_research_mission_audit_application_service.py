"""`proposal_for` must fail closed and never write anything.

Mirrors `render()`'s exact snapshot/run/stop-reason assembly and
`build_mission_audit`'s fail-closed gate: a missing snapshot, run or
recorded stop reason yields no proposal rather than a partial one, and
generating a proposal reads recorded state without ever writing it.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from cognition.ResearchMissionAuditApplicationService import (
    MISSION_AUDIT_TRACEABILITY_VIEW_INTENT,
    MISSION_CONTINUATION_PROPOSAL_PREVIEW_INTENT,
    ResearchMissionAuditApplicationService,
)
from core.Exceptions import ResearchError
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchMissionAuditTraceabilityGraph import traceability_graph_for
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
    """Expose only `get` and `source_revalidations`; any other call proves an
    unwanted read/write.

    `source_revalidations` is included (returning nothing recorded) because
    `_audit_for` reads it unconditionally whenever a run manager is
    configured, independent of whether `get` resolved a run -- so any test
    that reaches `_audit_for` (directly or through `proposal_for`/the
    traceability view) needs this fixture to answer it without that read
    itself being mistaken for a write.
    """

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

    def source_revalidations(self) -> tuple[object, ...]:
        return ()

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


class RunManagerRecordingCalls:
    """Expose exactly the reads `_audit_for` may perform. No network, no store.

    `temporal_history` raises if ever called: every fixture run below has no
    `requested_url` on any source, so `_audit_for`'s own requested-URL
    collection is always empty and this must never be reached.
    """

    def __init__(self, run: ResearchRun | None) -> None:
        self._run = run
        self.get_calls: list[str] = []
        self.source_revalidations_calls = 0

    def get(self, run_id: str) -> ResearchRun:
        self.get_calls.append(run_id)
        if self._run is None or run_id != self._run.run_id:
            raise ResearchError("No research run with that ID is known.")
        return self._run

    def source_revalidations(self) -> tuple[object, ...]:
        self.source_revalidations_calls += 1
        return ()

    def temporal_history(self, requested_url: str, *, run_id: str) -> object:
        raise AssertionError("temporal_history must not be called in this test.")

    def __getattr__(self, name: str) -> object:
        def _forbidden(*args: object, **kwargs: object) -> None:
            raise AssertionError(f"the traceability view must never call runs.{name}.")

        return _forbidden


def _traceability_run() -> ResearchRun:
    """A richer run than `_run()`: claims, a contradiction, a review too."""
    run = _run(with_note=True)
    claim = ResearchClaimRecord(
        claim_id="claim-1",
        text="The recorded evidence may support this.",
        epistemic_state=ResearchEpistemicState.HYPOTHESIS,
        confidence=ResearchClaimConfidence.LOW,
        source_document_ids=("doc-1",),
        evidence_ids=("evidence-1",),
        recorded_at=NOW,
    )
    other_claim = ResearchClaimRecord(
        claim_id="claim-2",
        text="The recorded evidence may contradict the first claim.",
        epistemic_state=ResearchEpistemicState.CONTRADICTED,
        confidence=ResearchClaimConfidence.LOW,
        source_document_ids=("doc-2",),
        evidence_ids=("evidence-2",),
        recorded_at=NOW,
    )
    contradiction = ResearchClaimContradictionRecord(
        contradiction_id="contradiction-1",
        claim_ids=("claim-1", "claim-2"),
        evidence_ids=("evidence-1", "evidence-2"),
        note="These disagree.",
        recorded_at=NOW,
    )
    return replace(
        run,
        claims=(claim, other_claim),
        claim_contradictions=(contradiction,),
    )


class ResearchMissionAuditApplicationServiceTraceabilityViewTests(unittest.TestCase):
    """The new read-only intent must match a direct `traceability_graph_for` call."""

    def test_matches_traceability_graph_for_called_directly_on_the_same_audit(
        self,
    ) -> None:
        snapshot = _snapshot()
        run = _traceability_run()
        execution = ExecutionMustNotWrite(snapshot)
        runs = RunManagerRecordingCalls(run)
        service = ResearchMissionAuditApplicationService(
            execution,  # type: ignore[arg-type]
            runs,  # type: ignore[arg-type]
            None,
            lambda: "0.0.0-test",
        )
        request = BrainRequest(
            message="View mission audit traceability graph",
            source="desktop",
            metadata={
                "intent": MISSION_AUDIT_TRACEABILITY_VIEW_INTENT,
                "research_plan_id": "plan-1",
            },
        )

        response = service.process(request)

        self.assertTrue(response.success)
        self.assertIsNotNone(response.research_mission_audit_traceability_graph)
        # Independently rebuild the exact same audit through the same
        # assembly (`_audit_for`, the one place `render()` and this intent
        # both build from) and compare the two graphs for exact dataclass
        # equality -- proving the intent adds no divergent computation.
        _expected_snapshot, _expected_run, expected_audit = service._audit_for("plan-1")
        expected_graph = traceability_graph_for(expected_audit["traceability"])
        self.assertEqual(
            response.research_mission_audit_traceability_graph, expected_graph
        )
        self.assertEqual(execution.mission_snapshot_calls.count("plan-1"), 2)
        self.assertTrue(all(call == "run-1" for call in runs.get_calls))

    def test_reports_unavailable_explicitly_when_there_is_no_run(self) -> None:
        snapshot = _snapshot(research_run_id=None, stop_reason=None)
        execution = ExecutionMustNotWrite(snapshot)
        service = ResearchMissionAuditApplicationService(
            execution,  # type: ignore[arg-type]
            None,
            None,
            lambda: "0.0.0-test",
        )
        request = BrainRequest(
            message="View mission audit traceability graph",
            source="desktop",
            metadata={
                "intent": MISSION_AUDIT_TRACEABILITY_VIEW_INTENT,
                "research_plan_id": "plan-1",
            },
        )

        response = service.process(request)

        self.assertTrue(response.success)
        self.assertIsNone(response.research_mission_audit_traceability_graph)
        self.assertIn("unavailable", response.message)
        self.assertIn("no research run is recorded", response.message)

    def test_reports_unavailable_when_the_recorded_run_id_no_longer_resolves(
        self,
    ) -> None:
        """`research_run_id` is set, but the run manager raises (a deleted or
        corrupted run record) -- `_audit_for` must fail closed to no run
        rather than let the exception escape or fabricate a graph.
        """
        snapshot = _snapshot(research_run_id="run-1")
        execution = ExecutionMustNotWrite(snapshot)
        runs = RunManagerMustNotWrite(raise_missing=True)
        service = ResearchMissionAuditApplicationService(
            execution,  # type: ignore[arg-type]
            runs,  # type: ignore[arg-type]
            None,
            lambda: "0.0.0-test",
        )
        request = BrainRequest(
            message="View mission audit traceability graph",
            source="desktop",
            metadata={
                "intent": MISSION_AUDIT_TRACEABILITY_VIEW_INTENT,
                "research_plan_id": "plan-1",
            },
        )

        response = service.process(request)

        self.assertTrue(response.success)
        self.assertIsNone(response.research_mission_audit_traceability_graph)
        self.assertIn("unavailable", response.message)
        self.assertIn("no research run is recorded", response.message)
        self.assertEqual(runs.get_calls, ["run-1"])

    def test_performs_no_write_and_no_unexpected_read(self) -> None:
        """Only `mission_snapshot`, `get` and `source_revalidations` are read."""
        snapshot = _snapshot()
        run = _traceability_run()
        execution = ExecutionMustNotWrite(snapshot)
        runs = RunManagerRecordingCalls(run)
        service = ResearchMissionAuditApplicationService(
            execution,  # type: ignore[arg-type]
            runs,  # type: ignore[arg-type]
            None,
            lambda: "0.0.0-test",
        )
        request = BrainRequest(
            message="View mission audit traceability graph",
            source="desktop",
            metadata={
                "intent": MISSION_AUDIT_TRACEABILITY_VIEW_INTENT,
                "research_plan_id": "plan-1",
            },
        )

        response = service.process(request)

        self.assertTrue(response.success)
        self.assertEqual(runs.source_revalidations_calls, 1)
        self.assertEqual(execution.mission_snapshot_calls, ["plan-1"])
        self.assertEqual(runs.get_calls, ["run-1"])


class ResearchMissionAuditApplicationServiceProposalPreviewIntentTests(
    unittest.TestCase
):
    """The new intent must add zero divergent computation over `proposal_for`."""

    def test_matches_calling_proposal_for_directly_for_an_eligible_mission(
        self,
    ) -> None:
        checkpoint = _agreement_checkpoint()
        snapshot = _snapshot(
            stop_reason=AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
            checkpoint=checkpoint,
        )
        execution = ExecutionMustNotWrite(snapshot)
        run = _run(with_note=True)
        runs = RunManagerMustNotWrite(run)
        service = _service(execution, runs)
        request = BrainRequest(
            message="Preview mission continuation proposal",
            source="desktop",
            metadata={
                "intent": MISSION_CONTINUATION_PROPOSAL_PREVIEW_INTENT,
                "research_plan_id": "plan-1",
            },
        )

        response = service.process(request)
        directly = service.proposal_for("plan-1")

        self.assertTrue(response.success)
        proposal = response.research_mission_continuation_proposal
        self.assertIsNotNone(proposal)
        self.assertIsNotNone(directly)
        assert proposal is not None and directly is not None
        # `proposal_id` (a fresh `uuid4()`) and `generated_at` (a fresh
        # `datetime.now(UTC)`) are, by `continuation_proposal_for`'s own
        # unmodified design, freshly derived on every call, so two
        # independent calls can never share those two values byte-for-byte.
        # Normalizing exactly those two fields and then asserting full
        # dataclass equality proves every other field -- including
        # `origin_run_id`, `origin_plan_digest`, `origin_stop_reason`,
        # `origin_goal_status`, `origin_evidence_status`,
        # `origin_evidence_limitations` and `seed_question` -- matches
        # exactly, i.e. the intent adds no divergent computation.
        self.assertEqual(
            replace(proposal, proposal_id="normalized", generated_at=NOW),
            replace(directly, proposal_id="normalized", generated_at=NOW),
        )
        self.assertIn(proposal.origin_run_id, response.message)

    def test_reports_an_accurate_not_eligible_message_and_succeeds(self) -> None:
        """A satisfied (ineligible) mission is refused explicitly, not silently.

        Mirrors `test_returns_none_for_an_ineligible_satisfied_outcome` and,
        like the traceability view's "no run" case, reports `success=True`
        with an explicit, generic explanation rather than a crash or a
        fabricated proposal.
        """
        snapshot = _snapshot(
            stop_reason=AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
            checkpoint=None,
        )
        execution = ExecutionMustNotWrite(snapshot)
        runs = RunManagerMustNotWrite(_run(with_note=True))
        service = _service(execution, runs)
        request = BrainRequest(
            message="Preview mission continuation proposal",
            source="desktop",
            metadata={
                "intent": MISSION_CONTINUATION_PROPOSAL_PREVIEW_INTENT,
                "research_plan_id": "plan-1",
            },
        )

        response = service.process(request)

        self.assertTrue(response.success)
        self.assertIsNone(response.research_mission_continuation_proposal)
        self.assertIn("No continuation proposal is available", response.message)
        self.assertIn("unresolved", response.message)
        self.assertIn("partially_satisfied", response.message)
        # The generic explanation folds every possible cause together; it
        # never names this mission's actual (satisfied) status specifically.
        self.assertNotIn("goal status is `satisfied`", response.message)

    def test_reports_the_same_generic_message_when_no_run_is_recorded(self) -> None:
        """A different ineligibility cause (no run) yields the same accurate,
        generic explanation -- `proposal_for` exposes no reason code to
        distinguish causes, so this intent must never fabricate one either.
        """
        snapshot = _snapshot(research_run_id=None, stop_reason=None)
        execution = ExecutionMustNotWrite(snapshot)
        service = _service(execution, None)
        request = BrainRequest(
            message="Preview mission continuation proposal",
            source="desktop",
            metadata={
                "intent": MISSION_CONTINUATION_PROPOSAL_PREVIEW_INTENT,
                "research_plan_id": "plan-1",
            },
        )

        response = service.process(request)

        self.assertTrue(response.success)
        self.assertIsNone(response.research_mission_continuation_proposal)
        self.assertIn("No continuation proposal is available", response.message)

    def test_is_registered_as_a_request_the_service_will_handle(self) -> None:
        service = _service(ExecutionMustNotWrite(None), None)
        request = BrainRequest(
            message="Preview mission continuation proposal",
            source="desktop",
            metadata={
                "intent": MISSION_CONTINUATION_PROPOSAL_PREVIEW_INTENT,
                "research_plan_id": "plan-1",
            },
        )

        self.assertTrue(service.is_request(request))

    def test_performs_no_write_and_no_unexpected_read(self) -> None:
        """Only `mission_snapshot` and `get` are read; nothing is written."""
        checkpoint = _agreement_checkpoint()
        snapshot = _snapshot(
            stop_reason=AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
            checkpoint=checkpoint,
        )
        execution = ExecutionMustNotWrite(snapshot)
        run = _run(with_note=True)
        runs = RunManagerMustNotWrite(run)
        service = _service(execution, runs)
        request = BrainRequest(
            message="Preview mission continuation proposal",
            source="desktop",
            metadata={
                "intent": MISSION_CONTINUATION_PROPOSAL_PREVIEW_INTENT,
                "research_plan_id": "plan-1",
            },
        )

        response = service.process(request)

        self.assertTrue(response.success)
        self.assertEqual(execution.mission_snapshot_calls, ["plan-1"])
        self.assertEqual(runs.get_calls, ["run-1"])


if __name__ == "__main__":
    unittest.main()
