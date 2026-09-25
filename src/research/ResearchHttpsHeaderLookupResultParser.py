"""Pure parser turning one completed HTTPS header lookup run into facts.

Deterministic, no network, no process, no model call — a pure function over
an already-completed `ResearchKaliOperationRun`. This module never trusts a
cached hostname/port field: it re-derives both from the reviewed command
plan's `--resolve` argv element and re-canonicalizes the hostname through
`ResearchTargetScope.canonical_dns_hostname`, then validates the URL argument
matches exactly — the same "never trust, re-derive and check" discipline the
v0.3.408 DNS parser used.

The reviewed `HTTPS_HEADER_LOOKUP` command plan
(`ResearchKaliOperationPreview.kali_operation_command_plan`) is always exactly
`curl --head --silent --show-error --max-time 10 --proto =https --resolve
<hostname>:443:<address> https://<hostname>/` — 11 argv elements, never
operator-influenceable beyond the hostname/address already bound by the
reviewed preview.

On a nonzero exit code or `timed_out=True`: zero headers, `None` status, one
bounded rejection reason — never a guessed status. On success: a real
`curl --head` success always emits an `HTTP/<version> <code> [<reason>]`
status line as its first line of output, so a missing or malformed one is a
structural contract break and the whole run is rejected outright
(`ResearchError`), not silently downgraded to a partial result. Each
remaining non-blank line must contain a `:` to become a header — header
values can legitimately contain `:` themselves (for example a `Link` header),
so only the *first* `:` on the line separates name from value. A line with no
`:` becomes an inert rejected line with a bounded literal reason, never
interpreted. Blank lines are silently skipped: normal curl header-block
termination, not an error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchHttpHeaderRecord import ResearchHttpHeaderRecord
from research.ResearchKaliOperationExecution import ResearchKaliOperationRun
from research.ResearchKaliOperationPreview import ResearchKaliOperationKind
from research.ResearchTargetScope import canonical_dns_hostname

MAX_HTTPS_HEADER_LOOKUP_RAW_LINE_CHARACTERS = 500
MAX_HTTPS_HEADER_LOOKUP_REASON_CHARACTERS = 200

_EXPECTED_ARGV_LENGTH = 11
_RESOLVE_ARGV_INDEX = 9
_URL_ARGV_INDEX = 10
_ALLOWED_PORT = 443

_STATUS_LINE_PATTERN = re.compile(
    r"^HTTP/\d+(?:\.\d+)?[ \t]+(?P<code>\d{3})(?:[ \t]+.*)?$"
)

_UNSUCCESSFUL_OPERATION_REASON = "Kali operation did not complete successfully."
_NOT_A_HEADER_REASON = "Line does not contain a header separator."
_EMPTY_HEADER_NAME_REASON = "Header name is empty."


@dataclass(frozen=True, slots=True)
class ResearchHttpsHeaderLookupRejectedLine:
    """One `stdout_lines` entry (after the status line) that is not a header.

    `raw_line` is preserved verbatim as inert display data only — never
    parsed, executed, or treated as an intent, even if it looks like a shell
    command or an instruction.
    """

    raw_line: str
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.raw_line, str) or "\x00" in self.raw_line:
            raise ResearchError("HTTPS header lookup rejected line is invalid.")
        if len(self.raw_line) > MAX_HTTPS_HEADER_LOOKUP_RAW_LINE_CHARACTERS:
            raise ResearchError("HTTPS header lookup rejected line is too long.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError("HTTPS header lookup rejected reason cannot be empty.")
        if len(self.reason) > MAX_HTTPS_HEADER_LOOKUP_REASON_CHARACTERS:
            raise ResearchError("HTTPS header lookup rejected reason is too long.")


@dataclass(frozen=True, slots=True)
class ResearchHttpsHeaderLookupResult:
    """The structured facts one completed `HTTPS_HEADER_LOOKUP` run can honestly yield.

    `hostname` is already canonical (`canonical_dns_hostname`). This result
    says only what the run returned at the time it ran — it never says a
    target is reachable, in scope, or currently answers the same way, and a
    `Location` header here is inert descriptive text, never a followed
    redirect.
    """

    hostname: str
    port: int
    status_code: int | None
    headers: tuple[ResearchHttpHeaderRecord, ...]
    rejected_lines: tuple[ResearchHttpsHeaderLookupRejectedLine, ...]

    def __post_init__(self) -> None:
        if self.hostname != canonical_dns_hostname(self.hostname):
            raise ResearchError("HTTPS header lookup result hostname is not canonical.")
        if self.port != _ALLOWED_PORT:
            raise ResearchError("HTTPS header lookup result port is invalid.")
        if self.status_code is not None:
            if (
                isinstance(self.status_code, bool)
                or not isinstance(self.status_code, int)
                or not 100 <= self.status_code <= 599
            ):
                raise ResearchError("HTTPS header lookup result status is invalid.")
        if not isinstance(self.headers, tuple) or any(
            not isinstance(header, ResearchHttpHeaderRecord) for header in self.headers
        ):
            raise ResearchError("HTTPS header lookup result headers are invalid.")
        if self.status_code is None and self.headers:
            raise ResearchError(
                "HTTPS header lookup result cannot carry headers without a status."
            )
        if not isinstance(self.rejected_lines, tuple) or any(
            not isinstance(row, ResearchHttpsHeaderLookupRejectedLine)
            for row in self.rejected_lines
        ):
            raise ResearchError(
                "HTTPS header lookup result rejected lines are invalid."
            )


def parse_https_header_lookup_result(
    run: ResearchKaliOperationRun,
) -> ResearchHttpsHeaderLookupResult:
    """Classify one completed HTTPS header lookup run's output; never mutate/execute."""
    if not isinstance(run, ResearchKaliOperationRun):
        raise ResearchError("Kali operation run is invalid.")
    if run.operation_kind is not ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP:
        raise ResearchError(
            "Only an HTTPS header lookup run can be parsed into HTTP evidence."
        )
    argv = run.command_plan.argv
    if len(argv) != _EXPECTED_ARGV_LENGTH:
        raise ResearchError(
            "HTTPS header lookup command plan argv shape is unexpected."
        )
    resolve_arg = argv[_RESOLVE_ARGV_INDEX]
    url_arg = argv[_URL_ARGV_INDEX]
    resolve_parts = resolve_arg.split(":", 2)
    if len(resolve_parts) != 3:
        raise ResearchError("HTTPS header lookup resolve argument shape is unexpected.")
    raw_hostname, raw_port, _raw_address = resolve_parts
    if raw_port != str(_ALLOWED_PORT):
        raise ResearchError("HTTPS header lookup resolve port is unexpected.")
    if url_arg != f"https://{raw_hostname}/":
        raise ResearchError(
            "HTTPS header lookup URL argument does not match the hostname."
        )
    hostname = canonical_dns_hostname(raw_hostname)
    process_result = run.process_result
    if process_result.exit_code != 0 or process_result.timed_out:
        return ResearchHttpsHeaderLookupResult(
            hostname=hostname,
            port=_ALLOWED_PORT,
            status_code=None,
            headers=(),
            rejected_lines=(
                ResearchHttpsHeaderLookupRejectedLine(
                    raw_line="", reason=_UNSUCCESSFUL_OPERATION_REASON
                ),
            ),
        )
    stdout_lines = process_result.stdout_lines
    if not stdout_lines:
        raise ResearchError(
            "A successful HTTPS header lookup must produce a status line."
        )
    match = _STATUS_LINE_PATTERN.fullmatch(stdout_lines[0])
    if match is None:
        raise ResearchError("HTTPS header lookup status line is malformed.")
    status_code = int(match.group("code"))
    headers: list[ResearchHttpHeaderRecord] = []
    rejected_lines: list[ResearchHttpsHeaderLookupRejectedLine] = []
    for raw_line in stdout_lines[1:]:
        if not raw_line.strip():
            continue
        if ":" not in raw_line:
            rejected_lines.append(
                ResearchHttpsHeaderLookupRejectedLine(
                    raw_line=raw_line, reason=_NOT_A_HEADER_REASON
                )
            )
            continue
        raw_name, _, raw_value = raw_line.partition(":")
        name, value = raw_name.strip(), raw_value.strip()
        if not name:
            rejected_lines.append(
                ResearchHttpsHeaderLookupRejectedLine(
                    raw_line=raw_line, reason=_EMPTY_HEADER_NAME_REASON
                )
            )
            continue
        headers.append(ResearchHttpHeaderRecord(name=name, value=value))
    return ResearchHttpsHeaderLookupResult(
        hostname=hostname,
        port=_ALLOWED_PORT,
        status_code=status_code,
        headers=tuple(headers),
        rejected_lines=tuple(rejected_lines),
    )
