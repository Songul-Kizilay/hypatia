"""VMware/Kali runtime readiness probe for the reviewed DNS_RECORD_LOOKUP path.

This probe grants no execution authority of any kind. It only composes the
two already-reviewed, already-typed readiness boundaries
(`ResearchVMwareKaliHostReadiness`, `ResearchVMwareKaliGuestReadiness`) into
the single `ResearchKaliRuntimeProbe` contract `KaliToolGateway` already
checks before dispatch. It never starts `vmrun`, SSH or any other process by
itself -- both sub-probes own their own process/network effects, and this
class only calls them, in the trusted host-then-guest order, when its own
`readiness()` method is invoked.

Mirroring `ResearchVMwareKaliHostReadiness.guest_execution_verified` and
`ResearchVMwareKaliGuestReadiness.kali_operation_authorization_created`, this
module never creates a Kali operation authorization and never claims one;
"ready" here means only that the one reviewed guest version probe
(`/usr/bin/dig -v`) succeeded, exactly as `ResearchVMwareKaliGuestReadiness`
itself defines it.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchKaliOperationPreview import ResearchKaliCommandTransport
from research.ResearchKaliRuntimeEnvironment import (
    ResearchKaliRuntimeProbe,
    ResearchKaliRuntimeReadiness,
    ResearchKaliRuntimeReadinessState,
    ResearchKaliRuntimeRequirement,
)
from research.ResearchVMwareKaliGuestReadiness import (
    EXPECTED_GUEST_DIG_EXECUTABLE,
    EXPECTED_GUEST_DIG_VERSION_PREFIX,
    ResearchVMwareKaliGuestReadinessProbe,
    ResearchVMwareKaliGuestTransportRequirement,
)
from research.ResearchVMwareKaliHostReadiness import (
    ResearchVMwareKaliHostReadinessProbe,
    ResearchVMwareKaliHostRequirement,
)


class VmwareKaliRuntimeProbe(ResearchKaliRuntimeProbe):
    """Compose host- and guest-readiness checks behind one trusted transport.

    Every constructor argument is trusted, code-owned configuration (the
    concrete sub-probes and the host/guest facts they check), injected once
    at process startup -- never request metadata, model output or a
    user-supplied string. Constructing this probe starts no process and
    touches no network; only a later `readiness()` call can.
    """

    def __init__(
        self,
        *,
        host_readiness_probe: ResearchVMwareKaliHostReadinessProbe,
        host_requirement: ResearchVMwareKaliHostRequirement,
        guest_readiness_probe: ResearchVMwareKaliGuestReadinessProbe,
        guest_transport: ResearchVMwareKaliGuestTransportRequirement,
    ) -> None:
        # `host_readiness_probe` and `guest_readiness_probe` are duck-typed
        # collaborators, exactly like `KaliToolGateway`'s own `runtime_probe`
        # and `process_adapter` constructor arguments: this class never
        # isinstance-checks a replaceable probe/adapter interface, only the
        # trusted data it is handed.
        if not isinstance(host_requirement, ResearchVMwareKaliHostRequirement):
            raise ResearchError("VMware Kali host requirement is invalid.")
        if not isinstance(guest_transport, ResearchVMwareKaliGuestTransportRequirement):
            raise ResearchError("VMware Kali guest transport requirement is invalid.")
        self._host_readiness_probe = host_readiness_probe
        self._host_requirement = host_requirement
        self._guest_readiness_probe = guest_readiness_probe
        self._guest_transport = guest_transport

    def readiness(
        self,
        requirement: ResearchKaliRuntimeRequirement,
    ) -> ResearchKaliRuntimeReadiness:
        """Return VMware guest readiness, or fail closed before any attempt.

        Refuses immediately -- with no host or guest attempt of any kind --
        unless the caller's own requirement already names this transport.
        This is what keeps a WSL-bound runtime requirement from ever
        reaching a VMware probe: `KaliToolGateway` builds the requirement
        from the preview's own trusted `transport` field, so a requirement
        naming any other transport reaching here would already indicate a
        caller/wiring mistake, never an operator or model choice.
        """
        if not isinstance(requirement, ResearchKaliRuntimeRequirement):
            raise ResearchError("Kali runtime requirement is invalid.")
        if requirement.transport is not ResearchKaliCommandTransport.VMWARE_KALI:
            return ResearchKaliRuntimeReadiness(
                requirement=requirement,
                state=ResearchKaliRuntimeReadinessState.UNAVAILABLE,
                reason="VMware Kali runtime probe does not support this transport.",
            )

        host_readiness = self._host_readiness_probe.readiness(self._host_requirement)
        guest_readiness = self._guest_readiness_probe.readiness(
            host_readiness, self._guest_transport
        )
        if not guest_readiness.guest_ready:
            return ResearchKaliRuntimeReadiness(
                requirement=requirement,
                state=ResearchKaliRuntimeReadinessState.UNAVAILABLE,
                reason=guest_readiness.reason,
            )
        # The guest probe only ever verifies one fixed tool (`/usr/bin/dig`);
        # confirm that is what this specific operation's requirement expects
        # before calling it ready, rather than reusing "guest_ready" for any
        # tool this requirement might one day name.
        if (
            requirement.executable_path != EXPECTED_GUEST_DIG_EXECUTABLE
            or requirement.version_prefix != EXPECTED_GUEST_DIG_VERSION_PREFIX
        ):
            return ResearchKaliRuntimeReadiness(
                requirement=requirement,
                state=ResearchKaliRuntimeReadinessState.UNAVAILABLE,
                reason=(
                    "VMware Kali guest readiness only verifies the reviewed "
                    "dig tool."
                ),
            )
        return ResearchKaliRuntimeReadiness(
            requirement=requirement,
            state=ResearchKaliRuntimeReadinessState.READY,
            reason=(
                "Reviewed VMware Kali host and guest prerequisites are " "available."
            ),
            observed_executable_path=requirement.executable_path,
            observed_version=guest_readiness.observed_version,
        )
