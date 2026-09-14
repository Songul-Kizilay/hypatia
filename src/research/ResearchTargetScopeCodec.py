"""Strict, versioned target-scope snapshots with inspectable content identity.

The digest detects content changes, not malicious editing by a writer able to
recompute it. Execution authority must independently bind an approved digest.
No field is dropped, interpreted as prose, or converted into a broader rule.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields
from typing import Any

from core.Exceptions import ResearchError
from research.ResearchTargetScope import (
    MAX_SCOPE_RULES,
    ResearchTargetScope,
    TargetHostRule,
)

MAX_TARGET_SCOPE_BYTES = 65_536
_VERSION = 1
_SCOPE_FIELDS = frozenset(
    {"allowed_hosts", "excluded_hosts", "allowed_networks", "excluded_networks"}
)
_HOST_FIELDS = frozenset({"host", "subdomains_only"})


def _scope_document(scope: ResearchTargetScope) -> dict[str, Any]:
    if not isinstance(scope, ResearchTargetScope):
        raise ResearchError("Target scope snapshot requires a validated scope.")
    # A future model field must not disappear from the snapshot or its digest.
    if {field.name for field in fields(scope)} != _SCOPE_FIELDS or {
        field.name for field in fields(TargetHostRule)
    } != _HOST_FIELDS:
        raise ResearchError("Target scope model needs a new snapshot schema.")
    if any(
        {field.name for field in fields(rule)} != _HOST_FIELDS
        for rule in (*scope.allowed_hosts, *scope.excluded_hosts)
    ):
        raise ResearchError("Target scope host model needs a new snapshot schema.")
    return {
        "allowed_hosts": [
            {"host": r.host, "subdomains_only": r.subdomains_only}
            for r in scope.allowed_hosts
        ],
        "excluded_hosts": [
            {"host": r.host, "subdomains_only": r.subdomains_only}
            for r in scope.excluded_hosts
        ],
        "allowed_networks": list(scope.allowed_networks),
        "excluded_networks": list(scope.excluded_networks),
    }


def canonical_target_scope_bytes(scope: ResearchTargetScope) -> bytes:
    """Encode every rule in authored order, with a separate scope schema tag."""
    return json.dumps(
        {"schema_version": _VERSION, "scope": _scope_document(scope)},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def target_scope_digest(scope: ResearchTargetScope) -> str:
    """Identify this scope content; not an authorization or a signature."""
    return hashlib.sha256(canonical_target_scope_bytes(scope)).hexdigest()


def encode_target_scope(scope: ResearchTargetScope) -> bytes:
    document = {
        "schema_version": _VERSION,
        "scope": _scope_document(scope),
        "scope_digest": target_scope_digest(scope),
    }
    payload = (
        json.dumps(document, sort_keys=True, ensure_ascii=True, indent=2) + "\n"
    ).encode("utf-8")
    if len(payload) > MAX_TARGET_SCOPE_BYTES:
        raise ResearchError("Target scope snapshot is too large.")
    return payload


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ResearchError("Target scope snapshot contains duplicate fields.")
        result[key] = value
    return result


def decode_target_scope(payload: bytes) -> ResearchTargetScope:
    """Reject malformed, unsupported or changed snapshots instead of widening."""
    if not isinstance(payload, bytes) or len(payload) > MAX_TARGET_SCOPE_BYTES:
        raise ResearchError("Target scope snapshot bytes are invalid.")
    try:
        document = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ResearchError("Target scope snapshot cannot be decoded.") from error
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "scope",
        "scope_digest",
    }:
        raise ResearchError("Target scope snapshot fields are invalid.")
    if (
        type(document["schema_version"]) is not int
        or document["schema_version"] != _VERSION
    ):
        raise ResearchError("Target scope snapshot schema is unsupported.")
    value = document["scope"]
    if not isinstance(value, dict) or set(value) != _SCOPE_FIELDS:
        raise ResearchError("Target scope rule fields are invalid.")
    if any(not isinstance(value[name], list) for name in _SCOPE_FIELDS):
        raise ResearchError("Target scope rule collections must be lists.")
    if sum(len(value[name]) for name in _SCOPE_FIELDS) > MAX_SCOPE_RULES:
        raise ResearchError("Target scope snapshot has too many rules.")
    host_groups: list[tuple[TargetHostRule, ...]] = []
    for name in ("allowed_hosts", "excluded_hosts"):
        rules: list[TargetHostRule] = []
        for entry in value[name]:
            if not isinstance(entry, dict) or set(entry) != _HOST_FIELDS:
                raise ResearchError("Target scope host fields are invalid.")
            rules.append(TargetHostRule(entry["host"], entry["subdomains_only"]))
        host_groups.append(tuple(rules))
    scope = ResearchTargetScope(
        allowed_hosts=host_groups[0],
        excluded_hosts=host_groups[1],
        allowed_networks=tuple(value["allowed_networks"]),
        excluded_networks=tuple(value["excluded_networks"]),
    )
    if document["scope_digest"] != target_scope_digest(scope):
        raise ResearchError("Target scope snapshot digest does not match its rules.")
    return scope
