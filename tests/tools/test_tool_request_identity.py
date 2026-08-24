"""Code-owned identity shared by one tool outcome and its lifecycle events."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from typing import Any, cast

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.CancellationSignal import CancellationSignal
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from tools.FilesystemContentPayload import FilesystemContentPayload
from tools.ToolCapability import ToolCapability
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolEffect import ToolEffect
from tools.ToolExecutionOutcome import (
    MAX_TOOL_REQUEST_ID_LENGTH,
    ToolExecutionOutcome,
)
from tools.ToolExecutionService import ToolExecutionService
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRegistry import ToolRegistry
from tools.ToolResult import ToolResult

READ_LOCAL = frozenset({ToolEffect.READS_LOCAL_STATE})
READ_NETWORK = frozenset({ToolEffect.READS_NETWORK})


class ReturningTool:
    def __init__(
        self,
        *,
        effects: frozenset[ToolEffect] = READ_LOCAL,
        raises: bool = False,
        declines: bool = False,
    ) -> None:
        self._descriptor = ToolDescriptor(
            capability=ToolCapability.CLOCK_READ,
            effects=effects,
            summary="Returns one bounded test result.",
        )
        self.raises = raises
        self.declines = declines
        self.calls: list[ToolInvocation] = []

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        self.calls.append(invocation)
        if self.raises:
            raise ResearchError("A private tool failure.")
        if self.declines:
            return ToolResult.declined(
                ToolCapability.CLOCK_READ,
                "The bounded request was declined.",
            )
        return ToolResult(
            capability=ToolCapability.CLOCK_READ,
            performed=True,
            detail="Returned the test value.",
            values=(("value", "one"),),
        )


def invocation(
    capability: ToolCapability = ToolCapability.CLOCK_READ,
    effects: frozenset[ToolEffect] = READ_LOCAL,
) -> ToolInvocation:
    return ToolInvocation(capability=capability, authorized_effects=effects)


class ToolRequestIdentifierValueTests(unittest.TestCase):
    def outcome(self, request_id: object) -> ToolExecutionOutcome:
        return ToolExecutionOutcome(
            capability=ToolCapability.CLOCK_READ,
            result=ToolResult(
                capability=ToolCapability.CLOCK_READ,
                performed=True,
                detail="Completed.",
            ),
            resolved=True,
            authorized=True,
            request_id=cast(Any, request_id),
        )

    def test_identifier_is_required_bounded_and_immutable(self) -> None:
        request_id = "r" * MAX_TOOL_REQUEST_ID_LENGTH

        outcome = self.outcome(request_id)

        self.assertEqual(outcome.request_id, request_id)
        with self.assertRaises(FrozenInstanceError):
            outcome.request_id = "replacement"  # type: ignore[misc]

    def test_non_text_empty_and_overlong_identifiers_are_refused(self) -> None:
        for value in (None, 7, b"request-1", "", "r" * 101):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    self.outcome(value)

    def test_whitespace_control_unicode_and_path_tokens_are_refused(self) -> None:
        for value in (
            " request-1",
            "request-1 ",
            "request\n1",
            "request\t1",
            "istek-ç",
            "../request-1",
            "request/1",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    self.outcome(value)


class ToolRequestIdentifierExecutionTests(unittest.TestCase):
    def service(
        self,
        request_ids: object,
        *,
        tool: ReturningTool | None = None,
        event_bus: EventBus | None = None,
    ) -> ToolExecutionService:
        registry = ToolRegistry()
        if tool is not None:
            registry.register(tool)
        return ToolExecutionService(
            registry,
            event_bus=event_bus,
            id_factory=cast(Any, request_ids),
        )

    def test_success_outcome_and_every_event_share_one_factory_identifier(self) -> None:
        calls = 0

        def next_id() -> str:
            nonlocal calls
            calls += 1
            return "request-success-1"

        event_bus = EventBus()
        events: list[Event] = []
        event_bus.subscribe("*", events.append)
        tool = ReturningTool()

        outcome = self.service(
            next_id, tool=tool, event_bus=event_bus
        ).execute_detailed(invocation())

        self.assertEqual(calls, 1)
        self.assertEqual(outcome.request_id, "request-success-1")
        self.assertEqual(
            {event.payload["request_id"] for event in events},
            {outcome.request_id},
        )

    def test_unknown_unauthorized_cancelled_and_failed_outcomes_keep_the_id(
        self,
    ) -> None:
        signal = CancellationSignal()
        signal.cancel()
        cases = (
            (
                "request-unknown-1",
                None,
                invocation(ToolCapability.FILESYSTEM_READ),
                None,
                ToolFailureKind.UNKNOWN_CAPABILITY,
            ),
            (
                "request-unauthorized-1",
                ReturningTool(effects=READ_NETWORK),
                invocation(),
                None,
                ToolFailureKind.UNAUTHORIZED_EFFECT,
            ),
            (
                "request-cancelled-1",
                ReturningTool(),
                invocation(),
                signal,
                ToolFailureKind.CANCELLED,
            ),
            (
                "request-declined-1",
                ReturningTool(declines=True),
                invocation(),
                None,
                ToolFailureKind.INVOCATION_DECLINED,
            ),
            (
                "request-failed-1",
                ReturningTool(raises=True),
                invocation(),
                None,
                ToolFailureKind.EXECUTION_FAILED,
            ),
        )

        for expected_id, tool, request, cancellation, kind in cases:
            with self.subTest(kind=kind):
                event_bus = EventBus()
                events: list[Event] = []
                event_bus.subscribe("*", events.append)
                service = self.service(
                    lambda expected_id=expected_id: expected_id,
                    tool=tool,
                    event_bus=event_bus,
                )
                outcome = service.execute_detailed(
                    request,
                    cancellation_token=cancellation,
                )
                self.assertEqual(outcome.request_id, expected_id)
                self.assertIs(outcome.failure_kind, kind)
                self.assertEqual(
                    {event.payload["request_id"] for event in events},
                    {outcome.request_id},
                )

    def test_each_invocation_gets_exactly_one_new_identifier(self) -> None:
        identifiers = iter(("request-1", "request-2"))
        service = self.service(lambda: next(identifiers), tool=ReturningTool())

        first = service.execute_detailed(invocation())
        second = service.execute_detailed(invocation())

        self.assertEqual(
            (first.request_id, second.request_id), ("request-1", "request-2")
        )

    def test_invalid_factory_value_stops_before_events_and_tool_execution(self) -> None:
        event_bus = EventBus()
        events: list[Event] = []
        event_bus.subscribe("*", events.append)
        tool = ReturningTool()
        service = self.service(
            lambda: "private\nidentifier",
            tool=tool,
            event_bus=event_bus,
        )

        with self.assertRaisesRegex(ResearchError, "safe ASCII token"):
            service.execute_detailed(invocation())

        self.assertEqual(events, [])
        self.assertEqual(tool.calls, [])

    def test_identifier_is_not_given_to_the_tool_or_ordinary_result(self) -> None:
        tool = ReturningTool()
        service = self.service(lambda: "request-private-1", tool=tool)

        outcome = service.execute_detailed(invocation())
        ordinary_result = service.execute(invocation())

        self.assertEqual(outcome.request_id, "request-private-1")
        self.assertFalse(hasattr(tool.calls[0], "request_id"))
        self.assertFalse(hasattr(outcome.result, "request_id"))
        self.assertFalse(hasattr(ordinary_result, "request_id"))

    def test_content_payload_cannot_author_an_invocation_identifier(self) -> None:
        payload_fields = {item.name for item in fields(FilesystemContentPayload)}

        self.assertNotIn("request_id", payload_fields)


if __name__ == "__main__":
    unittest.main()
