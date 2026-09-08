"""Kali operation previews are inert, scope-bound and policy-bound."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.KaliOperationPreviewApplicationService import (
    KALI_OPERATION_PREVIEW_INTENT,
    KaliOperationPreviewApplicationService,
)
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
    kali_operation_command_plan_document,
    kali_operation_preview_document,
)
from research.ResearchProgramScopeExecutionPolicy import (
    ResearchProgramScopeCheckClass,
    ResearchProgramScopeExecutionPolicy,
)
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from research.ResearchTargetScope import ResearchTargetScope, TargetHostRule
from response.ResponseComposer import ResponseComposer

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


class FakeProgramScopeRevisionStore:
    def __init__(self, revisions: list[ResearchProgramScopeRevision]) -> None:
        self._revisions = revisions
        self.save_calls: list[list[ResearchProgramScopeRevision]] = []

    def load(self) -> list[ResearchProgramScopeRevision]:
        return list(self._revisions)

    def save(self, revisions: list[ResearchProgramScopeRevision]) -> None:
        self.save_calls.append(revisions)
        self._revisions = list(revisions)


def scope_fixture() -> ResearchTargetScope:
    return ResearchTargetScope(
        allowed_hosts=(
            TargetHostRule("example.test"),
            TargetHostRule("example.test", True),
        ),
        excluded_hosts=(TargetHostRule("admin.example.test"),),
    )


def dns_policy() -> ResearchProgramScopeExecutionPolicy:
    return ResearchProgramScopeExecutionPolicy(
        permitted_check_classes=(
            ResearchProgramScopeCheckClass.PUBLIC_HTTPS_CONTENT,
            ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP,
        ),
        permitted_ports=(53, 443),
        max_request_count=2,
        max_requests_per_minute=1,
        max_seconds=30.0,
    )


def revision_fixture(
    *,
    execution_policy: ResearchProgramScopeExecutionPolicy | None = None,
    confirmed_at: datetime = NOW - timedelta(minutes=1),
    expires_at: datetime = NOW + timedelta(minutes=30),
) -> ResearchProgramScopeRevision:
    return ResearchProgramScopeRevision(
        "scope-revision-1",
        "program-a",
        scope_fixture(),
        confirmed_at,
        expires_at,
        execution_policy=execution_policy or dns_policy(),
    )


class KaliOperationPreviewApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.revision = revision_fixture()
        self.store = FakeProgramScopeRevisionStore([self.revision])
        self.service = KaliOperationPreviewApplicationService(
            ResponseComposer(),
            self.store,
            clock=lambda: NOW,
        )

    def request(self, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="preview Kali operation",
            metadata={
                "intent": KALI_OPERATION_PREVIEW_INTENT,
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

    def test_preview_is_explicit_structured_intent_only(self) -> None:
        self.assertTrue(self.service.is_preview_request(self.request()))
        self.assertFalse(
            self.service.is_preview_request(
                BrainRequest(
                    message="run dig example.test",
                    metadata={"intent": "message"},
                )
            )
        )

    def test_dns_lookup_preview_is_inert_scope_bound_and_digest_bound(self) -> None:
        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            response = self.service.process_preview(self.request())

        self.assertTrue(response.success, response.message)
        preview = response.kali_operation_preview
        assert preview is not None
        self.assertEqual(preview.program_id, "program-a")
        self.assertEqual(preview.scope_revision_id, self.revision.revision_id)
        self.assertEqual(preview.scope_revision_digest, self.revision.revision_digest)
        self.assertEqual(
            preview.execution_policy_digest,
            self.revision.execution_policy_digest,
        )
        self.assertEqual(preview.hostname, "www.example.test")
        self.assertEqual(
            preview.check_class, ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP
        )
        self.assertEqual(preview.dns_record_type, ResearchDnsRecordType.A)
        self.assertEqual(preview.permitted_ports, (53, 443))
        self.assertIn("Operation digest:", response.message)
        self.assertIn("Command plan: reviewed argv only", response.message)
        self.assertIn("Executable: /usr/bin/dig", response.message)
        self.assertIn("argv[0]: /usr/bin/dig", response.message)
        self.assertIn("argv[4]: www.example.test", response.message)
        self.assertNotIn("dig ", response.message)
        self.assertFalse(self.store.save_calls)
        getaddrinfo.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

    def test_https_header_lookup_preview_uses_reviewed_curl_argv(self) -> None:
        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
        ):
            response = self.service.process_preview(
                self.request(
                    kali_operation_kind=(
                        ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP.value
                    )
                )
            )

        self.assertTrue(response.success, response.message)
        preview = response.kali_operation_preview
        assert preview is not None
        self.assertEqual(
            preview.operation_kind,
            ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
        )
        self.assertEqual(
            preview.check_class, ResearchProgramScopeCheckClass.PUBLIC_HTTPS_CONTENT
        )
        self.assertIsNone(preview.dns_record_type)
        self.assertEqual(preview.command_plan.executable_path, "/usr/bin/curl")
        self.assertEqual(
            preview.command_plan.argv,
            (
                "/usr/bin/curl",
                "--head",
                "--silent",
                "--show-error",
                "--max-time",
                "10",
                "--proto",
                "=https",
                "https://www.example.test/",
            ),
        )
        self.assertIn("Operation: https_header_lookup", response.message)
        self.assertIn("Check class: public_https_content", response.message)
        self.assertIn("DNS record type: not applicable", response.message)
        self.assertIn("Executable: /usr/bin/curl", response.message)
        self.assertNotIn("curl ", response.message)
        self.assertFalse(preview.command_plan.shell)
        self.assertFalse(self.store.save_calls)
        getaddrinfo.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

    def test_preview_document_contains_reviewed_argv_but_no_command_string(
        self,
    ) -> None:
        response = self.service.process_preview(self.request())
        preview = response.kali_operation_preview
        assert preview is not None
        document = kali_operation_preview_document(preview)
        self.assertNotIn("command", document)
        command_plan = document["command_plan"]
        self.assertIsInstance(command_plan, dict)
        assert isinstance(command_plan, dict)
        self.assertEqual(command_plan["transport"], "wsl_kali")
        self.assertEqual(command_plan["executable_path"], "/usr/bin/dig")
        self.assertEqual(
            command_plan["argv"],
            [
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "www.example.test",
                "A",
            ],
        )
        self.assertIs(command_plan["shell"], False)
        self.assertEqual(command_plan["stdin"], "closed")

    def test_command_plan_is_code_owned_and_digest_bound(self) -> None:
        first = self.service.process_preview(self.request()).kali_operation_preview
        second = self.service.process_preview(
            self.request(dns_record_type=ResearchDnsRecordType.AAAA.value)
        ).kali_operation_preview
        assert first is not None
        assert second is not None
        self.assertEqual(
            kali_operation_command_plan_document(first.command_plan)["argv"],
            [
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "www.example.test",
                "A",
            ],
        )
        self.assertNotEqual(first.operation_digest, second.operation_digest)
        self.assertNotIn("shell", " ".join(first.command_plan.argv).casefold())
        self.assertNotIn("|", first.command_plan.argv)

    def test_policy_without_dns_lookup_refuses_before_dns_or_process(self) -> None:
        self.store = FakeProgramScopeRevisionStore(
            [revision_fixture(execution_policy=ResearchProgramScopeExecutionPolicy())]
        )
        revision = self.store.load()[0]
        self.service = KaliOperationPreviewApplicationService(
            ResponseComposer(),
            self.store,
            clock=lambda: NOW,
        )
        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.Popen") as popen,
        ):
            response = self.service.process_preview(
                self.request(
                    scope_revision_digest=revision.revision_digest,
                )
            )
        self.assertFalse(response.success)
        self.assertIn("does not permit dns_record_lookup", response.message)
        getaddrinfo.assert_not_called()
        popen.assert_not_called()

    def test_policy_without_https_content_or_port_refuses_before_process(
        self,
    ) -> None:
        cases = (
            (
                ResearchProgramScopeExecutionPolicy(
                    permitted_check_classes=(
                        ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP,
                    ),
                    permitted_ports=(53,),
                ),
                "does not permit public_https_content",
            ),
            (
                ResearchProgramScopeExecutionPolicy(
                    permitted_check_classes=(
                        ResearchProgramScopeCheckClass.PUBLIC_HTTPS_CONTENT,
                    ),
                    permitted_ports=(80,),
                ),
                "does not permit HTTPS port 443",
            ),
        )
        for policy, reason in cases:
            with self.subTest(reason=reason):
                self.store = FakeProgramScopeRevisionStore(
                    [revision_fixture(execution_policy=policy)]
                )
                revision = self.store.load()[0]
                self.service = KaliOperationPreviewApplicationService(
                    ResponseComposer(),
                    self.store,
                    clock=lambda: NOW,
                )
                with (
                    patch("socket.getaddrinfo") as getaddrinfo,
                    patch("subprocess.Popen") as popen,
                ):
                    response = self.service.process_preview(
                        self.request(
                            kali_operation_kind=(
                                ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP.value
                            ),
                            scope_revision_digest=revision.revision_digest,
                        )
                    )
                self.assertFalse(response.success)
                self.assertIn(reason, response.message)
                getaddrinfo.assert_not_called()
                popen.assert_not_called()

    def test_out_of_scope_or_excluded_host_refuses_before_dns_or_process(self) -> None:
        for hostname, reason in (
            ("outside.test", "outside scope"),
            ("admin.example.test", "excluded"),
        ):
            with self.subTest(hostname=hostname):
                with (
                    patch("socket.getaddrinfo") as getaddrinfo,
                    patch("subprocess.Popen") as popen,
                ):
                    response = self.service.process_preview(
                        self.request(hostname=hostname)
                    )
                self.assertFalse(response.success)
                self.assertIn(reason, response.message)
                getaddrinfo.assert_not_called()
                popen.assert_not_called()

    def test_revision_mismatch_or_inactive_revision_refuses(self) -> None:
        cases: tuple[tuple[str, dict[str, object], str], ...] = (
            ("digest", {"scope_revision_digest": "0" * 64}, "exact active"),
            ("program", {"program_id": "program-b"}, "exact active"),
            (
                "revoked",
                {
                    "scope_revision_digest": self.revision.revoked(
                        NOW, ResearchAuthorizer.HUMAN
                    ).revision_digest
                },
                "not active",
            ),
        )
        for _label, metadata, reason in cases:
            with self.subTest(metadata=metadata):
                if "revoked" in _label:
                    self.store = FakeProgramScopeRevisionStore(
                        [self.revision.revoked(NOW, ResearchAuthorizer.HUMAN)]
                    )
                    self.service = KaliOperationPreviewApplicationService(
                        ResponseComposer(),
                        self.store,
                        clock=lambda: NOW,
                    )
                response = self.service.process_preview(self.request(**metadata))
                self.assertFalse(response.success)
                self.assertIn(reason, response.message)

    def test_expired_revision_refuses(self) -> None:
        expired = revision_fixture(
            confirmed_at=NOW - timedelta(minutes=20),
            expires_at=NOW - timedelta(minutes=1),
        )
        self.store = FakeProgramScopeRevisionStore([expired])
        self.service = KaliOperationPreviewApplicationService(
            ResponseComposer(),
            self.store,
            clock=lambda: NOW,
        )
        response = self.service.process_preview(
            self.request(scope_revision_digest=expired.revision_digest)
        )
        self.assertFalse(response.success)
        self.assertIn("not active", response.message)

    def test_invalid_operation_or_record_type_refuses(self) -> None:
        for metadata in (
            {"kali_operation_kind": "nmap_scan"},
            {"dns_record_type": "ANY"},
        ):
            with self.subTest(metadata=metadata):
                response = self.service.process_preview(self.request(**metadata))
                self.assertFalse(response.success)
                self.assertIsNone(response.kali_operation_preview)


if __name__ == "__main__":
    unittest.main()
