"""Where filesystem authority comes from, and what it refuses to accept.

This is the one place a real path becomes a capability, so the tests are mostly
about roots that must not be granted. A drive root and the home directory are
refused even when configured on purpose: they are not scopes, and a capability
over them would be a filesystem tool wearing a boundary rather than having one.

The absent case matters as much as the refusing one. When no usable root
resolves the answer is None and no filesystem tool is registered — not a
registered tool that declines everything, which is one configuration mistake
away from working.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from tools.FilesystemRootPolicy import (
    FILESYSTEM_ROOT_OVERRIDE,
    is_too_broad,
    resolve_filesystem_root,
)


class DefaultRootTests(unittest.TestCase):
    def test_the_workspace_directory_becomes_the_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = resolve_filesystem_root(default_root=Path(temp), environment={})

            self.assertIsNotNone(root)
            self.assertEqual(root.path, Path(temp).resolve())

    def test_a_missing_workspace_yields_no_root_rather_than_an_error(self) -> None:
        """A desktop started before its data directory exists still starts."""
        with tempfile.TemporaryDirectory() as temp:
            absent = Path(temp) / "not-created-yet"

            self.assertIsNone(
                resolve_filesystem_root(default_root=absent, environment={})
            )

    def test_no_default_and_no_override_yields_no_root(self) -> None:
        self.assertIsNone(resolve_filesystem_root(default_root=None, environment={}))

    def test_the_root_carries_a_stable_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = resolve_filesystem_root(default_root=Path(temp), environment={})

            self.assertEqual(root.root_id, "workspace")


class OverrideTests(unittest.TestCase):
    def test_an_operator_override_wins_over_the_default(self) -> None:
        with tempfile.TemporaryDirectory() as chosen:
            with tempfile.TemporaryDirectory() as default:
                root = resolve_filesystem_root(
                    default_root=Path(default),
                    environment={FILESYSTEM_ROOT_OVERRIDE: chosen},
                )

                self.assertEqual(root.path, Path(chosen).resolve())

    def test_a_relative_override_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            resolve_filesystem_root(
                default_root=None,
                environment={FILESYSTEM_ROOT_OVERRIDE: "some/relative/path"},
            )

    def test_a_blank_override_falls_back_to_the_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = resolve_filesystem_root(
                default_root=Path(temp),
                environment={FILESYSTEM_ROOT_OVERRIDE: "   "},
            )

            self.assertEqual(root.path, Path(temp).resolve())

    def test_an_override_pointing_nowhere_yields_no_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            absent = str(Path(temp) / "absent")

            self.assertIsNone(
                resolve_filesystem_root(
                    default_root=None,
                    environment={FILESYSTEM_ROOT_OVERRIDE: absent},
                )
            )


class TooBroadTests(unittest.TestCase):
    """Some directories are the absence of a scope rather than a wide one."""

    def test_a_drive_or_filesystem_root_is_too_broad(self) -> None:
        anchor = Path(Path.cwd().anchor)

        self.assertTrue(is_too_broad(anchor))

    def test_the_home_directory_itself_is_too_broad(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)

            self.assertTrue(is_too_broad(home, home=home))

    def test_an_ancestor_of_home_is_too_broad(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "user"
            home.mkdir()

            self.assertTrue(is_too_broad(Path(temp), home=home))

    def test_a_directory_inside_home_is_a_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            workspace = home / "hypatia"
            workspace.mkdir()

            self.assertFalse(is_too_broad(workspace, home=home))

    def test_configuring_a_root_that_wide_is_refused_outright(self) -> None:
        anchor = Path(Path.cwd().anchor)

        with self.assertRaises(ResearchError):
            resolve_filesystem_root(
                default_root=None,
                environment={FILESYSTEM_ROOT_OVERRIDE: str(anchor)},
            )

    def test_the_refusal_does_not_quote_the_path(self) -> None:
        anchor = Path(Path.cwd().anchor)

        with self.assertRaises(ResearchError) as caught:
            resolve_filesystem_root(
                default_root=None,
                environment={FILESYSTEM_ROOT_OVERRIDE: str(anchor)},
            )

        self.assertNotIn(str(anchor), str(caught.exception))


class AuthoritySourceTests(unittest.TestCase):
    """The root has exactly one source, and it is not a model."""

    def test_the_policy_reads_only_the_named_environment_variable(self) -> None:
        source = (SRC_DIR / "tools" / "FilesystemRootPolicy.py").read_text(
            encoding="utf-8"
        )

        self.assertEqual(source.count("values.get("), 1)
        self.assertIn(FILESYSTEM_ROOT_OVERRIDE, source)

    def test_the_policy_imports_nothing_that_could_carry_model_output(self) -> None:
        """Checked on the code, not the prose: the docstring says these words."""
        import ast

        tree = ast.parse(
            (SRC_DIR / "tools" / "FilesystemRootPolicy.py").read_text(encoding="utf-8")
        )
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        for forbidden in ("brain", "cognition", "response", "memory", "research"):
            with self.subTest(package=forbidden):
                self.assertNotIn(forbidden, imported)

    def test_the_policy_reads_no_value_off_a_message_or_invocation(self) -> None:
        import ast

        tree = ast.parse(
            (SRC_DIR / "tools" / "FilesystemRootPolicy.py").read_text(encoding="utf-8")
        )
        names = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }

        for forbidden in ("message", "prompt", "arguments", "argument", "content"):
            with self.subTest(attribute=forbidden):
                self.assertNotIn(forbidden, names)

    def test_the_override_name_is_an_operator_convention(self) -> None:
        self.assertTrue(FILESYSTEM_ROOT_OVERRIDE.startswith("HYPATIA_"))


if __name__ == "__main__":
    unittest.main()
