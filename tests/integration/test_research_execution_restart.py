"""Restart behavior for persisted research-plan execution.

Two independent runtimes share one execution store. The second must report what
the first actually did — never more. A step recorded as running when the first
runtime disappeared becomes interrupted, and nothing is replayed.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ResearchPlanExecutionEvents import EXECUTION_RESTORED
from core.Bootstrap import Bootstrap
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchExecutionStore import JsonFileResearchExecutionStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchPlanExecutionSnapshot import (
    ResearchPlanExecutionSnapshot,
    ResearchPlanExecutionStepSnapshot,
)
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the ring system have a measured age?"


class RestartFixture(unittest.TestCase):
    """Build independent runtimes over one shared execution store path."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        document = self.root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        self.document_path = document
        self.execution_path = self.root / "executions.json"
        self.run_path = self.root / "runs.json"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def build_runtime(
        self,
        persist: bool = True,
    ) -> tuple[CognitiveEngine, EventBus, ResearchRunManager]:
        """Create one fresh runtime, optionally sharing the execution store."""
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
            research_execution_store=(
                JsonFileResearchExecutionStore(self.execution_path) if persist else None
            ),
        )
        return engine, event_bus, run_manager

    @staticmethod
    def start(engine: CognitiveEngine, *drafts: ResearchPlanStepDraftInput) -> str:
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

    @staticmethod
    def advance(engine: CognitiveEngine, plan_id: str):  # type: ignore[no-untyped-def]
        return engine.process(
            BrainRequest(
                message="Advance research plan",
                metadata={
                    "intent": "research_plan_execution_advance",
                    "research_plan_id": plan_id,
                },
            )
        )

    @staticmethod
    def status(engine: CognitiveEngine, plan_id: str):  # type: ignore[no-untyped-def]
        return engine.process(
            BrainRequest(
                message="Research plan execution",
                metadata={
                    "intent": "research_plan_execution_status",
                    "research_plan_id": plan_id,
                },
            )
        )

    @staticmethod
    def search_step() -> ResearchPlanStepDraftInput:
        return ResearchPlanStepDraftInput(
            instruction="Search local knowledge",
            capability="local_knowledge_search",
        )


class ResearchExecutionRestartTests(RestartFixture):
    def test_completed_work_survives_and_is_never_replayed(self) -> None:
        runtime_a, _, _ = self.build_runtime()
        plan_id = self.start(runtime_a, self.search_step(), self.search_step())
        self.advance(runtime_a, plan_id)
        del runtime_a

        runtime_b, event_bus_b, _ = self.build_runtime()
        events: list[Event] = []
        event_bus_b.subscribe("*", events.append)

        response = self.status(runtime_b, plan_id)

        self.assertIn("restored", response.message.lower())
        self.assertIn("step-1: completed", response.message)
        self.assertIn("step-2: pending", response.message)
        self.assertIn("cannot be advanced", response.message)
        self.assertEqual(events, [])

    def test_running_step_restores_as_interrupted(self) -> None:
        snapshot = ResearchPlanExecutionSnapshot(
            plan_id="plan-midflight",
            question=QUESTION,
            status=ResearchPlanExecutionStatus.RUNNING,
            steps=(
                ResearchPlanExecutionStepSnapshot(
                    step_id="step-1",
                    capability=ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                    status=ResearchPlanStepStatus.COMPLETED,
                    operation="local_knowledge_search",
                    work_performed=True,
                ),
                ResearchPlanExecutionStepSnapshot(
                    step_id="step-2",
                    capability=ResearchPlanStepCapability.SOURCE_FETCH,
                    status=ResearchPlanStepStatus.RUNNING,
                ),
            ),
            recorded_at=datetime(2026, 8, 23, tzinfo=UTC),
        )
        JsonFileResearchExecutionStore(self.execution_path).save([snapshot])

        runtime_b, _, _ = self.build_runtime()

        response = self.status(runtime_b, "plan-midflight")

        self.assertIn("step-1: completed", response.message)
        self.assertIn("step-2: interrupted", response.message)
        self.assertNotIn("step-2: completed", response.message)
        self.assertIn("What those operations did is unknown", response.message)
        self.assertIn("nothing was replayed", response.message)

    def test_restore_emits_a_bounded_event(self) -> None:
        runtime_a, _, _ = self.build_runtime()
        plan_id = self.start(runtime_a, self.search_step())
        self.advance(runtime_a, plan_id)
        del runtime_a

        event_bus = EventBus()
        events: list[Event] = []
        event_bus.subscribe("*", events.append)
        memory_manager = MemoryManager(event_bus)
        knowledge_engine = KnowledgeEngine()
        knowledge_engine.load(self.document_path)
        session_manager = SessionManager(event_bus)
        CognitiveEngine(
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
            research_execution_store=JsonFileResearchExecutionStore(
                self.execution_path
            ),
        )

        restored = [event for event in events if event.name == EXECUTION_RESTORED]
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0].payload["plan_id"], plan_id)
        self.assertEqual(restored[0].payload["interrupted_steps"], 0)
        self.assertNotIn("Search local knowledge", repr(restored[0].payload))

    def test_restored_execution_cannot_be_advanced_or_replayed(self) -> None:
        runtime_a, _, run_manager_a = self.build_runtime()
        plan_id = self.start(runtime_a, self.search_step())
        self.advance(runtime_a, plan_id)
        del runtime_a

        runtime_b, _, run_manager_b = self.build_runtime()
        response = self.advance(runtime_b, plan_id)

        self.assertFalse(response.success)
        self.assertIsNone(response.research_plan_execution)
        self.assertEqual(run_manager_b.list(), run_manager_a.list())

    def test_terminal_and_cancelled_executions_survive_restart(self) -> None:
        runtime_a, _, _ = self.build_runtime()
        completed_plan = self.start(runtime_a, self.search_step())
        self.advance(runtime_a, completed_plan)
        cancelled_plan = self.start(runtime_a, self.search_step())
        runtime_a.process(
            BrainRequest(
                message="Cancel research plan",
                metadata={
                    "intent": "research_plan_execution_cancel",
                    "research_plan_id": cancelled_plan,
                },
            )
        )
        del runtime_a

        runtime_b, _, _ = self.build_runtime()

        self.assertIn(
            "Status: completed",
            self.status(runtime_b, completed_plan).message,
        )
        self.assertIn(
            "Status: cancelled",
            self.status(runtime_b, cancelled_plan).message,
        )

    def test_disabled_persistence_keeps_ephemeral_behavior(self) -> None:
        runtime_a, _, _ = self.build_runtime(persist=False)
        plan_id = self.start(runtime_a, self.search_step())
        self.advance(runtime_a, plan_id)
        del runtime_a

        self.assertFalse(self.execution_path.exists())

        runtime_b, _, _ = self.build_runtime(persist=False)
        response = self.status(runtime_b, plan_id)

        self.assertFalse(response.success)
        self.assertIn("It is not resumed after a restart.", response.message)

    def test_corrupted_store_refuses_rather_than_fabricating_state(self) -> None:
        self.execution_path.write_text("{ not json", encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.build_runtime()

    def test_duplicate_execution_ids_refuse_safely(self) -> None:
        snapshot = ResearchPlanExecutionSnapshot(
            plan_id="plan-duplicate",
            question=QUESTION,
            status=ResearchPlanExecutionStatus.RUNNING,
            steps=(
                ResearchPlanExecutionStepSnapshot(
                    step_id="step-1",
                    capability=ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                    status=ResearchPlanStepStatus.PENDING,
                ),
            ),
            recorded_at=datetime(2026, 8, 23, tzinfo=UTC),
        )
        with self.assertRaises(ResearchError):
            JsonFileResearchExecutionStore(self.execution_path).save(
                [snapshot, snapshot]
            )

    def test_persistence_failure_refuses_the_attempt_without_erasing_state(
        self,
    ) -> None:
        """A write that did not land is not a boundary an attempt may cross.

        This once asserted that the advance carried on and completed the step.
        It cannot any more: the attempt is written down before the provider is
        reachable precisely so that a crash leaves a record, and running the
        operation anyway would recreate the window that exists to be closed.

        What the test was really protecting is unchanged and still asserted
        here. Live state is not erased, the failure is announced rather than
        swallowed, and nothing durable is quietly replaced by an empty record.
        """
        runtime_a, event_bus, _ = self.build_runtime()
        plan_id = self.start(runtime_a, self.search_step())
        events: list[Event] = []
        event_bus.subscribe("*", events.append)

        with patch.object(
            JsonFileResearchExecutionStore,
            "save",
            side_effect=ResearchError("disk unavailable"),
        ):
            response = self.advance(runtime_a, plan_id)

        self.assertFalse(response.success)
        after = self.status(runtime_a, plan_id)
        assert after.research_plan_execution is not None
        self.assertEqual(after.research_plan_execution.completed_steps, 0)
        self.assertEqual(after.research_plan_execution.pending_steps, 1)
        failures = [
            event
            for event in events
            if event.name == "research.plan.execution.persistence_failed"
        ]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].payload["cause"], "ResearchError")

    def test_stored_document_duplicates_no_research_content(self) -> None:
        runtime_a, _, _ = self.build_runtime()
        plan_id = self.start(runtime_a, self.search_step())
        self.advance(runtime_a, plan_id)

        raw = self.execution_path.read_text(encoding="utf-8")

        self.assertIn(plan_id, raw)
        self.assertNotIn("Search local knowledge", raw)
        self.assertNotIn("Saturn has rings", raw)


class BootstrapExecutionPersistenceTests(unittest.TestCase):
    def test_persistence_is_disabled_without_the_flag(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {}, clear=True),
        ):
            path = Path(directory)
            bootstrap = Bootstrap(
                memory_path=path / "memory.json",
                session_path=path / "sessions.json",
            )

            self.assertIsNone(bootstrap._research_execution_store())

    def test_flag_enables_a_store_beside_the_run_store(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"HYPATIA_RESEARCH_EXECUTION_PERSISTENCE_ENABLED": "true"},
                clear=True,
            ),
        ):
            path = Path(directory)
            bootstrap = Bootstrap(
                memory_path=path / "memory.json",
                session_path=path / "sessions.json",
                research_run_path=path / "runs.json",
            )

            store = bootstrap._research_execution_store()

            self.assertIsNotNone(store)
            assert store is not None
            self.assertEqual(
                store._path,
                path / "research_executions.json",
            )

    def test_non_exact_flag_values_keep_persistence_disabled(self) -> None:
        for value in ("True", "1", "yes", ""):
            with (
                self.subTest(value=value),
                tempfile.TemporaryDirectory() as directory,
                patch.dict(
                    os.environ,
                    {"HYPATIA_RESEARCH_EXECUTION_PERSISTENCE_ENABLED": value},
                    clear=True,
                ),
            ):
                path = Path(directory)
                bootstrap = Bootstrap(
                    memory_path=path / "memory.json",
                    session_path=path / "sessions.json",
                )

                self.assertIsNone(bootstrap._research_execution_store())


if __name__ == "__main__":
    unittest.main()
