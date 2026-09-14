"""Atomic versioned persistence for research-plan execution snapshots.

Stage 2 of execution persistence. Deliberately a separate store: `ResearchRun`
and its schema are untouched, so every existing snapshot stays valid and no
migration of existing data is required. Removing this file returns the runtime
to purely ephemeral execution.

The store persists only execution bookkeeping. Research facts live in the run
store and are never duplicated here.

Write behavior follows the existing research-run store exactly: a bounded
temporary file in the destination directory, flushed and fsynced, then moved
into place with `os.replace`. A failed write therefore leaves the previous
snapshot intact rather than a partial document.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from core.Exceptions import ResearchError
from research.ResearchPlanExecutionCodec import (
    decode_execution_snapshot,
    encode_execution_snapshot,
)
from research.ResearchPlanExecutionSnapshot import ResearchPlanExecutionSnapshot

MAX_RESEARCH_EXECUTION_STORE_BYTES = 8 * 1024 * 1024
MAX_RESEARCH_EXECUTION_STORE_EXECUTIONS = 1_000

_SCHEMA_VERSION = 2
_READABLE_SCHEMA_VERSIONS = frozenset({1, 2})
_DOCUMENT_FIELDS = frozenset({"schema_version", "executions"})


class _BinaryWriter(Protocol):
    def write(self, value: bytes) -> int: ...


class _BoundedUtf8Writer:
    """Stop temporary JSON output before its UTF-8 byte budget is exceeded."""

    def __init__(self, stream: _BinaryWriter) -> None:
        self._stream = stream
        self._byte_count = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        encoded_size = len(encoded)
        if self._byte_count + encoded_size > MAX_RESEARCH_EXECUTION_STORE_BYTES:
            raise OverflowError("Research execution store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Research execution store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileResearchExecutionStore:
    """Load and atomically replace a strict versioned execution document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchPlanExecutionSnapshot]:
        """Return validated snapshots, or an empty list when absent.

        An absent file means no persisted executions, which is exactly the
        behavior of a runtime with persistence disabled. A malformed or
        unreadable file raises rather than being silently treated as empty,
        because silently discarding it would hide execution history.
        """
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_RESEARCH_EXECUTION_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError(
                f"Unable to read research execution store '{self._path}'."
            ) from error
        if len(encoded_document) > MAX_RESEARCH_EXECUTION_STORE_BYTES:
            raise ResearchError(
                f"Research execution store '{self._path}' is too large."
            )
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError(
                f"Unable to read research execution store '{self._path}'."
            ) from error
        return self._parse_document(document)

    def save(self, snapshots: list[ResearchPlanExecutionSnapshot]) -> None:
        """Atomically replace the complete execution snapshot document."""
        self._validate_snapshots(snapshots)
        document = {
            "schema_version": _SCHEMA_VERSION,
            "executions": [
                encode_execution_snapshot(snapshot) for snapshot in snapshots
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
            temporary_path = None
        except OverflowError as error:
            raise ResearchError(
                f"Research execution store '{self._path}' is too large."
            ) from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError(
                f"Unable to write research execution store '{self._path}'."
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _parse_document(
        self,
        document: object,
    ) -> list[ResearchPlanExecutionSnapshot]:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError(
                f"Research execution store '{self._path}' document is invalid."
            )
        if document["schema_version"] not in _READABLE_SCHEMA_VERSIONS:
            raise ResearchError(
                f"Research execution store '{self._path}' schema version "
                "is not supported."
            )
        executions = document["executions"]
        if not isinstance(executions, list):
            raise ResearchError(
                f"Research execution store '{self._path}' executions must be a list."
            )
        if len(executions) > MAX_RESEARCH_EXECUTION_STORE_EXECUTIONS:
            raise ResearchError(
                f"Research execution store '{self._path}' has too many executions."
            )
        snapshots = [decode_execution_snapshot(value) for value in executions]
        self._validate_snapshots(snapshots)
        return snapshots

    def _validate_snapshots(
        self,
        snapshots: list[ResearchPlanExecutionSnapshot],
    ) -> None:
        if not isinstance(snapshots, list):
            raise ResearchError("Research execution store accepts a list.")
        if len(snapshots) > MAX_RESEARCH_EXECUTION_STORE_EXECUTIONS:
            raise ResearchError("Research execution store has too many executions.")
        if not all(
            isinstance(snapshot, ResearchPlanExecutionSnapshot)
            for snapshot in snapshots
        ):
            raise ResearchError("Research execution store accepts only snapshots.")
        plan_ids = [snapshot.plan_id for snapshot in snapshots]
        if len(plan_ids) != len(set(plan_ids)):
            raise ResearchError("Research execution store has duplicate execution IDs.")
