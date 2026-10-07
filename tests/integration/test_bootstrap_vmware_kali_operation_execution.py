"""Production bootstrap installs VMware Kali DNS execution only by full,
explicit, consistent opt-in -- never by any single flag alone, never by a
malformed or ambiguous transport selection, and never with a process or
network effect at construction time. WSL/Kali behavior is unaffected by
every VMware-only configuration combination exercised here.
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
from core.Exceptions import ContainerError, ResearchError
from core.RuntimeOptIn import (
    KALI_OPERATION_EXECUTION_ENABLED_VARIABLE,
    KALI_OPERATION_TRANSPORT_VARIABLE,
    VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE,
    VMWARE_KALI_HOST_READINESS_ENABLED_VARIABLE,
)
from research.VmwareKaliOperationProcessAdapter import (
    VmwareKaliOperationProcessAdapter,
)
from research.VmwareKaliRuntimeProbe import VmwareKaliRuntimeProbe
from research.WslKaliOperationProcessAdapter import WslKaliOperationProcessAdapter
from research.WslKaliRuntimeProbe import WslKaliRuntimeProbe

_VALID_VMWARE_CONFIG = {
    "HYPATIA_VMWARE_KALI_VMRUN_PATH": r"C:\Program Files\VMware\vmrun.exe",
    "HYPATIA_VMWARE_KALI_VMX_PATH": r"D:\VMs\kali.vmx",
    "HYPATIA_VMWARE_KALI_VM_IDENTITY": "kali linux",
    "HYPATIA_VMWARE_KALI_SSH_PATH": r"C:\Windows\System32\OpenSSH\ssh.exe",
    "HYPATIA_VMWARE_KALI_PRIVATE_KEY_PATH": (
        r"C:\Users\hypatia\.ssh\hypatia_guest_ed25519"
    ),
    "HYPATIA_VMWARE_KALI_KNOWN_HOSTS_PATH": (
        r"C:\Users\hypatia\.ssh\hypatia_known_hosts"
    ),
    "HYPATIA_VMWARE_KALI_GUEST_USER": "hypatia-probe",
    "HYPATIA_VMWARE_KALI_GUEST_HOST": "192.168.206.128",
}


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


class BootstrapVmwareKaliOperationExecutionTests(unittest.TestCase):
    def test_default_environment_installs_only_wsl_types(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                    KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "true",
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
                bootstrap.container.resolve(WslKaliRuntimeProbe), WslKaliRuntimeProbe
            )
            self.assertIsInstance(
                bootstrap.container.resolve(WslKaliOperationProcessAdapter),
                WslKaliOperationProcessAdapter,
            )
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmwareKaliRuntimeProbe)
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmwareKaliOperationProcessAdapter)

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_vmware_transport_without_host_or_guest_readiness_installs_nothing(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                    KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "true",
                    KALI_OPERATION_TRANSPORT_VARIABLE: "vmware_kali",
                    **_VALID_VMWARE_CONFIG,
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

            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmwareKaliRuntimeProbe)
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmwareKaliOperationProcessAdapter)
            # Nor does an unconfigured VMware transport fall back to WSL.
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(WslKaliRuntimeProbe)
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(WslKaliOperationProcessAdapter)

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_host_readiness_opt_in_alone_does_not_enable_vmware_execution(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                    KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "true",
                    KALI_OPERATION_TRANSPORT_VARIABLE: "vmware_kali",
                    VMWARE_KALI_HOST_READINESS_ENABLED_VARIABLE: "true",
                    **_VALID_VMWARE_CONFIG,
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

            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmwareKaliRuntimeProbe)
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmwareKaliOperationProcessAdapter)

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_guest_readiness_opt_in_alone_does_not_enable_vmware_execution(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                    KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "true",
                    KALI_OPERATION_TRANSPORT_VARIABLE: "vmware_kali",
                    VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE: "true",
                    **_VALID_VMWARE_CONFIG,
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

            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmwareKaliRuntimeProbe)
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmwareKaliOperationProcessAdapter)

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_full_opt_in_and_valid_config_installs_vmware_types_without_process(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                    KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "true",
                    KALI_OPERATION_TRANSPORT_VARIABLE: "vmware_kali",
                    VMWARE_KALI_HOST_READINESS_ENABLED_VARIABLE: "true",
                    VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE: "true",
                    **_VALID_VMWARE_CONFIG,
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
                bootstrap.container.resolve(VmwareKaliRuntimeProbe),
                VmwareKaliRuntimeProbe,
            )
            self.assertIsInstance(
                bootstrap.container.resolve(VmwareKaliOperationProcessAdapter),
                VmwareKaliOperationProcessAdapter,
            )
            # Installing VMware execution never also installs WSL execution.
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(WslKaliRuntimeProbe)
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(WslKaliOperationProcessAdapter)

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_wsl_transport_with_vmware_readiness_opt_ins_still_installs_wsl(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                    KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "true",
                    VMWARE_KALI_HOST_READINESS_ENABLED_VARIABLE: "true",
                    VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE: "true",
                    **_VALID_VMWARE_CONFIG,
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
                bootstrap.container.resolve(WslKaliRuntimeProbe), WslKaliRuntimeProbe
            )
            self.assertIsInstance(
                bootstrap.container.resolve(WslKaliOperationProcessAdapter),
                WslKaliOperationProcessAdapter,
            )
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmwareKaliRuntimeProbe)
            with self.assertRaises(ContainerError):
                bootstrap.container.resolve(VmwareKaliOperationProcessAdapter)

        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_invalid_transport_configuration_fails_closed(self) -> None:
        for bad_value in ("VMWARE_KALI", "docker_kali", " vmware_kali", ""):
            with self.subTest(bad_value=bad_value):
                with (
                    tempfile.TemporaryDirectory() as temporary_directory,
                    patch.dict(
                        os.environ,
                        {
                            "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                            KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "true",
                            KALI_OPERATION_TRANSPORT_VARIABLE: bad_value,
                        },
                        clear=True,
                    ),
                    patch("subprocess.run") as run,
                    patch("subprocess.Popen") as popen,
                    patch("socket.getaddrinfo") as getaddrinfo,
                ):
                    with self.assertRaises(ResearchError):
                        _bootstrap(Path(temporary_directory))
                run.assert_not_called()
                popen.assert_not_called()
                getaddrinfo.assert_not_called()

    def test_vmware_opt_in_with_incomplete_host_config_fails_closed(self) -> None:
        incomplete_config = dict(_VALID_VMWARE_CONFIG)
        del incomplete_config["HYPATIA_VMWARE_KALI_VMX_PATH"]
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                    KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "true",
                    KALI_OPERATION_TRANSPORT_VARIABLE: "vmware_kali",
                    VMWARE_KALI_HOST_READINESS_ENABLED_VARIABLE: "true",
                    VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE: "true",
                    **incomplete_config,
                },
                clear=True,
            ),
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            with self.assertRaises(ResearchError):
                _bootstrap(Path(temporary_directory))
        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_vmware_opt_in_with_incomplete_guest_config_fails_closed(self) -> None:
        incomplete_config = dict(_VALID_VMWARE_CONFIG)
        del incomplete_config["HYPATIA_VMWARE_KALI_PRIVATE_KEY_PATH"]
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.dict(
                os.environ,
                {
                    "HYPATIA_RESEARCH_SOURCE_DISCOVERY_PROVIDER": "disabled",
                    KALI_OPERATION_EXECUTION_ENABLED_VARIABLE: "true",
                    KALI_OPERATION_TRANSPORT_VARIABLE: "vmware_kali",
                    VMWARE_KALI_HOST_READINESS_ENABLED_VARIABLE: "true",
                    VMWARE_KALI_GUEST_READINESS_ENABLED_VARIABLE: "true",
                    **incomplete_config,
                },
                clear=True,
            ),
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            with self.assertRaises(ResearchError):
                _bootstrap(Path(temporary_directory))
        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()


if __name__ == "__main__":
    unittest.main()
