"""The Guest-Agent host authorization handoff foundation (v0.3.463).

Proves the boundary between "the host's existing scope/preview/
authorization chain consumed an exact human approval" and "the host may
construct exactly one `GuestAgentRequest`." Does NOT prove, and must never
be read as proving, that any capability executes, that replay is
consumed, or that a receiving guest can independently verify host
authorization from the resulting bytes -- see
`research.GuestAgentHostAuthorizationHandoff`'s own module docstring for
why that last gap remains open by design.
"""

from __future__ import annotations

import ast
import sys
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentCore import admit_guest_agent_request  # noqa: E402
from research.GuestAgentHostAuthorizationHandoff import (  # noqa: E402
    _DISPATCH_GRANT_CAPABILITY,
    GuestAgentHostAuthorizationHandoffError,
    GuestAgentHostAuthorizationHandoffStage,
    GuestAgentHostDispatchGrant,
    consume_authorization_for_guest_agent_dispatch,
)
from research.GuestAgentProtocol import (  # noqa: E402
    GuestAgentProtocolVersion,
    GuestAgentResponseStatus,
)
from research.GuestAgentReplayNonceRecord import (  # noqa: E402
    GuestAgentReplayNonceRecord,
)
from research.GuestAgentReplayProtector import (  # noqa: E402
    GuestAgentReplayOutcome,
    GuestAgentReplayProtector,
)
from research.ResearchKaliOperationAuthorization import (  # noqa: E402
    ResearchKaliOperationAuthorization,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchDnsRecordType,
    ResearchKaliCommandTransport,
    ResearchKaliOperationKind,
    ResearchKaliOperationPreview,
)
from research.ResearchKaliRuntimeEnvironment import (  # noqa: E402
    ResearchKaliRuntimeRequirement,
)
from research.ResearchProgramScopeExecutionPolicy import (  # noqa: E402
    ResearchProgramScopeCheckClass,
)
from research.ResearchVMwareKaliGuestReadiness import (  # noqa: E402
    ResearchVMwareKaliGuestTransportRequirement,
)
from research.VmwareKaliOperationProcessAdapter import (  # noqa: E402
    VmwareKaliOperationProcessAdapter,
)
from research.VmwareKaliRuntimeProbe import VmwareKaliRuntimeProbe  # noqa: E402
from research.WslKaliOperationProcessAdapter import (  # noqa: E402
    WslKaliOperationProcessAdapter,
)
from tools.ProductCapabilityCatalogDefaults import (  # noqa: E402
    kali_operation_capability_records,
)
from tools.ProductCapabilitySchemaDefaults import (  # noqa: E402
    kali_operation_schema_records,
)

THIS_FILE = Path(__file__).resolve()
HANDOFF_MODULE_FILE = SRC_DIR / "research" / "GuestAgentHostAuthorizationHandoff.py"
CONSUMPTION_MODULE_FILE = (
    SRC_DIR / "research" / "ResearchKaliOperationAuthorizationConsumption.py"
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
        transport=ResearchKaliCommandTransport.GUEST_AGENT,
    )
    base.update(overrides)
    return ResearchKaliOperationPreview(**base)  # type: ignore[arg-type]


def _https_preview(**overrides: object) -> ResearchKaliOperationPreview:
    base: dict[str, object] = dict(
        operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
        check_class=ResearchProgramScopeCheckClass.PUBLIC_HTTPS_CONTENT,
        dns_record_type=None,
        resolved_address="93.184.216.34",
    )
    base.update(overrides)
    return _preview(**base)  # type: ignore[arg-type]


def _authorize(
    preview: ResearchKaliOperationPreview,
    *,
    authorization_id: str = "auth-1",
    authorized_at: datetime = NOW,
) -> ResearchKaliOperationAuthorization:
    return ResearchKaliOperationAuthorization.for_preview(
        authorization_id=authorization_id, preview=preview, authorized_at=authorized_at
    )


class FakeAuthorizationStore:
    """Mirrors `tests.cognition.test_kali_tool_gateway.RecordingAuthorizationStore`."""

    def __init__(
        self,
        authorizations: list[ResearchKaliOperationAuthorization] | None = None,
        *,
        load_error: Exception | None = None,
        save_error: Exception | None = None,
    ) -> None:
        self._authorizations = list(authorizations or [])
        self._load_error = load_error
        self._save_error = save_error
        self.load_calls = 0
        self.save_calls: list[list[ResearchKaliOperationAuthorization]] = []

    def load(self) -> list[ResearchKaliOperationAuthorization]:
        self.load_calls += 1
        if self._load_error is not None:
            raise self._load_error
        return list(self._authorizations)

    def save(self, authorizations: list[ResearchKaliOperationAuthorization]) -> None:
        self.save_calls.append(list(authorizations))
        if self._save_error is not None:
            raise self._save_error
        self._authorizations = list(authorizations)

    @property
    def current(self) -> list[ResearchKaliOperationAuthorization]:
        return list(self._authorizations)


class TransportBindingTests(unittest.TestCase):
    """Requirements: GUEST_AGENT transport binding; WSL/VMware authorizations
    cannot satisfy a Guest-Agent handoff even with identical other facts."""

    def test_guest_agent_preview_digest_differs_from_wsl_preview(self) -> None:
        guest_preview = _preview(transport=ResearchKaliCommandTransport.GUEST_AGENT)
        wsl_preview = _preview(transport=ResearchKaliCommandTransport.WSL_KALI)
        self.assertNotEqual(
            guest_preview.operation_digest, wsl_preview.operation_digest
        )

    def test_guest_agent_preview_digest_differs_from_vmware_preview(self) -> None:
        guest_preview = _preview(transport=ResearchKaliCommandTransport.GUEST_AGENT)
        vmware_preview = _preview(transport=ResearchKaliCommandTransport.VMWARE_KALI)
        self.assertNotEqual(
            guest_preview.operation_digest, vmware_preview.operation_digest
        )

    def test_wsl_authorization_cannot_satisfy_a_guest_agent_handoff(self) -> None:
        wsl_preview = _preview(transport=ResearchKaliCommandTransport.WSL_KALI)
        authorization = _authorize(wsl_preview)
        store = FakeAuthorizationStore([authorization])
        with self.assertRaises(GuestAgentHostAuthorizationHandoffError) as ctx:
            consume_authorization_for_guest_agent_dispatch(
                store, authorization.authorization_id, wsl_preview, now=NOW
            )
        self.assertIs(
            ctx.exception.failure.stage,
            GuestAgentHostAuthorizationHandoffStage.TRANSPORT_BINDING,
        )
        self.assertEqual(store.current, [authorization])
        self.assertEqual(store.save_calls, [])

    def test_vmware_authorization_cannot_satisfy_a_guest_agent_handoff(self) -> None:
        vmware_preview = _preview(transport=ResearchKaliCommandTransport.VMWARE_KALI)
        authorization = _authorize(vmware_preview)
        store = FakeAuthorizationStore([authorization])
        with self.assertRaises(GuestAgentHostAuthorizationHandoffError) as ctx:
            consume_authorization_for_guest_agent_dispatch(
                store, authorization.authorization_id, vmware_preview, now=NOW
            )
        self.assertIs(
            ctx.exception.failure.stage,
            GuestAgentHostAuthorizationHandoffStage.TRANSPORT_BINDING,
        )
        self.assertEqual(store.current, [authorization])


class ConsumeBeforeGrantOrderingTests(unittest.TestCase):
    """Requirements 1-13: no grant before exact validation and successful
    store consumption; every fail-closed scenario leaves the store and
    the absence of a grant unchanged."""

    def test_missing_authorization_fails_closed(self) -> None:
        preview = _preview()
        store = FakeAuthorizationStore([])
        with self.assertRaises(GuestAgentHostAuthorizationHandoffError) as ctx:
            consume_authorization_for_guest_agent_dispatch(
                store, "auth-1", preview, now=NOW
            )
        self.assertIs(
            ctx.exception.failure.stage,
            GuestAgentHostAuthorizationHandoffStage.AUTHORIZATION,
        )
        self.assertEqual(store.save_calls, [])

    def test_duplicate_authorization_identity_fails_closed(self) -> None:
        preview = _preview()
        one = _authorize(preview, authorization_id="auth-1")
        two = _authorize(preview, authorization_id="auth-1")
        store = FakeAuthorizationStore([one, two])
        with self.assertRaises(GuestAgentHostAuthorizationHandoffError):
            consume_authorization_for_guest_agent_dispatch(
                store, "auth-1", preview, now=NOW
            )
        self.assertEqual(store.save_calls, [])
        self.assertEqual(store.current, [one, two])

    def test_expired_authorization_fails_closed(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        past_expiry = authorization.expires_at + timedelta(seconds=1)
        store = FakeAuthorizationStore([authorization])
        with self.assertRaises(GuestAgentHostAuthorizationHandoffError):
            consume_authorization_for_guest_agent_dispatch(
                store, authorization.authorization_id, preview, now=past_expiry
            )
        self.assertEqual(store.current, [authorization])

    def test_operation_digest_mismatch_fails_closed(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        other_preview = _preview(hostname="other.example.com")
        store = FakeAuthorizationStore([authorization])
        with self.assertRaises(GuestAgentHostAuthorizationHandoffError):
            consume_authorization_for_guest_agent_dispatch(
                store, authorization.authorization_id, other_preview, now=NOW
            )
        self.assertEqual(store.current, [authorization])

    def test_program_scope_and_policy_binding_mismatches_fail_closed(self) -> None:
        preview = _preview()
        for stale_field, stale_value in (
            ("program_id", "prog-stale"),
            ("scope_revision_id", "scope-stale"),
            ("scope_revision_digest", "e" * 10),
            ("execution_policy_digest", "q" * 10),
        ):
            with self.subTest(field=stale_field):
                base = _authorize(preview, authorization_id=f"auth-{stale_field}")
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
                fields[stale_field] = stale_value
                stale_authorization = ResearchKaliOperationAuthorization(**fields)  # type: ignore[arg-type]
                store = FakeAuthorizationStore([stale_authorization])
                with self.assertRaises(GuestAgentHostAuthorizationHandoffError):
                    consume_authorization_for_guest_agent_dispatch(
                        store, stale_authorization.authorization_id, preview, now=NOW
                    )
                self.assertEqual(store.current, [stale_authorization])

    def test_store_read_failure_fails_closed(self) -> None:
        preview = _preview()
        store = FakeAuthorizationStore(load_error=OSError("disk error"))
        with self.assertRaises(GuestAgentHostAuthorizationHandoffError) as ctx:
            consume_authorization_for_guest_agent_dispatch(
                store, "auth-1", preview, now=NOW
            )
        self.assertIs(
            ctx.exception.failure.stage,
            GuestAgentHostAuthorizationHandoffStage.AUTHORIZATION,
        )
        # Hostile/system detail must not leak the raw OSError text.
        self.assertNotIn("disk error", ctx.exception.failure.reason)

    def test_store_save_failure_fails_closed(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization], save_error=OSError("disk full"))
        with self.assertRaises(GuestAgentHostAuthorizationHandoffError) as ctx:
            consume_authorization_for_guest_agent_dispatch(
                store, authorization.authorization_id, preview, now=NOW
            )
        self.assertIs(
            ctx.exception.failure.stage,
            GuestAgentHostAuthorizationHandoffStage.AUTHORIZATION_CONSUMPTION,
        )
        self.assertNotIn("disk full", ctx.exception.failure.reason)

    def test_failed_store_save_leaves_no_usable_dispatch_capability(self) -> None:
        """The function call itself raises -- there is no return value at
        all to misuse, which is the strongest possible proof that a
        failed save cannot leave a usable grant anywhere."""
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore(
            [authorization], save_error=ResearchError("could not persist")
        )
        with self.assertRaises(GuestAgentHostAuthorizationHandoffError):
            result = consume_authorization_for_guest_agent_dispatch(
                store, authorization.authorization_id, preview, now=NOW
            )
            self.fail(f"expected an exception, got a grant: {result!r}")

    def test_grant_construction_is_structurally_outside_the_try_block(self) -> None:
        """A deterministic, AST-based ordering proof -- not a runtime
        traceback inspection. (A runtime check that walks a caught
        exception's `__traceback__`/`__cause__` frames after the `with
        self.assertRaises(...)` block has exited was tried first and
        found unreliable: CPython clears a frame's fast-local slots once
        that frame is no longer live on the call stack, specifically to
        break traceback reference cycles, so `frame.f_locals` can -- and,
        confirmed experimentally, does -- report a local variable as
        absent even though it demonstrably existed at the moment the
        exception was raised. That is a CPython implementation detail of
        exception handling, not the security property under test, so
        relying on it would make this test non-deterministic across
        interpreter versions for reasons unrelated to this module's own
        correctness.)

        Instead, this parses `consume_authorization_for_guest_agent_dispatch`
        itself and proves textually that the only call to
        `GuestAgentHostDispatchGrant(` in its body is a top-level statement
        that comes AFTER the function's `try`/`except` -- never inside the
        `try` block. That is exactly "construct the grant only once
        `authorization_store.save(...)` has already returned normally,"
        made structurally impossible to violate without this test catching
        it, regardless of what any particular failure happens to do to a
        traceback at runtime.
        """
        tree = ast.parse(
            HANDOFF_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(HANDOFF_MODULE_FILE),
        )
        function_node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "consume_authorization_for_guest_agent_dispatch"
        )
        try_statements = [
            statement
            for statement in function_node.body
            if isinstance(statement, ast.Try)
        ]
        self.assertEqual(len(try_statements), 1, "expected exactly one try block")
        try_statement = try_statements[0]

        def _is_grant_call(node: ast.AST) -> bool:
            return (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "GuestAgentHostDispatchGrant"
            )

        for node in ast.walk(try_statement):
            if _is_grant_call(node):
                self.fail(
                    "GuestAgentHostDispatchGrant must never be constructed "
                    "inside the try block, even transiently."
                )

        try_index = function_node.body.index(try_statement)
        after_try_statements = function_node.body[try_index + 1 :]
        found_after_try = any(
            _is_grant_call(node)
            for statement in after_try_statements
            for node in ast.walk(statement)
        )
        self.assertTrue(
            found_after_try,
            "expected the grant construction call after the try block -- "
            "otherwise this test would pass vacuously",
        )


class ExactConsumptionTests(unittest.TestCase):
    """Requirements 14-15: exact removal, unrelated records untouched."""

    def test_exact_valid_authorization_is_removed_once(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        self.assertEqual(store.current, [])
        self.assertEqual(len(store.save_calls), 1)

    def test_unrelated_authorization_records_remain_unchanged(self) -> None:
        preview = _preview()
        target = _authorize(preview, authorization_id="auth-1")
        other_preview = _preview(hostname="other.example.com")
        other = _authorize(other_preview, authorization_id="auth-2")
        store = FakeAuthorizationStore([target, other])
        consume_authorization_for_guest_agent_dispatch(
            store, target.authorization_id, preview, now=NOW
        )
        self.assertEqual(store.current, [other])


class GrantForgeryResistanceTests(unittest.TestCase):
    """Requirement 16: a caller cannot construct a valid grant by copying
    strings into the dataclass."""

    def test_direct_construction_without_capability_token_raises(self) -> None:
        with self.assertRaises(TypeError):
            GuestAgentHostDispatchGrant(  # type: ignore[call-arg]
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                operation_digest="a" * 64,
                logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
            )

    def test_direct_construction_with_wrong_token_raises(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentHostDispatchGrant(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                operation_digest="a" * 64,
                logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
                max_seconds=5.0,
                _capability_token=object(),  # type: ignore[call-arg]
            )


class GrantMaxSecondsValidationTests(unittest.TestCase):
    """The grant's own `max_seconds` validation (stricter than
    `ResearchKaliOperationPreview.__post_init__`'s `<= 0`-only check,
    which does not reject NaN) fires even with a REAL capability token --
    not merely bypassed by the token-forgery guard above."""

    def _construct(self, max_seconds: object) -> None:
        GuestAgentHostDispatchGrant(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            operation_digest="a" * 64,
            logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
            max_seconds=max_seconds,  # type: ignore[arg-type]
            _capability_token=_DISPATCH_GRANT_CAPABILITY,
        )

    def test_valid_max_seconds_with_real_token_constructs_cleanly(self) -> None:
        self._construct(5.0)  # must not raise

    def test_bool_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            self._construct(True)

    def test_non_numeric_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            self._construct("5")

    def test_zero_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            self._construct(0)

    def test_negative_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            self._construct(-1.0)

    def test_nan_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            self._construct(float("nan"))

    def test_positive_infinity_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            self._construct(float("inf"))

    def test_negative_infinity_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            self._construct(float("-inf"))


class PreviewBindingProjectionTests(unittest.TestCase):
    """Requirements 17-23: bindings and logical inputs derive only from the
    exact validated preview; a caller cannot override any of them."""

    def test_grant_binds_operation_kind_from_preview(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        self.assertIs(grant.operation_kind, preview.operation_kind)

    def test_grant_binds_operation_digest_from_preview(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        self.assertEqual(grant.operation_digest, preview.operation_digest)

    def test_dns_logical_inputs_derive_only_from_preview(self) -> None:
        preview = _preview(
            hostname="dns.example.com", dns_record_type=ResearchDnsRecordType.AAAA
        )
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        self.assertEqual(
            dict(grant.logical_inputs),
            {"hostname": "dns.example.com", "dns_record_type": "AAAA"},
        )

    def test_https_logical_inputs_derive_only_from_preview(self) -> None:
        preview = _https_preview(
            hostname="https.example.com", resolved_address="203.0.113.5"
        )
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        self.assertEqual(
            dict(grant.logical_inputs),
            {"hostname": "https.example.com", "resolved_address": "203.0.113.5"},
        )

    def test_function_signature_accepts_no_operation_fact_overrides(self) -> None:
        """Structural proof that a caller cannot pass hostname/
        dns_record_type/resolved_address/operation_kind/operation_digest
        directly -- the function simply has no such parameters."""
        import inspect

        parameters = set(
            inspect.signature(consume_authorization_for_guest_agent_dispatch).parameters
        )
        forbidden = {
            "hostname",
            "dns_record_type",
            "resolved_address",
            "operation_kind",
            "operation_digest",
            "logical_inputs",
        }
        self.assertEqual(parameters & forbidden, set())
        self.assertEqual(
            parameters, {"authorization_store", "authorization_id", "preview", "now"}
        )


class RequestIdNonceTests(unittest.TestCase):
    """Requirements 26-27: request_id/nonce are correlation/replay identity
    only, supplied at the final boundary, never authorization facts."""

    def _grant(
        self, preview: ResearchKaliOperationPreview
    ) -> GuestAgentHostDispatchGrant:
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        return consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )

    def test_request_id_only_affects_correlation_field(self) -> None:
        preview = _preview()
        grant = self._grant(preview)
        request = grant.materialize_request(request_id="req-xyz", nonce="nonce-1")
        self.assertEqual(request.request_id, "req-xyz")
        self.assertEqual(request.operation_digest, preview.operation_digest)

    def test_nonce_only_affects_nonce_field(self) -> None:
        preview = _preview()
        grant = self._grant(preview)
        request = grant.materialize_request(request_id="req-1", nonce="nonce-xyz")
        self.assertEqual(request.nonce, "nonce-xyz")
        self.assertEqual(request.operation_kind, preview.operation_kind)

    def test_invalid_request_id_fails_closed_without_consuming_the_grant(self) -> None:
        preview = _preview()
        grant = self._grant(preview)
        with self.assertRaises(ResearchError):
            grant.materialize_request(request_id="", nonce="nonce-1")
        self.assertFalse(grant.already_materialized)
        # A corrected retry still succeeds -- the malformed attempt did not
        # burn the one-shot grant.
        request = grant.materialize_request(request_id="req-1", nonce="nonce-1")
        self.assertEqual(request.request_id, "req-1")


class RequestConstructionTests(unittest.TestCase):
    """Requirements 28-32: the constructed request's shape."""

    def test_protocol_version_is_v2(self) -> None:
        # v0.3.466: materialize_request now always produces the
        # execution-bound V2 generation -- every grant this module can
        # construct already carries a real, preview-derived max_seconds,
        # so there is no honest V1 request this function could produce.
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        request = grant.materialize_request(request_id="r1", nonce="n1")
        self.assertIs(request.protocol_version, GuestAgentProtocolVersion.V2)

    def test_request_carries_signed_execution_limits_from_preview(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        request = grant.materialize_request(request_id="r1", nonce="n1")
        self.assertIsNotNone(request.execution_limits)
        self.assertEqual(request.execution_limits.max_seconds, preview.max_seconds)

    def test_request_uses_exact_consumed_preview_digest(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        request = grant.materialize_request(request_id="r1", nonce="n1")
        self.assertEqual(request.operation_digest, preview.operation_digest)

    def test_dns_request_has_only_hostname_and_dns_record_type(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        request = grant.materialize_request(request_id="r1", nonce="n1")
        self.assertEqual(
            {name for name, _ in request.logical_inputs},
            {"hostname", "dns_record_type"},
        )

    def test_https_request_has_only_hostname_and_resolved_address(self) -> None:
        preview = _https_preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        request = grant.materialize_request(request_id="r1", nonce="n1")
        self.assertEqual(
            {name for name, _ in request.logical_inputs},
            {"hostname", "resolved_address"},
        )

    def test_no_command_shell_argv_executable_field_exists(self) -> None:
        import dataclasses

        forbidden = {
            "shell",
            "command",
            "command_line",
            "argv",
            "executable",
            "script",
        }
        for cls in (GuestAgentHostDispatchGrant,):
            field_names = {f.name.lower() for f in dataclasses.fields(cls)}
            self.assertEqual(field_names & forbidden, set())


class OneShotHandoffTests(unittest.TestCase):
    """Requirements 33-34: one consumed authorization mints at most one
    request; a second attempt fails closed, including under concurrency."""

    def _grant(self) -> GuestAgentHostDispatchGrant:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        return consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )

    def test_one_consumed_authorization_cannot_mint_two_requests(self) -> None:
        grant = self._grant()
        grant.materialize_request(request_id="r1", nonce="n1")
        with self.assertRaises(ResearchError):
            grant.materialize_request(request_id="r2", nonce="n2")

    def test_second_use_fails_closed_with_a_bounded_message(self) -> None:
        grant = self._grant()
        grant.materialize_request(request_id="r1", nonce="n1")
        with self.assertRaises(ResearchError) as ctx:
            grant.materialize_request(request_id="r2", nonce="n2")
        self.assertLess(len(str(ctx.exception)), 200)

    def test_concurrent_materialize_attempts_yield_exactly_one_success(self) -> None:
        grant = self._grant()
        successes: list[object] = []
        failures: list[Exception] = []
        lock = threading.Lock()

        def _attempt(index: int) -> None:
            try:
                request = grant.materialize_request(
                    request_id=f"r{index}", nonce=f"n{index}"
                )
                with lock:
                    successes.append(request)
            except ResearchError as error:
                with lock:
                    failures.append(error)

        threads = [threading.Thread(target=_attempt, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5.0)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 7)


class ReplayIndependenceTests(unittest.TestCase):
    """Requirements 35-36: replay is a distinct property, never touched."""

    def test_replay_protector_symbols_are_not_referenced_in_production_code(
        self,
    ) -> None:
        forbidden = {
            "GuestAgentReplayProtector",
            "GuestAgentReplayOutcome",
            "JsonFileGuestAgentReplayNonceStore",
            "GuestAgentReplayNonceStore",
            "consume_once",
        }
        for path in (HANDOFF_MODULE_FILE, CONSUMPTION_MODULE_FILE):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            referenced = _referenced_names(tree)
            with self.subTest(file=path.name):
                self.assertEqual(referenced & forbidden, set())

    def test_replay_nonce_remains_unconsumed_after_a_full_handoff(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        request = grant.materialize_request(
            request_id="r1", nonce="still-unconsumed-nonce"
        )

        class _InMemoryReplayStore:
            def __init__(self) -> None:
                self._records: list[GuestAgentReplayNonceRecord] = []

            def load(self) -> list[GuestAgentReplayNonceRecord]:
                return list(self._records)

            def save(self, records: list[GuestAgentReplayNonceRecord]) -> None:
                self._records = list(records)

        protector = GuestAgentReplayProtector(_InMemoryReplayStore())
        outcome = protector.consume_once(request)
        self.assertEqual(outcome, GuestAgentReplayOutcome.ACCEPTED)


class GuestCoreStillInertTests(unittest.TestCase):
    """Requirements 37-38: the resulting request still only reaches
    GuestAgentCore's existing inert, non-SUCCESS admission outcome."""

    def test_guest_core_returns_non_success_for_the_resulting_dns_request(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        request = grant.materialize_request(request_id="r1", nonce="n1")
        response = admit_guest_agent_request(request)
        self.assertNotEqual(response.status, GuestAgentResponseStatus.SUCCESS)
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)

    def test_guest_core_returns_non_success_for_the_resulting_https_request(
        self,
    ) -> None:
        preview = _https_preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        request = grant.materialize_request(request_id="r1", nonce="n1")
        response = admit_guest_agent_request(request)
        self.assertNotEqual(response.status, GuestAgentResponseStatus.SUCCESS)


class NoAutomaticAdapterOrProbeAcceptanceTests(unittest.TestCase):
    """If GUEST_AGENT transport is added: no existing process adapter or
    runtime probe treats it as ready/acceptable automatically."""

    def test_wsl_adapter_rejects_a_guest_agent_transport_command_plan(self) -> None:
        guest_preview = _preview(transport=ResearchKaliCommandTransport.GUEST_AGENT)
        adapter = WslKaliOperationProcessAdapter()
        with self.assertRaises(ResearchError):
            adapter.run(guest_preview.command_plan, timeout_seconds=1.0)

    def test_vmware_adapter_rejects_a_guest_agent_transport_command_plan(self) -> None:
        guest_preview = _preview(transport=ResearchKaliCommandTransport.GUEST_AGENT)
        adapter = VmwareKaliOperationProcessAdapter(
            guest_transport=ResearchVMwareKaliGuestTransportRequirement(
                ssh_executable_path=r"C:\Windows\System32\OpenSSH\ssh.exe",
                private_key_path=r"C:\Users\hypatia\.ssh\hypatia_guest_ed25519",
                known_hosts_path=r"C:\Users\hypatia\.ssh\hypatia_known_hosts",
                guest_user="hypatia-probe",
                guest_host="192.168.206.128",
            )
        )
        with self.assertRaises(ResearchError):
            adapter.run(guest_preview.command_plan, timeout_seconds=1.0)

    def test_vmware_runtime_probe_never_reports_guest_agent_ready(self) -> None:
        """Refuses immediately (no host/guest probing of any kind) for any
        transport other than VMWARE_KALI -- confirmed safe to call
        directly with zero side effects, per the probe's own guard."""
        from research.ResearchKaliRuntimeEnvironment import (
            ResearchKaliRuntimeReadinessState,
        )
        from research.ResearchVMwareKaliHostReadiness import (
            ResearchVMwareKaliHostRequirement,
        )

        probe = VmwareKaliRuntimeProbe(
            host_readiness_probe=_NeverCalledProbe(),
            host_requirement=ResearchVMwareKaliHostRequirement(
                vmrun_executable_path=(
                    r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
                ),
                vmx_path=r"C:\VMs\kali\kali.vmx",
                vm_identity="kali-guest",
            ),
            guest_readiness_probe=_NeverCalledProbe(),
            guest_transport=ResearchVMwareKaliGuestTransportRequirement(
                ssh_executable_path=r"C:\Windows\System32\OpenSSH\ssh.exe",
                private_key_path=r"C:\Users\hypatia\.ssh\hypatia_guest_ed25519",
                known_hosts_path=r"C:\Users\hypatia\.ssh\hypatia_known_hosts",
                guest_user="hypatia-probe",
                guest_host="192.168.206.128",
            ),
        )
        requirement = ResearchKaliRuntimeRequirement(
            transport=ResearchKaliCommandTransport.GUEST_AGENT
        )
        readiness = probe.readiness(requirement)
        self.assertFalse(readiness.ready)
        self.assertEqual(readiness.state, ResearchKaliRuntimeReadinessState.UNAVAILABLE)


class _NeverCalledProbe:
    """A probe double that fails the test loudly if it is ever invoked."""

    def readiness(self, *args: object, **kwargs: object) -> object:
        raise AssertionError(
            "this probe must never be called for a non-VMware transport"
        )


class CatalogAndSchemaNoAutoExposureTests(unittest.TestCase):
    """If GUEST_AGENT transport is added: no executable capability catalog
    or schema entry is produced for it merely because the enum member
    exists."""

    def test_capability_catalog_has_no_guest_agent_entry(self) -> None:
        records = kali_operation_capability_records()
        for record in records:
            with self.subTest(identity=record.identity):
                self.assertNotIn("guest_agent", record.identity)

    def test_capability_catalog_entry_count_is_unchanged(self) -> None:
        # Historical fact: exactly 3 production-dispatchable (kind, transport)
        # pairs exist today (DNS over WSL, DNS over VMware, HTTPS over WSL).
        # A regression here would mean GUEST_AGENT silently became a 4th.
        records = kali_operation_capability_records()
        self.assertEqual(len(records), 3)

    def test_capability_schema_has_no_guest_agent_entry(self) -> None:
        schemas = kali_operation_schema_records()
        for schema in schemas:
            with self.subTest(identity=schema.capability_identity):
                self.assertNotIn("guest_agent", schema.capability_identity)


def _referenced_names(tree: ast.AST) -> set[str]:
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            referenced.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            referenced.update(alias.name for alias in node.names)
    return referenced


class StructuralSecurityTests(unittest.TestCase):
    """AST-based (never naive substring) proof that the new production
    files introduce no execution-authority dependency, no process/
    network side effect, and no arbitrary command channel -- mirroring
    `tests.research.test_guest_agent_rpc_transport.StructuralSecurityTests`
    exactly, including its lesson that a naive text scan is fooled by
    honest negative-claim prose in a docstring (v0.3.461)."""

    def setUp(self) -> None:
        self.handoff_tree = ast.parse(
            HANDOFF_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(HANDOFF_MODULE_FILE),
        )
        self.consumption_tree = ast.parse(
            CONSUMPTION_MODULE_FILE.read_text(encoding="utf-8"),
            filename=str(CONSUMPTION_MODULE_FILE),
        )
        self.all_trees = (self.handoff_tree, self.consumption_tree)

    def test_no_kali_execution_authority_is_imported_or_referenced(self) -> None:
        forbidden = {
            "KaliToolGateway",
            "ToolExecutionService",
            "WslKaliOperationProcessAdapter",
            "VmwareKaliOperationProcessAdapter",
            "ResearchKaliRuntimeProbe",
        }
        for tree in self.all_trees:
            with self.subTest(tree=tree):
                self.assertEqual(_referenced_names(tree) & forbidden, set())

    def test_no_subprocess_socket_or_network_reference(self) -> None:
        forbidden = {"subprocess", "socket", "ssl", "urllib", "http", "requests"}
        for tree in self.all_trees:
            with self.subTest(tree=tree):
                self.assertEqual(_referenced_names(tree) & forbidden, set())

    def test_no_vmware_kali_ssh_wsl_execution_token_is_referenced(self) -> None:
        forbidden = {"vmrun", "sshd", "paramiko", "wsl", "ssh"}
        for tree in self.all_trees:
            with self.subTest(tree=tree):
                lowered = {name.lower() for name in _referenced_names(tree)}
                self.assertEqual(lowered & forbidden, set())

    def test_no_arbitrary_command_channel_vocabulary_is_referenced(self) -> None:
        forbidden = {
            "shell",
            "command",
            "command_line",
            "argv",
            "executable",
            "script",
            "powershell",
            "bash",
        }
        for tree in self.all_trees:
            with self.subTest(tree=tree):
                lowered = {name.lower() for name in _referenced_names(tree)}
                self.assertEqual(lowered & forbidden, set())

    def test_no_authorization_store_mutation_api_beyond_save_is_referenced(
        self,
    ) -> None:
        """No delete/extend-expiration/synthesize-authorization-id API
        exists anywhere in the new production files."""
        forbidden = {"delete", "remove_authorization", "extend_expiration", "renew"}
        for tree in self.all_trees:
            with self.subTest(tree=tree):
                lowered = {name.lower() for name in _referenced_names(tree)}
                self.assertEqual(lowered & forbidden, set())


if __name__ == "__main__":
    unittest.main()
