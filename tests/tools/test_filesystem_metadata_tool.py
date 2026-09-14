"""Facts about one entry, without the ability to read what is inside it.

That sentence is the whole boundary this capability sits on, so most of these
tests are about the second half. There are source-level assertions that the
implementation contains no way to open, read, hash, sniff, walk, glob, write or
execute anything, because the dangerous version of this tool is not one that
fails — it is one that quietly grows a convenience.

The path tests are deliberately not a copy of the listing tests. Admission is
`FilesystemRoot.locate` for both tools, and duplicating its whole suite here
would test the same code twice while proving nothing about this one. What is
tested here is that this tool actually delegates, that the reparse rule reaches
the final component, and that the second stat is re-checked rather than trusted.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from eventbus.Event import Event
from eventbus.EventBus import EventBus
from tools.FilesystemEntryKind import FilesystemEntryKind
from tools.FilesystemMetadataTool import FilesystemMetadataTool
from tools.FilesystemPathRefusal import FilesystemPathRefusal
from tools.FilesystemRoot import FilesystemRoot
from tools.ToolCapability import ToolCapability
from tools.ToolDisposition import ToolDisposition
from tools.ToolEffect import ToolEffect
from tools.ToolEvents import TOOL_STARTED
from tools.ToolExecutionService import ToolExecutionService
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRegistry import ToolRegistry
from tools.ToolResult import MAX_TOOL_VALUES
from tools.ToolRuntime import ToolRuntime

GRANT = frozenset({ToolEffect.READS_FILESYSTEM_METADATA})

#: Distinctive on purpose. A sentinel like "name" or "size" would collide with
#: the audit field labels and make an absence assertion pass for the wrong
#: reason.
SENTINEL_ENTRY = "zz-oracle-sentinel-77421.txt"
SENTINEL_OUTSIDE = "zz-outside-sentinel-90853"
BS = chr(92)


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


class MetadataFixture(unittest.TestCase):
    """A real root on disk, with one file, one folder and one nested entry."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.base = Path(self._temp.name).resolve()
        self.outside = self.base / SENTINEL_OUTSIDE
        self.outside.mkdir()
        (self.outside / "secret.txt").write_text("secret", encoding="utf-8")
        self.root_path = self.base / "project"
        self.root_path.mkdir()
        self.file = self.root_path / "readme.md"
        self.file.write_text("hello world", encoding="utf-8")
        (self.root_path / "src").mkdir()
        (self.root_path / "src" / "main.py").write_text("x = 1", encoding="utf-8")
        self.root = FilesystemRoot(self.root_path, root_id="workspace")
        self.tool = FilesystemMetadataTool(self.root)
        self.addCleanup(self._temp.cleanup)

    def invoke(self, **arguments: str) -> object:
        return self.tool.invoke(
            ToolInvocation(
                capability=ToolCapability.FILESYSTEM_METADATA,
                authorized_effects=GRANT,
                arguments=tuple(arguments.items()),
            )
        )

    def values(self, **arguments: str) -> dict[str, str]:
        result = self.invoke(**arguments)
        self.assertTrue(result.succeeded, result.detail)
        return dict(result.values)


class DescriptorTests(MetadataFixture):
    def test_it_declares_the_metadata_capability(self) -> None:
        self.assertIs(
            self.tool.descriptor.capability,
            ToolCapability.FILESYSTEM_METADATA,
        )

    def test_it_declares_only_reading_filesystem_metadata(self) -> None:
        self.assertEqual(self.tool.descriptor.effects, GRANT)

    def test_it_reuses_the_existing_effect_rather_than_a_broader_one(self) -> None:
        for absent in (
            ToolEffect.READS_LOCAL_STATE,
            ToolEffect.WRITES_LOCAL_STATE,
            ToolEffect.READS_NETWORK,
            ToolEffect.SPENDS_MODEL,
            ToolEffect.COMPUTES_LOCALLY,
        ):
            with self.subTest(effect=absent):
                self.assertNotIn(absent, self.tool.descriptor.effects)

    def test_it_shares_the_effect_with_listing(self) -> None:
        """One scope, one effect. Two would suggest two boundaries."""
        from tools.FilesystemListTool import FilesystemListTool

        self.assertEqual(
            self.tool.descriptor.effects,
            FilesystemListTool(self.root).descriptor.effects,
        )

    def test_it_is_read_only_and_reaches_nothing_outside(self) -> None:
        self.assertTrue(self.tool.descriptor.read_only)
        self.assertFalse(self.tool.descriptor.reaches_outside)

    def test_it_accepts_exactly_one_argument(self) -> None:
        from tools.FilesystemMetadataTool import ACCEPTED_ARGUMENTS

        self.assertEqual(ACCEPTED_ARGUMENTS, frozenset({"path"}))

    def test_a_tool_cannot_be_built_without_a_root(self) -> None:
        with self.assertRaises(TypeError):
            FilesystemMetadataTool(None)  # type: ignore[arg-type]


class FileMetadataTests(MetadataFixture):
    def test_a_regular_file_is_described(self) -> None:
        values = self.values(path="readme.md")

        self.assertEqual(values["name"], "readme.md")
        self.assertEqual(values["kind"], "file")

    def test_the_size_is_the_exact_byte_length(self) -> None:
        self.assertEqual(self.values(path="readme.md")["size_bytes"], "11")

    def test_an_empty_file_reports_zero_rather_than_nothing(self) -> None:
        (self.root_path / "empty.txt").write_text("", encoding="utf-8")

        self.assertEqual(self.values(path="empty.txt")["size_bytes"], "0")

    def test_the_size_counts_bytes_not_characters(self) -> None:
        (self.root_path / "utf.txt").write_text("é" * 5, encoding="utf-8")

        self.assertEqual(self.values(path="utf.txt")["size_bytes"], "10")

    def test_a_nested_file_inside_the_root_is_described(self) -> None:
        values = self.values(path="src/main.py")

        self.assertEqual(values["name"], "main.py")
        self.assertEqual(values["kind"], "file")
        self.assertEqual(values["size_bytes"], "5")

    def test_the_result_names_its_own_capability(self) -> None:
        self.assertIs(
            self.invoke(path="readme.md").capability,
            ToolCapability.FILESYSTEM_METADATA,
        )


class TimestampTests(MetadataFixture):
    def test_the_modification_time_is_utc_with_an_explicit_offset(self) -> None:
        stamp = self.values(path="readme.md")["modified_utc"]

        self.assertTrue(stamp.endswith("+00:00"))
        parsed = datetime.fromisoformat(stamp)
        self.assertEqual(parsed.tzinfo, UTC)

    def test_the_modification_time_is_whole_seconds(self) -> None:
        """Filesystems disagree below a second; a volume-dependent field cannot
        be compared."""
        stamp = self.values(path="readme.md")["modified_utc"]

        self.assertNotIn(".", stamp)
        self.assertEqual(len(stamp), len("2026-08-24T00:00:00+00:00"))

    def test_the_modification_time_matches_the_filesystem(self) -> None:
        expected = datetime.fromtimestamp(self.file.lstat().st_mtime, tz=UTC)

        self.assertEqual(
            self.values(path="readme.md")["modified_utc"],
            expected.isoformat(timespec="seconds"),
        )

    def test_the_timestamp_is_not_locale_formatted(self) -> None:
        stamp = self.values(path="readme.md")["modified_utc"]

        for month in ("Jan", "Feb", "Aug", "AM", "PM"):
            with self.subTest(token=month):
                self.assertNotIn(month, stamp)

    def test_no_creation_time_is_claimed(self) -> None:
        """Creation time is not portable, so it is not offered as though it were."""
        values = self.values(path="readme.md")

        for absent in ("created", "created_utc", "birth", "ctime"):
            with self.subTest(field=absent):
                self.assertNotIn(absent, values)


class DirectoryMetadataTests(MetadataFixture):
    def test_a_directory_is_described(self) -> None:
        values = self.values(path="src")

        self.assertEqual(values["name"], "src")
        self.assertEqual(values["kind"], "directory")

    def test_a_directory_is_given_no_size_at_all(self) -> None:
        """Its stat size is bookkeeping, not the size of what is inside it."""
        self.assertNotIn("size_bytes", self.values(path="src"))

    def test_a_directory_reports_no_fabricated_recursive_size(self) -> None:
        values = self.values(path="src")

        for invented in ("size_bytes", "total_size", "recursive_size", "bytes"):
            with self.subTest(field=invented):
                self.assertNotIn(invented, values)

    def test_a_directory_reports_no_child_information(self) -> None:
        values = self.values(path="src")

        for invented in ("entry_count", "children", "entries", "file_count"):
            with self.subTest(field=invented):
                self.assertNotIn(invented, values)

    def test_describing_a_directory_does_not_name_its_children(self) -> None:
        result = self.invoke(path="src")

        self.assertNotIn("main.py", str(result.values))

    def test_the_root_itself_can_be_described(self) -> None:
        values = self.values(path=".")

        self.assertEqual(values["kind"], "directory")
        self.assertNotIn("size_bytes", values)

    def test_only_a_file_kind_carries_a_byte_size(self) -> None:
        for kind in FilesystemEntryKind:
            with self.subTest(kind=kind):
                self.assertIs(kind.has_byte_size, kind is FilesystemEntryKind.FILE)


class PathAdmissionTests(MetadataFixture):
    """Delegated to FilesystemRoot; these prove the delegation, not the rules."""

    def refusal_detail(self, path: str) -> str:
        result = self.invoke(path=path)
        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.values, ())
        return result.detail

    def test_traversal_out_of_the_root_is_refused(self) -> None:
        for path in (
            "..",
            "../..",
            f"../{SENTINEL_OUTSIDE}",
            f"src/../../{SENTINEL_OUTSIDE}",
        ):
            with self.subTest(path=path):
                self.assertIn("outside the authorized root", self.refusal_detail(path))

    def test_absolute_paths_are_refused(self) -> None:
        for path in ("/", "/etc/passwd", "/Windows"):
            with self.subTest(path=path):
                self.assertIn("must be relative", self.refusal_detail(path))

    def test_drive_qualified_paths_are_refused(self) -> None:
        for path in ("C:" + BS + "Windows", "C:src", "D:"):
            with self.subTest(path=path):
                self.assertIn("must be relative", self.refusal_detail(path))

    def test_unc_and_device_paths_are_refused(self) -> None:
        for path in (
            BS * 2 + "server" + BS + "share",
            BS * 2 + "?" + BS + "D:" + BS + "project",
            BS * 2 + "." + BS + "PhysicalDrive0",
        ):
            with self.subTest(path=path):
                self.assertIn("must be relative", self.refusal_detail(path))

    def test_stream_syntax_is_refused(self) -> None:
        for path in ("readme.md::$DATA", "readme.md:hidden", "src::$INDEX_ALLOCATION"):
            with self.subTest(path=path):
                self.assertIn("not a valid path", self.refusal_detail(path))

    def test_reserved_device_names_are_refused(self) -> None:
        for path in ("NUL", "nul", "CON.txt", "COM1", "src/nul"):
            with self.subTest(path=path):
                self.assertIn("not a file", self.refusal_detail(path))

    def test_the_depth_bound_is_preserved(self) -> None:
        self.assertIn("must be relative", self.refusal_detail("/".join(["a"] * 40)))

    def test_the_length_bound_is_preserved(self) -> None:
        self.assertIn("must be relative", self.refusal_detail("a" * 2_000))

    def test_the_tool_does_not_reimplement_admission(self) -> None:
        """One boundary, used twice, rather than two that can drift apart."""
        source = (SRC_DIR / "tools" / "FilesystemMetadataTool.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("self._root.locate(", source)
        for reimplemented in (
            "PureWindowsPath",
            "PurePosixPath",
            "normpath",
            "RESERVED_DEVICE_NAMES",
            "is_relative_to",
        ):
            with self.subTest(construct=reimplemented):
                self.assertNotIn(reimplemented, source)


class ExistenceOracleTests(MetadataFixture):
    """What a caller may learn about what is and is not there."""

    def test_a_missing_entry_inside_the_root_says_so(self) -> None:
        """Kept distinguishable: the operator configured this scope, and could
        learn the same thing by listing it."""
        result = self.invoke(path="no-such-entry")

        self.assertIn("no such entry", result.detail.casefold())

    def test_an_outside_path_never_reveals_whether_it_exists(self) -> None:
        present = self.invoke(path=f"../{SENTINEL_OUTSIDE}")
        absent = self.invoke(path="../zz-definitely-not-there-11111")

        self.assertEqual(present.detail, absent.detail)
        self.assertEqual(present.disposition, absent.disposition)

    def test_an_outside_path_is_refused_without_touching_the_filesystem(self) -> None:
        """Proven by counting syscalls: nothing outside the root is ever probed."""
        original = Path.lstat
        calls: list[Path] = []

        def counting(self: Path, *args: object, **kwargs: object) -> os.stat_result:
            calls.append(self)
            return original(self, *args, **kwargs)

        Path.lstat = counting  # type: ignore[method-assign]
        try:
            self.invoke(path=f"../{SENTINEL_OUTSIDE}")
        finally:
            Path.lstat = original  # type: ignore[method-assign]

        self.assertEqual(calls, [])

    def test_an_inside_lookup_does_touch_the_filesystem(self) -> None:
        """Proves the previous test is measuring something real."""
        original = Path.lstat
        calls: list[Path] = []

        def counting(self: Path, *args: object, **kwargs: object) -> os.stat_result:
            calls.append(self)
            return original(self, *args, **kwargs)

        Path.lstat = counting  # type: ignore[method-assign]
        try:
            self.invoke(path="readme.md")
        finally:
            Path.lstat = original  # type: ignore[method-assign]

        self.assertNotEqual(calls, [])

    def test_no_refusal_names_the_outside_entry(self) -> None:
        result = self.invoke(path=f"../{SENTINEL_OUTSIDE}")

        self.assertNotIn(SENTINEL_OUTSIDE, result.detail)
        self.assertNotIn("secret.txt", result.detail)

    def test_no_refusal_quotes_the_requested_path(self) -> None:
        for path in ("no-such-entry", f"../{SENTINEL_OUTSIDE}", "C:" + BS + "Windows"):
            with self.subTest(path=path):
                self.assertNotIn(path, self.invoke(path=path).detail)

    def test_no_refusal_contains_the_root_path(self) -> None:
        for path in ("readme.md", "no-such-entry", ".."):
            with self.subTest(path=path):
                self.assertNotIn(str(self.root_path), self.invoke(path=path).detail)


class LinkPolicyTests(MetadataFixture):
    """Model A: a reparse entry is refused, never described, never followed."""

    def test_a_junction_target_is_refused_rather_than_described(self) -> None:
        link = self.root_path / "escape"
        if not _make_junction(link, self.outside):
            self.skipTest("This platform did not allow creating a junction.")

        result = self.invoke(path="escape")

        self.assertFalse(result.succeeded)
        self.assertIn("goes through a link", result.detail)

    def test_a_junction_never_leaks_its_target(self) -> None:
        link = self.root_path / "escape"
        if not _make_junction(link, self.outside):
            self.skipTest("This platform did not allow creating a junction.")

        result = self.invoke(path="escape")

        self.assertNotIn(SENTINEL_OUTSIDE, result.detail)
        self.assertNotIn(str(self.outside), result.detail)
        self.assertEqual(result.values, ())

    def test_a_path_through_a_junction_cannot_escape(self) -> None:
        link = self.root_path / "escape"
        if not _make_junction(link, self.outside):
            self.skipTest("This platform did not allow creating a junction.")

        result = self.invoke(path="escape/secret.txt")

        self.assertFalse(result.succeeded)
        self.assertEqual(result.values, ())

    def test_a_junction_pointing_inside_the_root_is_still_refused(self) -> None:
        """Not following is the rule. Where it points earns no exception."""
        link = self.root_path / "inward"
        if not _make_junction(link, self.root_path / "src"):
            self.skipTest("This platform did not allow creating a junction.")

        self.assertFalse(self.invoke(path="inward").succeeded)

    def test_a_symlink_is_refused(self) -> None:
        link = self.root_path / "symescape"
        if not _make_symlink(link, self.outside):
            self.skipTest(
                "This platform did not allow creating a symlink. On Windows this "
                "needs elevation and fails with WinError 1314; the junction "
                "tests cover the unprivileged case."
            )

        self.assertFalse(self.invoke(path="symescape").succeeded)

    def test_the_final_component_is_link_checked_not_only_the_parents(self) -> None:
        """The property this tool depends on for its whole link policy."""
        link = self.root_path / "escape"
        if not _make_junction(link, self.outside):
            self.skipTest("This platform did not allow creating a junction.")

        refusal, resolved = self.root.locate("escape")

        self.assertIs(refusal, FilesystemPathRefusal.LINK_COMPONENT)
        self.assertIsNone(resolved)

    def test_a_link_that_appeared_after_admission_is_caught_again(self) -> None:
        """Defence in depth: the stat reported is re-checked, not trusted."""
        link = self.root_path / "escape"
        if not _make_junction(link, self.outside):
            self.skipTest("This platform did not allow creating a junction.")

        result = self.tool._describe(link)

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertIs(result.disposition, ToolDisposition.FAILED)
        self.assertEqual(result.values, ())


class RaceTests(MetadataFixture):
    """Validation and metadata are separate syscalls. The gap is reported."""

    def test_an_entry_that_vanished_after_admission_is_a_failed_attempt(self) -> None:
        vanished = self.root_path / "gone.txt"

        result = self.tool._describe(vanished)

        self.assertIs(result.disposition, ToolDisposition.FAILED)
        self.assertIn("no longer does", result.detail)

    def test_a_vanished_entry_differs_from_one_that_was_never_there(self) -> None:
        """Already-missing is about the request; vanished is about the machine."""
        never = self.invoke(path="no-such-entry")
        vanished = self.tool._describe(self.root_path / "gone.txt")

        self.assertIs(never.disposition, ToolDisposition.DECLINED)
        self.assertIs(vanished.disposition, ToolDisposition.FAILED)
        self.assertNotEqual(never.detail, vanished.detail)

    def test_an_entry_moved_outside_the_root_is_refused_at_the_second_check(
        self,
    ) -> None:
        result = self.tool._describe(self.outside / "secret.txt")

        self.assertFalse(result.succeeded)
        self.assertIs(result.disposition, ToolDisposition.FAILED)
        self.assertEqual(result.values, ())

    def test_the_reported_stat_is_the_stat_that_was_checked(self) -> None:
        """One lstat produces both the check and the answer."""
        source = (SRC_DIR / "tools" / "FilesystemMetadataTool.py").read_text(
            encoding="utf-8"
        )

        self.assertEqual(source.count("entry.lstat()"), 1)
        self.assertIn("from_status(status", source)

    def test_metadata_never_uses_a_following_stat(self) -> None:
        source = (SRC_DIR / "tools" / "FilesystemMetadataTool.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn(".stat()", source)
        self.assertNotIn("os.stat(", source)
        self.assertNotIn("follow_symlinks=True", source)


class FailureTaxonomyTests(MetadataFixture):
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

    def execute(self, granted: frozenset = GRANT, **arguments: str) -> object:
        return self.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.FILESYSTEM_METADATA,
                authorized_effects=granted,
                arguments=tuple(arguments.items()),
            )
        )

    def test_success_completes(self) -> None:
        outcome = self.execute(path="readme.md")

        self.assertIsNone(outcome.failure_kind)
        self.assertIs(outcome.result.disposition, ToolDisposition.COMPLETED)

    def test_a_refused_path_is_declined(self) -> None:
        outcome = self.execute(path="..")

        self.assertIs(outcome.failure_kind, ToolFailureKind.INVOCATION_DECLINED)
        self.assertIs(outcome.result.disposition, ToolDisposition.DECLINED)
        self.assertFalse(outcome.failure_kind.attempted_the_work)

    def test_a_missing_entry_is_declined(self) -> None:
        outcome = self.execute(path="no-such-entry")

        self.assertIs(outcome.failure_kind, ToolFailureKind.INVOCATION_DECLINED)

    def test_an_unknown_argument_is_declined(self) -> None:
        outcome = self.execute(path="readme.md", depth="2")

        self.assertIs(outcome.failure_kind, ToolFailureKind.INVOCATION_DECLINED)

    def test_a_missing_argument_is_declined(self) -> None:
        outcome = self.execute()

        self.assertIs(outcome.failure_kind, ToolFailureKind.INVOCATION_DECLINED)

    def test_an_unauthorized_call_never_reaches_the_tool(self) -> None:
        outcome = self.execute(frozenset(), path="readme.md")

        self.assertIs(outcome.failure_kind, ToolFailureKind.UNAUTHORIZED_EFFECT)
        self.assertIs(outcome.result.disposition, ToolDisposition.NOT_REACHED)
        self.assertFalse(outcome.result.performed)
        self.assertNotIn(TOOL_STARTED, [e.name for e in self.events])

    def test_a_local_state_grant_does_not_authorize_metadata(self) -> None:
        outcome = self.execute(frozenset({ToolEffect.READS_LOCAL_STATE}), path=".")

        self.assertIs(outcome.failure_kind, ToolFailureKind.UNAUTHORIZED_EFFECT)

    def test_the_tool_declares_its_disposition_rather_than_raising(self) -> None:
        """Classification comes from the tool, never from a message."""
        source = (SRC_DIR / "tools" / "FilesystemMetadataTool.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("ToolResult.declined", source)
        self.assertIn("ToolResult.failed", source)
        self.assertNotIn("in detail", source)
        self.assertNotIn(".casefold()", source)


class TelemetryPrivacyTests(MetadataFixture):
    def setUp(self) -> None:
        super().setUp()
        (self.root_path / SENTINEL_ENTRY).write_text("x" * 4242, encoding="utf-8")
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        registry = ToolRegistry()
        registry.register(self.tool)
        self.service = ToolExecutionService(registry, event_bus=self.event_bus)

    def run_lookup(self, path: str) -> object:
        return self.service.execute(
            ToolInvocation(
                capability=ToolCapability.FILESYSTEM_METADATA,
                authorized_effects=GRANT,
                arguments=(("path", path),),
            )
        )

    def payloads(self) -> str:
        return str([event.payload for event in self.events])

    def test_no_event_carries_the_entry_name(self) -> None:
        self.run_lookup(SENTINEL_ENTRY)

        self.assertNotIn(SENTINEL_ENTRY, self.payloads())

    def test_no_event_carries_the_size(self) -> None:
        result = self.run_lookup(SENTINEL_ENTRY)

        self.assertEqual(dict(result.values)["size_bytes"], "4242")
        self.assertNotIn("4242", self.payloads())

    def test_no_event_carries_the_modification_time(self) -> None:
        result = self.run_lookup(SENTINEL_ENTRY)

        self.assertNotIn(dict(result.values)["modified_utc"], self.payloads())

    def test_no_event_carries_the_root_path(self) -> None:
        self.run_lookup(SENTINEL_ENTRY)

        self.assertNotIn(str(self.root_path), self.payloads())
        self.assertNotIn(self.root_path.name, self.payloads())

    def test_no_event_carries_the_detail_sentence(self) -> None:
        result = self.run_lookup(SENTINEL_ENTRY)

        self.assertNotIn(result.detail, self.payloads())

    def test_a_refused_lookup_leaks_nothing_either(self) -> None:
        self.run_lookup(f"../{SENTINEL_OUTSIDE}")

        self.assertNotIn(SENTINEL_OUTSIDE, self.payloads())

    def test_events_still_report_bounded_structure(self) -> None:
        self.run_lookup(SENTINEL_ENTRY)

        completed = [e for e in self.events if e.name == "tool.completed"][0]
        self.assertEqual(completed.payload["capability"], "filesystem_metadata")
        self.assertEqual(completed.payload["value_count"], 4)
        self.assertEqual(completed.payload["argument_count"], 1)


class BoundingTests(MetadataFixture):
    def test_the_shared_result_limit_is_unchanged(self) -> None:
        self.assertEqual(MAX_TOOL_VALUES, 20)

    def test_a_metadata_result_is_far_below_the_limit(self) -> None:
        self.assertLessEqual(len(self.invoke(path="readme.md").values), 4)

    def test_a_file_returns_exactly_four_fields(self) -> None:
        self.assertEqual(
            [name for name, _ in self.invoke(path="readme.md").values],
            ["name", "kind", "modified_utc", "size_bytes"],
        )

    def test_a_directory_returns_exactly_three_fields(self) -> None:
        self.assertEqual(
            [name for name, _ in self.invoke(path="src").values],
            ["name", "kind", "modified_utc"],
        )

    def test_a_long_entry_name_is_bounded(self) -> None:
        from tools.FilesystemMetadataTool import MAX_ENTRY_NAME_LENGTH

        self.assertEqual(MAX_ENTRY_NAME_LENGTH, 255)


class ForbiddenCapabilityTests(unittest.TestCase):
    """The line this milestone must not cross, checked in the source."""

    SOURCE = SRC_DIR / "tools" / "FilesystemMetadataTool.py"

    def source(self) -> str:
        return self.SOURCE.read_text(encoding="utf-8")

    def test_no_content_reading_api_is_introduced(self) -> None:
        for forbidden in (
            "open(",
            ".read(",
            "read_text",
            "read_bytes",
            "mmap",
            "hashlib",
            "sha256",
            "md5",
            "mimetypes",
            "guess_type",
            "chardet",
            "decode(",
        ):
            with self.subTest(construct=forbidden):
                self.assertNotIn(forbidden, self.source())

    def test_no_recursion_or_enumeration_api_is_introduced(self) -> None:
        for forbidden in (
            "walk(",
            "scandir",
            "iterdir",
            "glob",
            "rglob",
            "listdir",
        ):
            with self.subTest(construct=forbidden):
                self.assertNotIn(forbidden, self.source())

    def test_no_mutation_api_is_introduced(self) -> None:
        for forbidden in (
            "write_text",
            "write_bytes",
            "mkdir",
            "rmdir",
            "unlink",
            "rename",
            "replace(",
            "chmod",
            "chown",
            "utime",
            "symlink_to",
            "touch(",
        ):
            with self.subTest(construct=forbidden):
                self.assertNotIn(forbidden, self.source())

    def test_no_process_execution_api_is_introduced(self) -> None:
        for forbidden in (
            "subprocess",
            "os.system",
            "popen",
            "PowerShell",
            "cmd",
            "exec(",
            "eval(",
        ):
            with self.subTest(construct=forbidden):
                self.assertNotIn(forbidden, self.source())

    def test_no_owner_or_security_metadata_is_returned(self) -> None:
        for forbidden in (
            "st_uid",
            "st_gid",
            "st_ino",
            "st_dev",
            "getpwuid",
            "acl",
            "security_descriptor",
            "st_ctime",
        ):
            with self.subTest(field=forbidden):
                self.assertNotIn(forbidden, self.source())

    def test_only_the_intended_stat_fields_are_read(self) -> None:
        source = self.source()

        self.assertIn("st_mtime", source)
        self.assertIn("st_size", source)


class RegistrationTests(unittest.TestCase):
    def test_a_configured_root_registers_both_filesystem_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = ToolRuntime(FilesystemRoot(Path(temp)))

            self.assertEqual(
                [capability.value for capability in runtime.capabilities],
                [
                    "clock_read",
                    "text_statistics",
                    "filesystem_list",
                    "filesystem_metadata",
                ],
            )

    def test_no_root_registers_neither_filesystem_capability(self) -> None:
        names = [capability.value for capability in ToolRuntime(None).capabilities]

        self.assertNotIn("filesystem_metadata", names)
        self.assertNotIn("filesystem_list", names)

    def test_the_capability_resolves_to_the_metadata_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = ToolRuntime(FilesystemRoot(Path(temp)))

            self.assertIsInstance(
                runtime.registry.resolve(ToolCapability.FILESYSTEM_METADATA),
                FilesystemMetadataTool,
            )

    def test_content_capability_is_declared_but_no_content_tool_is_registered(
        self,
    ) -> None:
        names = {capability.value for capability in ToolCapability}

        self.assertIn("filesystem_read", names)
        with tempfile.TemporaryDirectory() as temp:
            registered = {
                capability.value
                for capability in ToolRuntime(FilesystemRoot(Path(temp))).capabilities
            }
        self.assertNotIn("filesystem_read", registered)

        for forbidden in (
            "filesystem_write",
            "filesystem_delete",
            "filesystem_execute",
            "shell",
        ):
            with self.subTest(capability=forbidden):
                self.assertNotIn(forbidden, names)


if __name__ == "__main__":
    unittest.main()
