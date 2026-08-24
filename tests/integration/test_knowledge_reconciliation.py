"""Knowledge-only is a normal state, not a cleanup list.

Live testing kept producing the question "a document was created, so where did it
go?". The answer is usually complete and unalarming: it is indexed, and no
research run references it. Being able to say that is the point of this
subsystem.

The word choice is load-bearing. A document no run references is very often a
book, a note, or a page someone loaded deliberately to search locally, and
calling it an orphan invites deleting it. Orphan is reserved for the one case
that is genuinely broken: a run naming a document the index does not hold.

Everything here reads. There is no delete path to test because there is no
delete path, and these tests assert that the store and the index are unchanged
afterwards.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.KnowledgeReconciliationApplicationService import (
    KnowledgeReconciliationApplicationService,
)
from cognition.KnowledgeReconciliationEvents import RECONCILIATION_REPORTED
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.KnowledgeAttachment import KnowledgeAttachment
from research.KnowledgeAttachmentReconciler import KnowledgeAttachmentReconciler
from research.KnowledgeResourceRecord import KnowledgeResourceRecord
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.SourceIdentity import identity_of
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does web cache deception have a documented mitigation?"
FETCHED = datetime(2026, 8, 1, tzinfo=UTC)


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


def source(slug: str, body: str = "") -> ResearchSource:
    return ResearchSource(
        url=f"https://example.test/{slug}",
        title=f"Source {slug}",
        content=body or f"Body about {slug}, caches, and path suffixes.",
        content_type="text/html",
        fetched_at=FETCHED,
    )


class AttachmentVocabularyTests(unittest.TestCase):
    def test_only_attachment_means_research_uses_it(self) -> None:
        self.assertTrue(KnowledgeAttachment.ATTACHED.in_research)
        self.assertFalse(KnowledgeAttachment.KNOWLEDGE_ONLY.in_research)
        self.assertFalse(KnowledgeAttachment.BROKEN_REFERENCE.in_research)

    def test_knowledge_only_is_not_breakage(self) -> None:
        """The word choice that keeps someone from deleting a wanted book."""
        self.assertFalse(KnowledgeAttachment.KNOWLEDGE_ONLY.is_structural_breakage)
        self.assertFalse(KnowledgeAttachment.ATTACHED.is_structural_breakage)
        self.assertTrue(KnowledgeAttachment.BROKEN_REFERENCE.is_structural_breakage)

    def test_only_a_broken_reference_is_missing_from_the_index(self) -> None:
        self.assertTrue(KnowledgeAttachment.ATTACHED.indexed_locally)
        self.assertTrue(KnowledgeAttachment.KNOWLEDGE_ONLY.indexed_locally)
        self.assertFalse(KnowledgeAttachment.BROKEN_REFERENCE.indexed_locally)

    def test_a_record_cannot_contradict_its_classification(self) -> None:
        with self.assertRaises(ResearchError):
            KnowledgeResourceRecord(
                resource_identity="https://example.test/a",
                attachment=KnowledgeAttachment.ATTACHED,
                document_ids=("document-1",),
            )
        with self.assertRaises(ResearchError):
            KnowledgeResourceRecord(
                resource_identity="https://example.test/a",
                attachment=KnowledgeAttachment.KNOWLEDGE_ONLY,
                document_ids=("document-1",),
                run_ids=("run-1",),
            )
        with self.assertRaises(ResearchError):
            KnowledgeResourceRecord(
                resource_identity="https://example.test/a",
                attachment=KnowledgeAttachment.BROKEN_REFERENCE,
                document_ids=("document-1",),
                run_ids=("run-1",),
            )

    def test_an_indexed_record_must_name_a_document(self) -> None:
        with self.assertRaises(ResearchError):
            KnowledgeResourceRecord(
                resource_identity="https://example.test/a",
                attachment=KnowledgeAttachment.KNOWLEDGE_ONLY,
            )


class ReconciliationFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        self.manager.load()
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            InMemoryContentStore(),  # type: ignore[arg-type]
        )
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.reconciler = KnowledgeAttachmentReconciler()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def service(self) -> KnowledgeReconciliationApplicationService:
        return KnowledgeReconciliationApplicationService(
            self.knowledge_engine,
            ResponseComposer(),
            run_manager=self.manager,
            event_bus=self.event_bus,
        )

    def new_run(self) -> str:
        return self.manager.create(QUESTION).run_id

    def attach(self, run_id: str, slug: str, body: str = "") -> str:
        result = self.acceptance.accept(source(slug, body), run_id)
        assert result.document_id is not None
        return result.document_id

    def index_only(self, slug: str, body: str = "") -> str:
        result = self.acceptance.accept(source(slug, body), "")
        assert result.document_id is not None
        return result.document_id

    def report(self) -> object:
        return self.reconciler.reconcile(
            self.knowledge_engine.documents(),
            self.manager.list(),
        )

    def request(self, intent: str) -> BrainRequest:
        return BrainRequest(message="Reconcile", metadata={"intent": intent})


class ReconciliationTests(ReconciliationFixture):
    def test_an_empty_machine_reconciles_to_zero(self) -> None:
        report = self.report()

        self.assertEqual(report.indexed_resource_count, 0)
        self.assertEqual(report.attached, ())
        self.assertEqual(report.knowledge_only, ())
        self.assertTrue(report.healthy)

    def test_an_attached_source_is_classified_as_attached(self) -> None:
        run_id = self.new_run()
        self.attach(run_id, "attached")

        report = self.report()

        self.assertEqual(len(report.attached), 1)
        self.assertEqual(report.attached[0].run_ids, (run_id,))
        self.assertEqual(report.knowledge_only, ())

    def test_an_index_only_document_is_knowledge_only(self) -> None:
        """The live question: a document was created, so where did it go?"""
        self.index_only("local")

        report = self.report()

        self.assertEqual(len(report.knowledge_only), 1)
        self.assertEqual(report.knowledge_only[0].run_ids, ())
        self.assertEqual(report.attached, ())
        self.assertTrue(report.healthy)

    def test_both_kinds_are_counted_separately(self) -> None:
        run_id = self.new_run()
        self.attach(run_id, "attached")
        self.index_only("local")

        report = self.report()

        self.assertEqual(report.indexed_resource_count, 2)
        self.assertEqual(len(report.attached), 1)
        self.assertEqual(len(report.knowledge_only), 1)

    def test_a_duplicate_resource_is_one_entry_holding_two_documents(self) -> None:
        """Two records of one page is one resource, and the report says so."""
        run_id = self.new_run()
        self.attach(run_id, "page", "First body about shared cache keys.")
        second = self.acceptance.accept(
            ResearchSource(
                url="https://example.test/page/",
                title="Source page",
                content="Second body about shared cache keys and suffixes.",
                content_type="text/html",
                fetched_at=FETCHED,
            ),
            run_id,
        )
        self.assertTrue(second.attached_to_run)

        report = self.report()

        self.assertEqual(report.indexed_resource_count, 1)
        self.assertEqual(report.indexed_document_count, 2)
        self.assertEqual(len(report.attached), 1)
        self.assertTrue(report.attached[0].duplicated)

    def test_a_run_naming_a_missing_document_is_a_broken_reference(self) -> None:
        run_id = self.new_run()
        document_id = self.attach(run_id, "attached")
        self.knowledge_engine.remove_document(document_id)

        report = self.report()

        self.assertEqual(len(report.broken_references), 1)
        self.assertEqual(report.broken_references[0].run_ids, (run_id,))
        self.assertFalse(report.healthy)

    def test_a_broken_reference_is_not_counted_as_indexed(self) -> None:
        run_id = self.new_run()
        document_id = self.attach(run_id, "attached")
        self.knowledge_engine.remove_document(document_id)

        report = self.report()

        self.assertEqual(report.indexed_resource_count, 0)
        self.assertEqual(report.indexed_document_count, 0)

    def test_the_resource_identity_is_used_not_the_document_id(self) -> None:
        run_id = self.new_run()
        self.attach(run_id, "attached")

        report = self.report()

        self.assertEqual(
            report.attached[0].resource_identity,
            identity_of("https://example.test/attached"),
        )

    def test_a_resource_used_by_two_runs_names_both(self) -> None:
        first_run = self.new_run()
        document_id = self.attach(first_run, "shared")
        second_run = self.new_run()
        self.manager.add_source(second_run, source("shared"), document_id)

        report = self.report()

        self.assertEqual(len(report.attached), 1)
        self.assertEqual(set(report.attached[0].run_ids), {first_run, second_run})

    def test_reconciliation_reads_only(self) -> None:
        run_id = self.new_run()
        self.attach(run_id, "attached")
        self.index_only("local")
        runs_before = self.run_path.read_bytes()
        documents_before = len(self.knowledge_engine.documents())

        for _ in range(3):
            self.report()

        self.assertEqual(self.run_path.read_bytes(), runs_before)
        self.assertEqual(len(self.knowledge_engine.documents()), documents_before)

    def test_the_reconciler_exposes_no_removal_path(self) -> None:
        """The absence is the design, so it is asserted rather than assumed."""
        for forbidden in ("delete", "remove", "prune", "cleanup", "collect"):
            with self.subTest(method=forbidden):
                self.assertFalse(
                    any(
                        forbidden in name
                        for name in dir(KnowledgeAttachmentReconciler)
                        if not name.startswith("__")
                    )
                )

    def test_the_service_exposes_no_removal_path(self) -> None:
        for forbidden in ("delete", "remove", "prune", "cleanup", "collect"):
            with self.subTest(method=forbidden):
                self.assertFalse(
                    any(
                        forbidden in name
                        for name in dir(KnowledgeReconciliationApplicationService)
                        if not name.startswith("__")
                    )
                )


class ReconciliationPresentationTests(ReconciliationFixture):
    def test_the_report_names_every_count(self) -> None:
        run_id = self.new_run()
        self.attach(run_id, "attached")
        self.index_only("local")

        response = self.service().process_report(
            self.request("knowledge_reconciliation_report")
        )

        for line in (
            "Indexed resources: 2",
            "Attached to research: 1",
            "Knowledge-only: 1",
            "Broken references: 0",
        ):
            with self.subTest(line=line):
                self.assertIn(line, response.message)

    def test_the_report_says_knowledge_only_is_normal(self) -> None:
        self.index_only("local")

        response = self.service().process_report(
            self.request("knowledge_reconciliation_report")
        )

        self.assertIn("not a problem and not a cleanup list", response.message)
        self.assertIn("Nothing was deleted, merged, or repaired", response.message)

    def test_the_report_avoids_the_word_orphan_for_knowledge(self) -> None:
        self.index_only("local")

        response = self.service().process_report(
            self.request("knowledge_reconciliation_report")
        )

        self.assertNotIn("orphan", response.message.casefold())

    def test_broken_references_are_explained_when_present(self) -> None:
        run_id = self.new_run()
        document_id = self.attach(run_id, "attached")
        self.knowledge_engine.remove_document(document_id)

        response = self.service().process_report(
            self.request("knowledge_reconciliation_report")
        )

        self.assertIn("genuine breakage", response.message)

    def test_the_knowledge_only_list_can_be_inspected(self) -> None:
        self.index_only("local")

        response = self.service().process_knowledge_only(
            self.request("knowledge_only_list")
        )

        self.assertIn("Knowledge-only resources: 1", response.message)
        self.assertIn("Source local", response.message)
        self.assertIn("nothing here removes them", response.message)

    def test_an_empty_knowledge_only_list_says_so(self) -> None:
        run_id = self.new_run()
        self.attach(run_id, "attached")

        response = self.service().process_knowledge_only(
            self.request("knowledge_only_list")
        )

        self.assertIn("Every indexed resource is referenced", response.message)

    def test_the_event_reports_counts_and_two_zeroes(self) -> None:
        self.index_only("local")

        self.service().process_report(self.request("knowledge_reconciliation_report"))

        events = [
            event for event in self.events if event.name == RECONCILIATION_REPORTED
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["documents_removed"], 0)
        self.assertEqual(events[0].payload["references_repaired"], 0)
        self.assertEqual(events[0].payload["knowledge_only"], 1)

    def test_no_event_names_a_document_or_a_resource(self) -> None:
        self.index_only("local")

        self.service().process_report(self.request("knowledge_reconciliation_report"))

        payloads = str(
            [
                event.payload
                for event in self.events
                if event.name.startswith("knowledge_reconciliation")
            ]
        )
        self.assertNotIn("example.test", payloads)
        self.assertNotIn("Source local", payloads)


class ReconciliationCompositionTests(ReconciliationFixture):
    def build_engine(self, with_runs: bool = True) -> CognitiveEngine:
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
            research_run_manager=self.manager if with_runs else None,
        )

    def test_the_engine_routes_the_reconciliation_report(self) -> None:
        engine = self.build_engine()
        self.index_only("local")

        response = engine.process(self.request("knowledge_reconciliation_report"))

        self.assertTrue(response.success)
        assert response.knowledge_reconciliation is not None
        self.assertEqual(len(response.knowledge_reconciliation.knowledge_only), 1)

    def test_the_engine_routes_the_knowledge_only_list(self) -> None:
        engine = self.build_engine()
        self.index_only("local")

        response = engine.process(self.request("knowledge_only_list"))

        self.assertIn("Knowledge-only resources: 1", response.message)

    def test_reconciliation_works_without_research_persistence(self) -> None:
        """Everything indexed is knowledge-only when there are no runs at all."""
        engine = self.build_engine(with_runs=False)
        self.index_only("local")

        response = engine.process(self.request("knowledge_reconciliation_report"))

        assert response.knowledge_reconciliation is not None
        self.assertEqual(len(response.knowledge_reconciliation.knowledge_only), 1)
        self.assertTrue(response.knowledge_reconciliation.healthy)


if __name__ == "__main__":
    unittest.main()
