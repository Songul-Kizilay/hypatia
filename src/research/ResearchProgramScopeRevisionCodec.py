"""Strict bounded codec for immutable program-scope revision history."""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import UTC, datetime
from typing import Any

from core.Exceptions import ResearchError
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchProgramScopeExecutionPolicy import (
    DEFAULT_PROGRAM_SCOPE_EXECUTION_POLICY,
    ResearchProgramScopeExecutionPolicy,
    execution_policy_digest,
    execution_policy_document,
    parse_execution_policy,
)
from research.ResearchProgramScopeRevision import (
    PROGRAM_SCOPE_CAPABILITIES,
    PROGRAM_SCOPE_TRANSPORT,
    ResearchProgramScopeRevision,
    program_scope_revision_digest,
)
from research.ResearchTargetScopeCodec import (
    decode_target_scope,
    encode_target_scope,
    target_scope_digest,
)

MAX_PROGRAM_SCOPE_REVISION_STORE_BYTES = 4 * 1024 * 1024
MAX_PROGRAM_SCOPE_REVISIONS = 500
PROGRAM_SCOPE_REVISION_SCHEMA_VERSION = 2
_LEGACY_PROGRAM_SCOPE_REVISION_SCHEMA_VERSION = 1

_DOCUMENT_FIELDS = frozenset({"schema_version", "revisions"})
_ENTRY_FIELDS_V1 = frozenset(
    {
        "revision_id",
        "program_id",
        "scope",
        "scope_digest",
        "revision_digest",
        "capabilities",
        "transport",
        "confirmed_at",
        "confirmed_by",
        "expires_at",
        "state",
        "revoked_at",
        "revoked_by",
    }
)
_ENTRY_FIELDS_V2 = _ENTRY_FIELDS_V1 | frozenset(
    {"execution_policy", "execution_policy_digest"}
)
_MODEL_FIELDS = frozenset(
    {
        "revision_id",
        "program_id",
        "scope",
        "confirmed_at",
        "expires_at",
        "execution_policy",
        "revoked_at",
        "revoked_by",
        "scope_digest",
        "execution_policy_digest",
        "revision_digest",
        "capabilities",
        "transport",
        "confirmed_by",
    }
)
_CAPABILITY_FACTS = sorted(value.value for value in PROGRAM_SCOPE_CAPABILITIES)


def encode_program_scope_revisions(
    revisions: list[ResearchProgramScopeRevision],
) -> bytes:
    """Encode a complete, validated history without dropping policy fields."""
    validate_program_scope_revision_history(revisions)
    document = {
        "schema_version": PROGRAM_SCOPE_REVISION_SCHEMA_VERSION,
        "revisions": [_entry_document(revision) for revision in revisions],
    }
    try:
        payload = (
            json.dumps(
                document,
                sort_keys=True,
                ensure_ascii=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ResearchError(
            "Program scope revision history cannot be encoded."
        ) from error
    if len(payload) > MAX_PROGRAM_SCOPE_REVISION_STORE_BYTES:
        raise ResearchError("Program scope revision history is too large.")
    return payload


def decode_program_scope_revisions(
    payload: bytes,
) -> list[ResearchProgramScopeRevision]:
    """Reject corruption or changed audit facts instead of widening authority."""
    if (
        not isinstance(payload, bytes)
        or len(payload) > MAX_PROGRAM_SCOPE_REVISION_STORE_BYTES
    ):
        raise ResearchError("Program scope revision history bytes are invalid.")
    try:
        document = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
    except ResearchError:
        raise
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ResearchError(
            "Program scope revision history cannot be decoded."
        ) from error
    if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
        raise ResearchError("Program scope revision history fields are invalid.")
    if type(document["schema_version"]) is not int or document[
        "schema_version"
    ] not in (
        _LEGACY_PROGRAM_SCOPE_REVISION_SCHEMA_VERSION,
        PROGRAM_SCOPE_REVISION_SCHEMA_VERSION,
    ):
        raise ResearchError("Program scope revision history schema is unsupported.")
    schema_version = document["schema_version"]
    values = document["revisions"]
    if not isinstance(values, list):
        raise ResearchError("Program scope revisions must be a list.")
    if len(values) > MAX_PROGRAM_SCOPE_REVISIONS:
        raise ResearchError("Program scope revision history has too many entries.")
    revisions = [_parse_entry(value, schema_version) for value in values]
    validate_program_scope_revision_history(revisions)
    return revisions


def validate_program_scope_revision_history(
    revisions: list[ResearchProgramScopeRevision],
) -> None:
    """Validate identity, immutable audit facts and per-program succession."""
    if not isinstance(revisions, list) or not all(
        isinstance(revision, ResearchProgramScopeRevision) for revision in revisions
    ):
        raise ResearchError("Program scope history accepts only revisions.")
    if len(revisions) > MAX_PROGRAM_SCOPE_REVISIONS:
        raise ResearchError("Program scope revision history has too many entries.")

    revision_ids: set[str] = set()
    latest_by_program: dict[str, ResearchProgramScopeRevision] = {}
    for revision in revisions:
        _validate_revision(revision)
        if revision.revision_id in revision_ids:
            raise ResearchError("Program scope revision IDs must be unique.")
        revision_ids.add(revision.revision_id)

        previous = latest_by_program.get(revision.program_id)
        if previous is not None:
            if previous.active:
                raise ResearchError(
                    "A program scope revision must be revoked before replacement."
                )
            assert previous.revoked_at is not None
            if revision.confirmed_at.astimezone(UTC) < previous.revoked_at.astimezone(
                UTC
            ):
                raise ResearchError(
                    "A replacement scope revision predates the prior revocation."
                )
        latest_by_program[revision.program_id] = revision


def _entry_document(revision: ResearchProgramScopeRevision) -> dict[str, Any]:
    scope_document = json.loads(encode_target_scope(revision.scope))
    return {
        "revision_id": revision.revision_id,
        "program_id": revision.program_id,
        "scope": scope_document,
        "scope_digest": revision.scope_digest,
        "revision_digest": revision.revision_digest,
        "capabilities": list(_CAPABILITY_FACTS),
        "transport": PROGRAM_SCOPE_TRANSPORT,
        "execution_policy": execution_policy_document(revision.execution_policy),
        "execution_policy_digest": revision.execution_policy_digest,
        "confirmed_at": revision.confirmed_at.isoformat(),
        "confirmed_by": ResearchAuthorizer.HUMAN.value,
        "expires_at": revision.expires_at.isoformat(),
        "state": revision.state,
        "revoked_at": (
            revision.revoked_at.isoformat() if revision.revoked_at is not None else None
        ),
        "revoked_by": (
            revision.revoked_by.value if revision.revoked_by is not None else None
        ),
    }


def _parse_entry(
    value: object,
    schema_version: int,
) -> ResearchProgramScopeRevision:
    entry_fields = (
        _ENTRY_FIELDS_V1
        if schema_version == _LEGACY_PROGRAM_SCOPE_REVISION_SCHEMA_VERSION
        else _ENTRY_FIELDS_V2
    )
    if not isinstance(value, dict) or set(value) != entry_fields:
        raise ResearchError("A program scope revision entry is invalid.")
    if value["capabilities"] != _CAPABILITY_FACTS:
        raise ResearchError("Program scope revision capabilities are invalid.")
    if value["transport"] != PROGRAM_SCOPE_TRANSPORT:
        raise ResearchError("Program scope revision transport is invalid.")
    if value["confirmed_by"] != ResearchAuthorizer.HUMAN.value:
        raise ResearchError(
            "Program scope revision confirmation provenance is invalid."
        )

    scope_value = value["scope"]
    if not isinstance(scope_value, dict):
        raise ResearchError("Program scope revision target scope is invalid.")
    try:
        scope_payload = json.dumps(
            scope_value,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ResearchError(
            "Program scope revision target scope is invalid."
        ) from error
    scope = decode_target_scope(scope_payload)

    revoked_at = _optional_timestamp(value["revoked_at"])
    revoked_by_value = value["revoked_by"]
    if revoked_by_value is None:
        revoked_by = None
    elif revoked_by_value == ResearchAuthorizer.HUMAN.value:
        revoked_by = ResearchAuthorizer.HUMAN
    else:
        raise ResearchError("Program scope revision revocation provenance is invalid.")
    execution_policy = (
        DEFAULT_PROGRAM_SCOPE_EXECUTION_POLICY
        if schema_version == _LEGACY_PROGRAM_SCOPE_REVISION_SCHEMA_VERSION
        else parse_execution_policy(value["execution_policy"])
    )

    revision = ResearchProgramScopeRevision(
        revision_id=_text(value["revision_id"]),
        program_id=_text(value["program_id"]),
        scope=scope,
        confirmed_at=_timestamp(value["confirmed_at"]),
        expires_at=_timestamp(value["expires_at"]),
        execution_policy=execution_policy,
        revoked_at=revoked_at,
        revoked_by=revoked_by,
    )
    if value["state"] != revision.state:
        raise ResearchError("Program scope revision state is invalid.")
    if value["scope_digest"] != revision.scope_digest:
        raise ResearchError("Program scope revision scope digest does not match.")
    if value["revision_digest"] != revision.revision_digest:
        raise ResearchError("Program scope revision digest does not match.")
    if (
        schema_version == PROGRAM_SCOPE_REVISION_SCHEMA_VERSION
        and value["execution_policy_digest"] != revision.execution_policy_digest
    ):
        raise ResearchError(
            "Program scope revision execution policy digest does not match."
        )
    return revision


def _validate_revision(revision: ResearchProgramScopeRevision) -> None:
    if {field.name for field in fields(revision)} != _MODEL_FIELDS:
        raise ResearchError("Program scope revision model needs a new history schema.")
    if revision.capabilities != PROGRAM_SCOPE_CAPABILITIES:
        raise ResearchError("Program scope revision capabilities are invalid.")
    if revision.transport != PROGRAM_SCOPE_TRANSPORT:
        raise ResearchError("Program scope revision transport is invalid.")
    if not isinstance(revision.execution_policy, ResearchProgramScopeExecutionPolicy):
        raise ResearchError("Program scope revision execution policy is invalid.")
    if revision.execution_policy_digest != execution_policy_digest(
        revision.execution_policy
    ):
        raise ResearchError(
            "Program scope revision execution policy digest does not match."
        )
    if revision.confirmed_by is not ResearchAuthorizer.HUMAN:
        raise ResearchError(
            "Program scope revision confirmation provenance is invalid."
        )
    if revision.scope_digest != target_scope_digest(revision.scope):
        raise ResearchError("Program scope revision scope digest does not match.")
    if revision.revision_digest != program_scope_revision_digest(revision):
        raise ResearchError("Program scope revision digest does not match.")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, entry in pairs:
        if key in value:
            raise ResearchError("Program scope revision history has duplicate fields.")
        value[key] = entry
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise ResearchError("Program scope revision text is invalid.")
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ResearchError("Program scope revision timestamp is invalid.")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise ResearchError("Program scope revision timestamp is invalid.") from error


def _optional_timestamp(value: object) -> datetime | None:
    return None if value is None else _timestamp(value)
