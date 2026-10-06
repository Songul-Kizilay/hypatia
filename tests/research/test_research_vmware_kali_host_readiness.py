"""VMware host readiness: host-only facts, never guest execution authority.

Locks in every fail-closed distinction the probe must make, that building
the contract types or the probe never starts a process or touches the
network, that only a read-only `vmrun ... list` call is ever made (never a
power-state mutation, guest login or guest command), and that output stays
bounded even when the host or vmrun returns adversarial content.
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
from research.ResearchVMwareKaliHostReadiness import (
    ResearchVMwareKaliHostReadinessState,
    ResearchVMwareKaliHostRequirement,
    UnavailableResearchVMwareKaliHostReadinessProbe,
)
from research.VmrunVMwareKaliHostReadinessProbe import (
    MAX_VMX_FILE_BYTES,
    VmrunVMwareKaliHostReadinessProbe,
)

VM_IDENTITY = "Kali Linux (Hypatia)"


class _HostFixture:
    """A real temp directory with a vmrun.exe and a .vmx file, nothing else."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vmrun_path = str(Path(self._tmp.name) / "vmrun.exe")
        self.vmx_path = str(Path(self._tmp.name) / "kali.vmx")

    def write_vmrun(self) -> None:
        Path(self.vmrun_path).write_bytes(b"")

    def write_vmx(self, display_name: str = VM_IDENTITY) -> None:
        Path(self.vmx_path).write_text(
            f'.encoding = "UTF-8"\ndisplayName = "{display_name}"\n',
            encoding="utf-8",
        )

    def requirement(self) -> ResearchVMwareKaliHostRequirement:
        return ResearchVMwareKaliHostRequirement(
            vmrun_executable_path=self.vmrun_path,
            vmx_path=self.vmx_path,
            vm_identity=VM_IDENTITY,
        )

    def cleanup(self) -> None:
        self._tmp.cleanup()


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=(), returncode=returncode, stdout=stdout, stderr=""
    )


class ResearchVMwareKaliHostRequirementTests(unittest.TestCase):
    def test_construction_never_touches_the_filesystem_or_a_process(self) -> None:
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            ResearchVMwareKaliHostRequirement(
                vmrun_executable_path=r"C:\Program Files\VMware\vmrun.exe",
                vmx_path=r"D:\VMs\kali.vmx",
                vm_identity=VM_IDENTITY,
            )

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_rejects_empty_or_control_character_fields(self) -> None:
        for bad in ("", "   ", "a\nb", "a\rb", "a\x00b"):
            with self.assertRaises(ResearchError):
                ResearchVMwareKaliHostRequirement(
                    vmrun_executable_path=bad,
                    vmx_path=r"D:\VMs\kali.vmx",
                    vm_identity=VM_IDENTITY,
                )

    def test_rejects_a_relative_or_wrongly_named_vmrun_path(self) -> None:
        for bad_path in (
            r"vmrun.exe",
            r"C:\Program Files\VMware\notvmrun.exe",
            r"C:\Program Files\VMware\vmrun.exe.bat",
        ):
            with self.assertRaises(ResearchError):
                ResearchVMwareKaliHostRequirement(
                    vmrun_executable_path=bad_path,
                    vmx_path=r"D:\VMs\kali.vmx",
                    vm_identity=VM_IDENTITY,
                )

    def test_rejects_a_relative_or_wrongly_suffixed_vmx_path(self) -> None:
        for bad_path in (r"kali.vmx", r"D:\VMs\kali.txt"):
            with self.assertRaises(ResearchError):
                ResearchVMwareKaliHostRequirement(
                    vmrun_executable_path=r"C:\Program Files\VMware\vmrun.exe",
                    vmx_path=bad_path,
                    vm_identity=VM_IDENTITY,
                )

    def test_accepts_a_posix_style_absolute_path_but_still_rejects_relative(
        self,
    ) -> None:
        """`vmrun`/VMware Workstation are Windows-only in real deployment, but
        this same format check also runs on a non-Windows CI runner against
        real, OS-native temporary-file paths (see `_HostFixture` below) --
        so an absolute POSIX-style path must be accepted here, while a
        genuinely relative path must still be rejected on every platform.
        """
        ResearchVMwareKaliHostRequirement(
            vmrun_executable_path="/tmp/fake/vmrun.exe",
            vmx_path="/tmp/fake/kali.vmx",
            vm_identity=VM_IDENTITY,
        )
        with self.assertRaises(ResearchError):
            ResearchVMwareKaliHostRequirement(
                vmrun_executable_path="tmp/fake/vmrun.exe",
                vmx_path="/tmp/fake/kali.vmx",
                vm_identity=VM_IDENTITY,
            )

    def test_rejects_an_invalid_timeout(self) -> None:
        for bad_timeout in (0, -1.0, 31.0, True):
            with self.assertRaises(ResearchError):
                ResearchVMwareKaliHostRequirement(
                    vmrun_executable_path=r"C:\Program Files\VMware\vmrun.exe",
                    vmx_path=r"D:\VMs\kali.vmx",
                    vm_identity=VM_IDENTITY,
                    list_timeout_seconds=bad_timeout,
                )


class UnavailableResearchVMwareKaliHostReadinessProbeTests(unittest.TestCase):
    def test_default_probe_fails_closed_without_process_or_network(self) -> None:
        requirement = ResearchVMwareKaliHostRequirement(
            vmrun_executable_path=r"C:\Program Files\VMware\vmrun.exe",
            vmx_path=r"D:\VMs\kali.vmx",
            vm_identity=VM_IDENTITY,
        )
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            readiness = UnavailableResearchVMwareKaliHostReadinessProbe().readiness(
                requirement
            )

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()
        self.assertFalse(readiness.host_ready)
        self.assertIs(
            readiness.state, ResearchVMwareKaliHostReadinessState.HOST_INSPECTION_FAILED
        )
        self.assertFalse(readiness.guest_execution_verified)


class VmrunVMwareKaliHostReadinessProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = _HostFixture()
        self.addCleanup(self.fixture.cleanup)
        self.probe = VmrunVMwareKaliHostReadinessProbe()

    def test_construction_never_touches_the_filesystem_or_a_process(self) -> None:
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            VmrunVMwareKaliHostReadinessProbe()

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_missing_vmrun_executable_fails_closed(self) -> None:
        self.fixture.write_vmx()
        with patch("subprocess.run") as run:
            readiness = self.probe.readiness(self.fixture.requirement())

        run.assert_not_called()
        self.assertIs(
            readiness.state,
            ResearchVMwareKaliHostReadinessState.VMRUN_EXECUTABLE_MISSING,
        )
        self.assertFalse(readiness.host_ready)

    def test_missing_vmx_fails_closed(self) -> None:
        self.fixture.write_vmrun()
        with patch("subprocess.run") as run:
            readiness = self.probe.readiness(self.fixture.requirement())

        run.assert_not_called()
        self.assertIs(readiness.state, ResearchVMwareKaliHostReadinessState.VMX_MISSING)

    def test_vmx_identity_mismatch_fails_closed(self) -> None:
        self.fixture.write_vmrun()
        self.fixture.write_vmx(display_name="Some Other VM")
        with patch("subprocess.run") as run:
            readiness = self.probe.readiness(self.fixture.requirement())

        run.assert_not_called()
        self.assertIs(
            readiness.state,
            ResearchVMwareKaliHostReadinessState.VM_IDENTITY_MISMATCH,
        )

    def test_vmx_with_no_display_name_at_all_fails_closed_as_mismatch(self) -> None:
        self.fixture.write_vmrun()
        Path(self.fixture.vmx_path).write_text(
            '.encoding = "UTF-8"\n', encoding="utf-8"
        )
        readiness = self.probe.readiness(self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliHostReadinessState.VM_IDENTITY_MISMATCH,
        )

    def test_a_decoy_key_sharing_the_displayname_prefix_is_never_accepted(
        self,
    ) -> None:
        """A key like `displayNameExtra` is not `displayName`: the probe must
        match the exact key, never merely a case-insensitive prefix.
        """
        self.fixture.write_vmrun()
        Path(self.fixture.vmx_path).write_text(
            f'.encoding = "UTF-8"\n'
            f'displayNameExtra = "{VM_IDENTITY}"\n'
            f'displayNameBackup = "{VM_IDENTITY}"\n',
            encoding="utf-8",
        )
        readiness = self.probe.readiness(self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliHostReadinessState.VM_IDENTITY_MISMATCH,
        )

    def test_vm_not_in_running_list_is_not_execution_ready(self) -> None:
        self.fixture.write_vmrun()
        self.fixture.write_vmx()
        completed = _completed(
            stdout="Total running VMs: 1\nC:\\VMs\\other\\other.vmx\n"
        )
        with (
            patch("subprocess.run", return_value=completed) as run,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            readiness = self.probe.readiness(self.fixture.requirement())

        getaddrinfo.assert_not_called()
        self.assertIs(
            readiness.state, ResearchVMwareKaliHostReadinessState.VM_NOT_RUNNING
        )
        self.assertFalse(readiness.host_ready)
        run.assert_called_once_with(
            (self.fixture.vmrun_path, "-T", "ws", "list"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            shell=False,
            timeout=5.0,
            check=False,
        )

    def test_host_ready_only_when_the_exact_configured_vmx_is_running(self) -> None:
        self.fixture.write_vmrun()
        self.fixture.write_vmx()
        completed = _completed(
            stdout=f"Total running VMs: 1\n{self.fixture.vmx_path}\n"
        )
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(self.fixture.requirement())

        self.assertIs(readiness.state, ResearchVMwareKaliHostReadinessState.HOST_READY)
        self.assertTrue(readiness.host_ready)
        self.assertFalse(readiness.guest_execution_verified)

    def test_host_ready_despite_case_slash_and_whitespace_differences(self) -> None:
        """A regression in `_normalized_windows_path` back to a plain
        identity comparison must be caught: vmrun's own output commonly
        differs from the configured path only in case, slash style, or
        trailing whitespace, and that must still resolve to HOST_READY.
        """
        self.fixture.write_vmrun()
        self.fixture.write_vmx()
        varied_path = self.fixture.vmx_path.upper().replace("\\", "/") + "  "
        completed = _completed(stdout=f"Total running VMs: 1\n{varied_path}\n")
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(self.fixture.requirement())

        self.assertIs(readiness.state, ResearchVMwareKaliHostReadinessState.HOST_READY)
        self.assertTrue(readiness.host_ready)

    def test_malformed_vmrun_output_fails_closed(self) -> None:
        self.fixture.write_vmrun()
        self.fixture.write_vmx()
        completed = _completed(stdout="not the expected header at all\n")
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliHostReadinessState.HOST_INSPECTION_FAILED,
        )

    def test_nonzero_exit_code_fails_closed(self) -> None:
        self.fixture.write_vmrun()
        self.fixture.write_vmx()
        completed = _completed(
            stdout=f"Total running VMs: 1\n{self.fixture.vmx_path}\n", returncode=1
        )
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliHostReadinessState.HOST_INSPECTION_FAILED,
        )

    def test_timeout_fails_closed(self) -> None:
        self.fixture.write_vmrun()
        self.fixture.write_vmx()
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="vmrun", timeout=5.0),
        ):
            readiness = self.probe.readiness(self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliHostReadinessState.HOST_INSPECTION_FAILED,
        )

    def test_oserror_fails_closed(self) -> None:
        self.fixture.write_vmrun()
        self.fixture.write_vmx()
        with patch("subprocess.run", side_effect=OSError("boom")):
            readiness = self.probe.readiness(self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliHostReadinessState.HOST_INSPECTION_FAILED,
        )

    def test_the_only_subprocess_call_is_a_read_only_list_never_power_or_guest(
        self,
    ) -> None:
        """Across every reachable branch, the one and only vmrun invocation
        is `-T ws list`. There is no code path to `start`, `stop`,
        `runProgramInGuest`, a guest credential argument, a shell, or open
        stdin.
        """
        self.fixture.write_vmrun()
        self.fixture.write_vmx()
        completed = _completed(
            stdout=f"Total running VMs: 1\n{self.fixture.vmx_path}\n"
        )
        with patch("subprocess.run", return_value=completed) as run:
            self.probe.readiness(self.fixture.requirement())

        self.assertEqual(run.call_count, 1)
        args, kwargs = run.call_args
        self.assertEqual(args[0], (self.fixture.vmrun_path, "-T", "ws", "list"))
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        forbidden = ("start", "stop", "runprograminguest", "-gu", "-gp", "reset")
        joined = " ".join(args[0]).lower()
        for term in forbidden:
            self.assertNotIn(term, joined)

    def test_oversized_vmx_content_is_bounded_before_parsing(self) -> None:
        self.fixture.write_vmrun()
        huge_prefix = "x" * (MAX_VMX_FILE_BYTES + 1000)
        Path(self.fixture.vmx_path).write_text(
            huge_prefix + f'\ndisplayName = "{VM_IDENTITY}"\n', encoding="utf-8"
        )
        # The real displayName line is pushed past the bounded read window,
        # so this must fail closed as a mismatch, never crash and never
        # silently scan the whole adversarial file.
        readiness = self.probe.readiness(self.fixture.requirement())

        self.assertIs(
            readiness.state,
            ResearchVMwareKaliHostReadinessState.VM_IDENTITY_MISMATCH,
        )

    def test_oversized_vmrun_list_output_is_bounded(self) -> None:
        self.fixture.write_vmrun()
        self.fixture.write_vmx()
        huge = "Total running VMs: 1\n" + ("y" * 100000) + "\n" + self.fixture.vmx_path
        completed = _completed(stdout=huge)
        with patch("subprocess.run", return_value=completed):
            readiness = self.probe.readiness(self.fixture.requirement())

        # Bounded truncation means the real match line may fall outside the
        # retained window; either way nothing unbounded is retained.
        self.assertLessEqual(
            sum(len(line) for line in readiness.observed_running_vmx_paths),
            4000,
        )

    def test_never_calls_socket_getaddrinfo(self) -> None:
        self.fixture.write_vmrun()
        self.fixture.write_vmx()
        completed = _completed(
            stdout=f"Total running VMs: 1\n{self.fixture.vmx_path}\n"
        )
        with (
            patch("subprocess.run", return_value=completed),
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            self.probe.readiness(self.fixture.requirement())

        getaddrinfo.assert_not_called()


if __name__ == "__main__":
    unittest.main()
