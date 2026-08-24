"""The one seam every tool invocation passes through.

Resolve, authorise, invoke, report — in that order, in one place. Callers do not
reassemble this sequence, because a sequence reproduced at each call site is a
sequence that will eventually be reproduced wrongly, and the step most likely to
be skipped is the one in the middle.

Authorization is central and fail-closed. A tool never checks its own grant: it
declares its effects in its descriptor and this service compares them against
the effects the invocation authorised, before the implementation is reached. A
tool that policed itself would be the only thing between a mistake and its
consequences, and every future tool would have to get that right again.

There is no bypass. No trusted-tool shortcut, no ambient permission, no flag
that skips the gate for something that looks harmless. The clock tool goes
through exactly the path a filesystem or process tool would, which is the only
way to know the path works before anything dangerous uses it.

Nothing here decides *whether* a tool should be used. That judgement belongs to
a caller — eventually a meta-controller — and keeping it out means ordinary
conversation cannot reach a tool just because one exists.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from tools.Tool import Tool
from tools.ToolDescriptor import ToolDescriptor
from tools.ToolEvents import ToolEvents
from tools.ToolExecutionOutcome import ToolExecutionOutcome
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRegistry import ToolRegistry
from tools.ToolResult import ToolResult


class ToolExecutionService:
    """Resolve, authorise, and run one tool, reporting honestly either way."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        event_bus: EventBus | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._registry = registry
        self._events = ToolEvents(event_bus)
        self._id_factory = id_factory or (lambda: f"tool-{uuid4()}")

    def execute(
        self,
        invocation: ToolInvocation,
        *,
        cancellation_token: object | None = None,
    ) -> ToolResult:
        """Run one invocation and return only what the tool produced."""
        return self.execute_detailed(
            invocation,
            cancellation_token=cancellation_token,
        ).result

    def execute_detailed(
        self,
        invocation: ToolInvocation,
        *,
        cancellation_token: object | None = None,
    ) -> ToolExecutionOutcome:
        """Run one invocation and report how far it got and why it stopped."""
        if not isinstance(invocation, ToolInvocation):
            raise ResearchError("A tool execution requires an invocation.")
        events = self._events.for_request(self._id_factory())
        events.requested(invocation)

        tool = self._registry.resolve(invocation.capability)
        if tool is None:
            return self._refused(
                events,
                invocation,
                ToolFailureKind.UNKNOWN_CAPABILITY,
                "No tool is registered for this capability.",
                resolved=False,
            )

        if self._cancelled(cancellation_token):
            events.cancelled(invocation)
            return self._cancellation(invocation)

        descriptor = tool.descriptor
        if not descriptor.within(invocation.authorized_effects):
            return self._refused(
                events,
                invocation,
                ToolFailureKind.UNAUTHORIZED_EFFECT,
                "The tool declares effects this invocation did not authorize.",
                resolved=True,
                descriptor=descriptor,
            )

        events.authorized(invocation, descriptor)
        events.started(invocation, descriptor)
        return self._run(events, tool, invocation)

    def _run(
        self,
        events: ToolEvents,
        tool: Tool,
        invocation: ToolInvocation,
    ) -> ToolExecutionOutcome:
        """Invoke an authorised tool, turning a raised failure into a bounded one."""
        descriptor = tool.descriptor
        try:
            result = tool.invoke(invocation)
        except ResearchError:
            failed = ToolResult(
                capability=invocation.capability,
                performed=True,
                detail="The tool ran and reported a failure.",
                succeeded=False,
            )
            events.failed(
                invocation,
                ToolFailureKind.TOOL_FAILED,
                descriptor=descriptor,
                result=failed,
            )
            return ToolExecutionOutcome(
                capability=invocation.capability,
                result=failed,
                resolved=True,
                authorized=True,
                failure_kind=ToolFailureKind.TOOL_FAILED,
            )
        self._validate_returned(result, invocation)
        if result.succeeded:
            events.completed(invocation, descriptor, result)
        else:
            events.failed(
                invocation,
                ToolFailureKind.TOOL_FAILED,
                descriptor=descriptor,
                result=result,
            )
        return ToolExecutionOutcome(
            capability=invocation.capability,
            result=result,
            resolved=True,
            authorized=True,
            failure_kind=None if result.succeeded else ToolFailureKind.TOOL_FAILED,
        )

    @staticmethod
    def _validate_returned(result: object, invocation: ToolInvocation) -> None:
        """Refuse a tool that answered for a capability it was not asked about."""
        if not isinstance(result, ToolResult):
            raise ResearchError("A tool must return a tool result.")
        if result.capability is not invocation.capability:
            raise ResearchError("A tool returned a result for another capability.")

    @staticmethod
    def _refused(
        events: ToolEvents,
        invocation: ToolInvocation,
        failure_kind: ToolFailureKind,
        reason: str,
        *,
        resolved: bool,
        descriptor: ToolDescriptor | None = None,
    ) -> ToolExecutionOutcome:
        """Report a stop that happened before the implementation was reached."""
        result = ToolResult.refused(invocation.capability, reason)
        events.failed(
            invocation,
            failure_kind,
            descriptor=descriptor,
            result=result,
        )
        return ToolExecutionOutcome(
            capability=invocation.capability,
            result=result,
            resolved=resolved,
            authorized=False,
            failure_kind=failure_kind,
        )

    @staticmethod
    def _cancellation(invocation: ToolInvocation) -> ToolExecutionOutcome:
        """Report a cancellation, which is neither a refusal nor a tool failure."""
        return ToolExecutionOutcome(
            capability=invocation.capability,
            result=ToolResult.refused(
                invocation.capability,
                "The invocation was cancelled before the tool ran.",
            ),
            resolved=True,
            authorized=False,
            failure_kind=ToolFailureKind.CANCELLED,
        )

    @staticmethod
    def _cancelled(cancellation_token: object | None) -> bool:
        """Read the same cancellation shape the rest of the runtime uses."""
        if cancellation_token is None:
            return False
        is_cancelled = getattr(cancellation_token, "is_cancelled", None)
        return bool(callable(is_cancelled) and is_cancelled())
