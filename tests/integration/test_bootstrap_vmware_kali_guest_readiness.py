"""Production bootstrap installs the VMware guest-readiness probe only by
explicit opt-in, independently of every other opt-in, and WSL/host behavior
is completely unaffected either way.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Bootstrap import Bootstrap
from core.Exceptions import ContainerError
from core.RuntimeOptIn import (
    VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE,
    VMWARE_KALI_HOST_READINESS_ENABLED_VARIABLE,
    vmware_kali_guest_readiness_enabled,
)
from research.SshVMwareKaliGuestReadinessProbe import SshVMwareKaliGuestReadinessProbe
from research.VmrunVMwareKaliHostReadinessProbe import VmrunVMwareKaliHostReadinessProbe


def _bootstrap(temporary_path: Path) -> Bootstrap:
    bootstrap = Bootstrap.from_process_environment(
        memory_path=temporary_path / "memory.json",
        session_path=temporary_path / "sessions.json",
        research_run_path=temporary_path / "runs.json",
        research_source_content_path=temporary_path / "content.json",
        research_program_scope_revision_path=(
            temporary_path / "program_scope_revisions.json"
        ),
    )
    bootstrap.initialize()
    return bootstrap


class VmwareKaliGuestReadinessOptInTests(unittest.TestCase):
    def test_opt_in_is_strict(self) -> None:
        self.assertFalse(vmware_kali_guest_readiness_enabled({}))
        self.assertFalse(
            vmware_kali_guest_readiness_enabled(
                {VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE: "True"}
            )
        )
        self.assertFalse(
            vmware_kali_guest_readiness_enabled(
                {VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE: "1"}
            )
        )
        self.assertTrue(
            vmware_kali_guest_readiness_enabled(
                {VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE: "true"}
            )
        )

    def test_default_process_environment_installs_no_guest_probe(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {"HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled"},
                clear=True,
            ),
            patch("core.Bootstrap.HttpResearchSourceFetcher"),
            patch("core.Bootstrap.NvdResearchSourceDiscoveryProvider"),
            patch("core.Bootstrap.NvdResearchSourceFetcher"),
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            bootstrap = _bootstrap(Path(temporary_directory))

            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(SshVMwareKaliGuestReadinessProbe)
            # Host readiness stays unaffected by the guest flag being absent.
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmrunVMwareKaliHostReadinessProbe)

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_enabled_environment_installs_only_the_guest_probe(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                    VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE: "true",
                },
                clear=True,
            ),
            patch("core.Bootstrap.HttpResearchSourceFetcher"),
            patch("core.Bootstrap.NvdResearchSourceDiscoveryProvider"),
            patch("core.Bootstrap.NvdResearchSourceFetcher"),
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            bootstrap = _bootstrap(Path(temporary_directory))

            self.assertIsInstance(
                bootstrap.container.resolve(SshVMwareKaliGuestReadinessProbe),
                SshVMwareKaliGuestReadinessProbe,
            )
            # Enabling guest readiness must not also enable host readiness:
            # the two opt-ins are independent.
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmrunVMwareKaliHostReadinessProbe)

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_enabling_both_vmware_opt_ins_installs_both_independently(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                    VMWARE_KALI_HOST_READINESS_ENABLED_VARIABLE: "true",
                    VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE: "true",
                },
                clear=True,
            ),
            patch("core.Bootstrap.HttpResearchSourceFetcher"),
            patch("core.Bootstrap.NvdResearchSourceDiscoveryProvider"),
            patch("core.Bootstrap.NvdResearchSourceFetcher"),
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            bootstrap = _bootstrap(Path(temporary_directory))

            self.assertIsInstance(
                bootstrap.container.resolve(VmrunVMwareKaliHostReadinessProbe),
                VmrunVMwareKaliHostReadinessProbe,
            )
            self.assertIsInstance(
                bootstrap.container.resolve(SshVMwareKaliGuestReadinessProbe),
                SshVMwareKaliGuestReadinessProbe,
            )

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()


if __name__ == "__main__":
    unittest.main()
