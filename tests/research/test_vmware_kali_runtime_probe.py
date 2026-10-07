"""VMware/Kali runtime probe composes host+guest readiness; grants nothing.

Locks in: construction starts no process/network; a non-VMware transport
requirement is refused with no host or guest attempt; a host-not-ready
result reaches the real guest probe (via the gateway's own composition) and
still produces no SSH attempt; guest-not-ready never becomes READY; and
reaching GUEST_READY end-to-end never creates a Kali operation
authorization or claims any transport other than VMWARE_KALI.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchKaliOperationPreview import ResearchKaliCommandTransport
from research.ResearchKaliRuntimeEnvironment import (
    ResearchKaliRuntimeReadinessState,
    ResearchKaliRuntimeRequirement,
)
from research.ResearchVMwareKaliGuestReadiness import (
    EXPECTED_GUEST_DIG_EXECUTABLE,
    EXPECTED_GUEST_DIG_VERSION_PREFIX,
    ResearchVMwareKaliGuestReadiness,
    ResearchVMwareKaliGuestReadinessState,
    ResearchVMwareKaliGuestTransportRequirement,
)
from research.ResearchVMwareKaliHostReadiness import (
    ResearchVMwareKaliHostReadiness,
    ResearchVMwareKaliHostReadinessState,
    ResearchVMwareKaliHostRequirement,
)
from research.SshVMwareKaliGuestReadinessProbe import SshVMwareKaliGuestReadinessProbe
from research.VmrunVMwareKaliHostReadinessProbe import VmrunVMwareKaliHostReadinessProbe
from research.VmwareKaliRuntimeProbe import VmwareKaliRuntimeProbe

GUEST_USER = "hypatia-probe"
GUEST_HOST = "192.168.206.128"


def _host_requirement() -> ResearchVMwareKaliHostRequirement:
    return ResearchVMwareKaliHostRequirement(
        vmrun_executable_path=r"C:\Program Files\VMware\vmrun.exe",
        vmx_path=r"D:\VMs\kali.vmx",
        vm_identity="kali linux",
    )


def _host_ready() -> ResearchVMwareKaliHostReadiness:
    return ResearchVMwareKaliHostReadiness(
        requirement=_host_requirement(),
        state=ResearchVMwareKaliHostReadinessState.HOST_READY,
        reason="ok",
    )


def _host_not_ready() -> ResearchVMwareKaliHostReadiness:
    return ResearchVMwareKaliHostReadiness(
        requirement=_host_requirement(),
        state=ResearchVMwareKaliHostReadinessState.VM_NOT_RUNNING,
        reason="VM not running.",
    )


class _FakeHostProbe:
    def __init__(self, readiness: ResearchVMwareKaliHostReadiness) -> None:
        self._readiness = readiness
        self.calls: list[ResearchVMwareKaliHostRequirement] = []

    def readiness(
        self, requirement: ResearchVMwareKaliHostRequirement
    ) -> ResearchVMwareKaliHostReadiness:
        self.calls.append(requirement)
        return self._readiness


class _FakeGuestProbe:
    def __init__(self, readiness: ResearchVMwareKaliGuestReadiness) -> None:
        self._readiness = readiness
        self.calls: list[tuple[object, object]] = []

    def readiness(self, host_readiness, transport):  # type: ignore[no-untyped-def]
        self.calls.append((host_readiness, transport))
        return self._readiness


def _guest_transport() -> ResearchVMwareKaliGuestTransportRequirement:
    """A trusted-shaped transport requirement that never needs real files.

    Every test below that does not reach the real guest probe's own
    filesystem checks (because it uses a fake guest probe, or because a
    host-not-ready result short-circuits before those checks) can use this
    static-path fixture instead of a real temporary directory.
    """
    return ResearchVMwareKaliGuestTransportRequirement(
        ssh_executable_path=r"C:\Windows\System32\OpenSSH\ssh.exe",
        private_key_path=r"C:\Users\hypatia\.ssh\hypatia_guest_ed25519",
        known_hosts_path=r"C:\Users\hypatia\.ssh\hypatia_known_hosts",
        guest_user=GUEST_USER,
        guest_host=GUEST_HOST,
    )


class _TransportFixture:
    """A real temp directory with ssh.exe, a key file and known_hosts.

    Only needed by the one test that exercises the real guest probe's
    happy path, which checks file existence before it probes.
    """

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ssh_path = str(Path(self._tmp.name) / "ssh.exe")
        self.key_path = str(Path(self._tmp.name) / "hypatia_guest_ed25519")
        self.known_hosts_path = str(Path(self._tmp.name) / "hypatia_known_hosts")

    def write_all(self) -> None:
        Path(self.ssh_path).write_bytes(b"")
        Path(self.key_path).write_bytes(b"")
        Path(self.known_hosts_path).write_bytes(b"")

    def requirement(self) -> ResearchVMwareKaliGuestTransportRequirement:
        return ResearchVMwareKaliGuestTransportRequirement(
            ssh_executable_path=self.ssh_path,
            private_key_path=self.key_path,
            known_hosts_path=self.known_hosts_path,
            guest_user=GUEST_USER,
            guest_host=GUEST_HOST,
        )

    def cleanup(self) -> None:
        self._tmp.cleanup()


def _dns_requirement(
    transport: ResearchKaliCommandTransport = ResearchKaliCommandTransport.VMWARE_KALI,
) -> ResearchKaliRuntimeRequirement:
    return ResearchKaliRuntimeRequirement(
        transport=transport,
        executable_path=EXPECTED_GUEST_DIG_EXECUTABLE,
        version_prefix=EXPECTED_GUEST_DIG_VERSION_PREFIX,
        version_arguments=("-v",),
    )


class VmwareKaliRuntimeProbeTests(unittest.TestCase):
    def test_construction_starts_no_process_or_network(self) -> None:
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            VmwareKaliRuntimeProbe(
                host_readiness_probe=_FakeHostProbe(_host_ready()),
                host_requirement=_host_requirement(),
                guest_readiness_probe=_FakeGuestProbe(
                    ResearchVMwareKaliGuestReadiness(
                        transport=_guest_transport(),
                        state=ResearchVMwareKaliGuestReadinessState.GUEST_READY,
                        reason="ok",
                        observed_version=f"{EXPECTED_GUEST_DIG_VERSION_PREFIX}18.36",
                    )
                ),
                guest_transport=_guest_transport(),
            )
        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_wsl_transport_requirement_is_rejected_without_any_attempt(self) -> None:
        host_probe = _FakeHostProbe(_host_ready())
        guest_probe = _FakeGuestProbe(
            ResearchVMwareKaliGuestReadiness(
                transport=_guest_transport(),
                state=ResearchVMwareKaliGuestReadinessState.GUEST_READY,
                reason="ok",
                observed_version=f"{EXPECTED_GUEST_DIG_VERSION_PREFIX}18.36",
            )
        )
        probe = VmwareKaliRuntimeProbe(
            host_readiness_probe=host_probe,
            host_requirement=_host_requirement(),
            guest_readiness_probe=guest_probe,
            guest_transport=_guest_transport(),
        )

        readiness = probe.readiness(
            _dns_requirement(ResearchKaliCommandTransport.WSL_KALI)
        )

        self.assertIs(readiness.state, ResearchKaliRuntimeReadinessState.UNAVAILABLE)
        self.assertFalse(readiness.ready)
        self.assertEqual(host_probe.calls, [])
        self.assertEqual(guest_probe.calls, [])

    def test_wrong_requirement_type_is_rejected(self) -> None:
        probe = VmwareKaliRuntimeProbe(
            host_readiness_probe=_FakeHostProbe(_host_ready()),
            host_requirement=_host_requirement(),
            guest_readiness_probe=_FakeGuestProbe(
                ResearchVMwareKaliGuestReadiness(
                    transport=_guest_transport(),
                    state=ResearchVMwareKaliGuestReadinessState.GUEST_READY,
                    reason="ok",
                )
            ),
            guest_transport=_guest_transport(),
        )
        with self.assertRaises(ResearchError):
            probe.readiness("not-a-requirement")  # type: ignore[arg-type]

    def test_host_not_ready_short_circuits_before_any_real_ssh_attempt(
        self,
    ) -> None:
        host_probe = _FakeHostProbe(_host_not_ready())
        probe = VmwareKaliRuntimeProbe(
            host_readiness_probe=host_probe,
            host_requirement=_host_requirement(),
            guest_readiness_probe=SshVMwareKaliGuestReadinessProbe(),
            guest_transport=_guest_transport(),
        )

        with patch("subprocess.run") as run:
            readiness = probe.readiness(_dns_requirement())

        self.assertIs(readiness.state, ResearchKaliRuntimeReadinessState.UNAVAILABLE)
        self.assertEqual(len(host_probe.calls), 1)
        run.assert_not_called()

    def test_guest_not_ready_never_becomes_ready(self) -> None:
        guest_probe = _FakeGuestProbe(
            ResearchVMwareKaliGuestReadiness(
                transport=_guest_transport(),
                state=ResearchVMwareKaliGuestReadinessState.GUEST_UNREACHABLE,
                reason="Guest endpoint could not be reached.",
            )
        )
        probe = VmwareKaliRuntimeProbe(
            host_readiness_probe=_FakeHostProbe(_host_ready()),
            host_requirement=_host_requirement(),
            guest_readiness_probe=guest_probe,
            guest_transport=_guest_transport(),
        )

        readiness = probe.readiness(_dns_requirement())

        self.assertIs(readiness.state, ResearchKaliRuntimeReadinessState.UNAVAILABLE)
        self.assertIn("could not be reached", readiness.reason)
        self.assertEqual(len(guest_probe.calls), 1)

    def test_requirement_naming_a_different_tool_is_refused_even_if_guest_ready(
        self,
    ) -> None:
        guest_probe = _FakeGuestProbe(
            ResearchVMwareKaliGuestReadiness(
                transport=_guest_transport(),
                state=ResearchVMwareKaliGuestReadinessState.GUEST_READY,
                reason="ok",
                observed_version=f"{EXPECTED_GUEST_DIG_VERSION_PREFIX}18.36",
            )
        )
        probe = VmwareKaliRuntimeProbe(
            host_readiness_probe=_FakeHostProbe(_host_ready()),
            host_requirement=_host_requirement(),
            guest_readiness_probe=guest_probe,
            guest_transport=_guest_transport(),
        )
        requirement = ResearchKaliRuntimeRequirement(
            transport=ResearchKaliCommandTransport.VMWARE_KALI,
            executable_path="/usr/bin/curl",
            version_prefix="curl ",
            version_arguments=("--version",),
        )

        readiness = probe.readiness(requirement)

        self.assertIs(readiness.state, ResearchKaliRuntimeReadinessState.UNAVAILABLE)

    def test_end_to_end_guest_ready_never_creates_an_authorization(self) -> None:
        fixture = _TransportFixture()
        fixture.write_all()
        try:
            probe = VmwareKaliRuntimeProbe(
                host_readiness_probe=_FakeHostProbe(_host_ready()),
                host_requirement=_host_requirement(),
                guest_readiness_probe=SshVMwareKaliGuestReadinessProbe(),
                guest_transport=fixture.requirement(),
            )
            import subprocess as subprocess_module

            completed = subprocess_module.CompletedProcess(
                args=(),
                returncode=0,
                stdout=f"{EXPECTED_GUEST_DIG_VERSION_PREFIX}18.36-1-Debian\n",
                stderr="",
            )
            with patch("subprocess.run", return_value=completed) as run:
                readiness = probe.readiness(_dns_requirement())

            self.assertTrue(readiness.ready)
            self.assertIs(readiness.state, ResearchKaliRuntimeReadinessState.READY)
            self.assertFalse(readiness.process_created)
            self.assertFalse(readiness.network_used)
            run.assert_called_once()
            # No operation authority of any kind is exposed by this type.
            self.assertFalse(hasattr(readiness, "authorization_id"))
            self.assertFalse(hasattr(readiness, "operation_digest"))
        finally:
            fixture.cleanup()

    def test_host_probe_construction_uses_the_trusted_vmrun_probe_type(
        self,
    ) -> None:
        # Confirms the probe this module is meant to be wired with in
        # Bootstrap satisfies its own interface, without starting anything.
        probe = VmrunVMwareKaliHostReadinessProbe()
        self.assertTrue(hasattr(probe, "readiness"))


if __name__ == "__main__":
    unittest.main()
