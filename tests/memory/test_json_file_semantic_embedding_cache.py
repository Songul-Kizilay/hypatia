from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import MemoryError
from memory.Embedding import Embedding
from memory.JsonFileSemanticEmbeddingCache import JsonFileSemanticEmbeddingCache


class JsonFileSemanticEmbeddingCacheTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
