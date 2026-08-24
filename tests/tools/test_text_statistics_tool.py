"""The first tool with a real argument, and the rules arguments must follow.

`ClockReadTool` proved the path for a tool that takes nothing. This file proves
it for one that takes something, which is where a tool layer usually starts
leaking: into the result, into the event payload, into an error message that
helpfully quotes what went wrong.

So the sentinel is the point of half these tests. It is a string that would be
obviously wrong to find anywhere outside the invocation object, and it is
searched for in the result, in every lifecycle payload, and in the detail of
every failure path.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.CancellationSignal import CancellationSignal
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from tools.ClockReadTool import ClockReadTool
from tools.TextStatisticsTool import TextStatisticsTool
from tools.ToolCapability import ToolCapability
from tools.ToolEffect import ToolEffect
from tools.ToolEvents import (
    TOOL_AUTHORIZED,
    TOOL_COMPLETED,
    TOOL_FAILED,
    TOOL_REQUESTED,
    TOOL_STARTED,
)
from tools.ToolExecutionService import ToolExecutionService
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRegistry import ToolRegistry

PURE = frozenset({ToolEffect.COMPUTES_LOCALLY})
SENTINEL = "PRIVATE-SENTINEL-DO-NOT-LOG-8472"


class TextStatisticsDescriptorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = TextStatisticsTool()

    def test_it_declares_the_text_statistics_capability(self) -> None:
        self.assertIs(
            self.tool.descriptor.capability,
            ToolCapability.TEXT_STATISTICS,
        )

    def test_it_declares_only_computing_locally(self) -> None:
        """It transforms what it was handed. Anything more would be a lie."""
        self.assertEqual(self.tool.descriptor.effects, PURE)

    def test_it_declares_no_effect_it_does_not_have(self) -> None:
        for absent in (
            ToolEffect.READS_LOCAL_STATE,
            ToolEffect.WRITES_LOCAL_STATE,
            ToolEffect.READS_NETWORK,
            ToolEffect.SPENDS_MODEL,
        ):
            with self.subTest(effect=absent):
                self.assertNotIn(absent, self.tool.descriptor.effects)

    def test_it_is_read_only_and_reaches_nothing_outside(self) -> None:
        self.assertTrue(self.tool.descriptor.read_only)
        self.assertFalse(self.tool.descriptor.reaches_outside)

    def test_it_accepts_exactly_one_argument_name(self) -> None:
        from tools.TextStatisticsTool import ACCEPTED_ARGUMENTS

        self.assertEqual(ACCEPTED_ARGUMENTS, frozenset({"text"}))


class CountingTests(unittest.TestCase):
    """One definition per count, chosen deliberately and pinned here."""

    def counts(self, text: str) -> dict[str, str]:
        result = TextStatisticsTool().invoke(
            ToolInvocation(
                capability=ToolCapability.TEXT_STATISTICS,
                authorized_effects=PURE,
                arguments=(("text", text),),
            )
        )
        self.assertTrue(result.succeeded, result.detail)
        return dict(result.values)

    def test_empty_text_counts_zero_of_everything(self) -> None:
        self.assertEqual(
            self.counts(""),
            {
                "character_count": "0",
                "word_count": "0",
                "line_count": "0",
                "non_whitespace_character_count": "0",
            },
        )

    def test_a_single_word_is_one_word_on_one_line(self) -> None:
        counts = self.counts("hello")

        self.assertEqual(counts["character_count"], "5")
        self.assertEqual(counts["word_count"], "1")
        self.assertEqual(counts["line_count"], "1")

    def test_runs_of_spaces_do_not_invent_words(self) -> None:
        counts = self.counts("  hello    world  ")

        self.assertEqual(counts["word_count"], "2")
        self.assertEqual(counts["character_count"], "18")
        self.assertEqual(counts["non_whitespace_character_count"], "10")

    def test_tabs_separate_words_like_any_whitespace(self) -> None:
        counts = self.counts("a\tb\tc")

        self.assertEqual(counts["word_count"], "3")
        self.assertEqual(counts["non_whitespace_character_count"], "3")

    def test_a_trailing_newline_does_not_start_a_line(self) -> None:
        self.assertEqual(self.counts("hello\n")["line_count"], "1")

    def test_two_lines_are_two_lines(self) -> None:
        counts = self.counts("hello\nworld")

        self.assertEqual(counts["line_count"], "2")
        self.assertEqual(counts["word_count"], "2")

    def test_a_lone_newline_is_one_line(self) -> None:
        """The empty line before the break is still a line."""
        self.assertEqual(self.counts("\n")["line_count"], "1")

    def test_line_counting_does_not_depend_on_the_platform(self) -> None:
        """The same text must count the same on every machine."""
        for text in ("a\nb", "a\r\nb", "a\rb"):
            with self.subTest(text=repr(text)):
                self.assertEqual(self.counts(text)["line_count"], "2")

    def test_blank_lines_between_text_are_counted(self) -> None:
        self.assertEqual(self.counts("a\n\nb")["line_count"], "3")

    def test_whitespace_only_text_has_characters_but_no_words(self) -> None:
        counts = self.counts("   \t  ")

        self.assertEqual(counts["word_count"], "0")
        self.assertEqual(counts["character_count"], "6")
        self.assertEqual(counts["non_whitespace_character_count"], "0")

    def test_unicode_simply_works(self) -> None:
        counts = self.counts("naïve café")

        self.assertEqual(counts["character_count"], "10")
        self.assertEqual(counts["word_count"], "2")

    def test_turkish_text_needs_no_special_handling(self) -> None:
        """No language logic. Python strings already know what a character is."""
        counts = self.counts("Hypatia güvenli şekilde öğrenir")

        self.assertEqual(counts["word_count"], "4")
        # 31, not 34: each of ü, ş, ö and ğ is one character, not one plus a mark.
        self.assertEqual(counts["character_count"], "31")

    def test_non_latin_scripts_count_the_same_way(self) -> None:
        counts = self.counts("日本語 テキスト")

        self.assertEqual(counts["word_count"], "2")
        self.assertEqual(counts["character_count"], "8")

    def test_counting_is_deterministic(self) -> None:
        self.assertEqual(self.counts(SENTINEL), self.counts(SENTINEL))


class ArgumentContractTests(unittest.TestCase):
    """Invalid input the tool itself owns, and what it must call it."""

    def invoke(self, arguments: tuple[tuple[str, str], ...]) -> object:
        return TextStatisticsTool().invoke(
            ToolInvocation(
                capability=ToolCapability.TEXT_STATISTICS,
                authorized_effects=PURE,
                arguments=arguments,
            )
        )

    def test_missing_text_is_declined_after_running(self) -> None:
        result = self.invoke(())

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.values, ())

    def test_an_unknown_argument_is_declined(self) -> None:
        result = self.invoke((("text", "hello"), ("extra", "no")))

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)

    def test_several_unknown_arguments_are_declined(self) -> None:
        result = self.invoke(
            (("text", "hello"), ("content", "no"), ("body", "no")),
        )

        self.assertFalse(result.succeeded)

    def test_no_alias_is_accepted_for_text(self) -> None:
        """One contract. 'content' is not a spelling of 'text'."""
        for alias in ("content", "input", "body", "message"):
            with self.subTest(alias=alias):
                self.assertFalse(self.invoke(((alias, "hello"),)).succeeded)

    def test_an_alias_alone_is_not_treated_as_missing_text_only(self) -> None:
        result = self.invoke((("content", "hello"),))

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)

    def test_a_non_string_value_never_reaches_the_tool(self) -> None:
        """The invocation contract owns this one, so construction fails first."""
        from core.Exceptions import ResearchError

        for value in (123, True, [], {}, None):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    ToolInvocation(
                        capability=ToolCapability.TEXT_STATISTICS,
                        authorized_effects=PURE,
                        arguments=(("text", value),),  # type: ignore[arg-type]
                    )

    def test_the_tool_still_refuses_to_coerce_a_non_string(self) -> None:
        """Defence in depth: a tool does not assume its caller validated."""
        smuggled = object.__new__(ToolInvocation)
        object.__setattr__(smuggled, "capability", ToolCapability.TEXT_STATISTICS)
        object.__setattr__(smuggled, "authorized_effects", PURE)
        object.__setattr__(smuggled, "arguments", (("text", 12345),))

        result = TextStatisticsTool().invoke(smuggled)

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.values, ())

    def test_declining_is_not_dressed_up_as_a_refusal(self) -> None:
        """It ran. Saying otherwise would borrow the gate's vocabulary."""
        self.assertTrue(self.invoke(()).performed)


class ResultSafetyTests(unittest.TestCase):
    """Derived counts go out. The text does not."""

    def invoke(self, arguments: tuple[tuple[str, str], ...]) -> object:
        return TextStatisticsTool().invoke(
            ToolInvocation(
                capability=ToolCapability.TEXT_STATISTICS,
                authorized_effects=PURE,
                arguments=arguments,
            )
        )

    def test_the_result_never_echoes_the_input(self) -> None:
        result = self.invoke((("text", SENTINEL),))

        self.assertNotIn(SENTINEL, str(result.values))
        self.assertNotIn(SENTINEL, result.detail)

    def test_the_result_returns_only_the_four_counts(self) -> None:
        names = [name for name, _ in self.invoke((("text", "a b"),)).values]

        self.assertEqual(
            names,
            [
                "character_count",
                "word_count",
                "line_count",
                "non_whitespace_character_count",
            ],
        )

    def test_a_failure_detail_never_quotes_the_input(self) -> None:
        result = self.invoke((("text", SENTINEL), ("extra", SENTINEL)))

        self.assertFalse(result.succeeded)
        self.assertNotIn(SENTINEL, result.detail)

    def test_a_failure_detail_never_quotes_an_argument_name(self) -> None:
        result = self.invoke((("text", "hi"), (SENTINEL, "no")))

        self.assertNotIn(SENTINEL, result.detail)

    def test_the_result_names_its_own_capability(self) -> None:
        self.assertIs(
            self.invoke((("text", "a"),)).capability,
            ToolCapability.TEXT_STATISTICS,
        )


class TextStatisticsEndToEndTests(unittest.TestCase):
    """Registry, gate, events, implementation, result — one real path."""

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.registry = ToolRegistry()
        self.registry.register(TextStatisticsTool())
        self.service = ToolExecutionService(
            self.registry,
            event_bus=self.event_bus,
            id_factory=lambda: "request-1",
        )

    def invocation(
        self,
        arguments: tuple[tuple[str, str], ...] = (("text", "a b"),),
        authorized: frozenset[ToolEffect] = PURE,
    ) -> ToolInvocation:
        return ToolInvocation(
            capability=ToolCapability.TEXT_STATISTICS,
            authorized_effects=authorized,
            arguments=arguments,
        )

    def names(self) -> list[str]:
        return [event.name for event in self.events if event.name.startswith("tool.")]

    def test_the_whole_path_runs_and_reports_counts(self) -> None:
        outcome = self.service.execute_detailed(
            self.invocation((("text", "Hypatia learns safely.\nEvidence first."),))
        )

        self.assertTrue(outcome.resolved)
        self.assertTrue(outcome.authorized)
        self.assertIsNone(outcome.failure_kind)
        self.assertTrue(outcome.result.succeeded)
        self.assertEqual(dict(outcome.result.values)["word_count"], "5")
        self.assertEqual(dict(outcome.result.values)["line_count"], "2")

    def test_success_emits_the_full_lifecycle_in_order(self) -> None:
        self.service.execute(self.invocation())

        self.assertEqual(
            self.names(),
            [TOOL_REQUESTED, TOOL_AUTHORIZED, TOOL_STARTED, TOOL_COMPLETED],
        )

    def test_bad_arguments_fail_after_starting_not_before(self) -> None:
        """The tool ran, so the stream must say it ran."""
        self.service.execute(self.invocation(()))

        self.assertEqual(
            self.names(),
            [TOOL_REQUESTED, TOOL_AUTHORIZED, TOOL_STARTED, TOOL_FAILED],
        )

    def test_bad_arguments_are_not_reported_as_refused_before_execution(self) -> None:
        self.service.execute(self.invocation((("extra", "no"),)))

        failed = [e for e in self.events if e.name == TOOL_FAILED][0]
        self.assertIs(failed.payload["refused_before_execution"], False)
        self.assertEqual(
            failed.payload["failure_kind"],
            ToolFailureKind.INVOCATION_DECLINED,
        )
        self.assertIs(failed.payload["performed"], True)

    def test_bad_arguments_are_a_decline_and_not_an_attempt(self) -> None:
        """The tool read the request and stopped. Nothing was counted."""
        self.service.execute(self.invocation((("extra", "no"),)))

        payload = [e for e in self.events if e.name == TOOL_FAILED][0].payload
        self.assertIs(payload["attempted_the_work"], False)
        self.assertIs(payload["concerns_the_request"], True)
        self.assertEqual(payload["disposition"], "declined")

    def test_bad_arguments_produce_a_decline_not_an_authorization_failure(
        self,
    ) -> None:
        outcome = self.service.execute_detailed(self.invocation(()))

        self.assertTrue(outcome.authorized)
        self.assertIs(outcome.failure_kind, ToolFailureKind.INVOCATION_DECLINED)
        self.assertFalse(outcome.failure_kind.concerns_authorization)
        self.assertFalse(outcome.failure_kind.attempted_the_work)
        self.assertTrue(outcome.result.declined_request)

    def test_a_pure_tool_is_still_refused_without_a_grant(self) -> None:
        """Purity is granted, not assumed. No exemption for touching nothing."""
        outcome = self.service.execute_detailed(self.invocation(authorized=frozenset()))

        self.assertFalse(outcome.result.performed)
        self.assertIs(outcome.failure_kind, ToolFailureKind.UNAUTHORIZED_EFFECT)
        self.assertEqual(self.names(), [TOOL_REQUESTED, TOOL_FAILED])

    def test_an_unrelated_grant_does_not_authorize_it(self) -> None:
        outcome = self.service.execute_detailed(
            self.invocation(authorized=frozenset({ToolEffect.READS_LOCAL_STATE}))
        )

        self.assertIs(outcome.failure_kind, ToolFailureKind.UNAUTHORIZED_EFFECT)

    def test_no_lifecycle_event_carries_the_text(self) -> None:
        self.service.execute(self.invocation((("text", SENTINEL),)))

        payloads = str([event.payload for event in self.events])
        self.assertNotIn(SENTINEL, payloads)

    def test_no_failure_event_carries_the_text(self) -> None:
        self.service.execute(self.invocation((("text", SENTINEL), ("extra", SENTINEL))))

        payloads = str([event.payload for event in self.events])
        self.assertNotIn(SENTINEL, payloads)
        self.assertIn(TOOL_FAILED, self.names())

    def test_telemetry_counts_arguments_rather_than_carrying_them(self) -> None:
        self.service.execute(self.invocation((("text", SENTINEL),)))

        requested = [e for e in self.events if e.name == TOOL_REQUESTED][0]
        self.assertEqual(requested.payload["argument_count"], 1)
        self.assertNotIn("arguments", requested.payload)

    def test_the_completion_event_counts_values_rather_than_carrying_them(
        self,
    ) -> None:
        self.service.execute(self.invocation())

        completed = [e for e in self.events if e.name == TOOL_COMPLETED][0]
        self.assertEqual(completed.payload["value_count"], 4)
        self.assertIs(completed.payload["read_only"], True)
        self.assertIs(completed.payload["reaches_outside"], False)

    def test_a_cancelled_invocation_never_reaches_the_tool(self) -> None:
        signal = CancellationSignal()
        signal.cancel()

        outcome = self.service.execute_detailed(
            self.invocation(),
            cancellation_token=signal,
        )

        self.assertIs(outcome.failure_kind, ToolFailureKind.CANCELLED)
        self.assertFalse(outcome.result.performed)

    def test_the_registry_resolves_the_exact_capability(self) -> None:
        resolved = self.registry.resolve(ToolCapability.TEXT_STATISTICS)

        self.assertIsInstance(resolved, TextStatisticsTool)

    def test_an_unregistered_capability_does_not_reach_this_tool(self) -> None:
        outcome = self.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.KNOWLEDGE_DOCUMENT_LIST,
                authorized_effects=PURE,
            )
        )

        self.assertFalse(outcome.resolved)
        self.assertIs(outcome.failure_kind, ToolFailureKind.UNKNOWN_CAPABILITY)


class RegistryCompositionTests(unittest.TestCase):
    """Both concrete tools, and nothing that reaches anything dangerous."""

    def setUp(self) -> None:
        from datetime import UTC, datetime

        self.registry = ToolRegistry()
        self.registry.register(TextStatisticsTool())
        self.registry.register(
            ClockReadTool(clock=lambda: datetime(2026, 8, 24, 9, 30, tzinfo=UTC))
        )

    def test_registration_order_does_not_decide_the_reported_order(self) -> None:
        """The registry reports declared enum order, not insertion order."""
        self.assertEqual(
            self.registry.registered_capabilities,
            (ToolCapability.CLOCK_READ, ToolCapability.TEXT_STATISTICS),
        )

    def test_only_the_two_intended_capabilities_are_registered(self) -> None:
        self.assertEqual(len(self.registry.registered_capabilities), 2)

    def test_no_registered_tool_reaches_outside_this_machine(self) -> None:
        for capability in self.registry.registered_capabilities:
            with self.subTest(capability=capability):
                tool = self.registry.resolve(capability)
                assert tool is not None
                self.assertFalse(tool.descriptor.reaches_outside)
                self.assertTrue(tool.descriptor.read_only)

    def test_each_tool_answers_only_for_its_own_capability(self) -> None:
        for capability in self.registry.registered_capabilities:
            with self.subTest(capability=capability):
                tool = self.registry.resolve(capability)
                assert tool is not None
                self.assertIs(tool.descriptor.capability, capability)


if __name__ == "__main__":
    unittest.main()
