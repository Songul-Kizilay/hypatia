"""Post-replay prepared-invocation foundation: admit -> replay-consume -> prepare.

This module composes three already-existing, unmodified building blocks --
`research.GuestAgentCore.admit_guest_agent_request`, `research
.GuestAgentReplayProtector.GuestAgentReplayProtector.consume_once`, and
`research.ResearchKaliOperationPreview.kali_operation_command_plan` -- into
one pure application-level function,
`prepare_guest_agent_invocation`, that a transport (today:
`research.GuestAgentSignedDispatchRpcTransport`) can call after cryptographic
verification has already succeeded.

PREPARED INVOCATION != PROCESS CREATED. PREPARED INVOCATION != RUNTIME
READY. PREPARED INVOCATION != EXECUTION SUCCESS. PREPARED INVOCATION !=
TRUSTED OUTPUT. PREPARED INVOCATION != EVIDENCE. A `GuestAgentPreparedInvocation`
means only "every pre-execution security gate this milestone defines has
passed for this exact reviewed capability" -- never that a process ran, that
a guest runtime is ready, or that any output exists. This module spawns no
process, opens no socket, performs no DNS/HTTP, and calls neither
`subprocess.run`/`subprocess.Popen`/`os.system` nor
`research.ResearchKaliOperationProcessAdapter.run`/`cognition.KaliToolGateway
.run`.

Ordering is load-bearing and structurally enforced by this function's own
source order, never merely documented: admission (logical capability
admission) runs first; only a `DECLINED` admission outcome reaches replay
consumption (`UNSUPPORTED_CAPABILITY`/`INVALID_REQUEST` return immediately,
spending no replay identity); replay consumption runs next: a prepared
invocation is only ever constructed AFTER `GuestAgentReplayOutcome.ACCEPTED`
-- `ALREADY_CONSUMED` and any replay-store failure both return before a
prepared invocation is ever attempted. No future effect may precede replay
acceptance.

V1 REQUEST != EXECUTION-BOUND REQUEST: a `GuestAgentRequest` whose
`execution_limits` is `None` (always true for `GuestAgentProtocolVersion.V1`,
by `GuestAgentRequest.__post_init__`'s own structural guarantee) can never
reach prepared-invocation construction here, regardless of admission or
replay outcome -- it still returns the plain `DECLINED`/`REPLAY_REJECTED`
response v0.3.465 already produced, byte-for-byte the same decision logic,
just reached through this shared function instead of being duplicated
inline in the RPC transport.

Execution-limit admission is not a separate runtime check this module
performs: by the time a `GuestAgentRequest` instance exists (whether built
directly, or decoded off the wire by `research
.GuestAgentProtocolSerialization`), its `execution_limits` -- if present --
is already a fully validated `research.GuestAgentProtocol
.GuestAgentExecutionLimits` instance; there is no further admission decision
left to make about its shape. This keeps the concern narrow: logical-input
admission (`admit_guest_agent_request`) and execution-limit validity
(enforced entirely by construction/decoding) remain two separate mechanisms,
neither duplicating the other.

The prepared invocation's command plan is reconstructed from code, never
carried from the wire: `_build_prepared_invocation` calls the existing,
unmodified `kali_operation_command_plan(...)` with
`transport=ResearchKaliCommandTransport.GUEST_AGENT` and only the already-
admitted `operation_kind`/logical inputs -- there is no `argv`, `executable`,
`shell`, or command text anywhere on the wire or in this module. WIRE DATA
!= ARBITRARY COMMAND.

The prepared invocation's `timeout_seconds` is
`min(request.execution_limits.max_seconds, MAX_KALI_OPERATION_TIMEOUT_SECONDS)`
-- the identical semantics `cognition.KaliToolGateway.run` already applies
when it computes `timeout_seconds=min(preview.max_seconds,
MAX_KALI_OPERATION_TIMEOUT_SECONDS)` for a real dispatch. This never widens
the host-approved ceiling; it can only ever narrow it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from research.GuestAgentCore import (
    FIELD_DNS_RECORD_TYPE,
    FIELD_HOSTNAME,
    FIELD_RESOLVED_ADDRESS,
    admit_guest_agent_request,
)
from research.GuestAgentProtocol import (
    GuestAgentProtocolVersion,
    GuestAgentRequest,
    GuestAgentResponse,
    GuestAgentResponseStatus,
)
from research.GuestAgentReplayProtector import (
    GuestAgentReplayOutcome,
    GuestAgentReplayProtector,
)
from research.ResearchKaliOperationExecution import MAX_KALI_OPERATION_TIMEOUT_SECONDS
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliCommandTransport,
    ResearchKaliOperationCommandPlan,
    ResearchKaliOperationKind,
    kali_operation_command_plan,
)

#: Module-private capability token. Never exported, never re-derivable from
#: public data: the only code path that can supply this exact object to
#: `GuestAgentPreparedInvocation.__init__` is `prepare_guest_agent_invocation`
#: below, after admission, execution-limit validity, and replay acceptance
#: have all already succeeded. Mirrors `research.GuestAgentDispatchVerification
#: ._VERIFIED_DISPATCH_CAPABILITY`'s own pattern exactly.
_PREPARED_INVOCATION_CAPABILITY = object()

_DETAIL_REPLAY_REJECTED = "This request's replay identity has already been consumed."


@dataclass(frozen=True, slots=True, kw_only=True)
class GuestAgentPreparedInvocation:
    """All pre-execution gates passed; ready for a future execution gate.

    PREPARED INVOCATION != PROCESS CREATED, != RUNTIME READY, != EXECUTION
    SUCCESS, != TRUSTED OUTPUT, != EVIDENCE -- see the module docstring. Not
    publicly constructible: `__post_init__` rejects any `_capability_token`
    other than this module's own private sentinel, which only
    `prepare_guest_agent_invocation` ever supplies. Contains only reviewed
    operation facts -- a code-owned, reconstructed command plan and a
    bounded timeout -- never a human name, scope document, or arbitrary
    wire-carried command.
    """

    operation_kind: ResearchKaliOperationKind
    command_plan: ResearchKaliOperationCommandPlan
    timeout_seconds: float
    _capability_token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._capability_token is not _PREPARED_INVOCATION_CAPABILITY:
            raise ResearchError(
                "Guest-agent prepared invocation may only be constructed by "
                "research.GuestAgentInvocationPreparation"
                ".prepare_guest_agent_invocation."
            )
        if not isinstance(self.operation_kind, ResearchKaliOperationKind):
            raise ResearchError(
                "Guest-agent prepared invocation operation kind is invalid."
            )
        if not isinstance(self.command_plan, ResearchKaliOperationCommandPlan):
            raise ResearchError(
                "Guest-agent prepared invocation command plan is invalid."
            )
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, int | float)
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ResearchError("Guest-agent prepared invocation timeout is invalid.")
        if self.timeout_seconds > MAX_KALI_OPERATION_TIMEOUT_SECONDS:
            raise ResearchError(
                "Guest-agent prepared invocation timeout exceeds the global "
                "hard cap."
            )


def prepare_guest_agent_invocation(
    request: GuestAgentRequest,
    replay_protector: GuestAgentReplayProtector,
) -> tuple[GuestAgentResponse, GuestAgentPreparedInvocation | None]:
    """Admit, replay-consume, and -- only for an execution-bound V2 request
    whose replay identity was just freshly accepted -- prepare one inert
    invocation. Returns the wire response to send, and the prepared
    invocation if (and only if) one was constructed.

    Never execution authority: see the module docstring. Raises
    `core.Exceptions.ResearchError` only if `replay_protector.consume_once`
    itself fails (a durable-store failure) -- the caller decides how to
    report that; this function never swallows it.
    """
    if not isinstance(request, GuestAgentRequest):
        raise ResearchError(
            "Guest-agent invocation preparation requires a bounded request."
        )
    if not isinstance(replay_protector, GuestAgentReplayProtector):
        raise ResearchError(
            "Guest-agent invocation preparation requires a bounded replay " "protector."
        )

    admitted = admit_guest_agent_request(request)
    if admitted.status is not GuestAgentResponseStatus.DECLINED:
        return admitted, None

    outcome = replay_protector.consume_once(request)
    if outcome is GuestAgentReplayOutcome.ALREADY_CONSUMED:
        rejected = GuestAgentResponse(
            protocol_version=admitted.protocol_version,
            request_id=admitted.request_id,
            status=GuestAgentResponseStatus.REPLAY_REJECTED,
            detail=_DETAIL_REPLAY_REJECTED,
            output_lines=(),
        )
        return rejected, None

    if request.protocol_version is not GuestAgentProtocolVersion.V2:
        return admitted, None

    prepared = _build_prepared_invocation(request)
    return admitted, prepared


def _build_prepared_invocation(
    request: GuestAgentRequest,
) -> GuestAgentPreparedInvocation:
    """Reconstruct the reviewed command plan from code, never from the wire.

    Called only once every pre-execution gate (admission, execution-limit
    presence guaranteed by `request.execution_limits` being non-`None` for
    a V2 request, and replay acceptance) has already succeeded.
    """
    assert request.execution_limits is not None  # guaranteed for V2 by construction
    values = dict(request.logical_inputs)
    if request.operation_kind is ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
        command_plan = kali_operation_command_plan(
            operation_kind=request.operation_kind,
            hostname=values[FIELD_HOSTNAME],
            dns_record_type=ResearchDnsRecordType(values[FIELD_DNS_RECORD_TYPE]),
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
        )
    elif request.operation_kind is ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP:
        command_plan = kali_operation_command_plan(
            operation_kind=request.operation_kind,
            hostname=values[FIELD_HOSTNAME],
            resolved_address=values[FIELD_RESOLVED_ADDRESS],
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
        )
    else:  # pragma: no cover - unreachable: admission already rejected this
        raise ResearchError(
            "Guest-agent prepared invocation operation kind is not supported."
        )

    timeout_seconds = min(
        request.execution_limits.max_seconds, MAX_KALI_OPERATION_TIMEOUT_SECONDS
    )
    return GuestAgentPreparedInvocation(
        operation_kind=request.operation_kind,
        command_plan=command_plan,
        timeout_seconds=timeout_seconds,
        _capability_token=_PREPARED_INVOCATION_CAPABILITY,
    )
