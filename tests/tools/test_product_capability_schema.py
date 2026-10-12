"""A capability schema describes shape; it never authorizes, validates for
execution, or runs anything.

SCHEMA KNOWN != INPUT AUTHORIZED. SCHEMA VALID != EXECUTION AUTHORIZED.
OUTPUT SHAPE KNOWN != OUTPUT TRUSTED. Mirrors how
`test_product_capability_catalog.py` proves CAPABILITY REGISTERED !=
CAPABILITY PERMITTED, and how `test_product_capability_version_assessment.py`
proves VERSION COMPATIBILITY != EXECUTION AUTHORITY. Every test below either
shows the schema types have no way to reach execution, authorization, or
mutation, or shows that building and looking up a schema is pure and
side-effect-free, even when an adversarial string is fed in as data.
"""

from __future__ import annotations

import ast
import dataclasses
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchKaliOperationPreview import (
    ResearchKaliCommandTransport,
    ResearchKaliOperationKind,
)
from tools.ClockReadTool import ClockReadTool
from tools.FilesystemListTool import MAX_SCANNED_ENTRIES, PAGE_SIZE
from tools.ProductCapabilityCatalogDefaults import (
    kali_operation_identity,
    tool_capability_identity,
)
from tools.ProductCapabilitySchema import (
    MAX_ENUM_VALUE_LENGTH,
    MAX_ENUM_VALUES,
    MAX_SCHEMA_FIELDS,
    ProductCapabilityField,
    ProductCapabilityFieldKind,
    ProductCapabilityInputSchema,
    ProductCapabilityOutputChannel,
    ProductCapabilityOutputSchema,
    ProductCapabilitySchema,
    ProductCapabilitySchemaCompleteness,
)
from tools.ProductCapabilitySchemaCatalog import ProductCapabilitySchemaCatalog
from tools.ProductCapabilitySchemaDefaults import (
    _dns_record_lookup_input_schema,
    _https_header_lookup_input_schema,
    _kali_operation_output_schema,
    clock_read_schema,
    default_product_capability_schema_catalog,
    filesystem_list_schema,
    filesystem_metadata_schema,
    filesystem_read_schema,
    kali_operation_schema_records,
    local_tool_schema_records,
    text_statistics_schema,
)
from tools.TextStatisticsTool import TextStatisticsTool
from tools.ToolCapability import ToolCapability
from tools.ToolRegistry import ToolRegistry
from tools.ToolResult import MAX_TOOL_VALUE_LENGTH

NEW_MODULE_PATHS = (
    SRC_DIR / "tools" / "ProductCapabilitySchema.py",
    SRC_DIR / "tools" / "ProductCapabilitySchemaCatalog.py",
    SRC_DIR / "tools" / "ProductCapabilitySchemaDefaults.py",
)

# Mirrors the existing catalog/assessment suites' own guard list exactly, for
# the same reason: an absent method cannot be invoked by any caller, chat,
# model, or otherwise, no matter what that caller is told.
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
)

FREE_TEXT = ProductCapabilityFieldKind.FREE_TEXT
WHOLE_NUMBER_TEXT = ProductCapabilityFieldKind.WHOLE_NUMBER_TEXT
BOOLEAN_TEXT = ProductCapabilityFieldKind.BOOLEAN_TEXT
CLOSED_ENUM_TEXT = ProductCapabilityFieldKind.CLOSED_ENUM_TEXT
COMPLETE = ProductCapabilitySchemaCompleteness.COMPLETE
PARTIAL = ProductCapabilitySchemaCompleteness.PARTIAL
UNDECLARED = ProductCapabilitySchemaCompleteness.UNDECLARED
LABELLED_VALUES = ProductCapabilityOutputChannel.LABELLED_VALUES
CONTENT_PAYLOAD = ProductCapabilityOutputChannel.CONTENT_PAYLOAD
ORDERED_TEXT_LINES = ProductCapabilityOutputChannel.ORDERED_TEXT_LINES


def _registry_with_local_tools() -> ToolRegistry:
    return ToolRegistry((ClockReadTool(), TextStatisticsTool()))


def _minimal_input_schema() -> ProductCapabilityInputSchema:
    return ProductCapabilityInputSchema(fields=(), completeness=COMPLETE)


def _minimal_output_schema() -> ProductCapabilityOutputSchema:
    return ProductCapabilityOutputSchema(
        channel=LABELLED_VALUES, fields=(), completeness=UNDECLARED
    )


def _minimal_schema(identity: str = "tool:clock_read") -> ProductCapabilitySchema:
    return ProductCapabilitySchema(
        capability_identity=identity,
        input_schema=_minimal_input_schema(),
        output_schema=_minimal_output_schema(),
    )


class NoProcessOrNetworkSideEffectTests(unittest.TestCase):
    """Requirements 1, 2: construction and lookup touch nothing real."""

    def test_schema_construction_has_zero_process_or_network_side_effects(
        self,
    ) -> None:
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            ProductCapabilitySchemaCatalog((_minimal_schema(),))
        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_default_schema_catalog_construction_has_zero_side_effects(self) -> None:
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            registry = _registry_with_local_tools()
            catalog = default_product_capability_schema_catalog(registry)
            for identity in catalog.identities:
                catalog.lookup(identity)
        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_repeated_lookup_on_an_already_built_catalog_has_zero_side_effects(
        self,
    ) -> None:
        catalog = ProductCapabilitySchemaCatalog(kali_operation_schema_records())
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            for identity in catalog.identities:
                self.assertTrue(catalog.described(identity))
                for _ in range(5):
                    catalog.lookup(identity)
            catalog.lookup("kali:dns_record_lookup:does_not_exist")
        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()


class NoAuthorityTests(unittest.TestCase):
    """Requirements 25, 26, 27, 28: a schema is never authority."""

    def test_schema_types_expose_no_execution_or_mutation_method(self) -> None:
        for owner in (
            ProductCapabilityField,
            ProductCapabilityInputSchema,
            ProductCapabilityOutputSchema,
            ProductCapabilitySchema,
            ProductCapabilitySchemaCatalog,
        ):
            for forbidden in FORBIDDEN_METHOD_NAMES:
                with self.subTest(owner=owner.__name__, method=forbidden):
                    self.assertFalse(
                        hasattr(owner, forbidden),
                        f"{owner.__name__} must not expose a '{forbidden}' method.",
                    )

    def test_repeated_lookup_of_the_same_identity_never_consumes_anything(
        self,
    ) -> None:
        """Requirement 26, 29: lookup cannot consume authorization and is pure."""
        catalog = ProductCapabilitySchemaCatalog(kali_operation_schema_records())
        identity = kali_operation_identity(
            ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            ResearchKaliCommandTransport.WSL_KALI,
        )
        first = catalog.lookup(identity)
        for _ in range(10):
            self.assertEqual(catalog.lookup(identity), first)
        self.assertTrue(catalog.described(identity))

    def test_schema_presence_cannot_invoke_or_dispatch_anything(self) -> None:
        """Requirements 27, 28: holding/looking up a schema calls nothing real."""
        registry = _registry_with_local_tools()
        with (
            patch(
                "tools.ToolExecutionService.ToolExecutionService.execute_detailed"
            ) as execute_detailed,
        ):
            catalog = default_product_capability_schema_catalog(registry)
            for identity in catalog.identities:
                schema = catalog.lookup(identity)
                assert schema is not None
        execute_detailed.assert_not_called()


class DeterministicFailureTests(unittest.TestCase):
    """Requirements 5, 6: duplicates and invalid names fail deterministically."""

    def test_duplicate_capability_identities_fail_deterministically(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilitySchemaCatalog((_minimal_schema(), _minimal_schema()))

    def test_an_unknown_identity_fails_closed_not_open(self) -> None:
        catalog = ProductCapabilitySchemaCatalog((_minimal_schema(),))
        self.assertIsNone(catalog.lookup("tool:not_a_real_capability"))
        self.assertFalse(catalog.described("tool:not_a_real_capability"))

    def test_empty_or_non_string_identity_lookup_is_refused(self) -> None:
        catalog = ProductCapabilitySchemaCatalog((_minimal_schema(),))
        with self.assertRaises(ResearchError):
            catalog.lookup("")
        with self.assertRaises(ResearchError):
            catalog.lookup(None)  # type: ignore[arg-type]

    def test_duplicate_field_names_within_one_schema_fail_deterministically(
        self,
    ) -> None:
        duplicated = (
            ProductCapabilityField("path", FREE_TEXT, required=True),
            ProductCapabilityField("path", FREE_TEXT, required=False),
        )
        with self.assertRaises(ResearchError):
            ProductCapabilityInputSchema(fields=duplicated, completeness=COMPLETE)

    def test_empty_or_whitespace_field_name_is_rejected(self) -> None:
        for bad in ("", "   "):
            with self.subTest(name=bad):
                with self.assertRaises(ResearchError):
                    ProductCapabilityField(bad, FREE_TEXT, required=True)

    def test_control_characters_in_field_name_are_rejected(self) -> None:
        for bad in ("a\x00b", "a\rb", "a\nb"):
            with self.subTest(name=bad):
                with self.assertRaises(ResearchError):
                    ProductCapabilityField(bad, FREE_TEXT, required=True)

    def test_overlong_field_name_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField("x" * 101, FREE_TEXT, required=True)


class ImmutabilityTests(unittest.TestCase):
    """Requirements 3, 4: schema records and nested collections are frozen."""

    def test_field_cannot_be_reassigned(self) -> None:
        field = ProductCapabilityField("path", FREE_TEXT, required=True)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            field.required = False  # type: ignore[misc]

    def test_schema_cannot_be_reassigned(self) -> None:
        schema = _minimal_schema()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            schema.capability_identity = "tool:other"  # type: ignore[misc]

    def test_input_and_output_schema_cannot_be_reassigned(self) -> None:
        schema = clock_read_schema()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            schema.input_schema = _minimal_input_schema()  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            schema.output_schema = _minimal_output_schema()  # type: ignore[misc]

    def test_field_tuples_are_immutable_sequences(self) -> None:
        schema = clock_read_schema()
        self.assertIsInstance(schema.output_schema.fields, tuple)
        with self.assertRaises(TypeError):
            schema.output_schema.fields[0] = None  # type: ignore[index]

    def test_enum_values_are_an_immutable_set(self) -> None:
        schema = clock_read_schema()
        timezone_field = next(
            f for f in schema.output_schema.fields if f.name == "timezone"
        )
        self.assertIsInstance(timezone_field.enum_values, frozenset)

    def test_catalog_has_no_way_to_add_or_remove_after_construction(self) -> None:
        catalog = ProductCapabilitySchemaCatalog((_minimal_schema(),))
        original = catalog.identities
        ProductCapabilitySchemaCatalog((_minimal_schema("tool:other"),))
        self.assertEqual(catalog.identities, original)


class FieldValidationTests(unittest.TestCase):
    """Requirements 7, 8, 9, 10, 11: every field-level guard is exercised."""

    def test_non_enum_kind_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField("path", "free_text", required=True)  # type: ignore[arg-type]

    def test_non_boolean_required_flag_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField("path", FREE_TEXT, required=1)  # type: ignore[arg-type]

    def test_non_boolean_repeated_flag_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField(
                "path", FREE_TEXT, required=False, repeated=1  # type: ignore[arg-type]
            )

    def test_bool_is_rejected_for_every_integer_bound_even_though_bool_is_an_int(
        self,
    ) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField("path", FREE_TEXT, required=True, max_length=True)
        with self.assertRaises(ResearchError):
            ProductCapabilityField(
                "n",
                WHOLE_NUMBER_TEXT,
                required=True,
                max_numeric_value=True,
            )
        with self.assertRaises(ResearchError):
            ProductCapabilityField(
                "entry",
                FREE_TEXT,
                required=False,
                repeated=True,
                max_repeat_count=True,
            )

    def test_negative_or_zero_bounds_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField("path", FREE_TEXT, required=True, max_length=0)
        with self.assertRaises(ResearchError):
            ProductCapabilityField("path", FREE_TEXT, required=True, max_length=-1)
        with self.assertRaises(ResearchError):
            ProductCapabilityField(
                "n", WHOLE_NUMBER_TEXT, required=True, max_numeric_value=-1
            )
        with self.assertRaises(ResearchError):
            ProductCapabilityField(
                "entry",
                FREE_TEXT,
                required=False,
                repeated=True,
                max_repeat_count=0,
            )

    def test_zero_max_numeric_value_is_accepted(self) -> None:
        field = ProductCapabilityField(
            "n", WHOLE_NUMBER_TEXT, required=True, max_numeric_value=0
        )
        self.assertEqual(field.max_numeric_value, 0)

    def test_repeated_and_required_together_is_an_impossible_combination(
        self,
    ) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField("entry", FREE_TEXT, required=True, repeated=True)

    def test_max_numeric_value_requires_whole_number_text_kind(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField(
                "path", FREE_TEXT, required=True, max_numeric_value=10
            )

    def test_max_repeat_count_requires_repeated_field(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField("path", FREE_TEXT, required=True, max_repeat_count=5)

    def test_enum_values_requires_closed_enum_kind(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField(
                "path", FREE_TEXT, required=True, enum_values=frozenset({"a"})
            )

    def test_closed_enum_kind_requires_enum_values(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField("kind", CLOSED_ENUM_TEXT, required=True)

    def test_empty_enum_value_set_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField(
                "kind",
                CLOSED_ENUM_TEXT,
                required=True,
                enum_values=frozenset(),
            )

    def test_a_fully_populated_valid_field_constructs_cleanly(self) -> None:
        field = ProductCapabilityField(
            "kind",
            CLOSED_ENUM_TEXT,
            required=True,
            max_length=10,
            enum_values=frozenset({"file", "directory"}),
        )
        self.assertEqual(field.enum_values, frozenset({"file", "directory"}))

    def test_enum_value_set_at_exactly_the_maximum_size_is_accepted(self) -> None:
        values = frozenset(f"v{i}" for i in range(MAX_ENUM_VALUES))
        field = ProductCapabilityField(
            "kind", CLOSED_ENUM_TEXT, required=True, enum_values=values
        )
        assert field.enum_values is not None
        self.assertEqual(len(field.enum_values), MAX_ENUM_VALUES)

    def test_enum_value_set_over_the_maximum_size_is_rejected(self) -> None:
        values = frozenset(f"v{i}" for i in range(MAX_ENUM_VALUES + 1))
        with self.assertRaises(ResearchError):
            ProductCapabilityField(
                "kind", CLOSED_ENUM_TEXT, required=True, enum_values=values
            )

    def test_enum_value_at_exactly_the_maximum_length_is_accepted(self) -> None:
        field = ProductCapabilityField(
            "kind",
            CLOSED_ENUM_TEXT,
            required=True,
            enum_values=frozenset({"x" * MAX_ENUM_VALUE_LENGTH}),
        )
        assert field.enum_values is not None
        self.assertEqual(len(next(iter(field.enum_values))), MAX_ENUM_VALUE_LENGTH)

    def test_enum_value_over_the_maximum_length_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityField(
                "kind",
                CLOSED_ENUM_TEXT,
                required=True,
                enum_values=frozenset({"x" * (MAX_ENUM_VALUE_LENGTH + 1)}),
            )


class SchemaValidationTests(unittest.TestCase):
    """Requirements 11, 12: schema-level cross-field and honesty guards."""

    def test_undeclared_completeness_cannot_carry_fields(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityInputSchema(
                fields=(ProductCapabilityField("path", FREE_TEXT, required=True),),
                completeness=UNDECLARED,
            )

    def test_content_payload_channel_cannot_declare_labelled_fields(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityOutputSchema(
                channel=CONTENT_PAYLOAD,
                fields=(ProductCapabilityField("text", FREE_TEXT, required=True),),
                completeness=PARTIAL,
            )

    def test_content_payload_channel_cannot_be_marked_complete(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityOutputSchema(
                channel=CONTENT_PAYLOAD, fields=(), completeness=COMPLETE
            )

    def test_content_payload_channel_with_partial_or_undeclared_is_accepted(
        self,
    ) -> None:
        for completeness in (PARTIAL, UNDECLARED):
            with self.subTest(completeness=completeness):
                schema = ProductCapabilityOutputSchema(
                    channel=CONTENT_PAYLOAD, fields=(), completeness=completeness
                )
                self.assertEqual(schema.fields, ())

    def test_too_many_fields_is_rejected(self) -> None:
        fields = tuple(
            ProductCapabilityField(f"field_{i}", FREE_TEXT, required=False)
            for i in range(MAX_SCHEMA_FIELDS + 1)
        )
        with self.assertRaises(ResearchError):
            ProductCapabilityInputSchema(fields=fields, completeness=PARTIAL)

    def test_non_tuple_fields_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityInputSchema(
                fields=[ProductCapabilityField("path", FREE_TEXT, required=True)],  # type: ignore[arg-type]
                completeness=COMPLETE,
            )

    def test_non_schema_member_in_the_tuple_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityInputSchema(
                fields=({"name": "path"},),  # type: ignore[arg-type]
                completeness=COMPLETE,
            )

    def test_empty_capability_identity_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilitySchema(
                capability_identity="",
                input_schema=_minimal_input_schema(),
                output_schema=_minimal_output_schema(),
            )

    def test_overlong_capability_identity_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilitySchema(
                capability_identity="x" * 101,
                input_schema=_minimal_input_schema(),
                output_schema=_minimal_output_schema(),
            )

    def test_wrong_typed_input_or_output_schema_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilitySchema(
                capability_identity="tool:clock_read",
                input_schema=None,  # type: ignore[arg-type]
                output_schema=_minimal_output_schema(),
            )
        with self.assertRaises(ResearchError):
            ProductCapabilitySchema(
                capability_identity="tool:clock_read",
                input_schema=_minimal_input_schema(),
                output_schema=None,  # type: ignore[arg-type]
            )


class UntrustedInputCannotDefineASchemaTests(unittest.TestCase):
    """Requirement 24: no chat/model/request path can register or replace
    a schema."""

    def test_the_catalog_constructor_is_the_only_way_in_and_is_code_typed(
        self,
    ) -> None:
        for bad_input in ("metadata string", {"capability": "x"}, 42, None):
            with self.subTest(bad_input=bad_input):
                with self.assertRaises(ResearchError):
                    ProductCapabilitySchemaCatalog(bad_input)  # type: ignore[arg-type]

    def test_a_non_schema_in_the_tuple_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilitySchemaCatalog(({"capability_identity": "tool:x"},))  # type: ignore[arg-type]

    def test_new_modules_never_import_chat_model_or_request_surfaces(self) -> None:
        forbidden_top_level_packages = {"brain", "cognition", "llm", "response"}
        for path in NEW_MODULE_PATHS:
            with self.subTest(module=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                imported: set[str] = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(
                            alias.name.split(".")[0] for alias in node.names
                        )
                    elif (
                        isinstance(node, ast.ImportFrom)
                        and node.module
                        and node.level == 0
                    ):
                        imported.add(node.module.split(".")[0])
                self.assertEqual(imported & forbidden_top_level_packages, set())

    def test_adversarial_strings_surviving_as_enum_values_remain_ordinary_data(
        self,
    ) -> None:
        """Strings like ALLOW/system/admin inside actual output data must
        remain ordinary data -- never treated as a schema or a grant, even
        when they happen to pass every structural validation a real field
        value could pass.
        """
        adversarial = ("ALLOW", "REQUIRE_APPROVAL", "system", "authorization", "admin")
        field = ProductCapabilityField(
            "status",
            CLOSED_ENUM_TEXT,
            required=True,
            enum_values=frozenset(adversarial),
        )
        self.assertEqual(field.enum_values, frozenset(adversarial))
        # Constructing this field did not authorize, execute, or register
        # anything -- it is still only a bounded set of strings to compare
        # untrusted output against, proven by the absence of any method
        # above that could act on a match.
        for owner in (ProductCapabilityField,):
            for forbidden in FORBIDDEN_METHOD_NAMES:
                self.assertFalse(hasattr(owner, forbidden))


class HonestLocalToolCoverageTests(unittest.TestCase):
    """Requirements 13-19: local-tool schemas agree with real implementations."""

    def test_clock_read_input_schema_is_exactly_zero_arguments(self) -> None:
        schema = clock_read_schema()
        self.assertEqual(schema.capability_identity, "tool:clock_read")
        self.assertEqual(schema.input_schema.fields, ())
        self.assertEqual(schema.input_schema.completeness, COMPLETE)

    def test_clock_read_output_fields_agree_with_the_real_implementation(
        self,
    ) -> None:
        schema = clock_read_schema()
        names = {f.name for f in schema.output_schema.fields}
        self.assertEqual(names, {"utc_iso", "utc_date", "utc_time", "timezone"})
        for field in schema.output_schema.fields:
            self.assertTrue(field.required)
        timezone_field = next(
            f for f in schema.output_schema.fields if f.name == "timezone"
        )
        self.assertEqual(timezone_field.enum_values, frozenset({"UTC"}))
        self.assertEqual(schema.output_schema.channel, LABELLED_VALUES)
        for field in schema.output_schema.fields:
            self.assertEqual(field.max_length, MAX_TOOL_VALUE_LENGTH)

    def test_text_statistics_input_schema_agrees_with_the_text_argument(
        self,
    ) -> None:
        schema = text_statistics_schema()
        self.assertEqual(len(schema.input_schema.fields), 1)
        field = schema.input_schema.fields[0]
        self.assertEqual(field.name, "text")
        self.assertTrue(field.required)
        self.assertEqual(field.kind, FREE_TEXT)

    def test_text_statistics_outputs_agree_with_the_real_implementation(
        self,
    ) -> None:
        schema = text_statistics_schema()
        names = {f.name for f in schema.output_schema.fields}
        self.assertEqual(
            names,
            {
                "character_count",
                "word_count",
                "line_count",
                "non_whitespace_character_count",
            },
        )
        for field in schema.output_schema.fields:
            self.assertTrue(field.required)
            self.assertEqual(field.kind, WHOLE_NUMBER_TEXT)
            self.assertEqual(field.max_length, MAX_TOOL_VALUE_LENGTH)

    def test_filesystem_schemas_expose_no_configured_root_or_sensitive_path(
        self,
    ) -> None:
        """Also exercises `FILESYSTEM_READ` through the real registry-driven
        path (a genuine `FilesystemReadTool` wired into `ToolRuntime`), not
        only by calling `filesystem_read_schema()` directly -- so the
        presence/absence mechanism `local_tool_schema_records` relies on is
        proven for all five local-tool schemas, not just four of them.
        """
        import tempfile
        from pathlib import Path as _Path

        from tools.FilesystemReadTool import FilesystemReadTool
        from tools.FilesystemRoot import FilesystemRoot
        from tools.ToolRuntime import ToolRuntime

        class _StubReader:
            root_id = "schema-honesty-test-root"

            def read_range(
                self, relative: str, *, offset: int, max_bytes: int
            ) -> object:
                raise NotImplementedError("never invoked by this test")

        with tempfile.TemporaryDirectory() as raw_root:
            root_path = _Path(raw_root)
            root = FilesystemRoot(root_path, root_id="schema-honesty-test-root")
            read_tool = FilesystemReadTool(_StubReader())
            runtime = ToolRuntime(filesystem_root=root, filesystem_read_tool=read_tool)
            catalog = default_product_capability_schema_catalog(runtime.registry)
            self.assertTrue(
                catalog.described(
                    tool_capability_identity(ToolCapability.FILESYSTEM_READ)
                )
            )
            for identity in catalog.identities:
                schema = catalog.lookup(identity)
                assert schema is not None
                serialized = repr(schema)
                self.assertNotIn(str(root_path), serialized)
                self.assertNotIn(root_path.name, serialized)
                self.assertNotIn("schema-honesty-test-root", serialized)

    def test_filesystem_list_dynamic_output_is_a_repeated_family_not_fixed_entries(
        self,
    ) -> None:
        schema = filesystem_list_schema()
        fixed_names = {f.name for f in schema.output_schema.fields if not f.repeated}
        self.assertEqual(
            fixed_names,
            {
                "entry_count",
                "entries_exceeded",
                "page_offset",
                "page_size",
                "more_pages",
            },
        )
        repeated = [f for f in schema.output_schema.fields if f.repeated]
        self.assertEqual(len(repeated), 1)
        self.assertEqual(repeated[0].name, "entry")
        self.assertFalse(repeated[0].required)
        self.assertEqual(repeated[0].max_repeat_count, PAGE_SIZE)
        # No fabricated entry_1 ... entry_N fixed fields exist.
        for field in schema.output_schema.fields:
            self.assertNotRegex(field.name, r"^entry_\d+$")

    def test_filesystem_list_entry_count_bound_matches_the_real_scan_ceiling(
        self,
    ) -> None:
        schema = filesystem_list_schema()
        entry_count_field = next(
            f for f in schema.output_schema.fields if f.name == "entry_count"
        )
        self.assertEqual(entry_count_field.max_numeric_value, MAX_SCANNED_ENTRIES)
        page_size_field = next(
            f for f in schema.output_schema.fields if f.name == "page_size"
        )
        self.assertEqual(page_size_field.max_numeric_value, PAGE_SIZE)

    def test_filesystem_metadata_size_bytes_is_optional_not_required(self) -> None:
        schema = filesystem_metadata_schema()
        size_field = next(
            f for f in schema.output_schema.fields if f.name == "size_bytes"
        )
        self.assertFalse(size_field.required)

    def test_filesystem_metadata_kind_is_a_grounded_closed_enum(self) -> None:
        schema = filesystem_metadata_schema()
        kind_field = next(f for f in schema.output_schema.fields if f.name == "kind")
        self.assertEqual(kind_field.kind, CLOSED_ENUM_TEXT)
        self.assertEqual(
            kind_field.enum_values, frozenset({"directory", "file", "other"})
        )
        # LINK is excluded: FilesystemRoot.locate refuses any path that is
        # itself a link before this tool's output is ever produced.
        assert kind_field.enum_values is not None
        self.assertNotIn("link", kind_field.enum_values)

    def test_filesystem_read_content_payload_is_distinguished_from_labelled_values(
        self,
    ) -> None:
        schema = filesystem_read_schema()
        self.assertEqual(schema.output_schema.channel, CONTENT_PAYLOAD)
        self.assertEqual(schema.output_schema.fields, ())
        self.assertNotEqual(schema.output_schema.completeness, COMPLETE)

    def test_filesystem_read_input_is_three_required_bounded_arguments(
        self,
    ) -> None:
        schema = filesystem_read_schema()
        names = {f.name: f for f in schema.input_schema.fields}
        self.assertEqual(set(names), {"path", "offset", "max_bytes"})
        for field in names.values():
            self.assertTrue(field.required)
        self.assertEqual(names["offset"].kind, WHOLE_NUMBER_TEXT)
        self.assertEqual(names["max_bytes"].kind, WHOLE_NUMBER_TEXT)

    def test_a_capability_without_an_honest_schema_is_simply_absent(self) -> None:
        """Requirement 12: RESEARCH_STATE_SUMMARY and KNOWLEDGE_DOCUMENT_LIST
        have no concrete `Tool` implementation at all today, so they must
        never appear with a fabricated schema.
        """
        registry = _registry_with_local_tools()
        catalog = default_product_capability_schema_catalog(registry)
        for capability in (
            ToolCapability.RESEARCH_STATE_SUMMARY,
            ToolCapability.KNOWLEDGE_DOCUMENT_LIST,
        ):
            identity = f"tool:{capability.value}"
            self.assertFalse(catalog.described(identity))
            self.assertIsNone(catalog.lookup(identity))

    def test_an_empty_registry_yields_no_local_tool_schemas_without_crashing(
        self,
    ) -> None:
        empty_registry = ToolRegistry()
        records = local_tool_schema_records(empty_registry)
        self.assertEqual(records, ())
        catalog = default_product_capability_schema_catalog(empty_registry)
        self.assertEqual(len(catalog), len(kali_operation_schema_records()))


class HonestKaliCoverageTests(unittest.TestCase):
    """Requirements 20-23: Kali schemas stay narrow, honest, and production-real."""

    def test_only_the_three_executable_kali_combinations_get_schemas(self) -> None:
        records = kali_operation_schema_records()
        self.assertEqual(
            {record.capability_identity for record in records},
            {
                kali_operation_identity(
                    ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                    ResearchKaliCommandTransport.WSL_KALI,
                ),
                kali_operation_identity(
                    ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                    ResearchKaliCommandTransport.VMWARE_KALI,
                ),
                kali_operation_identity(
                    ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                    ResearchKaliCommandTransport.WSL_KALI,
                ),
            },
        )

    def test_https_header_lookup_over_vmware_kali_stays_absent(self) -> None:
        catalog = ProductCapabilitySchemaCatalog(kali_operation_schema_records())
        identity = kali_operation_identity(
            ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
            ResearchKaliCommandTransport.VMWARE_KALI,
        )
        self.assertFalse(catalog.described(identity))
        self.assertIsNone(catalog.lookup(identity))

    def test_kali_schemas_contain_no_shell_command_or_argv_template(self) -> None:
        forbidden_substrings = (
            "/usr/bin/dig",
            "/usr/bin/curl",
            "argv",
            "--resolve",
            "+short",
        )
        for record in kali_operation_schema_records():
            serialized = repr(record)
            for forbidden in forbidden_substrings:
                with self.subTest(identity=record.capability_identity, token=forbidden):
                    self.assertNotIn(forbidden, serialized)

    def test_kali_schemas_expose_no_ssh_credential_or_vm_configuration(self) -> None:
        forbidden_substrings = (
            "ssh",
            "known_hosts",
            "private_key",
            "vmx",
            "vmrun",
            "password",
            "secret",
            "token",
        )
        for record in kali_operation_schema_records():
            serialized = repr(record).lower()
            for forbidden in forbidden_substrings:
                with self.subTest(identity=record.capability_identity, token=forbidden):
                    self.assertNotIn(forbidden, serialized)

    def test_dns_record_lookup_input_is_hostname_and_closed_record_type(
        self,
    ) -> None:
        schema = _dns_record_lookup_input_schema()
        names = {f.name: f for f in schema.fields}
        self.assertEqual(set(names), {"hostname", "dns_record_type"})
        self.assertEqual(
            names["dns_record_type"].enum_values, frozenset({"A", "AAAA", "CNAME"})
        )
        # PARTIAL, not COMPLETE: the real bound is enforced on the
        # *normalized* hostname, never the raw argument text, so no
        # max_length is stated for it.
        self.assertEqual(schema.completeness, PARTIAL)
        self.assertIsNone(names["hostname"].max_length)

    def test_kali_hostname_field_states_no_bound_on_the_raw_argument(self) -> None:
        """`.strip()` can discard arbitrarily much padding before the real
        253-character ceiling is ever checked, so the raw argument this
        field describes has no authoritative length bound of its own --
        stating one would misdescribe a bound on the normalized value as a
        bound on the raw one.
        """
        for schema in (
            _dns_record_lookup_input_schema(),
            _https_header_lookup_input_schema(),
        ):
            hostname_field = next(f for f in schema.fields if f.name == "hostname")
            with self.subTest(schema=schema):
                self.assertIsNone(hostname_field.max_length)

    def test_https_header_lookup_input_includes_resolved_address_as_partial(
        self,
    ) -> None:
        schema = _https_header_lookup_input_schema()
        names = {f.name for f in schema.fields}
        self.assertEqual(names, {"hostname", "resolved_address"})
        self.assertEqual(schema.completeness, PARTIAL)

    def test_kali_output_schema_is_a_bounded_ordered_line_family(self) -> None:
        """Kali output is `ORDERED_TEXT_LINES`, never `LABELLED_VALUES`: a
        reviewed Kali operation never produces a `ToolResult`, and its real
        `stdout_lines` is a plain, unlabelled, positionally-ordered tuple --
        not a family with synthesized `stdout_line_1`, `stdout_line_2`, ...
        keys.
        """
        schema = _kali_operation_output_schema()
        self.assertEqual(schema.channel, ORDERED_TEXT_LINES)
        self.assertEqual(len(schema.fields), 1)
        field = schema.fields[0]
        self.assertTrue(field.repeated)
        self.assertFalse(field.required)
        self.assertEqual(schema.completeness, PARTIAL)

    def test_ordered_text_lines_channel_rejects_a_non_repeated_field(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityOutputSchema(
                channel=ORDERED_TEXT_LINES,
                fields=(
                    ProductCapabilityField(
                        "exit_code", WHOLE_NUMBER_TEXT, required=True
                    ),
                ),
                completeness=PARTIAL,
            )

    def test_only_vmware_transport_kali_records_exist_for_dns_lookup_both_ways(
        self,
    ) -> None:
        records = {
            record.capability_identity: record
            for record in kali_operation_schema_records()
        }
        wsl_dns = records[
            kali_operation_identity(
                ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                ResearchKaliCommandTransport.WSL_KALI,
            )
        ]
        vmware_dns = records[
            kali_operation_identity(
                ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                ResearchKaliCommandTransport.VMWARE_KALI,
            )
        ]
        # Same logical input/output shape regardless of transport: transport
        # is execution plumbing, not a logical-shape fact.
        self.assertEqual(wsl_dns.input_schema, vmware_dns.input_schema)
        self.assertEqual(wsl_dns.output_schema, vmware_dns.output_schema)


class ExistingSuiteStillPassesTests(unittest.TestCase):
    """Requirements 30-33: confirm the pre-existing layers this milestone
    must not alter still behave exactly as before, imported directly here
    so a regression surfaces in this file too, not only in CI's full run.
    """

    def test_product_capability_catalog_is_unaffected_by_the_schema_module(
        self,
    ) -> None:
        from tools.ProductCapabilityCatalog import ProductCapabilityCatalog
        from tools.ProductCapabilityCatalogDefaults import (
            default_product_capability_catalog,
        )

        registry = _registry_with_local_tools()
        catalog = default_product_capability_catalog(registry)
        self.assertIsInstance(catalog, ProductCapabilityCatalog)
        self.assertTrue(
            catalog.described(tool_capability_identity(ToolCapability.CLOCK_READ))
        )


if __name__ == "__main__":
    unittest.main()
