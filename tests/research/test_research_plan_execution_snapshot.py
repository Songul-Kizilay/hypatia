from __future__ import annotations

import copy
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchMissionScope import SEMANTIC_POLICY, ResearchMissionScope
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanExecutionCodec import (
    decode_execution_snapshot,
    encode_execution_snapshot,
)
from research.ResearchPlanExecutionSnapshot import (
    ResearchPlanExecutionSnapshot,
    ResearchPlanExecutionStepSnapshot,
)
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.SemanticMissionPolicy import SemanticMissionPolicy

RECORDED_AT = datetime(2026, 8, 23, tzinfo=UTC)
QUESTION = "Does the ring system have a measured age?"


def plan_steps() -> tuple[ResearchPlanStep, ...]:
    return (
        ResearchPlanStep(
            step_id="step-1",
            instruction="Search local knowledge",
            capability=ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
        ),
        ResearchPlanStep(
            step_id="step-2",
            instruction="List accepted sources",
            capability=ResearchPlanStepCapability.ACCEPTED_SOURCE_LISTING,
        ),
    )


def plan() -> ResearchPlan:
    return ResearchPlan(
        plan_id="plan-1",
        question=QUESTION,
        steps=plan_steps(),
        created_at=RECORDED_AT,
    )


def capture(state: ResearchPlanExecutionState) -> ResearchPlanExecutionSnapshot:
    return ResearchPlanExecutionSnapshot.capture(
        state,
        QUESTION,
        plan_steps(),
        RECORDED_AT,
        research_run_id="run-1",
    )


class ExecutionSnapshotCaptureTests(unittest.TestCase):
    def test_capture_pairs_each_step_with_its_declared_capability(self) -> None:
        state = ResearchPlanExecutionState.prepare(plan()).start()

        snapshot = capture(state)

        self.assertEqual(snapshot.plan_id, "plan-1")
        self.assertEqual(snapshot.question, QUESTION)
        self.assertEqual(snapshot.research_run_id, "run-1")
        self.assertIs(snapshot.status, ResearchPlanExecutionStatus.RUNNING)
        self.assertIs(
            snapshot.steps[0].capability,
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
        )
        self.assertIs(
            snapshot.steps[1].capability,
            ResearchPlanStepCapability.ACCEPTED_SOURCE_LISTING,
        )

    def test_capture_derives_advance_refusal_from_state(self) -> None:
        state = (
            ResearchPlanExecutionState.prepare(plan())
            .start()
            .refuse_advance("step-1", "budget does not cover this step")
        )

        snapshot = capture(state)

        self.assertEqual(snapshot.advance_refusal_step_id, "step-1")
        self.assertEqual(
            snapshot.advance_refusal_detail, "budget does not cover this step"
        )

    def test_capture_preserves_work_and_operation_identity(self) -> None:
        state = (
            ResearchPlanExecutionState.prepare(plan())
            .start()
            .start_step("step-1")
            .complete_step(
                "step-1",
                "matched 2 chunks",
                work_performed=True,
                operation="local_knowledge_search",
            )
        )

        snapshot = capture(state)

        self.assertIs(snapshot.steps[0].status, ResearchPlanStepStatus.COMPLETED)
        self.assertTrue(snapshot.steps[0].work_performed)
        self.assertEqual(snapshot.steps[0].operation, "local_knowledge_search")
        self.assertFalse(snapshot.steps[1].work_performed)


class ExecutionSnapshotRestoreTests(unittest.TestCase):
    def test_running_step_restores_as_interrupted_never_completed(self) -> None:
        state = ResearchPlanExecutionState.prepare(plan()).start().start_step("step-1")

        restored = capture(state).restored()

        self.assertIs(restored.steps[0].status, ResearchPlanStepStatus.INTERRUPTED)
        self.assertIs(restored.status, ResearchPlanExecutionStatus.INTERRUPTED)
        self.assertFalse(restored.steps[0].work_performed)

    def test_completed_step_stays_completed(self) -> None:
        state = (
            ResearchPlanExecutionState.prepare(plan())
            .start()
            .start_step("step-1")
            .complete_step(
                "step-1",
                "done",
                work_performed=True,
                operation="local_knowledge_search",
            )
        )

        restored = capture(state).restored()

        self.assertIs(restored.steps[0].status, ResearchPlanStepStatus.COMPLETED)
        self.assertTrue(restored.steps[0].work_performed)
        self.assertEqual(restored.steps[0].operation, "local_knowledge_search")

    def test_pending_step_stays_pending(self) -> None:
        state = ResearchPlanExecutionState.prepare(plan()).start()

        restored = capture(state).restored()

        for step in restored.steps:
            self.assertIs(step.status, ResearchPlanStepStatus.PENDING)

    def test_terminal_execution_stays_terminal(self) -> None:
        state = (
            ResearchPlanExecutionState.prepare(plan()).start().cancel("user cancelled")
        )

        restored = capture(state).restored()

        self.assertIs(restored.status, ResearchPlanExecutionStatus.CANCELLED)

    def test_restore_is_idempotent(self) -> None:
        state = ResearchPlanExecutionState.prepare(plan()).start().start_step("step-1")
        once = capture(state).restored()

        self.assertEqual(once, once.restored())

    def test_advance_refusal_survives_restore_unchanged(self) -> None:
        """A refusal never coexists with a `RUNNING` step, so `restored()` has
        nothing to reinterpret about it; it is carried through exactly as
        recorded, which is the documented, deliberate choice for this field.
        """
        state = (
            ResearchPlanExecutionState.prepare(plan())
            .start()
            .refuse_advance("step-1", "budget does not cover this step")
        )

        restored = capture(state).restored()

        self.assertEqual(restored.advance_refusal_step_id, "step-1")
        self.assertEqual(
            restored.advance_refusal_detail, "budget does not cover this step"
        )
        # Step-status reinterpretation is completely unaffected: nothing was
        # running, so nothing becomes interrupted.
        self.assertIs(restored.status, ResearchPlanExecutionStatus.RUNNING)
        for step in restored.steps:
            self.assertIs(step.status, ResearchPlanStepStatus.PENDING)

    def test_blocked_and_interrupted_are_distinct_and_non_terminal(self) -> None:
        self.assertIsNot(
            ResearchPlanStepStatus.BLOCKED,
            ResearchPlanStepStatus.INTERRUPTED,
        )
        self.assertFalse(ResearchPlanStepStatus.INTERRUPTED.terminal)
        self.assertFalse(ResearchPlanExecutionStatus.INTERRUPTED.terminal)


class ExecutionSnapshotCodecTests(unittest.TestCase):
    def test_round_trip_is_lossless(self) -> None:
        state = (
            ResearchPlanExecutionState.prepare(plan())
            .start()
            .start_step("step-1")
            .complete_step(
                "step-1",
                "matched 2 chunks",
                work_performed=True,
                operation="local_knowledge_search",
            )
        )
        snapshot = capture(state)

        decoded = decode_execution_snapshot(encode_execution_snapshot(snapshot))

        self.assertEqual(decoded, snapshot)

    def test_round_trip_without_a_bound_run(self) -> None:
        snapshot = ResearchPlanExecutionSnapshot.capture(
            ResearchPlanExecutionState.prepare(plan()).start(),
            QUESTION,
            plan_steps(),
            RECORDED_AT,
        )

        decoded = decode_execution_snapshot(encode_execution_snapshot(snapshot))

        self.assertIsNone(decoded.research_run_id)
        self.assertEqual(decoded, snapshot)

    def test_round_trip_preserves_advance_refusal(self) -> None:
        state = (
            ResearchPlanExecutionState.prepare(plan())
            .start()
            .refuse_advance("step-1", "budget does not cover this step")
        )
        snapshot = capture(state)

        decoded = decode_execution_snapshot(encode_execution_snapshot(snapshot))

        self.assertEqual(decoded.advance_refusal_step_id, "step-1")
        self.assertEqual(
            decoded.advance_refusal_detail, "budget does not cover this step"
        )
        self.assertEqual(decoded, snapshot)

    def test_legacy_document_decodes_advance_refusal_as_absent(self) -> None:
        """No ``advance_refusal`` key at all: the pre-existing document shape.

        Decodes as no recorded refusal -- never inferred, never backfilled --
        mirroring how a legacy document with no ``mission_stop_reason`` key
        decodes as no recorded stop.
        """
        snapshot = capture(ResearchPlanExecutionState.prepare(plan()).start())
        document = encode_execution_snapshot(snapshot)

        self.assertNotIn("advance_refusal", document)

        decoded = decode_execution_snapshot(document)

        self.assertIsNone(decoded.advance_refusal_step_id)
        self.assertEqual(decoded.advance_refusal_detail, "")

    def test_advance_refusal_coexists_with_mission_stop_reason(self) -> None:
        """The two independent optional singleton keys decode together.

        Exercises the ordering fix this milestone required: stripping
        ``advance_refusal`` first, then recursing, so it never has to be
        enumerated alongside every mission-recovery field combination.
        """
        mission_plan = ResearchPlan(
            plan_id="mission-plan-1",
            question=QUESTION,
            steps=plan_steps(),
            created_at=RECORDED_AT,
        )
        scope = ResearchMissionScope(
            ResearchDiscoveryProviderName.CROSSREF,
            source_policy=SEMANTIC_POLICY,
            max_sources=3,
            semantic_policy=SemanticMissionPolicy(
                "http://127.0.0.1:11434/v1/chat/completions",
                "fixture",
                ResearchDisclosure.LOCAL_ONLY,
            ),
        )
        state = (
            ResearchPlanExecutionState.prepare(mission_plan)
            .start()
            .refuse_advance("step-1", "budget does not cover this step")
        )
        snapshot = ResearchPlanExecutionSnapshot.capture(
            state,
            QUESTION,
            plan_steps(),
            RECORDED_AT,
            mission_plan_digest=plan_digest(mission_plan),
            mission_scope=scope,
            mission_disclosure=ResearchDisclosure.LOCAL_ONLY,
            mission_stop_reason=AutonomyStopReason.ADVANCE_REFUSED,
        )
        document = encode_execution_snapshot(snapshot)

        self.assertIn("advance_refusal", document)
        self.assertIn("mission_stop_reason", document)

        decoded = decode_execution_snapshot(document)

        self.assertEqual(decoded, snapshot)
        self.assertEqual(decoded.advance_refusal_step_id, "step-1")
        self.assertIs(decoded.mission_stop_reason, AutonomyStopReason.ADVANCE_REFUSED)

    def test_malformed_advance_refusal_documents_are_rejected(self) -> None:
        state = (
            ResearchPlanExecutionState.prepare(plan())
            .start()
            .refuse_advance("step-1", "budget does not cover this step")
        )
        valid = encode_execution_snapshot(capture(state))

        for mutate in (
            lambda d: d.update({"advance_refusal": {"step_id": "step-1"}}),
            lambda d: d.update(
                {"advance_refusal": {"step_id": "", "detail": "reason"}}
            ),
            lambda d: d.update(
                {"advance_refusal": {"step_id": "step-9", "detail": "reason"}}
            ),
            lambda d: d.update({"advance_refusal": "not-a-dict"}),
            lambda d: d.update(
                {
                    "advance_refusal": {
                        "step_id": "step-1",
                        "detail": "x" * 501,
                    }
                }
            ),
        ):
            with self.subTest(mutate=mutate):
                document = copy.deepcopy(valid)
                mutate(document)
                with self.assertRaises(ResearchError):
                    decode_execution_snapshot(document)

        self.assertEqual(
            decode_execution_snapshot(valid).advance_refusal_step_id, "step-1"
        )

    def test_document_carries_no_authored_content_beyond_the_question(self) -> None:
        state = ResearchPlanExecutionState.prepare(plan()).start().start_step("step-1")
        encoded = repr(encode_execution_snapshot(capture(state)))

        self.assertNotIn("Search local knowledge", encoded)
        self.assertNotIn("List accepted sources", encoded)

    def test_work_without_an_operation_is_rejected(self) -> None:
        document = encode_execution_snapshot(
            capture(
                ResearchPlanExecutionState.prepare(plan())
                .start()
                .start_step("step-1")
                .complete_step(
                    "step-1",
                    "done",
                    work_performed=True,
                    operation="local_knowledge_search",
                )
            )
        )
        document["steps"][0]["operation"] = ""

        with self.assertRaises(ResearchError):
            decode_execution_snapshot(document)

    def test_malformed_documents_are_rejected(self) -> None:
        valid = encode_execution_snapshot(
            capture(ResearchPlanExecutionState.prepare(plan()).start())
        )

        for mutate in (
            lambda d: d.pop("plan_id"),
            lambda d: d.update({"unexpected": 1}),
            lambda d: d.update({"steps": []}),
            lambda d: d.update({"steps": "not-a-list"}),
            lambda d: d.update({"status": "imaginary"}),
            lambda d: d.update({"recorded_at": "not-a-timestamp"}),
            lambda d: d.update({"recorded_at": "2026-08-23T00:00:00"}),
            lambda d: d.update({"plan_id": "  "}),
            lambda d: d.update({"question": "  "}),
            lambda d: d.update({"research_run_id": 5}),
            lambda d: d.update({"detail": "x" * 501}),
        ):
            with self.subTest(mutate=mutate):
                document = encode_execution_snapshot(
                    capture(ResearchPlanExecutionState.prepare(plan()).start())
                )
                mutate(document)
                with self.assertRaises(ResearchError):
                    decode_execution_snapshot(document)

        self.assertEqual(decode_execution_snapshot(valid).plan_id, "plan-1")

    def test_malformed_step_documents_are_rejected(self) -> None:
        for mutate in (
            lambda s: s.pop("step_id"),
            lambda s: s.update({"capability": "imaginary"}),
            lambda s: s.update({"status": "imaginary"}),
            lambda s: s.update({"work_performed": "yes"}),
            lambda s: s.update({"operation": 5}),
        ):
            with self.subTest(mutate=mutate):
                document = encode_execution_snapshot(
                    capture(ResearchPlanExecutionState.prepare(plan()).start())
                )
                mutate(document["steps"][0])
                with self.assertRaises(ResearchError):
                    decode_execution_snapshot(document)

    def test_snapshot_validation_rejects_invalid_values(self) -> None:
        step = ResearchPlanExecutionStepSnapshot(
            step_id="step-1",
            capability=ResearchPlanStepCapability.NONE,
            status=ResearchPlanStepStatus.PENDING,
        )
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionStepSnapshot(
                step_id="step-1",
                capability=ResearchPlanStepCapability.NONE,
                status=ResearchPlanStepStatus.COMPLETED,
                work_performed=True,
            )
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionSnapshot(
                plan_id="plan-1",
                question=QUESTION,
                status=ResearchPlanExecutionStatus.RUNNING,
                steps=(step, step),
                recorded_at=RECORDED_AT,
            )
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionSnapshot(
                plan_id="plan-1",
                question=QUESTION,
                status=ResearchPlanExecutionStatus.RUNNING,
                steps=(),
                recorded_at=RECORDED_AT,
            )
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionSnapshot(
                plan_id="plan-1",
                question=QUESTION,
                status=ResearchPlanExecutionStatus.RUNNING,
                steps=(step,),
                recorded_at=datetime(2026, 8, 23),
            )

    def test_advance_refusal_requires_a_reason(self) -> None:
        step = ResearchPlanExecutionStepSnapshot(
            step_id="step-1",
            capability=ResearchPlanStepCapability.NONE,
            status=ResearchPlanStepStatus.PENDING,
        )
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionSnapshot(
                plan_id="plan-1",
                question=QUESTION,
                status=ResearchPlanExecutionStatus.RUNNING,
                steps=(step,),
                recorded_at=RECORDED_AT,
                advance_refusal_step_id="step-1",
                advance_refusal_detail="",
            )

    def test_advance_refusal_detail_requires_a_step_id(self) -> None:
        step = ResearchPlanExecutionStepSnapshot(
            step_id="step-1",
            capability=ResearchPlanStepCapability.NONE,
            status=ResearchPlanStepStatus.PENDING,
        )
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionSnapshot(
                plan_id="plan-1",
                question=QUESTION,
                status=ResearchPlanExecutionStatus.RUNNING,
                steps=(step,),
                recorded_at=RECORDED_AT,
                advance_refusal_detail="stray reason",
            )

    def test_advance_refusal_must_name_a_known_step(self) -> None:
        step = ResearchPlanExecutionStepSnapshot(
            step_id="step-1",
            capability=ResearchPlanStepCapability.NONE,
            status=ResearchPlanStepStatus.PENDING,
        )
        with self.assertRaises(ResearchError):
            ResearchPlanExecutionSnapshot(
                plan_id="plan-1",
                question=QUESTION,
                status=ResearchPlanExecutionStatus.RUNNING,
                steps=(step,),
                recorded_at=RECORDED_AT,
                advance_refusal_step_id="step-9",
                advance_refusal_detail="reason",
            )


if __name__ == "__main__":
    unittest.main()
