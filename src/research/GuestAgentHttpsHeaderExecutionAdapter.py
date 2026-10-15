"""First real Guest-Agent HTTPS_HEADER_LOOKUP executor adapter.

This module introduces exactly ONE real target-operation process
capability: one `/usr/bin/curl --head` request to one already-authorized
hostname, pinned by `--resolve` to one already-authorized resolved IP
address, on fixed port 443. It has ZERO production callers after this
milestone -- it is not wired into
`research.GuestAgentSignedDispatchRpcTransport`, `Bootstrap`,
`CognitiveEngine`, chat, or the desktop. A future milestone will
separately authorize RPC wiring; this module only proves the narrowest
possible HTTPS executor can exist, gated entirely by the exact
execution-admission boundary v0.3.468 already delivered, mirroring the
existing v0.3.469 DNS executor adapter's own shape exactly.

WHY HTTPS NEEDED A SEPARATE SAFETY AUDIT BEFORE THIS MODULE COULD EXIST:
unlike `dig`, which receives a hostname as a single, argv-safe, non-URL
parameter, curl is handed a URL string and a `--resolve` binding string,
both built by string interpolation around a hostname. A curl invocation
also inherits ambient process state (a `~/.curlrc` config file, proxy
environment variables) that `dig` never consults for anything
security-relevant. This milestone's audit, reviewing curl's documented
behavior for the reviewed, fixed, code-owned argv
`research.ResearchKaliOperationPreview.kali_operation_command_plan`
produces for `HTTPS_HEADER_LOOKUP`, found and closed two real gaps before
this module could safely exist, and confirmed three properties already
held:

  1. CLOSED -- default `.curlrc` loading: curl reads a user config file
     by default unless `-q` (curl's own "disable" switch) is the very
     first parameter on the command line. The reviewed argv now carries
     `-q` as `argv[1]`, immediately after the executable path.
  2. CLOSED -- proxy environment variables: curl honors
     `HTTPS_PROXY`/`https_proxy`/`ALL_PROXY`/`http_proxy`/equivalents by
     default, which could redirect the actual network destination away
     from the pinned `--resolve` address. The reviewed argv now carries
     `--noproxy "*"`, which forces curl to never use a proxy for this
     request regardless of ambient environment. This module additionally
     never passes this process's own environment to `subprocess.run`: see
     `_SANITIZED_SUBPROCESS_ENVIRONMENT` below -- defense in depth, not
     the only protection.
  3. ALREADY CORRECT -- protocol switching: `--proto =https` already
     restricts curl to exactly HTTPS for this transfer.
  4. ALREADY CORRECT -- redirects: the reviewed argv carries no
     `-L`/`--location`/`--location-trusted`; curl does not follow
     redirects unless one of those is present. A 3xx response is simply
     untrusted output this module never acts on.
  5. ALREADY CORRECT -- TLS verification: the reviewed argv carries no
     `-k`/`--insecure`/`--proxy-insecure`; curl's normal certificate and
     hostname verification (SNI against the URL's own hostname) stays
     enabled. `--resolve` pins the network address; it does not change
     which hostname curl validates the certificate against.

HOSTNAME TEXT != URL AUTHORITY UNTIL VALIDATED:
`research.ResearchKaliOperationPreview.kali_operation_command_plan` itself
now independently proves (reusing, never re-inventing,
`research.ResearchTargetScope.canonical_dns_hostname`) that the hostname
embedded in both the `--resolve` binding and the request URL is a safe DNS
name before either string is ever built -- see that module's own
docstring. `_validate_reviewed_https_command_plan` below re-proves this a
second, independent time, immediately before `subprocess.run`, exactly
mirroring the existing DNS executor adapter's own equivalent defense-in-
depth validator and its "defense in depth against a hypothetical future
bug upstream, never trust-by-existence" discipline:
it re-derives the hostname from the `--resolve` token and independently
re-validates it both against `canonical_dns_hostname` and, via
`urllib.parse.urlsplit`, against the URL token -- proving no userinfo,
port, path, query, or fragment component was smuggled into either string.
ARGV SAFE != URL SEMANTICS SAFE: `ResearchKaliOperationCommandPlan
.__post_init__` already proves argv elements contain no control data, but
that alone does not prove a string is a safe *URL authority* -- this
function proves that second, distinct fact.

RESOLVED ADDRESS BINDING: this module consumes ONLY the resolved address
already bound through verified dispatch -> prepared invocation ->
runtime-ready invocation -> exact `GuestAgentExecutionAdmission` -- there
is no separate IP argument, no DNS re-resolution, and no fallback address
anywhere in this module. `_validate_reviewed_https_command_plan`
independently re-parses the `--resolve` token's address with the stdlib
`ipaddress` module (the same parser
`research.ResearchKaliOperationPreview` already uses), proving IPv4
addresses are bare and IPv6 addresses are bracketed exactly as curl's
`--resolve` syntax requires. HOSTNAME AUTHORITY != RESOLVED ADDRESS
AUTHORITY.

EXECUTION ADMISSION != EXECUTION SUCCESS. EXECUTOR DOES NOT CREATE
AUTHORITY. This adapter's one entry point,
`execute_guest_agent_https_header_lookup`, accepts ONLY a real,
unforgeable `research.GuestAgentExecutionAdmission.GuestAgentExecutionAdmission`
-- never a `GuestAgentRequest`, a `GuestAgentVerifiedDispatch` alone, a
`GuestAgentPreparedInvocation` alone, a `GuestAgentRuntimeReadyInvocation`
alone, a hostname, a resolved address, a URL, an executable path, an argv
tuple, a command string, headers, a proxy value, a TLS option, a
callback, or a shell string. The executable path, argv, and timeout are
read ONLY from
`execution_admission.runtime_ready_invocation.prepared_invocation
.command_plan`/`.timeout_seconds`.

HTTPS ONLY: `execute_guest_agent_https_header_lookup` supports exactly
`research.ResearchKaliOperationPreview.ResearchKaliOperationKind
.HTTPS_HEADER_LOOKUP`. `DNS_RECORD_LOOKUP` -- and any future operation
kind -- fails closed before `subprocess.run` is ever reached.

ONE HTTPS ADMISSION != AUTHORITY FOR A SECOND DESTINATION. ONE HTTPS
ADMISSION != RETRY AUTHORITY. ONE ATTEMPT, NO RETRY: this module calls
`subprocess.run` at most once per call, with `shell=False`,
`stdin=subprocess.DEVNULL`, `check=False`, the exact admitted,
already-capped `timeout_seconds` (SIGNED EXECUTION LIMIT != CURL INTERNAL
LIMIT: curl's own fixed `--max-time 10` is a separate, independent bound
baked into the reviewed argv itself -- the outer `subprocess.run` timeout
from the signed invocation is never widened to accommodate it, and
whichever bound is tighter wins), and a fixed, minimal, code-owned
`env` -- never this process's own environment, and never a
caller-controlled mapping (`_SANITIZED_SUBPROCESS_ENVIRONMENT`). No loop,
no retry, no fallback executable, and no manual Location-header following
exists anywhere in this module.

`GuestAgentHttpsHeaderExecutionResult` honestly distinguishes whether the
local `curl` process actually started, its exit code (only when the
process both started and did not time out), whether it timed out, and
bounded, sanitized, explicitly `UNTRUSTED PROCESS OUTPUT` stdout/stderr.
HTTPS PROCESS STARTED != HTTPS SUCCESS. CURL EXIT 0 != TRUSTED HTTP FACT.
HTTP HEADER OUTPUT != EVIDENCE. HTTP HEADER OUTPUT != VERIFIED FACT.
`evidence_recorded`, `claim_created`, `source_accepted`, and
`memory_written` are all structurally forced `False`: this milestone ends
at a bounded, untrusted process result. No header parsing, evidence
creation, claim creation, source acceptance, memory write, technology
identification, security-header classification, finding creation, CVE
correlation, or follow-up request exists anywhere in this module.

If `subprocess.run` cannot even start the process (`OSError`), this
module raises `core.Exceptions.ResearchError` carrying only the bounded
exception type name, mirroring the existing DNS executor adapter's own
equivalent `OSError` handling -- never raw exception text or a leaked
path.

NO RPC WIRING: this module is never imported by
`research.GuestAgentSignedDispatchRpcTransport`. `HTTPS_HEADER_LOOKUP`
over signed RPC remains non-executing; the DNS RPC execution path
v0.3.470 delivered is unchanged and unexpanded by anything here. A future,
separately authorized milestone will review and decide RPC wiring for
this executor.
"""

from __future__ import annotations

import ipaddress
import subprocess
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlsplit

from core.Exceptions import ResearchError
from research.GuestAgentExecutionAdmission import GuestAgentExecutionAdmission
from research.ResearchKaliOperationExecution import (
    KALI_OPERATION_OUTPUT_TRUST,
    MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
    MAX_KALI_OPERATION_OUTPUT_LINES,
)
from research.ResearchKaliOperationPreview import (
    ResearchKaliCommandTransport,
    ResearchKaliOperationCommandPlan,
    ResearchKaliOperationKind,
)
from research.ResearchTargetScope import canonical_dns_hostname

#: The one reviewed, code-owned absolute executable this module may ever
#: invoke. Never derived from PATH, caller input, or any fallback.
_CURL_EXECUTABLE_PATH: Final[str] = "/usr/bin/curl"

#: The exact fixed argv prefix every reviewed HTTPS command plan must
#: carry, in this exact order. `-q` must be `argv[1]` (immediately after
#: the executable path) for curl to honor it as "disable default config
#: file loading" -- that positional requirement is preserved structurally
#: here, not merely documented. Never built from caller input; a literal
#: tuple only.
_CURL_ARGV_PREFIX: Final[tuple[str, ...]] = (
    "/usr/bin/curl",
    "-q",
    "--head",
    "--silent",
    "--show-error",
    "--noproxy",
    "*",
    "--max-time",
    "10",
    "--proto",
    "=https",
)

#: `_CURL_ARGV_PREFIX` plus exactly `"--resolve"`, one `--resolve` value,
#: and one URL -- never more, never fewer.
_CURL_ARGV_LENGTH: Final[int] = len(_CURL_ARGV_PREFIX) + 3

#: Options this module's defense-in-depth check must never find anywhere
#: in a reviewed HTTPS argv -- redirect-following and TLS-verification
#: bypass options. Checked by substring-free exact-token membership, never
#: a prefix/substring match that could itself be bypassed by an
#: unrelated-looking token.
_FORBIDDEN_REDIRECT_TOKENS: Final[frozenset[str]] = frozenset(
    {"-L", "--location", "--location-trusted"}
)
_FORBIDDEN_INSECURE_TLS_TOKENS: Final[frozenset[str]] = frozenset(
    {"-k", "--insecure", "--proxy-insecure"}
)

#: Minimal, fixed, code-owned subprocess environment. Deliberately never
#: this process's own `os.environ`, and never a caller-supplied mapping:
#: curl must not see this process's own proxy environment variables
#: (`HTTPS_PROXY`/`https_proxy`/`ALL_PROXY`/`NO_PROXY`/equivalents)
#: regardless of what the host process happens to have set. `-q` and
#: `--noproxy "*"` in the reviewed argv already close this at the
#: curl-option level; this is defense in depth, not the only protection.
_SANITIZED_SUBPROCESS_ENVIRONMENT: Final[dict[str, str]] = {"PATH": "/usr/bin:/bin"}

_REASON_UNSUPPORTED_OPERATION = (
    "Guest-agent HTTPS executor supports only HTTPS_HEADER_LOOKUP."
)
_REASON_WRONG_TRANSPORT = (
    "Guest-agent HTTPS executor requires a GUEST_AGENT command plan."
)
_REASON_WRONG_EXECUTABLE = (
    "Guest-agent HTTPS executor requires the reviewed /usr/bin/curl executable."
)
_REASON_SHELL_NOT_ALLOWED = "Guest-agent HTTPS executor must not use a shell."
_REASON_STDIN_NOT_CLOSED = "Guest-agent HTTPS executor requires closed stdin."
_REASON_ARGV_LENGTH = (
    "Guest-agent HTTPS executor requires the exact reviewed argv length."
)
_REASON_ARGV_PREFIX = (
    "Guest-agent HTTPS executor requires the exact reviewed argv prefix."
)
_REASON_RESOLVE_TOKEN = (
    "Guest-agent HTTPS executor requires the exact reviewed --resolve token."
)
_REASON_RESOLVE_SHAPE = (
    "Guest-agent HTTPS executor requires a well-formed --resolve binding."
)
_REASON_UNSAFE_HOSTNAME = "Guest-agent HTTPS executor requires a safe DNS hostname."
_REASON_RESOLVE_PORT = "Guest-agent HTTPS executor requires port 443 in --resolve."
_REASON_RESOLVE_ADDRESS = (
    "Guest-agent HTTPS executor requires a valid resolved address in --resolve."
)
_REASON_URL_SHAPE = "Guest-agent HTTPS executor requires the exact reviewed URL shape."
_REASON_URL_HOSTNAME_MISMATCH = (
    "Guest-agent HTTPS executor requires the URL hostname to match --resolve."
)
_REASON_FORBIDDEN_TOKEN = (
    "Guest-agent HTTPS executor rejects a command plan carrying a forbidden "
    "redirect or insecure-TLS option."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GuestAgentHttpsHeaderExecutionResult:
    """A bounded, honest, untrusted result of one attempted HTTPS HEAD request.

    HTTPS PROCESS STARTED != HTTPS SUCCESS. CURL EXIT 0 != TRUSTED HTTP
    FACT. HTTP HEADER OUTPUT != EVIDENCE. HTTP HEADER OUTPUT != VERIFIED
    FACT -- see the module docstring. `process_created=True` means only
    that the local `curl` process was launched; it never means a TLS
    handshake completed, a response was received, headers are valid, or
    the output is trustworthy.

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
        if self.operation_kind is not ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP:
            raise ResearchError(_REASON_UNSUPPORTED_OPERATION)
        if not isinstance(self.command_plan, ResearchKaliOperationCommandPlan):
            raise ResearchError(
                "Guest-agent HTTPS execution result command plan is invalid."
            )
        if self.command_plan.transport is not ResearchKaliCommandTransport.GUEST_AGENT:
            raise ResearchError(_REASON_WRONG_TRANSPORT)
        if self.command_plan.executable_path != _CURL_EXECUTABLE_PATH:
            raise ResearchError(_REASON_WRONG_EXECUTABLE)
        if not isinstance(self.process_created, bool):
            raise ResearchError(
                "Guest-agent HTTPS execution result process flag is invalid."
            )
        if not isinstance(self.timed_out, bool):
            raise ResearchError(
                "Guest-agent HTTPS execution result timeout flag is invalid."
            )
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise ResearchError(
                "Guest-agent HTTPS execution result exit code is invalid."
            )
        if self.process_created is False and (
            self.exit_code is not None or self.timed_out is not False
        ):
            raise ResearchError(
                "Guest-agent HTTPS execution result must not carry an exit "
                "code or timeout flag when no process was created."
            )
        if self.timed_out is True and self.exit_code is not None:
            raise ResearchError(
                "Guest-agent HTTPS execution result must not carry an exit "
                "code for a timed-out process."
            )
        self._validate_lines(self.stdout_lines, "stdout")
        self._validate_lines(self.stderr_lines, "stderr")
        if self.output_trust != KALI_OPERATION_OUTPUT_TRUST:
            raise ResearchError(
                "Guest-agent HTTPS execution result output trust is invalid."
            )
        if (
            self.evidence_recorded is not False
            or self.claim_created is not False
            or self.source_accepted is not False
            or self.memory_written is not False
        ):
            raise ResearchError(
                "Guest-agent HTTPS execution result must not claim evidence, "
                "a claim, an accepted source, or a memory write."
            )

    @staticmethod
    def _validate_lines(lines: object, label: str) -> None:
        if not isinstance(lines, tuple):
            raise ResearchError(
                f"Guest-agent HTTPS execution result {label} must be immutable."
            )
        if len(lines) > MAX_KALI_OPERATION_OUTPUT_LINES:
            raise ResearchError(
                f"Guest-agent HTTPS execution result {label} has too many lines."
            )
        for line in lines:
            if (
                not isinstance(line, str)
                or "\x00" in line
                or len(line) > MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS
            ):
                raise ResearchError(
                    f"Guest-agent HTTPS execution result {label} is invalid."
                )


def execute_guest_agent_https_header_lookup(
    execution_admission: GuestAgentExecutionAdmission,
) -> GuestAgentHttpsHeaderExecutionResult:
    """Run the one reviewed HTTPS HEAD request; never retry.

    Accepts ONLY a real `GuestAgentExecutionAdmission`. The exact
    executable, argv, and timeout are read exclusively from
    `execution_admission.runtime_ready_invocation.prepared_invocation` --
    there is no parameter through which a caller could supply or widen
    any of them. Raises `core.Exceptions.ResearchError` if the admission
    is the wrong type, if its bound operation is not
    `HTTPS_HEADER_LOOKUP`, if the reviewed command plan fails any
    defense-in-depth cross-check, or if the local process could not be
    started at all (`OSError`, reported only as a bounded exception type
    name). Calls `subprocess.run` at most once.
    """
    if not isinstance(execution_admission, GuestAgentExecutionAdmission):
        raise ResearchError(
            "Guest-agent HTTPS executor requires a real execution admission."
        )

    prepared_invocation = (
        execution_admission.runtime_ready_invocation.prepared_invocation
    )
    operation_kind = prepared_invocation.operation_kind
    if operation_kind is not ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP:
        raise ResearchError(_REASON_UNSUPPORTED_OPERATION)

    command_plan = prepared_invocation.command_plan
    _validate_reviewed_https_command_plan(command_plan)
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
            env=_SANITIZED_SUBPROCESS_ENVIRONMENT,
        )
    except subprocess.TimeoutExpired:
        return GuestAgentHttpsHeaderExecutionResult(
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
            "Unable to start the Guest-Agent HTTPS executor process: "
            f"{type(error).__name__}."
        ) from error

    return GuestAgentHttpsHeaderExecutionResult(
        operation_kind=operation_kind,
        command_plan=command_plan,
        process_created=True,
        exit_code=completed.returncode,
        timed_out=False,
        stdout_lines=_bounded_lines(completed.stdout),
        stderr_lines=_bounded_lines(completed.stderr),
    )


def _validate_reviewed_https_command_plan(
    command_plan: ResearchKaliOperationCommandPlan,
) -> None:
    """Independently re-prove every reviewed fact before any subprocess
    attempt; defense in depth against a hypothetical upstream bug.

    ARGV SAFE != URL SEMANTICS SAFE: beyond the fixed-prefix/length
    checks every reviewed executor in this repository already performs,
    this function additionally re-derives the hostname from the
    `--resolve` token and independently proves it is a safe DNS name
    (`research.ResearchTargetScope.canonical_dns_hostname`) and that the
    URL token names the exact same hostname with no userinfo, port,
    path, query, or fragment component -- via `urllib.parse.urlsplit`,
    never a hand-rolled parser.
    """
    if command_plan.transport is not ResearchKaliCommandTransport.GUEST_AGENT:
        raise ResearchError(_REASON_WRONG_TRANSPORT)
    if command_plan.executable_path != _CURL_EXECUTABLE_PATH:
        raise ResearchError(_REASON_WRONG_EXECUTABLE)
    if command_plan.shell is not False:
        raise ResearchError(_REASON_SHELL_NOT_ALLOWED)
    if command_plan.stdin != "closed":
        raise ResearchError(_REASON_STDIN_NOT_CLOSED)

    argv = command_plan.argv
    if len(argv) != _CURL_ARGV_LENGTH:
        raise ResearchError(_REASON_ARGV_LENGTH)
    if argv[: len(_CURL_ARGV_PREFIX)] != _CURL_ARGV_PREFIX:
        raise ResearchError(_REASON_ARGV_PREFIX)

    forbidden_present = frozenset(argv) & (
        _FORBIDDEN_REDIRECT_TOKENS | _FORBIDDEN_INSECURE_TLS_TOKENS
    )
    if forbidden_present:
        raise ResearchError(_REASON_FORBIDDEN_TOKEN)

    resolve_flag_index = len(_CURL_ARGV_PREFIX)
    if argv[resolve_flag_index] != "--resolve":
        raise ResearchError(_REASON_RESOLVE_TOKEN)

    resolve_value = argv[resolve_flag_index + 1]
    url = argv[resolve_flag_index + 2]

    hostname, port, address = _split_resolve_token(resolve_value)
    if port != "443":
        raise ResearchError(_REASON_RESOLVE_PORT)
    _validate_resolved_address_shape(address)

    try:
        safe_hostname = canonical_dns_hostname(hostname)
    except ResearchError as error:
        raise ResearchError(_REASON_UNSAFE_HOSTNAME) from error
    if safe_hostname != hostname:
        raise ResearchError(_REASON_UNSAFE_HOSTNAME)

    _validate_url_matches_hostname(url, hostname)


def _split_resolve_token(resolve_value: str) -> tuple[str, str, str]:
    """Split `"<hostname>:<port>:<address>"` into its three components.

    The hostname component never contains `:` once it has passed
    `canonical_dns_hostname`, so splitting on the first two colons is
    unambiguous; an IPv6 `<address>` keeps its own internal colons.
    """
    parts = resolve_value.split(":", 2)
    if len(parts) != 3:
        raise ResearchError(_REASON_RESOLVE_SHAPE)
    hostname, port, address = parts
    if not hostname or not port or not address:
        raise ResearchError(_REASON_RESOLVE_SHAPE)
    return hostname, port, address


def _validate_resolved_address_shape(address: str) -> None:
    """Re-prove the `--resolve` address is a valid, exactly-formatted
    IPv4 or bracketed IPv6 literal, reusing the stdlib `ipaddress` parser.
    """
    if address.startswith("[") and address.endswith("]"):
        candidate = address[1:-1]
        try:
            parsed = ipaddress.ip_address(candidate)
        except ValueError as error:
            raise ResearchError(_REASON_RESOLVE_ADDRESS) from error
        if not isinstance(parsed, ipaddress.IPv6Address):
            raise ResearchError(_REASON_RESOLVE_ADDRESS)
        if parsed.compressed != candidate:
            raise ResearchError(_REASON_RESOLVE_ADDRESS)
        return
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as error:
        raise ResearchError(_REASON_RESOLVE_ADDRESS) from error
    if not isinstance(parsed, ipaddress.IPv4Address):
        raise ResearchError(_REASON_RESOLVE_ADDRESS)
    if parsed.compressed != address:
        raise ResearchError(_REASON_RESOLVE_ADDRESS)


def _validate_url_matches_hostname(url: str, hostname: str) -> None:
    """Prove `url` is exactly `https://<hostname>/` with no userinfo,
    port, path, query, or fragment -- via `urllib.parse.urlsplit`, never
    a hand-rolled parser. URL TEXT != EXECUTION AUTHORITY."""
    if not url.isascii():
        raise ResearchError(_REASON_URL_SHAPE)
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise ResearchError(_REASON_URL_SHAPE)
    if parsed.username is not None or parsed.password is not None:
        raise ResearchError(_REASON_URL_SHAPE)
    if parsed.port is not None:
        raise ResearchError(_REASON_URL_SHAPE)
    if parsed.path != "/" or parsed.query != "" or parsed.fragment != "":
        raise ResearchError(_REASON_URL_SHAPE)
    if parsed.hostname != hostname:
        raise ResearchError(_REASON_URL_HOSTNAME_MISMATCH)
    if url != f"https://{hostname}/":
        raise ResearchError(_REASON_URL_SHAPE)


def _bounded_lines(value: object) -> tuple[str, ...]:
    if not value:
        return ()
    text = value if isinstance(value, str) else str(value)
    cleaned = "".join(
        (
            character
            if character == "\n" or (character >= " " and character != "\x7f")
            else "\N{REPLACEMENT CHARACTER}"
        )
        for character in text
    )
    lines = tuple(
        line[:MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS]
        for line in cleaned.splitlines()
        if line
    )
    return lines[:MAX_KALI_OPERATION_OUTPUT_LINES]
