"""One frozen, append-only fact about a completed HTTPS header-lookup operation.

Populated only where the one real producer — a completed,
authorization-gated `ResearchKaliOperationRun` whose `HTTPS_HEADER_LOOKUP`
result was parsed by `research.ResearchHttpsHeaderLookupResultParser` — can
honestly claim to know something. `scheme`/`port`/`path`/`request_method` are
literal, code-owned facts about the one reviewed operation profile that can
ever produce this record (always `"https"`/`443`/`"/"`/`"HEAD"`), never a
guess about what a different request might have done.

`request_headers_observed` is hard-pinned `False`: `curl --head` never reveals
what it actually sent on the wire, so this producer can never honestly claim
to have observed request headers. `response_body_observed` is hard-pinned
`False`: a HEAD request structurally never returns a body. Both are explicit
booleans rather than an implied empty value, so "not observed" can never be
silently read as "observed and empty" — a fabricated claim this milestone
must never make (mirrors `ResearchKaliOperationEvidenceCandidate`'s
hard-pinned-`False`-fields discipline for the same reason).

`response_status_code` is `None` exactly when the underlying operation did
not complete successfully — never a guessed `200`.

`evidence_id` is not a random UUID. It is the deterministic digest returned
by `http_evidence_id` over `(program_id, operation_digest, exit_code,
timed_out, stdout_lines)` — the exact content that makes two ingestions "the
same observed event." A byte-identical replayed run always yields the same
`evidence_id`; a later, genuinely different response from the same reviewed
operation yields a different one and is preserved as a separate event, never
merged or overwritten. This module can only validate the *shape* of a
supplied `evidence_id` (a 64-character lowercase hex digest) — it cannot
recompute it from the record's own stored fields, since the raw process facts
that feed the digest (`exit_code`/`timed_out`/`stdout_lines`) are not
themselves persisted here. `ResearchHttpEvidenceApplicationService` is the one
place that computes it correctly before ever constructing a record, mirroring
how `ResearchAssetObservationRecord` trusts an externally supplied
`observation_id`.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchHttpEvidenceProvenanceKind import (
    ResearchHttpEvidenceProvenanceKind,
)
from research.ResearchHttpHeaderRecord import ResearchHttpHeaderRecord
from research.ResearchKaliOperationPreview import is_kali_operation_digest
from research.ResearchTargetScope import canonical_dns_hostname

MAX_HTTP_EVIDENCE_PROGRAM_ID_CHARACTERS = 200
MAX_HTTP_EVIDENCE_RESPONSE_HEADERS = 100

_HTTP_EVIDENCE_ID_SCHEMA = "hypatia:http-evidence-id:v1"
_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")

_ALLOWED_SCHEME = "https"
_ALLOWED_PORT = 443
_ALLOWED_PATH = "/"
_ALLOWED_METHOD = "HEAD"


def is_http_evidence_id(value: object) -> bool:
    """Return whether a value can name one deterministic HTTP evidence event."""
    return isinstance(value, str) and _SHA256_HEX_PATTERN.fullmatch(value) is not None


def http_evidence_id(
    *,
    program_id: str,
    operation_digest: str,
    exit_code: int,
    timed_out: bool,
    stdout_lines: tuple[str, ...],
) -> str:
    """Deterministically name one observed event from the exact facts that define it.

    Mirrors `ResearchKaliOperationPreview.kali_operation_preview_digest`'s
    canonical-JSON-then-sha256 pattern. A byte-identical replayed run (same
    program, same reviewed operation, same exit code, same timeout flag, same
    stdout) always yields the same ID; a genuinely different response (even
    from the same reviewed operation) yields a different one, so replay can
    never duplicate an event nor fabricate a new one from identical facts.
    """
    if not isinstance(program_id, str) or not program_id.strip():
        raise ResearchError("HTTP evidence ID requires a program ID.")
    if not is_kali_operation_digest(operation_digest):
        raise ResearchError("HTTP evidence ID requires a valid operation digest.")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise ResearchError("HTTP evidence ID requires an integer exit code.")
    if not isinstance(timed_out, bool):
        raise ResearchError("HTTP evidence ID requires a boolean timeout flag.")
    if not isinstance(stdout_lines, tuple) or any(
        not isinstance(line, str) for line in stdout_lines
    ):
        raise ResearchError("HTTP evidence ID requires immutable stdout lines.")
    encoded = json.dumps(
        {
            "schema": _HTTP_EVIDENCE_ID_SCHEMA,
            "program_id": program_id,
            "operation_digest": operation_digest,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stdout_lines": list(stdout_lines),
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ResearchHttpEvidenceRecord:
    """One immutable HTTP evidence event derived from a completed Kali run."""

    evidence_id: str
    program_id: str
    target_kind: ResearchAssetKind
    target_canonical_value: str
    scheme: str
    port: int
    path: str
    request_method: str
    request_headers_observed: bool
    response_status_code: int | None
    response_headers: tuple[ResearchHttpHeaderRecord, ...]
    response_body_observed: bool
    provenance: ResearchHttpEvidenceProvenanceKind
    source_operation_digest: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not is_http_evidence_id(self.evidence_id):
            raise ResearchError("HTTP evidence ID is invalid.")
        if (
            not isinstance(self.program_id, str)
            or not self.program_id.strip()
            or len(self.program_id) > MAX_HTTP_EVIDENCE_PROGRAM_ID_CHARACTERS
        ):
            raise ResearchError("HTTP evidence program ID is invalid.")
        if self.target_kind is not ResearchAssetKind.HOSTNAME:
            raise ResearchError("HTTP evidence target kind is invalid.")
        if (
            not isinstance(self.target_canonical_value, str)
            or not self.target_canonical_value
        ):
            raise ResearchError("HTTP evidence target value cannot be empty.")
        if self.target_canonical_value != canonical_dns_hostname(
            self.target_canonical_value
        ):
            raise ResearchError("HTTP evidence target value is not canonical.")
        if self.scheme != _ALLOWED_SCHEME:
            raise ResearchError("HTTP evidence scheme is invalid.")
        if self.port != _ALLOWED_PORT:
            raise ResearchError("HTTP evidence port is invalid.")
        if self.path != _ALLOWED_PATH:
            raise ResearchError("HTTP evidence path is invalid.")
        if self.request_method != _ALLOWED_METHOD:
            raise ResearchError("HTTP evidence request method is invalid.")
        if self.request_headers_observed is not False:
            raise ResearchError(
                "HTTP evidence cannot claim request headers were observed."
            )
        if self.response_status_code is not None:
            if (
                isinstance(self.response_status_code, bool)
                or not isinstance(self.response_status_code, int)
                or not 100 <= self.response_status_code <= 599
            ):
                raise ResearchError("HTTP evidence response status code is invalid.")
        if not isinstance(self.response_headers, tuple) or any(
            not isinstance(header, ResearchHttpHeaderRecord)
            for header in self.response_headers
        ):
            raise ResearchError("HTTP evidence response headers are invalid.")
        if len(self.response_headers) > MAX_HTTP_EVIDENCE_RESPONSE_HEADERS:
            raise ResearchError("HTTP evidence has too many response headers.")
        if self.response_status_code is None and self.response_headers:
            raise ResearchError(
                "HTTP evidence cannot carry headers without an observed status."
            )
        if self.response_body_observed is not False:
            raise ResearchError(
                "HTTP evidence cannot claim a response body was observed."
            )
        if not isinstance(self.provenance, ResearchHttpEvidenceProvenanceKind):
            raise ResearchError("HTTP evidence provenance is invalid.")
        if not is_kali_operation_digest(self.source_operation_digest):
            raise ResearchError("HTTP evidence source operation digest is invalid.")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError("HTTP evidence recorded time must be timezone-aware.")
