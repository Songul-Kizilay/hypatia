from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from core.Bootstrap import Bootstrap
from core.Exceptions import MemoryError
from llm.LLMConversationMessage import LLMConversationMessage
from llm.LLMProvider import LLMProvider
from llm.LLMRuntimeConfig import LLMRuntimeConfig
from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCodec import decode_learned_memory
from memory.LearnedMemoryStore import append_learned_memory, load_learned_memories
from memory.SemanticMemoryMatch import SemanticMemoryMatch


class RecordingLLMProvider(LLMProvider):
    def __init__(self, response: str = "Understood.") -> None:
        self.response = response
        self.calls: list[tuple[str, tuple[LLMConversationMessage, ...]]] = []

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
    ) -> str:
        del system_instruction
        self.calls.append((prompt, history))
        return self.response


class RecordingSemanticRuntime:
    def __init__(self, matches: tuple[SemanticMemoryMatch, ...] = ()) -> None:
        self.matches = matches
        self.queries: list[str] = []
        self.attached = 0
        self.refreshes = 0

    def attach(self, event_bus: object) -> None:
        self.attached += 1

    def start_refresh(self, *args: object, **kwargs: object) -> str:
        self.refreshes += 1
        return "started"

    def search(
        self,
        source_text: str,
        *,
        limit: int | None = None,
    ) -> tuple[SemanticMemoryMatch, ...]:
        self.queries.append(source_text)
        return self.matches


class FailingSemanticRuntime(RecordingSemanticRuntime):
    def search(
        self,
        source_text: str,
        *,
        limit: int | None = None,
    ) -> tuple[SemanticMemoryMatch, ...]:
        self.queries.append(source_text)
        raise MemoryError("Embedding transport failed.")


class ChatSemanticMemoryFlagTests(unittest.TestCase):
    def _engine(
        self,
        temporary_path: Path,
        provider: RecordingLLMProvider,
        environment: dict[str, str],
        semantic_runtime: object | None = None,
    ) -> CognitiveEngine:
        with (
            patch.dict(os.environ, environment, clear=True),
            patch("core.Bootstrap.activate_llm", return_value=provider),
        ):
            bootstrap = Bootstrap.from_process_environment(
                temporary_path / "memory.json",
                temporary_path / "sessions.json",
            )
            if semantic_runtime is not None:
                bootstrap._semantic_memory_index_runtime = semantic_runtime
            bootstrap._llm_config = LLMRuntimeConfig(
                enabled=True,
                base_url="https://api.example.test/v1/chat/completions",
                model="test-model",
            )
            bootstrap._llm_api_key = "test-api-key"
            bootstrap.initialize()
            return bootstrap.container.resolve(CognitiveEngine)

    def test_flag_is_off_by_default(self) -> None:
        provider = RecordingLLMProvider()
        runtime = RecordingSemanticRuntime(
            (SemanticMemoryMatch(memory_id="anything", score=1.0),)
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            engine = self._engine(
                Path(temporary_directory),
                provider,
                {},
                semantic_runtime=runtime,
            )
            append_learned_memory(
                engine._memory_manager,
                LearnedMemory(
                    kind="preference",
                    key="favorite_planet",
                    value="Saturn",
                ),
            )

            response = engine.process(
                BrainRequest(message="What is my favorite planet?")
            )

        self.assertTrue(response.success)
        self.assertFalse(engine._chat_semantic_memory_enabled)
        self.assertEqual(runtime.queries, [])
        self.assertIn("favorite_planet | Saturn", provider.calls[0][0])

    def test_enabled_flag_issues_exactly_one_query_per_turn(self) -> None:
        provider = RecordingLLMProvider()
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime = RecordingSemanticRuntime()
            engine = self._engine(
                Path(temporary_directory),
                provider,
                {"HYPATIA_CHAT_SEMANTIC_MEMORY_ENABLED": "true"},
                semantic_runtime=runtime,
            )
            append_learned_memory(
                engine._memory_manager,
                LearnedMemory(
                    kind="preference",
                    key="favorite_planet",
                    value="Saturn",
                ),
            )
            saturn_id = next(
                record.memory_id
                for record in engine._memory_manager.all()
                if decode_learned_memory(record) is not None
            )
            runtime.matches = (SemanticMemoryMatch(memory_id=saturn_id, score=0.93),)

            refreshes_after_startup = runtime.refreshes

            engine.process(BrainRequest(message="Which ringed world do I like?"))
            engine.process(BrainRequest(message="And which one again?"))

        self.assertTrue(engine._chat_semantic_memory_enabled)
        self.assertEqual(len(runtime.queries), 2)
        self.assertEqual(runtime.refreshes, refreshes_after_startup)
        self.assertIn("favorite_planet | Saturn", provider.calls[0][0])

    def test_semantic_failure_keeps_chat_working_and_emits_bounded_event(
        self,
    ) -> None:
        provider = RecordingLLMProvider()
        message = "Which ringed world do I like?"
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime = FailingSemanticRuntime()
            engine = self._engine(
                Path(temporary_directory),
                provider,
                {"HYPATIA_CHAT_SEMANTIC_MEMORY_ENABLED": "true"},
                semantic_runtime=runtime,
            )
            failures: list[dict[str, object]] = []
            engine._event_bus.subscribe(
                "brain.chat_semantic_memory.query_failed",
                lambda event: failures.append(dict(event.payload)),
            )

            response = engine.process(
                BrainRequest(message=message, request_id="request-42")
            )

        self.assertTrue(response.success)
        self.assertEqual(
            failures,
            [{"request_id": "request-42", "cause": "MemoryError"}],
        )
        self.assertNotIn(message, repr(failures))

    def test_enabled_flag_without_runtime_keeps_lexical_behavior(self) -> None:
        provider = RecordingLLMProvider()
        with tempfile.TemporaryDirectory() as temporary_directory:
            engine = self._engine(
                Path(temporary_directory),
                provider,
                {"HYPATIA_CHAT_SEMANTIC_MEMORY_ENABLED": "true"},
            )
            append_learned_memory(
                engine._memory_manager,
                LearnedMemory(
                    kind="preference",
                    key="favorite_planet",
                    value="Saturn",
                ),
            )

            response = engine.process(
                BrainRequest(message="What is my favorite planet?")
            )

        self.assertTrue(response.success)
        self.assertIsNone(engine._semantic_memory_index_runtime)
        self.assertIn("favorite_planet | Saturn", provider.calls[0][0])

    def test_retrieval_adds_no_learned_memory_record(self) -> None:
        provider = RecordingLLMProvider()
        with tempfile.TemporaryDirectory() as temporary_directory:
            runtime = RecordingSemanticRuntime()
            engine = self._engine(
                Path(temporary_directory),
                provider,
                {"HYPATIA_CHAT_SEMANTIC_MEMORY_ENABLED": "true"},
                semantic_runtime=runtime,
            )

            engine.process(BrainRequest(message="Which ringed world do I like?"))

            self.assertEqual(load_learned_memories(engine._memory_manager), ())

    def test_explicit_semantic_recall_status_is_unchanged(self) -> None:
        provider = RecordingLLMProvider()
        with tempfile.TemporaryDirectory() as temporary_directory:
            engine = self._engine(
                Path(temporary_directory),
                provider,
                {"HYPATIA_CHAT_SEMANTIC_MEMORY_ENABLED": "true"},
            )

            response = engine.process(BrainRequest(message="semantic recall status"))

        self.assertTrue(response.success)
        self.assertIn("disabled", response.message)


if __name__ == "__main__":
    unittest.main()
