from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from core.Exceptions import MemoryError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.Embedding import Embedding
from memory.MemoryManager import MemoryManager
from memory.SemanticMemoryIndexBuilder import SemanticMemoryIndexBuilder
from memory.SemanticMemoryIndexRuntime import SemanticMemoryIndexRuntime
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class MappingEmbeddingProvider:
    def __init__(self, embeddings: dict[str, Embedding]) -> None:
        self._embeddings = embeddings
        self.should_fail = False
        self.calls: list[str] = []

    def embed(
        self,
        source_text: str,
        *,
        timeout_seconds: float | None = None,
    ) -> Embedding:
        self.calls.append(source_text)
        if self.should_fail:
            raise MemoryError("Embedding provider unavailable.")
        return self._embeddings[source_text]


class SemanticRecallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.session_manager = SessionManager(self.event_bus)
        self.response_composer = ResponseComposer()
        self.session_rename_service = SessionRenameTransactionService(
            session_manager=self.session_manager,
            memory_manager=self.memory_manager,
            event_bus=self.event_bus,
        )

    def _engine(
        self,
        runtime: SemanticMemoryIndexRuntime | None = None,
    ) -> CognitiveEngine:
        return CognitiveEngine(
            KnowledgeEngine(),
            self.memory_manager,
            Planner(),
            self.event_bus,
            self.response_composer,
            self.session_manager,
            self.session_rename_service,
            semantic_memory_index_runtime=runtime,
        )

    def _runtime(
        self,
        embeddings: dict[str, Embedding],
    ) -> tuple[SemanticMemoryIndexRuntime, MappingEmbeddingProvider]:
        provider = MappingEmbeddingProvider(embeddings)
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        runtime.refresh(self.memory_manager)
        return runtime, provider

    def test_semantic_recall_returns_scored_matching_conversation_records(self) -> None:
        content = "User: I enjoy felines\nHypatia: Noted."
        record = self.memory_manager.add(
            content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        runtime, provider = self._runtime(
            {content: Embedding((1, 0)), "cats": Embedding((1, 0))}
        )
        memory_count = self.memory_manager.count()

        response = self._engine(runtime).process(
            BrainRequest(message="semantic recall cats", request_id="request-1")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "semantic_recall")
        self.assertEqual(response.request_id, "request-1")
        self.assertEqual(response.memory_count, 1)
        self.assertIn("Semantic recall (semantic):", response.message)
        self.assertIn("[similarity: 1.000]", response.message)
        self.assertIn(record.content, response.message)
        self.assertEqual(provider.calls, [content, "cats"])
        self.assertEqual(self.memory_manager.count(), memory_count)

    def test_semantic_recall_fuses_current_session_semantic_and_lexical_results(
        self,
    ) -> None:
        semantic_only = "User: I enjoy felines\nHypatia: Noted."
        shared = "User: Cats are companion animals\nHypatia: Noted."
        lexical_only = "User: Cats have different sleep patterns\nHypatia: Noted."
        other_session = "User: Cats are private to another session\nHypatia: Noted."
        self.memory_manager.add(
            semantic_only,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            shared,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.memory_manager.add(
            lexical_only,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.session_manager.create("other")
        self.memory_manager.add(
            other_session,
            metadata={"session_id": "other"},
            tags={"brain", "conversation"},
        )
        runtime, _ = self._runtime(
            {
                semantic_only: Embedding((1, 0)),
                shared: Embedding((0.9, 0.1)),
                lexical_only: Embedding((0.1, 0.9)),
                other_session: Embedding((1, 0)),
                "cats": Embedding((1, 0)),
            }
        )

        response = self._engine(runtime).process(
            BrainRequest(message="semantic recall cats")
        )

        self.assertTrue(response.success)
        self.assertIn("Semantic recall (hybrid):", response.message)
        self.assertIn("[rank score:", response.message)
        self.assertNotIn("[similarity:", response.message)
        self.assertLess(
            response.message.index(shared),
            response.message.index(semantic_only),
        )
        self.assertLess(
            response.message.index(lexical_only),
            response.message.index(semantic_only),
        )
        self.assertNotIn(other_session, response.message)
        self.assertEqual(response.memory_count, 3)

    def test_missing_runtime_uses_deterministic_lexical_fallback(self) -> None:
        record = self.memory_manager.add(
            "User: I like cats\nHypatia: Noted.",
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )

        response = self._engine().process(BrainRequest(message="semantic recall cats"))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "semantic_recall")
        self.assertIn("Semantic recall (lexical fallback):", response.message)
        self.assertIn(record.content, response.message)
        self.assertNotIn("[similarity:", response.message)

    def test_semantic_recall_status_reports_a_disabled_runtime_without_mutation(
        self,
    ) -> None:
        memory_count = self.memory_manager.count()

        response = self._engine().process(
            BrainRequest(message="semantic recall status", request_id="request-1")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "semantic_recall_status")
        self.assertEqual(response.request_id, "request-1")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Semantic recall status:\n"
            "Runtime: disabled\n"
            "Indexed memory records: unavailable\n"
            "Embedding dimension: unavailable\n"
            "Last rebuild: unavailable\n"
            "Last incremental update: unavailable",
        )
        self.assertEqual(self.memory_manager.count(), memory_count)

    def test_semantic_recall_status_and_retry_report_a_stopped_runtime(self) -> None:
        runtime, _ = self._runtime({})
        runtime.shutdown()

        status = self._engine(runtime).process(
            BrainRequest(message="semantic recall status")
        )
        retry = self._engine(runtime).process(
            BrainRequest(message="semantic recall retry")
        )

        self.assertIn("Runtime: stopped", status.message)
        self.assertFalse(retry.success)
        self.assertEqual(retry.message, "Semantic recall runtime is stopped.")

    def test_semantic_recall_status_reports_index_health_without_query_embedding(
        self,
    ) -> None:
        content = "Indexed conversation"
        self.memory_manager.add(
            content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        runtime, provider = self._runtime({content: Embedding((1, 0))})
        calls_before_status = list(provider.calls)
        memory_count = self.memory_manager.count()

        response = self._engine(runtime).process(
            BrainRequest(message="semantic recall status")
        )

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "semantic_recall_status")
        self.assertEqual(response.memory_count, 0)
        self.assertEqual(
            response.message,
            "Semantic recall status:\n"
            "Runtime: ready\n"
            "Indexed memory records: 1\n"
            "Embedding dimension: 2\n"
            "Last rebuild: healthy\n"
            "Last incremental update: healthy",
        )
        self.assertEqual(provider.calls, calls_before_status)
        self.assertEqual(self.memory_manager.count(), memory_count)

    def test_semantic_recall_status_reports_refreshing_with_last_index(self) -> None:
        content = "Indexed conversation"
        self.memory_manager.add(
            content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        runtime, provider = self._runtime({content: Embedding((1, 0))})
        calls_before_status = list(provider.calls)

        with patch.object(runtime, "is_rebuilding", return_value=True):
            response = self._engine(runtime).process(
                BrainRequest(message="semantic recall status")
            )

        self.assertIn("Runtime: refreshing", response.message)
        self.assertIn("Indexed memory records: 1", response.message)
        self.assertIn("Embedding dimension: 2", response.message)
        self.assertIn("Last rebuild: in progress", response.message)
        self.assertEqual(provider.calls, calls_before_status)

    def test_semantic_recall_status_marks_an_empty_ready_index_as_unestablished(
        self,
    ) -> None:
        runtime, provider = self._runtime({})
        calls_before_status = list(provider.calls)

        response = self._engine(runtime).process(
            BrainRequest(message="semantic recall status")
        )

        self.assertEqual(
            response.message,
            "Semantic recall status:\n"
            "Runtime: ready\n"
            "Indexed memory records: 0\n"
            "Embedding dimension: not established\n"
            "Last rebuild: healthy\n"
            "Last incremental update: healthy",
        )
        self.assertEqual(provider.calls, calls_before_status)

    def test_semantic_recall_status_exposes_only_the_safe_incremental_error(
        self,
    ) -> None:
        content = "Indexed conversation"
        self.memory_manager.add(
            content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        runtime, provider = self._runtime({content: Embedding((1, 0))})
        runtime.attach(self.event_bus)
        provider.should_fail = True
        self.memory_manager.add("Update that cannot be embedded")

        response = self._engine(runtime).process(
            BrainRequest(message="semantic recall status")
        )

        self.assertTrue(response.success)
        self.assertIn("Runtime: ready", response.message)
        self.assertIn(
            "Last incremental update: Semantic index update failed.",
            response.message,
        )
        self.assertNotIn("Embedding provider unavailable.", response.message)

    def test_semantic_recall_status_exposes_safe_unavailable_rebuild_state(
        self,
    ) -> None:
        content = "Indexed conversation"
        self.memory_manager.add(
            content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        provider = MappingEmbeddingProvider({content: Embedding((1, 0))})
        provider.should_fail = True
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        with self.assertRaisesRegex(MemoryError, "provider unavailable"):
            runtime.refresh(self.memory_manager)

        response = self._engine(runtime).process(
            BrainRequest(message="semantic recall status")
        )

        self.assertEqual(
            response.message,
            "Semantic recall status:\n"
            "Runtime: unavailable\n"
            "Indexed memory records: unavailable\n"
            "Embedding dimension: unavailable\n"
            "Last rebuild: Semantic index rebuild failed.\n"
            "Last incremental update: unavailable",
        )
        self.assertNotIn("provider unavailable", response.message)

    def test_semantic_recall_retry_reports_disabled_runtime(self) -> None:
        response = self._engine().process(
            BrainRequest(message="semantic recall retry", request_id="request-1")
        )

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "semantic_recall_retry")
        self.assertEqual(response.request_id, "request-1")
        self.assertEqual(response.message, "Semantic recall runtime is disabled.")

    def test_semantic_recall_retry_recovers_unavailable_runtime(self) -> None:
        content = "Indexed conversation"
        self.memory_manager.add(
            content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        provider = MappingEmbeddingProvider({content: Embedding((1, 0))})
        provider.should_fail = True
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        with self.assertRaises(MemoryError):
            runtime.refresh(self.memory_manager)
        provider.should_fail = False

        response = self._engine(runtime).process(
            BrainRequest(message="semantic recall retry", request_id="request-1")
        )
        self.assertTrue(runtime.wait_for_idle(1))

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "semantic_recall_retry")
        self.assertEqual(response.request_id, "request-1")
        self.assertEqual(
            response.message,
            "Semantic recall rebuild started in the background.",
        )
        current_index = runtime.current()
        assert current_index is not None
        self.assertEqual(current_index.count(), 1)
        self.assertIsNone(runtime.last_rebuild_error())
        self.assertEqual(provider.calls, [content, content])

    def test_failed_semantic_retry_preserves_last_index_and_hides_provider_error(
        self,
    ) -> None:
        content = "Indexed conversation"
        self.memory_manager.add(
            content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        runtime, provider = self._runtime({content: Embedding((1, 0))})
        stable_index = runtime.current()
        provider.should_fail = True

        response = self._engine(runtime).process(
            BrainRequest(message="semantic recall retry")
        )
        self.assertTrue(runtime.wait_for_idle(1))
        status = self._engine(runtime).process(
            BrainRequest(message="semantic recall status")
        )

        self.assertTrue(response.success)
        self.assertEqual(
            response.message,
            "Semantic recall rebuild started in the background.",
        )
        self.assertIs(runtime.current(), stable_index)
        self.assertEqual(
            runtime.last_rebuild_error(),
            "Semantic index rebuild failed.",
        )
        self.assertNotIn("Embedding provider unavailable.", response.message)
        self.assertIn("Runtime: ready", status.message)
        self.assertIn(
            "Last rebuild: Semantic index rebuild failed.",
            status.message,
        )
        self.assertNotIn("Embedding provider unavailable.", status.message)

    def test_provider_failure_uses_deterministic_lexical_fallback(self) -> None:
        content = "User: I like cats\nHypatia: Noted."
        record = self.memory_manager.add(
            content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        runtime, provider = self._runtime(
            {content: Embedding((1, 0)), "cats": Embedding((1, 0))}
        )
        provider.should_fail = True

        response = self._engine(runtime).process(
            BrainRequest(message="semantic recall cats")
        )

        self.assertTrue(response.success)
        self.assertIn("Semantic recall (lexical fallback):", response.message)
        self.assertIn(record.content, response.message)

    def test_oversized_semantic_query_skips_provider_and_uses_lexical_fallback(
        self,
    ) -> None:
        content = "User: I like cats\nHypatia: Noted."
        record = self.memory_manager.add(
            content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        runtime, provider = self._runtime({content: Embedding((1, 0))})

        with patch(
            "memory.EmbeddingProvider.MAX_EMBEDDING_SOURCE_TEXT_CHARACTERS",
            3,
        ):
            response = self._engine(runtime).process(
                BrainRequest(message="semantic recall cats")
            )

        self.assertTrue(response.success)
        self.assertIn("Semantic recall (lexical fallback):", response.message)
        self.assertIn(record.content, response.message)
        self.assertEqual(provider.calls, [content])

    def test_semantic_recall_filters_records_to_the_resolved_session(self) -> None:
        default_content = "Default conversation"
        other_content = "Other conversation"
        self.memory_manager.add(
            default_content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        self.session_manager.create("other")
        self.memory_manager.add(
            other_content,
            metadata={"session_id": "other"},
            tags={"brain", "conversation"},
        )
        runtime, _ = self._runtime(
            {
                default_content: Embedding((1, 0)),
                other_content: Embedding((1, 0)),
                "query": Embedding((1, 0)),
            }
        )

        response = self._engine(runtime).process(
            BrainRequest(
                message="semantic recall query", metadata={"session_id": "default"}
            )
        )

        self.assertIn(default_content, response.message)
        self.assertNotIn(other_content, response.message)
        self.assertEqual(response.memory_count, 1)

    def test_semantic_recall_uses_current_session_metadata_after_session_rename(
        self,
    ) -> None:
        content = "Conversation that will move sessions"
        self.session_manager.create("original")
        self.memory_manager.add(
            content,
            metadata={"session_id": "original"},
            tags={"brain", "conversation"},
        )
        runtime, _ = self._runtime(
            {content: Embedding((1, 0)), "query": Embedding((1, 0))}
        )

        self.session_rename_service.rename("original", "renamed")
        response = self._engine(runtime).process(
            BrainRequest(
                message="semantic recall query",
                metadata={"session_id": "renamed"},
            )
        )

        self.assertTrue(response.success)
        self.assertIn("Semantic recall (semantic):", response.message)
        self.assertIn(content, response.message)
        self.assertEqual(response.memory_count, 1)

    def test_empty_semantic_recall_fails_before_query_embedding(self) -> None:
        content = "Stored conversation"
        self.memory_manager.add(
            content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        runtime, provider = self._runtime({content: Embedding((1, 0))})

        response = self._engine(runtime).process(
            BrainRequest(message="semantic recall")
        )

        self.assertFalse(response.success)
        self.assertEqual(response.intent, "semantic_recall")
        self.assertEqual(response.message, "A semantic recall query is required.")
        self.assertEqual(provider.calls, [content])

    def test_existing_recall_does_not_call_semantic_runtime(self) -> None:
        content = "User: I like cats\nHypatia: Noted."
        self.memory_manager.add(
            content,
            metadata={"session_id": "default"},
            tags={"brain", "conversation"},
        )
        runtime, provider = self._runtime({content: Embedding((1, 0))})

        response = self._engine(runtime).process(BrainRequest(message="recall cats"))

        self.assertEqual(response.intent, "recall")
        self.assertIn(content, response.message)
        self.assertEqual(provider.calls, [content])


if __name__ == "__main__":
    unittest.main()
