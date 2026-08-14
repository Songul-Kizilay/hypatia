"""Atomic local JSON cache for optional derived semantic embeddings."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from core.Exceptions import MemoryError
from memory.Embedding import Embedding


class JsonFileSemanticEmbeddingCache:
    """Persist model-scoped embeddings without changing the memory-store schema."""

    _SCHEMA_VERSION = 1

    def __init__(self, path: Path, provider_key: str) -> None:
        if not provider_key.strip():
            raise ValueError("Semantic embedding cache provider key cannot be empty.")
        self._path = path
        self._provider_key = provider_key
        self._entries: dict[str, tuple[str, Embedding]] | None = None

    def get(self, memory_id: str, source_text: str) -> Embedding | None:
        """Return an embedding only when the source content fingerprint matches."""
        entry = self._load_entries().get(memory_id)
        if entry is None:
            return None
        content_hash, embedding = entry
        return embedding if content_hash == self._content_hash(source_text) else None

    def replace(
        self,
        entries: tuple[tuple[str, str, Embedding], ...],
    ) -> None:
        """Atomically save a complete, validated cache snapshot."""
        replacement = self._entries_from_tuples(entries)
        self._save_entries(replacement)
        self._entries = replacement

    def upsert(self, memory_id: str, source_text: str, embedding: Embedding) -> None:
        """Add or replace one validated entry for the active provider key."""
        self._validate_memory_id(memory_id)
        if not isinstance(embedding, Embedding):
            raise ValueError("Semantic embedding cache requires an Embedding.")
        entries = dict(self._load_entries())
        entries[memory_id] = (self._content_hash(source_text), embedding)
        self._save_entries(entries)
        self._entries = entries

    def remove(self, memory_id: str) -> None:
        """Remove an entry when present without writing an unnecessary snapshot."""
        self._validate_memory_id(memory_id)
        entries = dict(self._load_entries())
        if memory_id not in entries:
            return
        entries.pop(memory_id)
        self._save_entries(entries)
        self._entries = entries

    def _load_entries(self) -> dict[str, tuple[str, Embedding]]:
        if self._entries is not None:
            return self._entries
        if not self._path.exists():
            self._entries = {}
            return self._entries

        try:
            with self._path.open(encoding="utf-8") as file:
                document = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MemoryError(
                f"Unable to read semantic embedding cache '{self._path}': {error}"
            ) from error

        self._entries = self._parse_document(document)
        return self._entries

    def _parse_document(self, document: Any) -> dict[str, tuple[str, Embedding]]:
        if not isinstance(document, dict):
            raise MemoryError(
                f"Semantic embedding cache '{self._path}' must contain an object."
            )
        if document.get("schema_version") != self._SCHEMA_VERSION:
            raise MemoryError(
                "Semantic embedding cache "
                f"'{self._path}' has an unsupported schema version."
            )
        if document.get("provider_key") != self._provider_key:
            return {}
        raw_entries = document.get("entries")
        if not isinstance(raw_entries, list):
            raise MemoryError(
                f"Semantic embedding cache '{self._path}' entries must be a list."
            )

        entries: dict[str, tuple[str, Embedding]] = {}
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, dict):
                raise MemoryError(
                    "Semantic embedding cache "
                    f"'{self._path}' contains an invalid entry."
                )
            memory_id = raw_entry.get("memory_id")
            content_hash = raw_entry.get("content_sha256")
            values = raw_entry.get("embedding")
            try:
                if not isinstance(memory_id, str):
                    raise ValueError("invalid memory ID")
                self._validate_memory_id(memory_id)
                if (
                    not isinstance(content_hash, str)
                    or len(content_hash) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in content_hash
                    )
                ):
                    raise ValueError("invalid content hash")
                if not isinstance(values, list):
                    raise ValueError("invalid embedding")
                embedding = Embedding(tuple(values))
            except ValueError as error:
                raise MemoryError(
                    "Semantic embedding cache "
                    f"'{self._path}' contains an invalid entry."
                ) from error
            if memory_id in entries:
                raise MemoryError(
                    "Semantic embedding cache "
                    f"'{self._path}' contains duplicate memory IDs."
                )
            entries[memory_id] = (content_hash, embedding)
        return entries

    def _entries_from_tuples(
        self,
        entries: tuple[tuple[str, str, Embedding], ...],
    ) -> dict[str, tuple[str, Embedding]]:
        replacement: dict[str, tuple[str, Embedding]] = {}
        for memory_id, source_text, embedding in entries:
            self._validate_memory_id(memory_id)
            if not isinstance(embedding, Embedding):
                raise ValueError("Semantic embedding cache requires an Embedding.")
            if memory_id in replacement:
                raise ValueError(
                    "Semantic embedding cache entries must have unique memory IDs."
                )
            replacement[memory_id] = (self._content_hash(source_text), embedding)
        return replacement

    def _save_entries(self, entries: dict[str, tuple[str, Embedding]]) -> None:
        document = {
            "schema_version": self._SCHEMA_VERSION,
            "provider_key": self._provider_key,
            "entries": [
                {
                    "memory_id": memory_id,
                    "content_sha256": content_hash,
                    "embedding": list(embedding.values),
                }
                for memory_id, (content_hash, embedding) in sorted(entries.items())
            ],
        }
        temporary_path: Path | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(document, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._path)
        except (OSError, OverflowError, TypeError, ValueError) as error:
            raise MemoryError(
                f"Unable to write semantic embedding cache '{self._path}': {error}"
            ) from error
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _content_hash(source_text: str) -> str:
        if not isinstance(source_text, str):
            raise ValueError("Semantic embedding cache source text must be a string.")
        return hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_memory_id(memory_id: object) -> None:
        if (
            not isinstance(memory_id, str)
            or not memory_id
            or memory_id != memory_id.strip()
        ):
            raise ValueError("Semantic embedding cache requires a non-empty memory ID.")
