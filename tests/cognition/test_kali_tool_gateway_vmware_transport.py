"""Transport is trusted, code-owned configuration -- never a request choice.

Locks in: a VMware-configured preview service always produces a
VMWARE_KALI-transport DNS preview; the identical logical hostname/record
request produces a *different* operation digest under WSL vs. VMware (so an
authorization for one transport can never be replayed against the other,
and the gateway's existing exact-digest check already refuses the
mismatch); and that nothing in request metadata or the chat message text
can select a transport the preview service was not already configured
with.

The generic gateway mechanics this file does not repeat -- missing/expired
authorization, digest/scope/policy mismatch, consume-before-dispatch,
no-retry, restart not recreating authority -- are already proven
transport-agnostically by `test_kali_tool_gateway.py`, which this change
leaves passing unmodified. This file only exercises what is new: that those
same mechanics hold when the configured transport is VMWARE_KALI, and that
transport selection itself cannot be forged.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
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
from research.KaliToolGatewayFailure import KaliToolGatewayError, KaliToolGatewayStage
from research.ResearchKaliOperationAuthorization import (
    ResearchKaliOperationAuthorization,
)
from research.ResearchKaliOperationExecution import ResearchKaliOperationProcessResult
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliCommandTransport,
    ResearchKaliOperationKind,
)
from research.ResearchKaliRuntimeEnvironment import (
    ResearchKaliRuntimeReadiness,
    ResearchKaliRuntimeReadinessState,
)
from response.ResponseComposer import ResponseComposer
from tests.cognition.test_kali_operation_preview_application_service import (
    FakeProgramScopeRevisionStore,
    revision_fixture,
)

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


class ReadyRuntimeProbe:
    """Always-ready probe that records the exact requirement it was given.

    Recording (not merely accepting) the requirement is what lets a test
    prove `KaliToolGateway._runtime_requirement` actually threads
    `preview.transport` through -- a probe that ignored its argument would
    pass every test below even if the gateway hard-coded the wrong
    transport into the requirement it builds.
    """

    def __init__(self) -> None:
        self.calls: list[object] = []

    def readiness(self, requirement) -> ResearchKaliRuntimeReadiness:  # type: ignore[no-untyped-def]
        self.calls.append(requirement)
        return ResearchKaliRuntimeReadiness(
            requirement=requirement,
            state=ResearchKaliRuntimeReadinessState.READY,
            reason="ready",
            observed_version=f"{requirement.version_prefix}18.36",
        )


class RecordingProcessAdapter:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def run(self, command_plan, *, timeout_seconds: float):  # type: ignore[no-untyped-def]
        self.calls.append(command_plan)
        return ResearchKaliOperationProcessResult(
            command_plan=command_plan, exit_code=0, stdout_lines=("192.0.2.10",)
        )


class RecordingAuthorizationStore:
    def __init__(self, authorizations=None) -> None:  # type: ignore[no-untyped-def]
        self._authorizations = list(authorizations or [])
        self.save_calls: list[object] = []

    def load(self):  # type: ignore[no-untyped-def]
        return list(self._authorizations)

    def save(self, authorizations) -> None:  # type: ignore[no-untyped-def]
        self.save_calls.append(list(authorizations))
        self._authorizations = list(authorizations)


def _request_metadata(revision, *, hostname="www.example.test", **extra):  # type: ignore[no-untyped-def]
    metadata = {
        "program_id": revision.program_id,
        "scope_revision_id": revision.revision_id,
        "scope_revision_digest": revision.revision_digest,
        "kali_operation_kind": ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value,
        "hostname": hostname,
        "dns_record_type": ResearchDnsRecordType.A.value,
    }
    metadata.update(extra)
    return metadata


class VmwareTransportPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.revision = revision_fixture()
        self.scope_store = FakeProgramScopeRevisionStore([self.revision])
        self.wsl_previews = KaliOperationPreviewApplicationService(
            ResponseComposer(), self.scope_store, clock=lambda: NOW
        )
        self.vmware_previews = KaliOperationPreviewApplicationService(
            ResponseComposer(),
            self.scope_store,
            clock=lambda: NOW,
            transport=ResearchKaliCommandTransport.VMWARE_KALI,
        )

    def test_vmware_configured_service_produces_a_vmware_transport_preview(
        self,
    ) -> None:
        preview = self.vmware_previews.preview_for_request(
            BrainRequest(message="preview", metadata=_request_metadata(self.revision))
        )
        self.assertIs(preview.transport, ResearchKaliCommandTransport.VMWARE_KALI)
        self.assertIs(
            preview.command_plan.transport, ResearchKaliCommandTransport.VMWARE_KALI
        )

    def test_default_configured_service_still_produces_wsl_transport(self) -> None:
        preview = self.wsl_previews.preview_for_request(
            BrainRequest(message="preview", metadata=_request_metadata(self.revision))
        )
        self.assertIs(preview.transport, ResearchKaliCommandTransport.WSL_KALI)

    def test_identical_request_has_a_different_digest_per_transport(self) -> None:
        wsl_preview = self.wsl_previews.preview_for_request(
            BrainRequest(message="preview", metadata=_request_metadata(self.revision))
        )
        vmware_preview = self.vmware_previews.preview_for_request(
            BrainRequest(message="preview", metadata=_request_metadata(self.revision))
        )
        self.assertEqual(wsl_preview.hostname, vmware_preview.hostname)
        self.assertEqual(wsl_preview.dns_record_type, vmware_preview.dns_record_type)
        self.assertNotEqual(
            wsl_preview.operation_digest, vmware_preview.operation_digest
        )

    def test_request_metadata_cannot_select_a_transport(self) -> None:
        preview = self.wsl_previews.preview_for_request(
            BrainRequest(
                message="preview",
                metadata=_request_metadata(
                    self.revision,
                    transport="vmware_kali",
                    kali_operation_transport="vmware_kali",
                ),
            )
        )
        self.assertIs(preview.transport, ResearchKaliCommandTransport.WSL_KALI)

    def test_chat_message_text_cannot_select_a_transport(self) -> None:
        preview = self.wsl_previews.preview_for_request(
            BrainRequest(
                message="please run this over vmware_kali transport",
                metadata=_request_metadata(self.revision),
            )
        )
        self.assertIs(preview.transport, ResearchKaliCommandTransport.WSL_KALI)

    def test_constructor_rejects_a_non_enum_transport(self) -> None:
        with self.assertRaises(ResearchError):
            KaliOperationPreviewApplicationService(
                ResponseComposer(),
                self.scope_store,
                transport="vmware_kali",  # type: ignore[arg-type]
            )


class CrossTransportAuthorizationReplayTests(unittest.TestCase):
    """An authorization recorded for one transport can never run the other.

    This already follows from `KaliToolGateway`'s existing exact
    `operation_digest` check (unchanged by this milestone) combined with
    the digest now differing per transport -- this test exists to prove
    that composed property holds end-to-end, not to add a new check.
    """

    def setUp(self) -> None:
        self.revision = revision_fixture()
        self.scope_store = FakeProgramScopeRevisionStore([self.revision])
        self.wsl_previews = KaliOperationPreviewApplicationService(
            ResponseComposer(), self.scope_store, clock=lambda: NOW
        )
        self.vmware_previews = KaliOperationPreviewApplicationService(
            ResponseComposer(),
            self.scope_store,
            clock=lambda: NOW,
            transport=ResearchKaliCommandTransport.VMWARE_KALI,
        )
        self.wsl_preview = self.wsl_previews.preview_for_request(
            BrainRequest(message="preview", metadata=_request_metadata(self.revision))
        )
        self.vmware_preview = self.vmware_previews.preview_for_request(
            BrainRequest(message="preview", metadata=_request_metadata(self.revision))
        )

    def _run_request(self, preview, authorization) -> BrainRequest:  # type: ignore[no-untyped-def]
        return BrainRequest(
            message="run",
            metadata={
                "operator_opt_in": True,
                "program_id": preview.program_id,
                "scope_revision_id": preview.scope_revision_id,
                "scope_revision_digest": preview.scope_revision_digest,
                "kali_operation_kind": preview.operation_kind.value,
                "hostname": preview.hostname,
                "dns_record_type": ResearchDnsRecordType.A.value,
                "operation_digest": authorization.operation_digest,
                "authorization_id": authorization.authorization_id,
            },
        )

    def test_a_wsl_authorization_cannot_run_the_vmware_preview(self) -> None:
        wsl_authorization = ResearchKaliOperationAuthorization.for_preview(
            authorization_id="auth-wsl", preview=self.wsl_preview, authorized_at=NOW
        )
        store = RecordingAuthorizationStore([wsl_authorization])
        adapter = RecordingProcessAdapter()
        gateway = KaliToolGateway(
            self.vmware_previews, store, ReadyRuntimeProbe(), adapter, clock=lambda: NOW
        )

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(self._run_request(self.vmware_preview, wsl_authorization))

        self.assertIs(caught.exception.failure.stage, KaliToolGatewayStage.SCOPE_POLICY)
        self.assertEqual(adapter.calls, [])

    def test_a_vmware_authorization_cannot_run_the_wsl_preview(self) -> None:
        vmware_authorization = ResearchKaliOperationAuthorization.for_preview(
            authorization_id="auth-vmware",
            preview=self.vmware_preview,
            authorized_at=NOW,
        )
        store = RecordingAuthorizationStore([vmware_authorization])
        adapter = RecordingProcessAdapter()
        gateway = KaliToolGateway(
            self.wsl_previews, store, ReadyRuntimeProbe(), adapter, clock=lambda: NOW
        )

        with self.assertRaises(KaliToolGatewayError) as caught:
            gateway.run(self._run_request(self.wsl_preview, vmware_authorization))

        self.assertIs(caught.exception.failure.stage, KaliToolGatewayStage.SCOPE_POLICY)
        self.assertEqual(adapter.calls, [])

    def test_the_matching_vmware_authorization_does_run_the_vmware_preview(
        self,
    ) -> None:
        vmware_authorization = ResearchKaliOperationAuthorization.for_preview(
            authorization_id="auth-vmware",
            preview=self.vmware_preview,
            authorized_at=NOW,
        )
        store = RecordingAuthorizationStore([vmware_authorization])
        adapter = RecordingProcessAdapter()
        runtime_probe = ReadyRuntimeProbe()
        gateway = KaliToolGateway(
            self.vmware_previews,
            store,
            runtime_probe,
            adapter,
            clock=lambda: NOW,
        )

        result = gateway.run(
            self._run_request(self.vmware_preview, vmware_authorization)
        )

        self.assertEqual(len(adapter.calls), 1)
        # Proves `_runtime_requirement` actually threads `preview.transport`
        # through to the probe, rather than defaulting/hard-coding it.
        self.assertEqual(len(runtime_probe.calls), 1)
        self.assertIs(
            runtime_probe.calls[0].transport,
            ResearchKaliCommandTransport.VMWARE_KALI,
        )
        self.assertIs(
            result.command_plan.transport, ResearchKaliCommandTransport.VMWARE_KALI
        )

    def test_the_matching_wsl_authorization_threads_wsl_transport_too(self) -> None:
        wsl_authorization = ResearchKaliOperationAuthorization.for_preview(
            authorization_id="auth-wsl", preview=self.wsl_preview, authorized_at=NOW
        )
        store = RecordingAuthorizationStore([wsl_authorization])
        adapter = RecordingProcessAdapter()
        runtime_probe = ReadyRuntimeProbe()
        gateway = KaliToolGateway(
            self.wsl_previews, store, runtime_probe, adapter, clock=lambda: NOW
        )

        result = gateway.run(self._run_request(self.wsl_preview, wsl_authorization))

        self.assertEqual(len(runtime_probe.calls), 1)
        self.assertIs(
            runtime_probe.calls[0].transport, ResearchKaliCommandTransport.WSL_KALI
        )
        self.assertIs(
            result.command_plan.transport, ResearchKaliCommandTransport.WSL_KALI
        )


if __name__ == "__main__":
    unittest.main()
