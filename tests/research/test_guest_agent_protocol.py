"""The Guest-Agent protocol describes a future message shape; it grants nothing.

PROTOCOL REQUEST != EXECUTION AUTHORITY. REQUEST DIGEST != AUTHORIZATION.
NONCE != AUTHORIZATION. REQUEST ID != AUTHORIZATION. AGENT RESPONSE != TRUSTED
FACT. Every test below either shows the protocol types have no way to reach
execution, authorization, or mutation, or shows that building and parsing a
message is pure, deterministic, and side-effect-free -- even when fed
adversarial text designed to look like a shell command, a policy decision, or
a system instruction.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.GuestAgentProtocol import (
    MAX_LOGICAL_INPUT_FIELD_NAME_LENGTH,
    MAX_LOGICAL_INPUT_FIELDS,
    MAX_LOGICAL_INPUT_VALUE_LENGTH,
    MAX_NONCE_LENGTH,
    MAX_REQUEST_ID_LENGTH,
    MAX_RESPONSE_DETAIL_LENGTH,
    GuestAgentProtocolVersion,
    GuestAgentRequest,
    GuestAgentResponse,
    GuestAgentResponseStatus,
)
from research.GuestAgentProtocolSerialization import (
    canonical_guest_agent_request_bytes,
    canonical_guest_agent_response_bytes,
    guest_agent_request_document,
    guest_agent_request_from_bytes,
    guest_agent_request_from_document,
    guest_agent_response_document,
    guest_agent_response_from_bytes,
    guest_agent_response_from_document,
)
from research.ResearchKaliOperationExecution import (
    KALI_OPERATION_OUTPUT_TRUST,
    MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
    MAX_KALI_OPERATION_OUTPUT_LINES,
)
from research.ResearchKaliOperationPreview import ResearchKaliOperationKind

NEW_MODULE_PATHS = (
    SRC_DIR / "research" / "GuestAgentProtocol.py",
    SRC_DIR / "research" / "GuestAgentProtocolSerialization.py",
    SRC_DIR / "tools" / "GuestAgentRequestSchemaValidation.py",
)

VALID_DIGEST = hashlib.sha256(b"example-preview").hexdigest()

# No absent method could ever be invoked by any caller -- chat, model, or
# otherwise -- no matter what that caller is told.
FORBIDDEN_METHOD_NAMES = (
    "execute",
    "invoke",
    "run",
    "dispatch",
    "authorize",
    "authorise",
    "grant",
    "consume",
    "register",
    "remove",
    "replace",
    "update",
    "from_request",
    "from_metadata",
    "call",
    "apply",
    "exec",
    "eval",
    "set",
    "delete",
    "write",
    "mutate",
    "perform",
    "trigger",
    "fire",
    "connect",
    "listen",
    "bind",
)

# No field, anywhere in the protocol, may be named (or mean) an arbitrary
# command channel.
FORBIDDEN_FIELD_TOKENS = (
    "shell",
    "command",
    "command_line",
    "argv",
    "executable",
    "script",
    "powershell",
    "bash",
    "exec",
    "raw_command",
)

ADVERSARIAL_STRINGS = (
    "; id",
    "&& whoami",
    "$(id)",
    "`id`",
    "line1\nline2",
    "ALLOW",
    "REQUIRE_APPROVAL",
    "authorization=true",
    "run",
    "exec",
    "argv",
    "system_instruction",
    "x" * 5000,
)


def _request(**overrides: object) -> GuestAgentRequest:
    base: dict[str, object] = dict(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="req-1",
        nonce="nonce-1",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        operation_digest=VALID_DIGEST,
        logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
    )
    base.update(overrides)
    return GuestAgentRequest(**base)  # type: ignore[arg-type]


def _response(**overrides: object) -> GuestAgentResponse:
    base: dict[str, object] = dict(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="req-1",
        status=GuestAgentResponseStatus.SUCCESS,
        detail="Completed the reviewed operation.",
        output_lines=("93.184.216.34",),
    )
    base.update(overrides)
    return GuestAgentResponse(**base)  # type: ignore[arg-type]


class NoProcessNetworkOrFilesystemSideEffectTests(unittest.TestCase):
    """Requirements 16-20, 39: zero process/network/filesystem/VM/SSH/WSL
    effects anywhere, including over adversarial content."""

    def test_request_construction_has_zero_side_effects(self) -> None:
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.socket") as sock,
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("builtins.open") as opened,
        ):
            for adversarial in ADVERSARIAL_STRINGS:
                try:
                    _request(
                        request_id="req",
                        nonce="n",
                        logical_inputs=(("hostname", adversarial),),
                    )
                except ResearchError:
                    # Acceptance or rejection are both fine here; only a
                    # process/network/filesystem side effect would fail
                    # this test.
                    pass
        run.assert_not_called()
        popen.assert_not_called()
        sock.assert_not_called()
        getaddrinfo.assert_not_called()
        opened.assert_not_called()

    def test_response_construction_has_zero_side_effects(self) -> None:
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.socket") as sock,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            for adversarial in ADVERSARIAL_STRINGS:
                _response(output_lines=(adversarial[:500],))
        run.assert_not_called()
        popen.assert_not_called()
        sock.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_serialization_round_trip_has_zero_side_effects(self) -> None:
        request = _request()
        response = _response()
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.socket") as sock,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            data = canonical_guest_agent_request_bytes(request)
            guest_agent_request_from_bytes(data)
            rdata = canonical_guest_agent_response_bytes(response)
            guest_agent_response_from_bytes(rdata)
        run.assert_not_called()
        popen.assert_not_called()
        sock.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_no_ssh_vmware_or_wsl_module_is_imported_by_the_new_modules(self) -> None:
        forbidden_modules = {
            "paramiko",
            "fabric",
            "subprocess",
            "socket",
            "ssl",
            "http",
            "urllib",
            "requests",
        }
        for path in NEW_MODULE_PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif (
                    isinstance(node, ast.ImportFrom) and node.module and node.level == 0
                ):
                    imported.add(node.module.split(".")[0])
            with self.subTest(module=path.name):
                self.assertEqual(imported & forbidden_modules, set())


class ImmutabilityTests(unittest.TestCase):
    """Requirements 1, 2: protocol objects and nested collections are frozen."""

    def test_request_fields_cannot_be_reassigned(self) -> None:
        request = _request()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            request.request_id = "other"  # type: ignore[misc]

    def test_response_fields_cannot_be_reassigned(self) -> None:
        response = _response()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            response.status = GuestAgentResponseStatus.FAILED  # type: ignore[misc]

    def test_logical_inputs_tuple_is_immutable(self) -> None:
        request = _request()
        self.assertIsInstance(request.logical_inputs, tuple)
        with self.assertRaises(TypeError):
            request.logical_inputs[0] = ("x", "y")  # type: ignore[index]

    def test_output_lines_tuple_is_immutable(self) -> None:
        response = _response()
        self.assertIsInstance(response.output_lines, tuple)
        with self.assertRaises(TypeError):
            response.output_lines[0] = "x"  # type: ignore[index]


class ProtocolVersionTests(unittest.TestCase):
    """Requirements 3, 4: protocol version is closed, bounded, and fails closed."""

    def test_exactly_one_protocol_version_exists_today(self) -> None:
        self.assertEqual(len(list(GuestAgentProtocolVersion)), 1)
        self.assertEqual(
            GuestAgentProtocolVersion.V1.value, "hypatia-kali-guest-agent/1"
        )

    def test_non_enum_protocol_version_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _request(protocol_version="hypatia-kali-guest-agent/1")  # type: ignore[arg-type]

    def test_unknown_protocol_version_fails_closed_at_parse_time(self) -> None:
        document = guest_agent_request_document(_request())
        document["protocol_version"] = "hypatia-kali-guest-agent/99"
        with self.assertRaises(ResearchError):
            guest_agent_request_from_document(document)

    def test_response_unknown_protocol_version_fails_closed(self) -> None:
        document = guest_agent_response_document(_response())
        document["protocol_version"] = "hypatia-kali-guest-agent/0"
        with self.assertRaises(ResearchError):
            guest_agent_response_from_document(document)


class RequestFieldValidationTests(unittest.TestCase):
    """Requirements 5, 6, 7, 11, 12: strict request-field validation."""

    def test_empty_or_whitespace_request_id_is_rejected(self) -> None:
        for bad in ("", "   "):
            with self.subTest(request_id=bad):
                with self.assertRaises(ResearchError):
                    _request(request_id=bad)

    def test_control_characters_in_request_id_are_rejected(self) -> None:
        for bad in ("a\x00b", "a\rb", "a\nb"):
            with self.subTest(request_id=bad):
                with self.assertRaises(ResearchError):
                    _request(request_id=bad)

    def test_overlong_request_id_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _request(request_id="x" * (MAX_REQUEST_ID_LENGTH + 1))

    def test_empty_or_control_character_nonce_is_rejected(self) -> None:
        for bad in ("", "a\x00b", "a\nb"):
            with self.subTest(nonce=bad):
                with self.assertRaises(ResearchError):
                    _request(nonce=bad)

    def test_overlong_nonce_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            _request(nonce="x" * (MAX_NONCE_LENGTH + 1))

    def test_malformed_operation_digest_is_rejected(self) -> None:
        for bad in (
            "not-a-digest",
            "",
            "x" * 63,
            VALID_DIGEST.upper(),
            VALID_DIGEST + "0",
        ):
            with self.subTest(digest=bad):
                with self.assertRaises(ResearchError):
                    _request(operation_digest=bad)

    def test_fake_operation_digest_that_merely_looks_hex_is_still_checked_by_shape(
        self,
    ) -> None:
        # A digest of the right *shape* (64 hex characters) still constructs:
        # this type only proves shape, never that a real preview produced it.
        fake_but_shaped = "0" * 64
        request = _request(operation_digest=fake_but_shaped)
        self.assertEqual(request.operation_digest, fake_but_shaped)

    def test_malformed_capability_identity_is_rejected(self) -> None:
        for bad in ("dns_record_lookup", "DNS_RECORD_LOOKUP", "", 1, None):
            with self.subTest(operation_kind=bad):
                with self.assertRaises(ResearchError):
                    _request(operation_kind=bad)  # type: ignore[arg-type]

    def test_a_local_only_tool_capability_cannot_be_expressed_as_an_operation_kind(
        self,
    ) -> None:
        """Structural guarantee: `tools.ToolCapability` and
        `ResearchKaliOperationKind` are disjoint enum types, so a local-only
        tool capability (for example `CLOCK_READ`) cannot be supplied here
        at all -- not merely rejected by a runtime check.
        """
        from tools.ToolCapability import ToolCapability

        with self.assertRaises(ResearchError):
            _request(operation_kind=ToolCapability.CLOCK_READ)  # type: ignore[arg-type]


class LogicalInputValidationTests(unittest.TestCase):
    """Requirements 8, 10, 12: logical input field validation."""

    def test_duplicate_logical_input_field_names_fail(self) -> None:
        with self.assertRaises(ResearchError):
            _request(
                logical_inputs=(
                    ("hostname", "example.com"),
                    ("hostname", "other.example.com"),
                )
            )

    def test_too_many_logical_input_fields_fail(self) -> None:
        fields = tuple(
            (f"field_{i}", "value") for i in range(MAX_LOGICAL_INPUT_FIELDS + 1)
        )
        with self.assertRaises(ResearchError):
            _request(logical_inputs=fields)

    def test_oversized_field_name_fails(self) -> None:
        with self.assertRaises(ResearchError):
            _request(
                logical_inputs=(
                    ("x" * (MAX_LOGICAL_INPUT_FIELD_NAME_LENGTH + 1), "value"),
                )
            )

    def test_oversized_value_fails(self) -> None:
        with self.assertRaises(ResearchError):
            _request(
                logical_inputs=(
                    ("hostname", "x" * (MAX_LOGICAL_INPUT_VALUE_LENGTH + 1)),
                )
            )

    def test_control_characters_in_value_fail(self) -> None:
        for bad in ("a\x00b", "a\rb", "a\nb"):
            with self.subTest(value=bad):
                with self.assertRaises(ResearchError):
                    _request(logical_inputs=(("hostname", bad),))

    def test_empty_field_name_fails(self) -> None:
        with self.assertRaises(ResearchError):
            _request(logical_inputs=(("", "value"),))

    def test_non_tuple_logical_inputs_fail(self) -> None:
        with self.assertRaises(ResearchError):
            _request(logical_inputs=[("hostname", "example.com")])  # type: ignore[arg-type]

    def test_non_string_pair_members_fail(self) -> None:
        with self.assertRaises(ResearchError):
            _request(logical_inputs=(("hostname", 1),))  # type: ignore[arg-type]

    def test_adversarial_values_construct_as_inert_data_or_are_rejected_structurally(
        self,
    ) -> None:
        for adversarial in ADVERSARIAL_STRINGS:
            with self.subTest(value=adversarial):
                if "\n" in adversarial or "\x00" in adversarial or "\r" in adversarial:
                    with self.assertRaises(ResearchError):
                        _request(logical_inputs=(("hostname", adversarial),))
                elif len(adversarial) > MAX_LOGICAL_INPUT_VALUE_LENGTH:
                    with self.assertRaises(ResearchError):
                        _request(logical_inputs=(("hostname", adversarial),))
                else:
                    request = _request(logical_inputs=(("hostname", adversarial),))
                    self.assertEqual(request.logical_inputs[0][1], adversarial)


class NoArbitraryCommandChannelTests(unittest.TestCase):
    """Requirement 13: no field anywhere means "execute this command"."""

    def test_no_dataclass_field_names_a_command_channel(self) -> None:
        for owner in (GuestAgentRequest, GuestAgentResponse):
            field_names = {field.name for field in dataclasses.fields(owner)}
            for forbidden in FORBIDDEN_FIELD_TOKENS:
                with self.subTest(owner=owner.__name__, token=forbidden):
                    self.assertFalse(
                        any(forbidden in name for name in field_names),
                        f"{owner.__name__} must not have a field related to "
                        f"'{forbidden}'.",
                    )

    def test_new_modules_define_no_code_identifier_naming_a_command_channel(
        self,
    ) -> None:
        """Structural, not textual: this walks the AST's actual identifiers
        (names, arguments, attributes, assignment targets) -- never prose,
        so a docstring correctly *explaining* why no such field exists does
        not trip this check, only a real function/variable/parameter named
        after one would.
        """
        for path in NEW_MODULE_PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            identifiers: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    identifiers.add(node.name)
                elif isinstance(node, ast.arg):
                    identifiers.add(node.arg)
                elif isinstance(node, ast.Name):
                    identifiers.add(node.id)
                elif isinstance(node, ast.Attribute):
                    identifiers.add(node.attr)
            lowered = {identifier.lower() for identifier in identifiers}
            for forbidden in FORBIDDEN_FIELD_TOKENS:
                with self.subTest(module=path.name, token=forbidden):
                    self.assertNotIn(forbidden, lowered)


class NoAuthorityTests(unittest.TestCase):
    """Requirements 14, 15, 23-27: protocol objects are never authority."""

    def test_protocol_types_expose_no_execution_or_mutation_method(self) -> None:
        for owner in (GuestAgentRequest, GuestAgentResponse):
            for forbidden in FORBIDDEN_METHOD_NAMES:
                with self.subTest(owner=owner.__name__, method=forbidden):
                    self.assertFalse(
                        hasattr(owner, forbidden),
                        f"{owner.__name__} must not expose a '{forbidden}' method.",
                    )

    def test_capability_identity_alone_creates_no_authorization(self) -> None:
        """Requirement 23: nothing about holding an `operation_kind` value
        grants, checks, or references any authorization store."""
        request = _request()
        field_names = {field.name for field in dataclasses.fields(request)}
        self.assertNotIn("authorized", field_names)
        self.assertNotIn("authorization_id", field_names)

    def test_operation_digest_alone_creates_no_authorization(self) -> None:
        """Requirement 24: the digest is carried opaquely; nothing here
        actually imports the authorization store or the gateway to check it
        against. Checked by the real import graph (AST), not by scanning
        prose that explains this invariant in the module's own docstring.
        """
        forbidden_imports = {
            "ResearchKaliOperationAuthorizationStore",
            "KaliToolGateway",
        }
        for path in NEW_MODULE_PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported_names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imported_names.update(alias.name for alias in node.names)
                elif isinstance(node, ast.Import):
                    imported_names.update(alias.name for alias in node.names)
            with self.subTest(module=path.name):
                self.assertEqual(imported_names & forbidden_imports, set())

    def test_request_id_alone_creates_no_authorization(self) -> None:
        """Requirement 25: two requests with the same request_id and
        different digests are both independently valid or invalid purely on
        their own fields -- the ID never substitutes for the digest check.
        """
        first = _request(request_id="shared-id", operation_digest=VALID_DIGEST)
        other_digest = hashlib.sha256(b"different-preview").hexdigest()
        second = _request(request_id="shared-id", operation_digest=other_digest)
        self.assertNotEqual(first.operation_digest, second.operation_digest)

    def test_nonce_alone_creates_no_authorization(self) -> None:
        """Requirement 26: nonce is inert; it participates in no check
        beyond its own boundedness."""
        a = _request(nonce="nonce-a")
        b = _request(nonce="nonce-b")
        self.assertEqual(a.operation_digest, b.operation_digest)
        self.assertEqual(a.operation_kind, b.operation_kind)

    def test_response_creates_no_authorization(self) -> None:
        """Requirement 27: a SUCCESS response has no field or method that
        could register, grant, or persist anything."""
        response = _response()
        field_names = {field.name for field in dataclasses.fields(response)}
        for forbidden in ("authorized", "authorization_id", "granted", "scope"):
            self.assertNotIn(forbidden, field_names)


class ResponseUntrustedBoundaryTests(unittest.TestCase):
    """Requirement 28: response output remains explicitly untrusted."""

    def test_response_output_trust_label_matches_the_existing_kali_label(self) -> None:
        response = _response()
        self.assertEqual(response.output_trust, KALI_OPERATION_OUTPUT_TRUST)

    def test_response_output_trust_label_cannot_be_overridden_to_something_else(
        self,
    ) -> None:
        with self.assertRaises(ResearchError):
            _response(output_trust="trusted")

    def test_declined_or_failed_response_cannot_carry_output_lines(self) -> None:
        for status in (
            GuestAgentResponseStatus.DECLINED,
            GuestAgentResponseStatus.FAILED,
            GuestAgentResponseStatus.UNSUPPORTED_CAPABILITY,
            GuestAgentResponseStatus.INVALID_REQUEST,
        ):
            with self.subTest(status=status):
                with self.assertRaises(ResearchError):
                    _response(status=status, output_lines=("some output",))

    def test_declined_or_failed_response_with_no_output_constructs_cleanly(
        self,
    ) -> None:
        response = _response(
            status=GuestAgentResponseStatus.DECLINED,
            detail="The reviewed operation was declined.",
            output_lines=(),
        )
        self.assertEqual(response.output_lines, ())

    def test_oversized_output_line_count_fails(self) -> None:
        lines = tuple(str(i) for i in range(MAX_KALI_OPERATION_OUTPUT_LINES + 1))
        with self.assertRaises(ResearchError):
            _response(output_lines=lines)

    def test_oversized_output_line_length_fails(self) -> None:
        with self.assertRaises(ResearchError):
            _response(
                output_lines=("x" * (MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS + 1),)
            )

    def test_empty_or_oversized_detail_fails(self) -> None:
        with self.assertRaises(ResearchError):
            _response(detail="")
        with self.assertRaises(ResearchError):
            _response(detail="x" * (MAX_RESPONSE_DETAIL_LENGTH + 1))

    def test_control_characters_in_detail_fail(self) -> None:
        for bad in ("a\x00b", "a\rb", "a\nb"):
            with self.subTest(detail=bad):
                with self.assertRaises(ResearchError):
                    _response(detail=bad)

    def test_malformed_response_status_is_rejected(self) -> None:
        for bad in ("success", "SUCCESS", "", 1, None):
            with self.subTest(status=bad):
                with self.assertRaises(ResearchError):
                    _response(status=bad)  # type: ignore[arg-type]


class DeterminismTests(unittest.TestCase):
    """Requirement 29: repeated construction/parsing is deterministic and
    stateless."""

    def test_repeated_construction_with_identical_arguments_is_equal(self) -> None:
        first = _request()
        second = _request()
        self.assertEqual(first, second)

    def test_repeated_parsing_of_the_same_bytes_is_equal(self) -> None:
        data = canonical_guest_agent_request_bytes(_request())
        first = guest_agent_request_from_bytes(data)
        second = guest_agent_request_from_bytes(data)
        self.assertEqual(first, second)

    def test_construction_never_auto_generates_request_id_or_nonce(self) -> None:
        """Nothing here manufactures a secret during import or
        construction: both fields are required, positional-equivalent
        arguments with no default."""
        fields_by_name = {
            field.name: field for field in dataclasses.fields(GuestAgentRequest)
        }
        for name in ("request_id", "nonce"):
            field = fields_by_name[name]
            self.assertIs(field.default, dataclasses.MISSING)
            self.assertIs(field.default_factory, dataclasses.MISSING)  # type: ignore[comparison-overlap]


class SerializationTests(unittest.TestCase):
    """Requirements 30-33: wire encoding is deterministic, fails closed, and
    uses no unsafe deserialization mechanism."""

    def test_request_round_trip_is_deterministic(self) -> None:
        request = _request()
        data = canonical_guest_agent_request_bytes(request)
        restored = guest_agent_request_from_bytes(data)
        self.assertEqual(restored, request)
        self.assertEqual(canonical_guest_agent_request_bytes(restored), data)

    def test_response_round_trip_is_deterministic(self) -> None:
        response = _response()
        data = canonical_guest_agent_response_bytes(response)
        restored = guest_agent_response_from_bytes(data)
        self.assertEqual(restored, response)
        self.assertEqual(canonical_guest_agent_response_bytes(restored), data)

    def test_unknown_top_level_field_fails_closed_on_request(self) -> None:
        document = guest_agent_request_document(_request())
        document["shell"] = "rm -rf /"
        with self.assertRaises(ResearchError):
            guest_agent_request_from_document(document)

    def test_unknown_top_level_field_fails_closed_on_response(self) -> None:
        document = guest_agent_response_document(_response())
        document["argv"] = ["curl", "http://example.com"]
        with self.assertRaises(ResearchError):
            guest_agent_response_from_document(document)

    def test_unknown_field_error_message_never_echoes_the_untrusted_key_name(
        self,
    ) -> None:
        """An unknown top-level JSON key is raw, unbounded, unsanitized
        attacker input at this point -- the error message must be one of
        this module's own fixed sentences, never text built by
        interpolating that key.
        """
        document = guest_agent_request_document(_request())
        adversarial_key = "evil\nkey\x00withcontrol" + ("x" * 5000)
        document[adversarial_key] = "anything"
        with self.assertRaises(ResearchError) as context:
            guest_agent_request_from_document(document)
        message = str(context.exception)
        self.assertLess(len(message), 200)
        self.assertNotIn(adversarial_key, message)
        self.assertNotIn("\x00", message)
        self.assertNotIn("\n", message)

    def test_missing_field_error_message_names_no_specific_field(self) -> None:
        document = guest_agent_request_document(_request())
        del document["operation_digest"]
        with self.assertRaises(ResearchError) as context:
            guest_agent_request_from_document(document)
        self.assertLess(len(str(context.exception)), 200)

    def test_missing_required_field_fails_closed(self) -> None:
        document = guest_agent_request_document(_request())
        del document["operation_digest"]
        with self.assertRaises(ResearchError):
            guest_agent_request_from_document(document)

    def test_non_object_document_fails_closed(self) -> None:
        for bad in ([], "not a document", 1, None):
            with self.subTest(document=bad):
                with self.assertRaises(ResearchError):
                    guest_agent_request_from_document(bad)

    def test_malformed_logical_inputs_shape_fails_closed(self) -> None:
        document = guest_agent_request_document(_request())
        document["logical_inputs"] = [{"hostname": "example.com"}]
        with self.assertRaises(ResearchError):
            guest_agent_request_from_document(document)

    def test_new_modules_contain_no_pickle_eval_yaml_or_dynamic_import_path(
        self,
    ) -> None:
        """Checked by the real AST (imports and call targets), not by
        scanning prose -- this module's own docstring correctly *names*
        `pickle`/`eval`/YAML while explaining that none of it is used, and
        that explanation must not itself trip the check.
        """
        forbidden_imports = {"pickle", "marshal", "yaml", "importlib"}
        forbidden_calls = {"eval", "exec", "__import__"}
        for path in NEW_MODULE_PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported_modules: set[str] = set()
            called_names: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.update(
                        alias.name.split(".")[0] for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module.split(".")[0])
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    called_names.add(node.func.id)
            with self.subTest(module=path.name, check="imports"):
                self.assertEqual(imported_modules & forbidden_imports, set())
            with self.subTest(module=path.name, check="calls"):
                self.assertEqual(called_names & forbidden_calls, set())

    def test_malformed_bytes_are_not_valid_json_and_fail_closed(self) -> None:
        with self.assertRaises(ResearchError):
            guest_agent_request_from_bytes(b"not json at all")

    def test_non_bytes_input_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            guest_agent_request_from_bytes("not bytes")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
