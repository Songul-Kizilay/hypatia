"""Atomic versioned persistence for durable human plan authorizations.

An eighth separate store, following the hypothesis store pattern exactly. Runs,
executions, background tasks, curiosity questions, reflections, lessons, and
hypotheses are untouched, so no migration runs and deleting this file simply
means no recorded approvals.

Records are append-only and immutable in practice: the service never rewrites
one, because an approval is a statement about a moment and editing it would
make the record disagree with the decision it claims to preserve.

Loading recreates nothing. A stored approval keeps the exact times it was given,
so an expired approval is still expired after a restart. Refreshing either
timestamp on load would silently turn persistence into renewal, which is the
one thing a durable approval must never do.

Every field is validated on the way back in through the same domain
constructor, so a hand-edited file cannot widen a capability set, alter a
disclosure decision, extend an expiry, or substitute a digest. A malformed
document fails closed rather than being repaired into something plausible.

Version 2 adds consumption. Version 1 documents are still read, as unconsumed,
because that is what they truthfully were: nothing could spend an approval when
they were written. Refusing them would not be safer — it would make an existing
store unreadable at startup, which is a worse failure than accepting a fact that
is already true. Anything newer than this file understands fails closed.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from core.Exceptions import ResearchError
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchPlanAuthorization import ResearchPlanAuthorization
from research.ResearchPlanAuthorizationConsumption import (
    ResearchPlanAuthorizationConsumption,
)
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

MAX_AUTHORIZATION_STORE_BYTES = 4 * 1024 * 1024

#: Matching the hypothesis, curiosity, and vulnerability stores. An approval is
#: small, and five hundred of them is far more history than one operator can
#: review — which is the number that matters, not what the disk could hold.
MAX_AUTHORIZATION_STORE_ENTRIES = 500

_SCHEMA_VERSION = 3
_READABLE_SCHEMA_VERSIONS = frozenset({1, 2, 3})
_DOCUMENT_FIELDS = frozenset({"schema_version", "authorizations"})
_ENTRY_FIELDS = frozenset(
    {
        "authorization_id",
        "plan_digest",
        "research_run_id",
        "capabilities",
        "approved_restrictions",
        "budget",
        "disclosure",
        "authorized_by",
        "authorized_at",
        "expires_at",
        "consumption",
    }
)
#: Version 3 added the approved restrictions. Earlier records are read with
#: none, which is what they truthfully had: nothing could record a typed
#: restriction when they were written. Reading a missing set as "restricted"
#: would invent an approval nobody gave, and reading it as a wildcard would be
#: worse; an empty set is simply the fact.
_ENTRY_FIELDS_V2 = _ENTRY_FIELDS - {"approved_restrictions"}
#: Version 1 wrote every field above except consumption and restrictions.
_ENTRY_FIELDS_V1 = _ENTRY_FIELDS_V2 - {"consumption"}
_CONSUMPTION_FIELDS = frozenset({"execution_id", "consumed_at"})
_BUDGET_FIELDS = frozenset(
    {
        "max_step_advances",
        "max_network_operations",
        "max_llm_operations",
        "max_seconds",
    }
)


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
        if self._byte_count + encoded_size > MAX_AUTHORIZATION_STORE_BYTES:
            raise OverflowError("Authorization store byte limit exceeded.")
        written = self._stream.write(encoded)
        if written != encoded_size:
            raise OSError("Authorization store temporary write was incomplete.")
        self._byte_count += encoded_size
        return len(value)


class JsonFileResearchPlanAuthorizationStore:
    """Load and atomically replace a strict versioned authorization document."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchPlanAuthorization]:
        """Return validated authorizations, or an empty list when absent."""
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                encoded_document = file.read(MAX_AUTHORIZATION_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError("Unable to read the authorization store.") from error
        if len(encoded_document) > MAX_AUTHORIZATION_STORE_BYTES:
            raise ResearchError("The authorization store is too large.")
        try:
            document = json.loads(encoded_document)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Unable to read the authorization store.") from error
        return self._parse_document(document)

    def save(self, authorizations: list[ResearchPlanAuthorization]) -> None:
        """Atomically replace the complete authorization document."""
        self._validate(authorizations)
        document = {
            "schema_version": _SCHEMA_VERSION,
            "authorizations": [self._serialize(entry) for entry in authorizations],
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
            raise ResearchError("The authorization store is too large.") from error
        except (OSError, TypeError, ValueError) as error:
            raise ResearchError("Unable to write the authorization store.") from error
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
    def _serialize(entry: ResearchPlanAuthorization) -> dict[str, Any]:
        return {
            "authorization_id": entry.authorization_id,
            "plan_digest": entry.plan_digest,
            "research_run_id": entry.research_run_id,
            # Sorted so one authorization always serializes identically, which
            # a set's iteration order would not guarantee.
            "approved_restrictions": sorted(
                restriction.value for restriction in entry.approved_restrictions
            ),
            "capabilities": sorted(
                capability.value for capability in entry.capabilities
            ),
            "budget": {
                "max_step_advances": entry.budget.max_step_advances,
                "max_network_operations": entry.budget.max_network_operations,
                "max_llm_operations": entry.budget.max_llm_operations,
                "max_seconds": entry.budget.max_seconds,
            },
            "disclosure": entry.disclosure.value,
            "authorized_by": entry.authorized_by.value,
            "authorized_at": entry.authorized_at.isoformat(),
            "expires_at": entry.expires_at.isoformat(),
            "consumption": (
                None
                if entry.consumption is None
                else {
                    "execution_id": entry.consumption.execution_id,
                    "consumed_at": entry.consumption.consumed_at.isoformat(),
                }
            ),
        }

    def _parse_document(self, document: object) -> list[ResearchPlanAuthorization]:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("The authorization document is invalid.")
        if document["schema_version"] not in _READABLE_SCHEMA_VERSIONS:
            raise ResearchError(
                "The authorization store schema version is not supported."
            )
        entries_value = document["authorizations"]
        if not isinstance(entries_value, list):
            raise ResearchError("Authorization store entries must be a list.")
        if len(entries_value) > MAX_AUTHORIZATION_STORE_ENTRIES:
            raise ResearchError("The authorization store has too many entries.")
        entries = [self._parse_entry(value) for value in entries_value]
        self._validate(entries)
        return entries

    @staticmethod
    def _parse_entry(document: object) -> ResearchPlanAuthorization:
        if not isinstance(document, dict) or set(document) not in (
            _ENTRY_FIELDS,
            _ENTRY_FIELDS_V2,
            _ENTRY_FIELDS_V1,
        ):
            raise ResearchError("An authorization document is invalid.")
        store = JsonFileResearchPlanAuthorizationStore
        return ResearchPlanAuthorization(
            authorization_id=store._text(document["authorization_id"]),
            plan_digest=store._text(document["plan_digest"]),
            research_run_id=store._text(document["research_run_id"]),
            capabilities=store._capabilities(document["capabilities"]),
            approved_restrictions=store._restrictions(
                document.get("approved_restrictions", [])
            ),
            budget=store._budget(document["budget"]),
            disclosure=store._member(
                ResearchDisclosure,
                document["disclosure"],
                "disclosure",
            ),
            authorized_by=store._member(
                ResearchAuthorizer,
                document["authorized_by"],
                "authority",
            ),
            authorized_at=store._timestamp(document["authorized_at"]),
            expires_at=store._timestamp(document["expires_at"]),
            consumption=store._consumption(document.get("consumption")),
        )

    @staticmethod
    def _consumption(
        value: object,
    ) -> ResearchPlanAuthorizationConsumption | None:
        """Read a consumption record, refusing a partial or unknown shape."""
        if value is None:
            return None
        if not isinstance(value, dict) or set(value) != _CONSUMPTION_FIELDS:
            raise ResearchError("An authorization consumption record is invalid.")
        store = JsonFileResearchPlanAuthorizationStore
        return ResearchPlanAuthorizationConsumption(
            execution_id=store._text(value["execution_id"]),
            consumed_at=store._timestamp(value["consumed_at"]),
        )

    @staticmethod
    def _capabilities(value: object) -> frozenset[ResearchPlanStepCapability]:
        if not isinstance(value, list) or not all(
            isinstance(entry, str) for entry in value
        ):
            raise ResearchError("An authorization capability list is invalid.")
        try:
            return frozenset(ResearchPlanStepCapability(entry) for entry in value)
        except ValueError as error:
            raise ResearchError("An authorization capability is invalid.") from error

    @staticmethod
    def _restrictions(value: object) -> frozenset[ResearchPlanRestriction]:
        if not isinstance(value, list) or not all(
            isinstance(entry, str) for entry in value
        ):
            raise ResearchError("An authorization restriction list is invalid.")
        try:
            return frozenset(ResearchPlanRestriction(entry) for entry in value)
        except ValueError as error:
            raise ResearchError("An authorization restriction is invalid.") from error

    @staticmethod
    def _budget(value: object) -> ResearchAutonomyBudget:
        if not isinstance(value, dict) or set(value) != _BUDGET_FIELDS:
            raise ResearchError("An authorization budget document is invalid.")
        for name in (
            "max_step_advances",
            "max_network_operations",
            "max_llm_operations",
        ):
            entry = value[name]
            if isinstance(entry, bool) or not isinstance(entry, int):
                raise ResearchError("An authorization budget value is invalid.")
        seconds = value["max_seconds"]
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise ResearchError("An authorization budget value is invalid.")
        return ResearchAutonomyBudget(
            max_step_advances=value["max_step_advances"],
            max_network_operations=value["max_network_operations"],
            max_llm_operations=value["max_llm_operations"],
            max_seconds=float(seconds),
        )

    @staticmethod
    def _member(enumeration: Any, value: object, label: str) -> Any:
        if not isinstance(value, str):
            raise ResearchError(f"An authorization {label} is invalid.")
        try:
            return enumeration(value)
        except ValueError as error:
            raise ResearchError(f"An authorization {label} is invalid.") from error

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("An authorization text field cannot be empty.")
        return value

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("An authorization timestamp is invalid.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError("An authorization timestamp is invalid.") from error
        if parsed.utcoffset() is None:
            raise ResearchError("An authorization timestamp must be timezone-aware.")
        return parsed

    @staticmethod
    def _validate(authorizations: list[ResearchPlanAuthorization]) -> None:
        if not isinstance(authorizations, list) or not all(
            isinstance(entry, ResearchPlanAuthorization) for entry in authorizations
        ):
            raise ResearchError("The authorization store accepts authorizations.")
        if len(authorizations) > MAX_AUTHORIZATION_STORE_ENTRIES:
            raise ResearchError("The authorization store has too many entries.")
        identifiers = [entry.authorization_id for entry in authorizations]
        if len(identifiers) != len(set(identifiers)):
            raise ResearchError("The authorization store has duplicate identities.")
