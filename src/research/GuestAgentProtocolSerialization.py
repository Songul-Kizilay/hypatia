"""Deterministic, pure wire encoding for the Guest-Agent protocol contract.

Reuses the one canonical-JSON convention this repository already has
(`research.ResearchKaliOperationPreview.canonical_kali_operation_preview_bytes`:
`json.dumps(..., sort_keys=True, ensure_ascii=True, separators=(",", ":"),
allow_nan=False)`) rather than inventing a second one. Encoding and decoding
are both pure functions over already-typed or already-parsed data: no
process, no network, no file, no pickle, no `eval`, no YAML object
constructor, and no dynamic import anywhere in this module.

Decoding fails closed on anything it cannot fully account for: an unknown
top-level key, a missing required key, an unrecognized protocol version, an
unrecognized operation kind, an unrecognized response status, or malformed
shapes for any field. Nothing here ever guesses a value or silently
downgrades a future protocol version to this one.
"""

from __future__ import annotations

import json

from core.Exceptions import ResearchError
from research.GuestAgentProtocol import (
    GuestAgentProtocolVersion,
    GuestAgentRequest,
    GuestAgentResponse,
    GuestAgentResponseStatus,
)
from research.ResearchKaliOperationPreview import ResearchKaliOperationKind

_REQUEST_REQUIRED_KEYS = frozenset(
    {
        "protocol_version",
        "request_id",
        "nonce",
        "operation_kind",
        "operation_digest",
    }
)
_REQUEST_OPTIONAL_KEYS = frozenset({"logical_inputs"})
_REQUEST_ALLOWED_KEYS = _REQUEST_REQUIRED_KEYS | _REQUEST_OPTIONAL_KEYS

_RESPONSE_REQUIRED_KEYS = frozenset(
    {"protocol_version", "request_id", "status", "detail"}
)
_RESPONSE_OPTIONAL_KEYS = frozenset({"output_lines", "output_trust"})
_RESPONSE_ALLOWED_KEYS = _RESPONSE_REQUIRED_KEYS | _RESPONSE_OPTIONAL_KEYS


def guest_agent_request_document(request: GuestAgentRequest) -> dict[str, object]:
    """Render one request as a plain, JSON-safe document."""
    if not isinstance(request, GuestAgentRequest):
        raise ResearchError("Guest-agent request document requires a bounded request.")
    return {
        "protocol_version": request.protocol_version.value,
        "request_id": request.request_id,
        "nonce": request.nonce,
        "operation_kind": request.operation_kind.value,
        "operation_digest": request.operation_digest,
        "logical_inputs": [list(pair) for pair in request.logical_inputs],
    }


def canonical_guest_agent_request_bytes(request: GuestAgentRequest) -> bytes:
    """Encode one request as canonical, deterministic JSON bytes."""
    return _canonical_bytes(guest_agent_request_document(request))


def guest_agent_request_from_document(document: object) -> GuestAgentRequest:
    """Parse one request from an already-decoded document; fail closed on
    anything unknown, missing, or malformed."""
    fields = _require_object_with_keys(
        document, _REQUEST_REQUIRED_KEYS, _REQUEST_ALLOWED_KEYS, "request"
    )
    return GuestAgentRequest(
        protocol_version=_parse_protocol_version(
            fields["protocol_version"], "protocol version"
        ),
        request_id=_require_str(fields["request_id"], "request identifier"),
        nonce=_require_str(fields["nonce"], "nonce"),
        operation_kind=_parse_operation_kind(
            fields["operation_kind"], "operation kind"
        ),
        operation_digest=_require_str(fields["operation_digest"], "operation digest"),
        logical_inputs=_parse_logical_inputs(fields.get("logical_inputs", [])),
    )


def guest_agent_request_from_bytes(data: bytes) -> GuestAgentRequest:
    """Parse one request from canonical JSON bytes; fail closed on anything
    that is not exactly this contract."""
    return guest_agent_request_from_document(_parse_json(data))


def guest_agent_response_document(response: GuestAgentResponse) -> dict[str, object]:
    """Render one response as a plain, JSON-safe document."""
    if not isinstance(response, GuestAgentResponse):
        raise ResearchError(
            "Guest-agent response document requires a bounded response."
        )
    return {
        "protocol_version": response.protocol_version.value,
        "request_id": response.request_id,
        "status": response.status.value,
        "detail": response.detail,
        "output_lines": list(response.output_lines),
        "output_trust": response.output_trust,
    }


def canonical_guest_agent_response_bytes(response: GuestAgentResponse) -> bytes:
    """Encode one response as canonical, deterministic JSON bytes."""
    return _canonical_bytes(guest_agent_response_document(response))


def guest_agent_response_from_document(document: object) -> GuestAgentResponse:
    """Parse one response from an already-decoded document; fail closed on
    anything unknown, missing, or malformed."""
    fields = _require_object_with_keys(
        document, _RESPONSE_REQUIRED_KEYS, _RESPONSE_ALLOWED_KEYS, "response"
    )
    protocol_version = _parse_protocol_version(
        fields["protocol_version"], "protocol version"
    )
    request_id = _require_str(fields["request_id"], "request identifier")
    status = _parse_response_status(fields["status"], "response status")
    detail = _require_str(fields["detail"], "detail")
    output_lines = _parse_output_lines(fields.get("output_lines", []))
    if "output_trust" in fields:
        output_trust = _require_str(fields["output_trust"], "output trust")
        return GuestAgentResponse(
            protocol_version=protocol_version,
            request_id=request_id,
            status=status,
            detail=detail,
            output_lines=output_lines,
            output_trust=output_trust,
        )
    return GuestAgentResponse(
        protocol_version=protocol_version,
        request_id=request_id,
        status=status,
        detail=detail,
        output_lines=output_lines,
    )


def guest_agent_response_from_bytes(data: bytes) -> GuestAgentResponse:
    """Parse one response from canonical JSON bytes; fail closed on
    anything that is not exactly this contract."""
    return guest_agent_response_from_document(_parse_json(data))


def _canonical_bytes(document: dict[str, object]) -> bytes:
    """Encode one already-built document using the one canonical-JSON
    convention this repository already has (same `dumps` arguments as
    `research.ResearchKaliOperationPreview.canonical_kali_operation_preview_bytes`).
    """
    return json.dumps(
        document,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _parse_json(data: bytes) -> object:
    if not isinstance(data, bytes):
        raise ResearchError("Guest-agent protocol bytes must be bytes.")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ResearchError("Guest-agent protocol bytes are not valid JSON.") from error


def _require_object_with_keys(
    document: object,
    required_keys: frozenset[str],
    allowed_keys: frozenset[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(document, dict):
        raise ResearchError(f"Guest-agent {label} document must be an object.")
    present = set(document.keys())
    # Deliberately a fixed sentence, never one built from the untrusted key
    # names themselves: a raw top-level JSON key is adversarial input this
    # function has not yet bounded or sanitized in any way, exactly the
    # class of content `GuestAgentResponse.detail`'s own fixed-sentence
    # convention exists to keep out of a raised message.
    if present - allowed_keys:
        raise ResearchError(f"Guest-agent {label} document has unknown field(s).")
    if required_keys - present:
        raise ResearchError(f"Guest-agent {label} document is missing field(s).")
    return document


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ResearchError(f"Guest-agent protocol {label} must be text.")
    return value


def _parse_protocol_version(value: object, label: str) -> GuestAgentProtocolVersion:
    if not isinstance(value, str):
        raise ResearchError(f"Guest-agent protocol {label} must be text.")
    try:
        return GuestAgentProtocolVersion(value)
    except ValueError as error:
        raise ResearchError(
            f"Guest-agent protocol {label} is not recognized."
        ) from error


def _parse_operation_kind(value: object, label: str) -> ResearchKaliOperationKind:
    if not isinstance(value, str):
        raise ResearchError(f"Guest-agent protocol {label} must be text.")
    try:
        return ResearchKaliOperationKind(value)
    except ValueError as error:
        raise ResearchError(
            f"Guest-agent protocol {label} is not recognized."
        ) from error


def _parse_response_status(value: object, label: str) -> GuestAgentResponseStatus:
    if not isinstance(value, str):
        raise ResearchError(f"Guest-agent protocol {label} must be text.")
    try:
        return GuestAgentResponseStatus(value)
    except ValueError as error:
        raise ResearchError(
            f"Guest-agent protocol {label} is not recognized."
        ) from error


def _parse_logical_inputs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise ResearchError("Guest-agent request logical inputs must be a list.")
    pairs = []
    for entry in value:
        if (
            not isinstance(entry, list)
            or len(entry) != 2
            or not isinstance(entry[0], str)
            or not isinstance(entry[1], str)
        ):
            raise ResearchError(
                "Guest-agent request logical input must be a [name, value] pair."
            )
        pairs.append((entry[0], entry[1]))
    return tuple(pairs)


def _parse_output_lines(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ResearchError("Guest-agent response output lines must be a list.")
    lines = []
    for entry in value:
        if not isinstance(entry, str):
            raise ResearchError("Guest-agent response output line must be text.")
        lines.append(entry)
    return tuple(lines)
