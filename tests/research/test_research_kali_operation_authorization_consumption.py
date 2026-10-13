"""The shared exact-authorization-matching primitive, in isolation.

`research.ResearchKaliOperationAuthorizationConsumption` was extracted from
`cognition.KaliToolGateway`'s own inline `AUTHORIZATION`-stage logic so both
the existing WSL/VMware dispatch gate and the new Guest-Agent host
authorization handoff (v0.3.463) share exactly one definition of "does this
authorization exactly match this preview." These tests exercise the shared
functions directly; `tests/cognition/test_kali_tool_gateway.py` and
`tests/cognition/test_kali_tool_gateway_vmware_transport.py` remain the
regression proof that the gateway's own behavior is unchanged after the
extraction.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError  # noqa: E402
from research.ResearchKaliOperationAuthorization import (  # noqa: E402
    ResearchKaliOperationAuthorization,
)
from research.ResearchKaliOperationAuthorizationConsumption import (  # noqa: E402
    authorizations_excluding,
    find_exact_kali_operation_authorization,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchDnsRecordType,
    ResearchKaliCommandTransport,
    ResearchKaliOperationKind,
    ResearchKaliOperationPreview,
)
from research.ResearchProgramScopeExecutionPolicy import (  # noqa: E402
    ResearchProgramScopeCheckClass,
)

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


def _preview(**overrides: object) -> ResearchKaliOperationPreview:
    base: dict[str, object] = dict(
        program_id="prog-1",
        scope_revision_id="scope-1",
        scope_revision_digest="d" * 10,
        execution_policy_digest="p" * 10,
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        check_class=ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP,
        hostname="example.com",
        dns_record_type=ResearchDnsRecordType.A,
        resolved_address=None,
        permitted_ports=(443,),
        max_request_count=1,
        max_requests_per_minute=1,
        max_seconds=5.0,
        created_at=NOW,
        transport=ResearchKaliCommandTransport.WSL_KALI,
    )
    base.update(overrides)
    return ResearchKaliOperationPreview(**base)  # type: ignore[arg-type]


def _authorize(
    preview: ResearchKaliOperationPreview,
    *,
    authorization_id: str = "auth-1",
    authorized_at: datetime = NOW,
) -> ResearchKaliOperationAuthorization:
    return ResearchKaliOperationAuthorization.for_preview(
        authorization_id=authorization_id, preview=preview, authorized_at=authorized_at
    )


class FindExactAuthorizationTests(unittest.TestCase):
    def test_exact_valid_match_is_returned(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        found = find_exact_kali_operation_authorization(
            [authorization], "auth-1", preview, now=NOW
        )
        self.assertIs(found, authorization)

    def test_missing_authorization_fails_closed(self) -> None:
        preview = _preview()
        with self.assertRaises(ResearchError):
            find_exact_kali_operation_authorization([], "auth-1", preview, now=NOW)

    def test_duplicate_authorization_identity_fails_closed(self) -> None:
        preview = _preview()
        one = _authorize(preview, authorization_id="auth-1")
        two = _authorize(preview, authorization_id="auth-1")
        with self.assertRaises(ResearchError):
            find_exact_kali_operation_authorization(
                [one, two], "auth-1", preview, now=NOW
            )

    def test_expired_authorization_fails_closed(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        past_expiry = authorization.expires_at + timedelta(seconds=1)
        with self.assertRaises(ResearchError):
            find_exact_kali_operation_authorization(
                [authorization], "auth-1", preview, now=past_expiry
            )

    def test_operation_digest_mismatch_fails_closed(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        other_preview = _preview(hostname="other.example.com")
        with self.assertRaises(ResearchError):
            find_exact_kali_operation_authorization(
                [authorization], "auth-1", other_preview, now=NOW
            )

    def _authorization_with_matching_digest_but(
        self, preview: ResearchKaliOperationPreview, **stale_bindings: str
    ) -> ResearchKaliOperationAuthorization:
        """An authorization whose digest matches `preview` exactly (so the
        digest check alone cannot explain a failure) but whose other
        binding field(s) are deliberately stale -- isolating exactly the
        one binding check under test from the digest check above it."""
        base = _authorize(preview)
        fields = {
            "authorization_id": base.authorization_id,
            "operation_digest": base.operation_digest,
            "program_id": base.program_id,
            "scope_revision_id": base.scope_revision_id,
            "scope_revision_digest": base.scope_revision_digest,
            "execution_policy_digest": base.execution_policy_digest,
            "authorized_at": base.authorized_at,
            "expires_at": base.expires_at,
        }
        fields.update(stale_bindings)
        return ResearchKaliOperationAuthorization(**fields)  # type: ignore[arg-type]

    def test_program_id_mismatch_fails_closed(self) -> None:
        preview = _preview()
        authorization = self._authorization_with_matching_digest_but(
            preview, program_id="prog-stale"
        )
        with self.assertRaises(ResearchError):
            find_exact_kali_operation_authorization(
                [authorization], authorization.authorization_id, preview, now=NOW
            )

    def test_scope_revision_id_mismatch_fails_closed(self) -> None:
        preview = _preview()
        authorization = self._authorization_with_matching_digest_but(
            preview, scope_revision_id="scope-stale"
        )
        with self.assertRaises(ResearchError):
            find_exact_kali_operation_authorization(
                [authorization], authorization.authorization_id, preview, now=NOW
            )

    def test_scope_revision_digest_mismatch_fails_closed(self) -> None:
        preview = _preview()
        authorization = self._authorization_with_matching_digest_but(
            preview, scope_revision_digest="e" * 10
        )
        with self.assertRaises(ResearchError):
            find_exact_kali_operation_authorization(
                [authorization], authorization.authorization_id, preview, now=NOW
            )

    def test_execution_policy_digest_mismatch_fails_closed(self) -> None:
        preview = _preview()
        authorization = self._authorization_with_matching_digest_but(
            preview, execution_policy_digest="q" * 10
        )
        with self.assertRaises(ResearchError):
            find_exact_kali_operation_authorization(
                [authorization], authorization.authorization_id, preview, now=NOW
            )

    def test_authorization_id_match_is_exact_not_prefix(self) -> None:
        preview = _preview()
        authorization = _authorize(preview, authorization_id="auth-1")
        with self.assertRaises(ResearchError):
            find_exact_kali_operation_authorization(
                [authorization], "auth-1-extra", preview, now=NOW
            )
        with self.assertRaises(ResearchError):
            find_exact_kali_operation_authorization(
                [authorization], "auth", preview, now=NOW
            )


class AuthorizationsExcludingTests(unittest.TestCase):
    def test_removes_exactly_the_matched_record(self) -> None:
        preview = _preview()
        authorization = _authorize(preview, authorization_id="auth-1")
        remaining = authorizations_excluding([authorization], authorization)
        self.assertEqual(remaining, [])

    def test_unrelated_records_remain_unchanged(self) -> None:
        preview = _preview()
        target = _authorize(preview, authorization_id="auth-1")
        other_preview = _preview(hostname="other.example.com")
        other = _authorize(other_preview, authorization_id="auth-2")
        remaining = authorizations_excluding([target, other], target)
        self.assertEqual(remaining, [other])

    def test_input_list_is_not_mutated(self) -> None:
        preview = _preview()
        authorization = _authorize(preview, authorization_id="auth-1")
        original = [authorization]
        authorizations_excluding(original, authorization)
        self.assertEqual(original, [authorization])


if __name__ == "__main__":
    unittest.main()
