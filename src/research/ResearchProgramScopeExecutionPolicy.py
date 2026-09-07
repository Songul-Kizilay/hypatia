"""Explicit bounded policy recorded on a human-confirmed program scope.

This is not a process runner and not an authorization to execute a Kali tool.
It records the small set of check classes and budgets a later operation layer
must be able to enforce before any process or target traffic can exist.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError
from research.ResearchAutonomyBudget import (
    MAX_AUTONOMY_NETWORK_OPERATIONS,
    MAX_AUTONOMY_SECONDS,
)

MAX_PROGRAM_SCOPE_POLICY_CHECK_CLASSES = 10
MAX_PROGRAM_SCOPE_POLICY_PORTS = 100
MAX_PROGRAM_SCOPE_POLICY_REQUESTS_PER_MINUTE = 60


class ResearchProgramScopeCheckClass(StrEnum):
    """Reviewed check classes a program scope can explicitly allow."""

    PUBLIC_HTTPS_CONTENT = "public_https_content"
    DNS_RECORD_LOOKUP = "dns_record_lookup"


@dataclass(frozen=True, slots=True)
class ResearchProgramScopeExecutionPolicy:
    """Human-confirmed operation limits attached to one immutable scope revision."""

    permitted_check_classes: tuple[ResearchProgramScopeCheckClass, ...] = (
        ResearchProgramScopeCheckClass.PUBLIC_HTTPS_CONTENT,
    )
    permitted_ports: tuple[int, ...] = (443,)
    max_request_count: int = 3
    max_requests_per_minute: int = 3
    max_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not isinstance(self.permitted_check_classes, tuple):
            raise ResearchError("Program scope check classes must be immutable.")
        if not (
            1
            <= len(self.permitted_check_classes)
            <= MAX_PROGRAM_SCOPE_POLICY_CHECK_CLASSES
        ):
            raise ResearchError("Program scope check classes are invalid.")
        if any(
            not isinstance(value, ResearchProgramScopeCheckClass)
            for value in self.permitted_check_classes
        ):
            raise ResearchError("Program scope check classes are invalid.")
        if len(set(self.permitted_check_classes)) != len(self.permitted_check_classes):
            raise ResearchError("Program scope check classes must be unique.")

        if not isinstance(self.permitted_ports, tuple):
            raise ResearchError("Program scope ports must be immutable.")
        if not 1 <= len(self.permitted_ports) <= MAX_PROGRAM_SCOPE_POLICY_PORTS:
            raise ResearchError("Program scope ports are invalid.")
        for port in self.permitted_ports:
            if isinstance(port, bool) or not isinstance(port, int):
                raise ResearchError("Program scope ports are invalid.")
            if not 1 <= port <= 65535:
                raise ResearchError("Program scope ports are invalid.")
        if len(set(self.permitted_ports)) != len(self.permitted_ports):
            raise ResearchError("Program scope ports must be unique.")

        if (
            isinstance(self.max_request_count, bool)
            or not isinstance(self.max_request_count, int)
            or not 1 <= self.max_request_count <= MAX_AUTONOMY_NETWORK_OPERATIONS
        ):
            raise ResearchError(
                "Program scope request count must be within its hard ceiling."
            )
        if (
            isinstance(self.max_requests_per_minute, bool)
            or not isinstance(self.max_requests_per_minute, int)
            or not (
                1
                <= self.max_requests_per_minute
                <= MAX_PROGRAM_SCOPE_POLICY_REQUESTS_PER_MINUTE
            )
        ):
            raise ResearchError(
                "Program scope request rate must be within its hard ceiling."
            )
        if (
            isinstance(self.max_seconds, bool)
            or not isinstance(self.max_seconds, int | float)
            or not 0 < self.max_seconds <= MAX_AUTONOMY_SECONDS
        ):
            raise ResearchError(
                "Program scope time budget must be within its hard ceiling."
            )


DEFAULT_PROGRAM_SCOPE_EXECUTION_POLICY = ResearchProgramScopeExecutionPolicy()
_EXECUTION_POLICY_DIGEST_SCHEMA = "hypatia:research-program-scope-execution-policy:v1"


def execution_policy_document(
    policy: ResearchProgramScopeExecutionPolicy,
) -> dict[str, object]:
    """Return the canonical policy facts recorded in a scope revision."""
    if not isinstance(policy, ResearchProgramScopeExecutionPolicy):
        raise ResearchError("Program scope execution policy is invalid.")
    return {
        "permitted_check_classes": [
            value.value for value in policy.permitted_check_classes
        ],
        "permitted_ports": list(policy.permitted_ports),
        "max_request_count": policy.max_request_count,
        "max_requests_per_minute": policy.max_requests_per_minute,
        "max_seconds": policy.max_seconds,
    }


def canonical_execution_policy_bytes(
    policy: ResearchProgramScopeExecutionPolicy,
) -> bytes:
    """Encode the exact policy independently from the scope revision identity."""
    return json.dumps(
        {
            "schema": _EXECUTION_POLICY_DIGEST_SCHEMA,
            "policy": execution_policy_document(policy),
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def execution_policy_digest(policy: ResearchProgramScopeExecutionPolicy) -> str:
    """Identify the complete policy without changing existing scope IDs."""
    return hashlib.sha256(canonical_execution_policy_bytes(policy)).hexdigest()


def parse_execution_policy(
    value: object,
) -> ResearchProgramScopeExecutionPolicy:
    """Restore a bounded execution policy from strict persisted JSON facts."""
    if not isinstance(value, dict) or set(value) != set(
        execution_policy_document(DEFAULT_PROGRAM_SCOPE_EXECUTION_POLICY)
    ):
        raise ResearchError("Program scope execution policy fields are invalid.")
    classes = value["permitted_check_classes"]
    ports = value["permitted_ports"]
    if not isinstance(classes, list) or not isinstance(ports, list):
        raise ResearchError("Program scope execution policy collections are invalid.")
    try:
        check_classes = tuple(ResearchProgramScopeCheckClass(item) for item in classes)
    except ValueError as error:
        raise ResearchError("Program scope check classes are invalid.") from error
    return ResearchProgramScopeExecutionPolicy(
        permitted_check_classes=check_classes,
        permitted_ports=tuple(ports),
        max_request_count=value["max_request_count"],
        max_requests_per_minute=value["max_requests_per_minute"],
        max_seconds=value["max_seconds"],
    )
