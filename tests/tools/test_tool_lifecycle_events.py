"""Tool telemetry must describe the invocation without carrying its contents.

Two separate dangers meet in a lifecycle event. The first is untruth: an
`authorized` event for a refused invocation, or a `started` event for a tool that
never ran, would make the stream a better story than the execution. The second is
leakage: lifecycle events are the most-copied, least-read artefact a system
produces, and the moment they carry arbitrary arguments or results they carry
whatever a future tool was handed — a token, a file, a command's output.

So the payload is bounded now, while the only tool is a clock and the stakes are
nothing. A rule established before it costs anything is a rule that survives the
first time it would be inconvenient. Counts of arguments and values are carried;
the arguments and values themselves are not.

Ordering is asserted exactly, because "the right events happened" and "they
happened in an order that describes what occurred" are different claims.
"""

from __future__ import annotations

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
from tools.ToolCapability import ToolCapability
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolEffect import ToolEffect
from tools.ToolEvents import (
    TOOL_AUTHORIZED,
    TOOL_CANCELLED,
    TOOL_COMPLETED,
    TOOL_FAILED,
    TOOL_REQUESTED,
    TOOL_STARTED,
)
from tools.ToolExecutionService import ToolExecutionService
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRegistry import ToolRegistry
from tools.ToolResult import ToolResult

READ_LOCAL = frozenset({ToolEffect.READS_LOCAL_STATE})
READ_AND_NETWORK = frozenset({ToolEffect.READS_LOCAL_STATE, ToolEffect.READS_NETWORK})

SECRET_ARGUMENT = "hunter2-token-do-not-log"
SECRET_VALUE = "contents-of-a-private-file"

PAYLOAD_FIELDS = frozenset(
    {
        "request_id",
        "capability",
        "authorized_effects",
        "argument_count",
        "performed",
        "succeeded",
    }
)


class EchoingTool:
    """Return the argument it was given, so leakage would be visible."""

    def __init__(
        self,
        effects: frozenset[ToolEffect] = READ_LOCAL,
        succeeds: bool = True,
        raises: bool = False,
    ) -> None:
        self._descriptor = ToolDescriptor(
            capability=ToolCapability.CLOCK_READ,
            effects=effects,
            summary="An echoing test tool.",
        )
        self.calls: list[ToolInvocation] = []
        self._succeeds = succeeds
        self._raises = raises

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        self.calls.append(invocation)
        if self._raises:
            raise ResearchError(f"failed while handling {SECRET_ARGUMENT}")
        return ToolResult(
            capability=ToolCapability.CLOCK_READ,
            performed=True,
            detail="echoed",
            succeeded=self._succeeds,
            values=(("secret", SECRET_VALUE),),
        )


class LifecycleFixture(unittest.TestCase):
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

    def register(self, **kwargs: object) -> EchoingTool:
        tool = EchoingTool(**kwargs)  # type: ignore[arg-type]
        self.registry.register(tool)
        return tool

    def invoke(
        self,
        authorized: frozenset[ToolEffect] = READ_LOCAL,
        capability: ToolCapability = ToolCapability.CLOCK_READ,
        cancellation_token: object | None = None,
    ) -> None:
        self.service.execute(
            ToolInvocation(
                capability=capability,
                authorized_effects=authorized,
                arguments=(("token", SECRET_ARGUMENT),),
            ),
            cancellation_token=cancellation_token,
        )

    def names(self) -> list[str]:
        return [event.name for event in self.events if event.name.startswith("tool.")]

    def named(self, name: str) -> list[Event]:
        return [event for event in self.events if event.name == name]


class LifecycleOrderTests(LifecycleFixture):
    def test_a_successful_invocation_walks_the_whole_path(self) -> None:
        self.register()

        self.invoke()

        self.assertEqual(
            self.names(),
            [TOOL_REQUESTED, TOOL_AUTHORIZED, TOOL_STARTED, TOOL_COMPLETED],
        )

    def test_an_unknown_capability_never_reports_authorization(self) -> None:
        self.invoke()

        self.assertEqual(self.names(), [TOOL_REQUESTED, TOOL_FAILED])
        self.assertEqual(self.named(TOOL_AUTHORIZED), [])
        self.assertEqual(self.named(TOOL_STARTED), [])

    def test_an_unauthorized_tool_never_reports_authorization_or_start(self) -> None:
        """The two events that would make a refusal look like a run."""
        tool = self.register(effects=READ_AND_NETWORK)

        self.invoke(READ_LOCAL)

        self.assertEqual(self.names(), [TOOL_REQUESTED, TOOL_FAILED])
        self.assertEqual(self.named(TOOL_AUTHORIZED), [])
        self.assertEqual(self.named(TOOL_STARTED), [])
        self.assertEqual(tool.calls, [])

    def test_a_refusal_never_reports_completion(self) -> None:
        self.register(effects=READ_AND_NETWORK)

        self.invoke(READ_LOCAL)

        self.assertEqual(self.named(TOOL_COMPLETED), [])

    def test_a_cancelled_invocation_reports_cancellation_not_failure(self) -> None:
        tool = self.register()
        signal = CancellationSignal()
        signal.cancel()

        self.invoke(cancellation_token=signal)

        self.assertEqual(self.names(), [TOOL_REQUESTED, TOOL_CANCELLED])
        self.assertEqual(self.named(TOOL_FAILED), [])
        self.assertEqual(tool.calls, [])

    def test_a_tool_that_raises_started_and_then_failed(self) -> None:
        self.register(raises=True)

        self.invoke()

        self.assertEqual(
            self.names(),
            [TOOL_REQUESTED, TOOL_AUTHORIZED, TOOL_STARTED, TOOL_FAILED],
        )

    def test_a_tool_that_ran_and_failed_reports_failure_after_starting(self) -> None:
        self.register(succeeds=False)

        self.invoke()

        self.assertEqual(
            self.names(),
            [TOOL_REQUESTED, TOOL_AUTHORIZED, TOOL_STARTED, TOOL_FAILED],
        )
        self.assertIs(self.named(TOOL_FAILED)[0].payload["performed"], True)

    def test_each_lifecycle_event_is_emitted_once(self) -> None:
        self.register()

        self.invoke()

        for name in (TOOL_REQUESTED, TOOL_AUTHORIZED, TOOL_STARTED, TOOL_COMPLETED):
            with self.subTest(name=name):
                self.assertEqual(len(self.named(name)), 1)

    def test_one_invocation_shares_one_request_identifier(self) -> None:
        self.register()

        self.invoke()

        identifiers = {
            event.payload["request_id"]
            for event in self.events
            if event.name.startswith("tool.")
        }
        self.assertEqual(identifiers, {"request-1"})

    def test_a_service_without_a_bus_still_executes(self) -> None:
        registry = ToolRegistry()
        tool = EchoingTool()
        registry.register(tool)

        result = ToolExecutionService(registry).execute(
            ToolInvocation(
                capability=ToolCapability.CLOCK_READ,
                authorized_effects=READ_LOCAL,
            )
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(len(tool.calls), 1)


class BoundedPayloadTests(LifecycleFixture):
    def rendered(self) -> str:
        return str(
            [event.payload for event in self.events if event.name.startswith("tool.")]
        )

    def test_no_event_carries_an_argument_value(self) -> None:
        """Established while the only tool is a clock and the stakes are nothing."""
        self.register()

        self.invoke()

        self.assertNotIn(SECRET_ARGUMENT, self.rendered())

    def test_no_event_carries_a_result_value(self) -> None:
        self.register()

        self.invoke()

        self.assertNotIn(SECRET_VALUE, self.rendered())

    def test_no_event_carries_raised_exception_text(self) -> None:
        self.register(raises=True)

        self.invoke()

        self.assertNotIn(SECRET_ARGUMENT, self.rendered())
        self.assertNotIn("failed while handling", self.rendered())

    def test_arguments_are_counted_not_carried(self) -> None:
        self.register()

        self.invoke()

        self.assertEqual(
            self.named(TOOL_REQUESTED)[0].payload["argument_count"],
            1,
        )

    def test_result_values_are_counted_not_carried(self) -> None:
        self.register()

        self.invoke()

        self.assertEqual(self.named(TOOL_COMPLETED)[0].payload["value_count"], 1)

    def test_every_payload_is_machine_readable(self) -> None:
        self.register()

        self.invoke()

        for event in self.events:
            if not event.name.startswith("tool."):
                continue
            with self.subTest(name=event.name):
                self.assertTrue(PAYLOAD_FIELDS <= set(event.payload))
                for value in event.payload.values():
                    self.assertIsInstance(value, str | bool | int | tuple)

    def test_declared_effects_appear_once_the_tool_is_known(self) -> None:
        self.register()

        self.invoke()

        self.assertEqual(
            self.named(TOOL_AUTHORIZED)[0].payload["declared_effects"],
            (ToolEffect.READS_LOCAL_STATE.value,),
        )

    def test_a_failure_names_a_bounded_kind(self) -> None:
        self.register(effects=READ_AND_NETWORK)

        self.invoke(READ_LOCAL)

        self.assertEqual(
            self.named(TOOL_FAILED)[0].payload["failure_kind"],
            ToolFailureKind.UNAUTHORIZED_EFFECT.value,
        )

    def test_a_refusal_reports_no_performed_work(self) -> None:
        self.register(effects=READ_AND_NETWORK)

        self.invoke(READ_LOCAL)

        payload = self.named(TOOL_FAILED)[0].payload
        self.assertIs(payload["performed"], False)
        self.assertIs(payload["succeeded"], False)


if __name__ == "__main__":
    unittest.main()
