"""Production gates for the inert Windows rooted-open foundation."""

from __future__ import annotations

import ast
import ctypes
import os
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any, cast
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import tools.WindowsRootedOpen as rooted
from tools.FilesystemPathRefusal import FilesystemPathRefusal
from tools.FilesystemRoot import FilesystemRoot
from tools.FilesystemSensitivePathPolicy import FilesystemSensitiveClass
from tools.WindowsRootedOpen import (
    WindowsContentRangeObservation,
    WindowsOpenedFile,
    WindowsRootedOpen,
    WindowsRootedOpenError,
    WindowsRootedOpenFailure,
)


def _identity_of(path: Path) -> rooted._FileIdentity:
    status = path.lstat()
    return rooted._FileIdentity(
        int(status.st_dev) & 0xFFFFFFFF,
        int(status.st_ino),
    )


class _FakeNode:
    def __init__(
        self,
        *,
        label: str,
        attributes: int,
        identity: rooted._FileIdentity,
        path: PureWindowsPath,
    ) -> None:
        self.label = label
        self.attributes = attributes
        self.identity = identity
        self.path = path


class _FakeWindowsApi:
    """Model native results without making a race depend on timing."""

    def __init__(self, admitted_file: Path) -> None:
        self.filesystem = "NTFS"
        self.root_identity = rooted._FileIdentity(7, 11)
        self.replacement_root_identity: rooted._FileIdentity | None = None
        self.file_identity = _identity_of(admitted_file)
        self.attributes_by_component: dict[str, int] = {}
        self.identity_by_component: dict[str, rooted._FileIdentity] = {}
        self.path_by_component: dict[str, PureWindowsPath] = {}
        self.content = admitted_file.read_bytes()
        self.last_write_filetime = 133_500_000_000_000_000
        self.observation_results: list[rooted._FileObservation] = []
        self.observation_failure_at: int | None = None
        self.observation_count = 0
        self.read_result: rooted._NativeReadResult | None = None
        self.read_failure: Exception | None = None
        self.read_calls: list[tuple[int, int]] = []
        self.content_open_calls: list[str] = []
        self.final_path_failure_for: str | None = None
        self.open_failure_for: str | None = None
        self.fail_close_for: set[str] = set()
        self.open_root_count = 0
        self.open_calls: list[tuple[str, bool]] = []
        self.closed_labels: list[str] = []
        self.active: set[int] = set()
        self._nodes: dict[int, _FakeNode] = {}
        self._next_handle = 100
        self._root_path = PureWindowsPath(r"\Device\HarddiskVolume7\workspace")

    def _add(self, node: _FakeNode) -> int:
        handle = self._next_handle
        self._next_handle += 1
        self._nodes[handle] = node
        self.active.add(handle)
        return handle

    def open_root(self, absolute_root: str) -> int:
        self.open_root_count += 1
        identity = self.root_identity
        if self.open_root_count > 1 and self.replacement_root_identity is not None:
            identity = self.replacement_root_identity
        return self._add(
            _FakeNode(
                label="<root>",
                attributes=rooted.FILE_ATTRIBUTE_DIRECTORY,
                identity=identity,
                path=self._root_path,
            )
        )

    def open_relative(self, parent: int, component: str, *, final: bool) -> int:
        self.open_calls.append((component, final))
        return self._open_component(parent, component, final=final)

    def open_relative_content(self, parent: int, component: str) -> int:
        self.open_calls.append((component, True))
        self.content_open_calls.append(component)
        return self._open_component(parent, component, final=True)

    def _open_component(self, parent: int, component: str, *, final: bool) -> int:
        if self.open_failure_for == component:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.OPEN_FAILED)
        parent_node = self._nodes[parent]
        attributes = self.attributes_by_component.get(
            component,
            rooted.FILE_ATTRIBUTE_NORMAL if final else rooted.FILE_ATTRIBUTE_DIRECTORY,
        )
        identity = self.identity_by_component.get(
            component,
            self.file_identity if final else rooted._FileIdentity(7, 20),
        )
        path = self.path_by_component.get(component, parent_node.path / component)
        return self._add(
            _FakeNode(
                label=component,
                attributes=attributes,
                identity=identity,
                path=path,
            )
        )

    def close(self, handle: int) -> bool:
        node = self._nodes[handle]
        self.closed_labels.append(node.label)
        self.active.discard(handle)
        return node.label not in self.fail_close_for

    def attributes(self, handle: int) -> int:
        return self._nodes[handle].attributes

    def filesystem_name(self, handle: int) -> str:
        return self.filesystem

    def identity(self, handle: int) -> rooted._FileIdentity:
        return self._nodes[handle].identity

    def observation(self, handle: int) -> rooted._FileObservation:
        self.observation_count += 1
        if self.observation_failure_at == self.observation_count:
            raise OSError(r"C:\private\sentinel.txt")
        if self.observation_count <= len(self.observation_results):
            return self.observation_results[self.observation_count - 1]
        node = self._nodes[handle]
        return rooted._FileObservation(
            identity=node.identity,
            size=len(self.content),
            last_write_filetime=self.last_write_filetime,
        )

    def read(
        self,
        handle: int,
        *,
        offset: int,
        capacity: int,
    ) -> rooted._NativeReadResult:
        del handle
        self.read_calls.append((offset, capacity))
        if self.read_failure is not None:
            raise self.read_failure
        if self.read_result is not None:
            return self.read_result
        content = self.content[offset : offset + capacity]
        return rooted._NativeReadResult(content, len(content))

    def final_path(self, handle: int) -> PureWindowsPath:
        node = self._nodes[handle]
        if self.final_path_failure_for == node.label:
            raise WindowsRootedOpenError(WindowsRootedOpenFailure.CONTAINMENT_UNPROVEN)
        return node.path


class WindowsRootedOpenDeterministicTests(unittest.TestCase):
    """Exercise every bounded branch through an injectable Windows API."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root_path = Path(self.temporary.name) / "root"
        self.parent = self.root_path / "parent"
        self.parent.mkdir(parents=True)
        self.file = self.parent / "note.txt"
        self.file.write_text("private sentinel", encoding="utf-8")
        self.root = FilesystemRoot(self.root_path, root_id="workspace")
        self.api = _FakeWindowsApi(self.file)
        self.acquirer = WindowsRootedOpen(self.root, _api=self.api)
        self.api.closed_labels.clear()

    def test_an_ordinary_acquisition_is_bounded_inert_and_closes_every_handle(
        self,
    ) -> None:
        with self.acquirer.acquire("parent/note.txt") as opened:
            self.assertIsInstance(opened, WindowsOpenedFile)
            self.assertEqual(opened.root_id, "workspace")
            self.assertEqual(opened.component_count, 2)
            self.assertEqual(opened.content_bytes_read, 0)
            self.assertTrue(opened.is_open)
            self.assertFalse(hasattr(opened, "handle"))
            self.assertFalse(hasattr(opened, "path"))
            self.assertFalse(hasattr(opened, "content"))
            self.assertFalse(any("handle" in name for name in dir(opened)))

        self.assertFalse(opened.is_open)
        self.assertEqual(
            self.api.closed_labels,
            ["note.txt", "parent", "<root>"],
        )
        self.assertEqual(self.api.active, set())
        self.assertEqual(
            self.api.open_calls,
            [("parent", False), ("note.txt", True)],
        )

    def test_initial_traversal_refusal_preserves_the_existing_reason(self) -> None:
        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("../outside.txt"):
                pass

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.PATH_REFUSED)
        self.assertIs(
            raised.exception.path_refusal,
            FilesystemPathRefusal.ESCAPES_ROOT,
        )
        self.assertEqual(self.api.open_calls, [])

    def test_initial_link_refusal_preserves_the_existing_reason(self) -> None:
        with (
            patch.object(
                FilesystemRoot,
                "locate",
                return_value=(FilesystemPathRefusal.LINK_COMPONENT, None),
            ),
            self.assertRaises(WindowsRootedOpenError) as raised,
        ):
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.PATH_REFUSED)
        self.assertIs(
            raised.exception.path_refusal,
            FilesystemPathRefusal.LINK_COMPONENT,
        )

    def test_sensitive_admitted_name_is_refused_before_native_acquisition(self) -> None:
        # Keep this integration case portable: POSIX preserves trailing spaces,
        # while Windows normalizes them away before lookup. Windows suffix
        # normalization itself is covered by the pure policy tests.
        sensitive = self.root_path / ".ENV"
        sensitive.write_text("must not be read", encoding="utf-8")
        root_open_count = self.api.open_root_count

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire(".ENV"):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.SENSITIVE_FILE,
        )
        self.assertIs(
            raised.exception.sensitive_class,
            FilesystemSensitiveClass.ENVIRONMENT_FILE,
        )
        self.assertIn("environment file", str(raised.exception))
        self.assertNotIn(".ENV", str(raised.exception))
        self.assertEqual(self.api.open_root_count, root_open_count)
        self.assertEqual(self.api.open_calls, [])

    def test_final_handle_name_is_reclassified_after_safe_open(self) -> None:
        self.api.path_by_component["note.txt"] = PureWindowsPath(
            r"\Device\HarddiskVolume7\workspace\.ENV. "
        )
        self.api.identity_by_component["note.txt"] = rooted._FileIdentity(7, 404)

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.SENSITIVE_FILE,
        )
        self.assertIs(
            raised.exception.sensitive_class,
            FilesystemSensitiveClass.ENVIRONMENT_FILE,
        )
        self.assertEqual(
            self.api.closed_labels,
            ["note.txt", "parent", "<root>"],
        )

    def test_invalid_final_handle_component_is_a_bounded_containment_failure(
        self,
    ) -> None:
        self.api.path_by_component["note.txt"] = PureWindowsPath(
            r"\Device\HarddiskVolume7\workspace\..."
        )

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.CONTAINMENT_UNPROVEN,
        )
        self.assertIsNone(raised.exception.__cause__)

    def test_entry_disappearing_between_locate_and_lstat_is_bounded(self) -> None:
        def locate_then_remove(
            _root: FilesystemRoot, _relative: str
        ) -> tuple[FilesystemPathRefusal, Path | None]:
            self.file.unlink()
            return (FilesystemPathRefusal.NONE, self.file)

        with (
            patch.object(FilesystemRoot, "locate", new=locate_then_remove),
            self.assertRaises(WindowsRootedOpenError) as raised,
        ):
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.ENTRY_CHANGED,
        )

    def test_an_entry_removed_after_admission_fails_the_rooted_open(self) -> None:
        def remove(stage: rooted._WindowsRootedOpenStage, _index: int) -> None:
            if stage is rooted._WindowsRootedOpenStage.AFTER_ADMISSION:
                self.file.unlink()
                self.api.open_failure_for = "note.txt"

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt", _seam=remove):
                pass

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.OPEN_FAILED)

    def test_a_changed_configured_root_identity_is_refused(self) -> None:
        self.api.replacement_root_identity = rooted._FileIdentity(7, 99)

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.ROOT_CHANGED)
        self.assertEqual(self.api.closed_labels, ["<root>"])

    def test_an_acquired_reparse_component_is_refused(self) -> None:
        self.api.attributes_by_component["parent"] = (
            rooted.FILE_ATTRIBUTE_DIRECTORY | rooted.FILE_ATTRIBUTE_REPARSE_POINT
        )

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.REPARSE_POINT,
        )

    def test_an_acquired_intermediate_non_directory_is_refused(self) -> None:
        self.api.attributes_by_component["parent"] = rooted.FILE_ATTRIBUTE_NORMAL

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.NOT_DIRECTORY,
        )

    def test_an_acquired_final_directory_is_refused(self) -> None:
        self.api.attributes_by_component["note.txt"] = rooted.FILE_ATTRIBUTE_DIRECTORY

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.NOT_FILE)

    def test_a_final_path_outside_the_held_root_is_refused(self) -> None:
        self.api.path_by_component["note.txt"] = PureWindowsPath(
            r"\Device\HarddiskVolume7\outside\note.txt"
        )

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.CONTAINMENT_UNPROVEN,
        )

    def test_a_final_path_query_failure_is_bounded(self) -> None:
        self.api.final_path_failure_for = "note.txt"

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.CONTAINMENT_UNPROVEN,
        )

    def test_a_final_identity_mismatch_is_refused(self) -> None:
        self.api.identity_by_component["note.txt"] = rooted._FileIdentity(7, 404)

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.IDENTITY_MISMATCH,
        )

    def test_all_handles_close_when_a_deterministic_seam_raises(self) -> None:
        def interrupt(stage: rooted._WindowsRootedOpenStage, _index: int) -> None:
            if stage is rooted._WindowsRootedOpenStage.BEFORE_FINAL_PROOF:
                raise RuntimeError("controlled interruption")

        with self.assertRaisesRegex(RuntimeError, "controlled interruption"):
            with self.acquirer.acquire("parent/note.txt", _seam=interrupt):
                pass

        self.assertEqual(
            self.api.closed_labels,
            ["note.txt", "parent", "<root>"],
        )
        self.assertEqual(self.api.active, set())

    def test_close_failure_prevents_a_successful_context_exit(self) -> None:
        self.api.fail_close_for.add("note.txt")
        opened: WindowsOpenedFile | None = None

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt") as current:
                opened = current

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.CLOSE_FAILED)
        self.assertIsNotNone(opened)
        assert opened is not None
        self.assertFalse(opened.is_open)
        self.assertEqual(
            self.api.closed_labels,
            ["note.txt", "parent", "<root>"],
        )

    def test_error_text_carries_no_path_native_code_or_sentinel(self) -> None:
        self.api.path_by_component["note.txt"] = PureWindowsPath(
            r"\Device\HarddiskVolume7\outside\private-sentinel.txt"
        )

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt"):
                pass

        rendered = str(raised.exception)
        self.assertNotIn("note.txt", rendered)
        self.assertNotIn("private", rendered)
        self.assertNotIn("Device", rendered)
        self.assertNotIn("WinError", rendered)
        self.assertIsNone(raised.exception.__cause__)
        self.assertIs(
            raised.exception.sensitive_class,
            FilesystemSensitiveClass.NONE,
        )


class WindowsContentRangeDeterministicTests(unittest.TestCase):
    """Lock the bounded raw-read contract without depending on native timing."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root_path = Path(self.temporary.name) / "root"
        self.parent = self.root_path / "parent"
        self.parent.mkdir(parents=True)
        self.file = self.parent / "note.txt"
        self.file.write_bytes(b"0123456789abcdef")
        self.root = FilesystemRoot(self.root_path, root_id="workspace")
        self.api = _FakeWindowsApi(self.file)
        self.read_at = datetime(2026, 8, 24, 18, 30, tzinfo=UTC)
        self.acquirer = WindowsRootedOpen(
            self.root,
            _api=self.api,
            _clock=lambda: self.read_at,
        )
        self.api.closed_labels.clear()

    def observation(
        self,
        *,
        identity: rooted._FileIdentity | None = None,
        size: int | None = None,
        last_write_filetime: int | None = None,
    ) -> rooted._FileObservation:
        return rooted._FileObservation(
            identity=identity or self.api.file_identity,
            size=len(self.api.content) if size is None else size,
            last_write_filetime=(
                self.api.last_write_filetime
                if last_write_filetime is None
                else last_write_filetime
            ),
        )

    def test_ordinary_read_returns_bounded_raw_observation_after_all_closes(
        self,
    ) -> None:
        result = self.acquirer.read_range(
            "parent/note.txt",
            offset=0,
            max_bytes=64,
        )

        self.assertIsInstance(result, WindowsContentRangeObservation)
        self.assertEqual(result.root_id, "workspace")
        self.assertEqual(result.resource, "parent/note.txt")
        self.assertEqual(result.offset, 0)
        self.assertEqual(result.bytes_requested, 64)
        self.assertEqual(result.bytes_returned, 16)
        self.assertEqual(result.content, b"0123456789abcdef")
        self.assertFalse(result.truncated)
        self.assertEqual(result.file_size_bytes, 16)
        self.assertEqual(result.read_at_utc, self.read_at)
        self.assertEqual(result.modified_utc.tzinfo, UTC)
        self.assertEqual(self.api.read_calls, [(0, 65)])
        self.assertEqual(self.api.content_open_calls, ["note.txt"])
        self.assertEqual(
            self.api.closed_labels,
            ["note.txt", "parent", "<root>"],
        )
        self.assertEqual(self.api.active, set())
        self.assertFalse(hasattr(result, "handle"))
        self.assertFalse(hasattr(result, "path"))

    def test_one_byte_lookahead_is_discarded_and_never_counted(self) -> None:
        result = self.acquirer.read_range(
            "parent/note.txt",
            offset=0,
            max_bytes=4,
        )

        self.assertEqual(self.api.read_calls, [(0, 5)])
        self.assertEqual(result.content, b"0123")
        self.assertEqual(result.bytes_returned, 4)
        self.assertTrue(result.truncated)
        self.assertNotIn(b"4", result.content)

    def test_raw_observation_is_immutable_and_rejects_inconsistent_state(self) -> None:
        result = self.acquirer.read_range(
            "parent/note.txt",
            offset=0,
            max_bytes=4,
        )
        with self.assertRaises(FrozenInstanceError):
            cast(Any, result).offset = 1

        base: dict[str, Any] = {
            "root_id": "workspace",
            "resource": "parent/note.txt",
            "offset": 0,
            "bytes_requested": 4,
            "bytes_returned": 4,
            "truncated": True,
            "file_size_bytes": 16,
            "modified_utc": self.read_at,
            "read_at_utc": self.read_at,
            "content": b"0123",
        }
        invalid = (
            ({"resource": "../note.txt"}, ValueError),
            ({"bytes_returned": 3}, ValueError),
            ({"truncated": False}, ValueError),
            ({"content": bytearray(b"0123")}, TypeError),
            ({"read_at_utc": datetime(2026, 8, 24)}, ValueError),
            ({"bytes_requested": True}, ValueError),
        )

        for override, error in invalid:
            with self.subTest(override=override):
                with self.assertRaises(error):
                    WindowsContentRangeObservation(**(base | override))

    def test_zero_maximum_reads_only_the_lookahead_and_returns_no_content(
        self,
    ) -> None:
        result = self.acquirer.read_range(
            "parent/note.txt",
            offset=0,
            max_bytes=0,
        )

        self.assertEqual(self.api.read_calls, [(0, 1)])
        self.assertEqual(result.content, b"")
        self.assertEqual(result.bytes_returned, 0)
        self.assertTrue(result.truncated)

    def test_decisive_maxima_produce_the_exact_bounded_native_capacity(self) -> None:
        for max_bytes in (0, 1, 65_536):
            with self.subTest(max_bytes=max_bytes):
                api = _FakeWindowsApi(self.file)
                acquirer = WindowsRootedOpen(
                    self.root,
                    _api=api,
                    _clock=lambda: self.read_at,
                )

                acquirer.read_range(
                    "parent/note.txt",
                    offset=0,
                    max_bytes=max_bytes,
                )

                self.assertEqual(api.read_calls, [(0, max_bytes + 1)])

    def test_decisive_offsets_reach_the_single_native_call_unchanged(self) -> None:
        for offset in (0, 1, (1 << 32) - 1, 1 << 32, (1 << 63) - 1):
            with self.subTest(offset=offset):
                api = _FakeWindowsApi(self.file)
                acquirer = WindowsRootedOpen(
                    self.root,
                    _api=api,
                    _clock=lambda: self.read_at,
                )
                api.closed_labels.clear()

                result = acquirer.read_range(
                    "parent/note.txt",
                    offset=offset,
                    max_bytes=0,
                )

                self.assertEqual(api.read_calls, [(offset, 1)])
                self.assertEqual(result.offset, offset)
                self.assertEqual(result.content, b"")

    def test_invalid_ranges_are_rejected_before_any_new_native_acquisition(
        self,
    ) -> None:
        cases = (
            ("offset", True, 1, TypeError),
            ("offset", 1.5, 1, TypeError),
            ("offset", -1, 1, ValueError),
            ("offset", 1 << 63, 1, ValueError),
            ("max_bytes", 0, False, TypeError),
            ("max_bytes", 0, "1", TypeError),
            ("max_bytes", 0, -1, ValueError),
            ("max_bytes", 0, 65_537, ValueError),
        )
        root_open_count = self.api.open_root_count

        for label, offset, max_bytes, error in cases:
            with self.subTest(label=label, value=(offset, max_bytes)):
                with self.assertRaises(error):
                    self.acquirer.read_range(
                        "parent/note.txt",
                        offset=offset,  # type: ignore[arg-type]
                        max_bytes=max_bytes,  # type: ignore[arg-type]
                    )

        self.assertEqual(self.api.open_root_count, root_open_count)
        self.assertEqual(self.api.open_calls, [])
        self.assertEqual(self.api.read_calls, [])

    def test_crossing_eof_returns_only_the_stable_suffix(self) -> None:
        result = self.acquirer.read_range(
            "parent/note.txt",
            offset=13,
            max_bytes=10,
        )

        self.assertEqual(result.content, b"def")
        self.assertEqual(result.bytes_returned, 3)
        self.assertFalse(result.truncated)
        self.assertEqual(self.api.read_calls, [(13, 11)])

    def test_successful_empty_reads_at_and_past_eof_are_accepted(self) -> None:
        for offset in (16, 17):
            with self.subTest(offset=offset):
                api = _FakeWindowsApi(self.file)
                acquirer = WindowsRootedOpen(
                    self.root,
                    _api=api,
                    _clock=lambda: self.read_at,
                )

                result = acquirer.read_range(
                    "parent/note.txt",
                    offset=offset,
                    max_bytes=8,
                )

                self.assertEqual(result.content, b"")
                self.assertFalse(result.truncated)

    def test_explicit_eof_signal_is_accepted_only_at_or_past_observed_eof(
        self,
    ) -> None:
        for offset in (16, 17):
            with self.subTest(offset=offset):
                api = _FakeWindowsApi(self.file)
                api.read_result = rooted._NativeReadResult(
                    b"",
                    0,
                    eof_signal=True,
                )
                acquirer = WindowsRootedOpen(
                    self.root,
                    _api=api,
                    _clock=lambda: self.read_at,
                )

                result = acquirer.read_range(
                    "parent/note.txt",
                    offset=offset,
                    max_bytes=8,
                )

                self.assertEqual(result.content, b"")

        self.api.read_result = rooted._NativeReadResult(b"", 0, eof_signal=True)
        with self.assertRaises(WindowsRootedOpenError) as raised:
            self.acquirer.read_range(
                "parent/note.txt",
                offset=15,
                max_bytes=8,
            )
        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.READ_FAILED)

    def test_positive_and_zero_short_reads_before_eof_fail_without_retry(
        self,
    ) -> None:
        for content in (b"01", b""):
            with self.subTest(content=content):
                api = _FakeWindowsApi(self.file)
                api.read_result = rooted._NativeReadResult(content, len(content))
                acquirer = WindowsRootedOpen(
                    self.root,
                    _api=api,
                    _clock=lambda: self.read_at,
                )

                with self.assertRaises(WindowsRootedOpenError) as raised:
                    acquirer.read_range(
                        "parent/note.txt",
                        offset=0,
                        max_bytes=8,
                    )

                self.assertIs(
                    raised.exception.failure,
                    WindowsRootedOpenFailure.READ_INCOMPLETE,
                )
                self.assertEqual(api.read_calls, [(0, 9)])

    def test_impossible_native_counts_fail_closed(self) -> None:
        cases = (
            rooted._NativeReadResult(b"012345", 6),
            rooted._NativeReadResult(b"0123", 3),
            rooted._NativeReadResult(b"xy", 2),
            rooted._NativeReadResult(b"x", 1, eof_signal=True),
        )
        offsets = (0, 0, 15, 16)

        for native, offset in zip(cases, offsets, strict=True):
            with self.subTest(native=native, offset=offset):
                api = _FakeWindowsApi(self.file)
                api.read_result = native
                acquirer = WindowsRootedOpen(
                    self.root,
                    _api=api,
                    _clock=lambda: self.read_at,
                )

                with self.assertRaises(WindowsRootedOpenError) as raised:
                    acquirer.read_range(
                        "parent/note.txt",
                        offset=offset,
                        max_bytes=4,
                    )

                self.assertIs(
                    raised.exception.failure,
                    WindowsRootedOpenFailure.READ_FAILED,
                )

    def test_each_pre_post_change_dimension_discards_the_read(self) -> None:
        changes = (
            self.observation(identity=rooted._FileIdentity(7, 999)),
            self.observation(size=17),
            self.observation(last_write_filetime=self.api.last_write_filetime + 1),
        )

        for changed in changes:
            with self.subTest(changed=changed):
                api = _FakeWindowsApi(self.file)
                api.observation_results = [self.observation(), changed]
                acquirer = WindowsRootedOpen(
                    self.root,
                    _api=api,
                    _clock=lambda: self.read_at,
                )

                with self.assertRaises(WindowsRootedOpenError) as raised:
                    acquirer.read_range(
                        "parent/note.txt",
                        offset=0,
                        max_bytes=4,
                    )

                self.assertIs(
                    raised.exception.failure,
                    WindowsRootedOpenFailure.CONTENT_CHANGED,
                )
                self.assertEqual(
                    api.closed_labels[-3:], ["note.txt", "parent", "<root>"]
                )
                self.assertEqual(api.active, set())

    def test_content_open_read_and_observation_failures_are_bounded_and_close(
        self,
    ) -> None:
        cases = ("open", "read", "pre_observation", "post_observation")

        for case in cases:
            with self.subTest(case=case):
                api = _FakeWindowsApi(self.file)
                if case == "open":
                    api.open_failure_for = "note.txt"
                elif case == "read":
                    api.read_failure = OSError(r"C:\private\sentinel.txt")
                elif case == "pre_observation":
                    api.observation_failure_at = 1
                else:
                    api.observation_failure_at = 2
                acquirer = WindowsRootedOpen(
                    self.root,
                    _api=api,
                    _clock=lambda: self.read_at,
                )
                api.closed_labels.clear()

                with self.assertRaises(WindowsRootedOpenError) as raised:
                    acquirer.read_range(
                        "parent/note.txt",
                        offset=0,
                        max_bytes=4,
                    )

                expected = (
                    WindowsRootedOpenFailure.OPEN_FAILED
                    if case == "open"
                    else WindowsRootedOpenFailure.READ_FAILED
                )
                self.assertIs(raised.exception.failure, expected)
                self.assertNotIn("private", str(raised.exception))
                self.assertNotIn("sentinel", str(raised.exception))
                self.assertIsNone(raised.exception.__cause__)
                self.assertEqual(api.active, set())

    def test_close_failure_prevents_the_completed_observation_from_returning(
        self,
    ) -> None:
        self.api.fail_close_for.add("note.txt")
        result: WindowsContentRangeObservation | None = None

        with self.assertRaises(WindowsRootedOpenError) as raised:
            result = self.acquirer.read_range(
                "parent/note.txt",
                offset=0,
                max_bytes=4,
            )

        self.assertIsNone(result)
        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.CLOSE_FAILED)
        self.assertEqual(self.api.read_calls, [(0, 5)])
        self.assertEqual(
            self.api.closed_labels,
            ["note.txt", "parent", "<root>"],
        )

    def test_invalid_or_raising_clock_fails_closed_after_the_read(self) -> None:
        def raise_clock() -> datetime:
            raise RuntimeError("private clock sentinel")

        for clock in (lambda: datetime(2026, 8, 24), raise_clock):
            with self.subTest(clock=clock):
                api = _FakeWindowsApi(self.file)
                acquirer = WindowsRootedOpen(self.root, _api=api, _clock=clock)
                api.closed_labels.clear()

                with self.assertRaises(WindowsRootedOpenError) as raised:
                    acquirer.read_range(
                        "parent/note.txt",
                        offset=0,
                        max_bytes=16,
                    )

                self.assertIs(
                    raised.exception.failure,
                    WindowsRootedOpenFailure.READ_FAILED,
                )
                self.assertNotIn("sentinel", str(raised.exception))
                self.assertEqual(api.active, set())


class WindowsRootedOpenConstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root_path = Path(self.temporary.name) / "root"
        self.root_path.mkdir()
        self.file = self.root_path / "note.txt"
        self.file.write_text("sentinel", encoding="utf-8")
        self.root = FilesystemRoot(self.root_path)

    def test_non_windows_construction_is_bounded_before_api_loading(self) -> None:
        with (
            patch.object(rooted.os, "name", "posix"),
            patch.object(rooted, "_SystemWindowsApi") as loader,
            self.assertRaises(WindowsRootedOpenError) as raised,
        ):
            WindowsRootedOpen(self.root)

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.NOT_WINDOWS)
        loader.assert_not_called()

    def test_an_unavailable_system_api_is_bounded(self) -> None:
        failure = WindowsRootedOpenError(WindowsRootedOpenFailure.API_UNAVAILABLE)
        with (
            patch.object(rooted.os, "name", "nt"),
            patch.object(rooted, "_SystemWindowsApi", side_effect=failure),
            self.assertRaises(WindowsRootedOpenError) as raised,
        ):
            WindowsRootedOpen(self.root)

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.API_UNAVAILABLE,
        )

    def test_a_non_ntfs_root_is_refused_and_closed(self) -> None:
        api = _FakeWindowsApi(self.file)
        api.filesystem = "ReFS"

        with self.assertRaises(WindowsRootedOpenError) as raised:
            WindowsRootedOpen(self.root, _api=api)

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.UNSUPPORTED_FILESYSTEM,
        )
        self.assertEqual(api.closed_labels, ["<root>"])
        self.assertEqual(api.active, set())

    def test_constructor_requires_the_code_owned_root_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "FilesystemRoot"):
            WindowsRootedOpen(object())  # type: ignore[arg-type]

    def test_sensitive_failure_requires_exactly_one_bounded_class(self) -> None:
        with self.assertRaisesRegex(ValueError, "needs a bounded class"):
            WindowsRootedOpenError(WindowsRootedOpenFailure.SENSITIVE_FILE)

        with self.assertRaisesRegex(ValueError, "Only a sensitive-file"):
            WindowsRootedOpenError(
                WindowsRootedOpenFailure.OPEN_FAILED,
                sensitive_class=FilesystemSensitiveClass.PRIVATE_KEY,
            )


class _WarningSystemApi(rooted._SystemWindowsApi):
    def __init__(self, close_result: bool) -> None:
        self.close_result = close_result
        self.closed: list[int] = []
        self.desired_access: list[int] = []
        self.share_access: list[int] = []

        def return_warning(output_pointer: Any, *arguments: object) -> int:
            self.desired_access.append(cast(int, arguments[0]))
            self.share_access.append(cast(int, arguments[5]))
            output = ctypes.cast(
                output_pointer,
                ctypes.POINTER(wintypes.HANDLE),
            )
            output.contents.value = 7331
            return 1

        self._nt_create_file = return_warning

    def close(self, handle: int) -> bool:
        self.closed.append(handle)
        return self.close_result


class _RaisingCloseWarningSystemApi(_WarningSystemApi):
    def close(self, handle: int) -> bool:
        self.closed.append(handle)
        raise OSError(r"C:\private\sentinel.txt")


class SystemWindowsApiFailureTests(unittest.TestCase):
    """Lock the defensive-close rule at the raw NtCreateFile seam."""

    def test_root_open_requests_only_attributes_and_synchronization(self) -> None:
        api = object.__new__(rooted._SystemWindowsApi)
        captured: list[int] = []

        def create_file(_path: str, access: int, *_: object) -> int:
            captured.append(access)
            return 7330

        api._create_file = create_file

        self.assertEqual(api.open_root(r"D:\workspace"), 7330)
        self.assertEqual(
            captured,
            [rooted.FILE_READ_ATTRIBUTES | rooted.SYNCHRONIZE],
        )

    def test_relative_open_never_requests_file_data_for_either_kind(self) -> None:
        observed: list[int] = []
        for final in (False, True):
            api = _WarningSystemApi(True)
            with self.assertRaises(WindowsRootedOpenError):
                api.open_relative(100, "component", final=final)
            observed.extend(api.desired_access)

        self.assertEqual(
            observed,
            [rooted.FILE_READ_ATTRIBUTES | rooted.SYNCHRONIZE] * 2,
        )

    def test_content_open_requests_exact_read_rights_and_read_only_sharing(
        self,
    ) -> None:
        api = _WarningSystemApi(True)

        with self.assertRaises(WindowsRootedOpenError):
            api.open_relative_content(100, "note.txt")

        self.assertEqual(
            api.desired_access,
            [rooted.FILE_READ_DATA | rooted.FILE_READ_ATTRIBUTES | rooted.SYNCHRONIZE],
        )
        self.assertEqual(api.share_access, [rooted.FILE_SHARE_READ])

    @unittest.skipUnless(os.name == "nt", "ReadFile ABI test requires Windows ctypes.")
    def test_readfile_uses_one_zeroed_overlapped_with_exact_64_bit_offset(
        self,
    ) -> None:
        api = object.__new__(rooted._SystemWindowsApi)
        calls: list[tuple[int, int, int, int, int, int, int]] = []

        def read_file(
            handle: Any,
            buffer: Any,
            capacity: int,
            count_pointer: Any,
            overlapped_pointer: Any,
        ) -> int:
            overlapped = ctypes.cast(
                overlapped_pointer,
                ctypes.POINTER(rooted._Overlapped),
            ).contents
            calls.append(
                (
                    int(handle.value or 0),
                    capacity,
                    int(overlapped.Internal),
                    int(overlapped.InternalHigh),
                    int(overlapped.Offset),
                    int(overlapped.OffsetHigh),
                    int(overlapped.hEvent or 0),
                )
            )
            ctypes.memmove(buffer, b"abc", 3)
            ctypes.cast(
                count_pointer,
                ctypes.POINTER(wintypes.DWORD),
            ).contents.value = 3
            return 1

        api._read_file = read_file

        result = api.read(7331, offset=(1 << 32) + 7, capacity=4)

        self.assertEqual(result, rooted._NativeReadResult(b"abc", 3))
        self.assertEqual(calls, [(7331, 4, 0, 0, 7, 1, 0)])

    @unittest.skipUnless(
        os.name == "nt", "ReadFile error test requires Windows ctypes."
    )
    def test_readfile_accepts_only_the_bounded_eof_error(self) -> None:
        api = object.__new__(rooted._SystemWindowsApi)

        def fail_with(error: int) -> Callable[..., int]:
            def read_file(*_: object) -> int:
                ctypes.set_last_error(error)
                return 0

            return read_file

        api._read_file = fail_with(rooted.ERROR_HANDLE_EOF)
        eof = api.read(7331, offset=99, capacity=1)
        self.assertEqual(eof, rooted._NativeReadResult(b"", 0, eof_signal=True))

        api._read_file = fail_with(rooted.ERROR_IO_PENDING)
        with self.assertRaises(WindowsRootedOpenError) as raised:
            api.read(7331, offset=99, capacity=1)

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.READ_FAILED)
        self.assertNotIn(str(rooted.ERROR_IO_PENDING), str(raised.exception))

    def test_warning_status_with_a_handle_closes_then_fails(self) -> None:
        api = _WarningSystemApi(True)

        with self.assertRaises(WindowsRootedOpenError) as raised:
            api.open_relative(100, "note.txt", final=True)

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.OPEN_FAILED)
        self.assertEqual(api.closed, [7331])

    def test_warning_handle_close_failure_is_not_hidden(self) -> None:
        api = _WarningSystemApi(False)

        with self.assertRaises(WindowsRootedOpenError) as raised:
            api.open_relative(100, "note.txt", final=True)

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.CLOSE_FAILED)
        self.assertEqual(api.closed, [7331])

    def test_warning_handle_raw_close_error_is_bounded(self) -> None:
        api = _RaisingCloseWarningSystemApi(True)

        with self.assertRaises(WindowsRootedOpenError) as raised:
            api.open_relative(100, "note.txt", final=True)

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.CLOSE_FAILED)
        self.assertEqual(api.closed, [7331])
        self.assertNotIn("private", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)


@unittest.skipUnless(os.name == "nt", "Native rooted-open tests require Windows.")
class WindowsRootedOpenNativeTests(unittest.TestCase):
    """Repeat the prototype's adversarial evidence against production code."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root_path = self.base / "root"
        self.outside = self.base / "outside"
        self.root_path.mkdir()
        self.outside.mkdir()
        self.parent = self.root_path / "parent"
        self.parent.mkdir()
        self.file = self.parent / "note.txt"
        self.file.write_text("inside sentinel", encoding="utf-8")
        self.outside_file = self.outside / "note.txt"
        self.outside_file.write_text("outside sentinel", encoding="utf-8")
        self.root = FilesystemRoot(self.root_path, root_id="workspace")
        self.acquirer = WindowsRootedOpen(self.root)

    def test_native_ordinary_file_yields_no_content_or_handle(self) -> None:
        with self.acquirer.acquire("parent/note.txt") as opened:
            self.assertEqual(opened.content_bytes_read, 0)
            self.assertFalse(hasattr(opened, "handle"))
            self.assertFalse(hasattr(opened, "path"))
            self.assertFalse(hasattr(opened, "content"))

        self.assertFalse(opened.is_open)
        self.file.unlink()
        self.parent.rmdir()

    def test_native_content_ranges_cover_raw_truncation_eof_and_offsets(self) -> None:
        read_at = datetime(2026, 8, 24, 19, 0, tzinfo=UTC)
        acquirer = WindowsRootedOpen(self.root, _clock=lambda: read_at)

        ordinary = acquirer.read_range(
            "parent/note.txt",
            offset=0,
            max_bytes=6,
        )
        suffix = acquirer.read_range(
            "parent/note.txt",
            offset=len("inside sentinel") - 3,
            max_bytes=10,
        )
        at_eof = acquirer.read_range(
            "parent/note.txt",
            offset=len("inside sentinel"),
            max_bytes=10,
        )
        past_eof = acquirer.read_range(
            "parent/note.txt",
            offset=len("inside sentinel") + 1,
            max_bytes=10,
        )

        self.assertEqual(ordinary.content, b"inside")
        self.assertEqual(ordinary.bytes_returned, 6)
        self.assertTrue(ordinary.truncated)
        self.assertEqual(suffix.content, b"nel")
        self.assertFalse(suffix.truncated)
        self.assertEqual(at_eof.content, b"")
        self.assertFalse(at_eof.truncated)
        self.assertEqual(past_eof.content, b"")
        self.assertFalse(past_eof.truncated)
        self.assertEqual(ordinary.read_at_utc, read_at)

    def test_native_raw_boundary_preserves_utf8_bom_and_invalid_bytes(self) -> None:
        cases = (
            "Merhaba, dünya".encode(),
            b"\xef\xbb\xbfhello",
            b"\xff\xfe\x00binary",
            b"",
        )

        for content in cases:
            with self.subTest(content=content):
                self.file.write_bytes(content)
                result = self.acquirer.read_range(
                    "parent/note.txt",
                    offset=0,
                    max_bytes=65_536,
                )

                self.assertEqual(result.content, content)
                self.assertEqual(result.bytes_returned, len(content))
                self.assertFalse(result.truncated)

    def test_native_active_writer_conflicts_with_read_only_sharing(self) -> None:
        with self.file.open("r+b") as writer:
            writer.write(b"active")
            writer.flush()

            with self.assertRaises(WindowsRootedOpenError) as raised:
                self.acquirer.read_range(
                    "parent/note.txt",
                    offset=0,
                    max_bytes=16,
                )

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.OPEN_FAILED)

    def test_native_parent_replaced_by_junction_is_refused(self) -> None:
        original = self.root_path / "parent-original"
        junction = self.root_path / "parent"

        def replace(stage: rooted._WindowsRootedOpenStage, _index: int) -> None:
            if stage is rooted._WindowsRootedOpenStage.AFTER_ADMISSION:
                self.parent.rename(original)
                self._junction(junction, self.outside)

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt", _seam=replace):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.REPARSE_POINT,
        )
        self._remove_junction(junction)

    def test_native_final_replaced_by_a_junction_is_refused(self) -> None:
        target = self.outside / "target"
        target.mkdir()

        def replace(stage: rooted._WindowsRootedOpenStage, _index: int) -> None:
            if stage is rooted._WindowsRootedOpenStage.AFTER_ADMISSION:
                self.file.unlink()
                self._junction(self.file, target)

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt", _seam=replace):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.REPARSE_POINT,
        )
        self._remove_junction(self.file)

    def test_native_moved_open_parent_fails_containment(self) -> None:
        moved = self.outside / "moved-parent"

        def move(stage: rooted._WindowsRootedOpenStage, index: int) -> None:
            if (
                stage is rooted._WindowsRootedOpenStage.AFTER_COMPONENT_OPEN
                and index == 0
            ):
                self.parent.rename(moved)

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt", _seam=move):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.CONTAINMENT_UNPROVEN,
        )

    def test_native_root_replacement_is_detected(self) -> None:
        original_root = self.base / "original-root"
        self.root_path.rename(original_root)
        self.root_path.mkdir()
        replacement_parent = self.root_path / "parent"
        replacement_parent.mkdir()
        (replacement_parent / "note.txt").write_text(
            "replacement",
            encoding="utf-8",
        )

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt"):
                pass

        self.assertIs(raised.exception.failure, WindowsRootedOpenFailure.ROOT_CHANGED)

    def test_native_final_file_replacement_is_detected(self) -> None:
        replacement = self.parent / "replacement.txt"
        replacement.write_text("replacement", encoding="utf-8")

        def replace(stage: rooted._WindowsRootedOpenStage, _index: int) -> None:
            if stage is rooted._WindowsRootedOpenStage.AFTER_ADMISSION:
                self.file.unlink()
                replacement.rename(self.file)

        with self.assertRaises(WindowsRootedOpenError) as raised:
            with self.acquirer.acquire("parent/note.txt", _seam=replace):
                pass

        self.assertIs(
            raised.exception.failure,
            WindowsRootedOpenFailure.IDENTITY_MISMATCH,
        )

    def test_native_handles_close_when_a_seam_raises(self) -> None:
        def interrupt(stage: rooted._WindowsRootedOpenStage, _index: int) -> None:
            if stage is rooted._WindowsRootedOpenStage.BEFORE_FINAL_PROOF:
                raise RuntimeError("controlled interruption")

        with self.assertRaisesRegex(RuntimeError, "controlled interruption"):
            with self.acquirer.acquire("parent/note.txt", _seam=interrupt):
                pass

        self.file.unlink()
        self.parent.rmdir()

    def _junction(self, link: Path, target: Path) -> None:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
            creationflags=flags,
        )
        if result.returncode != 0:
            self.skipTest("This Windows host could not create a test junction.")
        self.addCleanup(self._remove_junction, link)

    @staticmethod
    def _remove_junction(link: Path) -> None:
        try:
            os.rmdir(link)
        except FileNotFoundError:
            pass


class WindowsRootedOpenSourceGuards(unittest.TestCase):
    """Keep the foundation inert, local, unregistered, and experiment-free."""

    @classmethod
    def source(cls) -> str:
        return (SRC_DIR / "tools" / "WindowsRootedOpen.py").read_text(encoding="utf-8")

    def test_only_the_five_decided_public_types_are_exported(self) -> None:
        self.assertEqual(
            rooted.__all__,
            [
                "WindowsContentRangeObservation",
                "WindowsOpenedFile",
                "WindowsRootedOpen",
                "WindowsRootedOpenError",
                "WindowsRootedOpenFailure",
            ],
        )

    def test_no_mutation_execution_or_capability_path_exists(self) -> None:
        for forbidden in (
            "os.read(",
            "NtReadFile",
            "SetFilePointerEx",
            "read_bytes(",
            "read_text(",
            "FILE_LIST_DIRECTORY",
            "FILE_TRAVERSE",
            "FILE_EXECUTE",
            "FILE_WRITE_DATA",
            "GENERIC_WRITE",
            "CreateProcess",
            "subprocess",
            "ToolCapability",
            "ToolEffect",
            "ToolRegistry",
            "ToolRuntime",
            "FilesystemContentPayload",
            "LLMProvider",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source())

    def test_exactly_one_documented_native_read_call_has_no_loop_or_fallback(
        self,
    ) -> None:
        source = self.source()
        tree = ast.parse(source)
        system_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "_SystemWindowsApi"
        )
        read_method = next(
            node
            for node in system_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "read"
        )
        native_calls = [
            node
            for node in ast.walk(read_method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_read_file"
        ]

        self.assertEqual(len(native_calls), 1)
        self.assertFalse(
            any(
                isinstance(node, (ast.For, ast.While)) for node in ast.walk(read_method)
            )
        )
        self.assertIn(".ReadFile", source)
        self.assertNotIn("NtReadFile", source)
        self.assertNotIn("SetFilePointerEx", source)

    def test_system_dll_binding_is_fixed_and_has_no_configured_path(self) -> None:
        source = self.source()

        self.assertIn('"kernel32.dll"', source)
        self.assertIn('"ntdll.dll"', source)
        self.assertIn("LOAD_LIBRARY_SEARCH_SYSTEM32", source)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("getenv", source)
        self.assertNotIn("ctypes.CDLL", source)

    def test_only_the_composition_root_imports_the_inert_foundation(self) -> None:
        offenders = []
        target = SRC_DIR / "tools" / "WindowsRootedOpen.py"
        for path in SRC_DIR.rglob("*.py"):
            if path == target:
                continue
            if "WindowsRootedOpen" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(ROOT_DIR).as_posix())

        self.assertEqual(offenders, ["src/desktop_main.py"])
        entrypoint = (SRC_DIR / "desktop_main.py").read_text(encoding="utf-8")
        self.assertNotIn("WindowsRootedOpen(", entrypoint)

    def test_packaging_import_check_constructs_no_windows_api(self) -> None:
        import desktop_main

        with patch.object(rooted, "_SystemWindowsApi") as loader:
            desktop_main._verify_inert_platform_boundary_imports()

        loader.assert_not_called()

    def test_production_does_not_import_the_experiment(self) -> None:
        self.assertNotIn("experiments", self.source())
        self.assertNotIn("windows_rooted_open", self.source())


if __name__ == "__main__":
    unittest.main()
