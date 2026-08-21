"""Unit tests for ResponseComposer."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import planner

source_planner_dir = str(SRC_DIR / "planner")
if source_planner_dir not in planner.__path__:
    planner.__path__.append(source_planner_dir)

from brain.BrainRequest import BrainRequest
from brain.SessionSummary import SessionSummary
from knowledge.Chunk import Chunk, ChunkType
from knowledge.Document import DocumentType
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from knowledge.KnowledgeGraph import (
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphNodeKind,
    KnowledgeGraphRelation,
    KnowledgeGraphView,
)
from knowledge.KnowledgeRelationApplication import KnowledgeRelationApplication
from knowledge.KnowledgeRelationPreview import KnowledgeRelationPreview
from knowledge.KnowledgeRelationReference import KnowledgeRelationReference
from knowledge.KnowledgeRelationRevocation import KnowledgeRelationRevocation
from knowledge.KnowledgeRelationRevocationPreview import (
    KnowledgeRelationRevocationPreview,
)
from memory.MemoryRecord import MemoryRecord
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.SessionDeleteExecutionResult import SessionDeleteExecutionResult
from session.SessionDeletePolicy import SessionDeleteStatus
from session.SessionRecord import SessionRecord
from session.SessionRenamePreview import SessionRenamePreview
from session.SessionRenameResult import SessionRenameResult


class ResponseComposerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.composer = ResponseComposer()
        self.request = BrainRequest(message="hello")

    def test_greeting_composes_the_expected_response(self) -> None:
        response = self.composer.greeting(self.request)

        self.assertEqual(response.message, "Hello! I am Hypatia.")
        self.assertEqual(response.intent, "greeting")
        self.assertTrue(response.success)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_turkish_greeting_composes_a_turkish_response(self) -> None:
        request = BrainRequest(message="Merhaba!")

        response = self.composer.greeting(request)

        self.assertEqual(response.message, "Merhaba! Ben Hypatia.")
        self.assertEqual(response.intent, "greeting")
        self.assertTrue(response.success)
        self.assertEqual(response.request_id, request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_message_composes_the_expected_response(self) -> None:
        request = BrainRequest(message="how are you")

        response = self.composer.message(request)

        self.assertEqual(response.message, "I received your message: how are you")
        self.assertEqual(response.intent, "message")
        self.assertTrue(response.success)
        self.assertEqual(response.request_id, request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_search_success_preserves_results_and_formats_the_count(self) -> None:
        results = [
            Chunk("document", 0, "Hypatia", ChunkType.PARAGRAPH),
            Chunk("document", 1, "Knowledge", ChunkType.PARAGRAPH),
        ]

        response = self.composer.search_success(self.request, results)

        self.assertEqual(response.message, "I found 2 matching knowledge chunks.")
        self.assertEqual(response.intent, "search")
        self.assertTrue(response.success)
        self.assertIs(response.knowledge_results, results)

    def test_semantic_recall_status_composes_a_ready_read_only_response(self) -> None:
        response = self.composer.semantic_recall_status(
            self.request,
            runtime_state="ready",
            indexed_memory_records=3,
            embedding_dimension=768,
            last_rebuild_error=None,
            last_update_error=None,
        )

        self.assertEqual(
            response.message,
            "Semantic recall status:\n"
            "Runtime: ready\n"
            "Indexed memory records: 3\n"
            "Embedding dimension: 768\n"
            "Last rebuild: healthy\n"
            "Last incremental update: healthy",
        )
        self.assertEqual(response.intent, "semantic_recall_status")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_semantic_recall_retry_composes_started_duplicate_and_failure(self) -> None:
        started = self.composer.semantic_recall_retry_started(
            self.request,
            already_running=False,
        )
        duplicate = self.composer.semantic_recall_retry_started(
            self.request,
            already_running=True,
        )
        failure = self.composer.semantic_recall_retry_failure(
            self.request,
            "Semantic recall retry failed. Runtime remains unavailable.",
        )

        self.assertEqual(
            started.message,
            "Semantic recall rebuild started in the background.",
        )
        self.assertEqual(
            duplicate.message,
            "Semantic recall rebuild is already in progress; no second rebuild "
            "was started.",
        )
        self.assertEqual(started.intent, "semantic_recall_retry")
        self.assertTrue(started.success)
        self.assertEqual(started.memory_count, 0)
        self.assertTrue(duplicate.success)
        self.assertEqual(failure.intent, "semantic_recall_retry")
        self.assertFalse(failure.success)
        self.assertEqual(failure.memory_count, 0)

    def test_semantic_recall_status_composes_background_states(self) -> None:
        initializing = self.composer.semantic_recall_status(
            self.request,
            runtime_state="initializing",
            indexed_memory_records=None,
            embedding_dimension=None,
            last_rebuild_error=None,
            last_update_error=None,
        )
        refreshing = self.composer.semantic_recall_status(
            self.request,
            runtime_state="refreshing",
            indexed_memory_records=2,
            embedding_dimension=3,
            last_rebuild_error=None,
            last_update_error=None,
        )

        self.assertIn("Runtime: initializing", initializing.message)
        self.assertIn("Last rebuild: in progress", initializing.message)
        self.assertIn("Last incremental update: unavailable", initializing.message)
        self.assertIn("Runtime: refreshing", refreshing.message)
        self.assertIn("Indexed memory records: 2", refreshing.message)
        self.assertIn("Last rebuild: in progress", refreshing.message)
        self.assertIn("Last incremental update: healthy", refreshing.message)

    def test_search_success_exposes_one_citation_per_result(self) -> None:
        results = [
            Chunk(
                document_id="document-1",
                index=2,
                content="Hypatia source text",
                metadata={
                    "document_title": "Research Notes",
                    "document_source": "C:/knowledge/notes.md",
                },
                chunk_id="chunk-1",
            )
        ]

        response = self.composer.search_success(self.request, results)

        self.assertEqual(len(response.knowledge_citations), 1)
        citation = response.knowledge_citations[0]
        self.assertEqual(citation.document_id, "document-1")
        self.assertEqual(citation.document_title, "Research Notes")
        self.assertEqual(citation.source, "C:/knowledge/notes.md")
        self.assertEqual(citation.chunk_index, 2)
        self.assertEqual(citation.chunk_id, "chunk-1")
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_search_failure_preserves_the_given_message(self) -> None:
        response = self.composer.search_failure(
            self.request,
            "A search query is required.",
        )

        self.assertEqual(response.message, "A search query is required.")
        self.assertEqual(response.intent, "search")
        self.assertFalse(response.success)
        self.assertEqual(response.knowledge_results, [])
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_knowledge_context_truncates_display_without_changing_raw_results(
        self,
    ) -> None:
        content = "x" * 650
        results = [
            Chunk(
                document_id="document",
                index=0,
                content=content,
                metadata={
                    "document_title": "Local Notes",
                    "document_source": "C:/knowledge/notes.md",
                },
            )
        ]

        response = self.composer.knowledge_context_success(self.request, results)

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_context")
        self.assertIs(response.knowledge_results, results)
        self.assertIn(
            "Local Notes | C:/knowledge/notes.md | paragraph 1", response.message
        )
        self.assertIn("x" * 600 + "...", response.message)
        self.assertNotIn("x" * 601, response.message)

    def test_knowledge_graph_formats_visible_structural_relationships(
        self,
    ) -> None:
        result = Chunk(
            document_id="document",
            index=0,
            content="Hypatia",
            metadata={"document_title": "Local Notes", "document_source": "notes.md"},
        )
        view = KnowledgeGraphView(
            nodes=(
                KnowledgeGraphNode(
                    "document:document",
                    KnowledgeGraphNodeKind.DOCUMENT,
                    "Local Notes",
                ),
                KnowledgeGraphNode(
                    f"chunk:{result.chunk_id}",
                    KnowledgeGraphNodeKind.CHUNK,
                    "Paragraph 1",
                ),
            ),
            edges=(
                KnowledgeGraphEdge(
                    "document:document",
                    KnowledgeGraphRelation.CONTAINS,
                    f"chunk:{result.chunk_id}",
                ),
            ),
        )

        response = self.composer.knowledge_graph_success(self.request, [result], view)

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_graph")
        self.assertEqual(
            response.message,
            "Knowledge graph:\n- Local Notes --contains--> Paragraph 1",
        )
        self.assertEqual(len(response.knowledge_citations), 1)

    def test_knowledge_list_formats_document_identity_and_preserves_references(
        self,
    ) -> None:
        documents = [
            KnowledgeDocumentReference(
                document_id="document-1",
                title="Local Notes",
                source="notes.md",
                document_type=DocumentType.MARKDOWN,
                chunk_count=2,
            )
        ]

        response = self.composer.knowledge_list_success(self.request, documents)

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_list")
        self.assertEqual(response.knowledge_documents, documents)
        self.assertEqual(
            response.message,
            "Knowledge sources:\n"
            "- Local Notes | notes.md | chunks: 2 | id: document-1",
        )

    def test_knowledge_relation_preview_exposes_only_a_pending_change(self) -> None:
        source = KnowledgeDocumentReference(
            "source", "Source", "source.md", DocumentType.MARKDOWN, 1
        )
        target = KnowledgeDocumentReference(
            "target", "Target", "target.md", DocumentType.MARKDOWN, 1
        )
        preview = KnowledgeRelationPreview(
            source,
            KnowledgeGraphRelation.RELATED_TO,
            target,
        )

        response = self.composer.knowledge_relation_preview_success(
            self.request, preview
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_relation_preview")
        self.assertIs(response.knowledge_relation_preview, preview)
        self.assertIn("Relation: related_to", response.message)
        self.assertTrue(response.message.endswith("Changes: ready"))

    def test_knowledge_relation_apply_exposes_the_in_memory_boundary(self) -> None:
        source = KnowledgeDocumentReference(
            "source", "Source", "source.md", DocumentType.MARKDOWN, 1
        )
        target = KnowledgeDocumentReference(
            "target", "Target", "target.md", DocumentType.MARKDOWN, 1
        )
        preview = KnowledgeRelationPreview(
            source, KnowledgeGraphRelation.RELATED_TO, target
        )
        application = KnowledgeRelationApplication(
            preview,
            KnowledgeGraphEdge(
                "document:source", KnowledgeGraphRelation.RELATED_TO, "document:target"
            ),
        )

        response = self.composer.knowledge_relation_apply_success(
            self.request, application
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_relation_apply")
        self.assertIs(response.knowledge_relation_application, application)
        self.assertIn("Graph state: updated (memory only)", response.message)
        self.assertTrue(response.message.endswith("JSON memory: unchanged"))

    def test_knowledge_relation_removal_exposes_preview_and_persistence_boundary(
        self,
    ) -> None:
        source = KnowledgeDocumentReference(
            "source", "Source", "source.md", DocumentType.MARKDOWN, 1
        )
        target = KnowledgeDocumentReference(
            "target", "Target", "target.md", DocumentType.MARKDOWN, 1
        )
        relation = KnowledgeRelationPreview(
            source, KnowledgeGraphRelation.RELATED_TO, target
        )
        preview = KnowledgeRelationRevocationPreview(relation, persisted=True)
        revocation = KnowledgeRelationRevocation(
            preview,
            KnowledgeGraphEdge(
                "document:source", KnowledgeGraphRelation.RELATED_TO, "document:target"
            ),
        )

        preview_response = self.composer.knowledge_relation_removal_preview_success(
            self.request, preview
        )
        response = self.composer.knowledge_relation_remove_success(
            self.request, revocation
        )

        self.assertTrue(preview_response.success)
        self.assertIs(preview_response.knowledge_relation_revocation_preview, preview)
        self.assertIn("Relation storage: persisted", preview_response.message)
        self.assertTrue(preview_response.message.endswith("Changes: ready to remove"))
        self.assertTrue(response.success)
        self.assertIs(response.knowledge_relation_revocation, revocation)
        self.assertIn("Relation storage: removed", response.message)
        self.assertTrue(response.message.endswith("JSON memory: unchanged"))

    def test_knowledge_relation_list_formats_active_links_and_empty_state(self) -> None:
        source = KnowledgeDocumentReference(
            "source", "Source", "source.md", DocumentType.MARKDOWN, 1
        )
        target = KnowledgeDocumentReference(
            "target", "Target", "target.md", DocumentType.MARKDOWN, 1
        )
        relation = KnowledgeRelationReference(
            source, KnowledgeGraphRelation.RELATED_TO, target, persisted=True
        )

        response = self.composer.knowledge_relation_list_success(
            self.request, [relation]
        )
        empty_response = self.composer.knowledge_relation_list_success(self.request, [])

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_relation_list")
        self.assertEqual(response.knowledge_relations, [relation])
        self.assertIn(
            "Source | id: source --related_to--> Target | id: target",
            response.message,
        )
        self.assertTrue(response.message.endswith("storage: persisted"))
        self.assertEqual(
            empty_response.message, "No applied local knowledge relations are loaded."
        )

    def test_plan_success_preserves_goal_and_task_order(self) -> None:
        plan = Planner().create_plan("Read a PDF and summarize it")

        response = self.composer.plan_success(self.request, plan)

        self.assertEqual(response.intent, "plan")
        self.assertTrue(response.success)
        self.assertEqual(
            response.message,
            "Plan created for: Read a PDF and summarize it\n\n"
            "1. Locate file\n"
            "2. Read document\n"
            "3. Extract text\n"
            "4. Summarize\n"
            "5. Return response",
        )
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_plan_failure_preserves_the_given_message(self) -> None:
        response = self.composer.plan_failure(
            self.request,
            "A planning goal is required.",
        )

        self.assertEqual(response.message, "A planning goal is required.")
        self.assertEqual(response.intent, "plan")
        self.assertFalse(response.success)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_recall_success_with_no_records_returns_a_successful_empty_response(
        self,
    ) -> None:
        response = self.composer.recall_success(self.request, [])

        self.assertEqual(response.message, "No matching conversation records found.")
        self.assertEqual(response.intent, "recall")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_recall_success_numbers_a_single_record_without_changing_content(
        self,
    ) -> None:
        record = MemoryRecord(
            memory_id="memory-1",
            content="User: cats\nHypatia: Cats are animals.",
        )

        response = self.composer.recall_success(self.request, [record])

        self.assertEqual(
            response.message,
            "Matching conversation records:\n\n"
            "1. User: cats\nHypatia: Cats are animals.",
        )
        self.assertEqual(response.memory_count, 1)

    def test_recall_success_preserves_multiple_record_order(self) -> None:
        records = [
            MemoryRecord(memory_id="memory-1", content="User: first"),
            MemoryRecord(memory_id="memory-2", content="User: second"),
        ]

        response = self.composer.recall_success(self.request, records)

        self.assertEqual(
            response.message,
            "Matching conversation records:\n\n1. User: first\n\n2. User: second",
        )
        self.assertEqual(response.memory_count, 2)

    def test_recall_failure_preserves_the_given_message(self) -> None:
        response = self.composer.recall_failure(
            self.request,
            "A recall query is required.",
        )

        self.assertEqual(response.message, "A recall query is required.")
        self.assertEqual(response.intent, "recall")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_recent_conversations_preserves_record_order_and_content(self) -> None:
        records = [
            MemoryRecord(
                memory_id="memory-1",
                content="First conversation\nwith preserved formatting.",
            ),
            MemoryRecord(
                memory_id="memory-2",
                content="SECOND conversation!",
            ),
        ]

        response = self.composer.recent_conversations(
            self.request,
            records,
            self._session("work-1"),
        )

        self.assertEqual(
            response.message,
            "Recent conversations in work-1:\n"
            "1. First conversation\nwith preserved formatting.\n"
            "2. SECOND conversation!",
        )
        self.assertEqual(response.intent, "recent_conversations")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_recent_conversations_empty_composes_a_successful_response(self) -> None:
        response = self.composer.recent_conversations_empty(
            self.request,
            self._session("work-1"),
        )

        self.assertEqual(response.message, "No conversations found in session: work-1")
        self.assertEqual(response.intent, "recent_conversations")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_recent_conversations_failure_preserves_the_given_message(self) -> None:
        response = self.composer.recent_conversations_failure(
            self.request,
            "Count must be an integer.",
        )

        self.assertEqual(response.message, "Count must be an integer.")
        self.assertEqual(response.intent, "recent_conversations")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_conversation_search_results_preserves_record_order_and_content(
        self,
    ) -> None:
        records = [
            MemoryRecord(
                memory_id="memory-1",
                content="First matching conversation\nwith preserved formatting.",
            ),
            MemoryRecord(
                memory_id="memory-2",
                content="SECOND matching conversation!",
            ),
        ]

        response = self.composer.conversation_search_results(
            self.request,
            records,
            self._session("work-1"),
        )

        self.assertEqual(
            response.message,
            "Conversation matches in work-1:\n"
            "1. First matching conversation\nwith preserved formatting.\n"
            "2. SECOND matching conversation!",
        )
        self.assertEqual(response.intent, "conversation_search")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_conversation_search_empty_composes_a_successful_response(self) -> None:
        response = self.composer.conversation_search_empty(
            self.request,
            self._session("work-1"),
        )

        self.assertEqual(
            response.message,
            "No matching conversations found in session: work-1",
        )
        self.assertEqual(response.intent, "conversation_search")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_conversation_search_failure_preserves_the_given_message(self) -> None:
        response = self.composer.conversation_search_failure(
            self.request,
            "Search query must not be empty.",
        )

        self.assertEqual(response.message, "Search query must not be empty.")
        self.assertEqual(response.intent, "conversation_search")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_created_composes_the_expected_response(self) -> None:
        response = self.composer.session_created(self.request, self._session("work-1"))

        self.assertEqual(
            response.message,
            "Session created:\nID: work-1\nStatus: ready",
        )
        self.assertEqual(response.intent, "session_create")
        self.assertTrue(response.success)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.memory_count, 0)

    def test_session_exists_composes_the_expected_response(self) -> None:
        response = self.composer.session_exists(self.request, self._session("work-1"))

        self.assertEqual(response.message, "Session already exists: work-1")
        self.assertEqual(response.intent, "session_create")
        self.assertTrue(response.success)

    def test_session_create_failure_preserves_the_given_domain_message(self) -> None:
        response = self.composer.session_create_failure(
            self.request,
            "Session already exists: work-1",
        )

        self.assertEqual(
            response.message,
            "Session creation failed:\nReason: Session already exists: work-1",
        )
        self.assertEqual(response.intent, "session_create")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_activated_composes_the_expected_response(self) -> None:
        response = self.composer.session_activated(
            self.request, self._session("work-1")
        )

        self.assertEqual(response.message, "Active session: work-1")
        self.assertEqual(response.intent, "session_use")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_failure_preserves_the_given_message(self) -> None:
        response = self.composer.session_failure(
            self.request,
            "Unknown session: work-1",
        )

        self.assertEqual(response.message, "Unknown session: work-1")
        self.assertEqual(response.intent, "session")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_delete_preview_composes_each_policy_decision(self) -> None:
        allow = self.composer.session_delete_preview(
            self.request,
            "work-1",
            (),
            SessionDeleteStatus.ALLOW,
            "",
        )
        pending = self.composer.session_delete_preview(
            self.request,
            "work-1",
            ("memory-1", "memory-2"),
            SessionDeleteStatus.PENDING_MEMORY_POLICY,
            "session has attached memories",
        )
        denied = self.composer.session_delete_preview(
            self.request,
            "default",
            (),
            SessionDeleteStatus.DENY,
            "default session cannot be deleted",
        )

        self.assertTrue(allow.session_delete_allowed)
        self.assertFalse(pending.session_delete_allowed)
        self.assertFalse(denied.session_delete_allowed)

        self.assertEqual(
            allow.message,
            "Delete preview:\nSession: work-1\nDecision: ALLOW\n"
            "Affected memories: 0\nChanges: ready",
        )
        self.assertEqual(
            pending.message,
            "Delete preview:\nSession: work-1\nDecision: PENDING_MEMORY_POLICY\n"
            "Reason: session has attached memories",
        )
        self.assertEqual(
            denied.message,
            "Delete preview:\nSession: default\nDecision: DENY\n"
            "Reason: default session cannot be deleted",
        )
        self.assertEqual(pending.memory_count, 2)
        self.assertEqual(denied.intent, "session_delete_preview")
        self.assertEqual(allow.request_id, self.request.request_id)

    def test_session_deleted_composes_committed_zero_memory_result(self) -> None:
        response = self.composer.session_deleted(
            self.request,
            SessionDeleteExecutionResult(
                session_id="work-1",
                memory_records_removed=0,
                committed=True,
            ),
        )

        self.assertEqual(
            response.message,
            "Session deleted:\nID: work-1\nMemory records removed: 0\n"
            "Status: committed",
        )
        self.assertEqual(response.intent, "session_delete")
        self.assertEqual(response.memory_count, 0)
        self.assertTrue(response.success)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_deleted_preserves_removed_memory_count(self) -> None:
        response = self.composer.session_deleted(
            self.request,
            SessionDeleteExecutionResult(
                session_id="work-1",
                memory_records_removed=3,
                committed=True,
            ),
        )

        self.assertEqual(
            response.message,
            "Session deleted:\nID: work-1\nMemory records removed: 3\n"
            "Status: committed",
        )
        self.assertEqual(response.memory_count, 3)

    def test_session_delete_failure_composes_a_failed_delete_response(self) -> None:
        response = self.composer.session_delete_failure(
            self.request,
            "default session cannot be deleted",
        )

        self.assertEqual(
            response.message,
            "Delete failed:\nReason: default session cannot be deleted",
        )
        self.assertEqual(response.intent, "session_delete")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_delete_event_failure_composes_a_committed_warning(self) -> None:
        response = self.composer.session_delete_event_failure(
            self.request,
            SessionDeleteExecutionResult(
                session_id="work-1",
                memory_records_removed=3,
                committed=True,
            ),
        )

        self.assertEqual(
            response.message,
            "Session deleted:\nID: work-1\nMemory records removed: 3\n"
            "Status: committed\nWarning: lifecycle event publication failed",
        )
        self.assertEqual(response.intent, "session_delete")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 3)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_sessions_list_preserves_order_and_marks_only_the_active_session(
        self,
    ) -> None:
        sessions = [
            self._session("default"),
            self._session("work-1"),
            self._session("personal"),
        ]

        response = self.composer.sessions_list(
            self.request,
            sessions,
            sessions[1],
        )

        self.assertEqual(
            response.message,
            "Sessions:\n1. default\n2. work-1 (active)\n3. personal",
        )
        self.assertEqual(response.intent, "session_list")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.message.count("(active)"), 1)
        self.assertEqual(
            response.session_summaries,
            [
                SessionSummary("default", active=False, conversation_count=0),
                SessionSummary("work-1", active=True, conversation_count=0),
                SessionSummary("personal", active=False, conversation_count=0),
            ],
        )

    def test_session_overview_preserves_registry_order_and_formats_counts(self) -> None:
        sessions = [
            self._session("default"),
            self._session("work-1"),
            self._session("research"),
        ]

        response = self.composer.session_overview(
            self.request,
            sessions,
            {"default": 0, "work-1": 1, "research": 8},
            "work-1",
        )

        self.assertEqual(
            response.message,
            "Sessions:\n"
            "1. default — 0 conversations\n"
            "2. work-1 — 1 conversation [active]\n"
            "3. research — 8 conversations",
        )
        self.assertEqual(response.intent, "session_overview")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 9)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.message.count("[active]"), 1)
        self.assertEqual(
            response.session_summaries,
            [
                SessionSummary("default", active=False, conversation_count=0),
                SessionSummary("work-1", active=True, conversation_count=1),
                SessionSummary("research", active=False, conversation_count=8),
            ],
        )

    def test_session_overview_defaults_missing_counts_and_excludes_orphans(
        self,
    ) -> None:
        sessions = [self._session("default"), self._session("work-1")]

        response = self.composer.session_overview(
            self.request,
            sessions,
            {"default": 2, "orphan": 99},
            "default",
        )

        self.assertEqual(
            response.message,
            "Sessions:\n"
            "1. default — 2 conversations [active]\n"
            "2. work-1 — 0 conversations",
        )
        self.assertEqual(response.memory_count, 2)

    def test_session_overview_handles_an_empty_registry_deterministically(self) -> None:
        response = self.composer.session_overview(
            self.request,
            [],
            {"orphan": 99},
            "work-1",
        )

        self.assertEqual(response.message, "Sessions:\n")
        self.assertEqual(response.intent, "session_overview")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.session_summaries, [])

    def test_session_overview_failure_preserves_the_given_message(self) -> None:
        response = self.composer.session_overview_failure(
            self.request,
            "Memory snapshot changed.",
        )

        self.assertEqual(response.message, "Memory snapshot changed.")
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(response.intent, "session_overview")
        self.assertEqual(response.memory_count, 0)
        self.assertFalse(response.success)

    def test_session_details_composes_an_active_session_without_reformatting_time(
        self,
    ) -> None:
        session = SessionRecord(
            session_id="work-1",
            created_at=datetime(2026, 8, 5, 9, 10, tzinfo=UTC),
        )

        response = self.composer.session_details(
            self.request,
            session,
            conversation_count=1,
            is_active=True,
        )

        self.assertEqual(
            response.message,
            "Session: work-1\n"
            "Status: active\n"
            "Conversations: 1 conversation\n"
            "Created: 2026-08-05T09:10:00+00:00",
        )
        self.assertEqual(response.intent, "session_details")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 1)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_details_composes_an_inactive_session_with_plural_count(
        self,
    ) -> None:
        response = self.composer.session_details(
            self.request,
            self._session("research"),
            conversation_count=3,
            is_active=False,
        )

        self.assertEqual(
            response.message,
            "Session: research\n"
            "Status: inactive\n"
            "Conversations: 3 conversations\n"
            "Created: 2026-08-04T15:00:00+00:00",
        )
        self.assertEqual(response.memory_count, 3)

    def test_session_details_failure_preserves_the_given_message(self) -> None:
        response = self.composer.session_details_failure(
            self.request,
            "Session ID must not be empty.",
        )

        self.assertEqual(response.message, "Session ID must not be empty.")
        self.assertEqual(response.intent, "session_details")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_activity_composes_the_given_activity_values(self) -> None:
        first_activity = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
        last_activity = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)

        response = self.composer.session_activity(
            self.request,
            self._session("Work Research"),
            conversation_count=24,
            first_activity=first_activity,
            last_activity=last_activity,
        )

        self.assertEqual(
            response.message,
            "Session: Work Research\n"
            "Conversations: 24\n"
            "First activity: 2026-08-05T10:00:00+00:00\n"
            "Last activity: 2026-08-04T09:00:00+00:00",
        )
        self.assertEqual(response.intent, "session_activity")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 24)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_activity_renders_empty_sessions_successfully(self) -> None:
        response = self.composer.session_activity(
            self.request,
            self._session("empty-session"),
            conversation_count=0,
            first_activity=None,
            last_activity=None,
        )

        self.assertEqual(
            response.message,
            "Session: empty-session\n"
            "Conversations: 0\n"
            "First activity: none\n"
            "Last activity: none",
        )
        self.assertEqual(response.intent, "session_activity")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_activity_failure_preserves_the_given_message(self) -> None:
        response = self.composer.session_activity_failure(
            self.request,
            "Session ID must not be empty.",
        )

        self.assertEqual(response.message, "Session ID must not be empty.")
        self.assertEqual(response.intent, "session_activity")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_recent_preserves_record_order_and_content(self) -> None:
        records = [
            MemoryRecord(
                memory_id="memory-1",
                content="First conversation\nwith preserved formatting.",
            ),
            MemoryRecord(
                memory_id="memory-2",
                content="SECOND conversation!",
            ),
        ]

        response = self.composer.session_recent(
            self.request,
            records,
            self._session("Work Research"),
        )

        self.assertEqual(
            response.message,
            "Recent conversations in Work Research:\n"
            "1. First conversation\nwith preserved formatting.\n"
            "2. SECOND conversation!",
        )
        self.assertEqual(response.intent, "session_recent")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_recent_empty_composes_a_successful_response(self) -> None:
        response = self.composer.session_recent_empty(
            self.request,
            self._session("work-1"),
        )

        self.assertEqual(response.message, "No conversations found in session: work-1")
        self.assertEqual(response.intent, "session_recent")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_recent_failure_preserves_the_given_message(self) -> None:
        response = self.composer.session_recent_failure(
            self.request,
            "Session ID must not be empty.",
        )

        self.assertEqual(response.message, "Session ID must not be empty.")
        self.assertEqual(response.intent, "session_recent")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_search_results_preserve_the_given_record_order(self) -> None:
        records = [
            MemoryRecord(
                memory_id="memory-1",
                content="Second timestamp, first relevance result.",
                created_at=datetime(2026, 8, 5, 10, 0, tzinfo=UTC),
            ),
            MemoryRecord(
                memory_id="memory-2",
                content="First timestamp, second relevance result.",
                created_at=datetime(2026, 8, 4, 10, 0, tzinfo=UTC),
            ),
        ]

        response = self.composer.session_search_results(
            self.request,
            self._session("Work Research"),
            "Persistence Contract",
            records,
        )

        self.assertEqual(
            response.message,
            'Conversation matches in Work Research for "Persistence Contract":\n'
            "1. Second timestamp, first relevance result.\n"
            "2. First timestamp, second relevance result.",
        )
        self.assertEqual(response.intent, "session_search")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_search_empty_composes_a_successful_response(self) -> None:
        response = self.composer.session_search_empty(
            self.request,
            self._session("work research"),
            "persistence contract",
        )

        self.assertEqual(
            response.message,
            "No matching conversations found in session work research for: "
            "persistence contract",
        )
        self.assertEqual(response.intent, "session_search")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_search_failure_preserves_the_given_message(self) -> None:
        response = self.composer.session_search_failure(
            self.request,
            "Search query separator is required: --",
        )

        self.assertEqual(response.message, "Search query separator is required: --")
        self.assertEqual(response.intent, "session_search")
        self.assertFalse(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_rename_responses_preserve_the_exact_contract(self) -> None:
        result = SessionRenameResult("work", "Research Archive", 2, True)

        response = self.composer.session_renamed(self.request, result)

        self.assertEqual(
            response.message,
            "Rename complete:\n"
            "Source: work\n"
            "Target: Research Archive\n"
            "Memory records updated: 2\n"
            "Active session changed: yes\n"
            "Status: committed",
        )
        self.assertEqual(response.intent, "session_rename")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertEqual(response.request_id, self.request.request_id)
        zero_memory_response = self.composer.session_renamed(
            self.request,
            SessionRenameResult("work", "archive", 0, False),
        )
        self.assertEqual(
            zero_memory_response.message,
            "Rename complete:\n"
            "Source: work\n"
            "Target: archive\n"
            "Memory records updated: 0\n"
            "Active session changed: no\n"
            "Status: committed",
        )
        self.assertFalse(zero_memory_response.message.endswith("\n"))
        for message in (
            "Unknown session: missing",
            "Session already exists: personal",
            "Default session cannot be renamed.",
            "Session source and target must be different.",
        ):
            with self.subTest(message=message):
                failure = self.composer.session_rename_failure(self.request, message)

                self.assertEqual(
                    failure.message,
                    f"Rename failed:\nReason: {message}",
                )
                self.assertEqual(failure.intent, "session_rename")
                self.assertFalse(failure.success)
                self.assertEqual(failure.memory_count, 0)
                self.assertEqual(failure.request_id, self.request.request_id)
                self.assertFalse(failure.message.endswith("\n"))

    def test_session_rename_preview_responses_preserve_the_exact_contract(self) -> None:
        preview = SessionRenamePreview(
            "work", "archive", 2, True, ("memory-1", "memory-2")
        )
        response = self.composer.session_rename_preview(self.request, preview)
        failure = self.composer.session_rename_preview_failure(
            self.request,
            "Default session cannot be renamed.",
        )

        self.assertEqual(
            response.message,
            "Rename preview:\n"
            "Source: work\n"
            "Target: archive\n"
            "Affected memories: 2\n"
            "Memory IDs:\n"
            "- memory-1\n"
            "- memory-2\n"
            "Changes: ready",
        )
        self.assertEqual(response.intent, "session_rename_preview")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 2)
        self.assertFalse(response.message.endswith("\n"))
        zero_memory_response = self.composer.session_rename_preview(
            self.request,
            SessionRenamePreview("work", "archive", 0, False, ()),
        )
        self.assertEqual(
            zero_memory_response.message,
            "Rename preview:\n"
            "Source: work\n"
            "Target: archive\n"
            "Affected memories: 0\n"
            "Changes: ready",
        )
        self.assertEqual(zero_memory_response.memory_count, 0)
        self.assertEqual(failure.intent, "session_rename_preview")
        self.assertFalse(failure.success)

    def test_session_rename_help_preserves_the_exact_contract(self) -> None:
        response = self.composer.session_rename_help(self.request)

        self.assertEqual(
            response.message,
            "Rename session:\n"
            "rename session <source> -- <target>\n"
            "\n"
            "Preview:\n"
            "preview rename session <source> -- <target>\n"
            "\n"
            "Check target:\n"
            "check rename target <target>\n"
            "\n"
            "Example:\n"
            "rename session work -- archive",
        )
        self.assertFalse(response.message.endswith("\n"))
        self.assertEqual(response.intent, "session_rename_help")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_rename_candidates_preserve_the_exact_contract(self) -> None:
        response = self.composer.session_rename_candidates(
            self.request,
            [self._session("work"), self._session("archive")],
            "archive",
        )
        empty_response = self.composer.session_rename_candidates(
            self.request,
            [],
            "default",
        )

        self.assertEqual(
            response.message,
            "Renameable sessions:\nwork\narchive (active)",
        )
        self.assertEqual(response.intent, "session_rename_candidates")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)
        self.assertEqual(empty_response.message, "No renameable sessions.")
        self.assertEqual(empty_response.intent, "session_rename_candidates")
        self.assertTrue(empty_response.success)
        self.assertEqual(empty_response.memory_count, 0)

    def test_session_active_preserves_the_exact_contract(self) -> None:
        response = self.composer.session_active(self.request, self._session("work"))

        self.assertEqual(response.message, "Active session: work")
        self.assertEqual(response.intent, "session_active")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_help_preserves_the_exact_contract(self) -> None:
        response = self.composer.session_help(self.request)

        self.assertEqual(
            response.message,
            "Session commands:\n"
            "create session <session_id>\n"
            "list sessions\n"
            "use session <session_id>\n"
            "active session\n"
            "session overview\n"
            "session details <session_id>\n"
            "session recent <session_id>\n"
            "session activity <session_id>\n"
            "session search <session_id> <query>\n"
            "list renameable sessions\n"
            "check rename target <target>\n"
            "preview rename session <source> -- <target>\n"
            "rename session <source> -- <target>\n"
            "help rename session",
        )
        self.assertFalse(response.message.endswith("\n"))
        self.assertEqual(response.intent, "session_help")
        self.assertTrue(response.success)
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.request_id, self.request.request_id)

    def test_session_rename_target_check_preserves_the_exact_contract(self) -> None:
        available = self.composer.session_rename_target_check(
            self.request,
            "Work Archive",
            True,
        )
        unavailable = self.composer.session_rename_target_check(
            self.request,
            "archive",
            False,
        )
        failure = self.composer.session_rename_target_check_failure(
            self.request,
            "Session target ID must not be empty.",
        )

        self.assertEqual(
            available.message,
            "Session rename target available: Work Archive",
        )
        self.assertEqual(
            unavailable.message,
            "Session rename target unavailable: archive",
        )
        self.assertEqual(failure.message, "Session target ID must not be empty.")
        for response, success in (
            (available, True),
            (unavailable, True),
            (failure, False),
        ):
            self.assertEqual(response.intent, "session_rename_target_check")
            self.assertEqual(response.success, success)
            self.assertEqual(response.memory_count, 0)
            self.assertEqual(response.request_id, self.request.request_id)

    @staticmethod
    def _session(session_id: str) -> SessionRecord:
        return SessionRecord(
            session_id=session_id,
            created_at=datetime(2026, 8, 4, 15, 0, tzinfo=UTC),
        )


class KnowledgeLoadResponseComposerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.composer = ResponseComposer()
        self.request = BrainRequest(message="Load selected local knowledge source")

    def test_success_preserves_loaded_document_and_local_only_contract(self) -> None:
        document = KnowledgeDocumentReference(
            "source-1",
            "Project Notes",
            "C:/knowledge/project notes.md",
            DocumentType.MARKDOWN,
            2,
        )

        response = self.composer.knowledge_load_success(self.request, document)

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "knowledge_load")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.knowledge_documents, [document])
        self.assertEqual(
            response.message,
            "Local knowledge source loaded:\n"
            "Title: Project Notes\n"
            "Source: C:/knowledge/project notes.md\n"
            "Type: markdown\n"
            "Chunks: 2\n"
            "ID: source-1",
        )

    def test_failure_preserves_message_without_a_loaded_document(self) -> None:
        response = self.composer.knowledge_load_failure(
            self.request,
            "A local knowledge source path is required.",
        )

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "knowledge_load")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(response.knowledge_documents, [])
        self.assertEqual(response.message, "A local knowledge source path is required.")
