"""Production gates for the inert Windows rooted-open foundation."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import unittest
from ctypes import wintypes
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
from tools.WindowsRootedOpen import (
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


class _WarningSystemApi(rooted._SystemWindowsApi):
    def __init__(self, close_result: bool) -> None:
        self.close_result = close_result
        self.closed: list[int] = []
        self.desired_access: list[int] = []

        def return_warning(output_pointer: Any, *arguments: object) -> int:
            self.desired_access.append(cast(int, arguments[0]))
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

    def test_only_the_four_decided_public_types_are_exported(self) -> None:
        self.assertEqual(
            rooted.__all__,
            [
                "WindowsOpenedFile",
                "WindowsRootedOpen",
                "WindowsRootedOpenError",
                "WindowsRootedOpenFailure",
            ],
        )

    def test_no_content_mutation_execution_or_capability_path_exists(self) -> None:
        for forbidden in (
            "os.read(",
            "ReadFile",
            "NtReadFile",
            "read_bytes(",
            "read_text(",
            "FILE_LIST_DIRECTORY",
            "FILE_TRAVERSE",
            "FILE_EXECUTE",
            "FILE_READ_DATA",
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
