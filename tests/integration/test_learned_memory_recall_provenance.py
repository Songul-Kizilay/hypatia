"""Recalling a fact and remembering it are not the same achievement.

A live test taught Hypatia a secret word, saw it recalled later in the same
conversation, restarted the app, and saw it recalled again. That is good news,
but the first observation proves much less than it appears to: within one
session the fact is sitting in the conversation transcript, so the model can
simply read it back. Only a session with no transcript isolates durable learned
memory.

These tests separate the two provenances deterministically. The provider records
exactly what it was given, so each test can assert which channel actually
carried the fact: the transcript, the injected learned-memory context, or
neither.
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
from cognition.LearnedMemoryContextService import LearnedMemoryContextService
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from llm.LLMConversationMessage import LLMConversationMessage
from memory.JsonFileMemoryStore import JsonFileMemoryStore
from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCandidate import (
    LearnedMemoryCandidate,
    LearnedMemoryCandidateBatch,
)
from memory.LearnedMemoryStore import load_learned_memories
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from response.ResponseComposer import ResponseComposer
from session.JsonFileSessionStore import JsonFileSessionStore
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

SECRET = "Morvella"
STATEMENT = f"My test secret word is {SECRET}."
QUESTION = "What is my test secret word?"
TEACHING_SESSION = "teaching"
FRESH_SESSION = "fresh"


class RecordingLLMProvider:
    """Record the exact prompt and transcript handed to the model."""

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
        return "Acknowledged."

    @property
    def last_prompt(self) -> str:
        return self.calls[-1][0]

    @property
    def last_history_text(self) -> str:
        return "\n".join(message.content for message in self.calls[-1][1])


class StubExtractor:
    """Return one candidate for the teaching sentence, nothing otherwise."""

    def extract(self, message: str) -> LearnedMemoryCandidateBatch | None:
        if SECRET not in message:
            return None
        return LearnedMemoryCandidateBatch(
            source_text=message,
            candidates=(
                LearnedMemoryCandidate(
                    memory=LearnedMemory(
                        kind="preference",
                        key="test secret word",
                        value=SECRET,
                    ),
                    source_text=message,
                ),
            ),
        )


class RecallProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.memory_path = self.root / "memory.json"
        self.session_path = self.root / "sessions.json"
        document = self.root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(document)
        self.provider = RecordingLLMProvider()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def build_engine(self) -> CognitiveEngine:
        """Build a fresh runtime over the same durable files, as a restart does."""
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus, JsonFileMemoryStore(self.memory_path))
        memory_manager.load()
        session_manager = SessionManager(
            event_bus,
            JsonFileSessionStore(self.session_path),
        )
        session_manager.load()
        for session_id in (TEACHING_SESSION, FRESH_SESSION):
            if not session_manager.exists(session_id):
                session_manager.create(session_id)
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
            learned_memory_candidate_extractor=StubExtractor(),  # type: ignore[arg-type]
        )

    @staticmethod
    def ask(engine: CognitiveEngine, message: str, session_id: str) -> object:
        return engine.process(
            BrainRequest(message=message, metadata={"session_id": session_id})
        )

    def teach(self, engine: CognitiveEngine) -> None:
        self.ask(engine, STATEMENT, TEACHING_SESSION)

    def test_teaching_writes_a_durable_learned_record(self) -> None:
        engine = self.build_engine()

        self.teach(engine)

        memories = load_learned_memories(engine._memory_manager)
        self.assertEqual([memory.value for memory in memories], [SECRET])

    def test_same_session_recall_can_come_from_the_transcript_alone(self) -> None:
        """The weak observation: within one session the fact is simply visible."""
        engine = self.build_engine()
        self.teach(engine)

        self.ask(engine, QUESTION, TEACHING_SESSION)

        self.assertIn(SECRET, self.provider.last_history_text)

    def test_a_fresh_session_carries_no_transcript_at_all(self) -> None:
        engine = self.build_engine()
        self.teach(engine)

        self.ask(engine, QUESTION, FRESH_SESSION)

        self.assertEqual(self.provider.calls[-1][1], ())
        self.assertNotIn(SECRET, self.provider.last_history_text)

    def test_a_fresh_session_still_receives_the_fact_from_learned_memory(self) -> None:
        """The strong observation: no transcript, and the fact still arrives."""
        engine = self.build_engine()
        self.teach(engine)

        self.ask(engine, QUESTION, FRESH_SESSION)

        self.assertEqual(self.provider.calls[-1][1], ())
        self.assertIn(SECRET, self.provider.last_prompt)

    def test_the_fact_survives_a_restart_into_a_fresh_session(self) -> None:
        self.teach(self.build_engine())

        restarted = self.build_engine()
        self.ask(restarted, QUESTION, FRESH_SESSION)

        reloaded = load_learned_memories(restarted._memory_manager)
        self.assertEqual([memory.value for memory in reloaded], [SECRET])
        self.assertEqual(self.provider.calls[-1][1], ())
        self.assertIn(SECRET, self.provider.last_prompt)

    def test_learned_memory_context_is_the_channel_not_the_transcript(self) -> None:
        engine = self.build_engine()
        self.teach(engine)

        context = LearnedMemoryContextService(
            selector=engine._learned_memory_selector,
            context_limit=engine._learned_memory_context_limit,
        ).build(engine._memory_manager, QUESTION)

        self.assertIn(SECRET, context)

    def test_without_a_learned_record_a_fresh_session_gets_nothing(self) -> None:
        """The negative control: no durable record means no channel carries it."""
        engine = self.build_engine()

        self.ask(engine, QUESTION, FRESH_SESSION)

        self.assertEqual(load_learned_memories(engine._memory_manager), ())
        self.assertEqual(self.provider.calls[-1][1], ())
        self.assertNotIn(SECRET, self.provider.last_prompt)


if __name__ == "__main__":
    unittest.main()
