"""The first tool whose argument selects its target, and the boundary that holds it.

Most of this file is about paths that must not work. That balance is deliberate:
a clock tool can only be wrong about the time, but a filesystem tool given a bad
argument returns a correct answer about the wrong thing, and nothing looks broken
when it does.

The link tests use real links in a temporary directory rather than mocks,
because the entire question is what the filesystem actually does. On the
development machine that distinction is not academic. Creating a symlink needs
elevation and fails with WinError 1314; creating a junction needs no privilege
at all — and a junction reports `is_symlink() == False` while `scandir` reports
it as an ordinary directory. The indirection an unprivileged attacker can
actually create is exactly the one a naive check misses, so it is tested with a
real junction and the symlink tests skip loudly when they cannot run.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from tools.FilesystemEntryKind import FilesystemEntryKind
from tools.FilesystemListTool import (
    MAX_SCANNED_ENTRIES,
    PAGE_SIZE,
    SUMMARY_VALUE_COUNT,
    FilesystemListTool,
)
from tools.FilesystemPathRefusal import FilesystemPathRefusal
from tools.FilesystemRoot import FilesystemRoot
from tools.ToolCapability import ToolCapability
from tools.ToolEffect import ToolEffect
from tools.ToolEvents import TOOL_STARTED
from tools.ToolExecutionService import ToolExecutionService
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRegistry import ToolRegistry
from tools.ToolResult import MAX_TOOL_VALUES

GRANT = frozenset({ToolEffect.READS_FILESYSTEM_METADATA})
SENTINEL_DIR = "private-investigation-8472"
#: Distinctive on purpose. "outside" would collide with the existing
#: `reaches_outside` payload key and make the absence assertion meaningless.
OUTSIDE_DIR = "elsewhere-9317"


def _make_junction(link: Path, target: Path) -> bool:
    """Create a directory junction, reporting whether the platform allowed it."""
    if os.name != "nt":
        return False
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    return link.is_junction()


def _make_symlink(link: Path, target: Path) -> bool:
    """Create a directory symlink, reporting whether the platform allowed it."""
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError, NotImplementedError:
        return False
    return link.is_symlink()


class FilesystemFixture(unittest.TestCase):
    """A real root on disk, because the questions here are about a filesystem."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.base = Path(self._temp.name).resolve()
        self.outside = self.base / OUTSIDE_DIR
        self.outside.mkdir()
        (self.outside / "secret.txt").write_text("secret", encoding="utf-8")
        self.root_path = self.base / "project"
        self.root_path.mkdir()
        (self.root_path / "readme.md").write_text("hello", encoding="utf-8")
        (self.root_path / "src").mkdir()
        (self.root_path / "src" / "main.py").write_text("x = 1", encoding="utf-8")
        (self.root_path / "src" / "nested").mkdir()
        self.root = FilesystemRoot(self.root_path, root_id="root-1")
        self.tool = FilesystemListTool(self.root)
        self.addCleanup(self._temp.cleanup)

    def invoke(self, **arguments: str) -> object:
        return self.tool.invoke(
            ToolInvocation(
                capability=ToolCapability.FILESYSTEM_LIST,
                authorized_effects=GRANT,
                arguments=tuple(arguments.items()),
            )
        )

    def values(self, **arguments: str) -> dict[str, str]:
        result = self.invoke(**arguments)
        self.assertTrue(result.succeeded, result.detail)
        return dict(result.values)

    def names(self, **arguments: str) -> list[str]:
        values = self.values(**arguments)
        return [
            value
            for key, value in values.items()
            if key.startswith("entry_") and key != "entry_count"
        ]


class RootConfigurationTests(unittest.TestCase):
    """No root, no capability. The root is never an argument."""

    def test_a_tool_cannot_be_built_without_a_root(self) -> None:
        with self.assertRaises(TypeError):
            FilesystemListTool(None)  # type: ignore[arg-type]

    def test_a_missing_directory_is_not_a_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ResearchError):
                FilesystemRoot(Path(temp) / "no-such-directory")

    def test_a_file_is_not_a_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "file.txt"
            target.write_text("x", encoding="utf-8")
            with self.assertRaises(ResearchError):
                FilesystemRoot(target)

    def test_a_root_needs_an_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ResearchError):
                FilesystemRoot(Path(temp), root_id="  ")

    def test_the_root_is_resolved_once_at_construction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = FilesystemRoot(Path(temp) / "." / "")

            self.assertTrue(root.path.is_absolute())
            self.assertEqual(root.path, Path(temp).resolve())

    def test_the_root_path_is_never_taken_from_an_invocation(self) -> None:
        """`root` is not an accepted argument name, so it cannot be supplied."""
        from tools.FilesystemListTool import ACCEPTED_ARGUMENTS

        self.assertEqual(ACCEPTED_ARGUMENTS, frozenset({"path", "offset"}))


class DescriptorTests(FilesystemFixture):
    def test_it_declares_the_filesystem_list_capability(self) -> None:
        self.assertIs(
            self.tool.descriptor.capability,
            ToolCapability.FILESYSTEM_LIST,
        )

    def test_it_declares_only_reading_filesystem_metadata(self) -> None:
        self.assertEqual(self.tool.descriptor.effects, GRANT)

    def test_it_does_not_borrow_the_local_state_effect(self) -> None:
        """Otherwise every existing grant would become disk enumeration."""
        self.assertNotIn(ToolEffect.READS_LOCAL_STATE, self.tool.descriptor.effects)

    def test_it_declares_no_effect_it_does_not_have(self) -> None:
        for absent in (
            ToolEffect.WRITES_LOCAL_STATE,
            ToolEffect.READS_NETWORK,
            ToolEffect.SPENDS_MODEL,
            ToolEffect.COMPUTES_LOCALLY,
        ):
            with self.subTest(effect=absent):
                self.assertNotIn(absent, self.tool.descriptor.effects)

    def test_it_is_read_only_and_reaches_nothing_outside(self) -> None:
        self.assertTrue(self.tool.descriptor.read_only)
        self.assertFalse(self.tool.descriptor.reaches_outside)


class ListingTests(FilesystemFixture):
    def test_the_root_itself_can_be_listed(self) -> None:
        names = self.names(path=".")

        self.assertIn("file:readme.md", names)
        self.assertIn("directory:src", names)

    def test_a_nested_directory_inside_the_root_can_be_listed(self) -> None:
        names = self.names(path="src")

        self.assertIn("file:main.py", names)
        self.assertIn("directory:nested", names)

    def test_forward_slashes_work_the_same_as_backslashes(self) -> None:
        self.assertEqual(self.names(path="src/nested"), self.names(path="src\\nested"))

    def test_each_entry_carries_its_kind(self) -> None:
        values = self.values(path=".")

        kinds = {
            value.split(":", 1)[0]
            for key, value in values.items()
            if "entry_" in key and key != "entry_count"
        }
        self.assertTrue(kinds <= {kind.value for kind in FilesystemEntryKind})

    def test_the_listing_does_not_recurse(self) -> None:
        """One level. `main.py` lives under src and must not appear at the root."""
        names = self.names(path=".")

        self.assertNotIn("file:main.py", names)

    def test_no_file_content_is_returned(self) -> None:
        (self.root_path / "secret.txt").write_text(
            "TOP-SECRET-CONTENT-8472", encoding="utf-8"
        )

        result = self.invoke(path=".")

        self.assertNotIn("TOP-SECRET-CONTENT-8472", str(result.values))
        self.assertNotIn("TOP-SECRET-CONTENT-8472", result.detail)

    def test_listing_a_file_is_refused(self) -> None:
        result = self.invoke(path="readme.md")

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.detail, "That is not a directory.")

    def test_a_missing_entry_is_refused(self) -> None:
        result = self.invoke(path="no-such-directory")

        self.assertFalse(result.succeeded)
        self.assertEqual(result.detail, "There is no such entry.")

    def test_an_empty_directory_lists_nothing_successfully(self) -> None:
        values = self.values(path="src/nested")

        self.assertEqual(values["entry_count"], "0")
        self.assertEqual(values["page_size"], "0")
        self.assertEqual(values["more_pages"], "false")

    def test_the_tool_never_writes_anything(self) -> None:
        before = sorted(entry.name for entry in os.scandir(self.root_path))

        self.invoke(path=".")

        self.assertEqual(
            sorted(entry.name for entry in os.scandir(self.root_path)),
            before,
        )


class BoundingTests(FilesystemFixture):
    """Bounded, deterministic, and without relaxing a shared limit."""

    def populate(self, count: int) -> None:
        target = self.root_path / "many"
        target.mkdir()
        for index in range(count):
            (target / f"file-{index:04d}.txt").write_text("x", encoding="utf-8")

    def test_the_page_size_comes_from_the_shared_result_budget(self) -> None:
        """Derived, so this tool cannot quietly outgrow every other tool's bound."""
        self.assertEqual(PAGE_SIZE, MAX_TOOL_VALUES - SUMMARY_VALUE_COUNT)

    def test_the_global_result_limit_was_not_raised(self) -> None:
        self.assertEqual(MAX_TOOL_VALUES, 20)

    def test_a_large_directory_never_exceeds_the_result_limit(self) -> None:
        self.populate(120)

        result = self.invoke(path="many")

        self.assertLessEqual(len(result.values), MAX_TOOL_VALUES)

    def test_the_true_count_is_reported_even_when_the_page_is_smaller(self) -> None:
        self.populate(120)

        values = self.values(path="many")

        self.assertEqual(values["entry_count"], "120")
        self.assertEqual(values["page_size"], str(PAGE_SIZE))
        self.assertEqual(values["more_pages"], "true")

    def test_truncation_is_reported_rather_than_silent(self) -> None:
        """A listing that quietly stopped says a directory is smaller than it is."""
        self.populate(120)

        self.assertEqual(self.values(path="many")["more_pages"], "true")

    def test_paging_is_deterministic_and_complete(self) -> None:
        self.populate(50)

        seen: list[str] = []
        offset = 0
        while True:
            values = self.values(path="many", offset=str(offset))
            seen.extend(
                value
                for key, value in values.items()
                if key.startswith("entry_") and key != "entry_count"
            )
            if values["more_pages"] != "true":
                break
            offset += int(values["page_size"])

        self.assertEqual(len(seen), 50)
        self.assertEqual(len(set(seen)), 50)

    def test_the_same_page_is_the_same_entries_every_time(self) -> None:
        self.populate(50)

        self.assertEqual(
            self.names(path="many", offset="15"),
            self.names(path="many", offset="15"),
        )

    def test_pages_do_not_overlap(self) -> None:
        self.populate(50)

        first = set(self.names(path="many", offset="0"))
        second = set(self.names(path="many", offset=str(PAGE_SIZE)))

        self.assertEqual(first & second, set())

    def test_ordering_does_not_depend_on_the_page_requested(self) -> None:
        """Sorting the whole set, not the page, is what makes paging stable."""
        self.populate(50)
        everything = []
        for offset in range(0, 50, PAGE_SIZE):
            everything.extend(self.names(path="many", offset=str(offset)))

        self.assertEqual(everything, sorted(everything, key=str.casefold))

    def test_an_offset_past_the_end_returns_an_empty_page_honestly(self) -> None:
        self.populate(20)

        values = self.values(path="many", offset="999")

        self.assertEqual(values["page_size"], "0")
        self.assertEqual(values["entry_count"], "20")
        self.assertEqual(values["more_pages"], "false")

    def test_a_small_directory_reports_no_further_pages(self) -> None:
        self.assertEqual(self.values(path=".")["more_pages"], "false")

    def test_the_scan_ceiling_is_bounded(self) -> None:
        self.assertLessEqual(MAX_SCANNED_ENTRIES, 10_000)

    def test_a_non_numeric_offset_is_refused(self) -> None:
        result = self.invoke(path=".", offset="abc")

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)

    def test_a_negative_offset_is_refused(self) -> None:
        """A negative slice start would page backwards from the end."""
        self.assertFalse(self.invoke(path=".", offset="-5").succeeded)


class PathEscapeTests(FilesystemFixture):
    """Every one of these must fail, and the reasons must stay distinguishable."""

    def refusal(self, path: str) -> FilesystemPathRefusal:
        refusal, resolved = self.root.locate(path)
        self.assertIsNone(resolved)
        return refusal

    def test_parent_traversal_cannot_leave_the_root(self) -> None:
        for path in ("..", "../..", f"../{OUTSIDE_DIR}", f"src/../../{OUTSIDE_DIR}"):
            with self.subTest(path=path):
                self.assertIs(self.refusal(path), FilesystemPathRefusal.ESCAPES_ROOT)

    def test_traversal_is_refused_through_the_tool_as_well(self) -> None:
        result = self.invoke(path=f"../{OUTSIDE_DIR}")

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.values, ())

    def test_traversal_does_not_reveal_the_outside_directory(self) -> None:
        result = self.invoke(path=f"../{OUTSIDE_DIR}")

        self.assertNotIn("secret.txt", str(result.values))
        self.assertNotIn("secret.txt", result.detail)

    def test_absolute_posix_paths_are_refused(self) -> None:
        for path in ("/", "/etc/passwd", "/Windows"):
            with self.subTest(path=path):
                self.assertIs(self.refusal(path), FilesystemPathRefusal.NOT_RELATIVE)

    def test_a_leading_slash_is_refused_even_though_windows_calls_it_relative(
        self,
    ) -> None:
        """On Windows `/Windows` inherits the root's drive and lands outside."""
        self.assertIs(self.refusal("/Windows"), FilesystemPathRefusal.NOT_RELATIVE)

    def test_drive_qualified_paths_are_refused(self) -> None:
        for path in ("C:\\Windows", "C:src", "D:", "c:/windows/system32"):
            with self.subTest(path=path):
                self.assertIs(self.refusal(path), FilesystemPathRefusal.NOT_RELATIVE)

    def test_unc_paths_are_refused(self) -> None:
        for path in ("\\\\server\\share", "\\\\server\\share\\file.txt"):
            with self.subTest(path=path):
                self.assertIs(self.refusal(path), FilesystemPathRefusal.NOT_RELATIVE)

    def test_extended_length_and_device_namespaces_are_refused(self) -> None:
        for path in ("\\\\?\\D:\\project", "\\\\.\\PhysicalDrive0"):
            with self.subTest(path=path):
                self.assertIs(self.refusal(path), FilesystemPathRefusal.NOT_RELATIVE)

    def test_stream_syntax_is_refused(self) -> None:
        """`README.md::$DATA` resolves to the plain file while `.name` keeps it."""
        for path in ("readme.md::$DATA", "src::$INDEX_ALLOCATION", "readme.md:hidden"):
            with self.subTest(path=path):
                self.assertIs(self.refusal(path), FilesystemPathRefusal.STREAM_SYNTAX)

    def test_reserved_device_names_are_refused(self) -> None:
        """`NUL` reports as existing inside every directory that is asked."""
        for path in ("NUL", "nul", "con", "CON.txt", "COM1", "src/nul"):
            with self.subTest(path=path):
                self.assertIs(self.refusal(path), FilesystemPathRefusal.RESERVED_DEVICE)

    def test_a_sibling_sharing_the_root_name_prefix_is_refused(self) -> None:
        """The prefix check that looks equivalent and is not."""
        sibling = self.base / f"{self.root_path.name}-secrets"
        sibling.mkdir()

        self.assertTrue(str(sibling).startswith(str(self.root_path)))
        self.assertFalse(self.root.contains(sibling))

    def test_containment_uses_resolution_rather_than_text(self) -> None:
        sibling = self.base / f"{self.root_path.name}-secrets"
        sibling.mkdir()

        self.assertIs(
            self.refusal(f"../{sibling.name}"),
            FilesystemPathRefusal.ESCAPES_ROOT,
        )

    def test_an_over_deep_path_is_refused(self) -> None:
        self.assertIs(
            self.refusal("/".join(["a"] * 40)),
            FilesystemPathRefusal.NOT_RELATIVE,
        )

    def test_an_enormous_path_argument_is_refused(self) -> None:
        self.assertIs(self.refusal("a" * 2_000), FilesystemPathRefusal.NOT_RELATIVE)

    def test_an_ordinary_relative_path_is_admitted(self) -> None:
        """The refusals must not be passing by refusing everything."""
        refusal, resolved = self.root.locate("src")

        self.assertIs(refusal, FilesystemPathRefusal.NONE)
        self.assertEqual(resolved, (self.root_path / "src").resolve())


class LinkTests(FilesystemFixture):
    """Real links, because the whole question is what the filesystem does."""

    def test_a_junction_escaping_the_root_is_refused_as_a_traversal_target(
        self,
    ) -> None:
        link = self.root_path / "escape"
        if not _make_junction(link, self.outside):
            self.skipTest("This platform did not allow creating a junction.")

        refusal, resolved = self.root.locate("escape")

        self.assertIs(refusal, FilesystemPathRefusal.LINK_COMPONENT)
        self.assertIsNone(resolved)

    def test_a_junction_is_listed_as_a_link_rather_than_a_directory(self) -> None:
        """scandir calls it a directory and not a symlink. Both are misleading."""
        link = self.root_path / "escape"
        if not _make_junction(link, self.outside):
            self.skipTest("This platform did not allow creating a junction.")

        names = self.names(path=".")

        self.assertIn("link:escape", names)
        self.assertNotIn("directory:escape", names)

    def test_listing_through_a_junction_reveals_nothing_outside(self) -> None:
        link = self.root_path / "escape"
        if not _make_junction(link, self.outside):
            self.skipTest("This platform did not allow creating a junction.")

        result = self.invoke(path="escape")

        self.assertFalse(result.succeeded)
        self.assertNotIn("secret.txt", str(result.values))

    def test_a_junction_as_a_middle_component_is_refused(self) -> None:
        """Proves the check runs per component, not only on the last one."""
        link = self.root_path / "escape"
        if not _make_junction(link, self.outside):
            self.skipTest("This platform did not allow creating a junction.")

        self.assertIs(
            self.root.locate("escape/secret.txt")[0],
            FilesystemPathRefusal.LINK_COMPONENT,
        )

    def test_a_junction_pointing_inside_the_root_is_still_not_followed(self) -> None:
        """Not following is the rule. Where it points does not earn an exception."""
        link = self.root_path / "inward"
        if not _make_junction(link, self.root_path / "src"):
            self.skipTest("This platform did not allow creating a junction.")

        self.assertIs(
            self.root.locate("inward")[0],
            FilesystemPathRefusal.LINK_COMPONENT,
        )

    def test_a_symlink_escaping_the_root_is_refused(self) -> None:
        link = self.root_path / "symescape"
        if not _make_symlink(link, self.outside):
            self.skipTest(
                "This platform did not allow creating a symlink. On Windows this "
                "needs elevation and fails with WinError 1314; the junction "
                "tests cover the unprivileged case."
            )

        self.assertIs(
            self.root.locate("symescape")[0],
            FilesystemPathRefusal.LINK_COMPONENT,
        )

    def test_a_symlink_is_listed_as_a_link(self) -> None:
        link = self.root_path / "symescape"
        if not _make_symlink(link, self.outside):
            self.skipTest(
                "This platform did not allow creating a symlink. On Windows this "
                "needs elevation and fails with WinError 1314."
            )

        self.assertIn("link:symescape", self.names(path="."))

    def test_a_link_is_not_classified_by_is_symlink_alone(self) -> None:
        """A junction answers False to is_symlink; the reparse attribute does not."""
        link = self.root_path / "escape"
        if not _make_junction(link, self.outside):
            self.skipTest("This platform did not allow creating a junction.")

        self.assertFalse(link.is_symlink())
        with os.scandir(self.root_path) as entries:
            kinds = {entry.name: FilesystemEntryKind.of(entry) for entry in entries}

        self.assertIs(kinds["escape"], FilesystemEntryKind.LINK)

    def test_a_link_kind_is_never_treated_as_listable(self) -> None:
        self.assertFalse(FilesystemEntryKind.LINK.listable)
        self.assertTrue(FilesystemEntryKind.LINK.is_indirection)

    def test_the_root_itself_cannot_be_a_link(self) -> None:
        link = self.base / "root-link"
        if not _make_junction(link, self.outside):
            self.skipTest("This platform did not allow creating a junction.")

        with self.assertRaises(ResearchError):
            FilesystemRoot(link)


class ArgumentContractTests(FilesystemFixture):
    def test_a_missing_path_is_declined_after_running(self) -> None:
        result = self.invoke()

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.values, ())

    def test_an_unknown_argument_is_declined(self) -> None:
        result = self.invoke(path=".", depth="5")

        self.assertFalse(result.succeeded)

    def test_a_root_argument_is_not_accepted(self) -> None:
        """Accepting it would be unrestricted filesystem authority with steps."""
        result = self.invoke(path=".", root=str(self.outside))

        self.assertFalse(result.succeeded)

    def test_a_recursive_argument_is_not_accepted(self) -> None:
        self.assertFalse(self.invoke(path=".", recursive="true").succeeded)

    def test_declining_is_not_dressed_up_as_a_refusal(self) -> None:
        self.assertTrue(self.invoke().performed)


class ErrorDisclosureTests(FilesystemFixture):
    """Messages help without becoming a second channel for the path."""

    def test_no_detail_quotes_the_requested_path(self) -> None:
        for path in (
            f"../{OUTSIDE_DIR}",
            "C:\\Windows",
            "no-such-directory",
            "readme.md",
        ):
            with self.subTest(path=path):
                detail = self.invoke(path=path).detail
                self.assertNotIn(path, detail)

    def test_no_detail_contains_the_root_path(self) -> None:
        for path in (".", f"../{OUTSIDE_DIR}", "no-such-directory"):
            with self.subTest(path=path):
                self.assertNotIn(str(self.root_path), self.invoke(path=path).detail)

    def test_no_detail_contains_a_windows_error_number(self) -> None:
        detail = self.invoke(path="no-such-directory").detail

        self.assertNotIn("WinError", detail)
        self.assertNotIn("Errno", detail)

    def test_containment_and_absence_stay_distinguishable(self) -> None:
        """A deliberate decision: the caller already knows the root."""
        self.assertNotEqual(
            self.invoke(path=f"../{OUTSIDE_DIR}").detail,
            self.invoke(path="no-such-directory").detail,
        )

    def test_every_refusal_has_a_fixed_sentence(self) -> None:
        from tools.FilesystemListTool import _DETAILS

        for refusal in FilesystemPathRefusal:
            if refusal.admitted:
                continue
            with self.subTest(refusal=refusal):
                self.assertTrue(_DETAILS[refusal].strip())

    def test_no_refusal_sentence_leaks_the_enum_value(self) -> None:
        from tools.FilesystemListTool import _DETAILS

        for refusal, detail in _DETAILS.items():
            with self.subTest(refusal=refusal):
                self.assertNotIn(refusal.value, detail)


class AuthorizationTests(FilesystemFixture):
    """The gate, exercised on the first capability that can reach real data."""

    def setUp(self) -> None:
        super().setUp()
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.registry = ToolRegistry()
        self.registry.register(self.tool)
        self.service = ToolExecutionService(
            self.registry,
            event_bus=self.event_bus,
            id_factory=lambda: "request-1",
        )

    def execute(self, authorized: frozenset[ToolEffect], **arguments: str) -> object:
        return self.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.FILESYSTEM_LIST,
                authorized_effects=authorized,
                arguments=tuple(arguments.items()),
            )
        )

    def test_an_empty_grant_is_refused_before_the_tool_runs(self) -> None:
        outcome = self.execute(frozenset(), path=".")

        self.assertFalse(outcome.result.performed)
        self.assertIs(outcome.failure_kind, ToolFailureKind.UNAUTHORIZED_EFFECT)

    def test_a_local_state_grant_does_not_authorize_the_filesystem(self) -> None:
        """The reason this is a separate effect at all."""
        outcome = self.execute(frozenset({ToolEffect.READS_LOCAL_STATE}), path=".")

        self.assertIs(outcome.failure_kind, ToolFailureKind.UNAUTHORIZED_EFFECT)
        self.assertFalse(outcome.result.performed)

    def test_an_unauthorized_call_reads_no_directory(self) -> None:
        outcome = self.execute(frozenset(), path=".")

        self.assertEqual(outcome.result.values, ())
        self.assertNotIn(TOOL_STARTED, [event.name for event in self.events])

    def test_the_correct_grant_authorizes_it(self) -> None:
        outcome = self.execute(GRANT, path=".")

        self.assertTrue(outcome.authorized)
        self.assertTrue(outcome.result.succeeded)

    def test_the_registry_resolves_the_exact_capability(self) -> None:
        self.assertIsInstance(
            self.registry.resolve(ToolCapability.FILESYSTEM_LIST),
            FilesystemListTool,
        )


class TelemetryPrivacyTests(FilesystemFixture):
    """Results go to the caller. Events go to logs that outlive the question."""

    def setUp(self) -> None:
        super().setUp()
        (self.root_path / SENTINEL_DIR).mkdir()
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        registry = ToolRegistry()
        registry.register(self.tool)
        self.service = ToolExecutionService(
            registry,
            event_bus=self.event_bus,
            id_factory=lambda: "request-1",
        )

    def run_listing(self, path: str = ".") -> None:
        self.service.execute(
            ToolInvocation(
                capability=ToolCapability.FILESYSTEM_LIST,
                authorized_effects=GRANT,
                arguments=(("path", path),),
            )
        )

    def payloads(self) -> str:
        return str([event.payload for event in self.events])

    def test_no_event_carries_an_entry_name(self) -> None:
        self.run_listing()

        self.assertNotIn(SENTINEL_DIR, self.payloads())

    def test_no_event_carries_the_root_path(self) -> None:
        self.run_listing()

        self.assertNotIn(str(self.root_path), self.payloads())
        self.assertNotIn(self.root_path.name, self.payloads())

    def test_no_event_carries_the_requested_path(self) -> None:
        self.run_listing(f"{SENTINEL_DIR}")

        self.assertNotIn(SENTINEL_DIR, self.payloads())

    def test_a_refused_path_does_not_reach_telemetry_either(self) -> None:
        self.run_listing(f"../{OUTSIDE_DIR}/{SENTINEL_DIR}")

        self.assertNotIn(SENTINEL_DIR, self.payloads())
        self.assertNotIn(OUTSIDE_DIR, self.payloads())

    def test_events_still_count_what_happened(self) -> None:
        """Path-free does not mean signal-free."""
        self.run_listing()

        completed = [event for event in self.events if event.name == "tool.completed"]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload["capability"], "filesystem_list")
        self.assertGreater(completed[0].payload["value_count"], 0)

    def test_the_root_id_stands_in_for_the_root_path(self) -> None:
        self.assertEqual(self.tool.root_id, "root-1")
        self.assertNotIn(str(self.root_path), self.tool.root_id)

    def test_path_depth_is_shape_without_content(self) -> None:
        self.assertEqual(self.root.depth_of("src/nested"), 2)
        self.assertEqual(self.root.depth_of("."), 0)


class CapabilityScopeTests(unittest.TestCase):
    """What this milestone deliberately did not build."""

    def test_no_read_write_or_execute_capability_exists(self) -> None:
        names = {capability.value for capability in ToolCapability}

        for forbidden in (
            "filesystem_read",
            "filesystem_write",
            "filesystem_delete",
            "filesystem_execute",
            "shell",
            "process",
        ):
            with self.subTest(capability=forbidden):
                self.assertNotIn(forbidden, names)

    def test_the_tool_exposes_no_content_reading_method(self) -> None:
        for forbidden in ("read", "read_text", "read_bytes", "open", "cat"):
            with self.subTest(method=forbidden):
                self.assertFalse(hasattr(FilesystemListTool, forbidden))

    def test_the_tool_module_never_opens_a_file(self) -> None:
        source = (SRC_DIR / "tools" / "FilesystemListTool.py").read_text(
            encoding="utf-8"
        )

        for forbidden in ("open(", "read_text", "read_bytes", "subprocess", "walk("):
            with self.subTest(construct=forbidden):
                self.assertNotIn(forbidden, source)

    def test_no_filesystem_module_imports_a_process_launcher(self) -> None:
        for name in (
            "FilesystemListTool.py",
            "FilesystemRoot.py",
            "FilesystemEntryKind.py",
        ):
            source = (SRC_DIR / "tools" / name).read_text(encoding="utf-8")
            with self.subTest(module=name):
                self.assertNotIn("import subprocess", source)
                self.assertNotIn("os.system", source)


if __name__ == "__main__":
    unittest.main()
