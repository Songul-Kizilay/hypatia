"""Bounded observability for the tool invocation lifecycle.

The payload rule is set now, deliberately, while the only tool reads a clock and
the stakes are nothing. Lifecycle events are the most-copied and least-read
artefact a system produces: they land in logs, get forwarded, and are quoted long
after anyone remembers what produced them. The moment they carry arbitrary
arguments or results, they carry whatever a future tool was handed — a token, a
file's contents, a command's output — and no later filter reliably takes that
back.

So arguments and returned values are counted, never carried. A subscriber
deciding what to do needs to know that a tool ran, which capability, which
effects were declared and granted, and whether it worked. It does not need the
payload, and the one time it seems to is the time the payload is sensitive.

The events are also required to be true. `authorized` is emitted only after the
gate actually allowed the call, `started` only when the implementation is about
to run, and `completed` only when it returned. A refused invocation therefore
produces neither, which is what keeps the stream from reading as a better story
than the execution.

A failure event says which kind of failure it was in bounded fields rather than
in its detail, because the detail is not carried at all. A subscriber can tell
an unauthorized call from a declined request from a failed attempt without
parsing anything, which is the property a later system needs in order to decide
whether reformulating would help.
"""

from __future__ import annotations

from eventbus.EventBus import EventBus
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolEffect import ToolEffect
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolResult import ToolResult

TOOL_REQUESTED = "tool.requested"
TOOL_AUTHORIZED = "tool.authorized"
TOOL_STARTED = "tool.started"
TOOL_COMPLETED = "tool.completed"
TOOL_FAILED = "tool.failed"
TOOL_CANCELLED = "tool.cancelled"

EVENT_SOURCE = "tools.execution"


def _effect_names(effects: frozenset[ToolEffect]) -> tuple[str, ...]:
    """Render effects in a stable order so payloads compare equal."""
    return tuple(effect.value for effect in ToolEffect if effect in effects)


class ToolEvents:
    """Publish bounded lifecycle events, or nothing when no bus is present."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        request_id: str = "",
    ) -> None:
        self._event_bus = event_bus
        self._request_id = request_id

    def for_request(self, request_id: str) -> ToolEvents:
        """Return a view bound to one invocation, sharing the bus."""
        return ToolEvents(self._event_bus, request_id)

    def requested(self, invocation: ToolInvocation) -> None:
        """Announce that an invocation entered the service, nothing more."""
        self._emit(TOOL_REQUESTED, invocation)

    def authorized(
        self,
        invocation: ToolInvocation,
        descriptor: ToolDescriptor,
    ) -> None:
        """Announce that the gate allowed this call. Never emitted otherwise."""
        self._emit(TOOL_AUTHORIZED, invocation, descriptor=descriptor)

    def started(
        self,
        invocation: ToolInvocation,
        descriptor: ToolDescriptor,
    ) -> None:
        """Announce that the implementation is about to run."""
        self._emit(TOOL_STARTED, invocation, descriptor=descriptor)

    def completed(
        self,
        invocation: ToolInvocation,
        descriptor: ToolDescriptor,
        result: ToolResult,
    ) -> None:
        """Announce that the implementation returned a successful result."""
        self._emit(TOOL_COMPLETED, invocation, descriptor=descriptor, result=result)

    def failed(
        self,
        invocation: ToolInvocation,
        failure_kind: ToolFailureKind,
        *,
        descriptor: ToolDescriptor | None = None,
        result: ToolResult | None = None,
    ) -> None:
        """Announce a stop, naming a bounded kind rather than a message."""
        self._emit(
            TOOL_FAILED,
            invocation,
            descriptor=descriptor,
            result=result,
            failure_kind=failure_kind,
        )

    def cancelled(self, invocation: ToolInvocation) -> None:
        """Announce that the invocation was cancelled before the tool ran."""
        self._emit(
            TOOL_CANCELLED,
            invocation,
            failure_kind=ToolFailureKind.CANCELLED,
        )

    def _emit(
        self,
        name: str,
        invocation: ToolInvocation,
        *,
        descriptor: ToolDescriptor | None = None,
        result: ToolResult | None = None,
        failure_kind: ToolFailureKind | None = None,
    ) -> None:
        if self._event_bus is None:
            return
        payload: dict[str, object] = {
            "request_id": self._request_id,
            "capability": invocation.capability.value,
            "authorized_effects": _effect_names(invocation.authorized_effects),
            "argument_count": len(invocation.arguments),
            "performed": bool(result is not None and result.performed),
            "succeeded": bool(result is not None and result.succeeded),
        }
        if descriptor is not None:
            payload["declared_effects"] = _effect_names(descriptor.effects)
            payload["read_only"] = descriptor.read_only
            payload["reaches_outside"] = descriptor.reaches_outside
        if result is not None:
            payload["value_count"] = len(result.values)
        if failure_kind is not None:
            payload["failure_kind"] = failure_kind.value
            payload["refused_before_execution"] = failure_kind.refused_before_execution
            # Both are derived from the bounded kind, so a subscriber never has
            # to read a sentence to learn whether the tool got as far as trying.
            # They are separate keys because "nothing was attempted" and "the
            # request was the problem" are different claims, and a caller acts
            # on them differently.
            payload["attempted_the_work"] = failure_kind.attempted_the_work
            payload["concerns_the_request"] = failure_kind.concerns_the_request
        if result is not None and result.disposition is not None:
            payload["disposition"] = result.disposition.value
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
