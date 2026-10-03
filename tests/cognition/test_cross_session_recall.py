"""`CognitiveEngine.process` offers bounded, labeled reference context from a
genuinely different session only when the natural-language recall detector
fires -- never silently, never as a rewrite of same-session history.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from core.Exceptions import MemoryError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from llm.LLMConversationMessage import LLMConversationMessage
from memory.Embedding import Embedding
from memory.MemoryManager import MemoryManager
from memory.SemanticMemoryIndexBuilder import SemanticMemoryIndexBuilder
from memory.SemanticMemoryIndexRuntime import SemanticMemoryIndexRuntime
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class MappingEmbeddingProvider:
    """Deterministic stand-in embedding provider keyed by exact source text."""

    def __init__(self, embeddings: dict[str, Embedding]) -> None:
        self._embeddings = embeddings
        self.calls: list[str] = []

    def embed(
        self,
        source_text: str,
        *,
        timeout_seconds: float | None = None,
    ) -> Embedding:
        self.calls.append(source_text)
        try:
            return self._embeddings[source_text]
        except KeyError:
            raise MemoryError(f"No embedding fixture for: {source_text!r}") from None


class QueuedLLMProvider:
    """Records every call and returns one canned reply per call, in order."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, tuple[LLMConversationMessage, ...], str | None]] = (
            []
        )

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
    ) -> str:
        self.calls.append((prompt, history, system_instruction))
        return self._responses.pop(0)


class CrossSessionRecallTests(unittest.TestCase):
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
        llm_provider: QueuedLLMProvider,
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
            llm_provider=llm_provider,
            semantic_memory_index_runtime=runtime,
        )

    def test_recall_phrase_quotes_the_other_sessions_turn_with_its_session_id(
        self,
    ) -> None:
        lesson_question = "What is a UNION-based SQL injection?"
        lesson_answer = (
            "It combines two queries with UNION SELECT so an attacker can "
            "read data from other tables."
        )
        lesson_turn_content = f"User: {lesson_question}\nHypatia: {lesson_answer}"
        recall_message = "Let's continue the SQL injection lesson."
        recall_answer = "Sure, picking back up where we left off."

        provider = MappingEmbeddingProvider(
            {
                lesson_turn_content: Embedding((1, 0)),
                recall_message: Embedding((1, 0)),
            }
        )
        runtime = SemanticMemoryIndexRuntime(SemanticMemoryIndexBuilder(provider))
        llm_provider = QueuedLLMProvider([lesson_answer, recall_answer])
        engine = self._engine(llm_provider, runtime)
        self.session_manager.create("sql-injection-lesson")
        self.session_manager.create("new-session")

        lesson_response = engine.process(
            BrainRequest(
                message=lesson_question,
                metadata={"session_id": "sql-injection-lesson"},
            )
        )
        self.assertTrue(lesson_response.success)
        self.assertEqual(lesson_response.message, lesson_answer)
        runtime.refresh(self.memory_manager)

        recall_response = engine.process(
            BrainRequest(
                message=recall_message,
                metadata={"session_id": "new-session"},
            )
        )

        self.assertTrue(recall_response.success)
        self.assertEqual(len(llm_provider.calls), 2)
        recall_prompt = llm_provider.calls[1][0]
        self.assertIn("[session: sql-injection-lesson]", recall_prompt)
        self.assertIn(lesson_question, recall_prompt)
        self.assertIn(lesson_answer, recall_prompt)
        self.assertIn("Cross-session recall context", recall_prompt)
        self.assertIn(recall_message, recall_prompt)
        # The fixture deliberately omits attribution from generated prose.
        # The application must still show the actual source to the user.
        self.assertIn(recall_answer, recall_response.message)
        self.assertIn('"sql-injection-lesson"', recall_response.message)
        self.assertIn("Source sessions", recall_response.message)

    def test_recall_phrase_with_nothing_found_states_it_plainly(self) -> None:
        recall_message = "Where did we leave off last time?"
        reply = "I could not find anything relevant from another session."
        llm_provider = QueuedLLMProvider([reply])
        engine = self._engine(llm_provider)

        response = engine.process(BrainRequest(message=recall_message))

        self.assertTrue(response.success)
        self.assertEqual(len(llm_provider.calls), 0)
        self.assertIn("could not find", response.message)
        self.assertNotIn("Source sessions", response.message)

    def test_the_most_recent_matching_turn_surfaces_before_an_older_one(self) -> None:
        """Two relevant turns in the same other session: newest must lead.

        Closes a coverage gap: `_cross_session_recall_records` sorts by
        recency before truncating, but with only one candidate turn no test
        could tell a reverse-sort regression from a non-regression. This
        test fails if the sort direction is flipped.
        """
        recall_query = "Let's continue the SQL injection lesson."
        old_turn_message = "SQL injection (first attempt, blind SQLi)"
        new_turn_message = "SQL injection (second attempt, union-based)"
        llm_provider = QueuedLLMProvider(
            ["First attempt notes.", "Second attempt notes.", "Continuing now."]
        )
        engine = self._engine(llm_provider)
        self.session_manager.create("sql-injection-lesson")
        self.session_manager.create("asker-session")

        engine.process(
            BrainRequest(
                message=old_turn_message,
                metadata={"session_id": "sql-injection-lesson"},
            )
        )
        time.sleep(0.01)
        engine.process(
            BrainRequest(
                message=new_turn_message,
                metadata={"session_id": "sql-injection-lesson"},
            )
        )

        response = engine.process(
            BrainRequest(
                message=recall_query,
                metadata={"session_id": "asker-session"},
            )
        )

        self.assertTrue(response.success)
        prompt = llm_provider.calls[-1][0]
        self.assertIn(new_turn_message, prompt)
        self.assertIn(old_turn_message, prompt)
        self.assertLess(
            prompt.index(new_turn_message),
            prompt.index(old_turn_message),
        )

    def test_the_askers_own_session_is_excluded_even_when_its_content_matches(
        self,
    ) -> None:
        """A matching turn already in the asker's own session must not leak

        into the cross-session block labeled as if it came from elsewhere.
        Closes a coverage gap: every existing fixture left the asking
        session empty, so the inverted session filter was never actually
        exercised against a same-session false positive.
        """
        recall_query = "Let's continue the SQL injection lesson."
        other_session_message = "SQL injection (the real other-session lesson)"
        own_session_prior_message = "SQL injection (asked earlier in this very session)"
        llm_provider = QueuedLLMProvider(
            ["Noted in the other session.", "Noted in the asking session.", "Hi."]
        )
        engine = self._engine(llm_provider)
        self.session_manager.create("sql-injection-lesson")
        self.session_manager.create("asker-session")

        engine.process(
            BrainRequest(
                message=other_session_message,
                metadata={"session_id": "sql-injection-lesson"},
            )
        )
        engine.process(
            BrainRequest(
                message=own_session_prior_message,
                metadata={"session_id": "asker-session"},
            )
        )

        response = engine.process(
            BrainRequest(
                message=recall_query,
                metadata={"session_id": "asker-session"},
            )
        )

        self.assertTrue(response.success)
        prompt = llm_provider.calls[-1][0]
        self.assertIn("[session: sql-injection-lesson]", prompt)
        self.assertIn(other_session_message, prompt)
        self.assertNotIn(own_session_prior_message, prompt)
        self.assertNotIn("[session: asker-session]", prompt)

    def test_nothing_found_is_plain_even_with_unrelated_content_elsewhere(
        self,
    ) -> None:
        """Another session has real content, but none of it matches the

        query: the explicit not-found note must still appear, and the
        unrelated content must never be quoted. Closes a coverage gap: the
        original not-found test had zero other sessions and zero records,
        never exercising the "records existed but none matched" branch of
        `_cross_session_recall_records`.
        """
        unrelated_message = "What is reflected XSS and how do I test for it?"
        recall_message = "Where did we leave off last time?"
        llm_provider = QueuedLLMProvider(
            [
                "Reflected XSS echoes unsanitized input back into the page.",
                "I could not find anything relevant from another session.",
            ]
        )
        engine = self._engine(llm_provider)
        self.session_manager.create("xss-session")

        engine.process(
            BrainRequest(
                message=unrelated_message,
                metadata={"session_id": "xss-session"},
            )
        )

        response = engine.process(BrainRequest(message=recall_message))

        self.assertTrue(response.success)
        self.assertEqual(len(llm_provider.calls), 1)
        self.assertIn("could not find", response.message)
        self.assertNotIn(unrelated_message, response.message)

    def test_ordinary_message_has_no_cross_session_block_at_all(self) -> None:
        message = "What is reflected XSS?"
        reply = "It reflects unsanitized input back into the page."
        llm_provider = QueuedLLMProvider([reply])
        engine = self._engine(llm_provider)

        response = engine.process(BrainRequest(message=message))

        self.assertTrue(response.success)
        self.assertEqual(len(llm_provider.calls), 1)
        prompt, _history, _system = llm_provider.calls[0]
        self.assertEqual(prompt, message)
        self.assertNotIn("Cross-session recall", prompt)
        self.assertNotIn("Source sessions", response.message)

    def test_no_match_cannot_be_replaced_by_a_fabricated_model_memory(self) -> None:
        provider = QueuedLLMProvider(["You independently mastered SQL last time."])
        response = self._engine(provider).process(
            BrainRequest(message="Let's continue the SQL injection lesson.")
        )
        self.assertTrue(response.success)
        self.assertIn("could not find", response.message)
        self.assertNotIn("mastered", response.message)
        self.assertEqual(provider.calls, [])

    def test_recalled_answer_is_not_extracted_or_reused_as_new_evidence(self) -> None:
        provider = QueuedLLMProvider(
            ["SQL injection uses UNION.", "An assisted answer."]
        )
        engine = self._engine(provider)
        self.session_manager.create("lesson")
        engine.process(
            BrainRequest(
                message="Explain SQL injection", metadata={"session_id": "lesson"}
            )
        )
        extractor = Mock()
        engine._learned_memory_candidate_extractor = extractor
        engine.process(BrainRequest(message="Let's continue the SQL injection lesson."))
        extractor.extract.assert_not_called()
        retrieved = engine._cross_session_recall_records(
            "Let's continue the SQL injection lesson.", "lesson"
        )
        self.assertEqual(retrieved, [])

    def test_missing_provenance_and_nonconversation_records_are_excluded(self) -> None:
        for metadata, tags in (
            ({}, {"brain", "conversation"}),
            ({"session_id": "elsewhere"}, {"learned"}),
            ({"session_id": 123}, {"brain", "conversation"}),
        ):
            self.memory_manager.add("SQL injection", metadata=metadata, tags=tags)
        self.assertEqual(
            self._engine(QueuedLLMProvider([]))._cross_session_recall_records(
                "Let's continue the SQL injection lesson.", "default"
            ),
            [],
        )

    def test_semantic_relevance_precedes_recency_and_zero_similarity_is_excluded(
        self,
    ) -> None:
        from memory.SemanticMemoryMatch import SemanticMemoryMatch

        records = []
        for number in range(7):
            records.append(
                self.memory_manager.add(
                    f"topic {number}",
                    tags={"brain", "conversation"},
                    metadata={
                        "session_id": "other",
                        "user_message": f"topic {number}",
                        "assistant_message": "reply",
                    },
                )
            )
        runtime = Mock()
        runtime.search.return_value = tuple(
            SemanticMemoryMatch(record.memory_id, 1.0 - index * 0.07)
            for index, record in enumerate(records[:6])
        ) + (
            SemanticMemoryMatch(records[6].memory_id, 0.0),
        )
        result = self._engine(
            QueuedLLMProvider([]), runtime
        )._cross_session_recall_records(
            "Let's continue the SQL injection lesson.", "default"
        )
        self.assertEqual(
            [record.memory_id for record, _ in result],
            [r.memory_id for r in records[:5]],
        )

    def test_named_session_limits_sources_even_without_id_in_turn_text(self) -> None:
        self.session_manager.create("lesson-1")
        for session in ("lesson-1", "unrelated"):
            self.memory_manager.add(
                "SQL injection",
                tags={"brain", "conversation"},
                metadata={
                    "session_id": session,
                    "user_message": "SQL injection",
                    "assistant_message": "hint",
                },
            )
        result = self._engine(QueuedLLMProvider([]))._cross_session_recall_records(
            "Let's continue 'lesson-1'.", "default"
        )
        self.assertEqual([r.metadata["session_id"] for r, _ in result], ["lesson-1"])

    def test_storage_failure_does_not_fabricate_a_recalled_answer(self) -> None:
        engine = self._engine(QueuedLLMProvider(["An invented old answer."]))
        engine._cross_session_recall_records = Mock(
            side_effect=MemoryError("unavailable")
        )
        response = engine.process(
            BrainRequest(message="Let's continue the SQL injection lesson.")
        )
        self.assertTrue(response.success)
        self.assertIn("recall is unavailable", response.message)
        self.assertNotIn("invented", response.message)


if __name__ == "__main__":
    unittest.main()
