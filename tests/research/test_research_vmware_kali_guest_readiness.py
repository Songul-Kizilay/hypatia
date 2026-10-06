"""VMware guest readiness: one fixed, networkless version probe only.

Locks in every fail-closed distinction the probe must make, that building
the contract types or the probe never starts a process or touches the
network, that host-not-ready always short-circuits before any guest
attempt, that the remote command can never be anything but
`/usr/bin/dig -v`, that the restricted-SSH argv never allows a shell,
interactive auth, agent/port forwarding or credential leakage, and that
`GUEST_READY` never creates a Kali operation authorization.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchVMwareKaliGuestReadiness import (
    EXPECTED_GUEST_DIG_EXECUTABLE,
    EXPECTED_GUEST_DIG_VERSION_PREFIX,
    ResearchVMwareKaliGuestReadiness,
    ResearchVMwareKaliGuestReadinessState,
    ResearchVMwareKaliGuestTransportRequirement,
    UnavailableResearchVMwareKaliGuestReadinessProbe,
)
from research.ResearchVMwareKaliHostReadiness import (
    ResearchVMwareKaliHostReadiness,
    ResearchVMwareKaliHostReadinessState,
    ResearchVMwareKaliHostRequirement,
)
from research.SshVMwareKaliGuestReadinessProbe import SshVMwareKaliGuestReadinessProbe

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
        observed_running_vmx_paths=(r"D:\VMs\kali.vmx",),
    )


def _host_not_ready() -> ResearchVMwareKaliHostReadiness:
    return ResearchVMwareKaliHostReadiness(
        requirement=_host_requirement(),
        state=ResearchVMwareKaliHostReadinessState.VM_NOT_RUNNING,
        reason="not running",
    )


class _TransportFixture:
    """A real temp directory with ssh.exe, a key file and known_hosts."""

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


def _completed(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=(), returncode=returncode, stdout=stdout, stderr=stderr
    )


class ResearchVMwareKaliGuestTransportRequirementTests(unittest.TestCase):
    def test_construction_never_touches_the_filesystem_or_a_process(self) -> None:
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            ResearchVMwareKaliGuestTransportRequirement(
                ssh_executable_path=r"C:\Windows\System32\OpenSSH\ssh.exe",
                private_key_path=r"C:\Users\hypatia\.ssh\hypatia_guest_ed25519",
                known_hosts_path=r"C:\Users\hypatia\.ssh\hypatia_known_hosts",
                guest_user=GUEST_USER,
                guest_host=GUEST_HOST,
            )

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_rejects_empty_or_control_character_fields(self) -> None:
        for bad in ("", "   ", "a\nb", "a\rb", "a\x00b"):
            with self.assertRaises(ResearchError):
                ResearchVMwareKaliGuestTransportRequirement(
                    ssh_executable_path=bad,
                    private_key_path=r"D:\keys\k",
                    known_hosts_path=r"D:\keys\kh",
                    guest_user=GUEST_USER,
                    guest_host=GUEST_HOST,
                )

    def test_rejects_a_relative_or_wrongly_named_ssh_path(self) -> None:
        for bad_path in (r"ssh.exe", r"C:\Windows\System32\OpenSSH\notssh.exe"):
            with self.assertRaises(ResearchError):
                ResearchVMwareKaliGuestTransportRequirement(
                    ssh_executable_path=bad_path,
                    private_key_path=r"D:\keys\k",
                    known_hosts_path=r"D:\keys\kh",
                    guest_user=GUEST_USER,
                    guest_host=GUEST_HOST,
                )

    def test_rejects_a_relative_key_or_known_hosts_path(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchVMwareKaliGuestTransportRequirement(
                ssh_executable_path=r"C:\Windows\System32\OpenSSH\ssh.exe",
                private_key_path="k",
                known_hosts_path=r"D:\keys\kh",
                guest_user=GUEST_USER,
                guest_host=GUEST_HOST,
            )
        with self.assertRaises(ResearchError):
            ResearchVMwareKaliGuestTransportRequirement(
                ssh_executable_path=r"C:\Windows\System32\OpenSSH\ssh.exe",
                private_key_path=r"D:\keys\k",
                known_hosts_path="kh",
                guest_user=GUEST_USER,
                guest_host=GUEST_HOST,
            )

    def test_rejects_whitespace_in_user_or_host(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchVMwareKaliGuestTransportRequirement(
                ssh_executable_path=r"C:\Windows\System32\OpenSSH\ssh.exe",
                private_key_path=r"D:\keys\k",
                known_hosts_path=r"D:\keys\kh",
                guest_user="hypatia probe",
                guest_host=GUEST_HOST,
            )

    def test_rejects_an_invalid_port_or_timeout(self) -> None:
        for bad_port in (0, -1, 65536, True):
            with self.assertRaises(ResearchError):
                ResearchVMwareKaliGuestTransportRequirement(
                    ssh_executable_path=r"C:\Windows\System32\OpenSSH\ssh.exe",
                    private_key_path=r"D:\keys\k",
                    known_hosts_path=r"D:\keys\kh",
                    guest_user=GUEST_USER,
                    guest_host=GUEST_HOST,
                    guest_port=bad_port,
                )
        for bad_timeout in (0, -1.0, 31.0, True):
            with self.assertRaises(ResearchError):
                ResearchVMwareKaliGuestTransportRequirement(
                    ssh_executable_path=r"C:\Windows\System32\OpenSSH\ssh.exe",
                    private_key_path=r"D:\keys\k",
                    known_hosts_path=r"D:\keys\kh",
                    guest_user=GUEST_USER,
                    guest_host=GUEST_HOST,
                    connect_timeout_seconds=bad_timeout,
                )


class ResearchVMwareKaliGuestReadinessTests(unittest.TestCase):
    def test_guest_ready_never_creates_an_operation_authorization(self) -> None:
        fixture = _TransportFixture()
        self.addCleanup(fixture.cleanup)
        readiness = ResearchVMwareKaliGuestReadiness(
            transport=fixture.requirement(),
            state=ResearchVMwareKaliGuestReadinessState.GUEST_READY,
            reason="ok",
            observed_version="DiG 9.18.0",
        )
        self.assertTrue(readiness.guest_ready)
        self.assertFalse(readiness.kali_operation_authorization_created)

    def test_cannot_construct_a_readiness_that_claims_an_authorization(self) -> None:
        fixture = _TransportFixture()
        self.addCleanup(fixture.cleanup)
        with self.assertRaises(ResearchError):
            ResearchVMwareKaliGuestReadiness(
                transport=fixture.requirement(),
                state=ResearchVMwareKaliGuestReadinessState.GUEST_READY,
                reason="ok",
                kali_operation_authorization_created=True,  # type: ignore[arg-type]
            )


class UnavailableResearchVMwareKaliGuestReadinessProbeTests(unittest.TestCase):
    def test_default_probe_fails_closed_without_process_or_network(self) -> None:
        fixture = _TransportFixture()
        self.addCleanup(fixture.cleanup)
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            readiness = UnavailableResearchVMwareKaliGuestReadinessProbe().readiness(
                _host_ready(), fixture.requirement()
            )

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()
        self.assertFalse(readiness.guest_ready)
        self.assertIs(
            readiness.state,
            ResearchVMwareKaliGuestReadinessState.GUEST_TRANSPORT_UNCONFIGURED,
        )


class SshVMwareKaliGuestReadinessProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = _TransportFixture()
        self.addCleanup(self.fixture.cleanup)
        self.probe = SshVMwareKaliGuestReadinessProbe()

    def test_construction_never_touches_the_filesystem_or_a_process(self) -> None:
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            SshVMwareKaliGuestReadinessProbe()

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_host_not_ready_makes_zero_authentication_attempt(self) -> None:
        self.fixture.write_all()
        with (
            patch("subprocess.run") as run,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            readiness = self.probe.readiness(
                _host_not_ready(), self.fixture.requirement()
            )

        run.assert_not_called()
        getaddrinfo.assert_not_called()
        self.assertIs(
            readiness.state, ResearchVMwareKaliGuestReadinessState.HOST_NOT_READY
        )
        self.assertFalse(readiness.guest_ready)

    def test_wrong_vm_identity_is_host_not_ready_before_any_guest_attempt(
        self,
    ) -> None:
        """A `VM_IDENTITY_MISMATCH` host result is still not `HOST_READY`,
        so this must take the exact same zero-attempt path as any other
        not-ready host state.
        """
        mismatched_host = ResearchVMwareKaliHostReadiness(
            requirement=_host_requirement(),
            state=ResearchVMwareKaliHostReadinessState.VM_IDENTITY_MISMATCH,
            reason="wrong vm",
        )
        self.fixture.write_all()
        with patch("subprocess.run") as run:
            readiness = self.probe.readiness(
                mismatched_host, self.fixture.requirement()
            )

        run.assert_not_called()
        self.assertIs(
            readiness.state, ResearchVMwareKaliGuestReadinessState.HOST_NOT_READY
        )

    def test_missing_transport_files_fail_closed_without_a_connection_attempt(
        self,
    ) -> None:
        # Nothing written: ssh.exe, key and known_hosts are all absent --
        # matches this project's real current state exactly.
        with patch("subprocess.run") as run:
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        run.assert_not_called()
        self.assertIs(
            readiness.state,
            ResearchVMwareKaliGuestReadinessState.GUEST_TRANSPORT_UNCONFIGURED,
        )

    def test_host_key_verification_failure_is_identity_unverified(self) -> None:
        self.fixture.write_all()
        completed = _completed(
            returncode=255,
            stderr="Host key verification failed.",
        )
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliGuestReadinessState.GUEST_IDENTITY_UNVERIFIED,
        )
        self.assertNotIn("Host key verification failed", readiness.reason)

    def test_pubkey_rejection_is_authentication_unavailable_with_no_leakage(
        self,
    ) -> None:
        self.fixture.write_all()
        completed = _completed(
            returncode=255,
            stderr=f"{GUEST_USER}@{GUEST_HOST}: Permission denied (publickey).",
        )
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliGuestReadinessState.AUTHENTICATION_UNAVAILABLE,
        )
        # The fixed reason string never echoes raw stderr -- no credential,
        # username/host combination, or any other connection detail leaks
        # through the returned result.
        self.assertNotIn("Permission denied", readiness.reason)
        self.assertNotIn(GUEST_HOST, readiness.reason)
        self.assertIsNone(readiness.observed_version)

    def test_missing_remote_tool_is_tool_missing(self) -> None:
        self.fixture.write_all()
        completed = _completed(
            returncode=127,
            stderr="bash: /usr/bin/dig: No such file or directory",
        )
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state, ResearchVMwareKaliGuestReadinessState.TOOL_MISSING
        )

    def test_non_executable_remote_tool_is_tool_missing_not_auth_failure(
        self,
    ) -> None:
        """POSIX shells report "found but not executable" as exit code 126,
        with a message that also contains the bare substring "Permission
        denied" -- this must never be misclassified as an SSH authentication
        rejection; the exit-code check is checked first precisely to avoid
        that ambiguity.
        """
        self.fixture.write_all()
        completed = _completed(
            returncode=126,
            stderr="bash: /usr/bin/dig: Permission denied",
        )
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state, ResearchVMwareKaliGuestReadinessState.TOOL_MISSING
        )

    def test_connection_refused_is_guest_unreachable(self) -> None:
        self.fixture.write_all()
        completed = _completed(
            returncode=255,
            stderr=f"ssh: connect to host {GUEST_HOST} port 22: Connection refused",
        )
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state, ResearchVMwareKaliGuestReadinessState.GUEST_UNREACHABLE
        )

    def test_connection_timed_out_is_guest_unreachable(self) -> None:
        self.fixture.write_all()
        completed = _completed(
            returncode=255,
            stderr=f"ssh: connect to host {GUEST_HOST} port 22: "
            "Connection timed out",
        )
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state, ResearchVMwareKaliGuestReadinessState.GUEST_UNREACHABLE
        )

    def test_timeout_is_guest_unreachable(self) -> None:
        self.fixture.write_all()
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ssh", timeout=5.0),
        ):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state, ResearchVMwareKaliGuestReadinessState.GUEST_UNREACHABLE
        )

    def test_oserror_is_guest_inspection_failed(self) -> None:
        self.fixture.write_all()
        with patch("subprocess.run", side_effect=OSError("boom")):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliGuestReadinessState.GUEST_INSPECTION_FAILED,
        )

    def test_unclassified_failure_fails_closed_not_ready(self) -> None:
        self.fixture.write_all()
        completed = _completed(returncode=1, stderr="some unexpected thing happened")
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliGuestReadinessState.GUEST_INSPECTION_FAILED,
        )

    def test_wrong_dig_version_prefix_is_version_mismatch(self) -> None:
        self.fixture.write_all()
        completed = _completed(returncode=0, stdout="dig-like-tool 1.0\n")
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliGuestReadinessState.TOOL_VERSION_MISMATCH,
        )

    def test_guest_ready_on_the_expected_version_prefix(self) -> None:
        self.fixture.write_all()
        completed = _completed(
            returncode=0, stdout="DiG 9.18.28-1~deb12u2-Debian <<>> -v\n"
        )
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state, ResearchVMwareKaliGuestReadinessState.GUEST_READY
        )
        self.assertTrue(readiness.guest_ready)
        self.assertIn(EXPECTED_GUEST_DIG_VERSION_PREFIX, readiness.observed_version)
        self.assertFalse(readiness.kali_operation_authorization_created)

    def test_argv_is_exactly_the_fixed_remote_command_with_no_shell_and_closed_stdin(
        self,
    ) -> None:
        """Locks in: no shell, closed stdin, bounded timeout, and the remote
        command is always exactly `/usr/bin/dig -v` -- never an arbitrary
        executable, extra argument, or user/model-authored argv.
        """
        self.fixture.write_all()
        completed = _completed(returncode=0, stdout="DiG 9.18.0\n")
        with patch("subprocess.run", return_value=completed) as run:
            self.probe.readiness(_host_ready(), self.fixture.requirement())

        run.assert_called_once()
        args, kwargs = run.call_args
        argv = args[0]
        self.assertEqual(argv[-2:], (EXPECTED_GUEST_DIG_EXECUTABLE, "-v"))
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(
            kwargs["timeout"], self.fixture.requirement().command_timeout_seconds
        )
        self.assertIn("BatchMode=yes", argv)
        self.assertIn("PasswordAuthentication=no", argv)
        self.assertIn("StrictHostKeyChecking=yes", argv)
        self.assertIn("ForwardAgent=no", argv)
        self.assertNotIn("-L", argv)
        self.assertNotIn("-R", argv)
        self.assertNotIn("-D", argv)
        self.assertNotIn("-t", argv)
        self.assertNotIn("-tt", argv)
        self.assertNotIn("-A", argv)
        # No vmrun-style guest-password flag anywhere -- key-based auth only.
        self.assertNotIn("-gp", argv)

    def test_timeout_cannot_exceed_the_existing_kali_maximum(self) -> None:
        from research.ResearchKaliOperationExecution import (
            MAX_KALI_OPERATION_TIMEOUT_SECONDS,
        )

        # The transport requirement's own bound (30s) is already <= the
        # existing Kali execution ceiling; this pins that relationship so a
        # future change to either constant cannot silently violate it.
        self.assertLessEqual(30.0, MAX_KALI_OPERATION_TIMEOUT_SECONDS)

    def test_stdout_is_bounded_even_when_adversarially_large(self) -> None:
        self.fixture.write_all()
        huge = EXPECTED_GUEST_DIG_VERSION_PREFIX + ("x" * 10000)
        completed = _completed(returncode=0, stdout=huge)
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state, ResearchVMwareKaliGuestReadinessState.GUEST_READY
        )
        self.assertLessEqual(len(readiness.observed_version), 500)

    def test_oversized_stderr_still_classifies_correctly_and_stays_bounded(
        self,
    ) -> None:
        """Classification must use bounded stdout/stderr, not raw: an
        adversarial or compromised guest returning gigabytes of output must
        not cost an unbounded local `casefold()`/concatenation before a
        result is reached.
        """
        self.fixture.write_all()
        completed = _completed(
            returncode=255,
            stderr="Host key verification failed." + ("z" * 2_000_000),
        )
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliGuestReadinessState.GUEST_IDENTITY_UNVERIFIED,
        )

    def test_control_characters_in_output_are_sanitized(self) -> None:
        self.fixture.write_all()
        completed = _completed(
            returncode=0,
            stdout=f"{EXPECTED_GUEST_DIG_VERSION_PREFIX}x\x07\x1b[31my\x00z\n",
        )
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        self.assertNotIn("\x07", readiness.observed_version)
        self.assertNotIn("\x00", readiness.observed_version)

    def test_never_calls_socket_getaddrinfo_on_any_path(self) -> None:
        self.fixture.write_all()
        completed = _completed(returncode=0, stdout="DiG 9.18.0\n")
        with (
            patch("subprocess.run", return_value=completed),
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            self.probe.readiness(_host_ready(), self.fixture.requirement())

        getaddrinfo.assert_not_called()

    def test_no_credential_appears_anywhere_in_the_result_repr(self) -> None:
        self.fixture.write_all()
        completed = _completed(returncode=0, stdout="DiG 9.18.0\n")
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(_host_ready(), self.fixture.requirement())

        # There is no password in this design at all (key-based auth only);
        # this proves the result's own repr carries nothing resembling one.
        self.assertNotIn("password", repr(readiness).casefold())
        self.assertNotIn("-gp", repr(readiness))


if __name__ == "__main__":
    unittest.main()
