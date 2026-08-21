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
from core.Exceptions import ContainerError, MemoryError
from memory.Embedding import Embedding
from memory.JsonFileMemoryStore import JsonFileMemoryStore
from memory.MemoryRecord import MemoryRecord
from memory.SemanticMemoryIndexRuntime import SemanticMemoryIndexRuntime


class RecordingEmbeddingProvider:
    def __init__(self, embedding: Embedding, error: Exception | None = None) -> None:
        self._embedding = embedding
        self.error = error
        self.sources: list[str] = []

    def embed(self, source_text: str) -> Embedding:
        self.sources.append(source_text)
        if self.error is not None:
            raise self.error
        return self._embedding


class BootstrapSemanticMemoryRuntimeTests(unittest.TestCase):
    def test_disabled_process_runtime_does_not_construct_or_register_provider(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(os.environ, {}, clear=True),
            patch("core.Bootstrap.OllamaEmbeddingProvider") as construct_provider,
        ):
            temporary_path = Path(temporary_directory)
            memory_path = temporary_path / "memory.json"
            JsonFileMemoryStore(memory_path).save(
                [MemoryRecord(memory_id="memory-1", content="Persistent fact")]
            )
            bootstrap = Bootstrap.from_process_environment(
                memory_path,
                temporary_path / "sessions.json",
            )
            bootstrap.initialize()

            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(SemanticMemoryIndexRuntime)

        construct_provider.assert_not_called()

    def test_enabled_process_runtime_builds_and_registers_local_index(self) -> None:
        record = MemoryRecord(memory_id="memory-1", content="Persistent fact")
        provider = RecordingEmbeddingProvider(Embedding((1, 0)))

        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {"HYPATIA_SEMANTIC_MEMORY_ENABLED": "true"},
                clear=True,
            ),
            patch(
                "core.Bootstrap.OllamaEmbeddingProvider",
                return_value=provider,
            ) as construct_provider,
        ):
            temporary_path = Path(temporary_directory)
            memory_path = temporary_path / "memory.json"
            JsonFileMemoryStore(memory_path).save([record])
            bootstrap = Bootstrap.from_process_environment(
                memory_path,
                temporary_path / "sessions.json",
            )
            bootstrap.initialize()
            runtime = bootstrap.container.resolve(SemanticMemoryIndexRuntime)

        construct_provider.assert_called_once_with(
            endpoint="http://localhost:11434/api/embed",
            model="embeddinggemma",
            transport=unittest.mock.ANY,
        )
        self.assertEqual(provider.sources, ["Persistent fact"])
        assert runtime.current() is not None
        self.assertEqual(runtime.current().count(), 1)

    def test_enabled_runtime_passes_configured_timeout_to_local_transport(self) -> None:
        provider = RecordingEmbeddingProvider(Embedding((1, 0)))

        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_SEMANTIC_MEMORY_ENABLED": "true",
                    "HYPATIA_SEMANTIC_MEMORY_OLLAMA_TIMEOUT_SECONDS": "7.5",
                },
                clear=True,
            ),
            patch(
                "core.Bootstrap.UrllibOllamaEmbeddingTransport"
            ) as construct_transport,
            patch("core.Bootstrap.OllamaEmbeddingProvider", return_value=provider),
        ):
            temporary_path = Path(temporary_directory)
            Bootstrap.from_process_environment(
                temporary_path / "memory.json",
                temporary_path / "sessions.json",
            )

        construct_transport.assert_called_once_with(timeout_seconds=7.5)

    def test_rebuild_budget_starts_primary_runtime_without_provider_calls(self) -> None:
        provider = RecordingEmbeddingProvider(Embedding((1, 0)))

        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_SEMANTIC_MEMORY_ENABLED": "true",
                    "HYPATIA_SEMANTIC_MEMORY_REBUILD_MAX_PROVIDER_CALLS": "1",
                },
                clear=True,
            ),
            patch("core.Bootstrap.OllamaEmbeddingProvider", return_value=provider),
        ):
            temporary_path = Path(temporary_directory)
            memory_path = temporary_path / "memory.json"
            JsonFileMemoryStore(memory_path).save(
                [
                    MemoryRecord(memory_id="memory-1", content="First fact"),
                    MemoryRecord(memory_id="memory-2", content="Second fact"),
                ]
            )
            bootstrap = Bootstrap.from_process_environment(
                memory_path,
                temporary_path / "sessions.json",
            )
            bootstrap.initialize()
            runtime = bootstrap.container.resolve(SemanticMemoryIndexRuntime)
            engine = bootstrap.container.resolve(CognitiveEngine)
            status = engine.process(BrainRequest(message="semantic recall status"))

        self.assertEqual(provider.sources, [])
        self.assertIsNone(runtime.current())
        self.assertEqual(
            runtime.last_rebuild_error(),
            "Semantic index rebuild failed.",
        )
        self.assertIn("Runtime: unavailable", status.message)
        self.assertNotIn("provider-call budget", status.message)

    def test_enabled_runtime_indexes_new_conversation_memory_after_bootstrap(
        self,
    ) -> None:
        provider = RecordingEmbeddingProvider(Embedding((1, 0)))

        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {"HYPATIA_SEMANTIC_MEMORY_ENABLED": "true"},
                clear=True,
            ),
            patch("core.Bootstrap.OllamaEmbeddingProvider", return_value=provider),
        ):
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap.from_process_environment(
                temporary_path / "memory.json",
                temporary_path / "sessions.json",
            )
            bootstrap.initialize()
            runtime = bootstrap.container.resolve(SemanticMemoryIndexRuntime)
            engine = bootstrap.container.resolve(CognitiveEngine)

            engine.process(BrainRequest(message="Hello Hypatia"))
            response = engine.process(BrainRequest(message="semantic recall greeting"))

        assert runtime.current() is not None
        self.assertEqual(runtime.current().count(), 1)
        self.assertTrue(response.success)
        self.assertIn("Semantic recall (semantic):", response.message)
        self.assertEqual(len(provider.sources), 2)
        self.assertIn("User: Hello Hypatia", provider.sources[0])

    def test_opt_in_embedding_persistence_reuses_embeddings_after_restart(self) -> None:
        record = MemoryRecord(memory_id="memory-1", content="Persistent fact")
        provider = RecordingEmbeddingProvider(Embedding((1, 0)))

        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_SEMANTIC_MEMORY_ENABLED": "true",
                    "HYPATIA_SEMANTIC_MEMORY_PERSIST_EMBEDDINGS": "true",
                },
                clear=True,
            ),
            patch("core.Bootstrap.OllamaEmbeddingProvider", return_value=provider),
        ):
            temporary_path = Path(temporary_directory)
            memory_path = temporary_path / "memory.json"
            session_path = temporary_path / "sessions.json"
            JsonFileMemoryStore(memory_path).save([record])

            first_bootstrap = Bootstrap.from_process_environment(
                memory_path, session_path
            )
            first_bootstrap.initialize()
            second_bootstrap = Bootstrap.from_process_environment(
                memory_path, session_path
            )
            second_bootstrap.initialize()

            self.assertTrue((temporary_path / "semantic_embeddings.json").exists())

        self.assertEqual(provider.sources, ["Persistent fact"])

    def test_enabled_runtime_failure_keeps_primary_container_available(
        self,
    ) -> None:
        provider = RecordingEmbeddingProvider(
            Embedding((1, 0)),
            error=MemoryError("Embedding transport failed."),
        )

        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {"HYPATIA_SEMANTIC_MEMORY_ENABLED": "true"},
                clear=True,
            ),
            patch("core.Bootstrap.OllamaEmbeddingProvider", return_value=provider),
        ):
            temporary_path = Path(temporary_directory)
            memory_path = temporary_path / "memory.json"
            JsonFileMemoryStore(memory_path).save(
                [MemoryRecord(memory_id="memory-1", content="Persistent fact")]
            )
            bootstrap = Bootstrap.from_process_environment(
                memory_path,
                temporary_path / "sessions.json",
            )
            bootstrap.initialize()
            runtime = bootstrap.container.resolve(SemanticMemoryIndexRuntime)
            engine = bootstrap.container.resolve(CognitiveEngine)
            conversation = engine.process(BrainRequest(message="Hello Hypatia"))
            status = engine.process(BrainRequest(message="semantic recall status"))
            provider.error = None
            retry = engine.process(BrainRequest(message="semantic recall retry"))
            second_conversation = engine.process(
                BrainRequest(message="Hello again Hypatia")
            )

        self.assertTrue(conversation.success)
        self.assertIn("Runtime: unavailable", status.message)
        self.assertIn("Last rebuild: Semantic index rebuild failed.", status.message)
        self.assertNotIn("transport failed", status.message)
        self.assertTrue(retry.success)
        self.assertTrue(second_conversation.success)
        assert runtime.current() is not None
        self.assertEqual(runtime.current().count(), 3)
        self.assertIsNone(runtime.last_rebuild_error())

    def test_enabled_runtime_rejects_empty_endpoint_or_model_before_provider_constructs(
        self,
    ) -> None:
        for environment, expected_message in (
            (
                {
                    "HYPATIA_SEMANTIC_MEMORY_ENABLED": "true",
                    "HYPATIA_SEMANTIC_MEMORY_OLLAMA_ENDPOINT": "  ",
                },
                "ENDPOINT cannot be empty",
            ),
            (
                {
                    "HYPATIA_SEMANTIC_MEMORY_ENABLED": "true",
                    "HYPATIA_SEMANTIC_MEMORY_OLLAMA_MODEL": "",
                },
                "MODEL cannot be empty",
            ),
            (
                {
                    "HYPATIA_SEMANTIC_MEMORY_ENABLED": "true",
                    "HYPATIA_SEMANTIC_MEMORY_OLLAMA_ENDPOINT": (
                        "https://embedding.example.test/api/embed"
                    ),
                },
                "must be a local HTTP endpoint",
            ),
            (
                {
                    "HYPATIA_SEMANTIC_MEMORY_ENABLED": "true",
                    "HYPATIA_SEMANTIC_MEMORY_OLLAMA_TIMEOUT_SECONDS": "nan",
                },
                "must be a positive finite number",
            ),
            (
                {
                    "HYPATIA_SEMANTIC_MEMORY_ENABLED": "true",
                    "HYPATIA_SEMANTIC_MEMORY_REBUILD_MAX_PROVIDER_CALLS": "-1",
                },
                "must be a non-negative integer",
            ),
            (
                {
                    "HYPATIA_SEMANTIC_MEMORY_ENABLED": "true",
                    "HYPATIA_SEMANTIC_MEMORY_REBUILD_MAX_PROVIDER_CALLS": "٢٠",
                },
                "must be a non-negative integer",
            ),
            (
                {
                    "HYPATIA_SEMANTIC_MEMORY_ENABLED": "true",
                    "HYPATIA_SEMANTIC_MEMORY_REBUILD_MAX_PROVIDER_CALLS": "20001",
                },
                "cannot exceed 20000",
            ),
        ):
            with self.subTest(environment=environment):
                with (
                    tempfile.TemporaryDirectory() as temporary_directory,
                    patch.dict(os.environ, environment, clear=True),
                    patch(
                        "core.Bootstrap.OllamaEmbeddingProvider"
                    ) as construct_provider,
                ):
                    temporary_path = Path(temporary_directory)
                    with self.assertRaisesRegex(ValueError, expected_message):
                        Bootstrap.from_process_environment(
                            temporary_path / "memory.json",
                            temporary_path / "sessions.json",
                        )

                construct_provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
