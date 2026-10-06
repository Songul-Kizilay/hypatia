"""VMware host-side readiness probe for a future reviewed Kali transport.

This adapter checks only local host facts: whether the configured `vmrun`
executable and Kali `.vmx` file exist, whether the `.vmx` file's own recorded
display name matches the trusted configured identity, and whether that exact
VM is currently running -- observed with exactly one read-only
`vmrun -T ws list` call. It never starts, stops or otherwise mutates the
virtual machine's power state, never logs into the guest, never supplies a
guest credential and never runs a guest command. It performs no network
operation and no DNS/HTTPS target traffic of any kind.
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PureWindowsPath

from core.Exceptions import ResearchError
from research.ResearchVMwareKaliHostReadiness import (
    ResearchVMwareKaliHostReadiness,
    ResearchVMwareKaliHostReadinessProbe,
    ResearchVMwareKaliHostReadinessState,
    ResearchVMwareKaliHostRequirement,
)

MAX_VMX_FILE_BYTES = 65536
MAX_VMRUN_LIST_OUTPUT_CHARACTERS = 4000
_VMRUN_LIST_HEADER_PREFIX = "Total running VMs:"


class VmrunVMwareKaliHostReadinessProbe(ResearchVMwareKaliHostReadinessProbe):
    """Inspect one configured, trusted VMware host using `vmrun ... list`."""

    def readiness(
        self,
        requirement: ResearchVMwareKaliHostRequirement,
    ) -> ResearchVMwareKaliHostReadiness:
        """Return host readiness from read-only, host-local inspection only."""
        if not isinstance(requirement, ResearchVMwareKaliHostRequirement):
            raise ResearchError("VMware host requirement is invalid.")

        vmrun_path = Path(requirement.vmrun_executable_path)
        if not vmrun_path.is_file():
            return self._result(
                requirement,
                ResearchVMwareKaliHostReadinessState.VMRUN_EXECUTABLE_MISSING,
                "Configured vmrun executable was not found on this host.",
            )

        vmx_path = Path(requirement.vmx_path)
        if not vmx_path.is_file():
            return self._result(
                requirement,
                ResearchVMwareKaliHostReadinessState.VMX_MISSING,
                "Configured Kali VMX file was not found on this host.",
            )

        try:
            identity_matches = self._vmx_identity_matches(
                vmx_path, requirement.vm_identity
            )
        except OSError:
            return self._result(
                requirement,
                ResearchVMwareKaliHostReadinessState.HOST_INSPECTION_FAILED,
                "Configured Kali VMX file could not be read.",
            )
        if not identity_matches:
            return self._result(
                requirement,
                ResearchVMwareKaliHostReadinessState.VM_IDENTITY_MISMATCH,
                "Configured VMX file's recorded identity did not match the "
                "trusted configured identity.",
            )

        try:
            completed = subprocess.run(
                (str(vmrun_path), "-T", "ws", "list"),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                shell=False,
                timeout=requirement.list_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return self._result(
                requirement,
                ResearchVMwareKaliHostReadinessState.HOST_INSPECTION_FAILED,
                f"Unable to run vmrun list: {type(error).__name__}.",
            )

        if completed.returncode != 0:
            return self._result(
                requirement,
                ResearchVMwareKaliHostReadinessState.HOST_INSPECTION_FAILED,
                "vmrun list returned a non-zero exit code.",
            )

        running_paths = self._parse_vmrun_list_output(completed.stdout)
        if running_paths is None:
            return self._result(
                requirement,
                ResearchVMwareKaliHostReadinessState.HOST_INSPECTION_FAILED,
                "vmrun list output was not in the expected format.",
            )

        configured = self._normalized_windows_path(requirement.vmx_path)
        if any(
            self._normalized_windows_path(path) == configured for path in running_paths
        ):
            return self._result(
                requirement,
                ResearchVMwareKaliHostReadinessState.HOST_READY,
                "Configured vmrun, VMX identity and running VM were all "
                "verified host-side.",
                observed_running_vmx_paths=running_paths,
            )
        return self._result(
            requirement,
            ResearchVMwareKaliHostReadinessState.VM_NOT_RUNNING,
            "Configured Kali VM was not in the running VM list.",
            observed_running_vmx_paths=running_paths,
        )

    @staticmethod
    def _result(
        requirement: ResearchVMwareKaliHostRequirement,
        state: ResearchVMwareKaliHostReadinessState,
        reason: str,
        *,
        observed_running_vmx_paths: tuple[str, ...] = (),
    ) -> ResearchVMwareKaliHostReadiness:
        return ResearchVMwareKaliHostReadiness(
            requirement=requirement,
            state=state,
            reason=reason,
            observed_running_vmx_paths=observed_running_vmx_paths,
        )

    @staticmethod
    def _vmx_identity_matches(vmx_path: Path, expected_identity: str) -> bool:
        """Compare the VMX file's own `displayName` to the trusted identity.

        A plain local text-file read of a `.vmx` key/value file; no guest
        login, no guest command, no network access.
        """
        with vmx_path.open("rb") as vmx_file:
            raw = vmx_file.read(MAX_VMX_FILE_BYTES)
        text = raw.decode("utf-8", errors="replace")
        expected = expected_identity.strip().casefold()
        for line in text.splitlines():
            stripped = line.strip()
            if "=" not in stripped:
                continue
            raw_key, _, raw_value = stripped.partition("=")
            if raw_key.strip().casefold() != "displayname":
                continue
            value = raw_value.strip().strip('"').strip()
            return value.casefold() == expected
        return False

    @staticmethod
    def _parse_vmrun_list_output(output: str) -> tuple[str, ...] | None:
        lines = [
            line.strip()
            for line in output[:MAX_VMRUN_LIST_OUTPUT_CHARACTERS].splitlines()
            if line.strip()
        ]
        if not lines or not lines[0].startswith(_VMRUN_LIST_HEADER_PREFIX):
            return None
        return tuple(lines[1:])

    @staticmethod
    def _normalized_windows_path(value: str) -> str:
        return str(PureWindowsPath(value.strip().strip('"'))).casefold()
