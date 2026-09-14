"""The harmless tool proves the path the dangerous ones will travel.

Nothing here is about telling the time. It is about showing that an invocation
goes registry, gate, events, implementation, result — in that order, with the
result and the telemetry both describing what actually happened — while the worst
possible bug is a wrong clock reading.

The clock is injected in every test. A tool that read the wall clock could only
be asserted against the second it happened to run in, which is not a test, and
the point of this file is that the assertions mean something.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from tools.ClockReadTool import ClockReadTool
from tools.ToolCapability import ToolCapability
from tools.ToolEffect import ToolEffect
from tools.ToolEvents import (
    TOOL_AUTHORIZED,
    TOOL_COMPLETED,
    TOOL_REQUESTED,
    TOOL_STARTED,
)
from tools.ToolExecutionService import ToolExecutionService
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRegistry import ToolRegistry

FIXED = datetime(2026, 8, 24, 9, 30, 15, tzinfo=UTC)
READ_LOCAL = frozenset({ToolEffect.READS_LOCAL_STATE})


class ClockReadDescriptorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = ClockReadTool(clock=lambda: FIXED)

    def test_it_declares_the_clock_capability(self) -> None:
        self.assertIs(self.tool.descriptor.capability, ToolCapability.CLOCK_READ)

    def test_it_declares_only_reading_local_state(self) -> None:
        """Declaring more would be a lie the gate then enforces as truth."""
        self.assertEqual(self.tool.descriptor.effects, READ_LOCAL)

    def test_it_declares_no_effect_it_does_not_have(self) -> None:
        for absent in (
            ToolEffect.WRITES_LOCAL_STATE,
            ToolEffect.READS_NETWORK,
            ToolEffect.SPENDS_MODEL,
        ):
            with self.subTest(effect=absent):
                self.assertNotIn(absent, self.tool.descriptor.effects)

    def test_it_is_read_only_and_reaches_nothing_outside(self) -> None:
        self.assertTrue(self.tool.descriptor.read_only)
        self.assertFalse(self.tool.descriptor.reaches_outside)


class ClockReadBehaviourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = ClockReadTool(clock=lambda: FIXED)

    def invoke(self, arguments: tuple[tuple[str, str], ...] = ()) -> object:
        return self.tool.invoke(
            ToolInvocation(
                capability=ToolCapability.CLOCK_READ,
                authorized_effects=READ_LOCAL,
                arguments=arguments,
            )
        )

    def test_it_returns_the_injected_time(self) -> None:
        result = self.invoke()

        self.assertEqual(dict(result.values)["utc_iso"], FIXED.isoformat())

    def test_it_returns_structured_values_not_prose(self) -> None:
        result = self.invoke()
        values = dict(result.values)

        self.assertEqual(values["utc_date"], "2026-08-24")
        self.assertEqual(values["utc_time"], "09:30:15")
        self.assertEqual(values["timezone"], "UTC")

    def test_a_non_utc_clock_is_normalised(self) -> None:
        offset = timezone(timedelta(hours=3))
        tool = ClockReadTool(clock=lambda: FIXED.astimezone(offset))

        result = tool.invoke(
            ToolInvocation(
                capability=ToolCapability.CLOCK_READ,
                authorized_effects=READ_LOCAL,
            )
        )

        self.assertEqual(dict(result.values)["utc_iso"], FIXED.isoformat())

    def test_an_ambiguous_local_time_is_refused(self) -> None:
        tool = ClockReadTool(clock=lambda: datetime(2026, 8, 24, 9, 30))

        with self.assertRaises(ResearchError):
            tool.invoke(
                ToolInvocation(
                    capability=ToolCapability.CLOCK_READ,
                    authorized_effects=READ_LOCAL,
                )
            )

    def test_it_accepts_no_arguments(self) -> None:
        result = self.invoke((("timezone", "Europe/Istanbul"),))

        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.assertEqual(result.values, ())

    def test_rejecting_arguments_still_counts_as_having_run(self) -> None:
        """It was reached, it looked at what it was given, and it declined."""
        result = self.invoke((("anything", "at all"),))

        self.assertTrue(result.performed)

    def test_the_result_names_its_own_capability(self) -> None:
        self.assertIs(self.invoke().capability, ToolCapability.CLOCK_READ)


class ClockReadEndToEndTests(unittest.TestCase):
    """Registry, gate, events, implementation, result — one real path."""

    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.registry = ToolRegistry()
        self.registry.register(ClockReadTool(clock=lambda: FIXED))
        self.service = ToolExecutionService(
            self.registry,
            event_bus=self.event_bus,
            id_factory=lambda: "request-1",
        )

    def invocation(
        self,
        authorized: frozenset[ToolEffect] = READ_LOCAL,
    ) -> ToolInvocation:
        return ToolInvocation(
            capability=ToolCapability.CLOCK_READ,
            authorized_effects=authorized,
        )

    def names(self) -> list[str]:
        return [event.name for event in self.events if event.name.startswith("tool.")]

    def test_the_whole_path_runs_and_reports_the_time(self) -> None:
        outcome = self.service.execute_detailed(self.invocation())

        self.assertTrue(outcome.resolved)
        self.assertTrue(outcome.authorized)
        self.assertIsNone(outcome.failure_kind)
        self.assertTrue(outcome.result.performed)
        self.assertTrue(outcome.result.succeeded)
        self.assertEqual(dict(outcome.result.values)["utc_iso"], FIXED.isoformat())

    def test_the_path_emits_the_full_lifecycle_in_order(self) -> None:
        self.service.execute(self.invocation())

        self.assertEqual(
            self.names(),
            [TOOL_REQUESTED, TOOL_AUTHORIZED, TOOL_STARTED, TOOL_COMPLETED],
        )

    def test_the_completion_event_carries_no_time_value(self) -> None:
        """Even a harmless value stays out of generic telemetry."""
        self.service.execute(self.invocation())

        payloads = str([event.payload for event in self.events])
        self.assertNotIn(FIXED.isoformat(), payloads)

    def test_the_clock_tool_is_not_exempt_from_the_gate(self) -> None:
        """No trusted-tool shortcut, however harmless the tool is."""
        outcome = self.service.execute_detailed(self.invocation(frozenset()))

        self.assertFalse(outcome.result.performed)
        self.assertIs(outcome.failure_kind, ToolFailureKind.UNAUTHORIZED_EFFECT)
        self.assertNotIn(TOOL_STARTED, self.names())

    def test_a_cancelled_clock_read_never_reads_the_clock(self) -> None:
        signal = CancellationSignal()
        signal.cancel()

        outcome = self.service.execute_detailed(
            self.invocation(),
            cancellation_token=signal,
        )

        self.assertIs(outcome.failure_kind, ToolFailureKind.CANCELLED)
        self.assertFalse(outcome.result.performed)

    def test_another_capability_does_not_reach_the_clock_tool(self) -> None:
        outcome = self.service.execute_detailed(
            ToolInvocation(
                capability=ToolCapability.TEXT_STATISTICS,
                authorized_effects=READ_LOCAL,
            )
        )

        self.assertFalse(outcome.resolved)
        self.assertIs(outcome.failure_kind, ToolFailureKind.UNKNOWN_CAPABILITY)

    def test_nothing_registers_a_powerful_capability(self) -> None:
        """The milestone deliberately ships one harmless tool and no others."""
        self.assertEqual(
            self.registry.registered_capabilities,
            (ToolCapability.CLOCK_READ,),
        )


if __name__ == "__main__":
    unittest.main()
