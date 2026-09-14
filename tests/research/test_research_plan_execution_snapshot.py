from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchPlan import ResearchPlan
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


if __name__ == "__main__":
    unittest.main()
