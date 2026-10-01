"""The gateway distinguishes a pre-dispatch refusal from an unknown outcome.

An adapter exception after authorization consumption must never be reported
as though nothing happened, must never restore the consumed authorization,
and must never be retried. Request metadata is untrusted and must not be
able to assert a gateway stage or an authorization-consumption claim.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.KaliOperationPreviewApplicationService import (
    KaliOperationPreviewApplicationService,
)
from cognition.KaliToolGateway import KaliToolGateway
from core.Exceptions import ResearchError
from research.JsonFileResearchKaliOperationAuthorizationStore import (
    JsonFileResearchKaliOperationAuthorizationStore,
)
from research.KaliToolGatewayFailure import KaliToolGatewayError, KaliToolGatewayStage
from research.ResearchKaliOperationAuthorization import (
    ResearchKaliOperationAuthorization,
)
from research.ResearchKaliOperationExecution import ResearchKaliOperationProcessResult
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
    ResearchKaliOperationPreview,
)
from research.ResearchKaliRuntimeEnvironment import (
    ResearchKaliRuntimeReadiness,
    ResearchKaliRuntimeReadinessState,
    ResearchKaliRuntimeRequirement,
)
from response.ResponseComposer import ResponseComposer
from tests.cognition.test_kali_operation_preview_application_service import (
    FakeProgramScopeRevisionStore,
    revision_fixture,
)

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


class ReadyRuntimeProbe:
    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready
        self.calls: list[ResearchKaliRuntimeRequirement] = []

    def readiness(
        self, requirement: ResearchKaliRuntimeRequirement
    ) -> ResearchKaliRuntimeReadiness:
        self.calls.append(requirement)
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


class RecordingAuthorizationStore:
    """An in-memory store whose save() can be made to fail on demand."""

    def __init__(
        self,
        authorizations: list[ResearchKaliOperationAuthorization] | None = None,
        *,
        save_error: Exception | None = None,
    ) -> None:
        self._authorizations = list(authorizations or [])
        self._save_error = save_error
        self.save_calls: list[list[ResearchKaliOperationAuthorization]] = []
        self.load_calls = 0

    def load(self) -> list[ResearchKaliOperationAuthorization]:
        self.load_calls += 1
        return list(self._authorizations)

    def save(self, authorizations: list[ResearchKaliOperationAuthorization]) -> None:
        self.save_calls.append(list(authorizations))
        if self._save_error is not None:
            raise self._save_error
        self._authorizations = list(authorizations)


class RecordingProcessAdapter:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[object, float]] = []

    def run(self, command_plan, *, timeout_seconds: float):
        self.calls.append((command_plan, timeout_seconds))
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


def _preview_for(
    previews: KaliOperationPreviewApplicationService,
    revision,
    *,
    hostname: str = "www.example.test",
) -> ResearchKaliOperationPreview:
    return previews.preview_for_request(
        BrainRequest(
            message="preview",
            metadata={
                "program_id": revision.program_id,
                "scope_revision_id": revision.revision_id,
                "scope_revision_digest": revision.revision_digest,
                "kali_operation_kind": (
                    ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                ),
                "hostname": hostname,
                "dns_record_type": ResearchDnsRecordType.A.value,
            },
        )
    )


def _authorize(
    preview: ResearchKaliOperationPreview,
    *,
    authorization_id: str = "auth-1",
    authorized_at: datetime = NOW,
) -> ResearchKaliOperationAuthorization:
    return ResearchKaliOperationAuthorization.for_preview(
        authorization_id=authorization_id,
        preview=preview,
        authorized_at=authorized_at,
    )


def _run_request(
    preview: ResearchKaliOperationPreview,
    authorization: ResearchKaliOperationAuthorization,
    *,
    extra_metadata: dict[str, object] | None = None,
) -> BrainRequest:
    metadata: dict[str, object] = {
        "operator_opt_in": True,
        "program_id": preview.program_id,
        "scope_revision_id": preview.scope_revision_id,
        "scope_revision_digest": preview.scope_revision_digest,
        "kali_operation_kind": preview.operation_kind.value,
        "hostname": preview.hostname,
        "dns_record_type": ResearchDnsRecordType.A.value,
        "operation_digest": preview.operation_digest,
        "authorization_id": authorization.authorization_id,
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return BrainRequest(message="run", metadata=metadata)


class KaliToolGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.revision = revision_fixture()
        self.scope_store = FakeProgramScopeRevisionStore([self.revision])
        self.previews = KaliOperationPreviewApplicationService(
            ResponseComposer(), self.scope_store, clock=lambda: NOW
        )
        self.preview = _preview_for(self.previews, self.revision)
        self.authorization = _authorize(self.preview)

    def _gateway(
        self,
        *,
        authorization_store,
        process_adapter,
        runtime_probe=None,
    ) -> KaliToolGateway:
        return KaliToolGateway(
            self.previews,
            authorization_store,
            runtime_probe or ReadyRuntimeProbe(),
            process_adapter,
            clock=lambda: NOW,
        )

    def _process_result(self) -> ResearchKaliOperationProcessResult:
        return ResearchKaliOperationProcessResult(
            command_plan=self.preview.command_plan,
            exit_code=0,
            stdout_lines=("192.0.2.10",),
        )

    # 1. A failed authorization-store save must never invoke the adapter.
    def test_a_failed_authorization_store_save_never_invokes_the_adapter(self) -> None:
        store = RecordingAuthorizationStore(
            [self.authorization], save_error=OSError("disk full")
        )
        adapter = RecordingProcessAdapter(result=self._process_result())
        gateway = self._gateway(authorization_store=store, process_adapter=adapter)

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(_run_request(self.preview, self.authorization))

        self.assertEqual(adapter.calls, [])
        failure = caught.exception.failure
        self.assertIs(failure.stage, KaliToolGatewayStage.AUTHORIZATION_CONSUMPTION)
        self.assertEqual(
            failure.authorization_consumption,
            "unknown; persistence did not confirm completion",
        )
        self.assertFalse(failure.adapter_invoked)

    # 2. An adapter error must not restore consumed authorization.
    def test_an_adapter_error_does_not_restore_consumed_authorization(self) -> None:
        store = RecordingAuthorizationStore([self.authorization])
        adapter = RecordingProcessAdapter(error=ResearchError("adapter exploded"))
        gateway = self._gateway(authorization_store=store, process_adapter=adapter)

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(_run_request(self.preview, self.authorization))

        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(store.load(), [])
        failure = caught.exception.failure
        self.assertIs(failure.stage, KaliToolGatewayStage.DISPATCH)
        self.assertEqual(failure.authorization_consumption, "consumed")
        self.assertTrue(failure.adapter_invoked)

    # 3. A possible side effect must never be reported as though nothing
    #    happened: the composed message must not claim "not started"/"not
    #    created" once the adapter has actually been invoked.
    def test_a_dispatch_stage_failure_is_never_rendered_as_nothing_happened(
        self,
    ) -> None:
        store = RecordingAuthorizationStore([self.authorization])
        adapter = RecordingProcessAdapter(error=OSError("socket reset"))
        gateway = self._gateway(authorization_store=store, process_adapter=adapter)

        try:
            gateway.run(_run_request(self.preview, self.authorization))
            self.fail("expected KaliToolGatewayError")
        except KaliToolGatewayError as error:
            failure = error.failure
            composed = ResponseComposer().kali_operation_run_failure(
                _run_request(self.preview, self.authorization),
                str(error),
                gateway_failure=failure,
            )

        self.assertFalse(composed.success)
        self.assertNotIn("Execution: not started", composed.message)
        self.assertNotIn("Process: not created", composed.message)
        self.assertIn("Kali operation outcome unknown", composed.message)
        self.assertIn("Do not assume nothing happened", composed.message)
        self.assertIs(composed.kali_tool_gateway_failure, failure)

    # 4. A second call with the same authorization never dispatches again,
    #    including when a separate service/store instance reloads from the
    #    same durable file (e.g. after a restart).
    def test_second_call_with_same_authorization_never_dispatches_again(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kali-operation-authorizations.json"
            store_a = JsonFileResearchKaliOperationAuthorizationStore(path)
            store_a.save([self.authorization])
            adapter_a = RecordingProcessAdapter(result=self._process_result())
            gateway_a = self._gateway(
                authorization_store=store_a, process_adapter=adapter_a
            )

            result = gateway_a.run(_run_request(self.preview, self.authorization))
            self.assertEqual(len(adapter_a.calls), 1)
            self.assertIsNotNone(result)

            # A separate store instance reloading the same durable file (as
            # a fresh process/service instance would after a restart).
            store_b = JsonFileResearchKaliOperationAuthorizationStore(path)
            self.assertEqual(store_b.load(), [])
            adapter_b = RecordingProcessAdapter(result=self._process_result())
            gateway_b = self._gateway(
                authorization_store=store_b, process_adapter=adapter_b
            )

            with self.assertRaises(KaliToolGatewayError) as caught:
                gateway_b.run(_run_request(self.preview, self.authorization))

            self.assertEqual(adapter_b.calls, [])
            self.assertIs(
                caught.exception.failure.stage, KaliToolGatewayStage.AUTHORIZATION
            )

    # 5. Scope, policy, preview digest, authorization expiry and runtime
    #    refusals each produce an accurate, pre-dispatch failure stage.
    def test_invalid_digest_fails_at_request_stage(self) -> None:
        store = RecordingAuthorizationStore([self.authorization])
        adapter = RecordingProcessAdapter(result=self._process_result())
        gateway = self._gateway(authorization_store=store, process_adapter=adapter)
        request = _run_request(
            self.preview, self.authorization, extra_metadata={"operation_digest": "x"}
        )

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(request)

        self.assertIs(caught.exception.failure.stage, KaliToolGatewayStage.REQUEST)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(store.save_calls, [])

    def test_digest_mismatch_with_current_preview_fails_at_scope_policy_stage(
        self,
    ) -> None:
        store = RecordingAuthorizationStore([self.authorization])
        adapter = RecordingProcessAdapter(result=self._process_result())
        gateway = self._gateway(authorization_store=store, process_adapter=adapter)
        request = _run_request(
            self.preview,
            self.authorization,
            extra_metadata={"operation_digest": "0" * 64},
        )

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(request)

        self.assertIs(caught.exception.failure.stage, KaliToolGatewayStage.SCOPE_POLICY)
        self.assertEqual(adapter.calls, [])

    def test_out_of_scope_hostname_fails_at_scope_policy_stage(self) -> None:
        store = RecordingAuthorizationStore([self.authorization])
        adapter = RecordingProcessAdapter(result=self._process_result())
        gateway = self._gateway(authorization_store=store, process_adapter=adapter)
        request = _run_request(
            self.preview,
            self.authorization,
            extra_metadata={"hostname": "admin.example.test"},
        )

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(request)

        self.assertIs(caught.exception.failure.stage, KaliToolGatewayStage.SCOPE_POLICY)
        self.assertEqual(adapter.calls, [])

    def test_missing_authorization_record_fails_at_authorization_stage(self) -> None:
        store = RecordingAuthorizationStore([])
        adapter = RecordingProcessAdapter(result=self._process_result())
        gateway = self._gateway(authorization_store=store, process_adapter=adapter)

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(_run_request(self.preview, self.authorization))

        self.assertIs(
            caught.exception.failure.stage, KaliToolGatewayStage.AUTHORIZATION
        )
        self.assertEqual(adapter.calls, [])

    def test_expired_authorization_fails_at_authorization_stage(self) -> None:
        expired = _authorize(self.preview, authorized_at=NOW - timedelta(minutes=10))
        store = RecordingAuthorizationStore([expired])
        adapter = RecordingProcessAdapter(result=self._process_result())
        gateway = self._gateway(authorization_store=store, process_adapter=adapter)

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(_run_request(self.preview, expired))

        self.assertIs(
            caught.exception.failure.stage, KaliToolGatewayStage.AUTHORIZATION
        )
        self.assertEqual(adapter.calls, [])

    def test_stale_authorization_binding_fails_at_authorization_stage(self) -> None:
        # Same operation digest (passes the digest check) but a scope
        # revision id that no longer matches the current preview's — the
        # shape a revoked/rotated scope revision would produce.
        forged = ResearchKaliOperationAuthorization(
            authorization_id=self.authorization.authorization_id,
            operation_digest=self.preview.operation_digest,
            program_id=self.preview.program_id,
            scope_revision_id="scope-revision-rotated",
            scope_revision_digest=self.preview.scope_revision_digest,
            execution_policy_digest=self.preview.execution_policy_digest,
            authorized_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
        )
        store = RecordingAuthorizationStore([forged])
        adapter = RecordingProcessAdapter(result=self._process_result())
        gateway = self._gateway(authorization_store=store, process_adapter=adapter)

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(_run_request(self.preview, forged))

        self.assertIs(
            caught.exception.failure.stage, KaliToolGatewayStage.AUTHORIZATION
        )
        self.assertEqual(adapter.calls, [])

    def test_runtime_not_ready_fails_at_runtime_readiness_stage(self) -> None:
        store = RecordingAuthorizationStore([self.authorization])
        adapter = RecordingProcessAdapter(result=self._process_result())
        gateway = self._gateway(
            authorization_store=store,
            process_adapter=adapter,
            runtime_probe=ReadyRuntimeProbe(ready=False),
        )

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(_run_request(self.preview, self.authorization))

        self.assertIs(
            caught.exception.failure.stage, KaliToolGatewayStage.RUNTIME_READINESS
        )
        self.assertEqual(adapter.calls, [])
        # Readiness refusal is pre-consumption: the authorization survives.
        self.assertEqual(store.load(), [self.authorization])

    # 6. An invalid adapter result must never become accepted evidence or a
    #    successful operation result.
    def test_an_invalid_adapter_result_is_reported_as_unknown_not_success(
        self,
    ) -> None:
        store = RecordingAuthorizationStore([self.authorization])
        # Swap in a result bound to a *different* command plan than the one
        # dispatched, which ResearchKaliOperationRun's own validation rejects.
        other_preview = _preview_for(
            self.previews, self.revision, hostname="other.example.test"
        )
        adapter = RecordingProcessAdapter(
            result=ResearchKaliOperationProcessResult(
                command_plan=other_preview.command_plan,
                exit_code=0,
                stdout_lines=("203.0.113.5",),
            )
        )
        gateway = self._gateway(authorization_store=store, process_adapter=adapter)

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(_run_request(self.preview, self.authorization))

        self.assertEqual(len(adapter.calls), 1)
        failure = caught.exception.failure
        self.assertIs(failure.stage, KaliToolGatewayStage.DISPATCH)
        self.assertTrue(failure.adapter_invoked)

    # 7. Request metadata / model-controlled input cannot supply a trusted
    #    gateway stage or authorization-consumption claim.
    def test_forged_metadata_cannot_assert_a_trusted_stage_or_consumption(
        self,
    ) -> None:
        store = RecordingAuthorizationStore([self.authorization])
        adapter = RecordingProcessAdapter(result=self._process_result())
        gateway = self._gateway(authorization_store=store, process_adapter=adapter)
        # No opt-in: a real refusal at the REQUEST stage. The forged fields
        # must have no bearing on the stage or consumption state reported.
        request = BrainRequest(
            message="run",
            metadata={
                "operator_opt_in": False,
                "program_id": self.preview.program_id,
                "scope_revision_id": self.preview.scope_revision_id,
                "scope_revision_digest": self.preview.scope_revision_digest,
                "kali_operation_kind": self.preview.operation_kind.value,
                "hostname": self.preview.hostname,
                "dns_record_type": ResearchDnsRecordType.A.value,
                "operation_digest": self.preview.operation_digest,
                "authorization_id": self.authorization.authorization_id,
                "kali_tool_gateway_stage": "dispatch",
                "gateway_failure": "dispatch",
                "authorization_consumption": "consumed",
            },
        )

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(request)

        failure = caught.exception.failure
        self.assertIs(failure.stage, KaliToolGatewayStage.REQUEST)
        self.assertEqual(
            failure.authorization_consumption, "not attempted by this call"
        )
        self.assertFalse(failure.adapter_invoked)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(store.save_calls, [])


if __name__ == "__main__":
    unittest.main()
