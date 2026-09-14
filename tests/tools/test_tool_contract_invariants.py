"""The two contract corrections a pure, argument-taking tool required.

Neither is about text statistics. Both are about what the layer promised and did
not yet enforce: that a tool can declare purity honestly, and that an argument
called a string is one.

The effect change is the load-bearing one. `ToolDescriptor` refuses an empty
effect set on purpose, so a tool that genuinely touches nothing had two dishonest
options — claim to read local state, or make the blank declaration legal. The
second is worse than it looks: an empty set is a subset of every grant, so the
declaration nobody filled in would become the only one no authorisation could
refuse.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from tools.ToolCapability import ToolCapability
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolEffect import ToolEffect
from tools.ToolInvocation import ToolInvocation
from tools.ToolResult import ToolResult

PURE = frozenset({ToolEffect.COMPUTES_LOCALLY})


class PureEffectTests(unittest.TestCase):
    """A tool that touches nothing must be able to say so out loud."""

    def test_an_empty_effect_set_is_still_refused(self) -> None:
        """The blank-declaration guard is kept, not relaxed."""
        with self.assertRaises(ResearchError):
            ToolDescriptor(
                capability=ToolCapability.TEXT_STATISTICS,
                effects=frozenset(),
                summary="Counts things.",
            )

    def test_computing_locally_is_a_declarable_effect(self) -> None:
        descriptor = ToolDescriptor(
            capability=ToolCapability.TEXT_STATISTICS,
            effects=PURE,
            summary="Counts things.",
        )

        self.assertEqual(descriptor.effects, PURE)

    def test_computing_locally_changes_nothing_and_reaches_nothing(self) -> None:
        self.assertFalse(ToolEffect.COMPUTES_LOCALLY.irreversible)
        self.assertFalse(ToolEffect.COMPUTES_LOCALLY.observable_outside)

    def test_a_pure_tool_is_read_only_and_stays_on_this_machine(self) -> None:
        descriptor = ToolDescriptor(
            capability=ToolCapability.TEXT_STATISTICS,
            effects=PURE,
            summary="Counts things.",
        )

        self.assertTrue(descriptor.read_only)
        self.assertFalse(descriptor.reaches_outside)

    def test_an_empty_grant_does_not_authorize_a_pure_tool(self) -> None:
        """The whole point: purity is granted, not assumed."""
        descriptor = ToolDescriptor(
            capability=ToolCapability.TEXT_STATISTICS,
            effects=PURE,
            summary="Counts things.",
        )

        self.assertFalse(descriptor.within(frozenset()))
        self.assertEqual(descriptor.unauthorized(frozenset()), PURE)

    def test_granting_computation_does_not_grant_anything_else(self) -> None:
        reading = ToolDescriptor(
            capability=ToolCapability.CLOCK_READ,
            effects=frozenset({ToolEffect.READS_LOCAL_STATE}),
            summary="Reads the clock.",
        )

        self.assertFalse(reading.within(PURE))


class ArgumentTypeTests(unittest.TestCase):
    """A length bound is not a type check; an empty list has a length."""

    def invocation(self, value: object) -> ToolInvocation:
        return ToolInvocation(
            capability=ToolCapability.TEXT_STATISTICS,
            authorized_effects=PURE,
            arguments=(("text", value),),  # type: ignore[arg-type]
        )

    def test_a_non_string_argument_value_is_refused(self) -> None:
        for value in (123, True, None, [], {}, 1.5, b"bytes"):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    self.invocation(value)

    def test_the_empty_container_hole_is_closed(self) -> None:
        """These two used to construct, because len(()) works on anything sized."""
        for value in ([], {}):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    self.invocation(value)

    def test_a_non_string_argument_name_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ToolInvocation(
                capability=ToolCapability.TEXT_STATISTICS,
                authorized_effects=PURE,
                arguments=((7, "hello"),),  # type: ignore[arg-type]
            )

    def test_an_empty_string_value_is_still_allowed(self) -> None:
        """Empty text is a real input with real answers, not a missing one."""
        invocation = self.invocation("")

        self.assertEqual(invocation.arguments, (("text", ""),))

    def test_ordinary_string_arguments_still_construct(self) -> None:
        self.assertEqual(self.invocation("hello").argument("text"), "hello")

    def test_duplicate_names_are_still_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ToolInvocation(
                capability=ToolCapability.TEXT_STATISTICS,
                authorized_effects=PURE,
                arguments=(("text", "a"), ("text", "b")),
            )


class ResultValueTypeTests(unittest.TestCase):
    """The same hole existed on the way out, where it matters more."""

    def result(self, value: object) -> ToolResult:
        return ToolResult(
            capability=ToolCapability.TEXT_STATISTICS,
            performed=True,
            detail="Counted.",
            values=(("word_count", value),),  # type: ignore[arg-type]
        )

    def test_a_non_string_result_value_is_refused(self) -> None:
        for value in (3, True, None, [], {}):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    self.result(value)

    def test_string_result_values_still_construct(self) -> None:
        self.assertEqual(self.result("3").values, (("word_count", "3"),))


if __name__ == "__main__":
    unittest.main()
