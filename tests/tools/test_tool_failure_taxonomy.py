"""Two things that used to be one fact, and the state that now separates them.

A tool that read its arguments and said no, and a tool that accepted the request
and broke partway through, both used to arrive as `TOOL_FAILED` with
`performed=True`. The only difference was the wording of a sentence. That made a
decision a later system has to make — is it worth asking differently? — depend
on reading English.

So the tests here are mostly about the four canonical outcomes staying four, and
about none of them being derivable from prose. The doubles are deliberately
built to be indistinguishable by their detail text: `DecliningTool` and
`BreakingTool` return and raise respectively while saying nothing that reveals
which is which, so any implementation that classified by wording would fail
these rather than pass them.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from tools.ClockReadTool import ClockReadTool
from tools.TextStatisticsTool import TextStatisticsTool
from tools.ToolCapability import ToolCapability
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolDisposition import ToolDisposition
from tools.ToolEffect import ToolEffect
from tools.ToolEvents import TOOL_FAILED, TOOL_STARTED
from tools.ToolExecutionService import ToolExecutionService
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRegistry import ToolRegistry
from tools.ToolResult import ToolResult

READ_LOCAL = frozenset({ToolEffect.READS_LOCAL_STATE})

#: The same words for both doubles. Any classifier that reads the sentence gets
#: the same answer for a decline and a failure, so these tests catch it.
AMBIGUOUS_DETAIL = "That did not work out."


class DecliningTool:
    """A tool that reads the request and will not take it."""

    def __init__(self) -> None:
        self.calls = 0
        self._descriptor = ToolDescriptor(
            capability=ToolCapability.CLOCK_READ,
            effects=READ_LOCAL,
            summary="Declines everything, on purpose.",
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        self.calls += 1
        return ToolResult.declined(ToolCapability.CLOCK_READ, AMBIGUOUS_DETAIL)


class BreakingTool:
    """A tool that accepts the request and breaks partway through."""

    SECRET = "C:/Users/someone/private/thing.txt"

    def __init__(self) -> None:
        self.calls = 0
        self._descriptor = ToolDescriptor(
            capability=ToolCapability.CLOCK_READ,
            effects=READ_LOCAL,
            summary="Starts work and then fails, on purpose.",
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        self.calls += 1
        raise ResearchError(f"{AMBIGUOUS_DETAIL} while reading {self.SECRET}")


class SelfReportingFailureTool:
    """A tool that catches its own error and reports the attempt honestly."""

    def __init__(self) -> None:
        self._descriptor = ToolDescriptor(
            capability=ToolCapability.CLOCK_READ,
            effects=READ_LOCAL,
            summary="Catches its own failure and says so.",
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        return ToolResult.failed(ToolCapability.CLOCK_READ, AMBIGUOUS_DETAIL)


class TaxonomyFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.registry = ToolRegistry()
        self.service = ToolExecutionService(
            self.registry,
            event_bus=self.event_bus,
            id_factory=lambda: "request-1",
        )

    def run_with(self, tool: object, granted: frozenset = READ_LOCAL) -> object:
        self.registry.register(tool)
        return self.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.CLOCK_READ,
                authorized_effects=granted,
            )
        )

    def names(self) -> list[str]:
        return [event.name for event in self.events if event.name.startswith("tool.")]

    def failed_payload(self) -> dict[str, object]:
        return [e for e in self.events if e.name == TOOL_FAILED][0].payload


class FourOutcomesTests(TaxonomyFixture):
    """The whole point: four realities, four structurally different answers."""

    def test_authorization_denied_has_its_own_state(self) -> None:
        outcome = self.run_with(ClockReadTool(), frozenset())

        self.assertIs(outcome.failure_kind, ToolFailureKind.UNAUTHORIZED_EFFECT)
        self.assertTrue(outcome.failure_kind.concerns_authorization)
        self.assertTrue(outcome.failure_kind.refused_before_execution)
        self.assertFalse(outcome.failure_kind.attempted_the_work)

    def test_a_declined_invocation_has_its_own_state(self) -> None:
        outcome = self.run_with(DecliningTool())

        self.assertIs(outcome.failure_kind, ToolFailureKind.INVOCATION_DECLINED)
        self.assertFalse(outcome.failure_kind.concerns_authorization)
        self.assertFalse(outcome.failure_kind.refused_before_execution)
        self.assertFalse(outcome.failure_kind.attempted_the_work)
        self.assertTrue(outcome.failure_kind.concerns_the_request)

    def test_a_failed_execution_has_its_own_state(self) -> None:
        outcome = self.run_with(BreakingTool())

        self.assertIs(outcome.failure_kind, ToolFailureKind.EXECUTION_FAILED)
        self.assertFalse(outcome.failure_kind.concerns_authorization)
        self.assertFalse(outcome.failure_kind.refused_before_execution)
        self.assertTrue(outcome.failure_kind.attempted_the_work)
        self.assertFalse(outcome.failure_kind.concerns_the_request)

    def test_success_remains_success(self) -> None:
        outcome = self.run_with(ClockReadTool())

        self.assertIsNone(outcome.failure_kind)
        self.assertTrue(outcome.result.succeeded)
        self.assertIs(outcome.result.disposition, ToolDisposition.COMPLETED)

    def test_all_four_outcomes_are_mutually_distinct(self) -> None:
        """No two of them collapse into the same structured answer."""
        seen = []
        for tool, grant in (
            (ClockReadTool(), frozenset()),
            (DecliningTool(), READ_LOCAL),
            (BreakingTool(), READ_LOCAL),
            (ClockReadTool(), READ_LOCAL),
        ):
            registry = ToolRegistry()
            registry.register(tool)
            service = ToolExecutionService(registry)
            outcome = service.execute_detailed(
                ToolInvocation(
                    capability=ToolCapability.CLOCK_READ,
                    authorized_effects=grant,
                )
            )
            seen.append(
                (
                    outcome.failure_kind,
                    outcome.result.performed,
                    outcome.result.succeeded,
                    outcome.result.disposition,
                )
            )

        self.assertEqual(len(set(seen)), 4)

    def test_a_decline_and_a_failure_differ_despite_identical_wording(self) -> None:
        """The doubles say the same sentence. The state still separates them."""
        declining = self.run_with(DecliningTool())
        self.setUp()
        breaking = self.run_with(BreakingTool())

        self.assertIn(AMBIGUOUS_DETAIL, declining.result.detail)
        self.assertNotEqual(declining.failure_kind, breaking.failure_kind)
        self.assertNotEqual(
            declining.result.disposition,
            breaking.result.disposition,
        )

    def test_a_tool_may_report_its_own_failed_attempt_without_raising(self) -> None:
        """Catching your own error must not turn a failure into a decline."""
        outcome = self.run_with(SelfReportingFailureTool())

        self.assertIs(outcome.failure_kind, ToolFailureKind.EXECUTION_FAILED)
        self.assertTrue(outcome.result.failed_execution)


class StateMatrixTests(TaxonomyFixture):
    """performed, succeeded and disposition must agree, always."""

    def test_authorization_denied_performed_nothing(self) -> None:
        outcome = self.run_with(ClockReadTool(), frozenset())

        self.assertFalse(outcome.result.performed)
        self.assertFalse(outcome.result.succeeded)
        self.assertIs(outcome.result.disposition, ToolDisposition.NOT_REACHED)

    def test_a_decline_performed_but_did_not_attempt(self) -> None:
        outcome = self.run_with(DecliningTool())

        self.assertTrue(outcome.result.performed)
        self.assertFalse(outcome.result.succeeded)
        self.assertIs(outcome.result.disposition, ToolDisposition.DECLINED)
        self.assertFalse(outcome.result.disposition.attempted_the_work)

    def test_a_failure_performed_and_attempted(self) -> None:
        outcome = self.run_with(BreakingTool())

        self.assertTrue(outcome.result.performed)
        self.assertFalse(outcome.result.succeeded)
        self.assertIs(outcome.result.disposition, ToolDisposition.FAILED)
        self.assertTrue(outcome.result.disposition.attempted_the_work)

    def test_success_performed_attempted_and_succeeded(self) -> None:
        outcome = self.run_with(ClockReadTool())

        self.assertTrue(outcome.result.performed)
        self.assertTrue(outcome.result.succeeded)
        self.assertTrue(outcome.result.disposition.attempted_the_work)

    def test_cancellation_reached_no_tool(self) -> None:
        signal = CancellationSignal()
        signal.cancel()
        self.registry.register(ClockReadTool())

        outcome = self.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.CLOCK_READ,
                authorized_effects=READ_LOCAL,
            ),
            cancellation_token=signal,
        )

        self.assertIs(outcome.failure_kind, ToolFailureKind.CANCELLED)
        self.assertIs(outcome.result.disposition, ToolDisposition.NOT_REACHED)

    def test_performed_and_disposition_are_defined_against_each_other(self) -> None:
        for disposition in ToolDisposition:
            with self.subTest(disposition=disposition):
                self.assertIs(
                    disposition.entered_the_tool,
                    disposition is not ToolDisposition.NOT_REACHED,
                )

    def test_a_disposition_disagreeing_with_performed_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ToolResult(
                capability=ToolCapability.CLOCK_READ,
                performed=False,
                detail="Impossible.",
                succeeded=False,
                disposition=ToolDisposition.FAILED,
            )

    def test_a_declined_result_claiming_success_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ToolResult(
                capability=ToolCapability.CLOCK_READ,
                performed=True,
                detail="Contradictory.",
                succeeded=True,
                disposition=ToolDisposition.DECLINED,
            )

    def test_a_completed_result_claiming_failure_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ToolResult(
                capability=ToolCapability.CLOCK_READ,
                performed=True,
                detail="Contradictory.",
                succeeded=False,
                disposition=ToolDisposition.COMPLETED,
            )

    def test_a_never_reached_result_cannot_have_entered_the_tool(self) -> None:
        with self.assertRaises(ResearchError):
            ToolResult(
                capability=ToolCapability.CLOCK_READ,
                performed=True,
                detail="Contradictory.",
                succeeded=False,
                disposition=ToolDisposition.NOT_REACHED,
            )

    def test_an_unsuccessful_result_defaults_to_the_weaker_claim(self) -> None:
        """Not saying which is safer than guessing 'the machine is broken'."""
        result = ToolResult(
            capability=ToolCapability.CLOCK_READ,
            performed=True,
            detail="Unspecified.",
            succeeded=False,
        )

        self.assertIs(result.disposition, ToolDisposition.DECLINED)


class LifecycleTests(TaxonomyFixture):
    """A subscriber can tell them apart without reading anything."""

    def test_a_decline_reports_bounded_fields_not_prose(self) -> None:
        self.run_with(DecliningTool())

        payload = self.failed_payload()
        self.assertEqual(payload["failure_kind"], "invocation_declined")
        self.assertIs(payload["attempted_the_work"], False)
        self.assertIs(payload["concerns_the_request"], True)
        self.assertEqual(payload["disposition"], "declined")

    def test_a_failure_reports_different_bounded_fields(self) -> None:
        self.run_with(BreakingTool())

        payload = self.failed_payload()
        self.assertEqual(payload["failure_kind"], "execution_failed")
        self.assertIs(payload["attempted_the_work"], True)
        self.assertIs(payload["concerns_the_request"], False)
        self.assertEqual(payload["disposition"], "failed")

    def test_authorization_denial_stays_distinct_in_the_stream(self) -> None:
        self.run_with(ClockReadTool(), frozenset())

        payload = self.failed_payload()
        self.assertEqual(payload["failure_kind"], "unauthorized_effect")
        self.assertIs(payload["refused_before_execution"], True)
        self.assertIs(payload["attempted_the_work"], False)
        self.assertNotIn(TOOL_STARTED, self.names())

    def test_both_tool_outcomes_still_start_before_failing(self) -> None:
        for tool in (DecliningTool(), BreakingTool()):
            self.setUp()
            with self.subTest(tool=type(tool).__name__):
                self.run_with(tool)
                self.assertIn(TOOL_STARTED, self.names())

    def test_no_event_carries_the_detail_sentence(self) -> None:
        self.run_with(DecliningTool())

        payloads = str([event.payload for event in self.events])
        self.assertNotIn(AMBIGUOUS_DETAIL, payloads)

    def test_a_raised_failure_leaks_no_exception_text(self) -> None:
        self.run_with(BreakingTool())

        payloads = str([event.payload for event in self.events])
        self.assertNotIn(BreakingTool.SECRET, payloads)
        self.assertNotIn(BreakingTool.SECRET, self.failed_payload().get("detail", ""))

    def test_a_raised_failure_leaks_no_path_into_the_result(self) -> None:
        outcome = self.run_with(BreakingTool())

        self.assertNotIn(BreakingTool.SECRET, outcome.result.detail)
        self.assertNotIn("someone", outcome.result.detail)


class NoProseClassificationTests(unittest.TestCase):
    """The category must never be decided by reading the sentence."""

    CLASSIFIERS = (
        Path("tools") / "ToolExecutionService.py",
        Path("tools") / "ToolFailureKind.py",
        Path("tools") / "ToolResult.py",
        Path("desktop") / "ToolConsoleController.py",
        Path("desktop") / "ToolRunStatus.py",
        Path("desktop") / "ToolRunView.py",
    )

    def test_no_classifier_inspects_detail_text(self) -> None:
        for name in self.CLASSIFIERS:
            tree = ast.parse((SRC_DIR / name).read_text(encoding="utf-8"))
            reads = [
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute) and node.attr == "detail"
            ]
            comparisons = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Compare)
                and any(isinstance(op, ast.In) for op in node.ops)
                and "detail" in ast.dump(node)
            ]
            with self.subTest(module=str(name)):
                self.assertEqual(comparisons, [], f"{name} compares against detail")
                self.assertLessEqual(len(reads), 4)

    def test_no_classifier_inspects_a_detail_string(self) -> None:
        """Targeted at `detail` specifically.

        A blanket ban on `.startswith(` would also catch filtering event names
        by prefix, which is not prose classification and is exactly how a guard
        gets deleted for being wrong rather than tightened for being loose.
        """
        import re

        patterns = (
            re.compile(r"detail\s*\.\s*(lower|casefold|startswith|endswith|find)"),
            re.compile(r"detail\s*=="),
            re.compile(r"\bin\s+\w*detail\b"),
            re.compile(r"detail\s*\.\s*__contains__"),
        )
        for name in self.CLASSIFIERS:
            source = (SRC_DIR / name).read_text(encoding="utf-8")
            for pattern in patterns:
                with self.subTest(module=str(name), pattern=pattern.pattern):
                    self.assertIsNone(pattern.search(source))

    def test_no_classifier_lowercases_anything_at_all(self) -> None:
        """Case folding is only ever needed to compare text, never an enum."""
        for name in self.CLASSIFIERS:
            source = (SRC_DIR / name).read_text(encoding="utf-8")
            for forbidden in (".lower()", ".casefold()"):
                with self.subTest(module=str(name), pattern=forbidden):
                    self.assertNotIn(forbidden, source)

    def test_the_service_classifies_from_the_disposition_alone(self) -> None:
        source = (SRC_DIR / "tools" / "ToolExecutionService.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("ToolFailureKind.for_disposition(result.disposition)", source)

    def test_the_failure_kind_translation_has_exactly_one_home(self) -> None:
        """One translation point, so the vocabularies cannot drift apart."""
        producers = []
        for path in (SRC_DIR / "tools").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "INVOCATION_DECLINED" in text or "EXECUTION_FAILED" in text:
                producers.append(path.name)

        self.assertEqual(sorted(producers), ["ToolFailureKind.py"])


class RealToolTests(TaxonomyFixture):
    """The production tools classify themselves correctly."""

    def test_text_statistics_declines_a_bad_argument(self) -> None:
        registry = ToolRegistry()
        registry.register(TextStatisticsTool())
        service = ToolExecutionService(registry)

        outcome = service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.TEXT_STATISTICS,
                authorized_effects=frozenset({ToolEffect.COMPUTES_LOCALLY}),
            )
        )

        self.assertIs(outcome.failure_kind, ToolFailureKind.INVOCATION_DECLINED)

    def test_clock_read_declines_an_unsupported_argument(self) -> None:
        outcome = self.run_with(ClockReadTool())
        self.assertIsNone(outcome.failure_kind)

        self.setUp()
        self.registry.register(ClockReadTool())
        outcome = self.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.CLOCK_READ,
                authorized_effects=READ_LOCAL,
                arguments=(("timezone", "UTC"),),
            )
        )

        self.assertIs(outcome.failure_kind, ToolFailureKind.INVOCATION_DECLINED)

    def test_a_broken_clock_source_is_a_failed_attempt(self) -> None:
        """The request was fine. The environment was not."""
        outcome = self.run_with(ClockReadTool(clock=lambda: "not a time"))

        self.assertIs(outcome.failure_kind, ToolFailureKind.EXECUTION_FAILED)
        self.assertTrue(outcome.result.failed_execution)


if __name__ == "__main__":
    unittest.main()
