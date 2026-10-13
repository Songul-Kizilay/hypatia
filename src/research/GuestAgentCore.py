"""The guest-side application core: inert admission, never execution.

This is the first bounded foundation of roadmap step 5 -- the guest-side
application boundary that will eventually receive an authenticated,
already-decoded `GuestAgentRequest` and decide what happens next. Today it
decides exactly one thing, honestly: whether a request names a reviewed
operation and carries the logical inputs that operation's reviewed shape
requires. It never decides whether the operation may run, because nothing
in this repository yet proves that a request crossing the real RPC
transport (`research.GuestAgentRpcTransport`) was ever actually authorized
by the host's own scope/preview/authorization chain.

AUTHENTICATED REQUEST != AUTHORIZED REQUEST. OPERATION DIGEST !=
AUTHORIZATION. `GuestAgentRequest` carries `operation_digest` as opaque,
caller-supplied correlation data (see `research.GuestAgentProtocol`'s own
docstring) -- it is never recomputed, never compared against a scope or
policy fact, and never treated as proof that
`research.ResearchKaliOperationAuthorizationStore` ever granted anything
for it. This module does not import that store, `cognition.KaliToolGateway`,
or any process adapter, and never will while it remains this inert:
CAPABILITY ALLOWLIST MATCH != EXECUTION AUTHORITY, INPUT SCHEMA VALID !=
EXECUTION AUTHORITY, GUEST ADMISSION SUCCESS != EXECUTION AUTHORITY.

`admit_guest_agent_request` is a pure, deterministic, side-effect-free
function: no socket, no subprocess, no file, no network, no replay-state
consumption (`research.GuestAgentReplayProtector.consume_once` is never
called -- an inert admission must never spend a request's one real future
execution attempt), and no mutation of any host-side authorization record.
It never returns `GuestAgentResponseStatus.SUCCESS`: a structurally valid,
admitted request still only reaches `DECLINED`, because no capability
implementation exists yet to produce a real success. `output_lines` is
always empty -- there is no process output to report, ever, from this
module. Its signature already matches
`research.GuestAgentRpcTransport.GuestAgentRpcRequestHandler`, so it can be
passed directly as the `handler` argument to `GuestAgentRpcServer` without
any adapter; this module intentionally adds no second, generic
`Callable[[GuestAgentRequest], GuestAgentResponse]` execution extension
point of its own -- the RPC transport's existing injection point is the
only one, and this function is the only thing registered there today.

The supported-operation allowlist is a fixed, code-owned literal, never
derived by iterating `research.ResearchKaliOperationPreview
.ResearchKaliOperationKind` itself: CAPABILITY REGISTERED != CAPABILITY
PERMITTED, and a future third member added to that enum must deny by
default here until a deliberate, reviewed edit adds it to
`_OPERATION_REQUIRED_LOGICAL_INPUT_FIELDS` below (see
`tests/research/test_guest_agent_core.py`'s structural proof of this).

Field validation reuses only facts this repository already treats as
authoritative elsewhere, never a second, independently-invented copy of
them: the closed `research.ResearchKaliOperationPreview.ResearchDnsRecordType`
enum (constructing it is itself the validation -- an unrecognized value
raises `ValueError`, exactly as `ResearchKaliOperationPreview` already
relies on), the stdlib `ipaddress.ip_address` parser (the same one
`ResearchKaliOperationPreview`/`kali_operation_command_plan` already call
for `resolved_address`), and the existing
`MAX_KALI_OPERATION_HOSTNAME_CHARACTERS` bound. What this module does
*not* reuse, and does not invent a parallel version of either: the
case-folding/trailing-dot hostname normalization
`ResearchKaliOperationPreview.__post_init__` performs before building a
command plan. That normalization exists only there, is not exposed as a
standalone function this module could call without duplicating its exact
three-line body (which would create a second source of truth for it), and
this milestone's own scope forbids inventing hostname-rewriting logic. The
honest, narrower claim this module makes instead: a `hostname` logical
input must be non-empty and within the existing reviewed length bound --
nothing here proves it is syntactically a well-formed DNS name, proves it
matches case/trailing-dot-insensitively what any host-side preview named,
or performs any lookup. `tools.ProductCapabilitySchema`/
`tools.GuestAgentRequestSchemaValidation` were audited and are
deliberately not imported here: `tools` already depends on `research`
(see `tools.ProductCapabilitySchemaDefaults`), so the reverse import would
invert that existing layering -- confirmed by inspection, not assumed.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from typing import Final

from core.Exceptions import ResearchError
from research.GuestAgentProtocol import (
    GuestAgentRequest,
    GuestAgentResponse,
    GuestAgentResponseStatus,
)
from research.ResearchKaliOperationPreview import (
    MAX_KALI_OPERATION_HOSTNAME_CHARACTERS,
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
)

#: Logical-input field names this module recognizes. Plain data-field
#: names, never executable identity -- see the module docstring's "no
#: arbitrary command channel" guarantee.
_FIELD_HOSTNAME: Final[str] = "hostname"
_FIELD_DNS_RECORD_TYPE: Final[str] = "dns_record_type"
_FIELD_RESOLVED_ADDRESS: Final[str] = "resolved_address"

#: The one fixed, code-owned admission allowlist. A hypothetical future
#: `ResearchKaliOperationKind` member is denied by default -- it simply has
#: no entry here -- until a deliberate, reviewed edit adds one. Never
#: constructed by iterating the enum class itself; built only from named
#: members, so adding one there changes nothing here automatically. See
#: `tests/research/test_guest_agent_core.py::test_...deny_by_default...`
#: for the structural (AST) proof that this literal is not enum-derived.
_OPERATION_REQUIRED_LOGICAL_INPUT_FIELDS: Final[
    Mapping[ResearchKaliOperationKind, frozenset[str]]
] = {
    ResearchKaliOperationKind.DNS_RECORD_LOOKUP: frozenset(
        {_FIELD_HOSTNAME, _FIELD_DNS_RECORD_TYPE}
    ),
    ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP: frozenset(
        {_FIELD_HOSTNAME, _FIELD_RESOLVED_ADDRESS}
    ),
}

#: Public, read-only view of the allowlist's domain -- useful for tests and
#: future composition code to inspect without reaching into a private name.
SUPPORTED_GUEST_AGENT_OPERATION_KINDS: Final[frozenset[ResearchKaliOperationKind]] = (
    frozenset(_OPERATION_REQUIRED_LOGICAL_INPUT_FIELDS)
)

# Fixed, code-owned response details. Never built by interpolating request
# data: a hostile logical-input value, the request's nonce, its
# operation_digest, or any exception text must never reach a peer through
# one of these strings -- exactly the discipline
# `research.GuestAgentRpcTransport`'s own error model already keeps.
_DETAIL_UNSUPPORTED_CAPABILITY: Final[str] = (
    "This operation is not in the Guest-Agent's reviewed capability allowlist."
)
_DETAIL_INVALID_FIELD_SET: Final[str] = (
    "This operation's logical inputs do not match its required field set."
)
_DETAIL_INVALID_HOSTNAME: Final[str] = "The hostname logical input is invalid."
_DETAIL_INVALID_DNS_RECORD_TYPE: Final[str] = (
    "The dns_record_type logical input is invalid."
)
_DETAIL_INVALID_RESOLVED_ADDRESS: Final[str] = (
    "The resolved_address logical input is invalid."
)
_DETAIL_DECLINED: Final[str] = (
    "Guest-agent admitted this request, but capability execution is not "
    "enabled by this transport-layer milestone."
)


def admit_guest_agent_request(request: GuestAgentRequest) -> GuestAgentResponse:
    """Decide only admission, never execution, for one decoded request.

    Returns `GuestAgentResponseStatus.UNSUPPORTED_CAPABILITY` when
    `request.operation_kind` is outside the fixed allowlist above;
    `INVALID_REQUEST` when the operation is recognized but the supplied
    logical inputs do not exactly match its required field set or a
    required field's value fails its narrow, reused syntactic check; and
    `DECLINED` for every other case -- a structurally valid, admitted
    request that this milestone deliberately does not execute.
    `GuestAgentResponseStatus.SUCCESS` and `REPLAY_REJECTED` are
    structurally unreachable return values of this function: see the
    module docstring for why neither would be honest here.

    `response.request_id` always equals `request.request_id` exactly --
    required for the RPC client's own correlation check -- and
    `response.output_lines` is always empty. This function never calls
    `research.GuestAgentReplayProtector.consume_once`, never reads or
    writes `research.ResearchKaliOperationAuthorizationStore`, and never
    references `cognition.KaliToolGateway` or any process adapter.
    """
    if not isinstance(request, GuestAgentRequest):
        raise ResearchError("Guest-agent core admission requires a bounded request.")

    required_fields = _OPERATION_REQUIRED_LOGICAL_INPUT_FIELDS.get(
        request.operation_kind
    )
    if required_fields is None:
        return _response(
            request,
            GuestAgentResponseStatus.UNSUPPORTED_CAPABILITY,
            _DETAIL_UNSUPPORTED_CAPABILITY,
        )

    present_fields = frozenset(name for name, _ in request.logical_inputs)
    if present_fields != required_fields:
        return _response(
            request,
            GuestAgentResponseStatus.INVALID_REQUEST,
            _DETAIL_INVALID_FIELD_SET,
        )

    values = dict(request.logical_inputs)

    if not _is_valid_hostname(values[_FIELD_HOSTNAME]):
        return _response(
            request,
            GuestAgentResponseStatus.INVALID_REQUEST,
            _DETAIL_INVALID_HOSTNAME,
        )

    if request.operation_kind is ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
        if not _is_valid_dns_record_type(values[_FIELD_DNS_RECORD_TYPE]):
            return _response(
                request,
                GuestAgentResponseStatus.INVALID_REQUEST,
                _DETAIL_INVALID_DNS_RECORD_TYPE,
            )
    elif request.operation_kind is ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP:
        if not _is_valid_resolved_address(values[_FIELD_RESOLVED_ADDRESS]):
            return _response(
                request,
                GuestAgentResponseStatus.INVALID_REQUEST,
                _DETAIL_INVALID_RESOLVED_ADDRESS,
            )

    return _response(request, GuestAgentResponseStatus.DECLINED, _DETAIL_DECLINED)


def _is_valid_hostname(value: str) -> bool:
    """Prove only non-emptiness and the existing reviewed length bound.

    Does not prove DNS-name syntax; does not normalize case or a trailing
    dot (see the module docstring for why that normalization is not
    reused here). A caller must not read more into `True` than that.
    """
    stripped = value.strip()
    if not stripped:
        return False
    return len(stripped) <= MAX_KALI_OPERATION_HOSTNAME_CHARACTERS


def _is_valid_dns_record_type(value: str) -> bool:
    """Prove membership in the closed `ResearchDnsRecordType` enum only."""
    try:
        ResearchDnsRecordType(value)
    except ValueError:
        return False
    return True


def _is_valid_resolved_address(value: str) -> bool:
    """Prove syntactic IP-literal validity only, via the stdlib parser.

    Never resolves, never contacts a network, and never proves the
    address matches any host-side preview or authorization.
    """
    if not value.strip():
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _response(
    request: GuestAgentRequest,
    status: GuestAgentResponseStatus,
    detail: str,
) -> GuestAgentResponse:
    return GuestAgentResponse(
        protocol_version=request.protocol_version,
        request_id=request.request_id,
        status=status,
        detail=detail,
        output_lines=(),
    )
