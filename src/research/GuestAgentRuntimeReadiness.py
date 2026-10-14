"""Readiness gate: prepared invocation -> local probe -> runtime-ready invocation.

This module composes one already-unforgeable
`research.GuestAgentInvocationPreparation.GuestAgentPreparedInvocation` with
one `research.GuestAgentLocalReadiness.GuestAgentLocalReadinessProbe` into a
single pure function, `check_guest_agent_runtime_readiness`, that produces a
`GuestAgentRuntimeReadyInvocation` only when the probe reports `READY`.

RUNTIME READY != EXECUTION AUTHORITY. VERSION MATCH != CAPABILITY PERMITTED.
VERSION MATCH != EXECUTION SUCCESS. RUNTIME-READY INVOCATION != EXECUTION
SUCCESS. RUNTIME-READY INVOCATION != AUTHORITY TO EXPAND SCOPE. READINESS
FAILURE != AUTHORITY DECISION.

`GuestAgentRuntimeReadyInvocation` means only: "the exact local reviewed
executable required by this already-prepared invocation passed the bounded
local readiness probe." It does not mean execution authorized, process
executed, target reachable, target vulnerable, operation succeeded, output
trusted, or evidence recorded. It carries the original prepared invocation
and the readiness receipt that justified it -- never a second, independently
editable copy of the command plan or timeout, and never any new field this
milestone's own command-plan reconstruction did not already produce.

Unforgeable by the same module-private capability-token pattern
`GuestAgentPreparedInvocation` itself uses
(`research.GuestAgentInvocationPreparation._PREPARED_INVOCATION_CAPABILITY`):
a caller cannot construct `GuestAgentRuntimeReadyInvocation` by copying
fields into a dataclass -- the only code path that can supply this module's
own private sentinel is `check_guest_agent_runtime_readiness` below, and
only after the supplied probe's `check()` call already returned a `READY`
receipt.

This function introduces no generic execution callback, "run after ready"
hook, or process adapter of any kind. It stops after readiness: there is no
code path from here to `prepared_invocation.command_plan.argv`,
`research.ResearchKaliOperationProcessAdapter.run`,
`cognition.KaliToolGateway.run`, or any other execution entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from research.GuestAgentInvocationPreparation import GuestAgentPreparedInvocation
from research.GuestAgentLocalReadiness import (
    GuestAgentLocalReadinessProbe,
    GuestAgentLocalReadinessReceipt,
)

#: Module-private capability token. Never exported, never re-derivable from
#: public data: the only code path that can supply this exact object to
#: `GuestAgentRuntimeReadyInvocation.__init__` is
#: `check_guest_agent_runtime_readiness` below, after the local readiness
#: probe has already returned `READY`. Mirrors `research
#: .GuestAgentInvocationPreparation._PREPARED_INVOCATION_CAPABILITY`'s own
#: pattern exactly.
_RUNTIME_READY_CAPABILITY = object()


@dataclass(frozen=True, slots=True, kw_only=True)
class GuestAgentRuntimeReadyInvocation:
    """A prepared invocation whose exact local executable passed readiness.

    RUNTIME-READY INVOCATION != EXECUTION SUCCESS -- see the module
    docstring. Not publicly constructible: `__post_init__` rejects any
    `_capability_token` other than this module's own private sentinel.
    Carries only the original prepared invocation and the readiness receipt
    that justified it -- no raw argv, new command string, scope text,
    authorization-store contents, human name, credential, or private key.
    """

    prepared_invocation: GuestAgentPreparedInvocation
    readiness_receipt: GuestAgentLocalReadinessReceipt
    _capability_token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._capability_token is not _RUNTIME_READY_CAPABILITY:
            raise ResearchError(
                "Guest-agent runtime-ready invocation may only be constructed "
                "by research.GuestAgentRuntimeReadiness"
                ".check_guest_agent_runtime_readiness."
            )
        if not isinstance(self.prepared_invocation, GuestAgentPreparedInvocation):
            raise ResearchError(
                "Guest-agent runtime-ready invocation requires a prepared "
                "invocation."
            )
        if not isinstance(self.readiness_receipt, GuestAgentLocalReadinessReceipt):
            raise ResearchError(
                "Guest-agent runtime-ready invocation requires a readiness " "receipt."
            )
        if not self.readiness_receipt.ready:
            raise ResearchError(
                "Guest-agent runtime-ready invocation requires a READY "
                "readiness receipt."
            )
        if self.readiness_receipt.operation_kind is not (
            self.prepared_invocation.operation_kind
        ):
            raise ResearchError(
                "Guest-agent runtime-ready invocation readiness receipt does "
                "not match the prepared invocation's operation kind."
            )


def check_guest_agent_runtime_readiness(
    prepared_invocation: GuestAgentPreparedInvocation,
    local_runtime_probe: GuestAgentLocalReadinessProbe,
) -> tuple[GuestAgentLocalReadinessReceipt, GuestAgentRuntimeReadyInvocation | None]:
    """Check local readiness for one prepared invocation; never execute it.

    Returns the readiness receipt, and -- only when the receipt is `READY`
    -- a `GuestAgentRuntimeReadyInvocation`. Raises `core.Exceptions
    .ResearchError` if either argument is not the exact bounded type this
    function requires; never calls `prepared_invocation.command_plan.argv`,
    never starts a target operation, and never invokes anything beyond the
    supplied probe's own `check()` method.
    """
    if not isinstance(prepared_invocation, GuestAgentPreparedInvocation):
        raise ResearchError(
            "Guest-agent runtime readiness check requires a prepared invocation."
        )
    if not isinstance(local_runtime_probe, GuestAgentLocalReadinessProbe):
        raise ResearchError(
            "Guest-agent runtime readiness check requires a bounded local "
            "readiness probe."
        )

    receipt = local_runtime_probe.check(prepared_invocation)
    if not isinstance(receipt, GuestAgentLocalReadinessReceipt):
        raise ResearchError(
            "Guest-agent local readiness probe returned an invalid receipt."
        )
    if not receipt.ready:
        return receipt, None

    ready_invocation = GuestAgentRuntimeReadyInvocation(
        prepared_invocation=prepared_invocation,
        readiness_receipt=receipt,
        _capability_token=_RUNTIME_READY_CAPABILITY,
    )
    return receipt, ready_invocation
