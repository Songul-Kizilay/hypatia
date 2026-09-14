"""Bounded background scheduling of approved research tasks.

The scheduler drives the real autonomy service through the real engine, so any
budget it weakened or capability it invented would surface here. Time and
identifiers are injected, and no test sleeps or touches a network.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.BackgroundResearchEvents import (
    TASK_CANCELLED,
    TASK_COMPLETED,
    TASK_CREATED,
    TASK_INTERRUPTED,
    TASK_RETRY_SCHEDULED,
    TASK_STARTED,
)
from cognition.BackgroundResearchSchedulerApplicationService import (
    BackgroundResearchSchedulerApplicationService,
)
from cognition.CognitiveEngine import CognitiveEngine
from core.Bootstrap import Bootstrap
from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.BackgroundResearchTask import BackgroundResearchTask
from research.BackgroundResearchTaskStatus import BackgroundResearchTaskStatus
from research.BackgroundTaskOutcome import BackgroundTaskOutcome, outcome_for
from research.DeferredExecutionGrant import DeferredExecutionGrant
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.JsonFileBackgroundTaskStore import (
    MAX_BACKGROUND_TASK_STORE_TASKS,
    JsonFileBackgroundTaskStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchPlanAuthorization import capabilities_of, restrictions_of
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the ring system have a measured age?"
START = datetime(2026, 8, 23, tzinfo=UTC)


class StubClock:
    """Advance one second per read so ordering is deterministic."""

    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        value = self.now
        self.now += timedelta(seconds=1)
        return value


class StaticDeferredGrantReader:
    def __init__(self, grant: DeferredExecutionGrant | None) -> None:
        self.grant = grant

    def active_for_task(self, task_id: str) -> DeferredExecutionGrant | None:
        if self.grant is not None and self.grant.task_id == task_id:
            return self.grant
        return None


class SchedulerFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        document = self.root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        self.document_path = document
        self.task_path = self.root / "tasks.json"
        self.run_path = self.root / "runs.json"
        self.identifiers = count(1)
        self.clock = StubClock()
        self.engine, self.event_bus = self.build_runtime()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def build_runtime(
        self,
        persist: bool = True,
        max_tasks_per_cycle: int = 1,
        max_active_tasks: int = 20,
    ) -> tuple[CognitiveEngine, EventBus]:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        knowledge_engine = KnowledgeEngine()
        knowledge_engine.load(self.document_path)
        session_manager = SessionManager(event_bus)
        run_manager = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        run_manager.load()
        engine = CognitiveEngine(
            knowledge_engine,
            memory_manager,
            Planner(),
            event_bus,
            ResponseComposer(),
            session_manager,
            SessionRenameTransactionService(
                session_manager=session_manager,
                memory_manager=memory_manager,
                event_bus=event_bus,
            ),
            research_run_manager=run_manager,
        )
        engine._background_research_scheduler = (
            BackgroundResearchSchedulerApplicationService(
                engine._research_autonomy_service,
                ResponseComposer(),
                executions=engine._research_plan_execution_service,
                task_store=(
                    JsonFileBackgroundTaskStore(self.task_path) if persist else None
                ),
                event_bus=event_bus,
                clock=self.clock,
                id_factory=lambda: f"task-{next(self.identifiers)}",
                max_tasks_per_cycle=max_tasks_per_cycle,
                max_active_tasks=max_active_tasks,
            )
        )
        return engine, event_bus

    def start_execution(
        self,
        engine: CognitiveEngine,
        *drafts: ResearchPlanStepDraftInput,
    ) -> str:
        response = engine.process(
            BrainRequest(
                message="Start research plan",
                metadata={
                    "intent": "research_plan_execution_start",
                    "research_plan_question": QUESTION,
                    "research_plan_steps": drafts,
                },
            )
        )
        assert response.research_plan_execution is not None
        return response.research_plan_execution.plan_id

    def create_task(
        self,
        engine: CognitiveEngine,
        execution_id: str,
        budget: ResearchAutonomyBudget | None = None,
        max_retries: int | None = None,
    ) -> str:
        metadata: dict[str, object] = {
            "intent": "background_research_task_create",
            "research_plan_id": execution_id,
        }
        if budget is not None:
            metadata["research_autonomy_budget"] = budget
        if max_retries is not None:
            metadata["background_task_max_retries"] = max_retries
        response = engine.process(
            BrainRequest(message="Create background task", metadata=metadata)
        )
        assert response.background_research_task is not None
        return response.background_research_task.task_id

    @staticmethod
    def task_action(engine: CognitiveEngine, intent: str, task_id: str):  # type: ignore[no-untyped-def]
        return engine.process(
            BrainRequest(
                message="Background task",
                metadata={"intent": intent, "background_task_id": task_id},
            )
        )

    @staticmethod
    def run_cycle(engine: CognitiveEngine, cancellation_token: object = None):  # type: ignore[no-untyped-def]
        return engine.process(
            BrainRequest(
                message="Run background worker cycle",
                metadata={"intent": "background_research_worker_cycle"},
                cancellation_token=cancellation_token,  # type: ignore[arg-type]
            )
        )

    def task(self, engine: CognitiveEngine, task_id: str) -> BackgroundResearchTask:
        for candidate in engine._background_research_scheduler.tasks():
            if candidate.task_id == task_id:
                return candidate
        raise AssertionError(f"No task {task_id}")

    @staticmethod
    def search_step() -> ResearchPlanStepDraftInput:
        return ResearchPlanStepDraftInput(
            instruction="Search local knowledge",
            capability="local_knowledge_search",
        )


class BackgroundSchedulerTests(SchedulerFixture):
    def deferred_grant(self, task_id: str) -> DeferredExecutionGrant:
        task = self.task(self.engine, task_id)
        plan = self.engine.live_research_plan(task.execution_id)
        assert plan is not None
        self.engine._research_plan_execution_service._allowances[task.execution_id] = (
            ResearchExecutionAllowance(ResearchAutonomyBudget())
        )
        return DeferredExecutionGrant(
            grant_id=f"grant-{task_id}",
            task_id=task.task_id,
            execution_id=task.execution_id,
            plan_digest=plan_digest(plan),
            capabilities=capabilities_of(plan),
            # Recorded as a real grant records it. Omitting it now means
            # "never recorded", which is deliberately not eligible.
            approved_restrictions=restrictions_of(plan),
            task_budget=task.budget,
            granted_at=START,
            granted_by=DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR,
        )

    def test_exact_deferred_run_requires_live_exact_grant(self) -> None:
        execution_id = self.start_execution(self.engine, self.search_step())
        task_id = self.create_task(self.engine, execution_id)
        result = self.engine.run_exact_deferred_background_task(task_id)
        self.assertIsNone(result)
        self.assertIs(
            self.task(self.engine, task_id).status,
            BackgroundResearchTaskStatus.PENDING,
        )

    def test_exact_deferred_run_never_falls_back_to_older_task(self) -> None:
        first_execution = self.start_execution(self.engine, self.search_step())
        second_execution = self.start_execution(self.engine, self.search_step())
        first_task = self.create_task(self.engine, first_execution)
        second_task = self.create_task(self.engine, second_execution)
        self.engine._background_research_scheduler._deferred_grants = (
            StaticDeferredGrantReader(self.deferred_grant(second_task))
        )
        result = self.engine.run_exact_deferred_background_task(second_task)
        self.assertIsNotNone(result)
        self.assertIs(
            self.task(self.engine, first_task).status,
            BackgroundResearchTaskStatus.PENDING,
        )
        self.assertIs(
            self.task(self.engine, second_task).status,
            BackgroundResearchTaskStatus.COMPLETED,
        )

    def test_create_persists_a_pending_task(self) -> None:
        execution_id = self.start_execution(self.engine, self.search_step())

        task_id = self.create_task(self.engine, execution_id)

        task = self.task(self.engine, task_id)
        self.assertIs(task.status, BackgroundResearchTaskStatus.PENDING)
        self.assertEqual(task.execution_id, execution_id)
        stored = JsonFileBackgroundTaskStore(self.task_path).load()
        self.assertEqual([entry.task_id for entry in stored], [task_id])

    def test_worker_runs_one_approved_task_to_completion(self) -> None:
        execution_id = self.start_execution(self.engine, self.search_step())
        task_id = self.create_task(self.engine, execution_id)

        self.run_cycle(self.engine)

        task = self.task(self.engine, task_id)
        self.assertIs(task.status, BackgroundResearchTaskStatus.COMPLETED)
        self.assertEqual(task.outcome, BackgroundTaskOutcome.COMPLETED.value)

    def test_completed_task_is_not_run_again(self) -> None:
        execution_id = self.start_execution(self.engine, self.search_step())
        task_id = self.create_task(self.engine, execution_id)
        self.run_cycle(self.engine)

        response = self.run_cycle(self.engine)

        self.assertIn("Tasks run this cycle: 0", response.message)
        self.assertIs(
            self.task(self.engine, task_id).status,
            BackgroundResearchTaskStatus.COMPLETED,
        )

    def test_pause_prevents_execution_and_resume_allows_it(self) -> None:
        execution_id = self.start_execution(self.engine, self.search_step())
        task_id = self.create_task(self.engine, execution_id)

        self.task_action(self.engine, "background_research_task_pause", task_id)
        self.run_cycle(self.engine)

        self.assertIs(
            self.task(self.engine, task_id).status,
            BackgroundResearchTaskStatus.PAUSED,
        )

        self.task_action(self.engine, "background_research_task_resume", task_id)
        self.run_cycle(self.engine)

        self.assertIs(
            self.task(self.engine, task_id).status,
            BackgroundResearchTaskStatus.COMPLETED,
        )

    def test_cancelled_task_never_runs(self) -> None:
        execution_id = self.start_execution(self.engine, self.search_step())
        task_id = self.create_task(self.engine, execution_id)

        self.task_action(self.engine, "background_research_task_cancel", task_id)
        self.run_cycle(self.engine)

        self.assertIs(
            self.task(self.engine, task_id).status,
            BackgroundResearchTaskStatus.CANCELLED,
        )

    def test_cancelled_task_cannot_be_resumed(self) -> None:
        execution_id = self.start_execution(self.engine, self.search_step())
        task_id = self.create_task(self.engine, execution_id)
        self.task_action(self.engine, "background_research_task_cancel", task_id)

        response = self.task_action(
            self.engine,
            "background_research_task_resume",
            task_id,
        )

        self.assertFalse(response.success)
        self.assertIs(
            self.task(self.engine, task_id).status,
            BackgroundResearchTaskStatus.CANCELLED,
        )

    def test_budget_exhaustion_schedules_a_bounded_retry(self) -> None:
        execution_id = self.start_execution(
            self.engine,
            *(self.search_step() for _ in range(4)),
        )
        task_id = self.create_task(
            self.engine,
            execution_id,
            budget=ResearchAutonomyBudget(max_step_advances=1),
            max_retries=1,
        )

        self.run_cycle(self.engine)

        task = self.task(self.engine, task_id)
        self.assertIs(task.status, BackgroundResearchTaskStatus.PENDING)
        self.assertEqual(task.retry_count, 1)
        self.assertEqual(
            task.outcome,
            BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED.value,
        )

    def test_retry_limit_stops_further_attempts(self) -> None:
        execution_id = self.start_execution(
            self.engine,
            *(self.search_step() for _ in range(6)),
        )
        task_id = self.create_task(
            self.engine,
            execution_id,
            budget=ResearchAutonomyBudget(max_step_advances=1),
            max_retries=1,
        )

        self.run_cycle(self.engine)
        self.run_cycle(self.engine)
        self.run_cycle(self.engine)

        task = self.task(self.engine, task_id)
        self.assertIs(task.status, BackgroundResearchTaskStatus.FAILED)
        self.assertEqual(task.retry_count, 1)

    def test_non_retryable_failure_is_not_retried(self) -> None:
        execution_id = self.start_execution(
            self.engine,
            ResearchPlanStepDraftInput(instruction="No capability declared"),
        )
        task_id = self.create_task(self.engine, execution_id, max_retries=3)

        self.run_cycle(self.engine)

        task = self.task(self.engine, task_id)
        self.assertIs(task.status, BackgroundResearchTaskStatus.FAILED)
        self.assertEqual(task.retry_count, 0)
        self.assertEqual(task.outcome, BackgroundTaskOutcome.BLOCKED.value)

    def test_task_budget_is_passed_through_unweakened(self) -> None:
        execution_id = self.start_execution(
            self.engine,
            *(self.search_step() for _ in range(3)),
        )
        budget = ResearchAutonomyBudget(max_step_advances=2)
        self.create_task(self.engine, execution_id, budget=budget)

        self.run_cycle(self.engine)

        state = self.engine._research_plan_execution_service.live_execution(
            execution_id
        )
        assert state is not None
        self.assertEqual(state.completed_steps, 2)

    def test_cycle_runs_at_most_its_configured_task_count(self) -> None:
        engine, _ = self.build_runtime(max_tasks_per_cycle=2)
        first = self.start_execution(engine, self.search_step())
        second = self.start_execution(engine, self.search_step())
        third = self.start_execution(engine, self.search_step())
        for execution_id in (first, second, third):
            self.create_task(engine, execution_id)

        response = self.run_cycle(engine)

        self.assertIn("Tasks run this cycle: 2", response.message)
        pending = [
            task
            for task in engine._background_research_scheduler.tasks()
            if task.status is BackgroundResearchTaskStatus.PENDING
        ]
        self.assertEqual(len(pending), 1)

    def test_active_task_capacity_is_enforced(self) -> None:
        engine, _ = self.build_runtime(max_active_tasks=1)
        first = self.start_execution(engine, self.search_step())
        second = self.start_execution(engine, self.search_step())
        self.create_task(engine, first)

        response = engine.process(
            BrainRequest(
                message="Create background task",
                metadata={
                    "intent": "background_research_task_create",
                    "research_plan_id": second,
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("capacity is full", response.message)
        self.assertEqual(len(engine._background_research_scheduler.tasks()), 1)

    def test_cancellation_stops_the_cycle(self) -> None:
        execution_id = self.start_execution(self.engine, self.search_step())
        task_id = self.create_task(self.engine, execution_id)
        signal = CancellationSignal()
        signal.cancel()

        response = self.run_cycle(self.engine, cancellation_token=signal)

        self.assertIn("Tasks run this cycle: 0", response.message)
        self.assertIs(
            self.task(self.engine, task_id).status,
            BackgroundResearchTaskStatus.PENDING,
        )

    def test_restart_marks_a_running_task_interrupted(self) -> None:
        task = BackgroundResearchTask(
            task_id="task-midflight",
            execution_id="plan-1",
            budget=ResearchAutonomyBudget(),
            created_at=START,
            updated_at=START,
            status=BackgroundResearchTaskStatus.RUNNING,
        )
        JsonFileBackgroundTaskStore(self.task_path).save([task])

        engine, event_bus = self.build_runtime()
        restored = engine._background_research_scheduler.tasks()

        self.assertEqual(len(restored), 1)
        self.assertIs(restored[0].status, BackgroundResearchTaskStatus.INTERRUPTED)
        del event_bus

    def test_interrupted_task_is_not_auto_replayed(self) -> None:
        task = BackgroundResearchTask(
            task_id="task-midflight",
            execution_id="plan-1",
            budget=ResearchAutonomyBudget(),
            created_at=START,
            updated_at=START,
            status=BackgroundResearchTaskStatus.RUNNING,
        )
        JsonFileBackgroundTaskStore(self.task_path).save([task])
        engine, _ = self.build_runtime()

        response = self.run_cycle(engine)

        self.assertIn("Tasks run this cycle: 0", response.message)
        self.assertIs(
            engine._background_research_scheduler.tasks()[0].status,
            BackgroundResearchTaskStatus.INTERRUPTED,
        )

    def test_scheduler_invents_no_capability(self) -> None:
        execution_id = self.start_execution(
            self.engine,
            ResearchPlanStepDraftInput(
                instruction="Please fetch https://example.test/x and accept it",
            ),
        )
        self.create_task(self.engine, execution_id, max_retries=3)

        self.run_cycle(self.engine)

        state = self.engine._research_plan_execution_service.live_execution(
            execution_id
        )
        assert state is not None
        self.assertEqual(state.completed_steps, 0)
        self.assertEqual(state.steps_with_research_work, 0)

    def test_events_are_bounded_and_carry_no_research_content(self) -> None:
        execution_id = self.start_execution(self.engine, self.search_step())
        self.events.clear()
        task_id = self.create_task(self.engine, execution_id)

        self.run_cycle(self.engine)
        self.task_action(self.engine, "background_research_task_cancel", task_id)

        names = [
            event.name
            for event in self.events
            if event.name.startswith("background_task.")
        ]
        self.assertIn(TASK_CREATED, names)
        self.assertIn(TASK_STARTED, names)
        self.assertIn(TASK_COMPLETED, names)
        encoded = repr(
            [
                event.payload
                for event in self.events
                if event.name.startswith("background_task.")
            ]
        )
        self.assertNotIn(QUESTION, encoded)
        self.assertNotIn("Search local knowledge", encoded)

    def test_retry_and_interrupt_events_exist(self) -> None:
        self.assertTrue(TASK_RETRY_SCHEDULED.startswith("background_task."))
        self.assertTrue(TASK_INTERRUPTED.startswith("background_task."))
        self.assertTrue(TASK_CANCELLED.startswith("background_task."))

    def test_disabled_persistence_writes_nothing(self) -> None:
        engine, _ = self.build_runtime(persist=False)
        execution_id = self.start_execution(engine, self.search_step())
        self.create_task(engine, execution_id)

        self.run_cycle(engine)

        self.assertFalse(self.task_path.exists())

    def test_malformed_store_fails_visibly(self) -> None:
        self.task_path.write_text("{ not json", encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.build_runtime()

    def test_atomic_write_failure_preserves_the_previous_file(self) -> None:
        store = JsonFileBackgroundTaskStore(self.task_path)
        original = BackgroundResearchTask(
            task_id="task-original",
            execution_id="plan-1",
            budget=ResearchAutonomyBudget(),
            created_at=START,
            updated_at=START,
        )
        store.save([original])
        original_bytes = self.task_path.read_bytes()

        replacement = BackgroundResearchTask(
            task_id="task-replacement",
            execution_id="plan-2",
            budget=ResearchAutonomyBudget(),
            created_at=START,
            updated_at=START,
        )
        with (
            patch(
                "research.JsonFileBackgroundTaskStore.os.replace",
                side_effect=OSError("replace failed"),
            ),
            self.assertRaises(ResearchError),
        ):
            store.save([replacement])

        self.assertEqual(self.task_path.read_bytes(), original_bytes)

    def test_store_rejects_unknown_schema_and_duplicates(self) -> None:
        self.task_path.write_text(
            json.dumps({"schema_version": 2, "tasks": []}),
            encoding="utf-8",
        )
        with self.assertRaises(ResearchError):
            JsonFileBackgroundTaskStore(self.task_path).load()

        duplicate = BackgroundResearchTask(
            task_id="task-duplicate",
            execution_id="plan-1",
            budget=ResearchAutonomyBudget(),
            created_at=START,
            updated_at=START,
        )
        with self.assertRaises(ResearchError):
            JsonFileBackgroundTaskStore(self.task_path).save([duplicate, duplicate])

    def test_store_rejects_too_many_tasks(self) -> None:
        overflow = [
            BackgroundResearchTask(
                task_id=f"task-{index}",
                execution_id="plan-1",
                budget=ResearchAutonomyBudget(),
                created_at=START,
                updated_at=START,
            )
            for index in range(MAX_BACKGROUND_TASK_STORE_TASKS + 1)
        ]

        with self.assertRaises(ResearchError):
            JsonFileBackgroundTaskStore(self.task_path).save(overflow)

    def test_stored_document_carries_no_research_content(self) -> None:
        execution_id = self.start_execution(self.engine, self.search_step())
        self.create_task(self.engine, execution_id)
        self.run_cycle(self.engine)

        raw = self.task_path.read_text(encoding="utf-8")

        self.assertNotIn(QUESTION, raw)
        self.assertNotIn("Search local knowledge", raw)
        self.assertNotIn("Saturn has rings", raw)


class BackgroundTaskOutcomeTests(unittest.TestCase):
    def test_every_stop_reason_has_a_declared_outcome(self) -> None:
        for reason in AutonomyStopReason:
            with self.subTest(reason=reason):
                outcome_for(reason)

    def test_only_budget_exhaustion_is_retryable(self) -> None:
        retryable = {
            reason for reason in AutonomyStopReason if outcome_for(reason).retryable
        }

        self.assertEqual(
            retryable,
            {
                AutonomyStopReason.STEP_BUDGET_EXHAUSTED,
                AutonomyStopReason.NETWORK_BUDGET_EXHAUSTED,
                AutonomyStopReason.LLM_BUDGET_EXHAUSTED,
                AutonomyStopReason.TIME_BUDGET_EXHAUSTED,
            },
        )

    def test_authorization_and_policy_stops_are_not_retryable(self) -> None:
        for reason in (
            AutonomyStopReason.STEP_BLOCKED,
            AutonomyStopReason.STEP_FAILED,
            AutonomyStopReason.STEP_INTERRUPTED,
            AutonomyStopReason.CANCELLED,
        ):
            with self.subTest(reason=reason):
                self.assertFalse(outcome_for(reason).retryable)

    def test_invalid_stop_reason_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            outcome_for("step_failed")  # type: ignore[arg-type]


class BootstrapBackgroundResearchTests(unittest.TestCase):
    def test_scheduling_is_disabled_without_the_flag(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {}, clear=True),
        ):
            path = Path(directory)
            bootstrap = Bootstrap(
                memory_path=path / "memory.json",
                session_path=path / "sessions.json",
            )

            self.assertIsNone(bootstrap._background_task_store())

    def test_flag_enables_a_store_beside_the_run_store(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"HYPATIA_BACKGROUND_RESEARCH_ENABLED": "true"},
                clear=True,
            ),
        ):
            path = Path(directory)
            bootstrap = Bootstrap(
                memory_path=path / "memory.json",
                session_path=path / "sessions.json",
                research_run_path=path / "runs.json",
            )

            store = bootstrap._background_task_store()

            self.assertIsNotNone(store)
            assert store is not None
            self.assertEqual(
                store._path,
                path / "research_background_tasks.json",
            )

    def test_engine_wires_the_scheduler_over_the_autonomy_service(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            document = path / "knowledge.md"
            document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
            event_bus = EventBus()
            memory_manager = MemoryManager(event_bus)
            knowledge_engine = KnowledgeEngine()
            knowledge_engine.load(document)
            session_manager = SessionManager(event_bus)
            engine = CognitiveEngine(
                knowledge_engine,
                memory_manager,
                Planner(),
                event_bus,
                ResponseComposer(),
                session_manager,
                SessionRenameTransactionService(
                    session_manager=session_manager,
                    memory_manager=memory_manager,
                    event_bus=event_bus,
                ),
            )

            scheduler = engine._background_research_scheduler
            self.assertIsInstance(
                scheduler,
                BackgroundResearchSchedulerApplicationService,
            )
            self.assertIs(
                scheduler._autonomy_service,
                engine._research_autonomy_service,
            )
            self.assertIsNone(scheduler._task_store)


if __name__ == "__main__":
    unittest.main()
