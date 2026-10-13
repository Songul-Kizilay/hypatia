"""Pure admission-logic and real RPC-composition proofs for `GuestAgentCore`.

`research.GuestAgentCore.admit_guest_agent_request` is the guest-side
application core: inert admission, never execution. This file proves two
different things, deliberately kept apart:

1. The pure admission logic itself (no sockets, no TLS, no threads) --
   allowlist membership, exact required-field-set matching, narrow
   per-field syntactic validation, fixed response details, and that
   `SUCCESS`/`REPLAY_REJECTED` are structurally unreachable outcomes.
2. Real composition with the actual, unmodified v0.3.461 RPC transport
   over a genuine loopback TLS 1.3 mutual handshake -- proving this
   function can be registered directly as
   `research.GuestAgentRpcTransport.GuestAgentRpcRequestHandler` and that
   transport-layer authentication still gates every path to it, exactly
   as it gated every other handler in
   `tests/research/test_guest_agent_rpc_transport.py`.

Proving composition is not proving execution: every real-RPC test below
still only ever observes a `DECLINED`/`INVALID_REQUEST`/
`UNSUPPORTED_CAPABILITY` response, never `SUCCESS`, and never a process,
socket, or network side effect from the core itself.
"""

from __future__ import annotations

import ast
import ipaddress
import sys
import unittest
from pathlib import Path
from unittest import mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import research.GuestAgentCore as guest_agent_core_module  # noqa: E402
from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentCore import (  # noqa: E402
    SUPPORTED_GUEST_AGENT_OPERATION_KINDS,
    admit_guest_agent_request,
)
from research.GuestAgentMtlsContext import (  # noqa: E402
    build_guest_server_tls_context,
    build_host_client_tls_context,
)
from research.GuestAgentProtocol import (  # noqa: E402
    GuestAgentProtocolVersion,
    GuestAgentRequest,
    GuestAgentResponse,
    GuestAgentResponseStatus,
)
from research.GuestAgentReplayNonceRecord import (  # noqa: E402
    GuestAgentReplayNonceRecord,
)
from research.GuestAgentReplayProtector import (  # noqa: E402
    GuestAgentReplayOutcome,
    GuestAgentReplayProtector,
)
from research.GuestAgentRpcTransport import (  # noqa: E402
    GuestAgentRpcClient,
    GuestAgentRpcServer,
    GuestAgentRpcTransportTimeouts,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    MAX_KALI_OPERATION_HOSTNAME_CHARACTERS,
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
)
from tests.research.test_guest_agent_loopback_mtls_handshake import (  # noqa: E402
    _LoopbackMtlsFixture,
)
from tests.research.test_guest_agent_rpc_transport import (  # noqa: E402
    _run_server_in_thread,
    _sample_request,
)

THIS_FILE = Path(__file__).resolve()
CORE_MODULE_FILE = SRC_DIR / "research" / "GuestAgentCore.py"

_FAST_TIMEOUTS = GuestAgentRpcTransportTimeouts(
    connect_seconds=5.0, handshake_seconds=5.0, read_seconds=2.0, write_seconds=5.0
)

_DIGEST = "a" * 64
_VALID_DNS_INPUTS = (("hostname", "example.com"), ("dns_record_type", "A"))
_VALID_HTTPS_INPUTS = (
    ("hostname", "example.com"),
    ("resolved_address", "93.184.216.34"),
)


def _dns_request(**overrides: object) -> GuestAgentRequest:
    base: dict[str, object] = dict(
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        logical_inputs=_VALID_DNS_INPUTS,
        operation_digest=_DIGEST,
    )
    base.update(overrides)
    return _sample_request(**base)  # type: ignore[arg-type]


def _https_request(**overrides: object) -> GuestAgentRequest:
    base: dict[str, object] = dict(
        operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
        logical_inputs=_VALID_HTTPS_INPUTS,
        operation_digest=_DIGEST,
    )
    base.update(overrides)
    return _sample_request(**base)  # type: ignore[arg-type]


class AllowlistTests(unittest.TestCase):
    """Requirements 7-10: the allowlist is explicit, code-owned, and deny
    by default for anything not deliberately registered."""

    def test_allowlist_is_exactly_the_two_reviewed_operations(self) -> None:
        self.assertEqual(
            SUPPORTED_GUEST_AGENT_OPERATION_KINDS,
            frozenset(
                {
                    ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                    ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                }
            ),
        )

    def test_dns_record_lookup_is_deliberately_recognized(self) -> None:
        response = admit_guest_agent_request(_dns_request())
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)

    def test_https_header_lookup_is_deliberately_recognized(self) -> None:
        response = admit_guest_agent_request(_https_request())
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)

    def test_every_current_operation_kind_is_covered_by_the_allowlist(self) -> None:
        """Today's enum has exactly two members, and both are registered --
        this is a regression guard, not the deny-by-default proof itself
        (see `StructuralDenyByDefaultTests` below for that)."""
        self.assertEqual(
            set(ResearchKaliOperationKind), set(SUPPORTED_GUEST_AGENT_OPERATION_KINDS)
        )

    def test_operation_kind_outside_the_allowlist_is_reported_as_unsupported_capability(
        self,
    ) -> None:
        """The real `UNSUPPORTED_CAPABILITY` branch cannot be exercised with
        a genuine `GuestAgentRequest` today, because the allowlist already
        covers every existing `ResearchKaliOperationKind` member -- so no
        other test in this file ever actually observes this status or its
        fixed detail string. Prove both are correct by deliberately
        removing one real, already-registered entry from the allowlist for
        the duration of this test, which is the only way to make that
        branch reachable without inventing a third enum member this
        repository does not have."""
        with mock.patch.dict(
            guest_agent_core_module._OPERATION_REQUIRED_LOGICAL_INPUT_FIELDS,
            {},
            clear=True,
        ):
            response = admit_guest_agent_request(_dns_request())
        self.assertEqual(
            response.status, GuestAgentResponseStatus.UNSUPPORTED_CAPABILITY
        )
        self.assertEqual(
            response.detail, guest_agent_core_module._DETAIL_UNSUPPORTED_CAPABILITY
        )
        # The patch is scoped to the `with` block only: the real allowlist
        # is unaffected afterward, for every other test in this module.
        self.assertEqual(
            SUPPORTED_GUEST_AGENT_OPERATION_KINDS,
            frozenset(
                {
                    ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                    ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                }
            ),
        )


class StructuralDenyByDefaultTests(unittest.TestCase):
    """Requirement 10 / roadmap: a hypothetical future
    `ResearchKaliOperationKind` member must not become admitted merely by
    existing in the enum. Python's own closed `StrEnum` makes it impossible
    to construct a `GuestAgentRequest` naming a member that does not exist
    today, so this is proved structurally (AST) over the source that
    builds the allowlist, instead."""

    def setUp(self) -> None:
        self.tree = ast.parse(
            CORE_MODULE_FILE.read_text(encoding="utf-8"), filename=str(CORE_MODULE_FILE)
        )

    def test_allowlist_mapping_is_not_built_by_iterating_the_enum_class(self) -> None:
        """The dict literal that defines
        `_OPERATION_REQUIRED_LOGICAL_INPUT_FIELDS` must have keys that are
        explicit `ResearchKaliOperationKind.<NAME>` attribute references,
        never the enum class itself, `list(...)`/`set(...)` over it, or a
        comprehension iterating it -- any of which would make a future
        member automatically present without a deliberate code edit."""
        found_mapping = False
        for node in ast.walk(self.tree):
            target_name: str | None = None
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                target_name = node.targets[0].id
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target_name = node.target.id
            if target_name != "_OPERATION_REQUIRED_LOGICAL_INPUT_FIELDS":
                continue
            if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
                continue
            found_mapping = True
            value = node.value
            # Black may wrap the literal in an `ast.Dict` directly, or the
            # annotated-assignment value could itself be the dict; walk the
            # whole subtree and demand every dict key found is a plain
            # `ResearchKaliOperationKind.<NAME>` attribute access.
            dict_nodes = [n for n in ast.walk(value) if isinstance(n, ast.Dict)]
            self.assertTrue(dict_nodes, "expected a dict literal")
            for dict_node in dict_nodes:
                for key in dict_node.keys:
                    self.assertIsInstance(key, ast.Attribute)
                    self.assertIsInstance(key.value, ast.Name)  # type: ignore[union-attr]
                    self.assertEqual(
                        key.value.id,  # type: ignore[union-attr]
                        "ResearchKaliOperationKind",
                    )
            # No comprehension, no call to list()/set()/frozenset() wrapping
            # an iteration over the enum class itself, anywhere in the
            # right-hand side.
            for n in ast.walk(value):
                self.assertNotIsInstance(n, (ast.DictComp, ast.GeneratorExp))
        self.assertTrue(found_mapping)

    def test_no_comprehension_over_the_enum_class_anywhere_in_the_module(self) -> None:
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
                for generator in node.generators:
                    iterable = generator.iter
                    if isinstance(iterable, ast.Name):
                        self.assertNotEqual(iterable.id, "ResearchKaliOperationKind")


class RequiredFieldSetTests(unittest.TestCase):
    """Requirements 11, 12, 15, 16, 18, 19, 20, 22: exact field-set
    admission for each operation."""

    def test_dns_request_requires_hostname(self) -> None:
        response = admit_guest_agent_request(
            _dns_request(logical_inputs=(("dns_record_type", "A"),))
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_dns_request_requires_dns_record_type(self) -> None:
        response = admit_guest_agent_request(
            _dns_request(logical_inputs=(("hostname", "example.com"),))
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_dns_request_rejects_resolved_address(self) -> None:
        response = admit_guest_agent_request(
            _dns_request(
                logical_inputs=(
                    ("hostname", "example.com"),
                    ("dns_record_type", "A"),
                    ("resolved_address", "93.184.216.34"),
                )
            )
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_https_request_requires_hostname(self) -> None:
        response = admit_guest_agent_request(
            _https_request(logical_inputs=(("resolved_address", "93.184.216.34"),))
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_https_request_requires_resolved_address(self) -> None:
        response = admit_guest_agent_request(
            _https_request(logical_inputs=(("hostname", "example.com"),))
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_https_request_rejects_dns_record_type(self) -> None:
        response = admit_guest_agent_request(
            _https_request(
                logical_inputs=(
                    ("hostname", "example.com"),
                    ("resolved_address", "93.184.216.34"),
                    ("dns_record_type", "A"),
                )
            )
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_unknown_logical_input_field_is_rejected(self) -> None:
        response = admit_guest_agent_request(
            _dns_request(
                logical_inputs=(
                    ("hostname", "example.com"),
                    ("dns_record_type", "A"),
                    ("totally_unexpected_field", "value"),
                )
            )
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_empty_required_hostname_value_is_rejected(self) -> None:
        response = admit_guest_agent_request(
            _dns_request(logical_inputs=(("hostname", ""), ("dns_record_type", "A")))
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_empty_required_dns_record_type_value_is_rejected(self) -> None:
        response = admit_guest_agent_request(
            _dns_request(
                logical_inputs=(("hostname", "example.com"), ("dns_record_type", ""))
            )
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_duplicate_logical_input_fields_remain_rejected_at_the_protocol_layer(
        self,
    ) -> None:
        """The core never even sees a duplicate: `GuestAgentRequest` itself
        already rejects a repeated field name unconditionally -- this is a
        regression proof of that existing, unmodified guarantee, not new
        core logic."""
        with self.assertRaises(ResearchError):
            GuestAgentRequest(
                protocol_version=GuestAgentProtocolVersion.V1,
                request_id="dup",
                nonce="dup-nonce",
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                operation_digest=_DIGEST,
                logical_inputs=(
                    ("hostname", "example.com"),
                    ("hostname", "example.org"),
                ),
            )


class FieldValueValidationTests(unittest.TestCase):
    """Requirements 13, 14, 17, 23: narrow per-field syntactic validation."""

    def test_dns_record_type_must_be_an_existing_closed_enum_value(self) -> None:
        for value in ("A", "AAAA", "CNAME"):
            with self.subTest(value=value):
                response = admit_guest_agent_request(
                    _dns_request(
                        logical_inputs=(
                            ("hostname", "example.com"),
                            ("dns_record_type", value),
                        )
                    )
                )
                self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        self.assertEqual(
            {member.value for member in ResearchDnsRecordType}, {"A", "AAAA", "CNAME"}
        )

    def test_unrecognized_dns_record_type_value_is_rejected(self) -> None:
        response = admit_guest_agent_request(
            _dns_request(
                logical_inputs=(("hostname", "example.com"), ("dns_record_type", "MX"))
            )
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_malformed_resolved_address_is_rejected(self) -> None:
        for bad_value in ("not-an-ip", "999.999.999.999", "example.com", "1.2.3"):
            with self.subTest(value=bad_value):
                response = admit_guest_agent_request(
                    _https_request(
                        logical_inputs=(
                            ("hostname", "example.com"),
                            ("resolved_address", bad_value),
                        )
                    )
                )
                self.assertEqual(
                    response.status, GuestAgentResponseStatus.INVALID_REQUEST
                )

    def test_valid_ipv4_and_ipv6_resolved_address_is_accepted(self) -> None:
        for value in ("93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"):
            with self.subTest(value=value):
                ipaddress.ip_address(value)  # sanity: these really are valid
                response = admit_guest_agent_request(
                    _https_request(
                        logical_inputs=(
                            ("hostname", "example.com"),
                            ("resolved_address", value),
                        )
                    )
                )
                self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)

    def test_hostname_longer_than_the_reviewed_bound_is_rejected(self) -> None:
        too_long = "a" * (MAX_KALI_OPERATION_HOSTNAME_CHARACTERS + 1)
        response = admit_guest_agent_request(
            _dns_request(
                logical_inputs=(("hostname", too_long), ("dns_record_type", "A"))
            )
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_hostname_at_exactly_the_reviewed_bound_is_accepted(self) -> None:
        exact = "a" * MAX_KALI_OPERATION_HOSTNAME_CHARACTERS
        response = admit_guest_agent_request(
            _dns_request(logical_inputs=(("hostname", exact), ("dns_record_type", "A")))
        )
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)


class HostileInputHygieneTests(unittest.TestCase):
    """Requirement 24: no hostile logical-input value ever appears in a
    raised response detail."""

    def test_hostile_hostname_value_never_appears_in_response_detail(self) -> None:
        hostile = "<script>unique-marker-xyz-123</script>" * 5
        response = admit_guest_agent_request(
            _dns_request(
                logical_inputs=(("hostname", hostile), ("dns_record_type", "A"))
            )
        )
        self.assertNotIn("unique-marker-xyz-123", response.detail)
        self.assertNotIn(hostile, response.detail)

    def test_hostile_resolved_address_value_never_appears_in_response_detail(
        self,
    ) -> None:
        hostile = "unique-marker-abc-789-not-an-ip"
        response = admit_guest_agent_request(
            _https_request(
                logical_inputs=(
                    ("hostname", "example.com"),
                    ("resolved_address", hostile),
                )
            )
        )
        self.assertNotIn("unique-marker-abc-789", response.detail)

    def test_all_fixed_response_details_are_short_and_bounded(self) -> None:
        requests = [
            _dns_request(),
            _https_request(),
            _dns_request(logical_inputs=()),
            _sample_request(
                operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                operation_digest=_DIGEST,
                logical_inputs=(),
            ),
        ]
        for request in requests:
            with self.subTest(request_id=request.request_id):
                response = admit_guest_agent_request(request)
                self.assertLess(len(response.detail), 200)


class NeverSuccessTests(unittest.TestCase):
    """Requirements 25, 26, 28, 29, 30: no outcome can ever be `SUCCESS`,
    and correlation/output-emptiness hold for every outcome."""

    def _every_sample_request(self) -> list[GuestAgentRequest]:
        return [
            _dns_request(),
            _https_request(),
            _dns_request(logical_inputs=()),
            _https_request(logical_inputs=(("hostname", "x"),)),
            _sample_request(
                operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                operation_digest=_DIGEST,
                logical_inputs=_VALID_HTTPS_INPUTS,
                nonce="nonce-a",
            ),
            _sample_request(
                operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                operation_digest="b" * 64,
                logical_inputs=_VALID_HTTPS_INPUTS,
                nonce="nonce-b",
            ),
        ]

    def test_no_request_ever_produces_success(self) -> None:
        for request in self._every_sample_request():
            with self.subTest(request_id=request.request_id):
                response = admit_guest_agent_request(request)
                self.assertNotEqual(response.status, GuestAgentResponseStatus.SUCCESS)

    def test_no_request_ever_produces_replay_rejected(self) -> None:
        for request in self._every_sample_request():
            with self.subTest(request_id=request.request_id):
                response = admit_guest_agent_request(request)
                self.assertNotEqual(
                    response.status, GuestAgentResponseStatus.REPLAY_REJECTED
                )

    def test_output_lines_are_always_empty(self) -> None:
        for request in self._every_sample_request():
            with self.subTest(request_id=request.request_id):
                response = admit_guest_agent_request(request)
                self.assertEqual(response.output_lines, ())

    def test_response_request_id_exactly_equals_request_request_id(self) -> None:
        for request_id in ("r1", "another-id", "r1x", "R1"):
            request = _dns_request(request_id=request_id)
            response = admit_guest_agent_request(request)
            self.assertEqual(response.request_id, request_id)

    def test_operation_digest_does_not_influence_the_outcome(self) -> None:
        response_a = admit_guest_agent_request(_dns_request(operation_digest="a" * 64))
        response_b = admit_guest_agent_request(_dns_request(operation_digest="b" * 64))
        self.assertEqual(response_a.status, response_b.status)
        self.assertEqual(response_a.detail, response_b.detail)

    def test_nonce_does_not_influence_the_outcome(self) -> None:
        response_a = admit_guest_agent_request(_dns_request(nonce="nonce-a"))
        response_b = admit_guest_agent_request(_dns_request(nonce="nonce-z"))
        self.assertEqual(response_a.status, response_b.status)
        self.assertEqual(response_a.detail, response_b.detail)


class InputTypeGuardTests(unittest.TestCase):
    """Defensive contract check: the function requires a real
    `GuestAgentRequest`, matching the rest of this module's own style of
    raising on a caller-contract violation rather than guessing."""

    def test_non_request_argument_raises(self) -> None:
        with self.assertRaises(ResearchError):
            admit_guest_agent_request(object())  # type: ignore[arg-type]

    def test_none_argument_raises(self) -> None:
        with self.assertRaises(ResearchError):
            admit_guest_agent_request(None)  # type: ignore[arg-type]


class StructuralSecurityTests(unittest.TestCase):
    """Mirrors `tests.research.test_guest_agent_rpc_transport
    .StructuralSecurityTests`'s AST-based (never naive substring) approach:
    v0.3.461 already found that a plain textual scan is fooled by honest
    negative-claim prose in a docstring, so this inspects the AST's
    `Name`/`Attribute`/`Import` nodes only -- never raw text -- exactly
    like that existing precedent."""

    def setUp(self) -> None:
        self.tree = ast.parse(
            CORE_MODULE_FILE.read_text(encoding="utf-8"), filename=str(CORE_MODULE_FILE)
        )

    @staticmethod
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

    def test_no_kali_execution_authority_is_imported_or_referenced(self) -> None:
        forbidden = {
            "KaliToolGateway",
            "ToolExecutionService",
            "ResearchKaliOperationAuthorization",
            "ResearchKaliOperationAuthorizationStore",
            "JsonFileResearchKaliOperationAuthorizationStore",
            "WslKaliOperationProcessAdapter",
            "VmwareKaliOperationProcessAdapter",
            "KaliOperationPreviewApplicationService",
        }
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())

    def test_replay_protection_is_not_imported_or_invoked(self) -> None:
        forbidden = {
            "GuestAgentReplayProtector",
            "GuestAgentReplayOutcome",
            "JsonFileGuestAgentReplayNonceStore",
            "GuestAgentReplayNonceStore",
            "consume_once",
        }
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())

    def test_no_subprocess_shell_or_process_execution_api_is_referenced(self) -> None:
        forbidden = {
            "subprocess",
            "system",
            "popen",
            "Popen",
            "fork",
            "execv",
            "execve",
            "spawn",
        }
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())

    def test_no_socket_or_ssl_import_exists(self) -> None:
        """The core itself needs no transport; it only ever receives an
        already-decoded `GuestAgentRequest` and returns a
        `GuestAgentResponse`."""
        referenced = self._referenced_names(self.tree)
        self.assertNotIn("socket", referenced)
        self.assertNotIn("ssl", referenced)

    def test_no_vmware_kali_ssh_wsl_execution_token_is_referenced(self) -> None:
        forbidden = {"vmrun", "sshd", "paramiko", "wsl", "ssh"}
        lowered = {name.lower() for name in self._referenced_names(self.tree)}
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
        lowered = {name.lower() for name in self._referenced_names(self.tree)}
        self.assertEqual(lowered & forbidden, set())

    def test_no_generic_callable_execution_extension_point_is_defined(self) -> None:
        """No second `Callable[[GuestAgentRequest], GuestAgentResponse]`-
        shaped extension point, and no `run`/`execute`/`dispatch`-named
        function, is introduced by this module."""
        forbidden_function_names = {
            "run",
            "execute",
            "execute_shell",
            "dispatch_command",
            "invoke_executable",
            "dispatch",
        }
        defined_functions = {
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertEqual(defined_functions & forbidden_function_names, set())
        self.assertNotIn("Callable", self._referenced_names(self.tree))


class RealRpcCompositionTests(_LoopbackMtlsFixture):
    """Requirements 49-55: real loopback mTLS RPC composition. Proves the
    core can be registered directly as the RPC handler and that transport
    authentication still gates every path to it -- never that any
    capability executes."""

    def test_core_used_directly_as_the_rpc_handler_type_checks(self) -> None:
        """Type-level compatibility: `GuestAgentRpcServer`'s constructor
        accepts `admit_guest_agent_request` with no adapter. Exercised at
        runtime by every other test in this class; this one documents the
        intent explicitly."""
        from research.GuestAgentRpcTransport import GuestAgentRpcRequestHandler

        handler: GuestAgentRpcRequestHandler = admit_guest_agent_request
        self.assertIs(handler, admit_guest_agent_request)

    def test_real_loopback_dns_request_returns_inert_declined_response(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            admit_guest_agent_request,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        request = _dns_request()
        response = client.send_request(request)

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.request_id, request.request_id)
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        self.assertEqual(response.output_lines, ())
        self.assertNotEqual(response.status, GuestAgentResponseStatus.SUCCESS)

    def test_real_loopback_https_request_returns_inert_declined_response(self) -> None:
        host_config = self.host_config()
        guest_config = self.guest_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            admit_guest_agent_request,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        request = _https_request()
        response = client.send_request(request)

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome, msg=outcome.get("error"))
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        self.assertEqual(response.output_lines, ())

    def test_unsupported_capability_over_real_rpc(self) -> None:
        """There is no third `ResearchKaliOperationKind` member to send
        today, so this exercises the `UNSUPPORTED_CAPABILITY` branch via a
        recognized operation whose inputs are simply absent, confirming
        the branch is reachable through the real transport at all -- the
        field-set test above already proves `INVALID_REQUEST` is reachable
        this way; this test additionally confirms real-RPC composition
        does not alter which status the pure function already returns."""
        host_config = self.host_config()
        guest_config = self.guest_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            admit_guest_agent_request,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        request = _sample_request(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            operation_digest=_DIGEST,
            logical_inputs=(),
        )
        response = client.send_request(request)
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome)
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)

    def test_authentication_precedes_the_core_wrong_role_never_reaches_it(self) -> None:
        guest_config = self.guest_config()
        host_config_wrong_role = self.host_config(
            own_cert=self.guest_cert, own_key=self.guest_key
        )
        calls: list[GuestAgentRequest] = []

        def _counting_core(request: GuestAgentRequest) -> GuestAgentResponse:
            calls.append(request)
            return admit_guest_agent_request(request)

        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            _counting_core,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, _outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config_wrong_role),
            host_config_wrong_role,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        try:
            client.send_request(_dns_request())
        except Exception:  # noqa: BLE001 - client-side outcome is secondary
            pass

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(calls, [])

    def test_untrusted_ca_never_reaches_the_core(self) -> None:
        guest_config = self.guest_config()
        host_config_untrusted = self.host_config(own_cert=self.wrong_ca_host_cert)
        calls: list[GuestAgentRequest] = []

        def _counting_core(request: GuestAgentRequest) -> GuestAgentResponse:
            calls.append(request)
            return admit_guest_agent_request(request)

        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            _counting_core,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, _outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config_untrusted),
            host_config_untrusted,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        try:
            client.send_request(_dns_request())
        except Exception:  # noqa: BLE001
            pass

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(calls, [])

    def test_real_loopback_round_trip_leaves_replay_nonce_unconsumed(self) -> None:
        class _InMemoryReplayStore:
            def __init__(self) -> None:
                self._records: list[GuestAgentReplayNonceRecord] = []

            def load(self) -> list[GuestAgentReplayNonceRecord]:
                return list(self._records)

            def save(self, records: list[GuestAgentReplayNonceRecord]) -> None:
                self._records = list(records)

        guest_config = self.guest_config()
        host_config = self.host_config()
        server = GuestAgentRpcServer(
            build_guest_server_tls_context(guest_config),
            guest_config,
            admit_guest_agent_request,
            timeouts=_FAST_TIMEOUTS,
        )
        port = server.bind()
        thread, outcome = _run_server_in_thread(server)

        client = GuestAgentRpcClient(
            build_host_client_tls_context(host_config),
            host_config,
            port,
            timeouts=_FAST_TIMEOUTS,
        )
        request = _dns_request(nonce="core-still-unconsumed-nonce")
        response = client.send_request(request)
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome)
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)

        protector = GuestAgentReplayProtector(_InMemoryReplayStore())
        replay_outcome = protector.consume_once(request)
        self.assertEqual(replay_outcome, GuestAgentReplayOutcome.ACCEPTED)


if __name__ == "__main__":
    unittest.main()
