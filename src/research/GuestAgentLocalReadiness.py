"""Local Guest-Agent runtime-readiness boundary contract.

This module is a boundary contract only. It does not discover an executable,
launch a process, perform DNS/HTTP, or grant execution authority. It answers
one narrow question: "does the exact local executable a given, already-
prepared Guest-Agent invocation reviewed actually exist on this guest, with
the expected tool identity?" -- nothing about a target host, nothing about
authorization to run anything.

PREPARED INVOCATION != RUNTIME READY. RUNTIME READY != EXECUTION AUTHORITY.
VERSION MATCH != CAPABILITY PERMITTED. VERSION MATCH != EXECUTION SUCCESS.
LOCAL READINESS PROCESS != TARGET OPERATION. READINESS OUTPUT != TRUSTED
EVIDENCE.

`research.ResearchKaliRuntimeEnvironment.ResearchKaliRuntimeReadiness`
already exists for the WSL/VMware transports, but its `process_created`/
`network_used` fields are structurally forced to `False` by its own
`__post_init__` -- a shared contract across probes that do, in fact, start a
real local subprocess (`research.WslKaliRuntimeProbe`,
`research.VmrunVMwareKaliHostReadinessProbe`,
`research.SshVMwareKaliGuestReadinessProbe`). Reusing that exact type here
for a probe that also starts a real subprocess would force the same
dishonest claim. This module instead defines a narrow, Guest-Agent-specific
receipt (`GuestAgentLocalReadinessReceipt`) whose `probe_process_started`
field is allowed to be `True`, while `target_operation_executed` and
`target_network_used` remain structurally forced to `False` -- an honest
split the shared type does not offer. This is a deliberate, narrow addition,
not a broad refactor of the shared WSL/VMware contract: every WSL/VMware
probe, requirement, and test is untouched by this module.

This module reuses, rather than re-derives, exactly two already-reviewed
facts from `research.ResearchKaliRuntimeEnvironment`: the expected `dig`/
`curl` executable paths and version-prefix identities
(`EXPECTED_DIG_EXECUTABLE`, `EXPECTED_DIG_VERSION_PREFIX`,
`EXPECTED_CURL_EXECUTABLE`, `EXPECTED_CURL_VERSION_PREFIX`) -- plain string
literals with no behavior, so importing them creates no risky coupling to a
concrete adapter. It does not reuse `ResearchKaliRuntimeRequirement`,
`ResearchKaliRuntimeReadiness`, or `ResearchKaliRuntimeProbe` themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError
from research.GuestAgentInvocationPreparation import GuestAgentPreparedInvocation
from research.ResearchKaliOperationPreview import ResearchKaliOperationKind

MAX_GUEST_AGENT_READINESS_OUTPUT_CHARACTERS = 500


class GuestAgentLocalReadinessState(StrEnum):
    """Operator-visible local Guest-Agent readiness states.

    Deliberately only two members, mirroring
    `ResearchKaliRuntimeReadinessState`: every specific failure cause
    (missing executable, process start failure, timeout, non-zero exit,
    version mismatch, unsupported operation, wrong transport, mismatched
    executable path) collapses into `UNAVAILABLE`, distinguished only by
    `GuestAgentLocalReadinessReceipt.reason` -- never by a second status
    channel a caller might branch on as if it were authority.
    """

    READY = "ready"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class GuestAgentLocalReadinessReceipt:
    """A side-effect-free local readiness report for one reviewed operation.

    `probe_process_started` honestly reports whether this receipt's probe
    actually invoked a local version-probe subprocess -- it is `True` only
    when every fail-closed cross-check already passed and a real
    `subprocess.run` call was attempted (regardless of whether that attempt
    then succeeded). `target_operation_executed` and `target_network_used`
    are always `False`: this receipt can only ever describe a local version
    probe, never the reviewed operation's own target DNS/HTTPS argv.
    """

    operation_kind: ResearchKaliOperationKind
    state: GuestAgentLocalReadinessState
    reason: str
    executable_path: str | None = None
    observed_version: str | None = None
    probe_process_started: bool = False
    target_operation_executed: bool = False
    target_network_used: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.operation_kind, ResearchKaliOperationKind):
            raise ResearchError(
                "Guest-agent local readiness receipt operation kind is invalid."
            )
        if not isinstance(self.state, GuestAgentLocalReadinessState):
            raise ResearchError("Guest-agent local readiness receipt state is invalid.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError(
                "Guest-agent local readiness receipt reason cannot be empty."
            )
        if "\x00" in self.reason or "\r" in self.reason or "\n" in self.reason:
            raise ResearchError(
                "Guest-agent local readiness receipt reason contains control data."
            )
        for value, label in (
            (self.executable_path, "executable path"),
            (self.observed_version, "observed version"),
        ):
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(
                    f"Guest-agent local readiness receipt {label} cannot be empty."
                )
            if "\x00" in value:
                raise ResearchError(
                    f"Guest-agent local readiness receipt {label} contains "
                    "control data."
                )
        if self.executable_path is not None and not self.executable_path.startswith(
            "/"
        ):
            raise ResearchError(
                "Guest-agent local readiness receipt executable path is invalid."
            )
        if self.observed_version is not None and (
            len(self.observed_version) > MAX_GUEST_AGENT_READINESS_OUTPUT_CHARACTERS
        ):
            raise ResearchError(
                "Guest-agent local readiness receipt observed version is too long."
            )
        if not isinstance(self.probe_process_started, bool):
            raise ResearchError(
                "Guest-agent local readiness receipt process flag is invalid."
            )
        if (
            self.target_operation_executed is not False
            or self.target_network_used is not False
        ):
            raise ResearchError(
                "Guest-agent local readiness receipt must never claim target "
                "operation execution or target network use."
            )

    @property
    def ready(self) -> bool:
        """Return whether the exact reviewed local executable is available."""
        return self.state is GuestAgentLocalReadinessState.READY


class GuestAgentLocalReadinessProbe:
    """Replaceable no-authority probe interface for local Guest-Agent readiness.

    May inspect only a `GuestAgentPreparedInvocation` -- never a
    `GuestAgentRequest`, a signed envelope, a raw operation kind plus caller
    path, an arbitrary executable path, argv, shell command, callback,
    environment mapping, working directory, or stdin content.
    """

    def check(
        self, prepared_invocation: GuestAgentPreparedInvocation
    ) -> GuestAgentLocalReadinessReceipt:
        """Return readiness without granting execution authority."""
        raise NotImplementedError


class UnavailableGuestAgentLocalReadinessProbe(GuestAgentLocalReadinessProbe):
    """Default probe used until an explicit local adapter is installed."""

    def check(
        self, prepared_invocation: GuestAgentPreparedInvocation
    ) -> GuestAgentLocalReadinessReceipt:
        """Fail closed without starting any local process."""
        if not isinstance(prepared_invocation, GuestAgentPreparedInvocation):
            raise ResearchError(
                "Guest-agent local readiness probe requires a prepared invocation."
            )
        return GuestAgentLocalReadinessReceipt(
            operation_kind=prepared_invocation.operation_kind,
            state=GuestAgentLocalReadinessState.UNAVAILABLE,
            reason="Guest-agent local readiness probe is not configured.",
        )
