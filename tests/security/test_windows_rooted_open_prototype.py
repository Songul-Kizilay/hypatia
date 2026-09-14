"""Adversarial evidence for the isolated Windows rooted-open experiment."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from experiments.prototypes.windows_rooted_open import (
    PrototypeFailure,
    PrototypeStage,
    WindowsRootedOpenPrototype,
    WindowsRootedOpenPrototypeError,
)

from tools.FilesystemPathRefusal import FilesystemPathRefusal
from tools.FilesystemRoot import FilesystemRoot


@unittest.skipUnless(os.name == "nt", "The prototype measures Windows handles.")
class WindowsRootedOpenPrototypeTests(unittest.TestCase):
    """Prove the native handle walk at deterministic replacement seams."""

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
        self.file.write_text("inside", encoding="utf-8")
        self.outside_file = self.outside / "note.txt"
        self.outside_file.write_text("outside", encoding="utf-8")
        self.root = FilesystemRoot(self.root_path, root_id="workspace")
        self.prototype = WindowsRootedOpenPrototype(self.root)

    def test_an_ordinary_file_produces_bounded_proof_and_no_content(self) -> None:
        proof = self.prototype.prove("parent/note.txt")

        self.assertEqual(proof.root_id, "workspace")
        self.assertEqual(proof.component_count, 2)
        self.assertNotEqual(proof.root_identity.file_index, 0)
        self.assertNotEqual(proof.file_identity.file_index, 0)
        self.assertTrue(proof.reparse_free)
        self.assertTrue(proof.final_contained)
        self.assertEqual(proof.content_bytes_read, 0)
        self.assertFalse(hasattr(proof, "handle"))
        self.assertFalse(hasattr(proof, "path"))
        self.assertFalse(hasattr(proof, "content"))

    def test_a_parent_replaced_by_a_junction_after_admission_is_refused(
        self,
    ) -> None:
        original = self.root_path / "parent-original"
        junction = self.root_path / "parent"

        def replace(stage: PrototypeStage, _component: str) -> None:
            if stage is not PrototypeStage.AFTER_ADMISSION:
                return
            self.parent.rename(original)
            self._junction(junction, self.outside)

        with self.assertRaises(WindowsRootedOpenPrototypeError) as raised:
            self.prototype.prove("parent/note.txt", seam=replace)

        self.assertIs(raised.exception.failure, PrototypeFailure.REPARSE_POINT)
        self._remove_junction(junction)

    def test_moving_an_open_parent_outside_fails_final_handle_containment(
        self,
    ) -> None:
        moved = self.outside / "moved-parent"

        def move(stage: PrototypeStage, component: str) -> None:
            if stage is PrototypeStage.AFTER_COMPONENT_OPEN and component == "parent":
                self.parent.rename(moved)

        with self.assertRaises(WindowsRootedOpenPrototypeError) as raised:
            self.prototype.prove("parent/note.txt", seam=move)

        self.assertIs(
            raised.exception.failure,
            PrototypeFailure.CONTAINMENT_UNPROVEN,
        )

    def test_root_replacement_after_configuration_is_detected(self) -> None:
        original_root = self.base / "original-root"
        self.root_path.rename(original_root)
        self.root_path.mkdir()
        replacement_parent = self.root_path / "parent"
        replacement_parent.mkdir()
        (replacement_parent / "note.txt").write_text("replacement", encoding="utf-8")

        with self.assertRaises(WindowsRootedOpenPrototypeError) as raised:
            self.prototype.prove("parent/note.txt")

        self.assertIs(raised.exception.failure, PrototypeFailure.ROOT_CHANGED)

    def test_final_file_replacement_is_detected_by_identity(self) -> None:
        replacement = self.parent / "replacement.txt"
        replacement.write_text("replacement", encoding="utf-8")

        def replace(stage: PrototypeStage, _component: str) -> None:
            if stage is PrototypeStage.AFTER_ADMISSION:
                self.file.unlink()
                replacement.rename(self.file)

        with self.assertRaises(WindowsRootedOpenPrototypeError) as raised:
            self.prototype.prove("parent/note.txt", seam=replace)

        self.assertIs(
            raised.exception.failure,
            PrototypeFailure.IDENTITY_MISMATCH,
        )

    def test_existing_path_policy_still_refuses_traversal(self) -> None:
        with self.assertRaises(WindowsRootedOpenPrototypeError) as raised:
            self.prototype.prove("../outside/note.txt")

        self.assertIs(raised.exception.failure, PrototypeFailure.PATH_REFUSED)
        self.assertIs(
            raised.exception.path_refusal,
            FilesystemPathRefusal.ESCAPES_ROOT,
        )

    def test_handles_close_when_a_deterministic_seam_raises(self) -> None:
        def interrupt(stage: PrototypeStage, _component: str) -> None:
            if stage is PrototypeStage.BEFORE_FINAL_PROOF:
                raise RuntimeError("controlled test interruption")

        with self.assertRaisesRegex(RuntimeError, "controlled test interruption"):
            self.prototype.prove("parent/note.txt", seam=interrupt)

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


class WindowsRootedOpenPrototypeSourceGuards(unittest.TestCase):
    """Keep the experiment isolated from production and from content access."""

    def test_the_prototype_contains_no_content_read_or_execution_path(self) -> None:
        source = (
            ROOT_DIR
            / "experiments"
            / "prototypes"
            / "windows_rooted_open"
            / "prototype.py"
        ).read_text(encoding="utf-8")

        for forbidden in (
            "os.read(",
            "ReadFile",
            "NtReadFile",
            "FILE_WRITE_DATA",
            "GENERIC_WRITE",
            "CreateProcess",
            "subprocess",
            "ToolCapability",
            "ToolEffect",
            "ToolRegistry",
            "ToolRuntime",
            "LLMProvider",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_no_production_module_imports_the_experiment(self) -> None:
        offenders = []
        for path in (ROOT_DIR / "src").rglob("*.py"):
            if "windows_rooted_open" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(ROOT_DIR).as_posix())

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
