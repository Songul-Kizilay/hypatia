"""Kali operation approvals bind to exact inert preview digests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.KaliOperationAuthorizationApplicationService import (
    KALI_OPERATION_AUTHORIZATION_INTENT,
    KaliOperationAuthorizationApplicationService,
)
from cognition.KaliOperationFakeRunnerApplicationService import (
    KALI_OPERATION_FAKE_RUN_INTENT,
    KaliOperationFakeRunnerApplicationService,
)
from cognition.KaliOperationPreviewApplicationService import (
    KaliOperationPreviewApplicationService,
)
from cognition.KaliOperationRunApplicationService import (
    KALI_OPERATION_RUN_INTENT,
    KaliOperationRunApplicationService,
)
from core.Exceptions import ResearchError
from research.JsonFileResearchKaliOperationAuthorizationStore import (
    JsonFileResearchKaliOperationAuthorizationStore,
)
from research.ResearchKaliOperationExecution import (
    ResearchKaliOperationProcessResult,
)
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
)
from research.ResearchKaliRuntimeEnvironment import (
    ResearchKaliRuntimeReadiness,
    ResearchKaliRuntimeReadinessState,
    ResearchKaliRuntimeRequirement,
)
from response.ResponseComposer import ResponseComposer
from tests.cognition.test_kali_operation_preview_application_service import (
    NOW,
    FakeProgramScopeRevisionStore,
    revision_fixture,
)

AUTH_TIME = datetime(2026, 9, 7, 12, 1, tzinfo=UTC)


class FailingKaliOperationAuthorizationStore:
    def __init__(self) -> None:
        self.load_calls = 0
        self.save_calls = 0

    def load(self) -> list[object]:
        self.load_calls += 1
        return []

    def save(self, authorizations: list[object]) -> None:
        self.save_calls += 1
        raise ResearchError("no write")


class ReadyKaliRuntimeProbe:
    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready
        self.calls = 0
        self.requirements: list[ResearchKaliRuntimeRequirement] = []

    def readiness(
        self,
        requirement: ResearchKaliRuntimeRequirement,
    ) -> ResearchKaliRuntimeReadiness:
        self.calls += 1
        self.requirements.append(requirement)
        return ResearchKaliRuntimeReadiness(
            requirement=requirement,
            state=(
                ResearchKaliRuntimeReadinessState.READY
                if self.ready
                else ResearchKaliRuntimeReadinessState.UNAVAILABLE
            ),
            reason="ready" if self.ready else "not ready",
            observed_distribution=requirement.distribution if self.ready else None,
            observed_executable_path=(
                requirement.executable_path if self.ready else None
            ),
            observed_version=(
                f"{requirement.version_prefix}18.36" if self.ready else None
            ),
        )


class RecordingKaliProcessAdapter:
    def __init__(self) -> None:
        self.calls = 0
        self.timeout_seconds: float | None = None

    def run(self, command_plan, *, timeout_seconds: float):
        self.calls += 1
        self.timeout_seconds = timeout_seconds
        return ResearchKaliOperationProcessResult(
            command_plan=command_plan,
            exit_code=0,
            stdout_lines=("192.0.2.10",),
        )


class KaliOperationAuthorizationApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.revision = revision_fixture()
        self.store = FakeProgramScopeRevisionStore([self.revision])
        self.preview_service = KaliOperationPreviewApplicationService(
            ResponseComposer(),
            self.store,
            clock=lambda: NOW,
        )
        self.service = KaliOperationAuthorizationApplicationService(
            ResponseComposer(),
            self.preview_service,
            clock=lambda: AUTH_TIME,
            id_factory=lambda: "kali-auth-1",
        )

    def request(self, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="authorize Kali operation",
            metadata={
                "intent": KALI_OPERATION_AUTHORIZATION_INTENT,
                "program_id": "program-a",
                "scope_revision_id": self.revision.revision_id,
                "scope_revision_digest": self.revision.revision_digest,
                "kali_operation_kind": (
                    ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                ),
                "hostname": "www.example.test.",
                "dns_record_type": ResearchDnsRecordType.A.value,
                **metadata,
            },
        )

    def fake_run_request(self, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="fake run Kali operation",
            metadata={
                "intent": KALI_OPERATION_FAKE_RUN_INTENT,
                "program_id": "program-a",
                "scope_revision_id": self.revision.revision_id,
                "scope_revision_digest": self.revision.revision_digest,
                "kali_operation_kind": (
                    ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                ),
                "hostname": "www.example.test.",
                "dns_record_type": ResearchDnsRecordType.A.value,
                **metadata,
            },
        )

    def run_request(self, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="run Kali operation",
            metadata={
                "intent": KALI_OPERATION_RUN_INTENT,
                "program_id": "program-a",
                "scope_revision_id": self.revision.revision_id,
                "scope_revision_digest": self.revision.revision_digest,
                "kali_operation_kind": (
                    ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                ),
                "hostname": "www.example.test.",
                "dns_record_type": ResearchDnsRecordType.A.value,
                **metadata,
            },
        )

    def digest_for_request(self, **metadata: object) -> str:
        preview = self.preview_service.preview_for_request(self.request(**metadata))
        return preview.operation_digest

    def test_https_header_run_checks_curl_readiness_and_uses_curl_plan(self) -> None:
        digest = self.digest_for_request(
            kali_operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP.value
        )
        authorization_response = self.service.process_authorization(
            self.request(
                kali_operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP.value,
                operation_digest=digest,
            )
        )
        authorization = authorization_response.kali_operation_authorization
        assert authorization is not None
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        store = JsonFileResearchKaliOperationAuthorizationStore(
            Path(temporary_directory.name) / "authorizations.json"
        )
        store.save([authorization])
        probe = ReadyKaliRuntimeProbe()
        adapter = RecordingKaliProcessAdapter()
        runner = KaliOperationRunApplicationService(
            ResponseComposer(),
            self.preview_service,
            store,
            probe,
            adapter,
            clock=lambda: AUTH_TIME,
        )

        response = runner.process_run(
            self.run_request(
                operator_opt_in=True,
                kali_operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP.value,
                operation_digest=digest,
                authorization_id=authorization.authorization_id,
            )
        )

        self.assertTrue(response.success, response.message)
        self.assertEqual(probe.calls, 1)
        self.assertEqual(probe.requirements[0].executable_path, "/usr/bin/curl")
        self.assertEqual(probe.requirements[0].version_arguments, ("--version",))
        self.assertEqual(adapter.calls, 1)
        run_result = response.kali_operation_run
        assert run_result is not None
        self.assertEqual(run_result.command_plan.executable_path, "/usr/bin/curl")
        self.assertIn("https://www.example.test/", run_result.command_plan.argv)

    def test_authorization_is_explicit_structured_intent_only(self) -> None:
        self.assertTrue(self.service.is_authorization_request(self.request()))
        self.assertFalse(
            self.service.is_authorization_request(
                BrainRequest(
                    message="yes run dig",
                    metadata={"intent": "message"},
                )
            )
        )

    def test_exact_digest_authorization_is_inert_and_scope_bound(self) -> None:
        digest = self.digest_for_request()
        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            response = self.service.process_authorization(
                self.request(operation_digest=digest)
            )

        self.assertTrue(response.success, response.message)
        authorization = response.kali_operation_authorization
        assert authorization is not None
        self.assertEqual(authorization.authorization_id, "kali-auth-1")
        self.assertEqual(authorization.operation_digest, digest)
        self.assertEqual(authorization.program_id, "program-a")
        self.assertEqual(authorization.scope_revision_id, self.revision.revision_id)
        self.assertEqual(
            authorization.scope_revision_digest,
            self.revision.revision_digest,
        )
        self.assertEqual(
            authorization.execution_policy_digest,
            self.revision.execution_policy_digest,
        )
        self.assertIn("Execution: not started", response.message)
        self.assertIn("Command plan: bound by operation digest", response.message)
        self.assertNotIn("dig ", response.message)
        self.assertNotIn("wsl", response.message.casefold())
        self.assertFalse(self.store.save_calls)
        getaddrinfo.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

    def test_authorization_is_persisted_when_store_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileResearchKaliOperationAuthorizationStore(
                Path(directory) / "kali-operation-authorizations.json"
            )
            service = KaliOperationAuthorizationApplicationService(
                ResponseComposer(),
                self.preview_service,
                authorization_store=store,
                clock=lambda: AUTH_TIME,
                id_factory=lambda: "kali-auth-1",
            )
            digest = self.digest_for_request()

            response = service.process_authorization(
                self.request(operation_digest=digest)
            )

            self.assertTrue(response.success, response.message)
            [authorization] = store.load()
            self.assertEqual(authorization.authorization_id, "kali-auth-1")
            self.assertEqual(authorization.operation_digest, digest)

            restored = KaliOperationAuthorizationApplicationService(
                ResponseComposer(),
                self.preview_service,
                authorization_store=store,
                clock=lambda: AUTH_TIME,
                id_factory=lambda: "kali-auth-2",
            )
            second = restored.process_authorization(
                self.request(operation_digest=digest)
            )
            self.assertTrue(second.success, second.message)
            self.assertEqual(
                [entry.authorization_id for entry in store.load()],
                ["kali-auth-1", "kali-auth-2"],
            )

    def test_store_write_failure_refuses_without_reporting_authorization(
        self,
    ) -> None:
        store = FailingKaliOperationAuthorizationStore()
        service = KaliOperationAuthorizationApplicationService(
            ResponseComposer(),
            self.preview_service,
            authorization_store=store,  # type: ignore[arg-type]
            clock=lambda: AUTH_TIME,
            id_factory=lambda: "kali-auth-1",
        )
        response = service.process_authorization(
            self.request(operation_digest=self.digest_for_request())
        )

        self.assertFalse(response.success)
        self.assertIsNone(response.kali_operation_authorization)
        self.assertIn("could not be recorded", response.message)
        self.assertEqual(store.save_calls, 1)

    def test_digest_mismatch_refuses_before_dns_or_process(self) -> None:
        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.Popen") as popen,
        ):
            response = self.service.process_authorization(
                self.request(operation_digest="0" * 64)
            )
        self.assertFalse(response.success)
        self.assertIsNone(response.kali_operation_authorization)
        self.assertIn("does not match", response.message)
        getaddrinfo.assert_not_called()
        popen.assert_not_called()

    def test_changed_hostname_invalidates_the_preview_digest(self) -> None:
        digest = self.digest_for_request(hostname="www.example.test")
        response = self.service.process_authorization(
            self.request(
                hostname="api.example.test",
                operation_digest=digest,
            )
        )
        self.assertFalse(response.success)
        self.assertIn("does not match", response.message)

    def test_out_of_scope_authorization_refuses_before_dns_or_process(self) -> None:
        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.Popen") as popen,
        ):
            response = self.service.process_authorization(
                self.request(
                    hostname="outside.test",
                    operation_digest="0" * 64,
                )
            )
        self.assertFalse(response.success)
        self.assertIn("outside scope", response.message)
        getaddrinfo.assert_not_called()
        popen.assert_not_called()

    def test_missing_or_invalid_digest_refuses(self) -> None:
        for value in (None, "", "not-a-digest", True):
            with self.subTest(value=value):
                response = self.service.process_authorization(
                    self.request(operation_digest=value)
                )
                self.assertFalse(response.success)
                self.assertIsNone(response.kali_operation_authorization)

    def test_fake_runner_uses_recorded_authorization_without_process_or_dns(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileResearchKaliOperationAuthorizationStore(
                Path(directory) / "kali-operation-authorizations.json"
            )
            authorizer = KaliOperationAuthorizationApplicationService(
                ResponseComposer(),
                self.preview_service,
                authorization_store=store,
                clock=lambda: AUTH_TIME,
                id_factory=lambda: "kali-auth-1",
            )
            digest = self.digest_for_request()
            authorization = authorizer.process_authorization(
                self.request(operation_digest=digest)
            ).kali_operation_authorization
            assert authorization is not None
            runner = KaliOperationFakeRunnerApplicationService(
                ResponseComposer(),
                self.preview_service,
                store,
                clock=lambda: AUTH_TIME,
            )

            with (
                patch("socket.getaddrinfo") as getaddrinfo,
                patch("subprocess.run") as run,
                patch("subprocess.Popen") as popen,
            ):
                response = runner.process_fake_run(
                    self.fake_run_request(
                        authorization_id=authorization.authorization_id,
                        operation_digest=digest,
                    )
                )

            self.assertTrue(response.success, response.message)
            result = response.kali_operation_fake_run
            assert result is not None
            self.assertEqual(result.authorization_id, "kali-auth-1")
            self.assertEqual(result.operation_digest, digest)
            self.assertFalse(result.process_created)
            self.assertFalse(result.network_used)
            self.assertEqual(result.command_plan.argv[0], "/usr/bin/dig")
            self.assertIn("Execution: simulated only", response.message)
            self.assertIn("Process: not created", response.message)
            self.assertIn("Network/DNS: not used", response.message)
            getaddrinfo.assert_not_called()
            run.assert_not_called()
            popen.assert_not_called()

    def test_fake_runner_refuses_missing_expired_or_mismatched_authorization(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileResearchKaliOperationAuthorizationStore(
                Path(directory) / "kali-operation-authorizations.json"
            )
            digest = self.digest_for_request()
            authorizer = KaliOperationAuthorizationApplicationService(
                ResponseComposer(),
                self.preview_service,
                authorization_store=store,
                clock=lambda: AUTH_TIME,
                id_factory=lambda: "kali-auth-1",
            )
            authorizer.process_authorization(self.request(operation_digest=digest))
            cases = (
                (
                    "missing",
                    AUTH_TIME,
                    {"authorization_id": "missing-auth", "operation_digest": digest},
                    "requires one recorded authorization",
                ),
                (
                    "expired",
                    AUTH_TIME + timedelta(seconds=301),
                    {"authorization_id": "kali-auth-1", "operation_digest": digest},
                    "has expired",
                ),
                (
                    "mismatch",
                    AUTH_TIME,
                    {
                        "authorization_id": "kali-auth-1",
                        "operation_digest": digest,
                        "dns_record_type": ResearchDnsRecordType.AAAA.value,
                    },
                    "does not match the preview",
                ),
            )
            for label, moment, metadata, reason in cases:
                with self.subTest(label=label):
                    runner = KaliOperationFakeRunnerApplicationService(
                        ResponseComposer(),
                        self.preview_service,
                        store,
                        clock=lambda moment=moment: moment,
                    )
                    with (
                        patch("socket.getaddrinfo") as getaddrinfo,
                        patch("subprocess.Popen") as popen,
                    ):
                        response = runner.process_fake_run(
                            self.fake_run_request(**metadata)
                        )

                    self.assertFalse(response.success)
                    self.assertIn(reason, response.message)
                    self.assertIsNone(response.kali_operation_fake_run)
                    getaddrinfo.assert_not_called()
                    popen.assert_not_called()

    def test_operation_run_consumes_authorization_before_process_adapter(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileResearchKaliOperationAuthorizationStore(
                Path(directory) / "kali-operation-authorizations.json"
            )
            digest = self.digest_for_request()
            authorizer = KaliOperationAuthorizationApplicationService(
                ResponseComposer(),
                self.preview_service,
                authorization_store=store,
                clock=lambda: AUTH_TIME,
                id_factory=lambda: "kali-auth-1",
            )
            authorization = authorizer.process_authorization(
                self.request(operation_digest=digest)
            ).kali_operation_authorization
            assert authorization is not None
            probe = ReadyKaliRuntimeProbe()
            adapter = RecordingKaliProcessAdapter()
            runner = KaliOperationRunApplicationService(
                ResponseComposer(),
                self.preview_service,
                store,
                probe,
                adapter,
                clock=lambda: AUTH_TIME,
            )

            with (
                patch("socket.getaddrinfo") as getaddrinfo,
                patch("subprocess.run") as run,
                patch("subprocess.Popen") as popen,
            ):
                response = runner.process_run(
                    self.run_request(
                        authorization_id=authorization.authorization_id,
                        operation_digest=digest,
                        operator_opt_in=True,
                    )
                )

            self.assertTrue(response.success, response.message)
            result = response.kali_operation_run
            assert result is not None
            self.assertEqual(result.authorization_id, "kali-auth-1")
            self.assertTrue(result.authorization_consumed)
            self.assertEqual(result.process_result.stdout_lines, ("192.0.2.10",))
            self.assertEqual(store.load(), [])
            self.assertEqual(probe.calls, 1)
            self.assertEqual(adapter.calls, 1)
            self.assertEqual(
                adapter.timeout_seconds, self.revision.execution_policy.max_seconds
            )
            self.assertIn("Authorization ID consumed: kali-auth-1", response.message)
            self.assertIn("Output trust: untrusted process output", response.message)
            self.assertIn("Evidence: not recorded", response.message)
            getaddrinfo.assert_not_called()
            run.assert_not_called()
            popen.assert_not_called()

    def test_operation_run_refuses_before_process_without_opt_in_or_readiness(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileResearchKaliOperationAuthorizationStore(
                Path(directory) / "kali-operation-authorizations.json"
            )
            digest = self.digest_for_request()
            authorizer = KaliOperationAuthorizationApplicationService(
                ResponseComposer(),
                self.preview_service,
                authorization_store=store,
                clock=lambda: AUTH_TIME,
                id_factory=lambda: "kali-auth-1",
            )
            authorization = authorizer.process_authorization(
                self.request(operation_digest=digest)
            ).kali_operation_authorization
            assert authorization is not None
            cases = (
                (
                    "missing opt-in",
                    self.run_request(
                        authorization_id=authorization.authorization_id,
                        operation_digest=digest,
                    ),
                    ReadyKaliRuntimeProbe(),
                    "requires explicit run opt-in",
                ),
                (
                    "runtime unavailable",
                    self.run_request(
                        authorization_id=authorization.authorization_id,
                        operation_digest=digest,
                        operator_opt_in=True,
                    ),
                    ReadyKaliRuntimeProbe(ready=False),
                    "runtime is not ready",
                ),
            )
            for label, request, probe, expected in cases:
                with self.subTest(label=label):
                    adapter = RecordingKaliProcessAdapter()
                    runner = KaliOperationRunApplicationService(
                        ResponseComposer(),
                        self.preview_service,
                        store,
                        probe,
                        adapter,
                        clock=lambda: AUTH_TIME,
                    )
                    with (
                        patch("socket.getaddrinfo") as getaddrinfo,
                        patch("subprocess.Popen") as popen,
                    ):
                        response = runner.process_run(request)

                    self.assertFalse(response.success)
                    self.assertIsNone(response.kali_operation_run)
                    self.assertIn(expected, response.message)
                    self.assertEqual(adapter.calls, 0)
                    self.assertEqual(len(store.load()), 1)
                    getaddrinfo.assert_not_called()
                    popen.assert_not_called()

    def test_operation_run_refuses_missing_authorization_before_runtime_probe(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileResearchKaliOperationAuthorizationStore(
                Path(directory) / "kali-operation-authorizations.json"
            )
            digest = self.digest_for_request()
            probe = ReadyKaliRuntimeProbe()
            adapter = RecordingKaliProcessAdapter()
            runner = KaliOperationRunApplicationService(
                ResponseComposer(),
                self.preview_service,
                store,
                probe,
                adapter,
                clock=lambda: AUTH_TIME,
            )

            with (
                patch("socket.getaddrinfo") as getaddrinfo,
                patch("subprocess.run") as run,
                patch("subprocess.Popen") as popen,
            ):
                response = runner.process_run(
                    self.run_request(
                        authorization_id="missing-auth",
                        operation_digest=digest,
                        operator_opt_in=True,
                    )
                )

            self.assertFalse(response.success)
            self.assertIsNone(response.kali_operation_run)
            self.assertIn(
                "requires one recorded authorization",
                response.message,
            )
            self.assertEqual(probe.calls, 0)
            self.assertEqual(adapter.calls, 0)
            getaddrinfo.assert_not_called()
            run.assert_not_called()
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
