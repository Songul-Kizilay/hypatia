"""A local document existing is not a research run accepting a source.

This file exists because of a real live failure. A source was fetched and
indexed while no research run was bound to the request; the reply said "Research
source loaded" and printed a document ID; the run's canonical state correctly
showed zero accepted sources; and no safe failure was recorded, because nothing
had failed. Every part behaved. The report was still wrong, because one word was
covering two very different outcomes.

So these tests pin the distinction at every level: the stage vocabulary, the
acceptance transaction, the composed reply, and the desktop capture. They also
cover the partial transaction points — index succeeds, attach fails — and assert
the canonical run stays honest and nothing becomes citable from an unattached
source.

Level A is deterministic and needs no transport. Level B drives the real
acceptance service with controlled stores. Nothing here touches a network.
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
from brain.BrainResponse import BrainResponse
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import KnowledgeError, ResearchError
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from eventbus.EventBus import EventBus
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceAcceptanceResult import ResearchSourceAcceptanceResult
from research.SourceLoadStage import SourceLoadStage, summary_for
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does web cache deception have a documented mitigation?"
FETCHED = datetime(2026, 8, 1, tzinfo=UTC)
CONTENT = "Web cache deception arises when a cache stores a personalised page."


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []
        self.fail_on_save = False

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        if self.fail_on_save:
            raise ResearchError("content store unavailable")
        self.records = list(records)


class StubFetcher:
    """Return one prepared source, or refuse, without any network."""

    def __init__(self, source: ResearchSource | None = None) -> None:
        self.source = source
        self.calls: list[str] = []

    def fetch(self, url: str) -> ResearchSource:
        self.calls.append(url)
        if self.source is None:
            raise ResearchError("Research source could not be fetched.")
        return self.source


def source(slug: str = "a") -> ResearchSource:
    return ResearchSource(
        url=f"https://example.test/{slug}",
        title=f"Source {slug}",
        content=CONTENT,
        content_type="text/html",
        fetched_at=FETCHED,
    )


class StageVocabularyTests(unittest.TestCase):
    """Level A: the stage names mean exactly one thing each."""

    def test_only_one_stage_means_the_run_accepted_the_source(self) -> None:
        attached = [stage for stage in SourceLoadStage if stage.attached_to_run]

        self.assertEqual(attached, [SourceLoadStage.ACCEPTED_INTO_RUN])

    def test_indexing_without_a_run_is_not_attachment(self) -> None:
        stage = SourceLoadStage.INDEXED_WITHOUT_RUN

        self.assertTrue(stage.created_local_document)
        self.assertFalse(stage.attached_to_run)
        self.assertTrue(stage.partial)
        self.assertFalse(stage.failed)

    def test_a_partial_stage_is_neither_success_nor_failure(self) -> None:
        self.assertTrue(SourceLoadStage.INDEXED_WITHOUT_RUN.partial)
        self.assertFalse(SourceLoadStage.ACCEPTED_INTO_RUN.partial)
        self.assertFalse(SourceLoadStage.FETCH_REFUSED.partial)

    def test_a_refused_fetch_created_nothing(self) -> None:
        stage = SourceLoadStage.FETCH_REFUSED

        self.assertFalse(stage.created_local_document)
        self.assertFalse(stage.rolled_back)
        self.assertTrue(stage.failed)

    def test_rolled_back_stages_are_the_ones_that_undid_local_work(self) -> None:
        rolled = [stage for stage in SourceLoadStage if stage.rolled_back]

        self.assertEqual(
            rolled,
            [
                SourceLoadStage.CONTENT_PERSIST_FAILED,
                SourceLoadStage.RUN_ATTACH_FAILED,
            ],
        )

    def test_every_stage_declares_a_summary(self) -> None:
        for stage in SourceLoadStage:
            with self.subTest(stage=stage):
                self.assertTrue(summary_for(stage).strip())

    def test_an_undescribed_stage_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            summary_for("invented_stage")  # type: ignore[arg-type]

    def test_the_partial_summary_says_no_evidence_may_be_recorded(self) -> None:
        summary = SourceLoadStage.INDEXED_WITHOUT_RUN.summary

        self.assertIn("no research run accepted it", summary)
        self.assertIn("no evidence can be recorded from it", summary)

    def test_the_accepted_summary_still_denies_being_evidence(self) -> None:
        self.assertIn(
            "Acceptance is not evidence", SourceLoadStage.ACCEPTED_INTO_RUN.summary
        )


class AcceptanceResultConsistencyTests(unittest.TestCase):
    """Level A: a result cannot describe a stage it does not match."""

    def test_claiming_run_acceptance_without_a_run_is_refused(self) -> None:
        with self.assertRaises(ResearchError) as raised:
            ResearchSourceAcceptanceResult(
                accepted=True,
                transaction_attempted=True,
                document_id="document-1",
                run=None,
                stage=SourceLoadStage.ACCEPTED_INTO_RUN,
            )

        self.assertIn("without one", str(raised.exception))

    def test_an_indexed_stage_must_name_its_document(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSourceAcceptanceResult(
                accepted=True,
                transaction_attempted=True,
                document_id=None,
                stage=SourceLoadStage.INDEXED_WITHOUT_RUN,
            )

    def test_a_knowledge_only_result_is_not_attached(self) -> None:
        result = ResearchSourceAcceptanceResult(
            accepted=True,
            transaction_attempted=True,
            document_id="document-1",
            stage=SourceLoadStage.INDEXED_WITHOUT_RUN,
        )

        self.assertTrue(result.accepted)
        self.assertFalse(result.attached_to_run)
        self.assertTrue(result.partial)

    def test_a_rolled_back_stage_needs_no_document(self) -> None:
        result = ResearchSourceAcceptanceResult(
            accepted=False,
            transaction_attempted=True,
            failure_reason="attach failed",
            stage=SourceLoadStage.RUN_ATTACH_FAILED,
        )

        self.assertFalse(result.attached_to_run)


class AcceptanceTransactionTests(unittest.TestCase):
    """Level B: drive the real transaction through every partial point."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        self.manager.load()
        self.content_store = InMemoryContentStore()
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            self.content_store,  # type: ignore[arg-type]
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def new_run(self) -> str:
        return self.manager.create(QUESTION).run_id

    def test_no_run_bound_indexes_without_attaching(self) -> None:
        """The exact live case: a real document, no accepted source."""
        result = self.acceptance.accept(source(), "")

        self.assertIs(result.stage, SourceLoadStage.INDEXED_WITHOUT_RUN)
        self.assertTrue(result.accepted)
        self.assertFalse(result.attached_to_run)
        self.assertIsNotNone(result.document_id)
        self.assertEqual(self.manager.list(), [])

    def test_a_bound_run_reaches_acceptance(self) -> None:
        run_id = self.new_run()

        result = self.acceptance.accept(source(), run_id)

        self.assertIs(result.stage, SourceLoadStage.ACCEPTED_INTO_RUN)
        self.assertTrue(result.attached_to_run)
        assert result.run is not None
        self.assertEqual(len(result.run.sources), 1)
        self.assertEqual(len(self.manager.get(run_id).sources), 1)

    def test_index_succeeds_and_attachment_fails_leaves_the_run_honest(self) -> None:
        """Level B's required case: fetch ok, index ok, acceptance refused."""
        run_id = self.new_run()
        self.acceptance.accept(source("a"), run_id)
        documents_before = len(self.knowledge_engine.documents())

        with patch.object(
            ResearchRunManager,
            "add_source",
            side_effect=ResearchError("run refused the source"),
        ):
            result = self.acceptance.accept(source("b"), run_id)

        self.assertIs(result.stage, SourceLoadStage.RUN_ATTACH_FAILED)
        self.assertFalse(result.accepted)
        self.assertFalse(result.attached_to_run)
        self.assertTrue(result.failure_reason)
        self.assertEqual(len(self.manager.get(run_id).sources), 1)
        self.assertEqual(len(self.knowledge_engine.documents()), documents_before)

    def test_a_failed_attachment_rolls_back_the_local_document(self) -> None:
        run_id = self.new_run()

        with patch.object(
            ResearchRunManager,
            "add_source",
            side_effect=ResearchError("run refused the source"),
        ):
            self.acceptance.accept(source(), run_id)

        self.assertEqual(self.knowledge_engine.documents(), [])
        self.assertEqual(self.content_store.records, [])

    def test_a_content_persistence_failure_names_its_stage(self) -> None:
        run_id = self.new_run()
        self.content_store.fail_on_save = True

        result = self.acceptance.accept(source(), run_id)

        self.assertIs(result.stage, SourceLoadStage.CONTENT_PERSIST_FAILED)
        self.assertFalse(result.attached_to_run)
        self.assertEqual(self.manager.get(run_id).sources, ())

    def test_no_evidence_can_be_recorded_from_an_unattached_source(self) -> None:
        run_id = self.new_run()
        result = self.acceptance.accept(source(), "")
        assert result.document_id is not None
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == result.document_id
        )

        with self.assertRaises(ResearchError):
            self.manager.add_evidence(run_id, chunk, "Directly relevant.")

    def test_the_same_document_twice_is_refused_before_the_run(self) -> None:
        """Knowledge indexing already refuses it, so attachment is never reached."""
        run_id = self.new_run()
        self.acceptance.accept(source(), run_id)

        with self.assertRaises(KnowledgeError):
            self.acceptance.accept(source(), run_id)

        self.assertEqual(len(self.manager.get(run_id).sources), 1)

    def test_a_retry_after_a_failed_attachment_can_still_succeed(self) -> None:
        run_id = self.new_run()
        with patch.object(
            ResearchRunManager,
            "add_source",
            side_effect=ResearchError("transient refusal"),
        ):
            first = self.acceptance.accept(source(), run_id)

        second = self.acceptance.accept(source(), run_id)

        self.assertIs(first.stage, SourceLoadStage.RUN_ATTACH_FAILED)
        self.assertIs(second.stage, SourceLoadStage.ACCEPTED_INTO_RUN)
        self.assertEqual(len(self.manager.get(run_id).sources), 1)


class SourceLoadReportingTests(unittest.TestCase):
    """Level B: the reply must not describe an index as an accepted source."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        self.manager.load()
        self.fetcher = StubFetcher(source())

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def build_engine(self) -> CognitiveEngine:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        session_manager = SessionManager(event_bus)
        return CognitiveEngine(
            self.knowledge_engine,
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
            research_source_fetcher=self.fetcher,  # type: ignore[arg-type]
            research_run_manager=self.manager,
        )

    def load(
        self,
        engine: CognitiveEngine,
        run_id: str | None,
        url: str = "https://example.test/a",
    ) -> object:
        metadata: dict[str, object] = {
            "intent": "research_source_load",
            "research_url": url,
        }
        if run_id is not None:
            metadata["research_run_id"] = run_id
        return engine.process(BrainRequest(message="Load source", metadata=metadata))

    def test_a_load_without_a_run_does_not_claim_acceptance(self) -> None:
        engine = self.build_engine()

        response = self.load(engine, None)

        self.assertIs(response.source_load_stage, SourceLoadStage.INDEXED_WITHOUT_RUN)
        self.assertIn("NOT accepted into a research run", response.message)
        self.assertNotIn("Research source accepted", response.message)
        self.assertEqual(self.manager.list(), [])

    def test_a_load_without_a_run_labels_the_id_as_local(self) -> None:
        """The live report printed a bare "ID:" that read as an accepted source."""
        engine = self.build_engine()

        response = self.load(engine, None)

        self.assertIn("Local document ID:", response.message)
        self.assertNotIn("Research run:", response.message)

    def test_a_load_into_a_run_reports_acceptance_and_the_count(self) -> None:
        engine = self.build_engine()
        run_id = self.manager.create(QUESTION).run_id

        response = self.load(engine, run_id)

        self.assertIs(response.source_load_stage, SourceLoadStage.ACCEPTED_INTO_RUN)
        self.assertIn("Research source accepted into the run:", response.message)
        self.assertIn("Accepted sources in this run: 1", response.message)
        self.assertEqual(len(self.manager.get(run_id).sources), 1)

    def test_every_successful_reply_states_the_stage_reached(self) -> None:
        engine = self.build_engine()
        run_id = self.manager.create(QUESTION).run_id

        without = self.load(engine, None)
        self.fetcher.source = source("b")
        with_run = self.load(engine, run_id, url="https://example.test/b")

        self.assertIn("Stage reached: indexed_without_run", without.message)
        self.assertIn("Stage reached: accepted_into_run", with_run.message)

    def test_a_refused_fetch_reports_failure_and_records_it(self) -> None:
        self.fetcher.source = None
        engine = self.build_engine()
        run_id = self.manager.create(QUESTION).run_id

        response = self.load(engine, run_id)

        self.assertFalse(response.success)
        self.assertIsNone(response.source_load_stage)
        self.assertEqual(len(self.manager.get(run_id).failures), 1)

    def test_an_attachment_failure_is_reported_as_a_failure(self) -> None:
        engine = self.build_engine()
        run_id = self.manager.create(QUESTION).run_id

        with patch.object(
            ResearchRunManager,
            "add_source",
            side_effect=ResearchError("run refused the source"),
        ):
            response = self.load(engine, run_id)

        self.assertFalse(response.success)
        self.assertEqual(self.manager.get(run_id).sources, ())

    def test_an_indexing_failure_is_reported_as_a_failure(self) -> None:
        engine = self.build_engine()
        run_id = self.manager.create(QUESTION).run_id

        with patch.object(
            KnowledgeEngine,
            "add_document",
            side_effect=KnowledgeError("index unavailable"),
        ):
            response = self.load(engine, run_id)

        self.assertFalse(response.success)
        self.assertEqual(self.manager.get(run_id).sources, ())
        self.assertEqual(len(self.manager.get(run_id).failures), 1)


class DesktopCaptureTests(unittest.TestCase):
    """The desktop must not select a source the run never accepted."""

    class _Field:
        def __init__(self) -> None:
            self.value = ""

        def set(self, value: str) -> None:
            self.value = value

    class _Window:
        """Only what the capture method touches, so no Tk root is needed."""

        def __init__(self) -> None:
            self._research_source_document_id = DesktopCaptureTests._Field()

    def capture(self, response: BrainResponse) -> str:
        window = self._Window()
        TkinterDesktopWindow._capture_accepted_research_source(window, response)
        return window._research_source_document_id.value

    def document(self) -> KnowledgeDocumentReference:
        engine = KnowledgeEngine()
        service = ResearchSourceAcceptanceService(engine)
        result = service.accept(source(), "")
        assert result.document_id is not None
        return next(
            reference
            for reference in engine.documents()
            if reference.document_id == result.document_id
        )

    def test_an_indexed_only_load_selects_nothing(self) -> None:
        document = self.document()
        response = ResponseComposer().research_source_load_success(
            BrainRequest(message="Load source"),
            document,
            run=None,
            stage=SourceLoadStage.INDEXED_WITHOUT_RUN,
        )

        self.assertEqual(self.capture(response), "")

    def test_an_accepted_load_selects_the_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = ResearchRunManager(
                JsonFileResearchRunStore(Path(directory) / "runs.json")
            )
            manager.load()
            engine = KnowledgeEngine()
            service = ResearchSourceAcceptanceService(engine, manager)
            run_id = manager.create(QUESTION).run_id
            result = service.accept(source(), run_id)
            assert result.document_id is not None
            document = next(
                reference
                for reference in engine.documents()
                if reference.document_id == result.document_id
            )
            response = ResponseComposer().research_source_load_success(
                BrainRequest(message="Load source"),
                document,
                run=result.run,
                stage=result.stage,
            )

            self.assertEqual(self.capture(response), result.document_id)


if __name__ == "__main__":
    unittest.main()
