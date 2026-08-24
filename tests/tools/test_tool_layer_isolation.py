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

When tools are eventually connected — through a meta-controller, under explicit
authorization — this test is expected to fail. It should be updated then, by
naming the one module allowed to hold that authority, not deleted.
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

# No module outside src/tools may import the tool layer yet. Add a module here
# only when it is deliberately being given the authority to invoke a tool.
PERMITTED_IMPORTERS: frozenset[str] = frozenset()


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

    def test_ordinary_conversation_cannot_name_the_execution_service(self) -> None:
        """The seam is the only way in, so not naming it is not reaching it."""
        offenders = [
            str(path.relative_to(SRC_DIR))
            for path in self.outside_modules()
            if "ToolExecutionService" in path.read_text(encoding="utf-8")
        ]

        self.assertEqual(offenders, [])

    def test_no_module_outside_the_tool_layer_builds_an_invocation(self) -> None:
        offenders = [
            str(path.relative_to(SRC_DIR))
            for path in self.outside_modules()
            if "ToolInvocation(" in path.read_text(encoding="utf-8")
        ]

        self.assertEqual(offenders, [])

    def test_the_tool_layer_still_imports_itself(self) -> None:
        """Proves the detection works, rather than never matching anything."""
        service = SRC_DIR / TOOL_PACKAGE / "ToolExecutionService.py"

        self.assertIn(TOOL_PACKAGE, _imported_packages(service))


if __name__ == "__main__":
    unittest.main()
