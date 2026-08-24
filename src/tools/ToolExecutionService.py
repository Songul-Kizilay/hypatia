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

from core.Exceptions import ResearchError
from tools.Tool import Tool
from tools.ToolExecutionOutcome import ToolExecutionOutcome
from tools.ToolFailureKind import ToolFailureKind
from tools.ToolInvocation import ToolInvocation
from tools.ToolRegistry import ToolRegistry
from tools.ToolResult import ToolResult


class ToolExecutionService:
    """Resolve, authorise, and run one tool, reporting honestly either way."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

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
        tool = self._registry.resolve(invocation.capability)
        if tool is None:
            return self._refused(
                invocation,
                ToolFailureKind.UNKNOWN_CAPABILITY,
                "No tool is registered for this capability.",
                resolved=False,
            )

        if self._cancelled(cancellation_token):
            return self._refused(
                invocation,
                ToolFailureKind.CANCELLED,
                "The invocation was cancelled before the tool ran.",
                resolved=True,
            )

        descriptor = tool.descriptor
        if not descriptor.within(invocation.authorized_effects):
            return self._refused(
                invocation,
                ToolFailureKind.UNAUTHORIZED_EFFECT,
                "The tool declares effects this invocation did not authorize.",
                resolved=True,
            )

        return self._run(tool, invocation)

    def _run(self, tool: Tool, invocation: ToolInvocation) -> ToolExecutionOutcome:
        """Invoke an authorised tool, turning a raised failure into a bounded one."""
        try:
            result = tool.invoke(invocation)
        except ResearchError:
            return ToolExecutionOutcome(
                capability=invocation.capability,
                result=ToolResult(
                    capability=invocation.capability,
                    performed=True,
                    detail="The tool ran and reported a failure.",
                    succeeded=False,
                ),
                resolved=True,
                authorized=True,
                failure_kind=ToolFailureKind.TOOL_FAILED,
            )
        if not isinstance(result, ToolResult):
            raise ResearchError("A tool must return a tool result.")
        if result.capability is not invocation.capability:
            raise ResearchError("A tool returned another capability's result.")
        return ToolExecutionOutcome(
            capability=invocation.capability,
            result=result,
            resolved=True,
            authorized=True,
            failure_kind=None if result.succeeded else ToolFailureKind.TOOL_FAILED,
        )

    @staticmethod
    def _refused(
        invocation: ToolInvocation,
        failure_kind: ToolFailureKind,
        reason: str,
        *,
        resolved: bool,
    ) -> ToolExecutionOutcome:
        """Report a stop that happened before the implementation was reached."""
        return ToolExecutionOutcome(
            capability=invocation.capability,
            result=ToolResult.refused(invocation.capability, reason),
            resolved=resolved,
            authorized=False,
            failure_kind=failure_kind,
        )

    @staticmethod
    def _cancelled(cancellation_token: object | None) -> bool:
        """Read the same cancellation shape the rest of the runtime uses."""
        if cancellation_token is None:
            return False
        is_cancelled = getattr(cancellation_token, "is_cancelled", None)
        return bool(callable(is_cancelled) and is_cancelled())
