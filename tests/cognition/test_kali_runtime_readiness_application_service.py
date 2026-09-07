"""Kali runtime readiness is opt-in, inert and fail-closed."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.KaliRuntimeReadinessApplicationService import (
    KALI_RUNTIME_READINESS_INTENT,
    KaliRuntimeReadinessApplicationService,
)
from core.Exceptions import ResearchError
from research.ResearchKaliRuntimeEnvironment import (
    ResearchKaliRuntimeReadiness,
    ResearchKaliRuntimeReadinessState,
    ResearchKaliRuntimeRequirement,
)
from research.WslKaliRuntimeProbe import WslKaliRuntimeProbe
from response.ResponseComposer import ResponseComposer


class FakeReadyKaliRuntimeProbe:
    def __init__(self) -> None:
        self.calls = 0

    def readiness(
        self,
        requirement: ResearchKaliRuntimeRequirement,
    ) -> ResearchKaliRuntimeReadiness:
        self.calls += 1
        return ResearchKaliRuntimeReadiness(
            requirement=requirement,
            state=ResearchKaliRuntimeReadinessState.READY,
            reason="Reviewed fake runtime facts match.",
            observed_distribution=requirement.distribution,
            observed_executable_path=requirement.executable_path,
            observed_version=f"{requirement.version_prefix}18.36",
        )


class KaliRuntimeReadinessApplicationServiceTests(unittest.TestCase):
    def request(self, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="check Kali readiness",
            metadata={
                "intent": KALI_RUNTIME_READINESS_INTENT,
                **metadata,
            },
        )

    def test_readiness_is_explicit_structured_intent_only(self) -> None:
        request = self.request(operator_opt_in=True)
        self.assertTrue(
            KaliRuntimeReadinessApplicationService.is_readiness_request(request)
        )
        self.assertFalse(
            KaliRuntimeReadinessApplicationService.is_readiness_request(
                BrainRequest(
                    message="use kali terminal",
                    metadata={"intent": "message", "operator_opt_in": True},
                )
            )
        )

    def test_missing_operator_opt_in_refuses_before_probe_or_process(self) -> None:
        probe = FakeReadyKaliRuntimeProbe()
        service = KaliRuntimeReadinessApplicationService(
            ResponseComposer(),
            probe=probe,
        )

        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            response = service.process_readiness(self.request())

        self.assertFalse(response.success)
        self.assertIsNone(response.kali_runtime_readiness)
        self.assertIn("requires explicit opt-in", response.message)
        self.assertEqual(probe.calls, 0)
        getaddrinfo.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

    def test_default_probe_fails_closed_without_process_or_network(self) -> None:
        service = KaliRuntimeReadinessApplicationService(ResponseComposer())

        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            response = service.process_readiness(self.request(operator_opt_in=True))

        self.assertFalse(response.success)
        self.assertIsNotNone(response.kali_runtime_readiness)
        self.assertIn("probe is not configured", response.message)
        self.assertIn("Process: not created", response.message)
        self.assertIn("Network/DNS: not used", response.message)
        getaddrinfo.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

    def test_fake_ready_probe_reports_reviewed_requirements_without_process(
        self,
    ) -> None:
        probe = FakeReadyKaliRuntimeProbe()
        service = KaliRuntimeReadinessApplicationService(
            ResponseComposer(),
            probe=probe,
        )

        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            response = service.process_readiness(self.request(operator_opt_in=True))

        self.assertTrue(response.success, response.message)
        readiness = response.kali_runtime_readiness
        assert readiness is not None
        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.requirement.distribution, "kali-linux")
        self.assertEqual(readiness.requirement.executable_path, "/usr/bin/dig")
        self.assertEqual(readiness.requirement.version_prefix, "DiG 9.")
        self.assertFalse(readiness.process_created)
        self.assertFalse(readiness.network_used)
        self.assertIn("Execution: not started", response.message)
        self.assertIn("Process: not created", response.message)
        self.assertIn("Network/DNS: not used", response.message)
        getaddrinfo.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

    def test_wsl_probe_uses_fixed_version_argv_without_shell_or_target_dns(
        self,
    ) -> None:
        completed = subprocess.CompletedProcess(
            args=(),
            returncode=0,
            stdout="DiG 9.18.36-1-Debian\n",
            stderr="",
        )
        service = KaliRuntimeReadinessApplicationService(
            ResponseComposer(),
            probe=WslKaliRuntimeProbe(
                wsl_executable_path=r"C:\Windows\System32\wsl.exe"
            ),
        )

        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run", return_value=completed) as run,
            patch("subprocess.Popen") as popen,
        ):
            response = service.process_readiness(self.request(operator_opt_in=True))

        self.assertTrue(response.success, response.message)
        run.assert_called_once_with(
            (
                r"C:\Windows\System32\wsl.exe",
                "-d",
                "kali-linux",
                "--",
                "/usr/bin/dig",
                "-v",
            ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            shell=False,
            timeout=5.0,
            check=False,
        )
        self.assertIn("State: ready", response.message)
        self.assertIn("Observed version: DiG 9.18.36-1-Debian", response.message)
        getaddrinfo.assert_not_called()
        popen.assert_not_called()

    def test_wsl_probe_refuses_nonzero_or_wrong_version(self) -> None:
        cases = (
            (
                subprocess.CompletedProcess(
                    args=(),
                    returncode=1,
                    stdout="",
                    stderr="distribution not found",
                ),
                "non-zero exit code",
            ),
            (
                subprocess.CompletedProcess(
                    args=(),
                    returncode=0,
                    stdout="unexpected tool 1.0",
                    stderr="",
                ),
                "version did not match",
            ),
        )
        for completed, expected in cases:
            with self.subTest(expected=expected):
                service = KaliRuntimeReadinessApplicationService(
                    ResponseComposer(),
                    probe=WslKaliRuntimeProbe(
                        wsl_executable_path=r"C:\Windows\System32\wsl.exe"
                    ),
                )

                with (
                    patch("socket.getaddrinfo") as getaddrinfo,
                    patch("subprocess.run", return_value=completed),
                    patch("subprocess.Popen") as popen,
                ):
                    response = service.process_readiness(
                        self.request(operator_opt_in=True)
                    )

                self.assertFalse(response.success)
                self.assertIn(expected, response.message)
                self.assertIn("Process: not created", response.message)
                self.assertIn("Network/DNS: not used", response.message)
                getaddrinfo.assert_not_called()
                popen.assert_not_called()

    def test_wsl_probe_rejects_unreviewed_launcher_or_timeout(self) -> None:
        for kwargs in (
            {"wsl_executable_path": "wsl.exe"},
            {"wsl_executable_path": r"C:\Windows\System32\bash.exe"},
            {"timeout_seconds": 30.0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ResearchError):
                    WslKaliRuntimeProbe(**kwargs)


if __name__ == "__main__":
    unittest.main()
