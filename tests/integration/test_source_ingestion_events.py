"""Ingestion events must describe the transaction, never flatter it.

The event stream is a second account of the same work the run store records, and
the danger of a second account is that it drifts into a better story. So the
tests pin three things.

Events fire only after the transition they name, except the `*_started` events
which claim nothing about outcome. Each real transition fires exactly once, so a
subscriber counting acceptances counts acceptances. And no sequence of events can
make a local index look like a research run accepting a source: the two facts
stay in separate fields and only one stage carries `attached_to_run`.

Nothing here touches a network; the fetcher is a stub.
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
    ATTACH_STARTED,
    FETCH_COMPLETED,
    FETCH_STARTED,
    INDEX_COMPLETED,
    INDEX_STARTED,
    INGESTION_CANCELLED,
    INGESTION_FAILED,
    VALIDATION_COMPLETED,
    VALIDATION_STARTED,
    IngestionFailureKind,
    IngestionStatus,
)
from core.CancellationSignal import CancellationSignal
from core.Exceptions import KnowledgeError, ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.SourceIdentity import identity_of
from research.SourceLoadStage import SourceLoadStage
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does web cache deception have a documented mitigation?"
FETCHED = datetime(2026, 8, 1, tzinfo=UTC)
URL = "https://example.test/page"

PAYLOAD_FIELDS = frozenset(
    {
        "attempt_id",
        "stage",
        "status",
        "resource_identity",
        "document_id",
        "run_id",
        "attached_to_run",
        "created_local_document",
        "safe_failure_recorded",
    }
)


class StubFetcher:
    def __init__(self, source: ResearchSource | None) -> None:
        self.source = source
        self.calls: list[str] = []

    def fetch(self, url: str) -> ResearchSource:
        self.calls.append(url)
        if self.source is None:
            raise ResearchError("Research source could not be fetched.")
        return self.source


def source(slug: str = "page", body: str = "") -> ResearchSource:
    return ResearchSource(
        url=f"https://example.test/{slug}",
        title=f"Source {slug}",
        content=body or f"Body about {slug} and shared cache keys.",
        content_type="text/html",
        fetched_at=FETCHED,
    )


class IngestionEventFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        self.manager.load()
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.fetcher = StubFetcher(source())

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

    def load(
        self,
        engine: CognitiveEngine,
        run_id: str | None,
        url: str = URL,
        cancellation_token: object = None,
    ) -> object:
        metadata: dict[str, object] = {
            "intent": "research_source_load",
            "research_url": url,
        }
        if run_id is not None:
            metadata["research_run_id"] = run_id
        return engine.process(
            BrainRequest(
                message="Load source",
                metadata=metadata,
                cancellation_token=cancellation_token,  # type: ignore[arg-type]
            )
        )

    def ingestion(self) -> list[Event]:
        return [
            event for event in self.events if event.name.startswith("source_ingestion.")
        ]

    def names(self) -> list[str]:
        return [event.name for event in self.ingestion()]

    def named(self, name: str) -> list[Event]:
        return [event for event in self.ingestion() if event.name == name]

    def new_run(self) -> str:
        return self.manager.create(QUESTION).run_id


class SuccessfulIngestionTests(IngestionEventFixture):
    def test_a_full_ingestion_announces_every_stage_in_order(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        self.load(engine, run_id)

        self.assertEqual(
            self.names(),
            [
                VALIDATION_STARTED,
                VALIDATION_COMPLETED,
                FETCH_STARTED,
                FETCH_COMPLETED,
                INDEX_STARTED,
                INDEX_COMPLETED,
                ATTACH_STARTED,
                ATTACH_COMPLETED,
            ],
        )

    def test_each_transition_is_announced_exactly_once(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        self.load(engine, run_id)

        for name in (
            VALIDATION_COMPLETED,
            FETCH_COMPLETED,
            INDEX_COMPLETED,
            ATTACH_COMPLETED,
        ):
            with self.subTest(name=name):
                self.assertEqual(len(self.named(name)), 1)

    def test_one_attempt_shares_one_identifier(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        self.load(engine, run_id)

        identifiers = {event.payload["attempt_id"] for event in self.ingestion()}
        self.assertEqual(len(identifiers), 1)
        self.assertTrue(next(iter(identifiers)))

    def test_two_attempts_do_not_share_an_identifier(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()
        self.load(engine, run_id)
        first = self.ingestion()[0].payload["attempt_id"]
        self.events.clear()
        self.fetcher.source = source("second")

        self.load(engine, run_id, url="https://example.test/second")

        self.assertNotEqual(self.ingestion()[0].payload["attempt_id"], first)

    def test_the_attach_event_reports_the_canonical_count(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        self.load(engine, run_id)

        payload = self.named(ATTACH_COMPLETED)[0].payload
        self.assertEqual(payload["accepted_source_count"], 1)
        self.assertEqual(
            payload["accepted_source_count"],
            len(self.manager.get(run_id).sources),
        )

    def test_the_resource_identity_travels_with_the_events(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        self.load(engine, run_id)

        self.assertEqual(
            self.named(ATTACH_COMPLETED)[0].payload["resource_identity"],
            identity_of(URL),
        )

    def test_the_payload_is_machine_readable_only(self) -> None:
        """No prose, no translation, no exception text in the contract."""
        engine = self.build_engine()
        run_id = self.new_run()

        self.load(engine, run_id)

        for event in self.ingestion():
            with self.subTest(name=event.name):
                self.assertTrue(PAYLOAD_FIELDS <= set(event.payload))
                for value in event.payload.values():
                    self.assertIsInstance(value, str | bool | int)


class IndexOnlyStaysDistinctTests(IngestionEventFixture):
    def test_an_index_only_load_never_announces_attachment(self) -> None:
        engine = self.build_engine()

        self.load(engine, None)

        self.assertIn(INDEX_COMPLETED, self.names())
        self.assertEqual(self.named(ATTACH_STARTED), [])
        self.assertEqual(self.named(ATTACH_COMPLETED), [])

    def test_no_event_of_an_index_only_load_claims_attachment(self) -> None:
        """The invariant the whole pipeline exists to protect."""
        engine = self.build_engine()

        self.load(engine, None)

        for event in self.ingestion():
            with self.subTest(name=event.name):
                self.assertIs(event.payload["attached_to_run"], False)

    def test_only_the_attach_event_marks_attachment(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        self.load(engine, run_id)

        attached = [
            event.name for event in self.ingestion() if event.payload["attached_to_run"]
        ]
        self.assertEqual(attached, [ATTACH_COMPLETED])

    def test_the_index_event_reports_a_document_without_attachment(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        self.load(engine, run_id)

        payload = self.named(INDEX_COMPLETED)[0].payload
        self.assertTrue(payload["document_id"])
        self.assertIs(payload["created_local_document"], True)
        self.assertIs(payload["attached_to_run"], False)

    def test_an_index_only_load_reports_no_run(self) -> None:
        engine = self.build_engine()

        self.load(engine, None)

        self.assertEqual(self.named(INDEX_COMPLETED)[0].payload["run_id"], "")


class FailureAndCancellationTests(IngestionEventFixture):
    def test_a_refused_fetch_announces_one_failure_and_no_index(self) -> None:
        self.fetcher.source = None
        engine = self.build_engine()
        run_id = self.new_run()

        self.load(engine, run_id)

        self.assertEqual(len(self.named(INGESTION_FAILED)), 1)
        self.assertEqual(self.named(INDEX_COMPLETED), [])
        payload = self.named(INGESTION_FAILED)[0].payload
        self.assertEqual(payload["stage"], SourceLoadStage.FETCH_REFUSED.value)
        self.assertEqual(
            payload["failure_kind"],
            IngestionFailureKind.FETCH_REFUSED.value,
        )

    def test_a_refused_fetch_reports_the_recorded_safe_failure(self) -> None:
        """Reported because it happened, not to make the stream look complete."""
        self.fetcher.source = None
        engine = self.build_engine()
        run_id = self.new_run()

        self.load(engine, run_id)

        self.assertIs(
            self.named(INGESTION_FAILED)[0].payload["safe_failure_recorded"],
            True,
        )
        self.assertEqual(len(self.manager.get(run_id).failures), 1)

    def test_a_failure_without_a_run_records_no_safe_failure(self) -> None:
        self.fetcher.source = None
        engine = self.build_engine()

        self.load(engine, None)

        self.assertIs(
            self.named(INGESTION_FAILED)[0].payload["safe_failure_recorded"],
            False,
        )

    def test_an_attach_failure_announces_the_attempt_and_the_failure(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        with patch.object(
            ResearchRunManager,
            "add_source",
            side_effect=ResearchError("run refused the source"),
        ):
            self.load(engine, run_id)

        self.assertIn(ATTACH_STARTED, self.names())
        self.assertEqual(self.named(ATTACH_COMPLETED), [])
        payload = self.named(INGESTION_FAILED)[0].payload
        self.assertEqual(payload["stage"], SourceLoadStage.RUN_ATTACH_FAILED.value)
        self.assertEqual(
            payload["failure_kind"],
            IngestionFailureKind.ATTACH_REFUSED.value,
        )

    def test_an_attach_failure_leaves_the_run_unchanged(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        with patch.object(
            ResearchRunManager,
            "add_source",
            side_effect=ResearchError("run refused the source"),
        ):
            self.load(engine, run_id)

        self.assertEqual(self.manager.get(run_id).sources, ())

    def test_an_index_failure_announces_its_own_stage(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        with patch.object(
            KnowledgeEngine,
            "add_document",
            side_effect=KnowledgeError("index unavailable"),
        ):
            self.load(engine, run_id)

        self.assertIn(INDEX_STARTED, self.names())
        self.assertEqual(self.named(INDEX_COMPLETED), [])
        stages = {event.payload["stage"] for event in self.named(INGESTION_FAILED)}
        self.assertIn(SourceLoadStage.INDEX_FAILED.value, stages)

    def test_a_duplicate_document_fails_at_the_index_stage(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()
        self.load(engine, run_id)
        self.events.clear()

        self.load(engine, run_id)

        self.assertEqual(self.named(ATTACH_COMPLETED), [])
        self.assertEqual(len(self.manager.get(run_id).sources), 1)
        stages = {event.payload["stage"] for event in self.named(INGESTION_FAILED)}
        self.assertIn(SourceLoadStage.INDEX_FAILED.value, stages)

    def test_a_cancelled_load_announces_cancellation_not_failure(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()
        signal = CancellationSignal()
        signal.cancel()

        self.load(engine, run_id, cancellation_token=signal)

        self.assertEqual(len(self.named(INGESTION_CANCELLED)), 1)
        payload = self.named(INGESTION_CANCELLED)[0].payload
        self.assertEqual(payload["status"], IngestionStatus.CANCELLED.value)
        self.assertEqual(payload["stage"], SourceLoadStage.CANCELLED.value)
        self.assertIs(payload["attached_to_run"], False)

    def test_a_cancelled_load_indexes_nothing(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()
        signal = CancellationSignal()
        signal.cancel()

        self.load(engine, run_id, cancellation_token=signal)

        self.assertEqual(self.named(INDEX_COMPLETED), [])
        self.assertEqual(self.knowledge_engine.documents(), [])

    def test_a_retry_after_a_failed_attachment_announces_one_acceptance(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()
        with patch.object(
            ResearchRunManager,
            "add_source",
            side_effect=ResearchError("transient refusal"),
        ):
            self.load(engine, run_id)
        self.events.clear()

        self.load(engine, run_id)

        self.assertEqual(len(self.named(ATTACH_COMPLETED)), 1)
        self.assertEqual(len(self.manager.get(run_id).sources), 1)

    def test_a_started_event_never_asserts_an_outcome(self) -> None:
        self.assertFalse(IngestionStatus.STARTED.asserts_an_outcome)
        for status in (
            IngestionStatus.COMPLETED,
            IngestionStatus.FAILED,
            IngestionStatus.CANCELLED,
        ):
            with self.subTest(status=status):
                self.assertTrue(status.asserts_an_outcome)

    def test_a_missing_url_fails_validation_without_fetching(self) -> None:
        engine = self.build_engine()

        engine.process(
            BrainRequest(
                message="Load source",
                metadata={"intent": "research_source_load", "research_url": "  "},
            )
        )

        self.assertEqual(self.fetcher.calls, [])
        self.assertEqual(self.named(FETCH_STARTED), [])
        payload = self.named(INGESTION_FAILED)[0].payload
        self.assertEqual(
            payload["failure_kind"],
            IngestionFailureKind.VALIDATION_REFUSED.value,
        )


class NoBusIsSafeTests(IngestionEventFixture):
    def test_an_acceptance_service_without_a_bus_still_works(self) -> None:
        from cognition.ResearchSourceAcceptanceService import (
            ResearchSourceAcceptanceService,
        )

        service = ResearchSourceAcceptanceService(
            KnowledgeEngine(),
            self.manager,
        )
        run_id = self.new_run()

        result = service.accept(source(), run_id)

        self.assertIs(result.stage, SourceLoadStage.ACCEPTED_INTO_RUN)


if __name__ == "__main__":
    unittest.main()
