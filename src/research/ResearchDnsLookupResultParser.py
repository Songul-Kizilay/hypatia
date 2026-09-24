"""Pure parser turning one completed DNS lookup Kali operation run into facts.

Deterministic, no network, no process, no model call — a pure function over
an already-completed `ResearchKaliOperationRun`. This module never trusts the
preview's own simpler `.strip().lower().removesuffix(".")` hostname
normalization as sufficient: it re-derives the queried hostname from the
reviewed command plan's argv and re-canonicalizes it through
`ResearchTargetScope.canonical_dns_hostname`, the same normalization scope
matching itself uses.

Only `DNS_RECORD_LOOKUP` runs with an `A` or `AAAA` record type are accepted;
`CNAME` (and anything else) is rejected outright with a `ResearchError` —
there is no hostname-to-hostname relation kind to honestly hold a CNAME chain
result yet, so the whole run is refused rather than silently downgraded.

Each `stdout_lines` entry is classified as either an accepted address of the
record type's IP version, or a rejected line carrying a bounded, generic,
literal reason. A rejected line's raw text is preserved only as inert display
data — it is never interpreted as an instruction, a control-flow input, or
anything beyond a string to show an operator. A nonzero exit code or
`timed_out=True` yields zero accepted rows with one explicit rejected-row
reason instead of attempting to classify possibly-partial output. Empty
output with a clean exit is zero accepted rows, not an error — a real,
honestly-recorded NXDOMAIN-shaped result.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchKaliOperationExecution import ResearchKaliOperationRun
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
)
from research.ResearchTargetScope import canonical_dns_hostname

MAX_DNS_LOOKUP_RAW_LINE_CHARACTERS = 500
MAX_DNS_LOOKUP_REASON_CHARACTERS = 200

_RECORD_TYPE_IP_VERSION: dict[ResearchDnsRecordType, int] = {
    ResearchDnsRecordType.A: 4,
    ResearchDnsRecordType.AAAA: 6,
}

_UNSUCCESSFUL_OPERATION_REASON = "Kali operation did not complete successfully."
_NOT_AN_ADDRESS_REASON = "Line is not a valid IP address."


@dataclass(frozen=True, slots=True)
class ResearchDnsLookupRejectedRow:
    """One `stdout_lines` entry that could not become an accepted address.

    `raw_line` is preserved verbatim as inert display data only — never
    parsed, executed, or treated as an intent, even if it looks like a shell
    command or an instruction.
    """

    raw_line: str
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.raw_line, str) or "\x00" in self.raw_line:
            raise ResearchError("DNS lookup rejected row line is invalid.")
        if len(self.raw_line) > MAX_DNS_LOOKUP_RAW_LINE_CHARACTERS:
            raise ResearchError("DNS lookup rejected row line is too long.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError("DNS lookup rejected row reason cannot be empty.")
        if len(self.reason) > MAX_DNS_LOOKUP_REASON_CHARACTERS:
            raise ResearchError("DNS lookup rejected row reason is too long.")


@dataclass(frozen=True, slots=True)
class ResearchDnsLookupResult:
    """The structured facts one completed `DNS_RECORD_LOOKUP` run can honestly yield.

    `hostname` and every entry of `accepted_addresses` are already canonical
    (`canonical_dns_hostname`/`canonicalize_asset_value`). This result says
    only what the run returned at the time it ran — it never says a hostname
    is reachable, in scope, or currently resolves the same way.
    """

    hostname: str
    record_type: ResearchDnsRecordType
    accepted_addresses: tuple[str, ...]
    rejected_rows: tuple[ResearchDnsLookupRejectedRow, ...]

    def __post_init__(self) -> None:
        if self.hostname != canonical_dns_hostname(self.hostname):
            raise ResearchError("DNS lookup result hostname is not canonical.")
        if self.record_type not in _RECORD_TYPE_IP_VERSION:
            raise ResearchError("DNS lookup result record type is not supported.")
        if not isinstance(self.accepted_addresses, tuple):
            raise ResearchError("DNS lookup result addresses must be immutable.")
        expected_version = _RECORD_TYPE_IP_VERSION[self.record_type]
        for address in self.accepted_addresses:
            if canonicalize_asset_value(ResearchAssetKind.IP_ADDRESS, address) != (
                address
            ):
                raise ResearchError("DNS lookup result address is not canonical.")
            if ipaddress.ip_address(address).version != expected_version:
                raise ResearchError(
                    "DNS lookup result address does not match the record type."
                )
        if not isinstance(self.rejected_rows, tuple) or any(
            not isinstance(row, ResearchDnsLookupRejectedRow)
            for row in self.rejected_rows
        ):
            raise ResearchError("DNS lookup result rejected rows are invalid.")


def parse_dns_lookup_result(run: ResearchKaliOperationRun) -> ResearchDnsLookupResult:
    """Classify one completed DNS lookup run's output; never mutate or execute it."""
    if not isinstance(run, ResearchKaliOperationRun):
        raise ResearchError("Kali operation run is invalid.")
    if run.operation_kind is not ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
        raise ResearchError(
            "Only a DNS record lookup run can be parsed into asset facts."
        )
    argv = run.command_plan.argv
    if len(argv) != 6:
        raise ResearchError("DNS lookup command plan argv shape is unexpected.")
    raw_hostname, raw_record_type = argv[4], argv[5]
    try:
        record_type = ResearchDnsRecordType(raw_record_type)
    except ValueError as error:
        raise ResearchError("DNS lookup record type is not recognised.") from error
    if record_type not in _RECORD_TYPE_IP_VERSION:
        raise ResearchError(
            "CNAME is not supported by this milestone's hostname-to-address"
            " relation."
        )
    hostname = canonical_dns_hostname(raw_hostname)
    process_result = run.process_result
    if process_result.exit_code != 0 or process_result.timed_out:
        return ResearchDnsLookupResult(
            hostname=hostname,
            record_type=record_type,
            accepted_addresses=(),
            rejected_rows=(
                ResearchDnsLookupRejectedRow(
                    raw_line="", reason=_UNSUCCESSFUL_OPERATION_REASON
                ),
            ),
        )
    expected_version = _RECORD_TYPE_IP_VERSION[record_type]
    accepted: list[str] = []
    rejected: list[ResearchDnsLookupRejectedRow] = []
    for raw_line in process_result.stdout_lines:
        stripped = raw_line.strip()
        if not stripped:
            rejected.append(
                ResearchDnsLookupRejectedRow(raw_line=raw_line, reason="Line is empty.")
            )
            continue
        try:
            canonical_address = canonicalize_asset_value(
                ResearchAssetKind.IP_ADDRESS, stripped
            )
        except ResearchError:
            rejected.append(
                ResearchDnsLookupRejectedRow(
                    raw_line=raw_line, reason=_NOT_AN_ADDRESS_REASON
                )
            )
            continue
        if ipaddress.ip_address(canonical_address).version != expected_version:
            rejected.append(
                ResearchDnsLookupRejectedRow(
                    raw_line=raw_line,
                    reason=f"Line is not an IPv{expected_version} address.",
                )
            )
            continue
        if canonical_address not in accepted:
            accepted.append(canonical_address)
    return ResearchDnsLookupResult(
        hostname=hostname,
        record_type=record_type,
        accepted_addresses=tuple(accepted),
        rejected_rows=tuple(rejected),
    )
