"""Integration tests for Bootstrap dependency wiring."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.Brain import Brain
from brain.BrainRequest import BrainRequest
from core.Bootstrap import Bootstrap
from core.Exceptions import MemoryError, ResearchError, SessionError
from eventbus.EventBus import EventBus
from knowledge.JsonFileKnowledgeRelationStore import JsonFileKnowledgeRelationStore
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.JsonFileMemoryStore import JsonFileMemoryStore
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.JsonFileResearchSourceContentStore import (
    JsonFileResearchSourceContentStore,
)
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceContentRecord import ResearchSourceContentRecord
from research.ResearchSourceContentRestorationStatus import (
    ResearchSourceContentRestorationStatus,
)
from research.ResearchSourceContentRestorer import ResearchSourceContentRestorer
from response.ResponseComposer import ResponseComposer
from session.JsonFileSessionStore import JsonFileSessionStore
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class RecordingResearchSourceFetcher:
    def __init__(self, source: ResearchSource) -> None:
        self.source = source
        self.calls: list[str] = []

    def fetch(self, url: str) -> ResearchSource:
        self.calls.append(url)
        return self.source


class RecordingResearchSourceDiscoveryProvider:
    provider_name = "bootstrap-test-provider"

    def __init__(self, candidate: ResearchSourceCandidate) -> None:
        self.candidate = candidate
        self.calls: list[tuple[str, int]] = []

    def discover(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[ResearchSourceCandidate]:
        self.calls.append((query, limit))
        return [self.candidate]


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.memory_path = Path(self.temporary_directory.name) / "memory.json"
        self.session_path = Path(self.temporary_directory.name) / "sessions.json"
        self.knowledge_relation_path = (
            Path(self.temporary_directory.name) / "knowledge_relations.json"
        )
        self.research_run_path = (
            Path(self.temporary_directory.name) / "research_runs.json"
        )
        self.research_source_content_path = (
            Path(self.temporary_directory.name) / "research_content.json"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _bootstrap(self) -> Bootstrap:
        return Bootstrap(
            memory_path=self.memory_path,
            session_path=self.session_path,
            knowledge_relation_path=self.knowledge_relation_path,
            research_run_path=self.research_run_path,
            research_source_content_path=self.research_source_content_path,
        )

    def test_bootstrap_registers_response_composer(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()

        response_composer = bootstrap.container.resolve(ResponseComposer)

        self.assertIsInstance(response_composer, ResponseComposer)

    def test_bootstrap_wires_an_injected_research_source_fetcher_to_brain(self) -> None:
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="Evidence paragraph.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        fetcher = RecordingResearchSourceFetcher(source)
        bootstrap = Bootstrap(
            memory_path=self.memory_path,
            session_path=self.session_path,
            knowledge_relation_path=self.knowledge_relation_path,
            research_source_fetcher=fetcher,
        )
        bootstrap.initialize()

        response = bootstrap.container.resolve(Brain).process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": source.url,
                },
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(fetcher.calls, [source.url])
        self.assertEqual(response.knowledge_documents[0].source, source.url)

    def test_discovered_candidates_survive_a_bootstrap_restart(self) -> None:
        candidate = ResearchSourceCandidate(
            url="https://example.com/candidate",
            title="Candidate source",
            snippet="Potentially relevant.",
        )
        provider = RecordingResearchSourceDiscoveryProvider(candidate)
        first = Bootstrap(
            memory_path=self.memory_path,
            session_path=self.session_path,
            knowledge_relation_path=self.knowledge_relation_path,
            research_run_path=self.research_run_path,
            research_source_discovery_provider=provider,
        )
        first.initialize()
        brain = first.container.resolve(Brain)
        run = brain.process(
            BrainRequest(
                message="Create internet research run",
                metadata={
                    "intent": "research_run_create",
                    "research_question": "What sources should Hypatia compare?",
                },
            )
        ).research_runs[0]

        discovered = brain.process(
            BrainRequest(
                message="Discover candidate research sources",
                metadata={
                    "intent": "research_source_discover",
                    "research_run_id": run.run_id,
                },
            )
        )

        restarted = self._bootstrap()
        restarted.initialize()
        listed = restarted.container.resolve(Brain).process(
            BrainRequest(
                message="List internet research runs",
                metadata={"intent": "research_run_list"},
            )
        )

        self.assertTrue(discovered.success)
        self.assertEqual(provider.calls, [(run.question, 5)])
        self.assertEqual(discovered.research_runs[0].sources, ())
        self.assertEqual(len(discovered.research_runs[0].discoveries), 1)
        self.assertEqual(listed.research_runs, discovered.research_runs)
        self.assertEqual(
            listed.research_runs[0].discoveries[0].candidates,
            (candidate,),
        )

    def test_bootstrap_wires_cognitive_search_to_shared_memory_manager(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            document_path = Path(temporary_directory) / "knowledge.md"
            document_path.write_text("Hypatia", encoding="utf-8")

            bootstrap = self._bootstrap()
            bootstrap.initialize()
            container = bootstrap.container
            knowledge_engine = container.resolve(KnowledgeEngine)
            memory_manager = container.resolve(MemoryManager)
            brain = container.resolve(Brain)
            knowledge_engine.load(document_path)

            response = brain.process("search hypatia")

        self.assertTrue(response.success)
        self.assertEqual(len(memory_manager.all()), 1)
        self.assertEqual(
            memory_manager.all()[0].content,
            "User: search hypatia\nHypatia: I found 1 matching knowledge chunks.",
        )

    def test_bootstrap_wires_brain_to_the_planner(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()
        brain = bootstrap.container.resolve(Brain)

        response = brain.process("plan learn SQL injection")

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "plan")
        self.assertIn("Plan created for: learn SQL injection", response.message)
        self.assertIn("1. Clarify goal", response.message)

    def test_bootstrap_processes_greeting_through_cognition(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()
        brain = bootstrap.container.resolve(Brain)

        response = brain.process("hello")

        self.assertEqual(response.intent, "greeting")
        self.assertEqual(response.message, "Hello! I am Hypatia.")

    def test_bootstrap_processes_message_through_cognition(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()
        brain = bootstrap.container.resolve(Brain)

        response = brain.process("how are you")

        self.assertEqual(response.intent, "message")
        self.assertEqual(response.message, "I received your message: how are you")

    def test_bootstrap_registers_json_file_memory_store_with_default_path(self) -> None:
        bootstrap = Bootstrap()
        bootstrap.initialize()

        memory_store = bootstrap.container.resolve(JsonFileMemoryStore)
        session_store = bootstrap.container.resolve(JsonFileSessionStore)
        relation_store = bootstrap.container.resolve(JsonFileKnowledgeRelationStore)
        research_run_store = bootstrap.container.resolve(JsonFileResearchRunStore)
        research_source_content_store = bootstrap.container.resolve(
            JsonFileResearchSourceContentStore
        )
        project_root = Path(__file__).resolve().parents[1]

        self.assertEqual(
            memory_store._path,
            project_root / "data" / "memory" / "memory.json",
        )
        self.assertEqual(
            session_store._path,
            project_root / "data" / "sessions" / "sessions.json",
        )
        self.assertEqual(
            relation_store._path,
            project_root / "data" / "knowledge" / "relations.json",
        )
        self.assertEqual(
            research_run_store._path,
            project_root / "data" / "research" / "runs.json",
        )
        self.assertEqual(
            research_source_content_store._path,
            project_root / "data" / "research" / "content.json",
        )

    def test_bootstrap_registers_the_selected_knowledge_relation_store(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()

        relation_store = bootstrap.container.resolve(JsonFileKnowledgeRelationStore)

        self.assertEqual(relation_store._path, self.knowledge_relation_path)

    def test_bootstrap_registers_the_selected_research_run_store(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()

        store = bootstrap.container.resolve(JsonFileResearchRunStore)
        manager = bootstrap.container.resolve(ResearchRunManager)

        self.assertEqual(store._path, self.research_run_path)
        self.assertEqual(manager.list(), [])

    def test_bootstrap_registers_the_selected_research_source_content_store(
        self,
    ) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()

        store = bootstrap.container.resolve(JsonFileResearchSourceContentStore)
        restorer = bootstrap.container.resolve(ResearchSourceContentRestorer)
        status = bootstrap.container.resolve(ResearchSourceContentRestorationStatus)

        self.assertEqual(store._path, self.research_source_content_path)
        self.assertEqual(store.load(), [])
        self.assertIsInstance(restorer, ResearchSourceContentRestorer)
        self.assertTrue(status.available)
        self.assertEqual(status.restored_document_count, 0)
        self.assertEqual(status.restored_paragraph_count, 0)

    def test_bootstrap_rejects_orphaned_research_content(self) -> None:
        source = ResearchSource(
            url="https://example.com/orphan",
            title="Orphan source",
            content="Unattached persisted finding.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        record = ResearchSourceContentRecord.from_source(
            source,
            source.to_document().document_id,
            datetime(2026, 8, 20, 12, 31, tzinfo=UTC),
        )
        store = JsonFileResearchSourceContentStore(self.research_source_content_path)
        store.save([record])

        with self.assertRaisesRegex(ResearchError, "no accepted provenance"):
            self._bootstrap().initialize()

        self.assertEqual(store.load(), [record])

    def test_research_runs_survive_a_bootstrap_restart(self) -> None:
        first = self._bootstrap()
        first.initialize()
        created = first.container.resolve(Brain).process(
            BrainRequest(
                message="Create internet research run",
                metadata={
                    "intent": "research_run_create",
                    "research_question": "What should Hypatia compare?",
                },
            )
        )

        restarted = self._bootstrap()
        restarted.initialize()
        listed = restarted.container.resolve(Brain).process(
            BrainRequest(
                message="List internet research runs",
                metadata={"intent": "research_run_list"},
            )
        )

        self.assertTrue(created.success)
        self.assertTrue(listed.success)
        self.assertEqual(listed.research_runs, created.research_runs)

    def test_accepted_research_content_is_saved_and_restored_at_startup(
        self,
    ) -> None:
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="Exact accepted finding.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        first = Bootstrap(
            memory_path=self.memory_path,
            session_path=self.session_path,
            knowledge_relation_path=self.knowledge_relation_path,
            research_run_path=self.research_run_path,
            research_source_content_path=self.research_source_content_path,
            research_source_fetcher=RecordingResearchSourceFetcher(source),
        )
        first.initialize()
        brain = first.container.resolve(Brain)
        run = brain.process(
            BrainRequest(
                message="Create internet research run",
                metadata={
                    "intent": "research_run_create",
                    "research_question": "What should Hypatia compare?",
                },
            )
        ).research_runs[0]

        accepted = brain.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": source.url,
                    "research_run_id": run.run_id,
                },
            )
        )
        records = first.container.resolve(JsonFileResearchSourceContentStore).load()

        restarted = self._bootstrap()
        restarted.initialize()

        self.assertTrue(accepted.success)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].content, source.content)
        self.assertEqual(
            records[0].document_id,
            accepted.knowledge_documents[0].document_id,
        )
        self.assertEqual(
            restarted.container.resolve(JsonFileResearchSourceContentStore).load(),
            records,
        )
        restored_knowledge = restarted.container.resolve(KnowledgeEngine)
        restoration_status = restarted.container.resolve(
            ResearchSourceContentRestorationStatus
        )
        self.assertEqual(
            [document.document_id for document in restored_knowledge.documents()],
            [records[0].document_id],
        )
        self.assertEqual(
            restored_knowledge.search("accepted")[0].document_id,
            records[0].document_id,
        )
        self.assertTrue(restoration_status.available)
        self.assertEqual(restoration_status.restored_document_count, 1)
        self.assertEqual(restoration_status.restored_paragraph_count, 1)

    def test_research_evidence_survives_a_bootstrap_restart(self) -> None:
        source = ResearchSource(
            url="https://example.com/research",
            title="Example research",
            content="First finding.\n\nSecond finding.",
            content_type="text/plain",
            fetched_at=datetime(2026, 8, 20, 12, 30, tzinfo=UTC),
        )
        first = Bootstrap(
            memory_path=self.memory_path,
            session_path=self.session_path,
            knowledge_relation_path=self.knowledge_relation_path,
            research_run_path=self.research_run_path,
            research_source_fetcher=RecordingResearchSourceFetcher(source),
        )
        first.initialize()
        brain = first.container.resolve(Brain)
        run = brain.process(
            BrainRequest(
                message="Create internet research run",
                metadata={
                    "intent": "research_run_create",
                    "research_question": "What should Hypatia compare?",
                },
            )
        ).research_runs[0]
        loaded = brain.process(
            BrainRequest(
                message="Load selected internet research source",
                metadata={
                    "intent": "research_source_load",
                    "research_url": source.url,
                    "research_run_id": run.run_id,
                },
            )
        )
        chunk = first.container.resolve(KnowledgeEngine).search("second")[0]

        recorded = brain.process(
            BrainRequest(
                message="Record selected research evidence",
                metadata={
                    "intent": "research_evidence_record",
                    "research_run_id": run.run_id,
                    "research_chunk_id": chunk.chunk_id,
                    "research_evidence_note": "Supports the comparison.",
                },
            )
        )
        document_id = loaded.knowledge_documents[0].document_id
        evidence_id = recorded.research_runs[0].evidence[0].evidence_id
        assessment_preview = brain.process(
            BrainRequest(
                message="Preview user-authored assessment",
                metadata={
                    "intent": "research_source_assessment_write_preview",
                    "research_run_id": run.run_id,
                    "research_source_document_id": document_id,
                    "research_assessment_evidence_ids": [evidence_id],
                    "research_assessment_text": "The source supports the comparison.",
                },
            )
        )
        assessment_recorded = brain.process(
            BrainRequest(
                message="Record user-authored assessment",
                metadata={
                    "intent": "research_source_assessment_record",
                    "research_run_id": run.run_id,
                    "research_source_document_id": document_id,
                    "research_assessment_evidence_ids": [evidence_id],
                    "research_assessment_text": "The source supports the comparison.",
                },
            )
        )
        original_assessment_id = (
            assessment_recorded.research_runs[0].assessments[0].assessment_id
        )
        correction_preview = brain.process(
            BrainRequest(
                message="Preview corrected user-authored assessment",
                metadata={
                    "intent": "research_source_assessment_write_preview",
                    "research_run_id": run.run_id,
                    "research_source_document_id": document_id,
                    "research_assessment_evidence_ids": [evidence_id],
                    "research_assessment_text": (
                        "The source supports only the narrower comparison."
                    ),
                    "research_assessment_supersedes_id": original_assessment_id,
                },
            )
        )
        correction_recorded = brain.process(
            BrainRequest(
                message="Record corrected user-authored assessment",
                metadata={
                    "intent": "research_source_assessment_record",
                    "research_run_id": run.run_id,
                    "research_source_document_id": document_id,
                    "research_assessment_evidence_ids": [evidence_id],
                    "research_assessment_text": (
                        "The source supports only the narrower comparison."
                    ),
                    "research_assessment_supersedes_id": original_assessment_id,
                },
            )
        )
        closed = brain.process(
            BrainRequest(
                message="Update selected research status",
                metadata={
                    "intent": "research_run_status_update",
                    "research_run_id": run.run_id,
                    "research_target_status": "completed",
                },
            )
        )

        restarted = self._bootstrap()
        restarted.initialize()
        listed = restarted.container.resolve(Brain).process(
            BrainRequest(
                message="List internet research runs",
                metadata={"intent": "research_run_list"},
            )
        )
        evidence_listed = restarted.container.resolve(Brain).process(
            BrainRequest(
                message="List selected research evidence",
                metadata={
                    "intent": "research_evidence_list",
                    "research_run_id": run.run_id,
                },
            )
        )
        assessment_listed = restarted.container.resolve(Brain).process(
            BrainRequest(
                message="Preview accepted research source assessment",
                metadata={
                    "intent": "research_source_assessment_preview",
                    "research_run_id": run.run_id,
                    "research_source_document_id": document_id,
                },
            )
        )

        self.assertTrue(recorded.success)
        self.assertTrue(assessment_preview.success)
        self.assertTrue(assessment_recorded.success)
        self.assertTrue(correction_preview.success)
        self.assertTrue(correction_recorded.success)
        self.assertTrue(closed.success)
        self.assertEqual(closed.research_runs[0].status.value, "completed")
        self.assertEqual(len(recorded.research_runs[0].evidence), 1)
        self.assertEqual(listed.research_runs, closed.research_runs)
        self.assertTrue(evidence_listed.success)
        self.assertEqual(evidence_listed.research_runs, closed.research_runs)
        self.assertIn("Second finding.", evidence_listed.message)
        self.assertEqual(len(correction_recorded.research_runs[0].assessments), 2)
        self.assertTrue(assessment_listed.success)
        self.assertIsNotNone(assessment_listed.research_source_assessment_preview)
        assert assessment_listed.research_source_assessment_preview is not None
        self.assertEqual(
            len(assessment_listed.research_source_assessment_preview.assessments),
            2,
        )
        self.assertIn("supports the comparison", assessment_listed.message)
        self.assertIn(
            f"supersedes: {original_assessment_id}",
            assessment_listed.message,
        )
        self.assertIn("state: superseded", assessment_listed.message)

    def test_missing_session_file_creates_and_persists_the_default_registry(
        self,
    ) -> None:
        bootstrap = self._bootstrap()

        bootstrap.initialize()

        session_manager = bootstrap.container.resolve(SessionManager)
        document = json.loads(self.session_path.read_text(encoding="utf-8"))
        self.assertEqual(session_manager.get_active().session_id, "default")
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["active_session_id"], "default")
        self.assertEqual(document["sessions"][0]["session_id"], "default")

    def test_bootstrap_loads_existing_memory_for_explicit_recall(self) -> None:
        record = MemoryRecord(
            memory_id="conversation-1",
            content="User: I like cats\nHypatia: Noted.",
            tags=frozenset({"brain", "conversation"}),
        )
        JsonFileMemoryStore(self.memory_path).save([record])
        bootstrap = self._bootstrap()

        bootstrap.initialize()
        memory_manager = bootstrap.container.resolve(MemoryManager)
        brain = bootstrap.container.resolve(Brain)
        response = brain.process("recall cats")

        self.assertEqual(memory_manager.all(), [record])
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 1)
        self.assertIn(record.content, response.message)

    def test_missing_memory_file_starts_with_empty_memory(self) -> None:
        bootstrap = self._bootstrap()

        bootstrap.initialize()

        memory_manager = bootstrap.container.resolve(MemoryManager)
        self.assertEqual(memory_manager.all(), [])

    def test_corrupt_memory_file_stops_bootstrap_without_a_container(self) -> None:
        self.memory_path.write_text("{invalid", encoding="utf-8")
        bootstrap = self._bootstrap()

        with self.assertRaises(MemoryError):
            bootstrap.initialize()

        self.assertFalse(hasattr(bootstrap, "container"))

    def test_corrupt_session_file_stops_before_memory_load_and_container_publish(
        self,
    ) -> None:
        self.session_path.write_text("{invalid", encoding="utf-8")
        self.memory_path.write_text("{invalid", encoding="utf-8")
        bootstrap = self._bootstrap()

        with self.assertRaises(SessionError):
            bootstrap.initialize()

        self.assertFalse(hasattr(bootstrap, "container"))

    def test_session_registry_and_memory_remain_independent_schema_documents(
        self,
    ) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()
        brain = bootstrap.container.resolve(Brain)
        brain.process("create session work-1")
        brain.process("use session work-1")
        brain.process("I like cats")

        session_document = json.loads(self.session_path.read_text(encoding="utf-8"))
        memory_document = json.loads(self.memory_path.read_text(encoding="utf-8"))

        self.assertEqual(session_document["schema_version"], 1)
        self.assertEqual(
            set(session_document), {"schema_version", "active_session_id", "sessions"}
        )
        self.assertEqual(memory_document["schema_version"], 1)
        self.assertEqual(set(memory_document), {"schema_version", "records"})

    def test_persisted_conversation_is_recalled_after_bootstrap_restart(self) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("I like cats")

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process("recall cats")

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 1)
        self.assertIn("User: I like cats", response.message)

    def test_active_session_and_conversation_persist_across_a_bootstrap_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("create session work-1")
        first_brain.process("use session work-1")
        first_brain.process("I like cats")

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        session_manager = restarted_bootstrap.container.resolve(SessionManager)
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process("recall cats")

        self.assertEqual(session_manager.get_active().session_id, "work-1")
        self.assertEqual(response.memory_count, 1)
        self.assertIn("User: I like cats", response.message)

    def test_request_override_remains_local_after_a_restart(self) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("create session work-1")
        first_brain.process("use session work-1")
        first_brain.process(
            BrainRequest(
                message="I like cats",
                metadata={"session_id": "default"},
            )
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        session_manager = restarted_bootstrap.container.resolve(SessionManager)
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process(
            BrainRequest(
                message="recall cats",
                metadata={"session_id": "default"},
            )
        )

        self.assertIn("User: I like cats", response.message)
        self.assertEqual(session_manager.get_active().session_id, "work-1")

    def test_duplicate_session_create_remains_idempotent_after_restart(self) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_bootstrap.container.resolve(Brain).process("create session work-1")

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process("create session work-1")

        self.assertTrue(response.success)
        self.assertEqual(response.message, "Session already exists: work-1")
        self.assertEqual(
            [
                session.session_id
                for session in restarted_bootstrap.container.resolve(
                    SessionManager
                ).list()
            ],
            ["default", "work-1"],
        )

    def test_persisted_search_records_are_excluded_from_recall(self) -> None:
        document_path = Path(self.temporary_directory.name) / "knowledge.md"
        document_path.write_text("Hypatia", encoding="utf-8")
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        knowledge_engine = first_bootstrap.container.resolve(KnowledgeEngine)
        first_brain = first_bootstrap.container.resolve(Brain)
        knowledge_engine.load(document_path)
        first_brain.process("search hypatia")

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process("recall hypatia")

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message, "No matching conversation records found.")

    def test_custom_session_conversation_persists_and_is_recalled_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("create session work-1")
        first_brain.process(
            BrainRequest(
                message="I like cats",
                metadata={"session_id": "work-1"},
            )
        )

        document = json.loads(self.memory_path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["records"][0]["metadata"]["session_id"], "work-1")
        self.assertEqual(set(document), {"schema_version", "records"})

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process(
            BrainRequest(
                message="recall cats",
                metadata={"session_id": "work-1"},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 1)
        self.assertIn("User: I like cats", response.message)

    def test_custom_session_record_is_excluded_from_default_recall_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("create session work-1")
        first_brain.process(
            BrainRequest(
                message="I like cats",
                metadata={"session_id": "work-1"},
            )
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process("recall cats")

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)

    def test_same_query_stays_isolated_between_sessions_after_restart(self) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("create session work-1")
        first_brain.process("create session personal")
        first_brain.process(
            BrainRequest(
                message="Cats are my work topic",
                metadata={"session_id": "work-1"},
            )
        )
        first_brain.process(
            BrainRequest(
                message="Cats are my personal topic",
                metadata={"session_id": "personal"},
            )
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        work_response = restarted_brain.process(
            BrainRequest(
                message="recall cats",
                metadata={"session_id": "work-1"},
            )
        )
        personal_response = restarted_brain.process(
            BrainRequest(
                message="recall cats",
                metadata={"session_id": "personal"},
            )
        )

        self.assertIn("work topic", work_response.message)
        self.assertNotIn("personal topic", work_response.message)
        self.assertIn("personal topic", personal_response.message)
        self.assertNotIn("work topic", personal_response.message)

    def test_persisted_search_records_are_excluded_from_custom_session_recall(
        self,
    ) -> None:
        document_path = Path(self.temporary_directory.name) / "knowledge.md"
        document_path.write_text("Hypatia", encoding="utf-8")
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        knowledge_engine = first_bootstrap.container.resolve(KnowledgeEngine)
        first_brain = first_bootstrap.container.resolve(Brain)
        knowledge_engine.load(document_path)
        first_brain.process("create session work-1")
        first_brain.process("search hypatia")

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_brain = restarted_bootstrap.container.resolve(Brain)
        response = restarted_brain.process(
            BrainRequest(
                message="recall hypatia",
                metadata={"session_id": "work-1"},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)

    def test_recent_conversations_persist_session_filter_order_and_limits_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_container = first_bootstrap.container
        first_brain = first_container.resolve(Brain)
        first_memory_manager = first_container.resolve(MemoryManager)
        first_brain.process("create session work-1")
        first_brain.process("create session personal")
        first_brain.process("use session work-1")
        for index in range(6):
            first_brain.process(f"Work message {index}")
        first_brain.process(
            BrainRequest(
                message="Personal message",
                metadata={"session_id": "personal"},
            )
        )
        first_memory_manager.add(
            "Search record",
            metadata={"session_id": "work-1"},
            tags={"cognition", "knowledge-search", "conversation"},
        )
        first_memory_manager.add(
            "Plan record",
            metadata={"session_id": "work-1"},
            tags={"brain", "plan"},
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_container = restarted_bootstrap.container
        restarted_brain = restarted_container.resolve(Brain)
        restarted_memory_manager = restarted_container.resolve(MemoryManager)
        restarted_session_manager = restarted_container.resolve(SessionManager)
        events: list[str] = []
        restarted_container.resolve(EventBus).subscribe(
            "*",
            lambda event: events.append(event.name),
        )
        memory_count = restarted_memory_manager.count()
        session_document = self.session_path.read_text(encoding="utf-8")

        default_response = restarted_brain.process("recent conversations")
        one_response = restarted_brain.process("recent conversations 1")
        twenty_response = restarted_brain.process("recent conversations 20")

        self.assertEqual(restarted_session_manager.get_active().session_id, "work-1")
        self.assertEqual(default_response.memory_count, 5)
        self.assertIn("1. User: Work message 5", default_response.message)
        self.assertIn("5. User: Work message 1", default_response.message)
        self.assertNotIn("Work message 0", default_response.message)
        self.assertNotIn("Personal message", default_response.message)
        self.assertNotIn("Search record", default_response.message)
        self.assertNotIn("Plan record", default_response.message)
        self.assertEqual(one_response.memory_count, 1)
        self.assertIn("1. User: Work message 5", one_response.message)
        self.assertEqual(twenty_response.memory_count, 6)
        self.assertIn("6. User: Work message 0", twenty_response.message)
        self.assertEqual(restarted_memory_manager.count(), memory_count)
        self.assertEqual(
            self.session_path.read_text(encoding="utf-8"), session_document
        )
        self.assertEqual(events, [])

    def test_recent_conversations_request_override_remains_local_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("create session work-1")
        first_brain.process("use session work-1")
        first_brain.process("Work conversation")
        first_brain.process(
            BrainRequest(
                message="Default conversation",
                metadata={"session_id": "default"},
            )
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        session_manager = restarted_bootstrap.container.resolve(SessionManager)
        brain = restarted_bootstrap.container.resolve(Brain)
        response = brain.process(
            BrainRequest(
                message="recent conversations",
                metadata={"session_id": "default"},
            )
        )

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Default conversation", response.message)
        self.assertNotIn("Work conversation", response.message)
        self.assertEqual(session_manager.get_active().session_id, "work-1")

    def test_recent_conversations_treats_only_missing_session_metadata_as_legacy(
        self,
    ) -> None:
        now = datetime.now(UTC)
        JsonFileMemoryStore(self.memory_path).save(
            [
                MemoryRecord(
                    memory_id="legacy-record",
                    content="Legacy conversation",
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now,
                    updated_at=now,
                ),
                MemoryRecord(
                    memory_id="null-session-record",
                    content="Null session conversation",
                    metadata={"session_id": None},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(seconds=1),
                    updated_at=now + timedelta(seconds=1),
                ),
            ]
        )

        bootstrap = self._bootstrap()
        bootstrap.initialize()
        response = bootstrap.container.resolve(Brain).process("recent conversations")

        self.assertEqual(response.memory_count, 1)
        self.assertIn("Legacy conversation", response.message)
        self.assertNotIn("Null session conversation", response.message)

    def test_session_overview_preserves_counts_and_read_only_state_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_container = first_bootstrap.container
        first_brain = first_container.resolve(Brain)
        first_memory_manager = first_container.resolve(MemoryManager)
        first_brain.process("create session work-1")
        first_brain.process("create session research")
        first_brain.process("use session work-1")
        first_brain.process("Work conversation")
        first_brain.process(
            BrainRequest(
                message="Research conversation",
                metadata={"session_id": "research"},
            )
        )
        first_brain.process(
            BrainRequest(
                message="Default conversation",
                metadata={"session_id": "default"},
            )
        )
        for content, metadata, tags in (
            ("Legacy default", {}, {"brain", "conversation"}),
            ("Null session", {"session_id": None}, {"brain", "conversation"}),
            ("Numeric session", {"session_id": 123}, {"brain", "conversation"}),
            ("Orphan session", {"session_id": "orphan"}, {"brain", "conversation"}),
            (
                "Knowledge search",
                {"session_id": "work-1"},
                {"cognition", "knowledge-search", "conversation"},
            ),
            ("Plan record", {"session_id": "work-1"}, {"brain", "plan"}),
        ):
            first_memory_manager.add(content, metadata=metadata, tags=tags)

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_container = restarted_bootstrap.container
        restarted_brain = restarted_container.resolve(Brain)
        restarted_memory_manager = restarted_container.resolve(MemoryManager)
        restarted_session_manager = restarted_container.resolve(SessionManager)
        events: list[str] = []
        restarted_container.resolve(EventBus).subscribe(
            "*",
            lambda event: events.append(event.name),
        )
        memory_count = restarted_memory_manager.count()
        memory_document = self.memory_path.read_text(encoding="utf-8")
        session_document = self.session_path.read_text(encoding="utf-8")

        response = restarted_brain.process(
            BrainRequest(message="session overview", metadata={"session_id": 123})
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_overview")
        self.assertEqual(
            response.message,
            "Sessions:\n"
            "1. default — 2 conversations\n"
            "2. work-1 — 1 conversation [active]\n"
            "3. research — 1 conversation",
        )
        self.assertEqual(response.memory_count, 4)
        self.assertEqual(restarted_session_manager.get_active().session_id, "work-1")
        self.assertEqual(restarted_memory_manager.count(), memory_count)
        self.assertEqual(self.memory_path.read_text(encoding="utf-8"), memory_document)
        self.assertEqual(
            self.session_path.read_text(encoding="utf-8"),
            session_document,
        )
        self.assertEqual(events, [])
        self.assertEqual(json.loads(memory_document)["schema_version"], 1)
        self.assertEqual(json.loads(session_document)["schema_version"], 1)

    def test_session_details_preserves_read_only_contract_after_restart(self) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_container = first_bootstrap.container
        first_brain = first_container.resolve(Brain)
        first_memory_manager = first_container.resolve(MemoryManager)
        first_brain.process("create session work-1")
        first_brain.process("create session research")
        first_brain.process("use session work-1")
        first_brain.process("Work conversation")
        first_brain.process("Another work conversation")
        first_brain.process(
            BrainRequest(
                message="Research conversation",
                metadata={"session_id": "research"},
            )
        )
        first_memory_manager.add(
            "Search record",
            metadata={"session_id": "work-1"},
            tags={"cognition", "knowledge-search", "conversation"},
        )
        first_memory_manager.add(
            "Null session",
            metadata={"session_id": None},
            tags={"brain", "conversation"},
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_container = restarted_bootstrap.container
        restarted_brain = restarted_container.resolve(Brain)
        restarted_memory_manager = restarted_container.resolve(MemoryManager)
        restarted_session_manager = restarted_container.resolve(SessionManager)
        events: list[str] = []
        restarted_container.resolve(EventBus).subscribe(
            "*",
            lambda event: events.append(event.name),
        )
        work_session = next(
            session
            for session in restarted_session_manager.list()
            if session.session_id == "work-1"
        )
        memory_count = restarted_memory_manager.count()
        memory_document = self.memory_path.read_text(encoding="utf-8")
        session_document = self.session_path.read_text(encoding="utf-8")

        response = restarted_brain.process(
            BrainRequest(
                message="session details work-1",
                metadata={"session_id": 123},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_details")
        self.assertEqual(
            response.message,
            "Session: work-1\n"
            "Status: active\n"
            "Conversations: 2 conversations\n"
            f"Created: {work_session.created_at.isoformat()}",
        )
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(restarted_session_manager.get_active().session_id, "work-1")
        self.assertEqual(restarted_memory_manager.count(), memory_count)
        self.assertEqual(self.memory_path.read_text(encoding="utf-8"), memory_document)
        self.assertEqual(
            self.session_path.read_text(encoding="utf-8"),
            session_document,
        )
        self.assertEqual(events, [])
        self.assertEqual(json.loads(memory_document)["schema_version"], 1)
        self.assertEqual(json.loads(session_document)["schema_version"], 1)

    def test_session_activity_preserves_aggregation_and_read_only_state_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("create session work research")
        first_brain.process("create session other")
        first_brain.process("use session other")

        oldest = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
        middle = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)
        newest = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
        JsonFileMemoryStore(self.memory_path).save(
            [
                MemoryRecord(
                    memory_id="target-middle",
                    content="Target middle",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=middle,
                    updated_at=middle,
                ),
                MemoryRecord(
                    memory_id="target-newest",
                    content="Target newest",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=newest,
                    updated_at=newest,
                ),
                MemoryRecord(
                    memory_id="target-oldest",
                    content="Target oldest",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=oldest,
                    updated_at=oldest,
                ),
                MemoryRecord(
                    memory_id="wrong-tags",
                    content="Wrong tags",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"cognition", "knowledge-search", "conversation"}),
                    created_at=newest + timedelta(hours=1),
                    updated_at=newest + timedelta(hours=1),
                ),
                MemoryRecord(
                    memory_id="null-session",
                    content="Null session",
                    metadata={"session_id": None},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=newest + timedelta(hours=2),
                    updated_at=newest + timedelta(hours=2),
                ),
                MemoryRecord(
                    memory_id="non-string-session",
                    content="Non-string session",
                    metadata={"session_id": 123},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=newest + timedelta(hours=3),
                    updated_at=newest + timedelta(hours=3),
                ),
                MemoryRecord(
                    memory_id="other-session",
                    content="Other session",
                    metadata={"session_id": "other"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=newest + timedelta(hours=4),
                    updated_at=newest + timedelta(hours=4),
                ),
                MemoryRecord(
                    memory_id="legacy-default",
                    content="Legacy default",
                    tags=frozenset({"brain", "conversation"}),
                    created_at=newest + timedelta(hours=5),
                    updated_at=newest + timedelta(hours=5),
                ),
                MemoryRecord(
                    memory_id="explicit-default",
                    content="Explicit default",
                    metadata={"session_id": "default"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=newest + timedelta(hours=6),
                    updated_at=newest + timedelta(hours=6),
                ),
            ]
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_container = restarted_bootstrap.container
        restarted_brain = restarted_container.resolve(Brain)
        restarted_memory_manager = restarted_container.resolve(MemoryManager)
        restarted_session_manager = restarted_container.resolve(SessionManager)
        events: list[str] = []
        restarted_container.resolve(EventBus).subscribe(
            "*",
            lambda event: events.append(event.name),
        )
        memory_count = restarted_memory_manager.count()
        memory_records = restarted_memory_manager.all()
        sessions = restarted_session_manager.list()
        active_session_id = restarted_session_manager.get_active().session_id
        memory_document = self.memory_path.read_text(encoding="utf-8")
        session_document = self.session_path.read_text(encoding="utf-8")

        response = restarted_brain.process(
            BrainRequest(
                message="session activity work research",
                metadata={"session_id": "other", "intent": "message"},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_activity")
        self.assertEqual(response.memory_count, 3)
        self.assertEqual(
            response.message,
            "Session: work research\n"
            "Conversations: 3\n"
            f"First activity: {oldest.isoformat()}\n"
            f"Last activity: {newest.isoformat()}",
        )
        self.assertEqual(
            restarted_session_manager.get_active().session_id, active_session_id
        )
        self.assertEqual(restarted_session_manager.list(), sessions)
        self.assertEqual(restarted_memory_manager.count(), memory_count)
        self.assertEqual(restarted_memory_manager.all(), memory_records)
        self.assertEqual(self.memory_path.read_text(encoding="utf-8"), memory_document)
        self.assertEqual(
            self.session_path.read_text(encoding="utf-8"),
            session_document,
        )
        self.assertEqual(events, [])
        self.assertEqual(json.loads(memory_document)["schema_version"], 1)
        self.assertEqual(json.loads(session_document)["schema_version"], 1)

    def test_session_recent_preserves_target_and_read_only_state_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_container = first_bootstrap.container
        first_brain = first_container.resolve(Brain)
        first_memory_manager = first_container.resolve(MemoryManager)
        first_brain.process("create session work research")
        for index in range(6):
            first_brain.process(
                BrainRequest(
                    message=f"Target conversation {index}",
                    metadata={"session_id": "work research"},
                )
            )
        first_brain.process(
            BrainRequest(
                message="Other session conversation",
                metadata={"session_id": "default"},
            )
        )
        first_memory_manager.add(
            "Search record",
            metadata={"session_id": "work research"},
            tags={"cognition", "knowledge-search", "conversation"},
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_container = restarted_bootstrap.container
        restarted_brain = restarted_container.resolve(Brain)
        restarted_memory_manager = restarted_container.resolve(MemoryManager)
        restarted_session_manager = restarted_container.resolve(SessionManager)
        events: list[str] = []
        restarted_container.resolve(EventBus).subscribe(
            "*",
            lambda event: events.append(event.name),
        )
        memory_count = restarted_memory_manager.count()
        memory_document = self.memory_path.read_text(encoding="utf-8")
        session_document = self.session_path.read_text(encoding="utf-8")

        response = restarted_brain.process(
            BrainRequest(
                message="SESSION RECENT work research",
                metadata={"session_id": 123},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_recent")
        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. User: Target conversation 5", response.message)
        self.assertIn("5. User: Target conversation 1", response.message)
        self.assertNotIn("Target conversation 0", response.message)
        self.assertNotIn("Other session conversation", response.message)
        self.assertNotIn("Search record", response.message)
        self.assertEqual(restarted_session_manager.get_active().session_id, "default")
        self.assertEqual(restarted_memory_manager.count(), memory_count)
        self.assertEqual(self.memory_path.read_text(encoding="utf-8"), memory_document)
        self.assertEqual(
            self.session_path.read_text(encoding="utf-8"),
            session_document,
        )
        self.assertEqual(events, [])

    def test_session_search_preserves_target_and_read_only_state_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("create session work research")
        first_brain.process("create session other")
        first_brain.process("use session other")

        now = datetime.now(UTC)
        JsonFileMemoryStore(self.memory_path).save(
            [
                MemoryRecord(
                    memory_id="target-a",
                    content="A persistence target",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now,
                    updated_at=now,
                ),
                MemoryRecord(
                    memory_id="target-b",
                    content="B persistence target",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(hours=1),
                    updated_at=now + timedelta(hours=1),
                ),
                MemoryRecord(
                    memory_id="target-other-query",
                    content="Target without the query",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(hours=2),
                    updated_at=now + timedelta(hours=2),
                ),
                MemoryRecord(
                    memory_id="other-session",
                    content="Other persistence target",
                    metadata={"session_id": "other"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(hours=3),
                    updated_at=now + timedelta(hours=3),
                ),
                MemoryRecord(
                    memory_id="legacy-default",
                    content="Legacy persistence target",
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(hours=4),
                    updated_at=now + timedelta(hours=4),
                ),
                MemoryRecord(
                    memory_id="null-session",
                    content="Null persistence target",
                    metadata={"session_id": None},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(hours=5),
                    updated_at=now + timedelta(hours=5),
                ),
                MemoryRecord(
                    memory_id="non-string-session",
                    content="Non-string persistence target",
                    metadata={"session_id": 123},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(hours=6),
                    updated_at=now + timedelta(hours=6),
                ),
                MemoryRecord(
                    memory_id="knowledge-record",
                    content="Knowledge persistence target",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"cognition", "knowledge-search", "conversation"}),
                    created_at=now + timedelta(hours=7),
                    updated_at=now + timedelta(hours=7),
                ),
            ]
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_container = restarted_bootstrap.container
        restarted_brain = restarted_container.resolve(Brain)
        restarted_memory_manager = restarted_container.resolve(MemoryManager)
        restarted_session_manager = restarted_container.resolve(SessionManager)
        events: list[str] = []
        restarted_container.resolve(EventBus).subscribe(
            "*",
            lambda event: events.append(event.name),
        )
        memory_count = restarted_memory_manager.count()
        memory_document = self.memory_path.read_text(encoding="utf-8")
        session_document = self.session_path.read_text(encoding="utf-8")

        response = restarted_brain.process(
            BrainRequest(
                message="session search work research -- persistence",
                metadata={"session_id": "other", "intent": "message"},
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_search")
        self.assertEqual(response.memory_count, 2)
        self.assertIn("1. A persistence target", response.message)
        self.assertIn("2. B persistence target", response.message)
        self.assertNotIn("Other persistence target", response.message)
        self.assertNotIn("Legacy persistence target", response.message)
        self.assertNotIn("Null persistence target", response.message)
        self.assertNotIn("Non-string persistence target", response.message)
        self.assertNotIn("Knowledge persistence target", response.message)
        self.assertEqual(restarted_session_manager.get_active().session_id, "other")
        self.assertEqual(restarted_memory_manager.count(), memory_count)
        self.assertEqual(self.memory_path.read_text(encoding="utf-8"), memory_document)
        self.assertEqual(
            self.session_path.read_text(encoding="utf-8"),
            session_document,
        )
        self.assertEqual(events, [])
        self.assertEqual(json.loads(memory_document)["schema_version"], 1)
        self.assertEqual(json.loads(session_document)["schema_version"], 1)

    def test_conversation_search_preserves_filter_order_and_limit_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_container = first_bootstrap.container
        first_brain = first_container.resolve(Brain)
        first_memory_manager = first_container.resolve(MemoryManager)
        first_brain.process("create session work-1")
        first_brain.process("create session personal")
        first_brain.process("use session work-1")
        for index in range(5):
            first_brain.process(
                BrainRequest(
                    message=f"Personal bootstrap relevance {index}",
                    metadata={"session_id": "personal"},
                )
            )
        for index in range(6):
            first_brain.process(f"Work bootstrap relevance {index}")
        first_memory_manager.add(
            "Knowledge bootstrap relevance",
            metadata={"session_id": "work-1"},
            tags={"cognition", "knowledge-search", "conversation"},
        )
        first_memory_manager.add(
            "Plan bootstrap relevance",
            metadata={"session_id": "work-1"},
            tags={"brain", "plan"},
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        restarted_container = restarted_bootstrap.container
        restarted_brain = restarted_container.resolve(Brain)
        restarted_memory_manager = restarted_container.resolve(MemoryManager)
        restarted_session_manager = restarted_container.resolve(SessionManager)
        events: list[str] = []
        restarted_container.resolve(EventBus).subscribe(
            "*",
            lambda event: events.append(event.name),
        )
        memory_count = restarted_memory_manager.count()
        memory_document = self.memory_path.read_text(encoding="utf-8")
        session_document = self.session_path.read_text(encoding="utf-8")

        response = restarted_brain.process("search conversations bootstrap")

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "conversation_search")
        self.assertEqual(restarted_session_manager.get_active().session_id, "work-1")
        self.assertEqual(response.memory_count, 5)
        self.assertIn("1. User: Work bootstrap relevance 0", response.message)
        self.assertIn("5. User: Work bootstrap relevance 4", response.message)
        self.assertNotIn("Work bootstrap relevance 5", response.message)
        self.assertNotIn("Personal bootstrap relevance", response.message)
        self.assertNotIn("Knowledge bootstrap relevance", response.message)
        self.assertNotIn("Plan bootstrap relevance", response.message)
        self.assertEqual(restarted_memory_manager.count(), memory_count)
        self.assertEqual(self.memory_path.read_text(encoding="utf-8"), memory_document)
        self.assertEqual(
            self.session_path.read_text(encoding="utf-8"), session_document
        )
        self.assertEqual(events, [])

    def test_conversation_search_request_override_remains_local_after_restart(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("create session work-1")
        first_brain.process("use session work-1")
        first_brain.process("Work bootstrap discussion")
        first_brain.process(
            BrainRequest(
                message="Default bootstrap discussion",
                metadata={"session_id": "default"},
            )
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        session_manager = restarted_bootstrap.container.resolve(SessionManager)
        response = restarted_bootstrap.container.resolve(Brain).process(
            BrainRequest(
                message="search conversations bootstrap",
                metadata={"session_id": "default"},
            )
        )

        self.assertTrue(response.success)
        self.assertIn("Default bootstrap discussion", response.message)
        self.assertNotIn("Work bootstrap discussion", response.message)
        self.assertEqual(session_manager.get_active().session_id, "work-1")

    def test_session_memory_policy_semantics_survive_restart_across_commands(
        self,
    ) -> None:
        first_bootstrap = self._bootstrap()
        first_bootstrap.initialize()
        first_brain = first_bootstrap.container.resolve(Brain)
        first_brain.process("create session work research")
        first_brain.process("create session other")
        first_brain.process("use session other")

        now = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
        JsonFileMemoryStore(self.memory_path).save(
            [
                MemoryRecord(
                    memory_id="legacy-default",
                    content="Legacy default policy",
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now,
                    updated_at=now,
                ),
                MemoryRecord(
                    memory_id="explicit-default",
                    content="Explicit default policy",
                    metadata={"session_id": "default"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(seconds=1),
                    updated_at=now + timedelta(seconds=1),
                ),
                MemoryRecord(
                    memory_id="null-session",
                    content="Null policy",
                    metadata={"session_id": None},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(seconds=2),
                    updated_at=now + timedelta(seconds=2),
                ),
                MemoryRecord(
                    memory_id="numeric-session",
                    content="Numeric policy",
                    metadata={"session_id": 123},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(seconds=3),
                    updated_at=now + timedelta(seconds=3),
                ),
                *[
                    MemoryRecord(
                        memory_id=f"target-{index}",
                        content=f"Target policy {index}",
                        metadata={"session_id": "work research"},
                        tags=frozenset({"brain", "conversation"}),
                        created_at=now + timedelta(minutes=index),
                        updated_at=now + timedelta(minutes=index),
                    )
                    for index in range(3)
                ],
                MemoryRecord(
                    memory_id="wrong-case",
                    content="Wrong case policy",
                    metadata={"session_id": "Work Research"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(minutes=4),
                    updated_at=now + timedelta(minutes=4),
                ),
                MemoryRecord(
                    memory_id="wrong-tags",
                    content="Wrong tags policy",
                    metadata={"session_id": "work research"},
                    tags=frozenset({"cognition", "knowledge-search", "conversation"}),
                    created_at=now + timedelta(minutes=5),
                    updated_at=now + timedelta(minutes=5),
                ),
                MemoryRecord(
                    memory_id="other-session",
                    content="Other policy",
                    metadata={"session_id": "other"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(minutes=6),
                    updated_at=now + timedelta(minutes=6),
                ),
                MemoryRecord(
                    memory_id="orphan-session",
                    content="Orphan policy",
                    metadata={"session_id": "orphan"},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(minutes=7),
                    updated_at=now + timedelta(minutes=7),
                ),
            ]
        )

        restarted_bootstrap = self._bootstrap()
        restarted_bootstrap.initialize()
        container = restarted_bootstrap.container
        brain = container.resolve(Brain)
        memory_manager = container.resolve(MemoryManager)
        session_manager = container.resolve(SessionManager)
        events: list[str] = []
        container.resolve(EventBus).subscribe(
            "*", lambda event: events.append(event.name)
        )
        memory_document = self.memory_path.read_text(encoding="utf-8")
        session_document = self.session_path.read_text(encoding="utf-8")
        records = memory_manager.all()
        sessions = session_manager.list()

        overview = brain.process("session overview")
        details = brain.process("session details work research")
        recent = brain.process("session recent work research")
        search = brain.process("session search work research -- policy")
        activity = brain.process("session activity work research")

        self.assertEqual(overview.memory_count, 6)
        overview_lines = overview.message.splitlines()
        self.assertTrue(overview_lines[1].startswith("1. default"))
        self.assertTrue(overview_lines[1].endswith("2 conversations"))
        self.assertTrue(overview_lines[2].startswith("2. work research"))
        self.assertTrue(overview_lines[2].endswith("3 conversations"))
        self.assertTrue(overview_lines[3].startswith("3. other"))
        self.assertTrue(overview_lines[3].endswith("1 conversation [active]"))
        self.assertEqual(details.memory_count, 3)
        self.assertEqual(recent.memory_count, 3)
        self.assertIn("1. Target policy 2", recent.message)
        self.assertIn("3. Target policy 0", recent.message)
        self.assertEqual(search.memory_count, 3)
        self.assertNotIn("Wrong case policy", search.message)
        self.assertNotIn("Wrong tags policy", search.message)
        self.assertEqual(activity.memory_count, 3)
        self.assertIn(f"First activity: {now.isoformat()}", activity.message)
        self.assertIn(
            f"Last activity: {(now + timedelta(minutes=2)).isoformat()}",
            activity.message,
        )
        self.assertEqual(session_manager.get_active().session_id, "other")
        self.assertEqual(session_manager.list(), sessions)
        self.assertEqual(memory_manager.all(), records)
        self.assertEqual(self.memory_path.read_text(encoding="utf-8"), memory_document)
        self.assertEqual(
            self.session_path.read_text(encoding="utf-8"), session_document
        )
        self.assertEqual(events, [])

    def test_conversation_search_legacy_and_invalid_session_contracts_survive_restart(
        self,
    ) -> None:
        now = datetime.now(UTC)
        JsonFileMemoryStore(self.memory_path).save(
            [
                MemoryRecord(
                    memory_id="legacy-bootstrap",
                    content="Legacy bootstrap conversation",
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now,
                    updated_at=now,
                ),
                MemoryRecord(
                    memory_id="null-session-bootstrap",
                    content="Null session bootstrap conversation",
                    metadata={"session_id": None},
                    tags=frozenset({"brain", "conversation"}),
                    created_at=now + timedelta(seconds=1),
                    updated_at=now + timedelta(seconds=1),
                ),
            ]
        )
        bootstrap = self._bootstrap()
        bootstrap.initialize()
        container = bootstrap.container
        brain = container.resolve(Brain)
        memory_manager = container.resolve(MemoryManager)
        events: list[str] = []
        container.resolve(EventBus).subscribe(
            "*", lambda event: events.append(event.name)
        )
        memory_count = memory_manager.count()

        legacy_response = brain.process("search conversations bootstrap")
        empty_response = brain.process("search conversations")
        unknown_response = brain.process(
            BrainRequest(
                message="search conversations bootstrap",
                metadata={"session_id": "unknown"},
            )
        )
        invalid_response = brain.process(
            BrainRequest(
                message="search conversations bootstrap",
                metadata={"session_id": 123},
            )
        )

        self.assertEqual(legacy_response.memory_count, 1)
        self.assertIn("Legacy bootstrap conversation", legacy_response.message)
        self.assertNotIn("Null session bootstrap conversation", legacy_response.message)
        self.assertFalse(empty_response.success)
        self.assertEqual(empty_response.message, "Search query must not be empty.")
        self.assertFalse(unknown_response.success)
        self.assertEqual(unknown_response.message, "Unknown session: unknown")
        self.assertFalse(invalid_response.success)
        self.assertEqual(invalid_response.message, "session_id must be a string.")
        self.assertEqual(memory_manager.count(), memory_count)
        self.assertEqual(events, [])

    def test_session_rename_uses_shared_wiring_and_survives_restart(self) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()
        container = bootstrap.container
        service = container.resolve(SessionRenameTransactionService)
        sessions = container.resolve(SessionManager)
        memories = container.resolve(MemoryManager)
        event_bus = container.resolve(EventBus)
        brain = container.resolve(Brain)

        self.assertIs(service._session_manager, sessions)
        self.assertIs(service._memory_manager, memories)
        self.assertIs(service._event_bus, event_bus)
        sessions.create("work")
        sessions.set_active("work")
        memories.add(
            "Migrated conversation",
            metadata={"session_id": "work"},
            tags={"brain", "conversation"},
        )
        events: list[str] = []
        event_bus.subscribe("*", lambda event: events.append(event.name))

        response = brain.process("rename session work -- archive")
        restarted = self._bootstrap()
        restarted.initialize()
        restarted_container = restarted.container
        restarted_brain = restarted_container.resolve(Brain)

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "session_rename")
        self.assertEqual(events, ["session.renamed"])
        self.assertEqual(
            restarted_container.resolve(SessionManager).get_active().session_id,
            "archive",
        )
        self.assertIn(
            "Migrated conversation",
            restarted_brain.process("session recent archive").message,
        )
        source_response = restarted_brain.process("session details work")
        self.assertFalse(source_response.success)
        self.assertEqual(source_response.message, "Unknown session: work")

    def test_session_rename_preview_is_read_only_and_preserves_later_rename(
        self,
    ) -> None:
        bootstrap = self._bootstrap()
        bootstrap.initialize()
        container = bootstrap.container
        sessions = container.resolve(SessionManager)
        memories = container.resolve(MemoryManager)
        event_bus = container.resolve(EventBus)
        brain = container.resolve(Brain)
        sessions.create("work")
        memories.add("Work", metadata={"session_id": "work"})
        events: list[str] = []
        event_bus.subscribe("*", lambda event: events.append(event.name))
        sessions_before = sessions.snapshot()
        memories_before = memories.snapshot()
        memory_document = self.memory_path.read_text(encoding="utf-8")
        session_document = self.session_path.read_text(encoding="utf-8")

        preview = brain.process("preview rename session work -- archive")

        self.assertTrue(preview.success)
        self.assertEqual(preview.intent, "session_rename_preview")
        self.assertEqual(preview.memory_count, 1)
        self.assertEqual(sessions.snapshot(), sessions_before)
        self.assertEqual(memories.snapshot(), memories_before)
        self.assertEqual(self.memory_path.read_text(encoding="utf-8"), memory_document)
        self.assertEqual(
            self.session_path.read_text(encoding="utf-8"), session_document
        )
        self.assertEqual(events, [])

        restarted = self._bootstrap()
        restarted.initialize()
        restarted_container = restarted.container
        self.assertEqual(
            restarted_container.resolve(SessionManager).snapshot(), sessions_before
        )
        self.assertEqual(
            restarted_container.resolve(MemoryManager).snapshot(), memories_before
        )

        renamed = brain.process("rename session work -- archive")
        self.assertTrue(renamed.success)
        self.assertEqual(events, ["session.renamed"])


if __name__ == "__main__":
    unittest.main()
