from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import tempfile

from brain.BrainRequest import BrainRequest
from cognition.ResearchPlanExecutionApplicationService import (
    RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT,
    RESEARCH_PLAN_EXECUTION_CANCEL_INTENT,
    RESEARCH_PLAN_EXECUTION_PAUSED_INTENT,
    RESEARCH_PLAN_EXECUTION_START_INTENT,
    RESEARCH_PLAN_EXECUTION_STATUS_INTENT,
    ResearchPlanExecutionApplicationService,
)
from core.Exceptions import ResearchError
from research.JsonFileResearchExecutionStore import JsonFileResearchExecutionStore
from research.ResearchAuthorityRequirementKind import ResearchAuthorityRequirementKind
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchPlanStepOperationResult import (
    ResearchPlanStepOperationResult,
)
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding
from research.SourceRevalidationStepBinding import SourceRevalidationStepBinding
from response.ResponseComposer import ResponseComposer

STEPS = (
    ("Collect candidate sources", ()),
    ("Compare accepted sources", ()),
)


def start_request(plan_steps: tuple = STEPS) -> BrainRequest:
    return BrainRequest(
        message="Start research plan",
        metadata={
            "intent": RESEARCH_PLAN_EXECUTION_START_INTENT,
            "research_plan_question": "What evidence supports the claim?",
            "research_plan_steps": plan_steps,
        },
    )


def plan_request(intent: str, plan_id: str) -> BrainRequest:
    return BrainRequest(
        message="Research plan execution",
        metadata={"intent": intent, "research_plan_id": plan_id},
    )


class ResearchPlanExecutionApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identifiers = count(1)
        self.service = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
                id_factory=lambda: f"plan-{next(self.identifiers)}",
            ),
        )

    def test_recognizes_only_the_exact_structured_intents(self) -> None:
        self.assertTrue(self.service.is_start_request(start_request()))
        self.assertTrue(
            self.service.is_status_request(
                plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, "plan-1")
            )
        )
        self.assertTrue(
            self.service.is_cancel_request(
                plan_request(RESEARCH_PLAN_EXECUTION_CANCEL_INTENT, "plan-1")
            )
        )
        self.assertFalse(
            self.service.is_start_request(BrainRequest(message="start research plan"))
        )

    def test_start_creates_running_state_without_advancing_a_step(self) -> None:
        response = self.service.process_start(start_request())

        self.assertTrue(response.success)
        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.RUNNING)
        self.assertEqual(state.completed_steps, 0)
        self.assertEqual(state.pending_steps, 2)
        self.assertIsNone(state.running_step_id)
        self.assertTrue(
            all(step.status is ResearchPlanStepStatus.PENDING for step in state.steps)
        )

    def test_start_never_reports_performed_research_work(self) -> None:
        response = self.service.process_start(start_request())

        state = response.research_plan_execution
        assert state is not None
        self.assertFalse(state.performed_research_work)
        self.assertEqual(state.steps_with_research_work, 0)
        self.assertIn("Research operations performed: 0", response.message)
        self.assertIn("No research work has run", response.message)
        self.assertIn(
            "it is not evidence and not a verified claim",
            response.message,
        )
        self.assertIn(
            "Evidence, assessment, and claims: not established here",
            response.message,
        )
        self.assertIn("Persistent writes: not used", response.message)

    def test_status_message_states_the_ephemeral_boundary(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id

        response = self.service.process_status(
            plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, plan_id)
        )

        self.assertTrue(response.success)
        self.assertIn(
            "Execution state: in-memory only, lost when Hypatia exits",
            response.message,
        )

    def test_duplicate_start_is_rejected_deterministically(self) -> None:
        fixed = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
                id_factory=lambda: "plan-fixed",
            ),
        )
        first = fixed.process_start(start_request())
        second = fixed.process_start(start_request())

        self.assertTrue(first.success)
        self.assertFalse(second.success)
        self.assertIn(
            "already has execution state in this process",
            second.message,
        )
        self.assertIn("Execution: not started", second.message)
        status = fixed.process_status(
            plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, "plan-fixed")
        )
        assert status.research_plan_execution is not None
        self.assertIs(
            status.research_plan_execution.status,
            ResearchPlanExecutionStatus.RUNNING,
        )

    def test_unknown_plan_reports_lost_ephemeral_state(self) -> None:
        response = self.service.process_status(
            plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, "plan-missing")
        )

        self.assertFalse(response.success)
        self.assertIsNone(response.research_plan_execution)
        self.assertIn("holds no execution state", response.message)
        self.assertIn("It is not resumed after a restart.", response.message)

    def test_cancel_marks_unfinished_steps_cancelled(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id

        response = self.service.process_cancel(
            plan_request(RESEARCH_PLAN_EXECUTION_CANCEL_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.CANCELLED)
        self.assertTrue(
            all(step.status is ResearchPlanStepStatus.CANCELLED for step in state.steps)
        )
        self.assertFalse(state.performed_research_work)

    def test_cancel_preserves_completed_step_history(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id
        advanced = (
            self.service._executions[plan_id]
            .start_step("step-1")
            .complete_step(
                "step-1",
                "verified source",
                work_performed=True,
                operation="recording",
            )
        )
        self.service._executions[plan_id] = advanced

        response = self.service.process_cancel(
            plan_request(RESEARCH_PLAN_EXECUTION_CANCEL_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.CANCELLED)
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.COMPLETED)
        self.assertTrue(state.steps[0].work_performed)
        self.assertIs(state.steps[1].status, ResearchPlanStepStatus.CANCELLED)
        self.assertEqual(state.completed_steps, 1)
        self.assertEqual(state.steps_with_research_work, 1)
        self.assertIn("Research operations performed: 1", response.message)
        self.assertNotIn("No research work has run", response.message)

    def test_manual_advance_without_work_is_reported_as_no_research(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id
        advanced = (
            self.service._executions[plan_id]
            .start_step("step-1")
            .complete_step("step-1", "state advanced only")
        )
        self.service._executions[plan_id] = advanced

        response = self.service.process_status(
            plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(state.completed_steps, 1)
        self.assertEqual(state.steps_with_research_work, 0)
        self.assertFalse(state.performed_research_work)
        self.assertIn("Research operations performed: 0", response.message)
        self.assertIn("No research work has run", response.message)

    def test_terminal_execution_rejects_a_second_cancel(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id
        cancel = plan_request(RESEARCH_PLAN_EXECUTION_CANCEL_INTENT, plan_id)
        self.service.process_cancel(cancel)

        response = self.service.process_cancel(cancel)

        self.assertFalse(response.success)
        self.assertIn("terminal status", response.message)

    def test_invalid_plan_draft_is_rejected_without_execution_state(self) -> None:
        response = self.service.process_start(start_request(plan_steps=()))

        self.assertFalse(response.success)
        self.assertIn("Research plan execution rejected", response.message)
        self.assertEqual(self.service._executions, {})

    def test_missing_plan_id_is_rejected(self) -> None:
        for intent in (
            RESEARCH_PLAN_EXECUTION_STATUS_INTENT,
            RESEARCH_PLAN_EXECUTION_CANCEL_INTENT,
        ):
            with self.subTest(intent=intent):
                with self.assertRaises(ResearchError):
                    self.service.process_status(
                        BrainRequest(message="", metadata={"intent": intent})
                    )

    def test_execution_capacity_is_bounded(self) -> None:
        service = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
                id_factory=lambda: f"plan-{next(self.identifiers)}",
            ),
            max_active_executions=2,
        )

        self.assertTrue(service.process_start(start_request()).success)
        self.assertTrue(service.process_start(start_request()).success)
        overflow = service.process_start(start_request())

        self.assertFalse(overflow.success)
        self.assertIn("capacity is full", overflow.message)
        self.assertEqual(len(service._executions), 2)

    def test_rejects_invalid_capacity(self) -> None:
        for invalid in (0, -1, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    ResearchPlanExecutionApplicationService(
                        ResponseComposer(),
                        max_active_executions=invalid,
                    )

    def test_fresh_service_holds_no_state_from_a_previous_process(self) -> None:
        started = self.service.process_start(start_request())
        assert started.research_plan_execution is not None
        plan_id = started.research_plan_execution.plan_id

        restarted = ResearchPlanExecutionApplicationService(ResponseComposer())
        response = restarted.process_status(
            plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, plan_id)
        )

        self.assertFalse(response.success)
        self.assertIn("It is not resumed after a restart.", response.message)


class RecordingStepOperation:
    """Record every step handed to a connected research operation."""

    def __init__(self, performed: bool = True, detail: str = "operation ran") -> None:
        self.performed = performed
        self.detail = detail
        self.steps: list[str] = []

    @property
    def operation_name(self) -> str:
        return "recording"

    def run(self, step, context) -> ResearchPlanStepOperationResult:  # type: ignore[no-untyped-def]
        del context
        self.steps.append(step.step_id)
        return ResearchPlanStepOperationResult(
            performed=self.performed,
            detail=self.detail,
            succeeded=self.performed,
        )


class FailingStepOperation(RecordingStepOperation):
    def run(self, step, context) -> ResearchPlanStepOperationResult:  # type: ignore[no-untyped-def]
        del context
        self.steps.append(step.step_id)
        raise ResearchError("Research operation failed.")


class ResearchPlanExecutionAdvanceTests(unittest.TestCase):
    def _service(self, operation=None):  # type: ignore[no-untyped-def]
        registry = ResearchPlanOperationRegistry()
        if operation is not None:
            registry.register(
                ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                operation,
            )
        return ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
                id_factory=lambda: "plan-advance",
            ),
            operation_registry=registry,
        )

    def _started(self, service, capability="local_knowledge_search"):  # type: ignore[no-untyped-def]
        steps = tuple(
            (instruction, sources, capability) for instruction, sources in STEPS
        )
        response = service.process_start(start_request(plan_steps=steps))
        assert response.research_plan_execution is not None
        return response.research_plan_execution.plan_id

    def test_step_without_a_declared_capability_is_blocked(self) -> None:
        operation = RecordingStepOperation()
        service = self._service(operation)
        plan_id = self._started(service, capability=None)

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.BLOCKED)
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.BLOCKED)
        self.assertEqual(state.completed_steps, 0)
        self.assertFalse(state.performed_research_work)
        self.assertEqual(operation.steps, [])
        self.assertIn("declares no executable capability", response.message)
        self.assertIn("Research operations performed: 0", response.message)

    def test_unregistered_capability_is_blocked_without_fallback(self) -> None:
        service = self._service(None)
        plan_id = self._started(service)

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.BLOCKED)
        self.assertEqual(state.completed_steps, 0)
        self.assertFalse(state.performed_research_work)
        self.assertIn("has no registered operation", response.message)

    def test_instruction_text_never_selects_a_capability(self) -> None:
        operation = RecordingStepOperation()
        service = self._service(operation)
        response = service.process_start(
            start_request(
                plan_steps=(
                    ("Run a local knowledge search for Saturn", ()),
                    ("search knowledge base", ()),
                )
            )
        )
        assert response.research_plan_execution is not None
        plan_id = response.research_plan_execution.plan_id

        advanced = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        state = advanced.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.BLOCKED)
        self.assertEqual(operation.steps, [])
        self.assertIn("declares no executable capability", advanced.message)

    def test_advance_runs_the_connected_operation_once_for_one_step(self) -> None:
        operation = RecordingStepOperation()
        service = self._service(operation)
        plan_id = self._started(service)

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertEqual(operation.steps, ["step-1"])
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.COMPLETED)
        self.assertTrue(state.steps[0].work_performed)
        self.assertEqual(state.steps[0].detail, "operation ran")
        self.assertEqual(state.steps[0].operation, "recording")
        self.assertIs(state.steps[1].status, ResearchPlanStepStatus.PENDING)
        self.assertEqual(state.steps_with_research_work, 1)
        self.assertIn("Research operations performed: 1", response.message)
        self.assertNotIn("No research work has run", response.message)

    def test_operation_reporting_nothing_performed_blocks_the_step(self) -> None:
        operation = RecordingStepOperation(performed=False, detail="nothing to do")
        service = self._service(operation)
        plan_id = self._started(service)

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.BLOCKED)
        self.assertEqual(state.completed_steps, 0)
        self.assertFalse(state.performed_research_work)

    def test_failing_operation_fails_the_step_and_the_plan(self) -> None:
        service = self._service(FailingStepOperation())
        plan_id = self._started(service)

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.FAILED)
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.FAILED)
        self.assertFalse(state.steps[0].work_performed)
        self.assertEqual(state.steps_with_research_work, 0)

    def test_advancing_every_step_completes_the_plan(self) -> None:
        operation = RecordingStepOperation()
        service = self._service(operation)
        plan_id = self._started(service)
        advance = plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)

        service.process_advance(advance)
        response = service.process_advance(advance)

        state = response.research_plan_execution
        assert state is not None
        self.assertIs(state.status, ResearchPlanExecutionStatus.COMPLETED)
        self.assertEqual(state.completed_steps, 2)
        self.assertEqual(state.steps_with_research_work, 2)
        self.assertEqual(operation.steps, ["step-1", "step-2"])

    def test_advance_beyond_the_last_step_is_rejected(self) -> None:
        service = self._service(RecordingStepOperation())
        plan_id = self._started(service)
        advance = plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        service.process_advance(advance)
        service.process_advance(advance)

        response = service.process_advance(advance)

        self.assertFalse(response.success)
        self.assertIn("no pending step to advance", response.message)

    def test_advance_on_unknown_plan_reports_lost_state(self) -> None:
        service = self._service(RecordingStepOperation())

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, "plan-missing")
        )

        self.assertFalse(response.success)
        self.assertIn("It is not resumed after a restart.", response.message)


def _semantic_evidence_step_draft() -> ResearchPlanStepDraftInput:
    return ResearchPlanStepDraftInput(
        instruction="Propose evidence",
        capability=ResearchPlanStepCapability.SEMANTIC_EVIDENCE_PROPOSAL.value,
        semantic_evidence_binding=SemanticEvidenceStepBinding(
            input_fingerprint="a" * 64,
            endpoint="http://127.0.0.1:11434/v1/chat/completions",
            model="fixture",
        ),
    )


def _model_step_start_request(research_run_id: str = "run-1") -> BrainRequest:
    return BrainRequest(
        message="Start research plan",
        metadata={
            "intent": RESEARCH_PLAN_EXECUTION_START_INTENT,
            "research_plan_question": "What evidence supports the claim?",
            "research_plan_steps": (_semantic_evidence_step_draft(),),
            "research_run_id": research_run_id,
        },
    )


class ResearchPlanExecutionAuthorityPauseTests(unittest.TestCase):
    """`process_advance` durably pauses a step missing authority entirely.

    Deliberately distinct from `ResearchPlanExecutionAdvanceTests`'s existing
    budget/capability coverage: those exercise `BLOCKED` (impossible work)
    and `_advance_refused` (an approved allowance falling short). This class
    exercises the third, previously untested path -- no allowance at all --
    where advancing today has always returned the same ephemeral rejection
    message; what this milestone adds is the durable trace alongside it.
    """

    def _service(
        self,
        *,
        execution_store: JsonFileResearchExecutionStore | None = None,
        id_factory=lambda: "plan-authority",  # type: ignore[no-untyped-def]
    ) -> ResearchPlanExecutionApplicationService:
        registry = ResearchPlanOperationRegistry()
        registry.register(
            ResearchPlanStepCapability.SEMANTIC_EVIDENCE_PROPOSAL,
            RecordingStepOperation(),
        )
        return ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
                id_factory=id_factory,
            ),
            operation_registry=registry,
            execution_store=execution_store,
        )

    def _started(
        self,
        service: ResearchPlanExecutionApplicationService,
        research_run_id: str = "run-1",
    ) -> str:
        response = service.process_start(_model_step_start_request(research_run_id))
        assert response.research_plan_execution is not None
        return response.research_plan_execution.plan_id

    def test_missing_model_budget_pauses_durably_instead_of_only_rejecting(
        self,
    ) -> None:
        service = self._service()
        plan_id = self._started(service)

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        self.assertFalse(response.success)
        self.assertIn(
            "Model steps require an explicit approved execution budget.",
            response.message,
        )
        # The immediate rejection response is byte-for-byte unchanged by the
        # durable side effect; the pause is visible on a later status read.
        status = service.process_status(
            plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, plan_id)
        )
        self.assertIn("Paused for authority on step-1", status.message)
        state = service._executions[plan_id]
        self.assertIsNotNone(state.authority_pause)
        assert state.authority_pause is not None
        self.assertIs(
            state.authority_pause.requirement_kind,
            ResearchAuthorityRequirementKind.PLAN_AUTHORIZATION,
        )
        self.assertEqual(state.authority_pause.step_id, "step-1")
        self.assertEqual(state.authority_pause.research_run_id, "run-1")
        self.assertEqual(
            state.authority_pause.plan_digest,
            plan_digest(service._plans[plan_id]),
        )
        # Nothing was attempted or charged, and the execution stays running.
        self.assertIs(state.status, ResearchPlanExecutionStatus.RUNNING)
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.PENDING)
        self.assertEqual(service._allowances.get(plan_id), None)

    def test_missing_source_revalidation_allowance_pauses_durably(self) -> None:
        registry = ResearchPlanOperationRegistry()
        registry.register(
            ResearchPlanStepCapability.SOURCE_REVALIDATION,
            RecordingStepOperation(),
        )
        service = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
                id_factory=lambda: "plan-revalidation",
            ),
            operation_registry=registry,
        )
        response = service.process_start(
            BrainRequest(
                message="Start research plan",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_START_INTENT,
                    "research_plan_question": "What evidence supports the claim?",
                    "research_plan_steps": (
                        ResearchPlanStepDraftInput(
                            instruction="Revalidate a source",
                            capability=(
                                ResearchPlanStepCapability.SOURCE_REVALIDATION.value
                            ),
                            source_revalidation_binding=SourceRevalidationStepBinding(
                                research_run_id="run-1",
                                prior_observation_id="observation-1",
                                requested_url="https://example.org/source",
                                max_sources=1,
                            ),
                        ),
                    ),
                    "research_run_id": "run-1",
                },
            )
        )
        assert response.research_plan_execution is not None
        plan_id = response.research_plan_execution.plan_id

        advanced = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        self.assertFalse(advanced.success)
        self.assertIn(
            "Source revalidation requires an explicit approved execution " "allowance",
            advanced.message,
        )
        state = service._executions[plan_id]
        self.assertIsNotNone(state.authority_pause)
        assert state.authority_pause is not None
        self.assertIs(
            state.authority_pause.requirement_kind,
            ResearchAuthorityRequirementKind.PLAN_AUTHORIZATION,
        )
        self.assertEqual(state.authority_pause.step_id, "step-1")

    def test_pause_without_a_bound_research_run_falls_back_to_ephemeral_only(
        self,
    ) -> None:
        """No `ResearchPlanAuthorization` can bind without a research run, so
        this deliberately does not record an incomplete requirement -- the
        plain rejection is unchanged, exactly as before this milestone.
        """
        service = self._service()
        response = service.process_start(
            BrainRequest(
                message="Start research plan",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_START_INTENT,
                    "research_plan_question": "What evidence supports the claim?",
                    "research_plan_steps": (_semantic_evidence_step_draft(),),
                    # No research_run_id: this execution is never bound to a run.
                },
            )
        )
        assert response.research_plan_execution is not None
        plan_id = response.research_plan_execution.plan_id
        self.assertIsNone(service._contexts[plan_id].research_run_id)

        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        self.assertFalse(response.success)
        self.assertIn(
            "Model steps require an explicit approved execution budget.",
            response.message,
        )
        state = service._executions[plan_id]
        self.assertIsNone(state.authority_pause)

    def test_repeated_advance_attempts_do_not_duplicate_or_drift_the_pause(
        self,
    ) -> None:
        service = self._service()
        plan_id = self._started(service)
        advance = plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)

        service.process_advance(advance)
        service.process_advance(advance)
        state = service._executions[plan_id]

        assert state.authority_pause is not None
        self.assertEqual(state.authority_pause.step_id, "step-1")

    def test_pause_is_cleared_once_the_step_actually_starts(self) -> None:
        """Proves the clearing mechanism: nothing but the step itself
        starting resolves the pause. No public API in this milestone can
        grant a fresh allowance to an already-running execution, so this
        directly installs one to exercise exactly the transition
        `require_authority`/`start_step` are built to make automatic once a
        future milestone adds that resume mechanism.
        """
        service = self._service()
        plan_id = self._started(service)
        service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )
        assert service._executions[plan_id].authority_pause is not None

        service._allowances[plan_id] = ResearchExecutionAllowance(
            budget=ResearchAutonomyBudget(max_llm_operations=1)
        )
        response = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        state = response.research_plan_execution
        assert state is not None
        self.assertIsNone(state.authority_pause)
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.COMPLETED)

    def test_authority_pause_survives_a_persisted_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store_path = Path(directory) / "executions.json"
            first = self._service(
                execution_store=JsonFileResearchExecutionStore(store_path)
            )
            plan_id = self._started(first)
            first.process_advance(
                plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
            )
            assert first._executions[plan_id].authority_pause is not None

            second = self._service(
                execution_store=JsonFileResearchExecutionStore(store_path)
            )

            self.assertNotIn(plan_id, second._executions)
            response = second.process_status(
                plan_request(RESEARCH_PLAN_EXECUTION_STATUS_INTENT, plan_id)
            )

            self.assertTrue(response.success)
            self.assertIn("Paused for authority on step-1", response.message)
            self.assertIn(
                "Model steps require an explicit approved execution budget.",
                response.message,
            )
            restored = second._restored[plan_id]
            self.assertIsNotNone(restored.authority_pause)
            assert restored.authority_pause is not None
            self.assertEqual(restored.authority_pause.step_id, "step-1")
            self.assertEqual(restored.authority_pause.research_run_id, "run-1")
            self.assertIs(
                restored.status,
                ResearchPlanExecutionStatus.RUNNING,
            )

    def test_wrong_run_authorization_cannot_be_confused_with_this_pause(self) -> None:
        """The pause names one exact run; a second execution under a
        different run has its own, independently distinguishable pause --
        proving there is no shared or ambiguous identity between them.
        """
        service = self._service()
        first_plan_id = self._started(service, research_run_id="run-1")
        service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, first_plan_id)
        )

        second_service = self._service(id_factory=lambda: "plan-authority-2")
        second_plan_id = self._started(second_service, research_run_id="run-2")
        second_service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, second_plan_id)
        )

        first_pause = service._executions[first_plan_id].authority_pause
        second_pause = second_service._executions[second_plan_id].authority_pause
        assert first_pause is not None and second_pause is not None
        self.assertNotEqual(first_pause.research_run_id, second_pause.research_run_id)
        self.assertNotEqual(first_pause, second_pause)

    def _paused(self, service: ResearchPlanExecutionApplicationService) -> object:
        return service.process_paused(
            BrainRequest(
                message="List executions paused for authority",
                metadata={"intent": RESEARCH_PLAN_EXECUTION_PAUSED_INTENT},
            )
        )

    def test_recognizes_the_paused_listing_intent(self) -> None:
        service = self._service()
        request = BrainRequest(
            message="x", metadata={"intent": RESEARCH_PLAN_EXECUTION_PAUSED_INTENT}
        )

        self.assertTrue(service.is_paused_request(request))
        self.assertFalse(
            service.is_paused_request(
                BrainRequest(message="x", metadata={"intent": "other"})
            )
        )

    def test_nothing_paused_is_an_explicit_empty_listing(self) -> None:
        service = self._service()

        response = self._paused(service)

        self.assertTrue(response.success)
        self.assertEqual(response.research_paused_execution_ids, ())
        self.assertIn(
            "No execution is currently paused for authority", response.message
        )

    def test_a_live_pause_is_listed_with_its_requirement_and_run(self) -> None:
        service = self._service()
        plan_id = self._started(service)
        service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        response = self._paused(service)

        self.assertEqual(response.research_paused_execution_ids, (plan_id,))
        self.assertEqual(response.research_paused_execution_run_ids, ("run-1",))
        self.assertIn(
            f"requires {ResearchAuthorityRequirementKind.PLAN_AUTHORIZATION.value} "
            "on step-1",
            response.message,
        )

    def test_a_running_but_unpaused_execution_is_not_listed(self) -> None:
        service = self._service()
        self._started(service)

        response = self._paused(service)

        self.assertEqual(response.research_paused_execution_ids, ())

    def test_listing_performs_no_work_and_changes_nothing(self) -> None:
        service = self._service()
        plan_id = self._started(service)
        service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )
        before = service._executions[plan_id]

        for _ in range(3):
            self._paused(service)

        self.assertEqual(service._executions[plan_id], before)
        self.assertIs(
            service._executions[plan_id].status, ResearchPlanExecutionStatus.RUNNING
        )

    def test_a_restored_pause_survives_a_persisted_restart_with_a_new_instance(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store_path = Path(directory) / "executions.json"
            first = self._service(
                execution_store=JsonFileResearchExecutionStore(store_path)
            )
            plan_id = self._started(first)
            first.process_advance(
                plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
            )

            second = self._service(
                execution_store=JsonFileResearchExecutionStore(store_path)
            )
            self.assertNotIn(plan_id, second._executions)

            response = self._paused(second)

            self.assertEqual(response.research_paused_execution_ids, (plan_id,))
            self.assertEqual(response.research_paused_execution_run_ids, ("run-1",))

    def test_a_live_pause_takes_precedence_over_a_stale_restored_entry(self) -> None:
        """If a plan_id is somehow both live and restored, the live, current
        pause must win -- never a stale one left over from before restart.
        """
        service = self._service()
        plan_id = self._started(service)
        service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )
        live_pause = service._executions[plan_id].authority_pause
        assert live_pause is not None
        stale_snapshot = service._live_snapshot(plan_id, service._clock())
        service._restored[plan_id] = replace(
            stale_snapshot,
            authority_pause=replace(live_pause, detail="Stale pre-restart detail."),
        )

        response = self._paused(service)

        self.assertEqual(response.research_paused_execution_ids, (plan_id,))
        self.assertIn(live_pause.detail, response.message)
        self.assertNotIn("Stale pre-restart detail.", response.message)

    def test_blocked_execution_with_a_later_authority_gap_does_not_pause_or_crash(
        self,
    ) -> None:
        """A later pending step that needs authority is never durably paused
        -- or allowed to raise -- while the execution as a whole is
        `BLOCKED` by an earlier, unrelated step. `require_authority` can
        only be recorded while the execution is `RUNNING`; `_paused_for_authority`
        must fall back to the plain ephemeral rejection whenever it is not,
        exactly as it already does when no research run is bound.
        """
        registry = ResearchPlanOperationRegistry()
        registry.register(
            ResearchPlanStepCapability.SEMANTIC_EVIDENCE_PROPOSAL,
            RecordingStepOperation(),
        )
        service = ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            ResearchPlanDraftService(
                clock=lambda: datetime(2026, 8, 23, tzinfo=UTC),
                id_factory=lambda: "plan-authority-blocked",
            ),
            operation_registry=registry,
        )
        response = service.process_start(
            BrainRequest(
                message="Start research plan",
                metadata={
                    "intent": RESEARCH_PLAN_EXECUTION_START_INTENT,
                    "research_plan_question": "What evidence supports the claim?",
                    "research_plan_steps": (
                        ResearchPlanStepDraftInput(
                            instruction="No declared capability"
                        ),
                        _semantic_evidence_step_draft(),
                    ),
                    "research_run_id": "run-1",
                },
            )
        )
        assert response.research_plan_execution is not None
        plan_id = response.research_plan_execution.plan_id

        blocked = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )
        assert blocked.research_plan_execution is not None
        self.assertIs(
            blocked.research_plan_execution.status,
            ResearchPlanExecutionStatus.BLOCKED,
        )

        # The execution is BLOCKED, not RUNNING, but step-2 is still PENDING
        # and needs authority this execution has never had. This advance
        # must fall back to the plain ephemeral rejection -- never record a
        # durable pause, and never raise.
        second = service.process_advance(
            plan_request(RESEARCH_PLAN_EXECUTION_ADVANCE_INTENT, plan_id)
        )

        self.assertFalse(second.success)
        self.assertIn(
            "Model steps require an explicit approved execution budget.",
            second.message,
        )
        state = service._executions[plan_id]
        self.assertIsNone(state.authority_pause)
        self.assertIs(state.status, ResearchPlanExecutionStatus.BLOCKED)


if __name__ == "__main__":
    unittest.main()
