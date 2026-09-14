"""The guard helpers are load-bearing, so they are tested like anything else.

Several dozen invariant guards are only as good as what these two functions
collect, and v0.3.233 found that out the hard way: `working_vocabulary` called
with no function names walks nothing, returns an empty set, and every
`assertNotIn` written against it passes while the prohibited construct sits in
the file untouched.

So both helpers are pinned here on what they actually promise. In particular
attribute access is asserted, because a guard saying "this module never reads
authored_at" is worthless against `hypothesis.assertions` if the collector only
sees bare names — and that is exactly the shape the real guards depend on.

The vacuity that started this is pinned too. `working_vocabulary` with no names
still returns nothing, and that behaviour is documented here rather than
quietly fixed, because callers that pass no names are the bug and the empty set
is the honest answer to a question nobody asked.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from tests.SourceVocabulary import mentions, module_vocabulary, working_vocabulary

MODULE = '''"""A module docstring mentioning forbidden_in_module_docstring."""

import urllib.request

FORBIDDEN_CONSTANT = "forbidden_in_constant"


def inspected(argument_name: str) -> str:
    """A function docstring mentioning forbidden_in_function_docstring."""
    client.fetch(argument_name)
    bare_call()
    value = attribute_read.authored_at
    return helper(keyword_name=value)


class Inspected:
    def other(self) -> None:
        untouched_by_named_walk()
'''


class ModuleVocabularyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vocabulary = module_vocabulary(MODULE)

    def test_it_collects_bare_identifiers(self) -> None:
        self.assertIn("bare_call", self.vocabulary)
        self.assertIn("client", self.vocabulary)

    def test_it_collects_attribute_names(self) -> None:
        """The property the timestamp guards depend on."""
        self.assertIn("fetch", self.vocabulary)
        self.assertIn("authored_at", self.vocabulary)

    def test_it_collects_imports(self) -> None:
        self.assertIn("urllib.request", self.vocabulary)

    def test_it_collects_definitions_and_keywords(self) -> None:
        self.assertIn("inspected", self.vocabulary)
        self.assertIn("keyword_name", self.vocabulary)
        self.assertIn("argument_name", self.vocabulary)

    def test_it_collects_string_constants(self) -> None:
        self.assertIn("forbidden_in_constant", self.vocabulary)

    def test_it_excludes_docstrings(self) -> None:
        """Otherwise a guard matches the prose explaining the guard."""
        self.assertNotIn(
            "a module docstring mentioning forbidden_in_module_docstring.",
            self.vocabulary,
        )
        self.assertNotIn(
            "a function docstring mentioning forbidden_in_function_docstring.",
            self.vocabulary,
        )

    def test_it_reaches_every_function_including_nested_ones(self) -> None:
        self.assertIn("untouched_by_named_walk", self.vocabulary)

    def test_it_is_never_silently_empty_for_real_code(self) -> None:
        self.assertGreater(len(self.vocabulary), 10)
        self.assertEqual(module_vocabulary("\n"), set())


class WorkingVocabularyTests(unittest.TestCase):
    def test_it_reads_only_the_named_function(self) -> None:
        vocabulary = working_vocabulary(MODULE, "inspected")

        self.assertIn("fetch", vocabulary)
        self.assertNotIn("untouched_by_named_walk", vocabulary)

    def test_it_refuses_a_name_that_is_absent(self) -> None:
        """Its own non-vacuity check: a renamed function breaks the guard."""
        with self.assertRaises(AssertionError):
            working_vocabulary(MODULE, "no_such_function")

    def test_calling_it_with_no_names_collects_nothing(self) -> None:
        """The v0.3.233 defect, pinned so it cannot come back unnoticed.

        This is not a bug in the helper — a walk over no functions truthfully
        finds no identifiers. It is a trap for callers, and the fix is to use
        `module_vocabulary` for whole-module questions rather than to make this
        one guess what was meant.
        """
        self.assertEqual(working_vocabulary(MODULE), set())
        self.assertNotIn("fetch", working_vocabulary(MODULE))
        self.assertIn("fetch", module_vocabulary(MODULE))


class MentionsTests(unittest.TestCase):
    def test_it_reports_the_matching_words_for_a_readable_failure(self) -> None:
        self.assertEqual(
            mentions({"authored_at", "author", "unrelated"}, "author"),
            ["author", "authored_at"],
        )


class CallerTests(unittest.TestCase):
    """No guard in the suite may go back to the vacuous form."""

    def test_no_test_calls_working_vocabulary_without_function_names(self) -> None:
        import ast

        offenders: list[str] = []
        for path in sorted((ROOT_DIR / "tests").rglob("test_*.py")):
            # This file calls it that way on purpose, to pin the behaviour.
            if path.name == Path(__file__).name:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "working_vocabulary"
                    and len(node.args) <= 1
                    and not node.keywords
                ):
                    offenders.append(f"{path.name}:{node.lineno}")

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
