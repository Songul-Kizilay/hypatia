"""Transport is trusted, code-owned configuration bound into the digest.

Locks in: WSL stays the default and unchanged; a different transport for the
same logical operation produces a different digest; an authorization
recorded for one transport can never validate against the other; and
request/model metadata can never select a transport.
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
from core.Exceptions import ResearchError
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliCommandTransport,
    ResearchKaliOperationKind,
    ResearchKaliOperationPreview,
    kali_operation_command_plan,
)
from research.ResearchProgramScopeExecutionPolicy import (
    ResearchProgramScopeCheckClass,
    ResearchProgramScopeExecutionPolicy,
)
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from research.ResearchTargetScope import ResearchTargetScope, TargetHostRule
from response.ResponseComposer import ResponseComposer

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


def preview(
    *, transport: ResearchKaliCommandTransport = ResearchKaliCommandTransport.WSL_KALI
) -> ResearchKaliOperationPreview:
    return ResearchKaliOperationPreview(
        program_id="program-a",
        scope_revision_id="scope-revision-1",
        scope_revision_digest="scope-digest-1",
        execution_policy_digest="policy-digest-1",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        check_class=ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP,
        hostname="www.example.test",
        dns_record_type=ResearchDnsRecordType.A,
        resolved_address=None,
        permitted_ports=(443,),
        max_request_count=1,
        max_requests_per_minute=1,
        max_seconds=10.0,
        created_at=NOW,
        transport=transport,
    )


class ResearchKaliCommandTransportTests(unittest.TestCase):
    def test_wsl_kali_is_still_the_default_transport(self) -> None:
        built = preview()

        self.assertIs(built.transport, ResearchKaliCommandTransport.WSL_KALI)
        self.assertIs(
            built.command_plan.transport, ResearchKaliCommandTransport.WSL_KALI
        )

    def test_wsl_default_digest_is_deterministic_and_matches_explicit_wsl(
        self,
    ) -> None:
        # Not passing `transport` at all (today's every existing caller)
        # must hash identically to passing WSL_KALI explicitly: the default
        # changes nothing about what a WSL preview hashes to.
        implicit_default = preview()
        explicit_wsl = preview(transport=ResearchKaliCommandTransport.WSL_KALI)

        self.assertEqual(
            implicit_default.operation_digest, explicit_wsl.operation_digest
        )

    def test_command_plan_rejects_a_non_enum_transport(self) -> None:
        with self.assertRaises(ResearchError):
            kali_operation_command_plan(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                hostname="www.example.test",
                dns_record_type=ResearchDnsRecordType.A,
                transport="vmware_kali",  # type: ignore[arg-type]
            )

    def test_preview_rejects_a_non_enum_transport(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchKaliOperationPreview(
                program_id="program-a",
                scope_revision_id="scope-revision-1",
                scope_revision_digest="scope-digest-1",
                execution_policy_digest="policy-digest-1",
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                check_class=ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP,
                hostname="www.example.test",
                dns_record_type=ResearchDnsRecordType.A,
                resolved_address=None,
                permitted_ports=(443,),
                max_request_count=1,
                max_requests_per_minute=1,
                max_seconds=10.0,
                created_at=NOW,
                transport="vmware_kali",  # type: ignore[arg-type]
            )

    def test_vmware_and_wsl_bind_the_same_logical_operation_to_different_digests(
        self,
    ) -> None:
        wsl_preview = preview(transport=ResearchKaliCommandTransport.WSL_KALI)
        vmware_preview = preview(transport=ResearchKaliCommandTransport.VMWARE_KALI)

        self.assertNotEqual(
            wsl_preview.operation_digest, vmware_preview.operation_digest
        )
        self.assertEqual(
            wsl_preview.command_plan.argv, vmware_preview.command_plan.argv
        )
        self.assertNotEqual(
            wsl_preview.command_plan.transport, vmware_preview.command_plan.transport
        )

    def test_an_authorization_digest_for_one_transport_never_matches_the_other(
        self,
    ) -> None:
        """Mirrors KaliToolGateway's own `authorization.operation_digest !=
        preview.operation_digest` check: an authorization recorded for a WSL
        preview's digest can never be satisfied by a VMware preview of the
        exact same logical operation, and vice versa.
        """
        wsl_preview = preview(transport=ResearchKaliCommandTransport.WSL_KALI)
        vmware_preview = preview(transport=ResearchKaliCommandTransport.VMWARE_KALI)
        recorded_authorization_digest = wsl_preview.operation_digest

        self.assertNotEqual(
            recorded_authorization_digest, vmware_preview.operation_digest
        )


class _FixedRevisionStore:
    def __init__(self, revisions: list[ResearchProgramScopeRevision]) -> None:
        self._revisions = revisions

    def load(self) -> list[ResearchProgramScopeRevision]:
        return list(self._revisions)


def _scope_fixture() -> ResearchTargetScope:
    return ResearchTargetScope(
        allowed_hosts=(TargetHostRule("example.test"),),
        excluded_hosts=(),
    )


def _dns_policy() -> ResearchProgramScopeExecutionPolicy:
    return ResearchProgramScopeExecutionPolicy(
        permitted_check_classes=(ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP,),
        permitted_ports=(443,),
        max_request_count=1,
        max_requests_per_minute=1,
        max_seconds=10.0,
    )


def _revision_fixture() -> ResearchProgramScopeRevision:
    return ResearchProgramScopeRevision(
        "scope-revision-1",
        "program-a",
        _scope_fixture(),
        NOW - timedelta(minutes=1),
        NOW + timedelta(minutes=30),
        execution_policy=_dns_policy(),
    )


class RequestMetadataCannotSelectTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.response_composer = ResponseComposer()

    def test_transport_in_request_metadata_has_no_effect_on_the_built_preview(
        self,
    ) -> None:
        revision = _revision_fixture()
        service = KaliOperationPreviewApplicationService(
            self.response_composer,
            _FixedRevisionStore([revision]),
            clock=lambda: NOW,
        )
        request = BrainRequest(
            message="preview",
            metadata={
                "intent": "kali_operation_preview",
                "kali_operation_kind": (
                    ResearchKaliOperationKind.DNS_RECORD_LOOKUP.value
                ),
                "hostname": "example.test",
                "program_id": "program-a",
                "scope_revision_id": "scope-revision-1",
                "scope_revision_digest": revision.revision_digest,
                "dns_record_type": ResearchDnsRecordType.A.value,
                # An attacker- or model-supplied transport claim: must be
                # completely inert. This service never reads this key.
                "transport": "vmware_kali",
            },
        )

        built = service.preview_for_request(request)

        self.assertIs(built.transport, ResearchKaliCommandTransport.WSL_KALI)
        self.assertIs(
            built.command_plan.transport, ResearchKaliCommandTransport.WSL_KALI
        )


if __name__ == "__main__":
    unittest.main()
