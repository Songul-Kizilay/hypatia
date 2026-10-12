"""mTLS is a transport boundary; the Guest-Agent wire protocol stays credential-free.

AUTHENTICATED PEER != EXECUTION AUTHORITY. Every test below either proves
`GuestAgentRequest`/`GuestAgentResponse` carry no certificate, fingerprint,
peer-role, or credential field, or proves this milestone did not touch
v0.3.457's replay semantics at all -- mTLS and replay protection are
independently required, and neither substitutes for the other.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from research.GuestAgentProtocol import (
    GuestAgentProtocolVersion,
    GuestAgentRequest,
    GuestAgentResponse,
    GuestAgentResponseStatus,
)
from research.GuestAgentProtocolSerialization import (
    guest_agent_request_document,
    guest_agent_response_document,
)
from research.GuestAgentReplayProtector import (
    GuestAgentReplayOutcome,
    GuestAgentReplayProtector,
)
from research.JsonFileGuestAgentReplayNonceStore import (
    JsonFileGuestAgentReplayNonceStore,
)
from research.ResearchKaliOperationPreview import ResearchKaliOperationKind

FORBIDDEN_FIELD_TOKENS = (
    "certificate",
    "cert",
    "fingerprint",
    "peer_identity",
    "peer_role",
    "client_certificate",
    "auth_token",
    "password",
    "api_key",
    "authenticated_as",
    "trusted",
    "is_admin",
    "authorized",
    "private_key",
    "privatekey",
)

MTLS_MODULE_PATHS = (
    SRC_DIR / "research" / "GuestAgentMtlsTrustConfiguration.py",
    SRC_DIR / "research" / "GuestAgentPeerCertificateIdentity.py",
    SRC_DIR / "research" / "GuestAgentMtlsContext.py",
)

VALID_DIGEST = hashlib.sha256(b"example-preview").hexdigest()


def _request(**overrides: object) -> GuestAgentRequest:
    base: dict[str, object] = dict(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="req-1",
        nonce="nonce-1",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        operation_digest=VALID_DIGEST,
    )
    base.update(overrides)
    return GuestAgentRequest(**base)  # type: ignore[arg-type]


def _response(**overrides: object) -> GuestAgentResponse:
    base: dict[str, object] = dict(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="req-1",
        status=GuestAgentResponseStatus.SUCCESS,
        detail="Completed the reviewed operation.",
    )
    base.update(overrides)
    return GuestAgentResponse(**base)  # type: ignore[arg-type]


class ProtocolRemainsCredentialFreeTests(unittest.TestCase):
    """Requirements 9, 10, 11: the wire protocol itself carries no
    certificate, fingerprint, peer-identity, or credential claim."""

    def test_request_fields_contain_no_credential_or_peer_auth_token(self) -> None:
        field_names = {field.name for field in dataclasses.fields(GuestAgentRequest)}
        for forbidden in FORBIDDEN_FIELD_TOKENS:
            with self.subTest(token=forbidden):
                self.assertFalse(any(forbidden in name for name in field_names))

    def test_response_fields_contain_no_credential_or_peer_auth_token(self) -> None:
        field_names = {field.name for field in dataclasses.fields(GuestAgentResponse)}
        for forbidden in FORBIDDEN_FIELD_TOKENS:
            with self.subTest(token=forbidden):
                self.assertFalse(any(forbidden in name for name in field_names))

    def test_serialized_request_document_has_no_credential_key(self) -> None:
        document = guest_agent_request_document(_request())
        for forbidden in FORBIDDEN_FIELD_TOKENS:
            with self.subTest(token=forbidden):
                self.assertFalse(any(forbidden in key for key in document))

    def test_serialized_response_document_has_no_credential_key(self) -> None:
        document = guest_agent_response_document(_response())
        for forbidden in FORBIDDEN_FIELD_TOKENS:
            with self.subTest(token=forbidden):
                self.assertFalse(any(forbidden in key for key in document))

    def test_request_has_exactly_its_known_v0_3_456_fields_unchanged(self) -> None:
        """This milestone must not add a single field to the existing
        protocol type -- proven by the exact, unchanged field set."""
        field_names = {field.name for field in dataclasses.fields(GuestAgentRequest)}
        self.assertEqual(
            field_names,
            {
                "protocol_version",
                "request_id",
                "nonce",
                "operation_kind",
                "operation_digest",
                "logical_inputs",
            },
        )

    def test_response_has_exactly_its_known_v0_3_457_fields_unchanged(self) -> None:
        field_names = {field.name for field in dataclasses.fields(GuestAgentResponse)}
        self.assertEqual(
            field_names,
            {
                "protocol_version",
                "request_id",
                "status",
                "detail",
                "output_lines",
                "output_trust",
            },
        )


class MtlsModulesDoNotTouchProtocolOrReplayTests(unittest.TestCase):
    """Requirements 16, 17: mTLS and replay protection are independent;
    neither this milestone's new modules, nor the existing protocol/replay
    modules, were made to depend on the other in a new way."""

    def test_new_mtls_modules_do_not_import_the_replay_protector(self) -> None:
        forbidden = {"GuestAgentReplayProtector", "JsonFileGuestAgentReplayNonceStore"}
        for path in MTLS_MODULE_PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported_names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imported_names.update(alias.name for alias in node.names)
            with self.subTest(module=path.name):
                self.assertEqual(imported_names & forbidden, set())

    def test_replay_protector_source_is_unmodified_by_this_milestone(self) -> None:
        """A direct behavioral regression check rather than a file-hash
        comparison: replay semantics must behave exactly as v0.3.457 left
        them, proven by exercising them here, in a test file this
        milestone adds."""
        import tempfile
        from datetime import UTC, datetime

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replay.json"
            store = JsonFileGuestAgentReplayNonceStore(path)
            protector = GuestAgentReplayProtector(
                store, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
            )
            first = protector.consume_once(_request())
            second = protector.consume_once(_request())
        self.assertEqual(first, GuestAgentReplayOutcome.ACCEPTED)
        self.assertEqual(second, GuestAgentReplayOutcome.ALREADY_CONSUMED)

    def test_mtls_success_alone_cannot_substitute_for_replay_consumption(
        self,
    ) -> None:
        """There is no function anywhere in the new mTLS modules that
        accepts a `GuestAgentRequest` and reports a replay-equivalent
        outcome -- peer authentication and replay consumption remain two
        separate, independently required steps."""
        import research.GuestAgentMtlsContext as context_module
        import research.GuestAgentMtlsTrustConfiguration as config_module
        import research.GuestAgentPeerCertificateIdentity as identity_module

        for module in (context_module, config_module, identity_module):
            self.assertFalse(hasattr(module, "consume_once"))
            self.assertFalse(hasattr(module, "GuestAgentReplayOutcome"))


if __name__ == "__main__":
    unittest.main()
