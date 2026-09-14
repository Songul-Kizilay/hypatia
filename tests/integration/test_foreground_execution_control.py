"""Foreground execution advances only when the operator asks.

One approval was spent to start. Everything here happens inside what that
approval allowed, and every advance is one press: one attempt, then stop. There
is no loop anywhere in this file because there is no loop anywhere in the code,
and several tests exist only to prove that.

The budget stops being a recorded number here. The arithmetic tests use the real
capability cost table rather than invented costs, because a budget tested against
made-up prices is a budget nobody has actually checked.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.ResearchPlanAuthorizationApplicationService import (
    ResearchPlanAuthorizationApplicationService,
)
from cognition.ResearchPlanExecutionApplicationService import (
    ResearchPlanExecutionApplicationService,
)
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from research.JsonFileResearchExecutionStore import JsonFileResearchExecutionStore
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchCapabilityCost import cost_for
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchExecutionSpend import ResearchExecutionSpend
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

QUESTION = "Does the Saturn ring system have a measured age?"
NOW = datetime(2026, 8, 26, 9, 0, tzinfo=UTC)

LOCAL_STEP: tuple[object, ...] = (
    "Search the local knowledge base.",
    (),
    "local_knowledge_search",
)
NETWORK_STEP: tuple[object, ...] = (
    "Find candidate sources.",
    (),
    "source_discovery",
)


class StubClock:
    """A clock the tests move deliberately rather than by waiting."""

    def __init__(self) -> None:
        self.moment = NOW

    def __call__(self) -> datetime:
        return self.moment

    def advance(self, seconds: float) -> None:
        self.moment = self.moment + timedelta(seconds=seconds)


class RecordingOperation:
    """A double that records every run and performs no real research."""

    def __init__(
        self,
        capability: ResearchPlanStepCapability,
        succeeded: bool = True,
        performed: bool = True,
        clock: StubClock | None = None,
        duration: float = 0.0,
    ) -> None:
        self.capability = capability
        self.operation_name = f"double:{capability.value}"
        self.runs = 0
        self._succeeded = succeeded
        self._performed = performed
        self._clock = clock
        self._duration = duration

    def run(self, step: object, context: object) -> ResearchPlanStepOperationResult:
        self.runs += 1
        if self._clock is not None and self._duration:
            self._clock.advance(self._duration)
        return ResearchPlanStepOperationResult(
            performed=self._performed,
            # The domain refuses an operation that performed nothing yet
            # claims success, which is the right refusal. The double honours
            # it rather than constructing a result the runtime would reject.
            succeeded=self._succeeded and self._performed,
            detail="Recorded by a test double.",
        )


class ForegroundFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.execution_path = self.root / "executions.json"
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.manager.load()
        self.run_id = self.manager.create(QUESTION).run_id
        self.clock = StubClock()
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.identities = iter(f"approval-{index}" for index in range(1, 100))
        self.approvals = ResearchPlanAuthorizationApplicationService(
            self.manager,
            ResponseComposer(),
            authorization_store=JsonFileResearchPlanAuthorizationStore(
                self.root / "authorizations.json"
            ),
            event_bus=self.event_bus,
            clock=self.clock,
            id_factory=lambda: next(self.identities),
        )
        self.operations: dict[ResearchPlanStepCapability, RecordingOperation] = {}
        self.addCleanup(self.temporary_directory.cleanup)

    def registry(
        self,
        *capabilities: ResearchPlanStepCapability,
        succeeded: bool = True,
        performed: bool = True,
        duration: float = 0.0,
    ) -> ResearchPlanOperationRegistry:
        registry = ResearchPlanOperationRegistry()
        for capability in capabilities:
            operation = RecordingOperation(
                capability,
                succeeded=succeeded,
                performed=performed,
                clock=self.clock,
                duration=duration,
            )
            self.operations[capability] = operation
            registry.register(capability, operation)  # type: ignore[arg-type]
        return registry

    def execution_service(
        self,
        registry: ResearchPlanOperationRegistry | None = None,
        persist: bool = False,
    ) -> ResearchPlanExecutionApplicationService:
        names = iter(f"execution-{index}" for index in range(1, 100))
        return ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            operation_registry=registry or ResearchPlanOperationRegistry(),
            event_bus=self.event_bus,
            clock=self.clock,
            authorization_consumer=self.approvals,
            execution_store=(
                JsonFileResearchExecutionStore(self.execution_path) if persist else None
            ),
            draft_service=ResearchPlanDraftService(
                clock=lambda: self.clock.moment,
                id_factory=lambda: next(names),
            ),
        )

    def request(self, intent: str, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="Foreground execution",
            metadata={"intent": intent, **metadata},
        )

    def approve(
        self,
        steps: tuple[tuple[object, ...], ...],
        budget: ResearchAutonomyBudget | None = None,
    ) -> str:
        """Approve one plan, optionally with a deliberately narrow budget."""
        previewed = self.approvals.process_preview(
            self.request(
                "research_plan_authorization_preview",
                research_run_id=self.run_id,
                research_plan_question=QUESTION,
                research_plan_steps=steps,
            )
        )
        assert previewed.research_plan_authorization is not None
        identity = previewed.research_plan_authorization.authorization_id
        if budget is not None:
            # Deliberately narrower than one clean pass of the plan, which the
            # approval boundary rightly refuses: an operator cannot grant a
            # budget that cannot cover the work. These tests are about the
            # executor's arithmetic in isolation, so the narrow approval is
            # placed directly rather than smuggled through confirmation.
            #
            # That shortcut is not what makes runtime refusal reachable. A grant
            # the real boundary accepts runs out too, once an attempt is charged
            # and does not finish; tests/research/test_runtime_budget_exhaustion
            # proves that end to end without forging anything.
            pending = self.approvals._pending.pop(identity)
            self.approvals._authorizations[identity] = replace(pending, budget=budget)
            return identity
        confirmed = self.approvals.process_confirm(
            self.request(
                "research_plan_authorization_confirm",
                authorization_id=identity,
                research_run_id=self.run_id,
                research_plan_question=QUESTION,
                research_plan_steps=steps,
            )
        )
        assert confirmed.success, confirmed.message
        return identity

    def start(
        self,
        execution: ResearchPlanExecutionApplicationService,
        steps: tuple[tuple[object, ...], ...],
        budget: ResearchAutonomyBudget | None = None,
    ) -> str:
        identity = self.approve(steps, budget)
        response = execution.process_start(
            self.request(
                "research_plan_execution_start",
                authorization_id=identity,
                research_run_id=self.run_id,
                research_plan_question=QUESTION,
                research_plan_steps=steps,
            )
        )
        assert response.success, response.message
        assert response.research_plan_execution is not None
        return response.research_plan_execution.plan_id

    def advance(
        self,
        execution: ResearchPlanExecutionApplicationService,
        execution_id: str,
    ) -> BrainResponse:
        return execution.process_advance(
            self.request(
                "research_plan_execution_advance",
                research_plan_id=execution_id,
            )
        )

    def status(
        self,
        execution: ResearchPlanExecutionApplicationService,
        execution_id: str,
    ) -> BrainResponse:
        return execution.process_status(
            self.request(
                "research_plan_execution_status",
                research_plan_id=execution_id,
            )
        )

    def cancel(
        self,
        execution: ResearchPlanExecutionApplicationService,
        execution_id: str,
    ) -> BrainResponse:
        return execution.process_cancel(
            self.request(
                "research_plan_execution_cancel",
                research_plan_id=execution_id,
            )
        )


class StatusTests(ForegroundFixture):
    def test_a_started_execution_can_be_inspected(self) -> None:
        execution = self.execution_service()
        execution_id = self.start(execution, (LOCAL_STEP,))

        response = self.status(execution, execution_id)

        self.assertTrue(response.success)
        self.assertIs(
            response.research_plan_execution.status,
            ResearchPlanExecutionStatus.RUNNING,
        )

    def test_status_reports_approved_spent_and_remaining_budget(self) -> None:
        execution = self.execution_service()
        execution_id = self.start(execution, (LOCAL_STEP,))

        message = self.status(execution, execution_id).message

        self.assertIn("Step advances: 0 of 5 used, 5 left", message)
        self.assertIn("Network operations: 0 of 3 used, 3 left", message)
        self.assertIn("Model calls: 0 of 0 used, 0 left", message)
        self.assertIn("Another advance is allowed: yes", message)

    def test_status_names_what_the_next_step_would_use(self) -> None:
        execution = self.execution_service()
        execution_id = self.start(execution, (NETWORK_STEP,))

        message = self.status(execution, execution_id).message

        self.assertIn("Next step capability: source_discovery", message)

    def test_status_advances_nothing_and_spends_nothing(self) -> None:
        registry = self.registry(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (LOCAL_STEP,))

        for _ in range(5):
            self.status(execution, execution_id)

        allowance = execution.allowance(execution_id)
        assert allowance is not None
        self.assertEqual(allowance.spend, ResearchExecutionSpend())
        self.assertEqual(
            self.operations[ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH].runs,
            0,
        )

    def test_a_cancelled_execution_stays_inspectable(self) -> None:
        execution = self.execution_service()
        execution_id = self.start(execution, (LOCAL_STEP,))
        self.cancel(execution, execution_id)

        response = self.status(execution, execution_id)

        self.assertTrue(response.success)
        self.assertIs(
            response.research_plan_execution.status,
            ResearchPlanExecutionStatus.CANCELLED,
        )


class AdvanceTests(ForegroundFixture):
    def test_one_advance_attempts_exactly_one_step(self) -> None:
        registry = self.registry(
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
            ResearchPlanStepCapability.SOURCE_DISCOVERY,
        )
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (LOCAL_STEP, NETWORK_STEP))

        self.advance(execution, execution_id)

        self.assertEqual(
            self.operations[ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH].runs,
            1,
        )
        self.assertEqual(
            self.operations[ResearchPlanStepCapability.SOURCE_DISCOVERY].runs,
            0,
        )

    def test_the_second_step_needs_a_second_explicit_advance(self) -> None:
        registry = self.registry(
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
            ResearchPlanStepCapability.SOURCE_DISCOVERY,
        )
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (LOCAL_STEP, NETWORK_STEP))

        self.advance(execution, execution_id)
        self.advance(execution, execution_id)

        self.assertEqual(
            self.operations[ResearchPlanStepCapability.SOURCE_DISCOVERY].runs,
            1,
        )

    def test_completing_every_step_completes_the_execution(self) -> None:
        registry = self.registry(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (LOCAL_STEP,))

        response = self.advance(execution, execution_id)

        self.assertIs(
            response.research_plan_execution.status,
            ResearchPlanExecutionStatus.COMPLETED,
        )

    def test_a_completed_execution_refuses_a_further_advance(self) -> None:
        registry = self.registry(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (LOCAL_STEP,))
        self.advance(execution, execution_id)

        response = self.advance(execution, execution_id)

        self.assertFalse(response.success)

    def test_an_unknown_execution_is_refused(self) -> None:
        execution = self.execution_service()

        response = self.advance(execution, "execution-nowhere")

        self.assertFalse(response.success)

    def test_a_cancelled_execution_refuses_an_advance(self) -> None:
        registry = self.registry(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (LOCAL_STEP,))
        self.cancel(execution, execution_id)

        response = self.advance(execution, execution_id)

        self.assertFalse(response.success)
        self.assertEqual(
            self.operations[ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH].runs,
            0,
        )

    def test_a_failing_operation_records_failure_not_refusal(self) -> None:
        registry = self.registry(
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
            succeeded=False,
        )
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (LOCAL_STEP,))

        response = self.advance(execution, execution_id)

        self.assertIs(
            response.research_plan_execution.steps[0].status,
            ResearchPlanStepStatus.FAILED,
        )

    def test_an_operation_that_did_nothing_blocks_rather_than_completes(self) -> None:
        registry = self.registry(
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
            performed=False,
        )
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (LOCAL_STEP,))

        response = self.advance(execution, execution_id)

        self.assertIs(
            response.research_plan_execution.steps[0].status,
            ResearchPlanStepStatus.BLOCKED,
        )


class BudgetArithmeticTests(ForegroundFixture):
    """Exact arithmetic against the real capability cost table."""

    def test_the_cost_table_is_what_these_tests_assume(self) -> None:
        """Assert the prices before asserting the sums."""
        self.assertEqual(
            cost_for(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH),
            cost_for(ResearchPlanStepCapability.NONE),
        )
        self.assertEqual(
            cost_for(ResearchPlanStepCapability.SOURCE_DISCOVERY).network_operations,
            1,
        )
        self.assertEqual(
            cost_for(
                ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH
            ).network_operations,
            0,
        )

    def test_each_advance_charges_exactly_its_declared_cost(self) -> None:
        registry = self.registry(
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
            ResearchPlanStepCapability.SOURCE_DISCOVERY,
        )
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (LOCAL_STEP, NETWORK_STEP))

        self.advance(execution, execution_id)
        after_local = execution.allowance(execution_id)
        self.advance(execution, execution_id)
        after_network = execution.allowance(execution_id)

        assert after_local is not None and after_network is not None
        self.assertEqual(after_local.spend.step_advances, 1)
        self.assertEqual(after_local.spend.network_operations, 0)
        self.assertEqual(after_network.spend.step_advances, 2)
        self.assertEqual(after_network.spend.network_operations, 1)

    def test_an_exhausted_network_budget_performs_no_network_operation(self) -> None:
        """The end-to-end arithmetic: two advances approved, one network call."""
        registry = self.registry(
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
            ResearchPlanStepCapability.SOURCE_DISCOVERY,
        )
        execution = self.execution_service(registry)
        execution_id = self.start(
            execution,
            (LOCAL_STEP, NETWORK_STEP, NETWORK_STEP),
            budget=ResearchAutonomyBudget(
                max_step_advances=3,
                max_network_operations=1,
                max_llm_operations=0,
                max_seconds=60.0,
            ),
        )

        first = self.advance(execution, execution_id)
        second = self.advance(execution, execution_id)
        third = self.advance(execution, execution_id)

        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertFalse(third.success)
        self.assertIn("does not cover the next step", third.message)
        self.assertEqual(
            self.operations[ResearchPlanStepCapability.SOURCE_DISCOVERY].runs,
            1,
        )
        allowance = execution.allowance(execution_id)
        assert allowance is not None
        self.assertEqual(allowance.spend.step_advances, 2)
        self.assertEqual(allowance.spend.network_operations, 1)

    def test_an_exhausted_advance_budget_attempts_nothing(self) -> None:
        registry = self.registry(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        execution = self.execution_service(registry)
        execution_id = self.start(
            execution,
            (LOCAL_STEP, LOCAL_STEP),
            budget=ResearchAutonomyBudget(
                max_step_advances=1,
                max_network_operations=0,
                max_llm_operations=0,
                max_seconds=60.0,
            ),
        )

        self.advance(execution, execution_id)
        refused = self.advance(execution, execution_id)

        self.assertFalse(refused.success)
        self.assertIn("not reached", refused.message)
        self.assertEqual(
            self.operations[ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH].runs,
            1,
        )

    def test_a_refusal_before_the_attempt_charges_nothing(self) -> None:
        registry = self.registry(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        execution = self.execution_service(registry)
        execution_id = self.start(
            execution,
            (LOCAL_STEP, LOCAL_STEP),
            budget=ResearchAutonomyBudget(
                max_step_advances=1,
                max_network_operations=0,
                max_llm_operations=0,
                max_seconds=60.0,
            ),
        )
        self.advance(execution, execution_id)
        before = execution.allowance(execution_id)

        self.advance(execution, execution_id)

        self.assertEqual(execution.allowance(execution_id), before)

    def test_a_failed_attempt_is_not_refunded(self) -> None:
        registry = self.registry(
            ResearchPlanStepCapability.SOURCE_DISCOVERY,
            succeeded=False,
        )
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (NETWORK_STEP,))

        self.advance(execution, execution_id)

        allowance = execution.allowance(execution_id)
        assert allowance is not None
        self.assertEqual(allowance.spend.step_advances, 1)
        self.assertEqual(allowance.spend.network_operations, 1)

    def test_cancelling_does_not_refund_spent_budget(self) -> None:
        registry = self.registry(ResearchPlanStepCapability.SOURCE_DISCOVERY)
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (NETWORK_STEP, NETWORK_STEP))
        self.advance(execution, execution_id)
        before = execution.allowance(execution_id)

        self.cancel(execution, execution_id)

        self.assertEqual(execution.allowance(execution_id), before)

    def test_active_time_counts_attempts_not_idle_waiting(self) -> None:
        """Idle time between advances is not charged, because nobody spent it."""
        registry = self.registry(
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
            duration=2.0,
        )
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (LOCAL_STEP,))
        self.clock.advance(600.0)

        self.advance(execution, execution_id)

        allowance = execution.allowance(execution_id)
        assert allowance is not None
        self.assertAlmostEqual(allowance.spend.active_seconds, 2.0, places=3)

    def test_no_spend_can_exceed_its_approved_bound(self) -> None:
        """The type refuses to represent an over-spend at all."""
        with self.assertRaises(ResearchError):
            ResearchExecutionAllowance(
                budget=ResearchAutonomyBudget(max_network_operations=1),
                spend=ResearchExecutionSpend(network_operations=2),
            )


class CancelTests(ForegroundFixture):
    def test_cancelling_moves_the_execution_to_cancelled(self) -> None:
        execution = self.execution_service()
        execution_id = self.start(execution, (LOCAL_STEP,))

        response = self.cancel(execution, execution_id)

        self.assertIs(
            response.research_plan_execution.status,
            ResearchPlanExecutionStatus.CANCELLED,
        )

    def test_cancelling_does_not_return_the_approval(self) -> None:
        execution = self.execution_service()
        execution_id = self.start(execution, (LOCAL_STEP,))

        self.cancel(execution, execution_id)

        spent = self.approvals.authorizations()[0]
        self.assertTrue(spent.is_consumed)
        self.assertEqual(spent.consumption.execution_id, execution_id)  # type: ignore[union-attr]

    def test_cancelling_creates_no_replacement_and_no_task(self) -> None:
        execution = self.execution_service()
        execution_id = self.start(execution, (LOCAL_STEP,))

        self.cancel(execution, execution_id)

        self.assertEqual(len(self.approvals.authorizations()), 1)
        self.assertEqual(
            [
                event.name
                for event in self.events
                if "background" in event.name or "task" in event.name
            ],
            [],
        )

    def test_cancelling_an_unknown_execution_is_refused(self) -> None:
        response = self.cancel(self.execution_service(), "execution-nowhere")

        self.assertFalse(response.success)


class RestartTests(ForegroundFixture):
    def test_spent_budget_survives_a_restart(self) -> None:
        registry = self.registry(ResearchPlanStepCapability.SOURCE_DISCOVERY)
        execution = self.execution_service(registry, persist=True)
        execution_id = self.start(execution, (NETWORK_STEP, NETWORK_STEP))
        self.advance(execution, execution_id)

        reopened = self.execution_service(self.registry(), persist=True)
        restored = reopened.restored_execution(execution_id)

        assert restored is not None
        assert restored.allowance is not None
        self.assertEqual(restored.allowance.spend.step_advances, 1)
        self.assertEqual(restored.allowance.spend.network_operations, 1)

    def test_a_restored_execution_cannot_be_advanced(self) -> None:
        registry = self.registry(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        execution = self.execution_service(registry, persist=True)
        execution_id = self.start(execution, (LOCAL_STEP, LOCAL_STEP))

        reopened = self.execution_service(
            self.registry(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH),
            persist=True,
        )
        response = self.advance(reopened, execution_id)

        self.assertFalse(response.success)
        self.assertEqual(
            self.operations[ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH].runs,
            0,
        )

    def test_restarting_does_not_return_the_approval(self) -> None:
        execution = self.execution_service(persist=True)
        execution_id = self.start(execution, (LOCAL_STEP,))

        reloaded = ResearchPlanAuthorizationApplicationService(
            self.manager,
            ResponseComposer(),
            authorization_store=JsonFileResearchPlanAuthorizationStore(
                self.root / "authorizations.json"
            ),
            event_bus=self.event_bus,
            clock=self.clock,
        )

        self.assertTrue(reloaded.authorizations()[0].is_consumed)
        self.assertEqual(
            reloaded.authorizations()[0].consumption.execution_id,  # type: ignore[union-attr]
            execution_id,
        )

    def test_nothing_advances_by_itself_at_startup(self) -> None:
        registry = self.registry(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        execution = self.execution_service(registry, persist=True)
        self.start(execution, (LOCAL_STEP,))

        self.execution_service(
            self.registry(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH),
            persist=True,
        )

        self.assertEqual(
            self.operations[ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH].runs,
            0,
        )


class NoLoopTests(ForegroundFixture):
    """There is no loop because there is no loop in the code."""

    def service_source(self) -> str:
        return (
            SRC_DIR / "cognition" / "ResearchPlanExecutionApplicationService.py"
        ).read_text(encoding="utf-8")

    def test_advancing_never_calls_itself(self) -> None:
        source = self.service_source()
        start = source.index("def process_advance")
        end = source.index("def _charge_elapsed")
        section = source[start:end]

        # Named exactly once: in its own definition. A second mention would
        # be the recursion this milestone exists to not have.
        self.assertEqual(section.count("process_advance"), 1)
        # Matched at the start of a statement rather than anywhere in the text.
        # A comment explaining that something committed "while this attempt was
        # being prepared" is prose about concurrency, not a loop, and a
        # substring check reads the two the same way.
        statements = [line.strip() for line in section.splitlines()]
        self.assertEqual([line for line in statements if line.startswith("while ")], [])
        self.assertNotIn("for step in plan.steps", section)

    def test_the_execution_service_reaches_no_scheduler_or_autonomy(self) -> None:
        source = self.service_source()

        for forbidden in (
            "ResearchAutonomyApplicationService",
            "BackgroundResearchSchedulerApplicationService",
            "BackgroundResearchTask",
            "ToolRuntime",
            "ToolExecutionService",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, source)

    def test_a_completed_execution_starts_nothing_else(self) -> None:
        registry = self.registry(ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH)
        execution = self.execution_service(registry)
        execution_id = self.start(execution, (LOCAL_STEP,))

        self.advance(execution, execution_id)

        self.assertEqual(len(self.approvals.authorizations()), 1)
        self.assertEqual(
            [
                event.name
                for event in self.events
                if event.name == "research.plan.execution.started"
            ],
            ["research.plan.execution.started"],
        )

    def test_no_dangerous_capability_exists(self) -> None:
        values = {member.value for member in ResearchPlanStepCapability}

        for forbidden in ("filesystem", "shell", "process", "tool", "command"):
            with self.subTest(name=forbidden):
                self.assertEqual([v for v in values if forbidden in v], [])


if __name__ == "__main__":
    unittest.main()
