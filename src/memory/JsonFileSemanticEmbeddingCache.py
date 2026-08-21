"""Atomic local JSON cache for optional derived semantic embeddings."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import MemoryError
from memory.Embedding import MAX_EMBEDDING_DIMENSION, Embedding
from memory.EmbeddingProvider import MAX_EMBEDDING_SOURCE_TEXT_CHARACTERS

MAX_SEMANTIC_EMBEDDING_CACHE_BYTES = 64 * 1024 * 1024
MAX_SEMANTIC_EMBEDDING_CACHE_ENTRIES = 20_000
MAX_SEMANTIC_EMBEDDING_CACHE_PROVIDER_KEY_CHARACTERS = 1_024
MAX_SEMANTIC_EMBEDDING_CACHE_MEMORY_ID_CHARACTERS = 1_024
MAX_SEMANTIC_EMBEDDING_CACHE_SOURCE_TEXT_CHARACTERS = (
    MAX_EMBEDDING_SOURCE_TEXT_CHARACTERS
)
MAX_SEMANTIC_EMBEDDING_CACHE_DIMENSION = MAX_EMBEDDING_DIMENSION
MAX_SEMANTIC_EMBEDDING_CACHE_VALUES = 4_000_000


class _BinaryWriter(Protocol):
    def write(self, value: bytes) -> int: ...


class _BoundedUtf8Writer:
    """Write exact UTF-8 bytes without exceeding the cache limit."""

    def __init__(self, stream: _BinaryWriter) -> None:
        self._stream = stream
        self._byte_count = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        encoded_size = len(encoded)
        if self._byte_count + encoded_size > MAX_SEMANTIC_EMBEDDING_CACHE_BYTES:
            raise OverflowError("Semantic embedding cache byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Semantic embedding cache temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileSemanticEmbeddingCache:
    """Persist model-scoped embeddings without changing the memory-store schema."""

    _SCHEMA_VERSION = 1

    def __init__(self, path: Path, provider_key: str) -> None:
        self._validate_provider_key(provider_key)
        self._path = path
        self._provider_key = provider_key
        self._entries: dict[str, tuple[str, Embedding]] | None = None

    def get(self, memory_id: str, source_text: str) -> Embedding | None:
        """Return an embedding only when the source content fingerprint matches."""
        self._validate_memory_id(memory_id)
        expected_content_hash = self._content_hash(source_text)
        entry = self._load_entries().get(memory_id)
        if entry is None:
            return None
        content_hash, embedding = entry
        return embedding if content_hash == expected_content_hash else None

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
        content_hash = self._content_hash(source_text)
        self._validate_embedding(embedding)
        entries = dict(self._load_entries())
        entries[memory_id] = (content_hash, embedding)
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
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_SEMANTIC_EMBEDDING_CACHE_BYTES + 1)
        except FileNotFoundError:
            self._entries = {}
            return self._entries
        except OSError as error:
            raise MemoryError(
                f"Unable to read semantic embedding cache '{self._path}': {error}"
            ) from error
        if len(encoded_document) > MAX_SEMANTIC_EMBEDDING_CACHE_BYTES:
            raise MemoryError(f"Semantic embedding cache '{self._path}' is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
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
        schema_version = document.get("schema_version")
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != self._SCHEMA_VERSION
        ):
            raise MemoryError(
                "Semantic embedding cache "
                f"'{self._path}' has an unsupported schema version."
            )
        persisted_provider_key = document.get("provider_key")
        try:
            self._validate_provider_key(persisted_provider_key)
        except ValueError as error:
            raise MemoryError(
                f"Semantic embedding cache '{self._path}' has an invalid provider key."
            ) from error
        if persisted_provider_key != self._provider_key:
            self._entries = {}
            return self._entries
        raw_entries = document.get("entries")
        if not isinstance(raw_entries, list):
            raise MemoryError(
                f"Semantic embedding cache '{self._path}' entries must be a list."
            )
        if len(raw_entries) > MAX_SEMANTIC_EMBEDDING_CACHE_ENTRIES:
            raise MemoryError(
                f"Semantic embedding cache '{self._path}' has too many entries."
            )

        entries: dict[str, tuple[str, Embedding]] = {}
        embedding_dimension: int | None = None
        embedding_value_count = 0
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
                self._validate_content_hash(content_hash)
                assert isinstance(content_hash, str)
                if not isinstance(values, list):
                    raise ValueError("invalid embedding")
                if len(values) > MAX_SEMANTIC_EMBEDDING_CACHE_DIMENSION:
                    raise ValueError("embedding dimension is too large")
                embedding_value_count += len(values)
                if embedding_value_count > MAX_SEMANTIC_EMBEDDING_CACHE_VALUES:
                    raise ValueError("too many embedding values")
                embedding = Embedding(tuple(values))
                self._validate_embedding(embedding)
                if embedding_dimension is None:
                    embedding_dimension = embedding.dimension
                elif embedding.dimension != embedding_dimension:
                    raise ValueError("inconsistent embedding dimension")
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
        if not isinstance(entries, tuple):
            raise ValueError("Semantic embedding cache replacement must be a tuple.")
        if len(entries) > MAX_SEMANTIC_EMBEDDING_CACHE_ENTRIES:
            raise ValueError("Semantic embedding cache has too many entries.")
        replacement: dict[str, tuple[str, Embedding]] = {}
        for memory_id, source_text, embedding in entries:
            self._validate_memory_id(memory_id)
            self._validate_embedding(embedding)
            if memory_id in replacement:
                raise ValueError(
                    "Semantic embedding cache entries must have unique memory IDs."
                )
            replacement[memory_id] = (self._content_hash(source_text), embedding)
        self._validate_entries(replacement)
        return replacement

    def _save_entries(self, entries: dict[str, tuple[str, Embedding]]) -> None:
        self._validate_entries(entries)
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
                mode="wb",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                bounded_file = _BoundedUtf8Writer(file)
                json.dump(document, bounded_file, ensure_ascii=False, indent=2)
                bounded_file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._path)
        except OverflowError as error:
            raise MemoryError(
                f"Semantic embedding cache '{self._path}' is too large."
            ) from error
        except (OSError, RecursionError, TypeError, ValueError) as error:
            raise MemoryError(
                f"Unable to write semantic embedding cache '{self._path}': {error}"
            ) from error
        finally:
            self._remove_temporary_file(temporary_path)

    def _validate_entries(
        self,
        entries: dict[str, tuple[str, Embedding]],
    ) -> None:
        if not isinstance(entries, dict):
            raise ValueError("Semantic embedding cache entries must be a dictionary.")
        if len(entries) > MAX_SEMANTIC_EMBEDDING_CACHE_ENTRIES:
            raise ValueError("Semantic embedding cache has too many entries.")

        embedding_dimension: int | None = None
        embedding_value_count = 0
        for memory_id, entry in entries.items():
            self._validate_memory_id(memory_id)
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError("Semantic embedding cache contains an invalid entry.")
            content_hash, embedding = entry
            self._validate_content_hash(content_hash)
            self._validate_embedding(embedding)
            embedding_value_count += embedding.dimension
            if embedding_value_count > MAX_SEMANTIC_EMBEDDING_CACHE_VALUES:
                raise ValueError("Semantic embedding cache has too many values.")
            if embedding_dimension is None:
                embedding_dimension = embedding.dimension
            elif embedding.dimension != embedding_dimension:
                raise ValueError(
                    "Semantic embedding cache dimensions must be consistent."
                )

    @staticmethod
    def _content_hash(source_text: str) -> str:
        if not isinstance(source_text, str):
            raise ValueError("Semantic embedding cache source text must be a string.")
        if len(source_text) > MAX_SEMANTIC_EMBEDDING_CACHE_SOURCE_TEXT_CHARACTERS:
            raise ValueError("Semantic embedding cache source text is too long.")
        return hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_memory_id(memory_id: object) -> None:
        if (
            not isinstance(memory_id, str)
            or not memory_id
            or memory_id != memory_id.strip()
        ):
            raise ValueError("Semantic embedding cache requires a non-empty memory ID.")
        if len(memory_id) > MAX_SEMANTIC_EMBEDDING_CACHE_MEMORY_ID_CHARACTERS:
            raise ValueError("Semantic embedding cache memory ID is too long.")

    @staticmethod
    def _validate_provider_key(provider_key: object) -> None:
        if not isinstance(provider_key, str) or not provider_key.strip():
            raise ValueError("Semantic embedding cache provider key cannot be empty.")
        if len(provider_key) > MAX_SEMANTIC_EMBEDDING_CACHE_PROVIDER_KEY_CHARACTERS:
            raise ValueError("Semantic embedding cache provider key is too long.")

    @staticmethod
    def _validate_content_hash(content_hash: object) -> None:
        if (
            not isinstance(content_hash, str)
            or len(content_hash) != 64
            or any(character not in "0123456789abcdef" for character in content_hash)
        ):
            raise ValueError("Semantic embedding cache has an invalid content hash.")

    @staticmethod
    def _validate_embedding(embedding: object) -> None:
        if not isinstance(embedding, Embedding):
            raise ValueError("Semantic embedding cache requires an Embedding.")
        if embedding.dimension > MAX_SEMANTIC_EMBEDDING_CACHE_DIMENSION:
            raise ValueError("Semantic embedding cache dimension is too large.")

    @staticmethod
    def _remove_temporary_file(path: Path | None) -> None:
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
