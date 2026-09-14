"""Nothing outside the tool layer can reach a tool yet, and that is checked.

A tool layer becomes dangerous at the moment something decides on its own to use
it. Every guarantee in the other test files is about what happens once an
invocation exists; this one is about who is able to make one.

The check is structural rather than behavioural on purpose. A test that asked
"does this particular chat path invoke a tool?" would pass right up until
someone wired a different path. Asking instead whether any module outside
`src/tools` can even name the execution service catches the wiring itself, on
the commit that adds it, which is when it should be a deliberate decision rather
than a discovery.

Tools are now connected, so the guard names who may reach them rather than
asserting that nobody does. Two modules are permitted: the composition root that
builds the runtime, and the one controller that turns operator actions into
invocations. Everything else — chat, research, cognition, memory, and the
Tkinter window itself — still cannot import the layer, name the execution
service, or construct an invocation.

That the window is *not* on the list is the load-bearing part. The console
controller passes plain strings and plain data across that boundary, so the Tk
callbacks cannot name an effect or build an invocation even by accident. A
future surface that wants tool access has to be added here, in a diff someone
reviews, rather than by importing something convenient.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

TOOL_PACKAGE = "tools"

# The only modules outside src/tools deliberately given tool authority. Add a
# module here only when it is meant to be able to invoke a capability, and
# never a whole package: this list is the answer to "what can run a tool?".
PERMITTED_IMPORTERS: frozenset[str] = frozenset(
    {
        "desktop_main.py",
        str(Path("desktop") / "ToolConsoleController.py"),
    }
)

# Surfaces that must never gain tool authority, asserted by name so that
# granting one is a visible edit here rather than a quiet import elsewhere.
FORBIDDEN_IMPORTERS: frozenset[str] = frozenset(
    {
        str(Path("desktop") / "TkinterDesktopWindow.py"),
        str(Path("desktop") / "DesktopController.py"),
        str(Path("brain") / "Brain.py"),
        str(Path("cognition") / "CognitiveEngine.py"),
    }
)


def _imported_packages(source: Path) -> set[str]:
    """Return the top-level packages one module imports."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    packages: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            packages.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            packages.add(node.module.split(".")[0])
    return packages


class ToolLayerIsolationTests(unittest.TestCase):
    """The tool layer is reachable from tests, and from nothing else."""

    def outside_modules(self) -> list[Path]:
        return [
            path
            for path in SRC_DIR.rglob("*.py")
            if TOOL_PACKAGE not in path.relative_to(SRC_DIR).parts
        ]

    def named_outside_modules(self) -> list[tuple[str, Path]]:
        """Pair each module outside the layer with its repo-relative name."""
        return [
            (str(path.relative_to(SRC_DIR)), path) for path in self.outside_modules()
        ]

    def test_the_scan_actually_sees_the_application(self) -> None:
        """A guard over an empty set of files would pass while proving nothing."""
        self.assertGreater(len(self.outside_modules()), 100)

    def test_no_module_outside_the_tool_layer_imports_it(self) -> None:
        importers = sorted(
            str(path.relative_to(SRC_DIR))
            for path in self.outside_modules()
            if TOOL_PACKAGE in _imported_packages(path)
            and str(path.relative_to(SRC_DIR)) not in PERMITTED_IMPORTERS
        )

        self.assertEqual(importers, [])

    def test_only_permitted_modules_name_the_execution_service(self) -> None:
        """The seam is the only way in, so naming it is the thing to control."""
        offenders = [
            name
            for name, path in self.named_outside_modules()
            if "ToolExecutionService" in path.read_text(encoding="utf-8")
            and name not in PERMITTED_IMPORTERS
        ]

        self.assertEqual(offenders, [])

    def test_only_permitted_modules_build_an_invocation(self) -> None:
        offenders = [
            name
            for name, path in self.named_outside_modules()
            if "ToolInvocation(" in path.read_text(encoding="utf-8")
            and name not in PERMITTED_IMPORTERS
        ]

        self.assertEqual(offenders, [])

    def test_the_permitted_list_is_two_named_modules_not_a_package(self) -> None:
        """A package on this list would be a grant nobody could read back."""
        self.assertEqual(len(PERMITTED_IMPORTERS), 2)
        for name in PERMITTED_IMPORTERS:
            with self.subTest(module=name):
                self.assertTrue(name.endswith(".py"))
                self.assertTrue((SRC_DIR / name).is_file())

    def test_the_window_and_chat_surfaces_still_cannot_reach_the_layer(self) -> None:
        """The console passes plain data, so Tk never touches a tool type."""
        for name in FORBIDDEN_IMPORTERS:
            path = SRC_DIR / name
            if not path.is_file():
                continue
            with self.subTest(module=name):
                self.assertNotIn(name, PERMITTED_IMPORTERS)
                self.assertNotIn(TOOL_PACKAGE, _imported_packages(path))
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("ToolExecutionService", text)
                self.assertNotIn("ToolInvocation(", text)

    def test_the_composition_root_is_the_only_place_building_the_runtime(
        self,
    ) -> None:
        builders = [
            name
            for name, path in self.named_outside_modules()
            if "ToolRuntime(" in path.read_text(encoding="utf-8")
        ]

        self.assertEqual(builders, ["desktop_main.py"])

    def test_the_tool_layer_still_imports_itself(self) -> None:
        """Proves the detection works, rather than never matching anything."""
        service = SRC_DIR / TOOL_PACKAGE / "ToolExecutionService.py"

        self.assertIn(TOOL_PACKAGE, _imported_packages(service))


if __name__ == "__main__":
    unittest.main()
