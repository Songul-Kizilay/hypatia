from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepOperationResult import (
    ResearchPlanStepOperationResult,
)


class StubOperation:
    def __init__(self, name: str = "stub") -> None:
        self._name = name

    @property
    def operation_name(self) -> str:
        return self._name

    def run(self, step: ResearchPlanStep) -> ResearchPlanStepOperationResult:
        return ResearchPlanStepOperationResult(performed=True, detail="ran")


class ResearchPlanStepCapabilityTests(unittest.TestCase):
    def test_only_none_is_non_executable(self) -> None:
        self.assertFalse(ResearchPlanStepCapability.NONE.executable)
        self.assertTrue(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH.executable)

    def test_step_defaults_to_no_capability(self) -> None:
        step = ResearchPlanStep(step_id="step-1", instruction="Search Saturn")

        self.assertIs(step.capability, ResearchPlanStepCapability.NONE)
        self.assertFalse(step.capability.executable)

    def test_step_rejects_a_non_capability_value(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchPlanStep(
                step_id="step-1",
                instruction="Search",
                capability="local_knowledge_search",  # type: ignore[arg-type]
            )


class ResearchPlanOperationRegistryTests(unittest.TestCase):
    def test_resolves_only_a_registered_capability(self) -> None:
        operation = StubOperation()
        registry = ResearchPlanOperationRegistry(
            {ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH: operation}
        )

        self.assertIs(
            registry.resolve(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH),
            operation,
        )
        self.assertIsNone(registry.resolve(ResearchPlanStepCapability.NONE))

    def test_empty_registry_resolves_nothing(self) -> None:
        registry = ResearchPlanOperationRegistry()

        self.assertIsNone(
            registry.resolve(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        )
        self.assertEqual(registry.registered_capabilities, ())

    def test_none_capability_cannot_be_registered(self) -> None:
        registry = ResearchPlanOperationRegistry()

        with self.assertRaises(ResearchError):
            registry.register(ResearchPlanStepCapability.NONE, StubOperation())

    def test_duplicate_registration_is_rejected(self) -> None:
        registry = ResearchPlanOperationRegistry(
            {ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH: StubOperation()}
        )

        with self.assertRaises(ResearchError):
            registry.register(
                ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                StubOperation("other"),
            )

    def test_invalid_capability_type_is_rejected(self) -> None:
        registry = ResearchPlanOperationRegistry()

        with self.assertRaises(ResearchError):
            registry.register("local_knowledge_search", StubOperation())  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            registry.resolve("local_knowledge_search")  # type: ignore[arg-type]

    def test_registered_capabilities_are_deterministic(self) -> None:
        registry = ResearchPlanOperationRegistry(
            {ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH: StubOperation()}
        )

        self.assertEqual(
            registry.registered_capabilities,
            (ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,),
        )


class ResearchPlanDraftCapabilityTests(unittest.TestCase):
    def test_two_element_draft_declares_no_capability(self) -> None:
        from datetime import UTC, datetime

        from research.ResearchPlanDraftService import ResearchPlanDraftService

        service = ResearchPlanDraftService(
            clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
            id_factory=lambda: "plan-1",
        )

        preview = service.preview("Question?", (("Search knowledge", ()),))

        self.assertTrue(preview.allowed)
        assert preview.plan is not None
        self.assertIs(
            preview.plan.steps[0].capability,
            ResearchPlanStepCapability.NONE,
        )

    def test_three_element_draft_declares_an_explicit_capability(self) -> None:
        from datetime import UTC, datetime

        from research.ResearchPlanDraftService import ResearchPlanDraftService

        service = ResearchPlanDraftService(
            clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
            id_factory=lambda: "plan-1",
        )

        preview = service.preview(
            "Question?",
            (("Anything at all", (), "local_knowledge_search"),),
        )

        self.assertTrue(preview.allowed)
        assert preview.plan is not None
        self.assertIs(
            preview.plan.steps[0].capability,
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
        )

    def test_unknown_capability_is_rejected(self) -> None:
        from datetime import UTC, datetime

        from research.ResearchPlanDraftService import ResearchPlanDraftService

        service = ResearchPlanDraftService(
            clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
            id_factory=lambda: "plan-1",
        )

        preview = service.preview("Question?", (("Step", (), "fetch_the_web"),))

        self.assertFalse(preview.allowed)
        self.assertIn("capability is not recognized", preview.reason)


class ResearchPlanExecutionSnapshotTests(unittest.TestCase):
    def test_snapshot_is_deterministic_and_records_operations(self) -> None:
        from datetime import UTC, datetime

        from research.ResearchPlan import ResearchPlan
        from research.ResearchPlanExecutionState import ResearchPlanExecutionState

        plan = ResearchPlan(
            plan_id="plan-1",
            question="Question?",
            steps=(ResearchPlanStep(step_id="step-1", instruction="Do it"),),
            created_at=datetime(2026, 8, 23, tzinfo=UTC),
        )
        state = ResearchPlanExecutionState.prepare(plan).start()

        self.assertEqual(state.snapshot(), (("step-1", "pending", "", False),))

        completed = state.start_step("step-1").complete_step(
            "step-1",
            "ran",
            work_performed=True,
            operation="stub",
        )

        self.assertEqual(completed.snapshot(), (("step-1", "completed", "stub", True),))
        self.assertEqual(completed.snapshot(), completed.snapshot())


if __name__ == "__main__":
    unittest.main()
