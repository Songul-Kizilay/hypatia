"""First real Guest-Agent DNS_RECORD_LOOKUP executor adapter.

This module introduces exactly ONE real target-operation process
capability: `/usr/bin/dig +time=5 +tries=1 +short <hostname> <A|AAAA
|CNAME>`. It has ZERO production callers after this milestone -- it is
not wired into `research.GuestAgentSignedDispatchRpcTransport`,
`Bootstrap`, `CognitiveEngine`, chat, or the desktop. A future milestone
will separately authorize RPC wiring; this module only proves the
narrowest possible executor can exist, gated entirely by the exact
execution-admission boundary v0.3.468 already delivered.

EXECUTION ADMISSION != EXECUTION SUCCESS. EXECUTOR DOES NOT CREATE
AUTHORITY. This adapter's one entry point,
`execute_guest_agent_dns_record_lookup`, accepts ONLY a real, unforgeable
`research.GuestAgentExecutionAdmission.GuestAgentExecutionAdmission` --
never a `GuestAgentRequest`, a `GuestAgentVerifiedDispatch` alone, a
`GuestAgentPreparedInvocation` alone, a `GuestAgentRuntimeReadyInvocation`
alone, a hostname, a record type, an executable path, an argv tuple, a
command string, a callback, or a shell string. There is no code path in
this module that accepts a target fact as a separate parameter: the
executable path, argv, and timeout are read ONLY from
`execution_admission.runtime_ready_invocation.prepared_invocation
.command_plan`/`.timeout_seconds` -- the same already-exact-bound,
already-capped facts v0.3.466/v0.3.467/v0.3.468 produced and verified.
The caller has ZERO ability to override or widen any of them.

Deliberately NOT built by copying `research.WslKaliOperationProcessAdapter`
or `research.VmwareKaliOperationProcessAdapter`: both of those implement
`research.ResearchKaliOperationProcessAdapter`, whose `.run(command_plan,
*, timeout_seconds)` signature itself accepts a command plan and timeout
as separate caller-supplied parameters -- exactly the shape this
milestone forbids. This adapter instead exposes one function taking only
the already-unforgeable admission value; there is no interface here a
caller could satisfy with a fabricated command plan or timeout.

DNS ONLY: `execute_guest_agent_dns_record_lookup` supports exactly
`research.ResearchKaliOperationPreview.ResearchKaliOperationKind
.DNS_RECORD_LOOKUP`. `HTTPS_HEADER_LOOKUP` -- and any future operation
kind -- fails closed before `subprocess.run` is ever reached. The
allowlist of accepted DNS record types (`A`, `AAAA`, `CNAME`) is an
explicit fixed literal, never built by enumerating
`research.ResearchKaliOperationPreview.ResearchDnsRecordType` itself, so
a future fourth record type fails closed by default.

Before ever calling `subprocess.run`, `_validate_reviewed_dns_command_plan`
independently re-proves every fact the rest of the chain already bound:
operation kind, transport, executable path, `shell is False`, `stdin ==
"closed"`, exact argv length, exact argv prefix
(`"/usr/bin/dig"`, `"+time=5"`, `"+tries=1"`, `"+short"`), hostname shape
(reusing the existing `MAX_KALI_OPERATION_HOSTNAME_CHARACTERS` bound),
and record-type membership -- defense in depth against a hypothetical
future bug upstream, never trust-by-existence. A mismatch anywhere fails
closed with zero subprocess attempts.

ONE ATTEMPT, NO RETRY: this module calls `subprocess.run` at most once
per call to `execute_guest_agent_dns_record_lookup`, with `shell=False`,
`stdin=subprocess.DEVNULL`, `check=False`, and the exact admitted,
already-capped `timeout_seconds` -- never a second, caller-supplied
timeout parameter. No loop, no retry after timeout/nonzero-exit/empty-
output/malformed-output/`OSError`, and no fallback executable, PATH
search, or package installation exists anywhere in this module.

`GuestAgentDnsExecutionResult` honestly distinguishes whether the local
`dig` process actually started (`process_created`), its exit code (only
when the process both started and did not time out), whether it timed
out, and bounded, sanitized, explicitly `UNTRUSTED PROCESS OUTPUT`
stdout/stderr. DNS PROCESS STARTED != DNS SUCCESS. DNS OUTPUT != TRUSTED
EVIDENCE. DNS OUTPUT != VERIFIED FACT. NONZERO EXIT != SUCCESS. TIMEOUT
!= SUCCESS. TARGET OPERATION ATTEMPTED != NETWORK OBSERVED: a started
`dig` process means the DNS lookup was ATTEMPTED on this host -- this
module cannot and does not claim that any packet was actually observed
leaving the machine, that the lookup succeeded, or that its output is
evidence. `evidence_recorded`, `claim_created`, `source_accepted`, and
`memory_written` are all structurally forced `False`: this milestone
ends at a bounded, untrusted process result. Parsing that output into
evidence (`research.ResearchDnsLookupResultParser` or any future
equivalent), creating a claim, accepting a source, writing memory,
creating a security finding, correlating vulnerabilities, or classifying
the target are all explicitly out of scope and not done anywhere here.

If `subprocess.run` cannot even start the process (`OSError` -- for
example the reviewed `/usr/bin/dig` path does not exist on this guest),
this module raises `core.Exceptions.ResearchError` carrying only the
bounded exception type name (mirroring
`research.WslKaliOperationProcessAdapter.run`'s own existing OSError
handling) -- never raw exception text, a path, or other leaked detail.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Final

from core.Exceptions import ResearchError
from research.GuestAgentExecutionAdmission import GuestAgentExecutionAdmission
from research.ResearchKaliOperationExecution import (
    KALI_OPERATION_OUTPUT_TRUST,
    MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
    MAX_KALI_OPERATION_OUTPUT_LINES,
)
from research.ResearchKaliOperationPreview import (
    MAX_KALI_OPERATION_HOSTNAME_CHARACTERS,
    ResearchKaliCommandTransport,
    ResearchKaliOperationCommandPlan,
    ResearchKaliOperationKind,
)

#: The one reviewed, code-owned absolute executable this module may ever
#: invoke. Never derived from PATH, caller input, or any fallback.
_DIG_EXECUTABLE_PATH: Final[str] = "/usr/bin/dig"

#: The exact fixed argv prefix every reviewed DNS command plan must carry.
#: Never built from caller input; a literal tuple only.
_DIG_ARGV_PREFIX: Final[tuple[str, str, str, str]] = (
    "/usr/bin/dig",
    "+time=5",
    "+tries=1",
    "+short",
)

#: `_DIG_ARGV_PREFIX` plus exactly one hostname and one record-type
#: argument -- never more, never fewer.
_DIG_ARGV_LENGTH: Final[int] = len(_DIG_ARGV_PREFIX) + 2

#: The one fixed literal allowlist of accepted DNS record types. Not
#: built by iterating `ResearchDnsRecordType` -- a future fourth member
#: simply has no entry here, so it fails closed by default, mirroring
#: `research.GuestAgentCore`'s own documented "deny by default" discipline
#: for its operation allowlist.
_SUPPORTED_DNS_RECORD_TYPE_VALUES: Final[frozenset[str]] = frozenset(
    {"A", "AAAA", "CNAME"}
)

_REASON_UNSUPPORTED_OPERATION = (
    "Guest-agent DNS executor supports only DNS_RECORD_LOOKUP."
)
_REASON_WRONG_TRANSPORT = (
    "Guest-agent DNS executor requires a GUEST_AGENT command plan."
)
_REASON_WRONG_EXECUTABLE = (
    "Guest-agent DNS executor requires the reviewed /usr/bin/dig executable."
)
_REASON_SHELL_NOT_ALLOWED = "Guest-agent DNS executor must not use a shell."
_REASON_STDIN_NOT_CLOSED = "Guest-agent DNS executor requires closed stdin."
_REASON_ARGV_LENGTH = (
    "Guest-agent DNS executor requires the exact reviewed argv length."
)
_REASON_ARGV_PREFIX = (
    "Guest-agent DNS executor requires the exact reviewed argv prefix."
)
_REASON_HOSTNAME_SHAPE = (
    "Guest-agent DNS executor requires a hostname within the reviewed contract."
)
_REASON_RECORD_TYPE = (
    "Guest-agent DNS executor requires an A, AAAA, or CNAME record type."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GuestAgentDnsExecutionResult:
    """A bounded, honest, untrusted result of one attempted DNS lookup.

    DNS PROCESS STARTED != DNS SUCCESS. DNS OUTPUT != TRUSTED EVIDENCE.
    DNS OUTPUT != VERIFIED FACT. NONZERO EXIT != SUCCESS. TIMEOUT !=
    SUCCESS. TARGET OPERATION ATTEMPTED != NETWORK OBSERVED -- see the
    module docstring. `process_created=True` means only that the local
    `dig` process was launched (the DNS operation was ATTEMPTED on this
    host); it never means a packet was observed leaving the machine, the
    lookup succeeded, or the output is trustworthy.

    `evidence_recorded`/`claim_created`/`source_accepted`/`memory_written`
    are all structurally forced `False`: this type can never be
    constructed to claim evidence was recorded, a claim was created, a
    source was accepted, or memory was written.
    """

    operation_kind: ResearchKaliOperationKind
    command_plan: ResearchKaliOperationCommandPlan
    process_created: bool
    exit_code: int | None
    timed_out: bool
    stdout_lines: tuple[str, ...]
    stderr_lines: tuple[str, ...]
    output_trust: str = KALI_OPERATION_OUTPUT_TRUST
    evidence_recorded: bool = False
    claim_created: bool = False
    source_accepted: bool = False
    memory_written: bool = False

    def __post_init__(self) -> None:
        if self.operation_kind is not ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
            raise ResearchError(_REASON_UNSUPPORTED_OPERATION)
        if not isinstance(self.command_plan, ResearchKaliOperationCommandPlan):
            raise ResearchError(
                "Guest-agent DNS execution result command plan is invalid."
            )
        if self.command_plan.transport is not ResearchKaliCommandTransport.GUEST_AGENT:
            raise ResearchError(_REASON_WRONG_TRANSPORT)
        if self.command_plan.executable_path != _DIG_EXECUTABLE_PATH:
            raise ResearchError(_REASON_WRONG_EXECUTABLE)
        if not isinstance(self.process_created, bool):
            raise ResearchError(
                "Guest-agent DNS execution result process flag is invalid."
            )
        if not isinstance(self.timed_out, bool):
            raise ResearchError(
                "Guest-agent DNS execution result timeout flag is invalid."
            )
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise ResearchError(
                "Guest-agent DNS execution result exit code is invalid."
            )
        if self.process_created is False and (
            self.exit_code is not None or self.timed_out is not False
        ):
            raise ResearchError(
                "Guest-agent DNS execution result must not carry an exit code "
                "or timeout flag when no process was created."
            )
        if self.timed_out is True and self.exit_code is not None:
            raise ResearchError(
                "Guest-agent DNS execution result must not carry an exit code "
                "for a timed-out process."
            )
        self._validate_lines(self.stdout_lines, "stdout")
        self._validate_lines(self.stderr_lines, "stderr")
        if self.output_trust != KALI_OPERATION_OUTPUT_TRUST:
            raise ResearchError(
                "Guest-agent DNS execution result output trust is invalid."
            )
        if (
            self.evidence_recorded is not False
            or self.claim_created is not False
            or self.source_accepted is not False
            or self.memory_written is not False
        ):
            raise ResearchError(
                "Guest-agent DNS execution result must not claim evidence, a "
                "claim, an accepted source, or a memory write."
            )

    @staticmethod
    def _validate_lines(lines: object, label: str) -> None:
        if not isinstance(lines, tuple):
            raise ResearchError(
                f"Guest-agent DNS execution result {label} must be immutable."
            )
        if len(lines) > MAX_KALI_OPERATION_OUTPUT_LINES:
            raise ResearchError(
                f"Guest-agent DNS execution result {label} has too many lines."
            )
        for line in lines:
            if (
                not isinstance(line, str)
                or "\x00" in line
                or len(line) > MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS
            ):
                raise ResearchError(
                    f"Guest-agent DNS execution result {label} is invalid."
                )


def execute_guest_agent_dns_record_lookup(
    execution_admission: GuestAgentExecutionAdmission,
) -> GuestAgentDnsExecutionResult:
    """Run the one reviewed DNS version-lookup command; never retry.

    Accepts ONLY a real `GuestAgentExecutionAdmission`. The exact
    executable, argv, and timeout are read exclusively from
    `execution_admission.runtime_ready_invocation.prepared_invocation` --
    there is no parameter through which a caller could supply or widen
    any of them. Raises `core.Exceptions.ResearchError` if the admission
    is the wrong type, if its bound operation is not
    `DNS_RECORD_LOOKUP`, if the reviewed command plan fails any
    defense-in-depth cross-check, or if the local process could not be
    started at all (`OSError`, reported only as a bounded exception type
    name). Calls `subprocess.run` at most once.
    """
    if not isinstance(execution_admission, GuestAgentExecutionAdmission):
        raise ResearchError(
            "Guest-agent DNS executor requires a real execution admission."
        )

    prepared_invocation = (
        execution_admission.runtime_ready_invocation.prepared_invocation
    )
    operation_kind = prepared_invocation.operation_kind
    if operation_kind is not ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
        raise ResearchError(_REASON_UNSUPPORTED_OPERATION)

    command_plan = prepared_invocation.command_plan
    _validate_reviewed_dns_command_plan(command_plan)
    timeout_seconds = prepared_invocation.timeout_seconds

    try:
        completed = subprocess.run(
            command_plan.argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            shell=False,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return GuestAgentDnsExecutionResult(
            operation_kind=operation_kind,
            command_plan=command_plan,
            process_created=True,
            exit_code=None,
            timed_out=True,
            stdout_lines=(),
            stderr_lines=(),
        )
    except OSError as error:
        raise ResearchError(
            "Unable to start the Guest-Agent DNS executor process: "
            f"{type(error).__name__}."
        ) from error

    return GuestAgentDnsExecutionResult(
        operation_kind=operation_kind,
        command_plan=command_plan,
        process_created=True,
        exit_code=completed.returncode,
        timed_out=False,
        stdout_lines=_bounded_lines(completed.stdout),
        stderr_lines=_bounded_lines(completed.stderr),
    )


def _validate_reviewed_dns_command_plan(
    command_plan: ResearchKaliOperationCommandPlan,
) -> None:
    """Independently re-prove every reviewed fact before any subprocess
    attempt; defense in depth against a hypothetical upstream bug."""
    if command_plan.transport is not ResearchKaliCommandTransport.GUEST_AGENT:
        raise ResearchError(_REASON_WRONG_TRANSPORT)
    if command_plan.executable_path != _DIG_EXECUTABLE_PATH:
        raise ResearchError(_REASON_WRONG_EXECUTABLE)
    if command_plan.shell is not False:
        raise ResearchError(_REASON_SHELL_NOT_ALLOWED)
    if command_plan.stdin != "closed":
        raise ResearchError(_REASON_STDIN_NOT_CLOSED)

    argv = command_plan.argv
    if len(argv) != _DIG_ARGV_LENGTH:
        raise ResearchError(_REASON_ARGV_LENGTH)
    if argv[: len(_DIG_ARGV_PREFIX)] != _DIG_ARGV_PREFIX:
        raise ResearchError(_REASON_ARGV_PREFIX)

    hostname = argv[len(_DIG_ARGV_PREFIX)]
    if (
        not isinstance(hostname, str)
        or not hostname.strip()
        or len(hostname) > MAX_KALI_OPERATION_HOSTNAME_CHARACTERS
        or "\x00" in hostname
        or "\r" in hostname
        or "\n" in hostname
    ):
        raise ResearchError(_REASON_HOSTNAME_SHAPE)

    record_type = argv[len(_DIG_ARGV_PREFIX) + 1]
    if record_type not in _SUPPORTED_DNS_RECORD_TYPE_VALUES:
        raise ResearchError(_REASON_RECORD_TYPE)


def _bounded_lines(value: object) -> tuple[str, ...]:
    if not value:
        return ()
    text = value if isinstance(value, str) else str(value)
    cleaned = "".join(
        (
            character
            if character == "\n" or (character >= " " and character != "\x7f")
            else "�"
        )
        for character in text
    )
    lines = tuple(
        line[:MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS]
        for line in cleaned.splitlines()
        if line
    )
    return lines[:MAX_KALI_OPERATION_OUTPUT_LINES]
