"""BSCP-style regression: assisted answers never become independent mastery.

Exercises the real `CognitiveEngine.process` path with a controllable LLM
provider and a controllable candidate extractor standing in for what a real
LLM-backed extractor might naively propose -- the point of this suite is
that `AssistedLearningGuard`'s deterministic filter catches a bad proposal
regardless of what the extractor returns, not that the extractor itself
behaves. Synthetic conversation data only; nothing here touches saved user
data.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from llm.LLMConversationMessage import LLMConversationMessage
from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCandidate import (
    LearnedMemoryCandidate,
    LearnedMemoryCandidateBatch,
)
from memory.LearnedMemoryStore import load_learned_memories
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

HINT_REPLY = (
    "Hint: you can use the UNION keyword to execute an additional SELECT "
    "statement and append its results to the original query, for example "
    "by reading from the users table instead."
)


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


class QueuedCandidateExtractor:
    """Returns caller-supplied batches in order; records the context it saw."""

    def __init__(self, batches: list[LearnedMemoryCandidateBatch]) -> None:
        self._batches = list(batches)
        self.calls: list[str] = []
        self.context_calls: list[str] = []

    def extract(
        self,
        source_text: str,
        *,
        recent_session_context: str = "",
    ) -> LearnedMemoryCandidateBatch:
        self.calls.append(source_text)
        self.context_calls.append(recent_session_context)
        return self._batches.pop(0)


def mastery_batch(
    message: str, value: str, key: str = "sql_injection"
) -> LearnedMemoryCandidateBatch:
    return LearnedMemoryCandidateBatch(
        source_text=message,
        candidates=(
            LearnedMemoryCandidate(
                memory=LearnedMemory(kind="self_fact", key=key, value=value),
                source_text=message,
            ),
        ),
    )


def empty_batch(message: str) -> LearnedMemoryCandidateBatch:
    return LearnedMemoryCandidateBatch(source_text=message, candidates=())


def preference_batch(
    message: str, value: str = "Python"
) -> LearnedMemoryCandidateBatch:
    return LearnedMemoryCandidateBatch(
        source_text=message,
        candidates=(
            LearnedMemoryCandidate(
                memory=LearnedMemory(
                    kind="preference", key="preferred_language", value=value
                ),
                source_text=message,
            ),
        ),
    )


class SameSessionAssistedLearningTests(unittest.TestCase):
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
        extractor: QueuedCandidateExtractor,
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
            learned_memory_candidate_extractor=extractor,
        )

    def _process(self, engine: CognitiveEngine, message: str, session_id: str):
        return engine.process(
            BrainRequest(message=message, metadata={"session_id": session_id})
        )

    def test_bscp_sequence_hint_then_independence_claim_is_not_recorded_as_mastery(
        self,
    ) -> None:
        """The exact required scenario: hint, then a claimed-independent answer."""
        self.session_manager.create("bscp-sqli")
        llm_provider = QueuedLLMProvider([HINT_REPLY, "Correct! Well done."])
        extractor = QueuedCandidateExtractor(
            [
                empty_batch("I don't know, can you give me a hint?"),
                mastery_batch(
                    "My answer is UNION SELECT username, password FROM "
                    "users. I solved it independently.",
                    "User independently solved SQL injection using UNION " "SELECT.",
                ),
            ]
        )
        engine = self._engine(llm_provider, extractor)

        hint_response = self._process(
            engine, "I don't know, can you give me a hint?", "bscp-sqli"
        )
        self.assertTrue(hint_response.success)
        self.assertEqual(hint_response.message, HINT_REPLY)

        claim_response = self._process(
            engine,
            "My answer is UNION SELECT username, password FROM users. "
            "I solved it independently.",
            "bscp-sqli",
        )

        self.assertTrue(claim_response.success)
        # Hypatia still acknowledges the correct answer normally.
        self.assertEqual(claim_response.message, "Correct! Well done.")
        # But nothing records it as independently demonstrated mastery.
        learned = load_learned_memories(self.memory_manager)
        self.assertFalse(any(memory.kind == "self_fact" for memory in learned))
        # The extractor was still given the hint as context, proving the
        # wiring threads it through rather than the filter alone saving us.
        self.assertIn("UNION keyword", extractor.context_calls[-1])

    def test_a_new_unhinted_question_is_not_misclassified_as_assisted(self) -> None:
        """Required negative scenario: an unaided answer must still be recorded."""
        self.session_manager.create("bscp-xss")
        llm_provider = QueuedLLMProvider(["Exactly right."])
        extractor = QueuedCandidateExtractor(
            [
                mastery_batch(
                    "Reflected XSS happens when unsanitized input is "
                    "echoed back in the response, and I worked this out "
                    "myself.",
                    "User independently explained reflected XSS.",
                    key="xss_understanding",
                )
            ]
        )
        engine = self._engine(llm_provider, extractor)

        response = self._process(
            engine,
            "Reflected XSS happens when unsanitized input is echoed back "
            "in the response, and I worked this out myself.",
            "bscp-xss",
        )

        self.assertTrue(response.success)
        learned = load_learned_memories(self.memory_manager)
        self.assertTrue(
            any(
                memory.kind == "self_fact" and memory.key == "xss_understanding"
                for memory in learned
            )
        )

    def test_explicit_disclosure_english_blocks_the_mastery_claim(self) -> None:
        self.session_manager.create("bscp-disclosure-en")
        llm_provider = QueuedLLMProvider(["Good, that's correct."])
        extractor = QueuedCandidateExtractor(
            [
                mastery_batch(
                    "ChatGPT helped me with this answer: UNION SELECT.",
                    "User understands UNION-based SQL injection.",
                )
            ]
        )
        engine = self._engine(llm_provider, extractor)

        response = self._process(
            engine,
            "ChatGPT helped me with this answer: UNION SELECT.",
            "bscp-disclosure-en",
        )

        self.assertTrue(response.success)
        learned = load_learned_memories(self.memory_manager)
        self.assertFalse(any(memory.kind == "self_fact" for memory in learned))

    def test_explicit_disclosure_turkish_blocks_the_mastery_claim(self) -> None:
        self.session_manager.create("bscp-disclosure-tr")
        llm_provider = QueuedLLMProvider(["Doğru, aferin."])
        extractor = QueuedCandidateExtractor(
            [
                mastery_batch(
                    "Bu soruda ChatGPT bana yardım etti: UNION SELECT.",
                    "Kullanıcı SQL injection'ı bağımsız olarak çözdü.",
                )
            ]
        )
        engine = self._engine(llm_provider, extractor)

        response = self._process(
            engine,
            "Bu soruda ChatGPT bana yardım etti: UNION SELECT.",
            "bscp-disclosure-tr",
        )

        self.assertTrue(response.success)
        learned = load_learned_memories(self.memory_manager)
        self.assertFalse(any(memory.kind == "self_fact" for memory in learned))

    def test_bare_agreement_with_an_explanation_is_not_recorded_as_mastery(
        self,
    ) -> None:
        """Requirement: agreement alone is never evidence of independent mastery."""
        self.session_manager.create("bscp-agreement")
        llm_provider = QueuedLLMProvider([HINT_REPLY, "Glad that clears it up."])
        extractor = QueuedCandidateExtractor(
            [
                empty_batch("How does UNION-based injection work?"),
                mastery_batch(
                    "I understand now.",
                    "User understands UNION-based SQL injection.",
                ),
            ]
        )
        engine = self._engine(llm_provider, extractor)

        self._process(engine, "How does UNION-based injection work?", "bscp-agreement")
        response = self._process(engine, "I understand now.", "bscp-agreement")

        self.assertTrue(response.success)
        learned = load_learned_memories(self.memory_manager)
        self.assertFalse(any(memory.kind == "self_fact" for memory in learned))

    def test_ordinary_preference_is_preserved_even_right_after_a_hint(self) -> None:
        """Requirement: ordinary legitimate memories are never touched by this."""
        self.session_manager.create("bscp-preference")
        llm_provider = QueuedLLMProvider([HINT_REPLY, "Noted!"])
        extractor = QueuedCandidateExtractor(
            [
                empty_batch("Give me a hint please."),
                preference_batch("By the way, I prefer Python for scripting exploits."),
            ]
        )
        engine = self._engine(llm_provider, extractor)

        self._process(engine, "Give me a hint please.", "bscp-preference")
        response = self._process(
            engine,
            "By the way, I prefer Python for scripting exploits.",
            "bscp-preference",
        )

        self.assertTrue(response.success)
        learned = load_learned_memories(self.memory_manager)
        self.assertTrue(
            any(
                memory.kind == "preference" and memory.value == "Python"
                for memory in learned
            )
        )

    def test_verbatim_restatement_of_the_hint_is_not_recorded_as_mastery(
        self,
    ) -> None:
        """A claim echoing the hint's own wording is caught deterministically."""
        self.session_manager.create("bscp-restate")
        llm_provider = QueuedLLMProvider([HINT_REPLY, "That's right."])
        extractor = QueuedCandidateExtractor(
            [
                empty_batch("Give me a hint."),
                mastery_batch(
                    "My answer is UNION SELECT.",
                    "User independently figured out: you can use the UNION "
                    "keyword to execute an additional SELECT statement and "
                    "append its results to the original query.",
                ),
            ]
        )
        engine = self._engine(llm_provider, extractor)

        self._process(engine, "Give me a hint.", "bscp-restate")
        response = self._process(engine, "My answer is UNION SELECT.", "bscp-restate")

        self.assertTrue(response.success)
        learned = load_learned_memories(self.memory_manager)
        self.assertFalse(any(memory.kind == "self_fact" for memory in learned))

    def test_filtering_does_not_happen_during_cross_session_recall(self) -> None:
        """Recall already skips extraction entirely; this guard adds nothing there."""
        self.session_manager.create("lesson-source")
        llm_provider = QueuedLLMProvider(["SQL injection uses UNION.", "Continuing."])
        extractor = QueuedCandidateExtractor([empty_batch("Explain SQL injection")])
        engine = self._engine(llm_provider, extractor)

        self._process(engine, "Explain SQL injection", "lesson-source")
        self._process(engine, "Let's continue the SQL injection lesson.", "new-session")

        # Only one extraction call: the recall turn never reaches the extractor.
        self.assertEqual(len(extractor.calls), 1)

    def test_a_prior_recall_turn_is_excluded_from_later_assistance_context(
        self,
    ) -> None:
        """A same-session recall exchange must not leak into assistance context.

        A recall reply quotes a *different* session's material; it is not
        something this session's own conversation actually established, so
        it must never be offered to the extractor as "Hypatia already
        explained this" evidence for a later, unrelated turn.
        """
        self.session_manager.create("bscp-sqli")
        llm_provider = QueuedLLMProvider(["Here is the UNION technique."])
        extractor = QueuedCandidateExtractor(
            [empty_batch("My answer uses UNION SELECT.")]
        )
        engine = self._engine(llm_provider, extractor)

        # Turn 1: a recall request in this same session. No other session has
        # matching content, so this resolves deterministically (no LLM call,
        # no extraction call) but is still recorded, tagged cross_session_recall.
        recall_response = self._process(
            engine, "Let's continue the SQL injection lesson.", "bscp-sqli"
        )
        self.assertTrue(recall_response.success)
        self.assertEqual(len(extractor.calls), 0)

        # Turn 2: an ordinary message in the same session.
        self._process(engine, "My answer uses UNION SELECT.", "bscp-sqli")

        self.assertEqual(len(extractor.context_calls), 1)
        self.assertEqual(extractor.context_calls[0], "")

    def test_the_window_reaches_back_through_one_intervening_unrelated_turn(
        self,
    ) -> None:
        """A hint two turns back must still be visible, not just one turn back.

        Distinct from the main BSCP-sequence test, where the claim directly
        follows the hint with nothing in between.
        """
        self.session_manager.create("bscp-window")
        llm_provider = QueuedLLMProvider(
            [HINT_REPLY, "Haha, indeed!", "Correct! Well done."]
        )
        extractor = QueuedCandidateExtractor(
            [
                empty_batch("Give me a hint."),
                empty_batch("By the way, nice weather today."),
                mastery_batch(
                    "My answer is UNION SELECT. I solved it independently.",
                    "User independently solved SQL injection using UNION " "SELECT.",
                ),
            ]
        )
        engine = self._engine(llm_provider, extractor)

        self._process(engine, "Give me a hint.", "bscp-window")
        self._process(engine, "By the way, nice weather today.", "bscp-window")
        response = self._process(
            engine,
            "My answer is UNION SELECT. I solved it independently.",
            "bscp-window",
        )

        self.assertTrue(response.success)
        self.assertIn("UNION keyword", extractor.context_calls[-1])
        learned = load_learned_memories(self.memory_manager)
        self.assertFalse(any(memory.kind == "self_fact" for memory in learned))

    def test_the_window_does_not_reach_back_three_turns(self) -> None:
        """The window is bounded at 2 turns, not unlimited history.

        The same hint as above, but now three turns back with two short,
        unrelated turns in between: it must have scrolled out of context, so
        the later independence claim is correctly treated as unaided.
        """
        self.session_manager.create("bscp-window-bound")
        llm_provider = QueuedLLMProvider(
            [HINT_REPLY, "Haha, indeed!", "Paris.", "Correct! Well done."]
        )
        extractor = QueuedCandidateExtractor(
            [
                empty_batch("Give me a hint."),
                empty_batch("By the way, nice weather today."),
                empty_batch("What's the capital of France?"),
                mastery_batch(
                    "My answer is UNION SELECT. I solved it independently.",
                    "User independently solved SQL injection using UNION " "SELECT.",
                ),
            ]
        )
        engine = self._engine(llm_provider, extractor)

        self._process(engine, "Give me a hint.", "bscp-window-bound")
        self._process(engine, "By the way, nice weather today.", "bscp-window-bound")
        self._process(engine, "What's the capital of France?", "bscp-window-bound")
        response = self._process(
            engine,
            "My answer is UNION SELECT. I solved it independently.",
            "bscp-window-bound",
        )

        self.assertTrue(response.success)
        self.assertNotIn("UNION keyword", extractor.context_calls[-1])
        learned = load_learned_memories(self.memory_manager)
        self.assertTrue(any(memory.kind == "self_fact" for memory in learned))

    def test_a_recall_turn_inside_the_window_is_skipped_not_just_the_recall_turn(
        self,
    ) -> None:
        """The exclusion holds for a recall turn sitting *inside* a later window.

        Distinct from the earlier recall test, which only proves extraction
        is skipped on the recall turn itself. Here the recall turn is the
        *first* of two prior turns a later, unrelated turn's window would
        otherwise include.
        """
        self.session_manager.create("bscp-recall-in-window")
        llm_provider = QueuedLLMProvider(["Noted.", "Here is the explanation."])
        extractor = QueuedCandidateExtractor(
            [
                empty_batch("By the way, nice weather today."),
                mastery_batch(
                    "I independently worked out reflected XSS.",
                    "User independently explained reflected XSS.",
                    key="xss_understanding",
                ),
            ]
        )
        engine = self._engine(llm_provider, extractor)

        # Turn 1: a recall request (no other session matches -> deterministic
        # not-found reply, no LLM call, no extraction call, but still recorded
        # and tagged cross_session_recall).
        self._process(
            engine,
            "Let's continue the SQL injection lesson.",
            "bscp-recall-in-window",
        )
        # Turn 2: unrelated small talk.
        self._process(
            engine, "By the way, nice weather today.", "bscp-recall-in-window"
        )
        # Turn 3: an unrelated independent claim. The window (last 2 turns)
        # would otherwise include the recall turn as turn 1.
        self._process(
            engine,
            "I independently worked out reflected XSS.",
            "bscp-recall-in-window",
        )

        self.assertNotIn("SQL injection lesson", extractor.context_calls[-1])
        learned = load_learned_memories(self.memory_manager)
        self.assertTrue(
            any(
                memory.kind == "self_fact" and memory.key == "xss_understanding"
                for memory in learned
            )
        )


if __name__ == "__main__":
    unittest.main()
