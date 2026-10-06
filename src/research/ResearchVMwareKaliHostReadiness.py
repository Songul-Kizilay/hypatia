"""Reviewed VMware host-side readiness facts for a future Kali transport.

This module is a boundary contract only. It does not power on or off a
virtual machine, does not log into a guest, does not run a guest command and
grants no execution authority of any kind.

A "host ready" result means only that the configured `vmrun` executable and
Kali `.vmx` exist, match the trusted identity this process was configured
with, and the virtual machine is currently running -- as observed by one
read-only `vmrun ... list` call. It says nothing about whether any tool
inside that guest is reachable, authenticated or runnable. Guest execution
readiness is a separate concern this module never asserts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath

from core.Exceptions import ResearchError


class ResearchVMwareKaliHostReadinessState(StrEnum):
    """Operator-visible VMware host readiness states.

    Each failure state names one specific, independently observable fact so
    an operator (or a test) never has to guess why `HOST_READY` was not
    reached. `HOST_READY` itself is a host-only fact; see the module and
    class docstrings for what it deliberately does not claim.
    """

    HOST_READY = "host_ready"
    VMRUN_EXECUTABLE_MISSING = "vmrun_executable_missing"
    VMX_MISSING = "vmx_missing"
    VM_IDENTITY_MISMATCH = "vm_identity_mismatch"
    VM_NOT_RUNNING = "vm_not_running"
    HOST_INSPECTION_FAILED = "host_inspection_failed"


@dataclass(frozen=True, slots=True)
class ResearchVMwareKaliHostRequirement:
    """Code-owned trusted facts required before VMware host readiness can exist.

    Every field here must be supplied by trusted, code-owned configuration
    (for example process environment variables read once at startup) --
    never by request metadata, model output or a user-supplied string. There
    is no constructor path that accepts an unvalidated or partially-trusted
    value: malformed input is rejected here, immediately, as a `ResearchError`.
    """

    vmrun_executable_path: str
    vmx_path: str
    vm_identity: str
    list_timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        for value, label in (
            (self.vmrun_executable_path, "vmrun executable path"),
            (self.vmx_path, "VMX path"),
            (self.vm_identity, "VM identity"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"VMware host {label} cannot be empty.")
            if "\x00" in value or "\r" in value or "\n" in value:
                raise ResearchError(f"VMware host {label} contains control data.")
        vmrun_path = PureWindowsPath(self.vmrun_executable_path)
        if (
            not self._is_absolute_on_any_platform(self.vmrun_executable_path)
            or vmrun_path.name.casefold() != "vmrun.exe"
        ):
            raise ResearchError(
                "VMware host vmrun executable path is not a trusted absolute "
                "vmrun.exe path."
            )
        vmx_path = PureWindowsPath(self.vmx_path)
        if (
            not self._is_absolute_on_any_platform(self.vmx_path)
            or vmx_path.suffix.casefold() != ".vmx"
        ):
            raise ResearchError(
                "VMware host VMX path is not a trusted absolute .vmx path."
            )
        if (
            isinstance(self.list_timeout_seconds, bool)
            or not isinstance(self.list_timeout_seconds, int | float)
            or not 0 < self.list_timeout_seconds <= 30.0
        ):
            raise ResearchError("VMware host list timeout is invalid.")

    @staticmethod
    def _is_absolute_on_any_platform(value: str) -> bool:
        """Accept a path absolute under either Windows or POSIX syntax.

        Real deployments always configure a genuine Windows path (`vmrun`
        and VMware Workstation only exist on Windows hosts); the Windows
        check alone is the one that matters there. The POSIX check exists
        only so this same trusted-format validation also accepts the
        real, OS-native temporary-file paths this module's own test suite
        constructs on a non-Windows CI runner -- it never relaxes what a
        *relative* path rejects on any platform.
        """
        return (
            PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()
        )


@dataclass(frozen=True, slots=True)
class ResearchVMwareKaliHostReadiness:
    """A readiness report limited to host-side VMware facts.

    `guest_execution_verified` exists only to make the boundary explicit in
    the type itself: this report can never claim guest execution is ready,
    so nothing downstream can mistake a host-ready result for a
    guest-execution grant. It is always `False` and is not settable to
    anything else.
    """

    requirement: ResearchVMwareKaliHostRequirement
    state: ResearchVMwareKaliHostReadinessState
    reason: str
    observed_running_vmx_paths: tuple[str, ...] = ()
    guest_execution_verified: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.requirement, ResearchVMwareKaliHostRequirement):
            raise ResearchError("VMware host requirement is invalid.")
        if not isinstance(self.state, ResearchVMwareKaliHostReadinessState):
            raise ResearchError("VMware host readiness state is invalid.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError("VMware host readiness reason cannot be empty.")
        if not isinstance(self.observed_running_vmx_paths, tuple):
            raise ResearchError(
                "VMware host observed running VMX paths must be immutable."
            )
        for value in self.observed_running_vmx_paths:
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise ResearchError(
                    "VMware host observed running VMX paths are invalid."
                )
        if self.guest_execution_verified is not False:
            raise ResearchError(
                "VMware host readiness must never claim guest execution."
            )

    @property
    def host_ready(self) -> bool:
        """Return whether the host-only prerequisites are reported ready.

        This is deliberately not named `ready`: see the class docstring for
        why host readiness must never be conflated with guest execution
        readiness.
        """
        return self.state is ResearchVMwareKaliHostReadinessState.HOST_READY


class ResearchVMwareKaliHostReadinessProbe:
    """Replaceable no-authority probe interface for VMware host readiness."""

    def readiness(
        self,
        requirement: ResearchVMwareKaliHostRequirement,
    ) -> ResearchVMwareKaliHostReadiness:
        """Return host readiness without granting execution authority."""
        raise NotImplementedError


class UnavailableResearchVMwareKaliHostReadinessProbe(
    ResearchVMwareKaliHostReadinessProbe
):
    """Default probe used until an explicit host adapter is installed."""

    def readiness(
        self,
        requirement: ResearchVMwareKaliHostRequirement,
    ) -> ResearchVMwareKaliHostReadiness:
        """Fail closed without running vmrun or touching the VM."""
        return ResearchVMwareKaliHostReadiness(
            requirement=requirement,
            state=ResearchVMwareKaliHostReadinessState.HOST_INSPECTION_FAILED,
            reason="VMware host readiness probe is not configured.",
        )
