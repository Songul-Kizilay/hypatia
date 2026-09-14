"""The interface refreshes when the store changes, and only from the store.

The live complaint was that accepted-source counts did not update after an
acceptance. The fix has two halves and they are deliberately separate: the event
bus says *that* a run changed, and the interface then reads *what* it now
contains. Nothing on screen is taken from a payload.

That separation is what these tests protect. A count sourced from an event can
disagree with the store, and an interface showing a number the store does not
hold is exactly the failure this area keeps producing — so the tests drive the
real ingestion pipeline, drain the real signal, and read the counts back through
the same read model the window uses.

Tk is not involved. The signal is thread-safe and the read model is Tk-free, so
the whole chain except widget assignment is testable headlessly.
"""

from __future__ import annotations

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
from cognition.SourceIngestionEvents import (
    ATTACH_COMPLETED,
    INDEX_COMPLETED,
    SourceIngestionEvents,
)
from core.Exceptions import ResearchError
from desktop.ResearchStateRefreshSignal import ResearchStateRefreshSignal
from desktop.ResearchWorkspaceReadModel import ResearchWorkspaceReadModel
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does web cache deception have a documented mitigation?"
FETCHED = datetime(2026, 8, 1, tzinfo=UTC)


class StubFetcher:
    def __init__(self, source: ResearchSource | None) -> None:
        self.source = source

    def fetch(self, url: str) -> ResearchSource:
        if self.source is None:
            raise ResearchError("Research source could not be fetched.")
        return self.source


def source(slug: str) -> ResearchSource:
    return ResearchSource(
        url=f"https://example.test/{slug}",
        title=f"Source {slug}",
        content=f"Body about {slug}, shared caches, and path suffixes.",
        content_type="text/html",
        fetched_at=FETCHED,
    )


class RefreshSignalTests(unittest.TestCase):
    """Level A: only canonical acceptance asks for a re-read."""

    def setUp(self) -> None:
        self.signal = ResearchStateRefreshSignal()

    def note(self, name: str, **payload: object) -> None:
        self.signal.note(Event(name=name, payload=dict(payload)))

    def test_an_acceptance_marks_its_run(self) -> None:
        self.note(ATTACH_COMPLETED, run_id="run-1", attached_to_run=True)

        self.assertEqual(self.signal.drain(), ("run-1",))

    def test_an_index_event_marks_nothing(self) -> None:
        self.note(INDEX_COMPLETED, run_id="run-1", attached_to_run=False)

        self.assertEqual(self.signal.drain(), ())

    def test_a_payload_denying_attachment_marks_nothing(self) -> None:
        """The name alone is not enough; the payload must claim acceptance."""
        self.note(ATTACH_COMPLETED, run_id="run-1", attached_to_run=False)

        self.assertEqual(self.signal.drain(), ())

    def test_a_missing_run_identifier_marks_nothing(self) -> None:
        for run_id in ("", "   ", None, 7):
            with self.subTest(run_id=run_id):
                self.note(ATTACH_COMPLETED, run_id=run_id, attached_to_run=True)
                self.assertEqual(self.signal.drain(), ())

    def test_one_run_is_recorded_once_however_often_it_changes(self) -> None:
        for _ in range(3):
            self.note(ATTACH_COMPLETED, run_id="run-1", attached_to_run=True)

        self.assertEqual(self.signal.drain(), ("run-1",))

    def test_draining_clears_the_pending_set(self) -> None:
        self.note(ATTACH_COMPLETED, run_id="run-1", attached_to_run=True)
        self.signal.drain()

        self.assertFalse(self.signal.pending)
        self.assertEqual(self.signal.drain(), ())

    def test_distinct_runs_are_kept_apart(self) -> None:
        self.note(ATTACH_COMPLETED, run_id="run-1", attached_to_run=True)
        self.note(ATTACH_COMPLETED, run_id="run-2", attached_to_run=True)

        self.assertEqual(self.signal.drain(), ("run-1", "run-2"))

    def test_the_signal_subscribes_itself_to_a_bus(self) -> None:
        bus = EventBus()
        signal = ResearchStateRefreshSignal(bus)
        SourceIngestionEvents(bus, "attempt-1").attach_completed(
            "https://example.test/a",
            "document-1",
            "run-1",
            1,
        )

        self.assertEqual(signal.drain(), ("run-1",))


class RefreshFromCanonicalStateTests(unittest.TestCase):
    """Level B: drive the real pipeline and read counts back from the store."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.manager.load()
        self.event_bus = EventBus()
        self.signal = ResearchStateRefreshSignal(self.event_bus)
        self.fetcher = StubFetcher(source("first"))
        self.engine = self.build_engine()
        self.run_id = self.manager.create(QUESTION).run_id

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def build_engine(self) -> CognitiveEngine:
        memory_manager = MemoryManager(self.event_bus)
        session_manager = SessionManager(self.event_bus)
        return CognitiveEngine(
            self.knowledge_engine,
            memory_manager,
            Planner(),
            self.event_bus,
            ResponseComposer(),
            session_manager,
            SessionRenameTransactionService(
                session_manager=session_manager,
                memory_manager=memory_manager,
                event_bus=self.event_bus,
            ),
            research_source_fetcher=self.fetcher,  # type: ignore[arg-type]
            research_run_manager=self.manager,
        )

    def load(self, slug: str, run_id: str | None) -> None:
        self.fetcher.source = source(slug)
        metadata: dict[str, object] = {
            "intent": "research_source_load",
            "research_url": f"https://example.test/{slug}",
        }
        if run_id is not None:
            metadata["research_run_id"] = run_id
        self.engine.process(BrainRequest(message="Load source", metadata=metadata))

    def displayed_source_count(self, run_id: str) -> int:
        """Read the count the way the window does: from the store, not an event."""
        run = self.manager.get(run_id)
        self.assertIn(
            f"sources: {len(run.sources)}",
            ResearchWorkspaceReadModel.run_progress_text(run).casefold(),
        )
        return len(run.sources)

    def test_zero_to_one_acceptance_asks_for_a_refresh(self) -> None:
        self.assertEqual(self.displayed_source_count(self.run_id), 0)

        self.load("first", self.run_id)

        self.assertEqual(self.signal.drain(), (self.run_id,))
        self.assertEqual(self.displayed_source_count(self.run_id), 1)

    def test_an_index_only_load_asks_for_no_refresh(self) -> None:
        self.load("first", None)

        self.assertEqual(self.signal.drain(), ())
        self.assertEqual(self.displayed_source_count(self.run_id), 0)

    def test_a_failed_attachment_asks_for_no_refresh(self) -> None:
        with patch.object(
            ResearchRunManager,
            "add_source",
            side_effect=ResearchError("run refused the source"),
        ):
            self.load("first", self.run_id)

        self.assertEqual(self.signal.drain(), ())
        self.assertEqual(self.displayed_source_count(self.run_id), 0)

    def test_a_retry_after_failure_refreshes_exactly_once(self) -> None:
        with patch.object(
            ResearchRunManager,
            "add_source",
            side_effect=ResearchError("transient refusal"),
        ):
            self.load("first", self.run_id)
        self.assertEqual(self.signal.drain(), ())

        self.load("first", self.run_id)

        self.assertEqual(self.signal.drain(), (self.run_id,))
        self.assertEqual(self.displayed_source_count(self.run_id), 1)

    def test_a_duplicate_load_does_not_double_count(self) -> None:
        self.load("first", self.run_id)
        self.signal.drain()

        self.load("first", self.run_id)

        self.assertEqual(self.signal.drain(), ())
        self.assertEqual(self.displayed_source_count(self.run_id), 1)

    def test_two_acceptances_leave_the_store_and_display_agreeing(self) -> None:
        self.load("first", self.run_id)
        self.load("second", self.run_id)

        self.assertEqual(self.signal.drain(), (self.run_id,))
        self.assertEqual(self.displayed_source_count(self.run_id), 2)

    def test_no_intermediate_event_can_show_a_count_the_store_lacks(self) -> None:
        """Event order must not produce a temporarily contradictory display.

        Every ingestion event is replayed in order, and after each one the count
        the interface would show is compared against the store. Because the
        count is read rather than carried, they cannot diverge at any point.
        """
        replayed: list[Event] = []
        self.event_bus.subscribe("*", replayed.append)

        self.load("first", self.run_id)

        signal = ResearchStateRefreshSignal()
        for event in replayed:
            if not event.name.startswith("source_ingestion."):
                continue
            signal.note(event)
            for run_id in signal.drain():
                self.assertEqual(
                    self.displayed_source_count(run_id),
                    len(self.manager.get(run_id).sources),
                )

    def test_a_refresh_reads_the_latest_state_not_the_event_state(self) -> None:
        """The event says which run changed; the store says what it holds."""
        self.load("first", self.run_id)
        self.load("second", self.run_id)

        changed = self.signal.drain()

        self.assertEqual(changed, (self.run_id,))
        self.assertEqual(len(self.manager.get(changed[0]).sources), 2)


if __name__ == "__main__":
    unittest.main()
