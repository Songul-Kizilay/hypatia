"""Atomic, fail-closed persistence for consumed Guest-Agent replay identities.

Mirrors `research.JsonFileResearchKaliOperationAuthorizationStore` and
`research.JsonFileOneShotDeferredExecutionScheduleStore` deliberately: the
same strict-document-shape, bounded-bytes, bounded-entries, temp-file +
fsync + atomic-rename write, and exact-field-set parse discipline this
repository already uses for every other durable authority-adjacent record.

A corrupt, truncated, oversized, or schema-mismatched document is never
read as "no nonces were used" -- that would reopen replay for every token
this store ever recorded. `load()` raises on anything it cannot fully
account for, rather than returning an empty list, so a caller cannot
mistake "the store is broken" for "this is the first use."

This store answers only "what has already been consumed, durably." It is
not consulted by, and does not consult, any execution or authorization
path -- it references no gateway, no tool-execution seam, and no
operation-authorization store anywhere in this module.

`lock` exposes one re-entrant lock shared by every instance of this class
constructed against the same resolved file path, process-wide. A caller
that only ever builds one instance per path never notices this; a caller
that (knowingly or not) builds more than one instance addressing the same
file still gets real mutual exclusion between them, because they share
the same lock object rather than each holding a private one. Without this,
two independently-constructed instances racing to update the same file
could each observe "not yet consumed" before either write lands -- the
exact same-process, same-file race
`research.GuestAgentReplayProtector.GuestAgentReplayProtector` exists to
prevent.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock, RLock
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.GuestAgentProtocol import GuestAgentProtocolVersion
from research.GuestAgentReplayNonceRecord import GuestAgentReplayNonceRecord

MAX_GUEST_AGENT_REPLAY_STORE_BYTES = 1024 * 1024
MAX_GUEST_AGENT_REPLAY_STORE_ENTRIES = 500

_SCHEMA_VERSION = 1
_DOCUMENT_FIELDS = frozenset({"schema_version", "records"})
_ENTRY_FIELDS = frozenset(
    {"protocol_version", "operation_digest", "nonce", "request_id", "consumed_at"}
)

_PATH_LOCK_REGISTRY_LOCK = Lock()
_PATH_LOCKS: dict[Path, RLock] = {}


def _shared_lock_for_path(path: Path) -> RLock:
    """Return the one re-entrant lock every store instance for this exact
    resolved path shares, creating it on first use.

    Keyed by the resolved (absolute, symlink-free) path rather than the
    path object as given, so two instances constructed from differently
    spelled but identical paths (relative vs. absolute, for example) still
    share one lock rather than silently getting two.
    """
    resolved = path.resolve()
    with _PATH_LOCK_REGISTRY_LOCK:
        lock = _PATH_LOCKS.get(resolved)
        if lock is None:
            lock = RLock()
            _PATH_LOCKS[resolved] = lock
        return lock


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
        if self._byte_count + encoded_size > MAX_GUEST_AGENT_REPLAY_STORE_BYTES:
            raise OverflowError("Guest-agent replay store limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Guest-agent replay temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileGuestAgentReplayNonceStore:
    """Load and atomically replace a bounded, strict replay-record document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def lock(self) -> RLock:
        """Return the one re-entrant lock every instance for this exact
        resolved path shares, process-wide -- see the module docstring."""
        return _shared_lock_for_path(self._path)

    def load(self) -> list[GuestAgentReplayNonceRecord]:
        """Return validated replay records, or empty when the file is absent.

        An absent file is the one, and only, legitimate way to read "no
        nonces were used yet." Every other failure mode -- truncation,
        corruption, an oversized file, an unrecognized schema version, an
        unknown or missing field -- raises instead of degrading to that
        same empty answer.
        """
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                payload = file.read(MAX_GUEST_AGENT_REPLAY_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError(
                "Unable to read the Guest-agent replay store."
            ) from error
        if len(payload) > MAX_GUEST_AGENT_REPLAY_STORE_BYTES:
            raise ResearchError("The Guest-agent replay store is too large.")
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError(
                "Unable to read the Guest-agent replay store."
            ) from error
        return self._parse_document(document)

    def save(self, records: list[GuestAgentReplayNonceRecord]) -> None:
        """Atomically replace the complete replay-record document."""
        self._validate(records)
        document = {
            "schema_version": _SCHEMA_VERSION,
            "records": [self._serialize(entry) for entry in records],
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
            raise ResearchError("The Guest-agent replay store is too large.") from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError(
                "Unable to write the Guest-agent replay store."
            ) from error
        finally:
            self._remove_temporary_file(temporary_path)

    @staticmethod
    def _remove_temporary_file(path: Path | None) -> None:
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _serialize(entry: GuestAgentReplayNonceRecord) -> dict[str, Any]:
        return {
            "protocol_version": entry.protocol_version.value,
            "operation_digest": entry.operation_digest,
            "nonce": entry.nonce,
            "request_id": entry.request_id,
            "consumed_at": entry.consumed_at.isoformat(),
        }

    def _parse_document(self, document: object) -> list[GuestAgentReplayNonceRecord]:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The Guest-agent replay document is invalid.")
        if document["schema_version"] != _SCHEMA_VERSION:
            raise ResearchError(
                "The Guest-agent replay schema version is not supported."
            )
        entries_value = document["records"]
        if not isinstance(entries_value, list):
            raise ResearchError("Guest-agent replay store entries must be a list.")
        entries = [self._parse_entry(value) for value in entries_value]
        self._validate(entries)
        return entries

    @staticmethod
    def _parse_entry(document: object) -> GuestAgentReplayNonceRecord:
        if not isinstance(document, dict) or set(document) != _ENTRY_FIELDS:
            raise ResearchError("A Guest-agent replay record document is invalid.")
        store = JsonFileGuestAgentReplayNonceStore
        return GuestAgentReplayNonceRecord(
            protocol_version=store._protocol_version(document["protocol_version"]),
            operation_digest=store._text(document["operation_digest"]),
            nonce=store._text(document["nonce"]),
            request_id=store._text(document["request_id"]),
            consumed_at=store._timestamp(document["consumed_at"]),
        )

    @staticmethod
    def _protocol_version(value: object) -> GuestAgentProtocolVersion:
        if not isinstance(value, str):
            raise ResearchError(
                "A Guest-agent replay record protocol version is invalid."
            )
        try:
            return GuestAgentProtocolVersion(value)
        except ValueError as error:
            raise ResearchError(
                "A Guest-agent replay record protocol version is invalid."
            ) from error

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(
                "A Guest-agent replay record text field cannot be empty."
            )
        return value

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("A Guest-agent replay record timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError(
                "A Guest-agent replay record timestamp is invalid."
            ) from error
        if parsed.utcoffset() is None:
            raise ResearchError(
                "A Guest-agent replay record timestamp must be timezone-aware."
            )
        return parsed

    @staticmethod
    def _validate(records: list[GuestAgentReplayNonceRecord]) -> None:
        if not isinstance(records, list) or not all(
            isinstance(entry, GuestAgentReplayNonceRecord) for entry in records
        ):
            raise ResearchError(
                "The Guest-agent replay store accepts only replay records."
            )
        if len(records) > MAX_GUEST_AGENT_REPLAY_STORE_ENTRIES:
            raise ResearchError("The Guest-agent replay store has too many entries.")
        identities = [entry.replay_identity for entry in records]
        if len(identities) != len(set(identities)):
            raise ResearchError(
                "The Guest-agent replay store has duplicate identities."
            )
