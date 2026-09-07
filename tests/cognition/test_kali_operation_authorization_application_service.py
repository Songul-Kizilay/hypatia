"""Kali operation approvals bind to exact inert preview digests."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
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
from cognition.KaliOperationPreviewApplicationService import (
    KaliOperationPreviewApplicationService,
)
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
)
from response.ResponseComposer import ResponseComposer
from tests.cognition.test_kali_operation_preview_application_service import (
    NOW,
    FakeProgramScopeRevisionStore,
    revision_fixture,
)

AUTH_TIME = datetime(2026, 9, 7, 12, 1, tzinfo=UTC)


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

    def digest_for_request(self, **metadata: object) -> str:
        preview = self.preview_service.preview_for_request(self.request(**metadata))
        return preview.operation_digest

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
        self.assertIn("Command line: not constructed", response.message)
        self.assertNotIn("dig ", response.message)
        self.assertNotIn("wsl", response.message.casefold())
        self.assertFalse(self.store.save_calls)
        getaddrinfo.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
