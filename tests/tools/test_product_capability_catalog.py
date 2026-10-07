"""A capability catalog describes; it never authorizes, executes, or mutates.

CAPABILITY REGISTERED != CAPABILITY PERMITTED is the one rule this whole
file exists to prove. Every test below either shows the catalog has no way
to grant, consume, or even gesture at execution authority, or shows that
its own construction and lookup never touch a process or the network --
locally, or through the Kali/VMware/WSL path its Kali-side records merely
describe.
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
from tools.ProductCapabilityCatalog import ProductCapabilityCatalog
from tools.ProductCapabilityCatalogDefaults import (
    default_product_capability_catalog,
    kali_operation_capability_records,
    kali_operation_identity,
    local_tool_capability_records,
    tool_capability_identity,
)
from tools.ProductCapabilityRecord import (
    ProductCapabilityCategory,
    ProductCapabilityRecord,
)
from tools.TextStatisticsTool import TextStatisticsTool
from tools.ToolCapability import ToolCapability
from tools.ToolRegistry import ToolRegistry

NEW_MODULE_PATHS = (
    SRC_DIR / "tools" / "ProductCapabilityRecord.py",
    SRC_DIR / "tools" / "ProductCapabilityCatalog.py",
    SRC_DIR / "tools" / "ProductCapabilityCatalogDefaults.py",
)

# Names that would signal this layer had grown an execution or mutation
# capability it must never have. Checked structurally, not by trying every
# call, because an absent method cannot be invoked by any caller -- chat,
# model, or otherwise -- no matter what that caller is told.
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


def _registry_with_two_local_tools() -> ToolRegistry:
    return ToolRegistry((ClockReadTool(), TextStatisticsTool()))


def _minimal_record(identity: str = "tool:clock_read") -> ProductCapabilityRecord:
    return ProductCapabilityRecord(
        identity=identity,
        display_name="Clock Read",
        category=ProductCapabilityCategory.LOCAL_TOOL,
        requires_network=False,
        requires_credentials=False,
        target_scope_relevant=False,
        destructive=False,
    )


class NoProcessOrNetworkSideEffectTests(unittest.TestCase):
    """Requirements 1, 2, 14: construction and lookup touch nothing real."""

    def test_catalog_construction_has_zero_process_or_network_side_effects(
        self,
    ) -> None:
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            ProductCapabilityCatalog((_minimal_record(),))
        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_default_catalog_including_kali_records_has_zero_side_effects(
        self,
    ) -> None:
        """Covers requirement 14: the Kali/VMware/WSL/SSH path is only
        described here (named constants, enum values) -- never touched.
        """
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            registry = _registry_with_two_local_tools()
            catalog = default_product_capability_catalog(registry)
            for identity in catalog.identities:
                catalog.lookup(identity)
        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()

    def test_lookup_on_an_already_built_catalog_has_zero_side_effects(self) -> None:
        catalog = ProductCapabilityCatalog(kali_operation_capability_records())
        with (
            patch("subprocess.run") as run,
            patch("subprocess.Popen") as popen,
            patch("socket.getaddrinfo") as getaddrinfo,
        ):
            for identity in catalog.identities:
                self.assertTrue(catalog.described(identity))
                catalog.lookup(identity)
            catalog.lookup("kali:dns_record_lookup:does_not_exist")
        run.assert_not_called()
        popen.assert_not_called()
        getaddrinfo.assert_not_called()


class NoAuthorityTests(unittest.TestCase):
    """Requirements 3, 4, 10, 11: a description is never authority."""

    def test_record_and_catalog_expose_no_execution_or_mutation_method(self) -> None:
        for owner in (ProductCapabilityRecord, ProductCapabilityCatalog):
            for forbidden in FORBIDDEN_METHOD_NAMES:
                with self.subTest(owner=owner.__name__, method=forbidden):
                    self.assertFalse(
                        hasattr(owner, forbidden),
                        f"{owner.__name__} must not expose a '{forbidden}' method.",
                    )

    def test_repeated_lookup_of_the_same_identity_never_consumes_anything(
        self,
    ) -> None:
        """Unlike a one-shot Kali authorization, a description is reusable:
        looking it up a second (or tenth) time returns the identical record,
        proving lookup cannot consume anything.
        """
        catalog = ProductCapabilityCatalog(kali_operation_capability_records())
        identity = kali_operation_identity(
            ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            ResearchKaliCommandTransport.WSL_KALI,
        )
        first = catalog.lookup(identity)
        for _ in range(10):
            self.assertEqual(catalog.lookup(identity), first)
        self.assertTrue(catalog.described(identity))

    def test_availability_reference_is_inert_text_never_a_live_check(self) -> None:
        """Requirement 11: presence/availability description != permission.

        The field is plain text to read, not a callable a caller could
        invoke hoping it means "ready to run" -- calling a string raises.
        """
        for record in kali_operation_capability_records():
            with self.subTest(identity=record.identity):
                self.assertIsInstance(record.availability_reference, str)
                with self.assertRaises(TypeError):
                    record.availability_reference()  # type: ignore[operator]

    def test_a_described_credential_requiring_capability_grants_no_credential(
        self,
    ) -> None:
        """Requirement 10: capability presence (even naming a credential
        requirement) never implies permission or supplies one.
        """
        record = ProductCapabilityCatalog(kali_operation_capability_records()).lookup(
            kali_operation_identity(
                ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                ResearchKaliCommandTransport.VMWARE_KALI,
            )
        )
        assert record is not None
        self.assertTrue(record.requires_credentials)
        # Nothing on the record type can ever hold, name, or return a
        # credential value -- there is no such field to begin with.
        field_names = {field.name for field in dataclasses.fields(record)}
        for forbidden in ("credential", "secret", "password", "token", "key"):
            self.assertNotIn(forbidden, field_names)


class DeterministicFailureTests(unittest.TestCase):
    """Requirements 5, 6: duplicates and unknowns both fail predictably."""

    def test_duplicate_identities_fail_deterministically(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityCatalog((_minimal_record(), _minimal_record()))

    def test_an_unknown_identity_fails_closed_not_open(self) -> None:
        catalog = ProductCapabilityCatalog((_minimal_record(),))
        self.assertIsNone(catalog.lookup("tool:not_a_real_capability"))
        self.assertFalse(catalog.described("tool:not_a_real_capability"))

    def test_empty_or_non_string_identity_lookup_is_refused(self) -> None:
        catalog = ProductCapabilityCatalog((_minimal_record(),))
        with self.assertRaises(ResearchError):
            catalog.lookup("")
        with self.assertRaises(ResearchError):
            catalog.lookup(None)  # type: ignore[arg-type]


class ImmutabilityTests(unittest.TestCase):
    """Requirement 7: entries cannot change after construction."""

    def test_record_fields_cannot_be_reassigned(self) -> None:
        record = _minimal_record()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.display_name = "Something else"  # type: ignore[misc]

    def test_catalog_has_no_way_to_add_or_remove_after_construction(self) -> None:
        catalog = ProductCapabilityCatalog((_minimal_record(),))
        original = catalog.identities
        # No public method exists to mutate the catalog; constructing a
        # second one with an overlapping identity does not alter the first.
        ProductCapabilityCatalog((_minimal_record("tool:other"),))
        self.assertEqual(catalog.identities, original)


class UntrustedInputCannotInjectATool(unittest.TestCase):
    """Requirements 8, 9: no request/model/chat path can register a tool."""

    def test_the_catalog_constructor_is_the_only_way_in_and_is_code_typed(
        self,
    ) -> None:
        """The constructor accepts only a tuple of already-built, bounded
        `ProductCapabilityRecord` values -- never a string, dict, or
        anything that free-form request metadata or model output could be.
        """
        for bad_input in ("metadata string", {"capability": "x"}, 42, None):
            with self.subTest(bad_input=bad_input):
                with self.assertRaises(ResearchError):
                    ProductCapabilityCatalog(bad_input)  # type: ignore[arg-type]

    def test_a_non_record_in_the_tuple_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityCatalog(({"identity": "tool:clock_read"},))  # type: ignore[arg-type]

    def test_new_modules_never_import_chat_model_or_request_surfaces(self) -> None:
        """Structural proof requirements 8/9 hold by construction: these
        modules cannot read a `BrainRequest`, chat text, or model output
        because they never import anything that carries one.
        """
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


class CapabilityPresenceIsNotPermissionTests(unittest.TestCase):
    """Requirement 10 (direct form): describing != permitting, by construction."""

    def test_an_absent_local_tool_capability_is_simply_absent(self) -> None:
        """A registry with no filesystem root configured has no filesystem
        capability -- the catalog correctly describes fewer tools, rather
        than describing one as present-but-forbidden.
        """
        registry = ToolRegistry((ClockReadTool(),))
        catalog = ProductCapabilityCatalog(local_tool_capability_records(registry))
        self.assertEqual(
            catalog.identities, (tool_capability_identity(ToolCapability.CLOCK_READ),)
        )
        self.assertFalse(
            catalog.described(tool_capability_identity(ToolCapability.FILESYSTEM_READ))
        )

    def test_catalog_lookup_result_type_has_no_authority_bearing_field(self) -> None:
        for record in kali_operation_capability_records():
            field_names = {field.name for field in dataclasses.fields(record)}
            with self.subTest(identity=record.identity):
                for forbidden in (
                    "authorization_id",
                    "authorized",
                    "scope_revision_id",
                    "operation_digest",
                ):
                    self.assertNotIn(forbidden, field_names)


class HonestKaliOperationCoverageTests(unittest.TestCase):
    """The catalog describes only combinations a real adapter accepts."""

    def test_https_header_lookup_over_vmware_kali_is_not_described(self) -> None:
        """VmwareKaliOperationProcessAdapter accepts only the reviewed dig
        plan; describing HTTPS over VMware here would claim a capability
        that does not actually exist in production.
        """
        catalog = ProductCapabilityCatalog(kali_operation_capability_records())
        identity = kali_operation_identity(
            ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
            ResearchKaliCommandTransport.VMWARE_KALI,
        )
        self.assertFalse(catalog.described(identity))

    def test_exactly_the_three_executable_kali_combinations_are_described(
        self,
    ) -> None:
        catalog = ProductCapabilityCatalog(kali_operation_capability_records())
        self.assertEqual(
            set(catalog.identities),
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

    def test_only_vmware_transport_requires_credentials(self) -> None:
        catalog = ProductCapabilityCatalog(kali_operation_capability_records())
        for identity in catalog.identities:
            record = catalog.lookup(identity)
            assert record is not None
            with self.subTest(identity=identity):
                self.assertEqual(
                    record.requires_credentials,
                    identity.endswith(":vmware_kali"),
                )


class LocalToolProjectionTests(unittest.TestCase):
    """The local-tool projection reads real descriptors, never a copy."""

    def test_network_flag_is_derived_from_the_real_descriptor_effects(self) -> None:
        registry = _registry_with_two_local_tools()
        records = {
            record.identity: record
            for record in local_tool_capability_records(registry)
        }
        clock = records[tool_capability_identity(ToolCapability.CLOCK_READ)]
        self.assertFalse(clock.requires_network)
        self.assertFalse(clock.destructive)
        self.assertEqual(clock.category, ProductCapabilityCategory.LOCAL_TOOL)

    def test_an_identity_is_rejected_for_the_none_capability(self) -> None:
        with self.assertRaises(ResearchError):
            tool_capability_identity(ToolCapability.NONE)

    def test_kali_identity_rejects_non_enum_arguments(self) -> None:
        with self.assertRaises(ResearchError):
            kali_operation_identity("dns_record_lookup", "wsl_kali")  # type: ignore[arg-type]

    def test_an_empty_registry_yields_no_local_tool_records_without_crashing(
        self,
    ) -> None:
        """An explicitly requested edge case: zero registered tools must
        describe zero local-tool capabilities, not raise or fabricate one.
        """
        empty_registry = ToolRegistry()

        records = local_tool_capability_records(empty_registry)

        self.assertEqual(records, ())
        catalog = default_product_capability_catalog(empty_registry)
        self.assertEqual(len(catalog), len(kali_operation_capability_records()))


class ProductCapabilityRecordValidationTests(unittest.TestCase):
    """Every `__post_init__` guard is exercised directly, not merely trusted.

    Each case below constructs one otherwise-valid record with exactly one
    field pushed outside its bound, so a future change that silently
    weakened or deleted any single check would fail exactly one of these,
    rather than passing the whole suite unnoticed.
    """

    def _kwargs(self, **override: object) -> dict[str, object]:
        base: dict[str, object] = {
            "identity": "tool:clock_read",
            "display_name": "Clock Read",
            "category": ProductCapabilityCategory.LOCAL_TOOL,
            "requires_network": False,
            "requires_credentials": False,
            "target_scope_relevant": False,
            "destructive": False,
        }
        base.update(override)
        return base

    def test_empty_or_whitespace_identity_is_rejected(self) -> None:
        for bad in ("", "   "):
            with self.subTest(identity=bad):
                with self.assertRaises(ResearchError):
                    ProductCapabilityRecord(**self._kwargs(identity=bad))

    def test_empty_display_name_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityRecord(**self._kwargs(display_name=""))

    def test_control_characters_in_identity_are_rejected(self) -> None:
        for bad in ("tool:a\x00b", "tool:a\rb", "tool:a\nb"):
            with self.subTest(identity=bad):
                with self.assertRaises(ResearchError):
                    ProductCapabilityRecord(**self._kwargs(identity=bad))

    def test_overlong_fields_are_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityRecord(**self._kwargs(identity="x" * 101))
        with self.assertRaises(ResearchError):
            ProductCapabilityRecord(**self._kwargs(display_name="x" * 151))
        with self.assertRaises(ResearchError):
            ProductCapabilityRecord(**self._kwargs(version="x" * 51))
        with self.assertRaises(ResearchError):
            ProductCapabilityRecord(**self._kwargs(availability_reference="x" * 301))

    def test_non_enum_category_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityRecord(**self._kwargs(category="local_tool"))

    def test_non_boolean_flags_are_rejected(self) -> None:
        for field_name in (
            "requires_network",
            "requires_credentials",
            "target_scope_relevant",
            "destructive",
        ):
            with self.subTest(field=field_name):
                with self.assertRaises(ResearchError):
                    ProductCapabilityRecord(**self._kwargs(**{field_name: 1}))

    def test_timeout_bool_is_rejected_even_though_bool_is_an_int_subclass(
        self,
    ) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityRecord(**self._kwargs(timeout_seconds=True))

    def test_timeout_out_of_bounds_is_rejected(self) -> None:
        for bad in (0, -1, 3601):
            with self.subTest(timeout_seconds=bad):
                with self.assertRaises(ResearchError):
                    ProductCapabilityRecord(**self._kwargs(timeout_seconds=bad))

    def test_retry_count_bool_is_rejected_even_though_bool_is_an_int_subclass(
        self,
    ) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityRecord(**self._kwargs(retry_count=True))

    def test_negative_retry_count_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            ProductCapabilityRecord(**self._kwargs(retry_count=-1))

    def test_zero_retry_count_is_accepted(self) -> None:
        record = ProductCapabilityRecord(**self._kwargs(retry_count=0))
        self.assertEqual(record.retry_count, 0)

    def test_a_fully_populated_valid_record_constructs_cleanly(self) -> None:
        record = ProductCapabilityRecord(
            **self._kwargs(
                version="DiG 9.",
                timeout_seconds=30.0,
                retry_count=0,
                availability_reference="always available",
            )
        )
        self.assertEqual(record.version, "DiG 9.")


if __name__ == "__main__":
    unittest.main()
