"""Exact-request execution-admission boundary; still no capability execution.

This module composes two already-unforgeable values --
`research.GuestAgentDispatchVerification.GuestAgentVerifiedDispatch` and
`research.GuestAgentRuntimeReadiness.GuestAgentRuntimeReadyInvocation` --
into one final in-process value, `GuestAgentExecutionAdmission`, that a
future real executor would be required to consume. It introduces zero new
process, socket, or network capability.

VERIFIED DISPATCH != EXECUTION AUTHORITY BY ITSELF. RUNTIME READY !=
EXECUTION AUTHORITY BY ITSELF. Neither already-unforgeable value is
individually sufficient: a verified dispatch proves only that the trusted
HOST signed this exact request; a runtime-ready invocation proves only that
*some* prepared invocation's exact local executable passed the bounded
local readiness probe. `GuestAgentExecutionAdmission` exists to prove the
one additional fact neither value alone establishes: that the runtime-ready
invocation corresponds -- exactly, not merely by matching
`operation_kind` -- to the one verified dispatch's own request. Without
this binding, a runtime-ready invocation legitimately produced for one
admitted request could otherwise be paired with an unrelated verified
dispatch for a different request (the confused-deputy shape this module
exists to close).

EXACT BINDING, NOT FUZZY MATCHING: `GuestAgentExecutionAdmission.__post_init__`
reconstructs the expected prepared invocation directly from
`verified_dispatch.request` by calling `research.GuestAgentInvocationPreparation
._build_prepared_invocation` -- the one existing function that already
performs this reconstruction for the real preparation path, reused here
rather than re-derived a second time (mirrors
`research.GuestAgentSignedDispatchRpcTransport`'s own reuse of
`research.GuestAgentRpcTransport._authenticate_tls_peer` -- a private
helper reused directly across module boundaries is an established pattern
in this codebase, not a new one). The reconstructed
`GuestAgentPreparedInvocation` is compared by dataclass equality (which
compares `operation_kind`, `command_plan`, and `timeout_seconds`, but never
the construction-only capability token) against
`runtime_ready_invocation.prepared_invocation` -- an exact match or
nothing. `ResearchKaliOperationCommandPlan` equality in turn compares
`transport`, `executable_path`, `argv`, `shell`, and `stdin` together, so
this one equality check transitively proves exact executable, exact argv,
exact transport, and `shell is False` -- there is no separate, narrower
"operation kind only" comparison anywhere in this module. A mismatch of
any kind -- different hostname, different DNS record type, different
resolved address, different signed `max_seconds` (once capped), different
operation kind, a tampered executable/argv/transport -- fails exactly the
same way: `__post_init__` raises `core.Exceptions.ResearchError`, and
`admit_guest_agent_execution` converts that into "no admission" (`None`),
never a partial or best-effort admission.

EXECUTION ADMISSION != EXECUTION SUCCESS. EXECUTION ADMISSION != SCOPE
EXPANSION. `GuestAgentExecutionAdmission` means only: "all existing
pre-execution gates for this exact signed request have been proven, and
the exact reviewed local executable is ready." It never means execution
occurred, a target was reached, output exists, or any new capability is
permitted beyond what the already-reviewed chain already decided.

Unforgeable by the same module-private capability-token pattern
`GuestAgentPreparedInvocation`/`GuestAgentRuntimeReadyInvocation` already
use: a caller cannot construct `GuestAgentExecutionAdmission` by copying
fields into a dataclass, and even supplying the real token does not bypass
the exact-binding check inside `__post_init__` itself (defense in depth,
mirroring `GuestAgentRuntimeReadyInvocation`'s own independent re-validation
of its readiness receipt).

NOT-EXECUTED RECEIPT != PROCESS RESULT. `GuestAgentExecutionBoundaryReceipt`
is this milestone's only executor-facing artifact, and it represents
nothing but "admitted, not executed": `process_created`,
`target_operation_executed`, `target_network_used`, `timed_out`,
`evidence_recorded`, `claim_created`, and `memory_written` are all
structurally forced `False`; `output_lines` is structurally forced empty;
`exit_code` is structurally forced `None`. There is no code path in this
module that can produce a receipt claiming a process ran, output exists,
or evidence was recorded -- doing so would require widening this type's
own `__post_init__`, which this milestone does not do. PROCESS NOT CREATED
!= OPERATION PERFORMED.

This module introduces no process, socket, DNS/HTTP client, SSH/VMware/WSL
call, generic execution callback, or process adapter of any kind. It does
not call `prepared_invocation.command_plan.argv`,
`subprocess.run`/`subprocess.Popen`/`os.system`,
`research.ResearchKaliOperationProcessAdapter.run`,
`cognition.KaliToolGateway.run`, or any Wsl/Vmware process adapter. The
v0.3.467 local readiness subprocess capability is unchanged and unexpanded
by anything here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from core.Exceptions import ResearchError
from research.GuestAgentDispatchVerification import GuestAgentVerifiedDispatch
from research.GuestAgentInvocationPreparation import _build_prepared_invocation
from research.GuestAgentRuntimeReadiness import GuestAgentRuntimeReadyInvocation

#: Module-private capability token. Never exported, never re-derivable from
#: public data: the only code path that can supply this exact object to
#: `GuestAgentExecutionAdmission.__init__` is `admit_guest_agent_execution`
#: below, after the exact-binding check inside `__post_init__` has already
#: succeeded. Mirrors `research.GuestAgentInvocationPreparation
#: ._PREPARED_INVOCATION_CAPABILITY` and `research.GuestAgentRuntimeReadiness
#: ._RUNTIME_READY_CAPABILITY`'s own pattern exactly.
_EXECUTION_ADMISSION_CAPABILITY = object()

_REASON_BINDING_MISMATCH = (
    "Guest-agent execution admission requires the runtime-ready invocation "
    "to correspond exactly to the verified dispatch's own request."
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GuestAgentExecutionAdmission:
    """All pre-execution gates proven for one exact signed request.

    VERIFIED DISPATCH != EXECUTION AUTHORITY BY ITSELF. RUNTIME READY !=
    EXECUTION AUTHORITY BY ITSELF. EXECUTION ADMISSION != EXECUTION
    SUCCESS. EXECUTION ADMISSION != SCOPE EXPANSION. EXECUTION ADMISSION
    IS BOUND TO ONE EXACT VERIFIED REQUEST -- see the module docstring.
    Not publicly constructible: `__post_init__` rejects any
    `_capability_token` other than this module's own private sentinel,
    and independently re-proves the exact binding between the two inputs
    even when the real token is supplied, so a caller cannot bypass the
    confused-deputy check by constructing this value some other way.
    """

    verified_dispatch: GuestAgentVerifiedDispatch
    runtime_ready_invocation: GuestAgentRuntimeReadyInvocation
    _capability_token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._capability_token is not _EXECUTION_ADMISSION_CAPABILITY:
            raise ResearchError(
                "Guest-agent execution admission may only be constructed "
                "by research.GuestAgentExecutionAdmission"
                ".admit_guest_agent_execution."
            )
        if not isinstance(self.verified_dispatch, GuestAgentVerifiedDispatch):
            raise ResearchError(
                "Guest-agent execution admission requires a verified dispatch."
            )
        if not isinstance(
            self.runtime_ready_invocation, GuestAgentRuntimeReadyInvocation
        ):
            raise ResearchError(
                "Guest-agent execution admission requires a runtime-ready "
                "invocation."
            )

        request = self.verified_dispatch.request
        if request.execution_limits is None:
            # V1 requests never carry execution limits and therefore never
            # produce a prepared invocation in the first place (see
            # research.GuestAgentInvocationPreparation's own module
            # docstring) -- this is a second, independent layer of the
            # same V1-never-reaches-execution-admission guarantee, not the
            # only one.
            raise ResearchError(_REASON_BINDING_MISMATCH)

        try:
            expected = _build_prepared_invocation(request)
        except (ResearchError, KeyError, ValueError) as error:
            # A verified dispatch whose own request cannot even be
            # reconstructed into a prepared invocation (an unsupported
            # operation kind, or logical inputs missing/malformed in a way
            # admission would normally have already rejected) can never
            # bind to anything -- fail closed rather than let a KeyError/
            # ValueError from the reused reconstruction helper escape as
            # an unexpected exception type.
            raise ResearchError(_REASON_BINDING_MISMATCH) from error

        if expected != self.runtime_ready_invocation.prepared_invocation:
            raise ResearchError(_REASON_BINDING_MISMATCH)


class GuestAgentExecutionBoundaryStatus(StrEnum):
    """The one outcome this milestone's execution boundary can report.

    Deliberately a single member: this milestone introduces no executor,
    so there is exactly one honest status an admitted-but-not-executed
    receipt can carry. A future milestone that adds a real executor adds
    its own new member(s) then, deliberately and reviewed -- this status
    is never silently widened to imply execution exists today.
    """

    NOT_EXECUTED = "not_executed"


@dataclass(frozen=True, slots=True, kw_only=True)
class GuestAgentExecutionBoundaryReceipt:
    """A bounded, honest "admitted, not executed" receipt; never a process result.

    NOT-EXECUTED RECEIPT != PROCESS RESULT. PROCESS NOT CREATED !=
    OPERATION PERFORMED -- see the module docstring. Every field below
    that could claim real work happened is structurally forced to its
    inert value in `__post_init__`; this type cannot be constructed to
    claim a process ran, output exists, or evidence was recorded.
    """

    execution_admission: GuestAgentExecutionAdmission
    status: GuestAgentExecutionBoundaryStatus = (
        GuestAgentExecutionBoundaryStatus.NOT_EXECUTED
    )
    process_created: bool = False
    target_operation_executed: bool = False
    target_network_used: bool = False
    output_lines: tuple[str, ...] = ()
    exit_code: int | None = None
    timed_out: bool = False
    evidence_recorded: bool = False
    claim_created: bool = False
    memory_written: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.execution_admission, GuestAgentExecutionAdmission):
            raise ResearchError(
                "Guest-agent execution boundary receipt requires an "
                "execution admission."
            )
        if self.status is not GuestAgentExecutionBoundaryStatus.NOT_EXECUTED:
            raise ResearchError(
                "Guest-agent execution boundary receipt status is invalid."
            )
        if self.process_created is not False:
            raise ResearchError(
                "Guest-agent execution boundary receipt must not claim a "
                "process was created."
            )
        if self.target_operation_executed is not False:
            raise ResearchError(
                "Guest-agent execution boundary receipt must not claim the "
                "target operation executed."
            )
        if self.target_network_used is not False:
            raise ResearchError(
                "Guest-agent execution boundary receipt must not claim "
                "target network use."
            )
        if not isinstance(self.output_lines, tuple) or self.output_lines != ():
            raise ResearchError(
                "Guest-agent execution boundary receipt must not carry " "output lines."
            )
        if self.exit_code is not None:
            raise ResearchError(
                "Guest-agent execution boundary receipt must not carry an " "exit code."
            )
        if self.timed_out is not False:
            raise ResearchError(
                "Guest-agent execution boundary receipt must not claim a "
                "timeout occurred."
            )
        if self.evidence_recorded is not False:
            raise ResearchError(
                "Guest-agent execution boundary receipt must not claim "
                "evidence was recorded."
            )
        if self.claim_created is not False:
            raise ResearchError(
                "Guest-agent execution boundary receipt must not claim a "
                "claim was created."
            )
        if self.memory_written is not False:
            raise ResearchError(
                "Guest-agent execution boundary receipt must not claim "
                "memory was written."
            )


def admit_guest_agent_execution(
    verified_dispatch: GuestAgentVerifiedDispatch,
    runtime_ready_invocation: GuestAgentRuntimeReadyInvocation,
) -> GuestAgentExecutionBoundaryReceipt | None:
    """Admit one exact, bound request for a future executor; never run one.

    Returns a `GuestAgentExecutionBoundaryReceipt` only when
    `runtime_ready_invocation` corresponds exactly to `verified_dispatch
    .request` (same operation kind, same reconstructed GUEST_AGENT command
    plan, same capped timeout) -- `None` otherwise, for any reason: wrong
    argument types, a V1 (non-execution-bound) verified dispatch, or any
    exact-binding mismatch, including a confused-deputy pairing of a
    legitimately-ready invocation for a *different* request. Never raises:
    every `ResearchError` `GuestAgentExecutionAdmission.__post_init__` can
    produce is caught here and converted into "no admission."
    """
    try:
        admission = GuestAgentExecutionAdmission(
            verified_dispatch=verified_dispatch,
            runtime_ready_invocation=runtime_ready_invocation,
            _capability_token=_EXECUTION_ADMISSION_CAPABILITY,
        )
    except ResearchError:
        return None
    return GuestAgentExecutionBoundaryReceipt(execution_admission=admission)
