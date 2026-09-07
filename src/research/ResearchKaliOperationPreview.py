"""Inert preview for a future reviewed Kali-backed operation.

This module deliberately contains no runner, process adapter, command string or
terminal affordance.  It records the exact operation facts a later
authorization layer must bind before any child process can be considered.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from core.Exceptions import ResearchError
from research.ResearchProgramScopeExecutionPolicy import (
    ResearchProgramScopeCheckClass,
)

MAX_KALI_OPERATION_HOSTNAME_CHARACTERS = 253
_KALI_OPERATION_DIGEST_SCHEMA = "hypatia:kali-operation-preview:v1"


class ResearchKaliOperationKind(StrEnum):
    """Reviewed operation profiles; not executable program names."""

    DNS_RECORD_LOOKUP = "dns_record_lookup"


class ResearchDnsRecordType(StrEnum):
    """Initial DNS record types allowed by the reviewed lookup profile."""

    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"


@dataclass(frozen=True, slots=True)
class ResearchKaliOperationPreview:
    """A complete side-effect-free operation proposal for operator review."""

    program_id: str
    scope_revision_id: str
    scope_revision_digest: str
    execution_policy_digest: str
    operation_kind: ResearchKaliOperationKind
    check_class: ResearchProgramScopeCheckClass
    hostname: str
    dns_record_type: ResearchDnsRecordType
    permitted_ports: tuple[int, ...]
    max_request_count: int
    max_requests_per_minute: int
    max_seconds: float
    created_at: datetime
    operation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for value, label in (
            (self.program_id, "program ID"),
            (self.scope_revision_id, "scope revision ID"),
            (self.scope_revision_digest, "scope revision digest"),
            (self.execution_policy_digest, "execution policy digest"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"Kali operation preview {label} cannot be empty.")
        if not isinstance(self.operation_kind, ResearchKaliOperationKind):
            raise ResearchError("Kali operation preview kind is invalid.")
        if not isinstance(self.check_class, ResearchProgramScopeCheckClass):
            raise ResearchError("Kali operation preview check class is invalid.")
        if not isinstance(self.hostname, str) or not self.hostname.strip():
            raise ResearchError("Kali operation preview hostname cannot be empty.")
        normalized_hostname = self.hostname.strip().lower().removesuffix(".")
        if len(normalized_hostname) > MAX_KALI_OPERATION_HOSTNAME_CHARACTERS:
            raise ResearchError("Kali operation preview hostname is too long.")
        if not isinstance(self.dns_record_type, ResearchDnsRecordType):
            raise ResearchError("Kali operation preview DNS record type is invalid.")
        if not isinstance(self.permitted_ports, tuple) or not self.permitted_ports:
            raise ResearchError("Kali operation preview permitted ports are invalid.")
        for port in self.permitted_ports:
            if isinstance(port, bool) or not isinstance(port, int):
                raise ResearchError(
                    "Kali operation preview permitted ports are invalid."
                )
            if not 1 <= port <= 65535:
                raise ResearchError(
                    "Kali operation preview permitted ports are invalid."
                )
        if len(set(self.permitted_ports)) != len(self.permitted_ports):
            raise ResearchError(
                "Kali operation preview permitted ports must be unique."
            )
        if (
            isinstance(self.max_request_count, bool)
            or not isinstance(self.max_request_count, int)
            or self.max_request_count < 1
        ):
            raise ResearchError("Kali operation preview request count is invalid.")
        if (
            isinstance(self.max_requests_per_minute, bool)
            or not isinstance(self.max_requests_per_minute, int)
            or self.max_requests_per_minute < 1
        ):
            raise ResearchError("Kali operation preview request rate is invalid.")
        if (
            isinstance(self.max_seconds, bool)
            or not isinstance(self.max_seconds, int | float)
            or self.max_seconds <= 0
        ):
            raise ResearchError("Kali operation preview time budget is invalid.")
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.utcoffset() is None
        ):
            raise ResearchError("Kali operation preview time must be timezone-aware.")
        object.__setattr__(self, "hostname", normalized_hostname)
        object.__setattr__(
            self, "operation_digest", kali_operation_preview_digest(self)
        )


def kali_operation_preview_document(
    preview: ResearchKaliOperationPreview,
) -> dict[str, object]:
    """Return the exact operation facts without a command string."""
    if not isinstance(preview, ResearchKaliOperationPreview):
        raise ResearchError("Kali operation preview is invalid.")
    return {
        "program_id": preview.program_id,
        "scope_revision_id": preview.scope_revision_id,
        "scope_revision_digest": preview.scope_revision_digest,
        "execution_policy_digest": preview.execution_policy_digest,
        "operation_kind": preview.operation_kind.value,
        "check_class": preview.check_class.value,
        "hostname": preview.hostname,
        "dns_record_type": preview.dns_record_type.value,
        "permitted_ports": list(preview.permitted_ports),
        "max_request_count": preview.max_request_count,
        "max_requests_per_minute": preview.max_requests_per_minute,
        "max_seconds": preview.max_seconds,
        "created_at": preview.created_at.isoformat(),
    }


def canonical_kali_operation_preview_bytes(
    preview: ResearchKaliOperationPreview,
) -> bytes:
    """Encode exactly what a future authorization must approve."""
    return json.dumps(
        {
            "schema": _KALI_OPERATION_DIGEST_SCHEMA,
            "preview": kali_operation_preview_document(preview),
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def kali_operation_preview_digest(preview: ResearchKaliOperationPreview) -> str:
    """Identify one inert operation proposal."""
    return hashlib.sha256(canonical_kali_operation_preview_bytes(preview)).hexdigest()
