"""Reviewed VMware guest-side readiness facts for the one allowed probe.

This module is a boundary contract only. It does not start an SSH
connection, does not authenticate, does not run a guest command and grants
no execution authority of any kind -- including no target-operation
authority. Guest readiness is deliberately a separate typed fact from host
readiness (`ResearchVMwareKaliHostReadiness`): a caller must already hold a
`HOST_READY` result before a guest check can mean anything, and this module
never re-derives or re-checks host facts itself.

"Guest ready" means only that: the host was already verified ready; a
trusted, pinned SSH identity (dedicated key, pinned host key, dedicated
guest account) reached exactly one fixed, code-owned, networkless command
(`/usr/bin/dig -v`) and it returned the expected version prefix. It is not
authority to run any target operation, and recording it never creates a
Kali operation authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath

from core.Exceptions import ResearchError
from research.ResearchVMwareKaliHostReadiness import ResearchVMwareKaliHostReadiness

#: The one allowed guest operation for this milestone: a fixed, code-owned
#: version probe. Not configurable, not an input anywhere in this module --
#: there is no parameter that could carry a different executable or
#: arguments.
EXPECTED_GUEST_DIG_EXECUTABLE = "/usr/bin/dig"
EXPECTED_GUEST_DIG_VERSION_PREFIX = "DiG 9."


class ResearchVMwareKaliGuestReadinessState(StrEnum):
    """Operator-visible VMware guest readiness states.

    Each failure state names one specific, independently observable fact,
    mirroring the host readiness contract's own discipline. `GUEST_READY`
    is still not execution authority of any kind; see the module docstring.
    """

    GUEST_READY = "guest_ready"
    HOST_NOT_READY = "host_not_ready"
    GUEST_TRANSPORT_UNCONFIGURED = "guest_transport_unconfigured"
    GUEST_UNREACHABLE = "guest_unreachable"
    GUEST_IDENTITY_UNVERIFIED = "guest_identity_unverified"
    AUTHENTICATION_UNAVAILABLE = "authentication_unavailable"
    TOOL_MISSING = "tool_missing"
    TOOL_UNEXECUTABLE = "tool_unexecutable"
    TOOL_VERSION_MISMATCH = "tool_version_mismatch"
    GUEST_INSPECTION_FAILED = "guest_inspection_failed"


@dataclass(frozen=True, slots=True)
class ResearchVMwareKaliGuestTransportRequirement:
    """Code-owned trusted facts required before a guest probe can run.

    Every field here must be supplied by trusted, code-owned configuration
    -- never by request metadata, model output or a user-supplied string.
    There is no field for a remote executable or arguments: the one allowed
    remote command is a module-level constant, never a parameter, so it
    cannot be substituted by anything this type carries.
    """

    ssh_executable_path: str
    private_key_path: str
    known_hosts_path: str
    guest_user: str
    guest_host: str
    guest_port: int = 22
    connect_timeout_seconds: float = 5.0
    command_timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        for value, label in (
            (self.ssh_executable_path, "ssh executable path"),
            (self.private_key_path, "private key path"),
            (self.known_hosts_path, "known_hosts path"),
            (self.guest_user, "guest user"),
            (self.guest_host, "guest host"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"VMware guest {label} cannot be empty.")
            if "\x00" in value or "\r" in value or "\n" in value:
                raise ResearchError(f"VMware guest {label} contains control data.")
        ssh_path = PureWindowsPath(self.ssh_executable_path)
        if (
            not self._is_absolute_on_any_platform(self.ssh_executable_path)
            or ssh_path.name.casefold() != "ssh.exe"
        ):
            raise ResearchError(
                "VMware guest ssh executable path is not a trusted absolute "
                "ssh.exe path."
            )
        if not self._is_absolute_on_any_platform(self.private_key_path):
            raise ResearchError(
                "VMware guest private key path is not a trusted absolute path."
            )
        if not self._is_absolute_on_any_platform(self.known_hosts_path):
            raise ResearchError(
                "VMware guest known_hosts path is not a trusted absolute path."
            )
        if any(character.isspace() for character in self.guest_user):
            raise ResearchError("VMware guest user is invalid.")
        if any(character.isspace() for character in self.guest_host):
            raise ResearchError("VMware guest host is invalid.")
        if (
            isinstance(self.guest_port, bool)
            or not isinstance(self.guest_port, int)
            or not 1 <= self.guest_port <= 65535
        ):
            raise ResearchError("VMware guest port is invalid.")
        for timeout_value, timeout_label in (
            (self.connect_timeout_seconds, "connect timeout"),
            (self.command_timeout_seconds, "command timeout"),
        ):
            if (
                isinstance(timeout_value, bool)
                or not isinstance(timeout_value, int | float)
                or not 0 < timeout_value <= 30.0
            ):
                raise ResearchError(f"VMware guest {timeout_label} is invalid.")

    @staticmethod
    def _is_absolute_on_any_platform(value: str) -> bool:
        """Accept a path absolute under either Windows or POSIX syntax.

        Real deployments always configure a genuine Windows path; the POSIX
        branch exists only so this same validation also accepts this
        module's own real, OS-native CI fixture paths on a non-Windows
        runner, exactly mirroring `ResearchVMwareKaliHostRequirement`.
        """
        return (
            PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()
        )


@dataclass(frozen=True, slots=True)
class ResearchVMwareKaliGuestReadiness:
    """A readiness report limited to the one allowed guest version probe.

    `kali_operation_authorization_created` exists only to make the boundary
    explicit in the type itself, mirroring `ResearchVMwareKaliHostReadiness
    .guest_execution_verified`: reaching `GUEST_READY` never creates a Kali
    operation authorization and is never itself execution authority. It is
    always `False` and is not settable to anything else.
    """

    transport: ResearchVMwareKaliGuestTransportRequirement
    state: ResearchVMwareKaliGuestReadinessState
    reason: str
    observed_version: str | None = None
    kali_operation_authorization_created: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.transport, ResearchVMwareKaliGuestTransportRequirement):
            raise ResearchError("VMware guest transport requirement is invalid.")
        if not isinstance(self.state, ResearchVMwareKaliGuestReadinessState):
            raise ResearchError("VMware guest readiness state is invalid.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError("VMware guest readiness reason cannot be empty.")
        if self.observed_version is not None:
            if (
                not isinstance(self.observed_version, str)
                or not self.observed_version.strip()
                or "\x00" in self.observed_version
            ):
                raise ResearchError("VMware guest observed version is invalid.")
        if self.kali_operation_authorization_created is not False:
            raise ResearchError(
                "VMware guest readiness must never claim an operation authorization."
            )

    @property
    def guest_ready(self) -> bool:
        """Return whether the one allowed version probe reached the guest.

        This is not execution authority: see the class and module
        docstrings.
        """
        return self.state is ResearchVMwareKaliGuestReadinessState.GUEST_READY


class ResearchVMwareKaliGuestReadinessProbe:
    """Replaceable no-authority probe interface for VMware guest readiness."""

    def readiness(
        self,
        host_readiness: ResearchVMwareKaliHostReadiness,
        transport: ResearchVMwareKaliGuestTransportRequirement,
    ) -> ResearchVMwareKaliGuestReadiness:
        """Return guest readiness without granting execution authority."""
        raise NotImplementedError


class UnavailableResearchVMwareKaliGuestReadinessProbe(
    ResearchVMwareKaliGuestReadinessProbe
):
    """Default probe used until an explicit guest adapter is installed."""

    def readiness(
        self,
        host_readiness: ResearchVMwareKaliHostReadiness,
        transport: ResearchVMwareKaliGuestTransportRequirement,
    ) -> ResearchVMwareKaliGuestReadiness:
        """Fail closed without an SSH attempt of any kind."""
        return ResearchVMwareKaliGuestReadiness(
            transport=transport,
            state=ResearchVMwareKaliGuestReadinessState.GUEST_TRANSPORT_UNCONFIGURED,
            reason="VMware guest readiness probe is not configured.",
        )
