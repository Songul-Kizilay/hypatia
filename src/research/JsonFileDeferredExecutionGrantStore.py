"""Atomic strict persistence for trusted-desktop deferred grants."""

from __future__ import annotations

import json
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol, TypeVar

from core.Exceptions import ResearchError
from research.DeferredExecutionGrant import DeferredExecutionGrant
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchPlanRestriction import ResearchPlanRestriction
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

MAX_DEFERRED_GRANT_STORE_BYTES = 4 * 1024 * 1024
MAX_DEFERRED_GRANT_STORE_ENTRIES = 500
_SCHEMA_VERSION = 2
_DOCUMENT_FIELDS = frozenset({"schema_version", "grants"})
_ENTRY_FIELDS = frozenset(
    {
        "grant_id",
        "task_id",
        "execution_id",
        "plan_digest",
        "capabilities",
        "task_budget",
        "granted_at",
        "granted_by",
        "revoked_at",
        "revoked_by",
        "approved_restrictions",
    }
)
#: Version 1 recorded no restrictions. Those entries load as unrecorded rather
#: than as an empty set, because an empty set is a claim and the record never
#: made it.
_ENTRY_FIELDS_V1 = _ENTRY_FIELDS - {"approved_restrictions"}

#: The declared version decides which shape is legal, rather than the shape
#: deciding what the record apparently means. Reading it the other way round
#: let a document call itself version 1 while carrying the version 2 field, and
#: be believed about a restriction that version could never have recorded.
_ENTRY_FIELDS_BY_VERSION = {1: _ENTRY_FIELDS_V1, 2: _ENTRY_FIELDS}
#: Derived, so a version added without a declared shape is unreadable rather
#: than silently accepting whatever turns up.
_READABLE_SCHEMA_VERSIONS = frozenset(_ENTRY_FIELDS_BY_VERSION)
_BUDGET_FIELDS = frozenset(
    {
        "max_step_advances",
        "max_network_operations",
        "max_llm_operations",
        "max_seconds",
    }
)
_EnumT = TypeVar("_EnumT", bound=Enum)


class _BinaryWriter(Protocol):
    def write(self, value: bytes) -> int: ...


class _BoundedUtf8Writer:
    def __init__(self, stream: _BinaryWriter) -> None:
        self._stream = stream
        self._byte_count = 0

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8")
        if self._byte_count + len(encoded) > MAX_DEFERRED_GRANT_STORE_BYTES:
            raise OverflowError
        written = self._stream.write(encoded)
        if written != len(encoded):
            raise OSError("Deferred grant temporary write was incomplete.")
        self._byte_count += written
        return len(value)


class JsonFileDeferredExecutionGrantStore:
    """Load and atomically replace a bounded grant history."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[DeferredExecutionGrant]:
        if not self._path.exists():
            return []
        try:
            with self._path.open("rb") as file:
                payload = file.read(MAX_DEFERRED_GRANT_STORE_BYTES + 1)
        except OSError as error:
            raise ResearchError("Unable to read deferred execution grants.") from error
        if len(payload) > MAX_DEFERRED_GRANT_STORE_BYTES:
            raise ResearchError("Deferred execution grant store is too large.")
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Unable to read deferred execution grants.") from error
        return self._parse_document(document)

    def save(self, grants: list[DeferredExecutionGrant]) -> None:
        self._validate(grants)
        document = {
            "schema_version": _SCHEMA_VERSION,
            "grants": [self._serialize(grant) for grant in grants],
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
                bounded = _BoundedUtf8Writer(file)
                json.dump(document, bounded, ensure_ascii=False, indent=2)
                bounded.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._path)
            temporary_path = None
        except (OSError, OverflowError, TypeError, ValueError) as error:
            raise ResearchError("Unable to write deferred execution grants.") from error
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
    def _serialize(grant: DeferredExecutionGrant) -> dict[str, Any]:
        budget = grant.task_budget
        return {
            "grant_id": grant.grant_id,
            "task_id": grant.task_id,
            "execution_id": grant.execution_id,
            "plan_digest": grant.plan_digest,
            "capabilities": sorted(value.value for value in grant.capabilities),
            "approved_restrictions": (
                None
                if grant.approved_restrictions is None
                else sorted(value.value for value in grant.approved_restrictions)
            ),
            "task_budget": {
                "max_step_advances": budget.max_step_advances,
                "max_network_operations": budget.max_network_operations,
                "max_llm_operations": budget.max_llm_operations,
                "max_seconds": budget.max_seconds,
            },
            "granted_at": grant.granted_at.isoformat(),
            "granted_by": grant.granted_by.value,
            "revoked_at": (
                grant.revoked_at.isoformat() if grant.revoked_at is not None else None
            ),
            "revoked_by": (
                grant.revoked_by.value if grant.revoked_by is not None else None
            ),
        }

    def _parse_document(self, document: object) -> list[DeferredExecutionGrant]:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ResearchError("Deferred execution grant document is invalid.")
        if document["schema_version"] not in _READABLE_SCHEMA_VERSIONS:
            raise ResearchError("Deferred execution grant schema is unsupported.")
        values = document["grants"]
        if not isinstance(values, list):
            raise ResearchError("Deferred execution grants must be a list.")
        version = document["schema_version"]
        grants = [self._parse_entry(value, version) for value in values]
        self._validate(grants)
        return grants

    @staticmethod
    def _parse_entry(document: object, version: int) -> DeferredExecutionGrant:
        """Decode one entry against the shape its document declared.

        Exactly that shape: a field the declared version never wrote is as
        wrong as a missing one, so neither is read past.
        """
        if (
            not isinstance(document, dict)
            or set(document) != _ENTRY_FIELDS_BY_VERSION[version]
        ):
            raise ResearchError("A deferred execution grant is invalid.")
        budget = document["task_budget"]
        if not isinstance(budget, dict) or set(budget) != _BUDGET_FIELDS:
            raise ResearchError("A deferred execution task budget is invalid.")
        capabilities = document["capabilities"]
        if not isinstance(capabilities, list):
            raise ResearchError("Deferred execution capabilities are invalid.")
        store = JsonFileDeferredExecutionGrantStore
        return DeferredExecutionGrant(
            grant_id=store._text(document["grant_id"]),
            task_id=store._text(document["task_id"]),
            execution_id=store._text(document["execution_id"]),
            plan_digest=store._text(document["plan_digest"]),
            capabilities=frozenset(
                store._member(
                    ResearchPlanStepCapability,
                    value,
                    "capability",
                )
                for value in capabilities
            ),
            approved_restrictions=store._restrictions(
                document.get("approved_restrictions")
            ),
            task_budget=ResearchAutonomyBudget(**budget),
            granted_at=store._timestamp(document["granted_at"]),
            granted_by=store._member(
                DeferredGrantAuthorizer,
                document["granted_by"],
                "provenance",
            ),
            revoked_at=(
                None
                if document["revoked_at"] is None
                else store._timestamp(document["revoked_at"])
            ),
            revoked_by=(
                None
                if document["revoked_by"] is None
                else store._member(
                    DeferredGrantAuthorizer,
                    document["revoked_by"],
                    "revocation provenance",
                )
            ),
        )

    @staticmethod
    def _restrictions(value: object) -> frozenset[ResearchPlanRestriction] | None:
        """Read a recorded set, or ``None`` where none was ever recorded."""
        if value is None:
            return None
        if not isinstance(value, list):
            raise ResearchError("Deferred execution restrictions are invalid.")
        store = JsonFileDeferredExecutionGrantStore
        return frozenset(
            store._member(ResearchPlanRestriction, entry, "restriction")
            for entry in value
        )

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str):
            raise ResearchError("Deferred execution text is invalid.")
        return value

    @staticmethod
    def _timestamp(value: object) -> datetime:
        if not isinstance(value, str):
            raise ResearchError("Deferred execution timestamp is invalid.")
        try:
            return datetime.fromisoformat(value)
        except ValueError as error:
            raise ResearchError("Deferred execution timestamp is invalid.") from error

    @staticmethod
    def _member(enum_type: type[_EnumT], value: object, label: str) -> _EnumT:
        if not isinstance(value, str):
            raise ResearchError(f"Deferred execution {label} is invalid.")
        try:
            return enum_type(value)
        except ValueError as error:
            raise ResearchError(f"Deferred execution {label} is invalid.") from error

    @staticmethod
    def _validate(grants: list[DeferredExecutionGrant]) -> None:
        if not isinstance(grants, list) or not all(
            isinstance(grant, DeferredExecutionGrant) for grant in grants
        ):
            raise ResearchError("Deferred execution store accepts only grants.")
        if len(grants) > MAX_DEFERRED_GRANT_STORE_ENTRIES:
            raise ResearchError("Deferred execution grant store has too many entries.")
        ids = [grant.grant_id for grant in grants]
        if len(ids) != len(set(ids)):
            raise ResearchError("Deferred execution grant IDs must be unique.")
        active_tasks = [grant.task_id for grant in grants if grant.active]
        if len(active_tasks) != len(set(active_tasks)):
            raise ResearchError("A task has multiple active deferred grants.")
