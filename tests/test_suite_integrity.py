"""The suite must run the same tests however it is invoked.

A `if __name__ == "__main__": unittest.main()` block placed mid-file does not
fail. It collects the classes defined above it, runs them, and prints OK —
silently omitting every class defined below. The file looks green while a
smaller population was executed.

That is worse than a failure, because the missing tests are usually the ones
appended most recently: the newest, least-settled behaviour is exactly what
stops being checked. It happened here. Four files in the restriction and
deferred-grant area had grown that way, hiding 47 tests from direct
invocation — including the ones proving a self-contradictory plan can never
become deferred-eligible.

`unittest discover` imports the module rather than executing it, so CI was
running everything and no gate was red. This guard exists because a green
"OK" from running a file directly must mean what a reader assumes it means.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT_DIR / "tests"


def _definitions_after_main(path: Path) -> list[str]:
    """Return names defined after the module's ``__main__`` guard, if any."""
    module = ast.parse(path.read_text(encoding="utf-8"))
    guard_line: int | None = None
    for node in module.body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        # Match `if __name__ == "__main__":` without matching on source text.
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
        ):
            # The FIRST guard is the one that matters: direct invocation stops
            # collecting there, so a correct trailing guard does not redeem a
            # stray earlier one. Taking the last would let the stray hide
            # behind it, which is exactly the shape this looks for.
            guard_line = node.lineno
            break
    if guard_line is None:
        return []
    return [
        node.name
        for node in module.body
        if isinstance(node, ast.ClassDef | ast.FunctionDef) and node.lineno > guard_line
    ]


class EveryTestFileRunsItsWholeSelfTests(unittest.TestCase):
    def test_no_test_file_defines_anything_after_its_main_guard(self) -> None:
        """Otherwise running that file directly reports a misleading OK."""
        offenders = {
            str(path.relative_to(ROOT_DIR)): names
            for path in sorted(TESTS_DIR.rglob("test_*.py"))
            if (names := _definitions_after_main(path))
        }

        self.assertEqual(offenders, {})

    def test_the_guard_recognizes_a_planted_offender(self) -> None:
        """A guard that cannot fail proves nothing, so it is shown failing."""
        planted = TESTS_DIR / "fixtures" / "_main_guard_probe.py"
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text(
            'import unittest\n\n\nif __name__ == "__main__":\n'
            "    unittest.main()\n\n\nclass Hidden(unittest.TestCase):\n"
            "    pass\n",
            encoding="utf-8",
        )
        self.addCleanup(planted.unlink)

        self.assertEqual(_definitions_after_main(planted), ["Hidden"])


if __name__ == "__main__":
    unittest.main()
