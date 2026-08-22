from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cognition.LearnedMemoryContextService import (
    DEFAULT_CHAT_SEMANTIC_CONTEXT_LIMIT,
    LearnedMemoryContextService,
)
from core.Exceptions import MemoryError
from eventbus.EventBus import EventBus
from memory.JsonFileMemoryStore import JsonFileMemoryStore
from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemoryCodec import decode_learned_memory
from memory.LearnedMemoryCorrection import correct_learned_memory_value
from memory.LearnedMemoryStore import append_learned_memory
from memory.MemoryManager import MemoryManager
from memory.RankedKeywordLearnedMemorySelector import (
    RankedKeywordLearnedMemorySelector,
)
from memory.SemanticMemoryMatch import SemanticMemoryMatch


class RecordingSemanticRuntime:
    """Stand in for SemanticMemoryIndexRuntime without embeddings or an index."""

    def __init__(self, matches: tuple[SemanticMemoryMatch, ...] = ()) -> None:
        self.matches = matches
        self.queries: list[tuple[str, int | None]] = []

    def search(
        self,
        source_text: str,
        *,
        limit: int | None = None,
    ) -> tuple[SemanticMemoryMatch, ...]:
        self.queries.append((source_text, limit))
        return self.matches


class FailingSemanticRuntime(RecordingSemanticRuntime):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def search(
        self,
        source_text: str,
        *,
        limit: int | None = None,
    ) -> tuple[SemanticMemoryMatch, ...]:
        self.queries.append((source_text, limit))
        raise self.error


class LearnedMemoryContextServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.memory_manager = MemoryManager(self.event_bus)
        self.selector = RankedKeywordLearnedMemorySelector(limit=8)

    def _remember(self, kind: str, key: str, value: str) -> str:
        record = append_learned_memory(
            self.memory_manager,
            LearnedMemory(kind=kind, key=key, value=value),  # type: ignore[arg-type]
        )
        return record.memory_id

    def _memory_id_for(self, key: str, value: str) -> str:
        for record in self.memory_manager.all():
            decoded = decode_learned_memory(record)
            if decoded is not None and decoded.key == key and decoded.value == value:
                return record.memory_id
        raise AssertionError(f"No record for {key}={value}")

    def test_disabled_feature_issues_no_semantic_query(self) -> None:
        runtime = RecordingSemanticRuntime(
            (SemanticMemoryMatch(memory_id="anything", score=1.0),)
        )
        self._remember("preference", "favorite_planet", "Saturn")
        service = LearnedMemoryContextService(selector=self.selector)

        context = service.build(self.memory_manager, "What is my favorite planet?")

        self.assertEqual(runtime.queries, [])
        self.assertFalse(service.semantic_enabled)
        self.assertIn("preference | favorite_planet | Saturn", context)

    def test_disabled_feature_matches_the_deterministic_path_exactly(self) -> None:
        self._remember("preference", "favorite_planet", "Saturn")
        self._remember("project_fact", "active_project", "Hypatia")
        message = "What is my favorite planet?"

        disabled = LearnedMemoryContextService(selector=self.selector)
        deterministic = LearnedMemoryContextService(selector=self.selector)

        self.assertEqual(
            disabled.build(self.memory_manager, message),
            deterministic._build_deterministic(self.memory_manager, message),
        )

    def test_semantic_wording_recovers_a_learned_memory(self) -> None:
        self._remember("preference", "favorite_planet", "Saturn")
        saturn_id = self._memory_id_for("favorite_planet", "Saturn")
        runtime = RecordingSemanticRuntime(
            (SemanticMemoryMatch(memory_id=saturn_id, score=0.91),)
        )
        service = LearnedMemoryContextService(
            selector=self.selector,
            semantic_runtime=runtime,  # type: ignore[arg-type]
        )

        context = service.build(
            self.memory_manager,
            "Which ringed world do I like the most?",
        )

        self.assertIn("preference | favorite_planet | Saturn", context)
        self.assertEqual(len(runtime.queries), 1)

    def test_unrelated_semantic_memories_are_not_injected(self) -> None:
        self._remember("preference", "favorite_planet", "Saturn")
        self._remember("project_fact", "active_project", "Hypatia")
        saturn_id = self._memory_id_for("favorite_planet", "Saturn")
        runtime = RecordingSemanticRuntime(
            (SemanticMemoryMatch(memory_id=saturn_id, score=0.91),)
        )
        service = LearnedMemoryContextService(
            selector=self.selector,
            semantic_runtime=runtime,  # type: ignore[arg-type]
        )

        context = service.build(
            self.memory_manager,
            "Which ringed world do I like the most?",
        )

        self.assertIn("Saturn", context)
        self.assertNotIn("Hypatia", context)

    def test_fused_context_remains_bounded(self) -> None:
        overflow = DEFAULT_CHAT_SEMANTIC_CONTEXT_LIMIT + 6
        matches = []
        for index in range(overflow):
            self._remember("preference", f"planet_{index}", f"Saturn{index}")
            matches.append(
                SemanticMemoryMatch(
                    memory_id=self._memory_id_for(f"planet_{index}", f"Saturn{index}"),
                    score=1.0 - index / 100,
                )
            )
        runtime = RecordingSemanticRuntime(tuple(matches))
        service = LearnedMemoryContextService(
            selector=self.selector,
            semantic_runtime=runtime,  # type: ignore[arg-type]
        )

        context = service.build(self.memory_manager, "planet")

        lines = [line for line in context.splitlines() if line.startswith("- ")]
        self.assertEqual(len(lines), DEFAULT_CHAT_SEMANTIC_CONTEXT_LIMIT)
        self.assertLess(len(lines), overflow)

    def test_keyword_and_semantic_overlap_is_deduplicated(self) -> None:
        self._remember("preference", "favorite_planet", "Saturn")
        saturn_id = self._memory_id_for("favorite_planet", "Saturn")
        runtime = RecordingSemanticRuntime(
            (SemanticMemoryMatch(memory_id=saturn_id, score=0.99),)
        )
        service = LearnedMemoryContextService(
            selector=self.selector,
            semantic_runtime=runtime,  # type: ignore[arg-type]
        )

        context = service.build(self.memory_manager, "What is my favorite planet?")

        lines = [line for line in context.splitlines() if line.startswith("- ")]
        self.assertEqual(lines, ["- preference | favorite_planet | Saturn"])

    def test_superseded_semantic_match_never_resurrects_a_stale_value(self) -> None:
        self._remember("preference", "favorite_planet", "Jupiter")
        stale_id = self._memory_id_for("favorite_planet", "Jupiter")
        correct_learned_memory_value(
            self.memory_manager,
            kind="preference",
            key="favorite_planet",
            value="Saturn",
        )
        runtime = RecordingSemanticRuntime(
            (SemanticMemoryMatch(memory_id=stale_id, score=0.99),)
        )
        service = LearnedMemoryContextService(
            selector=self.selector,
            semantic_runtime=runtime,  # type: ignore[arg-type]
        )

        context = service.build(
            self.memory_manager,
            "Which ringed world do I like the most?",
        )

        self.assertNotIn("Jupiter", context)

    def test_empty_semantic_result_falls_back_to_the_lexical_path(self) -> None:
        self._remember("preference", "favorite_planet", "Saturn")
        runtime = RecordingSemanticRuntime(())
        service = LearnedMemoryContextService(
            selector=self.selector,
            semantic_runtime=runtime,  # type: ignore[arg-type]
        )

        context = service.build(self.memory_manager, "What is my favorite planet?")

        self.assertEqual(len(runtime.queries), 1)
        self.assertIn("preference | favorite_planet | Saturn", context)

    def test_semantic_provider_failure_falls_back_and_reports_cause(self) -> None:
        self._remember("preference", "favorite_planet", "Saturn")
        runtime = FailingSemanticRuntime(MemoryError("Embedding transport failed."))
        causes: list[str] = []
        service = LearnedMemoryContextService(
            selector=self.selector,
            semantic_runtime=runtime,  # type: ignore[arg-type]
            on_semantic_failure=causes.append,
        )

        context = service.build(self.memory_manager, "What is my favorite planet?")

        self.assertEqual(causes, ["MemoryError"])
        self.assertIn("preference | favorite_planet | Saturn", context)

    def test_semantic_os_error_falls_back_without_raising(self) -> None:
        self._remember("preference", "favorite_planet", "Saturn")
        runtime = FailingSemanticRuntime(OSError("connection refused"))
        service = LearnedMemoryContextService(
            selector=self.selector,
            semantic_runtime=runtime,  # type: ignore[arg-type]
        )

        context = service.build(self.memory_manager, "What is my favorite planet?")

        self.assertIn("preference | favorite_planet | Saturn", context)

    def test_exactly_one_semantic_query_per_build(self) -> None:
        for index in range(5):
            self._remember("preference", f"planet_{index}", f"Saturn{index}")
        runtime = RecordingSemanticRuntime(
            (
                SemanticMemoryMatch(
                    memory_id=self._memory_id_for("planet_0", "Saturn0"),
                    score=0.9,
                ),
            )
        )
        service = LearnedMemoryContextService(
            selector=self.selector,
            semantic_runtime=runtime,  # type: ignore[arg-type]
        )

        service.build(self.memory_manager, "Which ringed world do I like?")

        self.assertEqual(len(runtime.queries), 1)
        self.assertEqual(runtime.queries[0][0], "Which ringed world do I like?")

    def test_retrieval_never_writes_a_memory_record(self) -> None:
        self._remember("preference", "favorite_planet", "Saturn")
        saturn_id = self._memory_id_for("favorite_planet", "Saturn")
        runtime = RecordingSemanticRuntime(
            (SemanticMemoryMatch(memory_id=saturn_id, score=0.9),)
        )
        service = LearnedMemoryContextService(
            selector=self.selector,
            semantic_runtime=runtime,  # type: ignore[arg-type]
        )
        before = [record.memory_id for record in self.memory_manager.all()]
        events: list[str] = []
        self.event_bus.subscribe("*", lambda event: events.append(event.name))

        service.build(self.memory_manager, "Which ringed world do I like?")

        after = [record.memory_id for record in self.memory_manager.all()]
        self.assertEqual(before, after)
        self.assertEqual(events, [])

    def test_missing_semantic_record_is_skipped(self) -> None:
        self._remember("preference", "favorite_planet", "Saturn")
        runtime = RecordingSemanticRuntime(
            (SemanticMemoryMatch(memory_id="deleted-record", score=0.99),)
        )
        service = LearnedMemoryContextService(
            selector=self.selector,
            semantic_runtime=runtime,  # type: ignore[arg-type]
        )

        context = service.build(self.memory_manager, "What is my favorite planet?")

        self.assertIn("preference | favorite_planet | Saturn", context)

    def test_rejects_invalid_semantic_query_limit(self) -> None:
        for invalid in (0, -1, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    LearnedMemoryContextService(semantic_query_limit=invalid)


class LearnedMemoryContextServicePersistenceTests(unittest.TestCase):
    """Fusion must work against a reloaded persistent memory store."""

    def test_reloaded_store_still_resolves_semantic_matches(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "memory.json"
            first_bus = EventBus()
            first_manager = MemoryManager(first_bus, store=JsonFileMemoryStore(path))
            append_learned_memory(
                first_manager,
                LearnedMemory(
                    kind="preference",
                    key="favorite_planet",
                    value="Saturn",
                ),
            )

            second_bus = EventBus()
            second_manager = MemoryManager(second_bus, store=JsonFileMemoryStore(path))
            second_manager.load()
            saturn_id = next(
                record.memory_id
                for record in second_manager.all()
                if decode_learned_memory(record) is not None
            )
            runtime = RecordingSemanticRuntime(
                (SemanticMemoryMatch(memory_id=saturn_id, score=0.95),)
            )
            service = LearnedMemoryContextService(
                selector=RankedKeywordLearnedMemorySelector(limit=8),
                semantic_runtime=runtime,  # type: ignore[arg-type]
            )

            context = service.build(
                second_manager,
                "Which ringed world do I like the most?",
            )

        self.assertIn("preference | favorite_planet | Saturn", context)


if __name__ == "__main__":
    unittest.main()
