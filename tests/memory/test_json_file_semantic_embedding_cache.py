from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import MemoryError
from memory.Embedding import Embedding
from memory.JsonFileSemanticEmbeddingCache import (
    JsonFileSemanticEmbeddingCache,
)


class JsonFileSemanticEmbeddingCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "semantic_embeddings.json"
        self.cache = JsonFileSemanticEmbeddingCache(self.path, "provider")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_reuses_only_exact_content_for_the_same_provider_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "semantic_embeddings.json"
            cache = JsonFileSemanticEmbeddingCache(path, "ollama:embeddinggemma")
            embedding = Embedding((1, 0))

            cache.upsert("memory-1", "Original fact", embedding)

            self.assertEqual(cache.get("memory-1", "Original fact"), embedding)
            self.assertIsNone(cache.get("memory-1", "Changed fact"))
            self.assertEqual(
                JsonFileSemanticEmbeddingCache(
                    path,
                    "ollama:embeddinggemma",
                ).get("memory-1", "Original fact"),
                embedding,
            )
            self.assertIsNone(
                JsonFileSemanticEmbeddingCache(path, "ollama:other-model").get(
                    "memory-1",
                    "Original fact",
                )
            )

    def test_replace_discards_deleted_entries_and_keeps_deterministic_json(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "semantic_embeddings.json"
            cache = JsonFileSemanticEmbeddingCache(path, "provider")
            cache.upsert("obsolete", "Old fact", Embedding((1, 0)))

            cache.replace(
                (
                    ("beta", "Second fact", Embedding((0, 1))),
                    ("alpha", "First fact", Embedding((1, 0))),
                )
            )

            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                [entry["memory_id"] for entry in document["entries"]],
                ["alpha", "beta"],
            )
            self.assertIsNone(cache.get("obsolete", "Old fact"))
            self.assertEqual(cache.get("alpha", "First fact"), Embedding((1, 0)))

    def test_rejects_corrupt_cached_embeddings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "semantic_embeddings.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "provider_key": "provider",
                        "entries": [
                            {
                                "memory_id": "memory-1",
                                "content_sha256": "not-a-sha256",
                                "embedding": [1, 0],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(MemoryError, "invalid entry"):
                JsonFileSemanticEmbeddingCache(path, "provider").get(
                    "memory-1",
                    "Fact",
                )

    def test_rejects_boolean_schema_without_coercion(self) -> None:
        for schema_version in (2, True):
            with self.subTest(schema_version=schema_version):
                self._write_document(
                    {
                        "schema_version": schema_version,
                        "provider_key": "provider",
                        "entries": [],
                    }
                )

                with self.assertRaisesRegex(MemoryError, "unsupported schema"):
                    JsonFileSemanticEmbeddingCache(
                        self.path,
                        "provider",
                    )._load_entries()

    def test_oversized_file_is_rejected_before_json_decoding(self) -> None:
        self.path.write_bytes(b"{}")

        with (
            patch(
                "memory.JsonFileSemanticEmbeddingCache."
                "MAX_SEMANTIC_EMBEDDING_CACHE_BYTES",
                1,
            ),
            patch(
                "memory.JsonFileSemanticEmbeddingCache.json.loads",
                side_effect=AssertionError("Oversized JSON must not be decoded."),
            ),
        ):
            with self.assertRaisesRegex(MemoryError, "too large"):
                self.cache._load_entries()

    def test_load_uses_open_descriptor_without_preflight_stat(self) -> None:
        embedding = Embedding((1, 0))
        self.cache.upsert("memory-1", "Fact", embedding)

        with patch.object(
            Path,
            "stat",
            side_effect=AssertionError("Cache load must not preflight file size."),
        ):
            loaded = JsonFileSemanticEmbeddingCache(
                self.path,
                "provider",
            ).get("memory-1", "Fact")

        self.assertEqual(loaded, embedding)

    def test_provider_key_bound_and_foreign_provider_isolation(self) -> None:
        with patch(
            "memory.JsonFileSemanticEmbeddingCache."
            "MAX_SEMANTIC_EMBEDDING_CACHE_PROVIDER_KEY_CHARACTERS",
            5,
        ):
            maximum_cache = JsonFileSemanticEmbeddingCache(self.path, "p" * 5)
            maximum_cache.upsert("memory-1", "Fact", Embedding((1, 0)))
            self.assertEqual(
                JsonFileSemanticEmbeddingCache(self.path, "p" * 5).get(
                    "memory-1",
                    "Fact",
                ),
                Embedding((1, 0)),
            )
            with self.assertRaisesRegex(ValueError, "provider key.*too long"):
                JsonFileSemanticEmbeddingCache(self.path, "p" * 6)

        self._write_document(
            {
                "schema_version": 1,
                "provider_key": "other-provider",
                "entries": "foreign entries are not parsed",
            }
        )
        foreign_cache = JsonFileSemanticEmbeddingCache(self.path, "provider")
        self.assertIsNone(
            foreign_cache.get(
                "memory-1",
                "Fact",
            )
        )
        self.path.write_bytes(b"invalid JSON must not be re-read")
        self.assertIsNone(foreign_cache.get("memory-1", "Fact"))

        self._write_document(
            {
                "schema_version": 1,
                "provider_key": "p" * 6,
                "entries": [],
            }
        )
        with patch(
            "memory.JsonFileSemanticEmbeddingCache."
            "MAX_SEMANTIC_EMBEDDING_CACHE_PROVIDER_KEY_CHARACTERS",
            5,
        ):
            with self.assertRaisesRegex(MemoryError, "invalid provider key"):
                JsonFileSemanticEmbeddingCache(
                    self.path,
                    "valid",
                )._load_entries()

    def test_entry_bound_is_checked_before_parse_and_serialization(self) -> None:
        self._write_document(
            {
                "schema_version": 1,
                "provider_key": "provider",
                "entries": [
                    self._entry_document("memory-1", (1, 0)),
                    self._entry_document("memory-2", (0, 1)),
                ],
            }
        )
        with (
            patch(
                "memory.JsonFileSemanticEmbeddingCache."
                "MAX_SEMANTIC_EMBEDDING_CACHE_ENTRIES",
                1,
            ),
            patch.object(
                self.cache,
                "_validate_memory_id",
                side_effect=AssertionError("Excess entries must not be parsed."),
            ),
        ):
            with self.assertRaisesRegex(MemoryError, "too many entries"):
                self.cache._load_entries()

        entries = (
            ("memory-1", "First", Embedding((1, 0))),
            ("memory-2", "Second", Embedding((0, 1))),
        )
        with (
            patch(
                "memory.JsonFileSemanticEmbeddingCache."
                "MAX_SEMANTIC_EMBEDDING_CACHE_ENTRIES",
                1,
            ),
            patch.object(
                self.cache,
                "_content_hash",
                side_effect=AssertionError("Excess entries must not be serialized."),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "too many entries"):
                self.cache.replace(entries)

        limited_path = self.path.parent / "limited.json"
        limited_cache = JsonFileSemanticEmbeddingCache(limited_path, "provider")
        with patch(
            "memory.JsonFileSemanticEmbeddingCache."
            "MAX_SEMANTIC_EMBEDDING_CACHE_ENTRIES",
            1,
        ):
            limited_cache.upsert("memory-1", "First", Embedding((1, 0)))
            original_snapshot = limited_path.read_bytes()
            with self.assertRaisesRegex(ValueError, "too many entries"):
                limited_cache.upsert("memory-2", "Second", Embedding((0, 1)))
            self.assertEqual(limited_path.read_bytes(), original_snapshot)
            self.assertEqual(
                limited_cache.get("memory-1", "First"),
                Embedding((1, 0)),
            )
            self.assertIsNone(limited_cache.get("memory-2", "Second"))

    def test_memory_id_and_source_text_bounds_apply_before_embedding_parse(
        self,
    ) -> None:
        with (
            patch(
                "memory.JsonFileSemanticEmbeddingCache."
                "MAX_SEMANTIC_EMBEDDING_CACHE_MEMORY_ID_CHARACTERS",
                5,
            ),
            patch(
                "memory.JsonFileSemanticEmbeddingCache."
                "MAX_SEMANTIC_EMBEDDING_CACHE_SOURCE_TEXT_CHARACTERS",
                5,
            ),
        ):
            self.cache.upsert("id123", "abcde", Embedding((1, 0)))
            self.assertEqual(
                JsonFileSemanticEmbeddingCache(self.path, "provider").get(
                    "id123",
                    "abcde",
                ),
                Embedding((1, 0)),
            )
            with self.assertRaisesRegex(ValueError, "memory ID.*too long"):
                self.cache.upsert("id1234", "abcde", Embedding((1, 0)))
            with self.assertRaisesRegex(ValueError, "source text.*too long"):
                self.cache.upsert("id123", "abcdef", Embedding((1, 0)))

            self._write_document(
                {
                    "schema_version": 1,
                    "provider_key": "provider",
                    "entries": [self._entry_document("id1234", (1, 0))],
                }
            )
            invalid_cache = JsonFileSemanticEmbeddingCache(self.path, "provider")
            with patch.object(
                invalid_cache,
                "_validate_embedding",
                side_effect=AssertionError(
                    "Oversized memory IDs must fail before embedding validation."
                ),
            ):
                with self.assertRaisesRegex(MemoryError, "invalid entry"):
                    invalid_cache._load_entries()

    def test_dimension_value_aggregate_and_consistency_bounds(self) -> None:
        entries = (
            ("memory-1", "First", Embedding((1, 0))),
            ("memory-2", "Second", Embedding((0, 1))),
        )
        with (
            patch(
                "memory.JsonFileSemanticEmbeddingCache."
                "MAX_SEMANTIC_EMBEDDING_CACHE_DIMENSION",
                2,
            ),
            patch(
                "memory.JsonFileSemanticEmbeddingCache."
                "MAX_SEMANTIC_EMBEDDING_CACHE_VALUES",
                4,
            ),
        ):
            self.cache.replace(entries)
            self.assertEqual(
                JsonFileSemanticEmbeddingCache(self.path, "provider").get(
                    "memory-2",
                    "Second",
                ),
                Embedding((0, 1)),
            )
        exact_snapshot = self.path.read_bytes()

        with patch(
            "memory.JsonFileSemanticEmbeddingCache."
            "MAX_SEMANTIC_EMBEDDING_CACHE_VALUES",
            3,
        ):
            with self.assertRaisesRegex(ValueError, "too many values"):
                self.cache.replace(entries)
        self.assertEqual(self.path.read_bytes(), exact_snapshot)

        with patch(
            "memory.JsonFileSemanticEmbeddingCache."
            "MAX_SEMANTIC_EMBEDDING_CACHE_DIMENSION",
            2,
        ):
            with self.assertRaisesRegex(ValueError, "dimension.*too large"):
                self.cache.upsert("memory-3", "Third", Embedding((1, 0, 0)))
            with self.assertRaisesRegex(ValueError, "dimensions.*consistent"):
                self.cache.upsert("memory-3", "Third", Embedding((1,)))
            self.assertEqual(self.path.read_bytes(), exact_snapshot)
            self.assertIsNone(self.cache.get("memory-3", "Third"))
            with self.assertRaisesRegex(ValueError, "dimensions.*consistent"):
                self.cache.replace(
                    (
                        ("memory-1", "First", Embedding((1, 0))),
                        ("memory-2", "Second", Embedding((1,))),
                    )
                )

        self._write_document(
            {
                "schema_version": 1,
                "provider_key": "provider",
                "entries": [
                    self._entry_document("memory-1", (1, 0)),
                    self._entry_document("memory-2", (1,)),
                ],
            }
        )
        with self.assertRaisesRegex(MemoryError, "invalid entry"):
            JsonFileSemanticEmbeddingCache(
                self.path,
                "provider",
            )._load_entries()

    def test_exact_utf8_file_bound_preserves_snapshot_and_cleans_temp(self) -> None:
        cache = JsonFileSemanticEmbeddingCache(self.path, "sağlayıcı")
        original_embedding = Embedding((1, 0))
        cache.upsert("hafıza", "İçerik", original_embedding)
        exact_snapshot = self.path.read_bytes()

        with patch(
            "memory.JsonFileSemanticEmbeddingCache."
            "MAX_SEMANTIC_EMBEDDING_CACHE_BYTES",
            len(exact_snapshot),
        ):
            cache.upsert("hafıza", "İçerik", original_embedding)

        self.assertEqual(self.path.read_bytes(), exact_snapshot)
        with patch(
            "memory.JsonFileSemanticEmbeddingCache."
            "MAX_SEMANTIC_EMBEDDING_CACHE_BYTES",
            len(exact_snapshot) - 1,
        ):
            with self.assertRaisesRegex(MemoryError, "too large"):
                cache.upsert("hafıza", "İçerik", Embedding((0, 1)))

        self.assertEqual(self.path.read_bytes(), exact_snapshot)
        self.assertEqual(cache.get("hafıza", "İçerik"), original_embedding)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_failed_replace_preserves_snapshot_and_in_memory_state(self) -> None:
        original_embedding = Embedding((1, 0))
        self.cache.upsert("memory-1", "First", original_embedding)
        module = import_module("memory.JsonFileSemanticEmbeddingCache")

        with patch.object(module.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(MemoryError):
                self.cache.upsert("memory-2", "Second", Embedding((0, 1)))

        self.assertEqual(self.cache.get("memory-1", "First"), original_embedding)
        self.assertIsNone(self.cache.get("memory-2", "Second"))
        self.assertEqual(
            JsonFileSemanticEmbeddingCache(self.path, "provider").get(
                "memory-1",
                "First",
            ),
            original_embedding,
        )
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def _write_document(self, document: dict[str, object]) -> None:
        self.path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _entry_document(
        memory_id: str,
        values: tuple[int | float, ...],
        *,
        source_text: str = "Fact",
    ) -> dict[str, object]:
        return {
            "memory_id": memory_id,
            "content_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            "embedding": list(values),
        }


if __name__ == "__main__":
    unittest.main()
