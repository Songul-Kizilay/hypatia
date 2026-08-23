"""The newest message must survive a small context window.

A live test asked about the news, then sent "2026 web application security",
and the model repeated its previous answer almost verbatim. Part of that is
model quality and cannot be fixed here. Part of it was orchestration: an unset
history limit meant an unbounded transcript, and a local model running with a
4096-token window drops what does not fit — which is exactly where the newest
message sits.

What is deterministic is asserted here: history is bounded by default, the
current message is delivered as the prompt rather than buried in the
transcript, and the transcript ends with the immediately preceding turn. What
is not deterministic is not asserted, because no prompt or limit can guarantee a
small model attends to what it was given.
"""

from __future__ import annotations

import sys
import tempfile
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
from llm.LLMEnvironmentSettings import (
    DEFAULT_LLM_HISTORY_MAX_TURNS,
    UNBOUNDED_LLM_HISTORY,
    load_llm_history_max_turns,
)
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService


class RecordingLLMProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[LLMConversationMessage, ...]]] = []

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
    ) -> str:
        self.calls.append((prompt, history))
        return f"Reply to {prompt}"


class ConversationContextPriorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        document = root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(document)
        self.provider = RecordingLLMProvider()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def build_engine(self, max_turns: int | None) -> CognitiveEngine:
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
            llm_provider=self.provider,
            llm_history_max_turns=max_turns,
        )

    def converse(self, engine: CognitiveEngine, count: int) -> None:
        for index in range(count):
            engine.process(BrainRequest(message=f"Question {index}"))

    def test_history_is_bounded_by_default(self) -> None:
        engine = self.build_engine(DEFAULT_LLM_HISTORY_MAX_TURNS)

        self.converse(engine, DEFAULT_LLM_HISTORY_MAX_TURNS * 3)

        _, history = self.provider.calls[-1]
        self.assertEqual(len(history), DEFAULT_LLM_HISTORY_MAX_TURNS * 2)

    def test_the_current_message_is_the_prompt_not_buried_in_history(self) -> None:
        engine = self.build_engine(DEFAULT_LLM_HISTORY_MAX_TURNS)
        self.converse(engine, 5)

        engine.process(BrainRequest(message="2026 web application security"))

        prompt, history = self.provider.calls[-1]
        self.assertEqual(prompt, "2026 web application security")
        self.assertNotIn(
            "2026 web application security",
            [message.content for message in history],
        )

    def test_history_ends_with_the_immediately_preceding_turn(self) -> None:
        engine = self.build_engine(DEFAULT_LLM_HISTORY_MAX_TURNS)
        self.converse(engine, 4)

        engine.process(BrainRequest(message="Latest question"))

        _, history = self.provider.calls[-1]
        self.assertEqual(history[-2].role, "user")
        self.assertEqual(history[-2].content, "Question 3")
        self.assertEqual(history[-1].role, "assistant")

    def test_the_oldest_turns_are_dropped_not_the_newest(self) -> None:
        engine = self.build_engine(2)
        self.converse(engine, 6)

        _, history = self.provider.calls[-1]
        contents = [message.content for message in history]

        self.assertIn("Question 4", contents)
        self.assertNotIn("Question 0", contents)

    def test_an_unbounded_transcript_remains_available_on_request(self) -> None:
        engine = self.build_engine(None)

        self.converse(engine, 8)

        _, history = self.provider.calls[-1]
        self.assertEqual(len(history), 14)

    def test_the_environment_default_matches_what_the_engine_bounds_to(self) -> None:
        self.assertEqual(
            load_llm_history_max_turns({}),
            DEFAULT_LLM_HISTORY_MAX_TURNS,
        )
        self.assertIsNone(
            load_llm_history_max_turns(
                {"HYPATIA_LLM_HISTORY_MAX_TURNS": UNBOUNDED_LLM_HISTORY}
            )
        )


if __name__ == "__main__":
    unittest.main()
