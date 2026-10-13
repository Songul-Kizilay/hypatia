"""Host authorization handoff foundation for future Guest-Agent dispatch.

This is the boundary between "the host's existing scope/preview/
authorization chain consumed an exact human approval" and "the host may
now construct exactly one `GuestAgentRequest` to carry over the real RPC
transport" (`research.GuestAgentRpcTransport`). It implements ONLY that
boundary -- nothing upstream of it (scope, preview, human approval) and
nothing downstream of it (sending the request, guest-side replay/authority
enforcement, execution) changes or exists because of this module.

AUTHORIZATION RECORD PRESENT != AUTHORIZATION CONSUMED. AUTHORIZATION VALID
!= AUTHORIZATION CONSUMED. AUTHORIZATION CONSUMED != EXECUTION SUCCESS.
HOST DISPATCH GRANT != GUEST-SIDE AUTHORIZATION PROOF. HOST DISPATCH GRANT
!= AUTHORITY TO EXECUTE BY ITSELF. A `GuestAgentHostDispatchGrant` means
only "the trusted host authority chain -- the same exact-binding checks
`cognition.KaliToolGateway` already applies, reused here via
`research.ResearchKaliOperationAuthorizationConsumption` rather than
duplicated -- successfully reached the post-consumption handoff point for
one exact, Guest-Agent-bound preview." It never means "the guest may
execute."

**This milestone does not solve guest-side independent cryptographic proof
of host authorization, and does not claim to.** A `GuestAgentRequest`
built from a valid grant is, once serialized, still only the same typed
protocol object `research.GuestAgentProtocol` already describes --
`protocol_version`/`request_id`/`nonce`/`operation_kind`/
`operation_digest`/`logical_inputs`, nothing more. There is no field here,
and none is added, that lets a receiving guest independently verify from
those bytes alone that a host authorization was ever consumed; the guest
must still treat an incoming request exactly as
`research.GuestAgentCore.admit_guest_agent_request` already does today --
admission only, never execution, never `SUCCESS`. Solving that gap (a
cryptographic authorization proof that survives serialization, or an
equivalent mechanism) is explicitly out of scope and left for a future,
separately-authorized milestone.

Transport binding: `research.ResearchKaliOperationPreview
.ResearchKaliCommandTransport.GUEST_AGENT` names this route so a
Guest-Agent-bound preview's `operation_digest` differs from the otherwise-
identical `WSL_KALI`/`VMWARE_KALI` digest for the same operation (transport
is part of the digested document -- see that enum's own docstring).
`consume_authorization_for_guest_agent_dispatch` refuses any preview whose
`transport` is not exactly `GUEST_AGENT`, so a WSL- or VMware-authorized
record can never satisfy a Guest-Agent handoff even though the underlying
exact-binding check (digest/program/scope/policy equality) is the same
shared primitive `cognition.KaliToolGateway` uses.

Ordering is load-bearing, and matches
`ResearchKaliOperationAuthorizationConsumption`'s own contract exactly:
validate the exact authorization -> persist its removal
(`authorization_store.save(...)`) -> ONLY THEN construct the
`GuestAgentHostDispatchGrant`. If `save` raises, or if validation fails
for any reason, no grant is ever constructed -- there is no code path
here that builds a grant first and attempts to persist consumption
afterward.

Replay (`research.GuestAgentReplayProtector.consume_once`) is a distinct
security property from host authorization consumption and is never
touched here: HOST AUTHORIZATION CONSUMED != GUEST REPLAY CONSUMED. A
future real dispatch path will need both, in the correct order, but this
milestone performs zero replay consumption.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from threading import RLock

from core.Exceptions import ResearchError
from research.GuestAgentCore import (
    FIELD_DNS_RECORD_TYPE,
    FIELD_HOSTNAME,
    FIELD_RESOLVED_ADDRESS,
)
from research.GuestAgentProtocol import (
    GuestAgentProtocolVersion,
    GuestAgentRequest,
)
from research.ResearchKaliOperationAuthorizationConsumption import (
    authorizations_excluding,
    find_exact_kali_operation_authorization,
)
from research.ResearchKaliOperationAuthorizationStore import (
    ResearchKaliOperationAuthorizationStore,
)
from research.ResearchKaliOperationPreview import (
    ResearchKaliCommandTransport,
    ResearchKaliOperationKind,
    ResearchKaliOperationPreview,
    is_kali_operation_digest,
)

#: Module-private capability token. Never exported, never re-derivable from
#: public data: the only code path that can supply this exact object to
#: `GuestAgentHostDispatchGrant.__init__` is
#: `consume_authorization_for_guest_agent_dispatch`, below, after exact
#: authorization validation and durable consumption have both already
#: succeeded. Mirrors `research.GuestAgentPeerAuthenticator`'s own
#: `_AUTHENTICATION_CAPABILITY` pattern exactly.
_DISPATCH_GRANT_CAPABILITY = object()


class GuestAgentHostAuthorizationHandoffStage(StrEnum):
    """Name which bounded step of the handoff failed; never a trust claim."""

    REQUEST = "request"
    TRANSPORT_BINDING = "transport_binding"
    LOGICAL_INPUT_PROJECTION = "logical_input_projection"
    AUTHORIZATION = "authorization"
    AUTHORIZATION_CONSUMPTION = "authorization_consumption"


@dataclass(frozen=True, slots=True)
class GuestAgentHostAuthorizationHandoffFailure:
    """Stage-owned facts; never a durable execution receipt.

    Mirrors `research.KaliToolGatewayFailure` exactly: a fixed, bounded
    `reason` naming which stage failed, never raw store contents, paths,
    hostile caller values, or arbitrary exception text.
    """

    stage: GuestAgentHostAuthorizationHandoffStage
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.stage, GuestAgentHostAuthorizationHandoffStage):
            raise ResearchError(
                "Guest-agent host authorization handoff failure stage is invalid."
            )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError(
                "Guest-agent host authorization handoff failure reason is invalid."
            )

    @property
    def authorization_consumed(self) -> str:
        """Name only what this call can honestly claim about consumption."""
        if (
            self.stage
            is GuestAgentHostAuthorizationHandoffStage.AUTHORIZATION_CONSUMPTION
        ):
            return "unknown; persistence did not confirm completion"
        return "not attempted by this call"


class GuestAgentHostAuthorizationHandoffError(ResearchError):
    """Carry descriptive failure facts back to the caller; never a grant."""

    def __init__(self, failure: GuestAgentHostAuthorizationHandoffFailure) -> None:
        super().__init__(failure.reason)
        self.failure = failure


@dataclass(frozen=True, slots=True, kw_only=True)
class GuestAgentHostDispatchGrant:
    """The host authority chain reached the post-consumption handoff point.

    HOST DISPATCH GRANT != GUEST-SIDE AUTHORIZATION PROOF. HOST DISPATCH
    GRANT != AUTHORITY TO EXECUTE BY ITSELF -- see the module docstring.
    Not publicly constructible: `__post_init__` rejects any
    `_capability_token` other than this module's own private sentinel,
    which only `consume_authorization_for_guest_agent_dispatch` ever
    supplies, and only after it has already validated and durably
    consumed the exact matching authorization. A caller cannot forge one
    merely by copying strings into this dataclass.

    `operation_kind`, `operation_digest`, and `logical_inputs` are the
    exact facts of the preview whose authorization was just consumed --
    never independently caller-suppliable. One-shot:
    `materialize_request` yields at most one real `GuestAgentRequest`;
    a second call fails closed, under the same lock that guards the
    first, so two concurrent callers can never both succeed.
    """

    operation_kind: ResearchKaliOperationKind
    operation_digest: str
    logical_inputs: tuple[tuple[str, str], ...]
    _capability_token: object = field(repr=False, compare=False)
    _already_materialized: bool = field(default=False, repr=False, compare=False)
    _lock: RLock = field(default_factory=RLock, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._capability_token is not _DISPATCH_GRANT_CAPABILITY:
            raise ResearchError(
                "Guest-agent host dispatch grant may only be constructed by "
                "research.GuestAgentHostAuthorizationHandoff"
                ".consume_authorization_for_guest_agent_dispatch."
            )
        if not isinstance(self.operation_kind, ResearchKaliOperationKind):
            raise ResearchError(
                "Guest-agent host dispatch grant operation kind is invalid."
            )
        if not is_kali_operation_digest(self.operation_digest):
            raise ResearchError(
                "Guest-agent host dispatch grant operation digest is invalid."
            )
        if not isinstance(self.logical_inputs, tuple) or not all(
            isinstance(entry, tuple)
            and len(entry) == 2
            and isinstance(entry[0], str)
            and isinstance(entry[1], str)
            for entry in self.logical_inputs
        ):
            raise ResearchError(
                "Guest-agent host dispatch grant logical inputs are invalid."
            )

    @property
    def already_materialized(self) -> bool:
        """Return whether this one-shot grant has already yielded a request."""
        return self._already_materialized

    def materialize_request(self, *, request_id: str, nonce: str) -> GuestAgentRequest:
        """Yield the one `GuestAgentRequest` this grant may ever produce.

        `request_id`/`nonce` are supplied by the caller at this final
        boundary (REQUEST ID != AUTHORIZATION, NONCE != AUTHORIZATION --
        they are transport/replay identity, not authorization facts) and
        validated only by `GuestAgentRequest`'s own existing bounds. Every
        other field is copied from this grant's own already-validated
        facts -- never independently suppliable here. Raises
        `core.Exceptions.ResearchError` if this grant already materialized
        a request, or if `GuestAgentRequest`'s own validation rejects
        `request_id`/`nonce` (in which case this grant remains unconsumed
        and may still be retried with corrected values). The entire
        check-construct-mark sequence holds one lock, so two concurrent
        callers can never both observe "not yet materialized."
        """
        with self._lock:
            if self._already_materialized:
                raise ResearchError(
                    "Guest-agent host dispatch grant has already been used."
                )
            request = GuestAgentRequest(
                protocol_version=GuestAgentProtocolVersion.V1,
                request_id=request_id,
                nonce=nonce,
                operation_kind=self.operation_kind,
                operation_digest=self.operation_digest,
                logical_inputs=self.logical_inputs,
            )
            object.__setattr__(self, "_already_materialized", True)
        return request


def consume_authorization_for_guest_agent_dispatch(
    authorization_store: ResearchKaliOperationAuthorizationStore,
    authorization_id: str,
    preview: ResearchKaliOperationPreview,
    *,
    now: datetime,
) -> GuestAgentHostDispatchGrant:
    """Validate and durably consume one exact authorization; return a grant.

    Requires `preview.transport is ResearchKaliCommandTransport.GUEST_AGENT`
    -- a WSL- or VMware-bound preview (and therefore its authorization)
    can never satisfy this function, even when every other binding fact
    matches exactly. Logical inputs for the eventual `GuestAgentRequest`
    are projected from `preview`'s own already-normalized fields only
    (see `_project_logical_inputs`), never accepted from a caller.

    Ordering is load-bearing: this function loads, matches, and durably
    saves the reduced authorization set entirely before constructing the
    returned grant. A store `load`/`save` failure, or any exact-binding
    mismatch, raises `GuestAgentHostAuthorizationHandoffError` and leaves
    no grant in existence -- there is no path that builds a grant and
    attempts persistence afterward. This function never calls
    `research.GuestAgentReplayProtector.consume_once`, never references
    `cognition.KaliToolGateway`, never performs a runtime-readiness check
    (none is needed: nothing here dispatches), and never spawns a
    process, opens a socket, or performs DNS/HTTP.
    """
    stage = GuestAgentHostAuthorizationHandoffStage.REQUEST
    try:
        if not isinstance(preview, ResearchKaliOperationPreview):
            raise ResearchError(
                "Guest-agent dispatch handoff requires a validated preview."
            )
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ResearchError(
                "Guest-agent dispatch handoff authorization ID cannot be empty."
            )

        stage = GuestAgentHostAuthorizationHandoffStage.TRANSPORT_BINDING
        if preview.transport is not ResearchKaliCommandTransport.GUEST_AGENT:
            raise ResearchError(
                "Guest-agent dispatch handoff requires a Guest-Agent-bound " "preview."
            )

        stage = GuestAgentHostAuthorizationHandoffStage.LOGICAL_INPUT_PROJECTION
        logical_inputs = _project_logical_inputs(preview)

        stage = GuestAgentHostAuthorizationHandoffStage.AUTHORIZATION
        authorizations = authorization_store.load()
        authorization = find_exact_kali_operation_authorization(
            authorizations, authorization_id, preview, now=now
        )

        remaining = authorizations_excluding(authorizations, authorization)
        stage = GuestAgentHostAuthorizationHandoffStage.AUTHORIZATION_CONSUMPTION
        authorization_store.save(remaining)
    except (ResearchError, OSError) as error:
        if stage is GuestAgentHostAuthorizationHandoffStage.AUTHORIZATION_CONSUMPTION:
            reason = "Authorization consumption could not be confirmed."
        elif isinstance(error, OSError):
            reason = "A required local resource could not be read."
        else:
            reason = str(error)
        raise GuestAgentHostAuthorizationHandoffError(
            GuestAgentHostAuthorizationHandoffFailure(stage=stage, reason=reason)
        ) from error

    return GuestAgentHostDispatchGrant(
        operation_kind=preview.operation_kind,
        operation_digest=preview.operation_digest,
        logical_inputs=logical_inputs,
        _capability_token=_DISPATCH_GRANT_CAPABILITY,
    )


def _project_logical_inputs(
    preview: ResearchKaliOperationPreview,
) -> tuple[tuple[str, str], ...]:
    """Derive `GuestAgentRequest` logical inputs ONLY from the preview.

    Every value is read directly from `preview`'s own already-normalized,
    already-validated fields -- never from an independently caller-
    supplied dictionary, and never re-normalized here. A caller cannot
    smuggle a different hostname/DNS-record-type/resolved-address into
    the eventual request than the one the human actually authorized.
    Field names reuse `research.GuestAgentCore`'s own public constants,
    the same vocabulary `admit_guest_agent_request` validates against, so
    neither module can silently drift from the other's idea of a field's
    name.
    """
    if preview.operation_kind is ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
        assert preview.dns_record_type is not None  # enforced by the preview itself
        return (
            (FIELD_HOSTNAME, preview.hostname),
            (FIELD_DNS_RECORD_TYPE, preview.dns_record_type.value),
        )
    if preview.operation_kind is ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP:
        assert preview.resolved_address is not None  # enforced by the preview itself
        return (
            (FIELD_HOSTNAME, preview.hostname),
            (FIELD_RESOLVED_ADDRESS, preview.resolved_address),
        )
    raise ResearchError("Guest-agent dispatch handoff operation kind is not supported.")
