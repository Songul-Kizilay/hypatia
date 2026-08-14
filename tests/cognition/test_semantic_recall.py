from __future__ import annotations

import sys
import unittest
from pathlib import Path

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

    def embed(self, source_text: str) -> Embedding:
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
