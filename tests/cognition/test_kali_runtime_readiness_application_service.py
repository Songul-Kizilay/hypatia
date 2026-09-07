"""Kali runtime readiness is opt-in, inert and fail-closed."""

from __future__ import annotations

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
from research.ResearchKaliRuntimeEnvironment import (
    ResearchKaliRuntimeReadiness,
    ResearchKaliRuntimeReadinessState,
    ResearchKaliRuntimeRequirement,
)
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


if __name__ == "__main__":
    unittest.main()
