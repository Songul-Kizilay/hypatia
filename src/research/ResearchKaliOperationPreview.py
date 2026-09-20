"""Inert preview for a future reviewed Kali-backed operation.

This module deliberately contains no runner, process adapter, command string or
terminal affordance.  It records the exact operation facts a later
authorization layer must bind before any child process can be considered.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from core.Exceptions import ResearchError
from research.ResearchProgramScopeExecutionPolicy import (
    ResearchProgramScopeCheckClass,
)

MAX_KALI_OPERATION_HOSTNAME_CHARACTERS = 253
_KALI_OPERATION_DIGEST_SCHEMA = "hypatia:kali-operation-preview:v2"
_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ResearchKaliOperationKind(StrEnum):
    """Reviewed operation profiles; not executable program names."""

    DNS_RECORD_LOOKUP = "dns_record_lookup"
    HTTPS_HEADER_LOOKUP = "https_header_lookup"


class ResearchDnsRecordType(StrEnum):
    """Initial DNS record types allowed by the reviewed lookup profile."""

    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"


class ResearchKaliCommandTransport(StrEnum):
    """Reviewed transport profile names; not an executable launcher."""

    WSL_KALI = "wsl_kali"


@dataclass(frozen=True, slots=True)
class ResearchKaliOperationCommandPlan:
    """Code-owned terminal argv plan for one reviewed Kali operation.

    The plan is still inert: it starts no process, performs no DNS lookup and
    grants no authority. It is intentionally an argv tuple, never a shell
    command string.
    """

    transport: ResearchKaliCommandTransport
    executable_path: str
    argv: tuple[str, ...]
    shell: bool = False
    stdin: str = "closed"

    def __post_init__(self) -> None:
        if not isinstance(self.transport, ResearchKaliCommandTransport):
            raise ResearchError("Kali command plan transport is invalid.")
        if (
            not isinstance(self.executable_path, str)
            or not self.executable_path.startswith("/")
            or not self.executable_path.strip()
        ):
            raise ResearchError("Kali command plan executable path is invalid.")
        if not isinstance(self.argv, tuple) or not self.argv:
            raise ResearchError("Kali command plan argv is invalid.")
        if self.argv[0] != self.executable_path:
            raise ResearchError("Kali command plan argv must name the executable.")
        for argument in self.argv:
            if not isinstance(argument, str) or not argument:
                raise ResearchError("Kali command plan argv is invalid.")
            if "\x00" in argument or "\r" in argument or "\n" in argument:
                raise ResearchError("Kali command plan argv contains control data.")
        if self.shell is not False:
            raise ResearchError("Kali command plan must not use a shell.")
        if self.stdin != "closed":
            raise ResearchError("Kali command plan stdin must be closed.")


@dataclass(frozen=True, slots=True)
class ResearchKaliOperationFakeRun:
    """Deterministic no-process result for exercising the runner gate."""

    authorization_id: str
    operation_digest: str
    program_id: str
    scope_revision_id: str
    scope_revision_digest: str
    execution_policy_digest: str
    operation_kind: ResearchKaliOperationKind
    command_plan: ResearchKaliOperationCommandPlan
    simulated_stdout: tuple[str, ...]
    process_created: bool = False
    network_used: bool = False

    def __post_init__(self) -> None:
        for value, label in (
            (self.authorization_id, "authorization ID"),
            (self.program_id, "program ID"),
            (self.scope_revision_id, "scope revision ID"),
            (self.scope_revision_digest, "scope revision digest"),
            (self.execution_policy_digest, "execution policy digest"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"Kali fake run {label} cannot be empty.")
        if not is_kali_operation_digest(self.operation_digest):
            raise ResearchError("Kali fake run operation digest is invalid.")
        if not isinstance(self.operation_kind, ResearchKaliOperationKind):
            raise ResearchError("Kali fake run operation kind is invalid.")
        if not isinstance(self.command_plan, ResearchKaliOperationCommandPlan):
            raise ResearchError("Kali fake run command plan is invalid.")
        if not isinstance(self.simulated_stdout, tuple):
            raise ResearchError("Kali fake run output must be immutable.")
        for line in self.simulated_stdout:
            if not isinstance(line, str) or "\x00" in line:
                raise ResearchError("Kali fake run output is invalid.")
        if self.process_created is not False or self.network_used is not False:
            raise ResearchError("Kali fake run must not perform real work.")


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
    dns_record_type: ResearchDnsRecordType | None
    resolved_address: str | None
    permitted_ports: tuple[int, ...]
    max_request_count: int
    max_requests_per_minute: int
    max_seconds: float
    created_at: datetime
    command_plan: ResearchKaliOperationCommandPlan = field(init=False)
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
        if self.operation_kind is ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
            if not isinstance(self.dns_record_type, ResearchDnsRecordType):
                raise ResearchError(
                    "Kali operation preview DNS record type is invalid."
                )
        elif self.dns_record_type is not None:
            raise ResearchError(
                "Kali operation preview DNS record type is not applicable."
            )
        if self.operation_kind is ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP:
            if (
                not isinstance(self.resolved_address, str)
                or not self.resolved_address.strip()
            ):
                raise ResearchError(
                    "Kali operation preview resolved address is invalid."
                )
            try:
                ipaddress.ip_address(self.resolved_address)
            except ValueError as error:
                raise ResearchError(
                    "Kali operation preview resolved address is invalid."
                ) from error
        elif self.resolved_address is not None:
            raise ResearchError(
                "Kali operation preview resolved address is not applicable."
            )
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
            self,
            "command_plan",
            kali_operation_command_plan(
                operation_kind=self.operation_kind,
                hostname=normalized_hostname,
                dns_record_type=self.dns_record_type,
                resolved_address=self.resolved_address,
            ),
        )
        object.__setattr__(
            self, "operation_digest", kali_operation_preview_digest(self)
        )


def kali_operation_command_plan(
    *,
    operation_kind: ResearchKaliOperationKind,
    hostname: str,
    dns_record_type: ResearchDnsRecordType | None = None,
    resolved_address: str | None = None,
) -> ResearchKaliOperationCommandPlan:
    """Build the reviewed argv plan for one supported operation."""
    if not isinstance(operation_kind, ResearchKaliOperationKind):
        raise ResearchError("Kali operation command plan kind is not supported.")
    if not isinstance(hostname, str):
        raise ResearchError("Kali operation command plan hostname is invalid.")
    normalized_hostname = hostname.strip().lower().removesuffix(".")
    if not normalized_hostname or len(normalized_hostname) > (
        MAX_KALI_OPERATION_HOSTNAME_CHARACTERS
    ):
        raise ResearchError("Kali operation command plan hostname is invalid.")
    if operation_kind is ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
        if not isinstance(dns_record_type, ResearchDnsRecordType):
            raise ResearchError(
                "Kali operation command plan DNS record type is invalid."
            )
        if resolved_address is not None:
            raise ResearchError(
                "Kali operation command plan resolved address is not applicable."
            )
        return ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.WSL_KALI,
            executable_path="/usr/bin/dig",
            argv=(
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                normalized_hostname,
                dns_record_type.value,
            ),
        )
    if operation_kind is ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP:
        if dns_record_type is not None:
            raise ResearchError(
                "Kali operation command plan DNS record type is not applicable."
            )
        if not isinstance(resolved_address, str) or not resolved_address.strip():
            raise ResearchError(
                "Kali operation command plan resolved address is invalid."
            )
        try:
            parsed_address = ipaddress.ip_address(resolved_address)
        except ValueError as error:
            raise ResearchError(
                "Kali operation command plan resolved address is invalid."
            ) from error
        resolve_address = (
            f"[{parsed_address.compressed}]"
            if isinstance(parsed_address, ipaddress.IPv6Address)
            else parsed_address.compressed
        )
        return ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.WSL_KALI,
            executable_path="/usr/bin/curl",
            argv=(
                "/usr/bin/curl",
                "--head",
                "--silent",
                "--show-error",
                "--max-time",
                "10",
                "--proto",
                "=https",
                "--resolve",
                f"{normalized_hostname}:443:{resolve_address}",
                f"https://{normalized_hostname}/",
            ),
        )
    raise ResearchError("Kali operation command plan kind is not supported.")


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
        "dns_record_type": (
            preview.dns_record_type.value
            if preview.dns_record_type is not None
            else None
        ),
        "resolved_address": preview.resolved_address,
        "permitted_ports": list(preview.permitted_ports),
        "max_request_count": preview.max_request_count,
        "max_requests_per_minute": preview.max_requests_per_minute,
        "max_seconds": preview.max_seconds,
        "command_plan": kali_operation_command_plan_document(preview.command_plan),
    }


def kali_operation_command_plan_document(
    command_plan: ResearchKaliOperationCommandPlan,
) -> dict[str, object]:
    """Return the reviewed argv facts without rendering a shell command line."""
    if not isinstance(command_plan, ResearchKaliOperationCommandPlan):
        raise ResearchError("Kali command plan is invalid.")
    return {
        "transport": command_plan.transport.value,
        "executable_path": command_plan.executable_path,
        "argv": list(command_plan.argv),
        "shell": command_plan.shell,
        "stdin": command_plan.stdin,
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


def is_kali_operation_digest(value: object) -> bool:
    """Return whether a value can name one reviewed operation preview."""
    return isinstance(value, str) and _SHA256_HEX_PATTERN.fullmatch(value) is not None
