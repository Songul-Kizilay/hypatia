"""Resolve exactly one registered tool for a declared capability.

The pattern is deliberately the one plan execution already uses: a table keyed
by a typed capability, with no heuristic, no import-time discovery, and no
fallback. A capability with no registered tool is simply unavailable, and the
caller is told so rather than being handed something similar.

The absence of a fallback matters more than it looks. Every other guarantee in
this layer — the effect gate, the bounded failure kinds, the honest results —
assumes the tool that runs is the tool that was asked for. A registry that
quietly substituted a near match would make all of them describe the wrong
thing while remaining technically true.

Registration is explicit and reads the capability from the tool's own
descriptor. Passing the capability separately would allow a tool to be filed
under a name it does not claim, which is a bug nobody would see until something
ran that should not have.

The registry resolves. It never invokes: running a tool is the execution
service's job, and keeping the two apart is what lets authorization sit between
them.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from tools.Tool import Tool
from tools.ToolCapability import ToolCapability


class ToolRegistry:
    """Bind each invocable capability to exactly one concrete tool."""

    def __init__(self, tools: tuple[Tool, ...] = ()) -> None:
        self._tools: dict[ToolCapability, Tool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        """Bind one tool to the capability its own descriptor declares."""
        if not isinstance(tool, Tool):
            raise ResearchError("A tool registry accepts only tools.")
        capability = tool.descriptor.capability
        if not isinstance(capability, ToolCapability):
            raise ResearchError("A tool capability must be a bounded value.")
        if not capability.invocable:
            raise ResearchError("The 'none' capability cannot be registered.")
        if capability in self._tools:
            raise ResearchError("That tool capability is already registered.")
        self._tools[capability] = tool

    def resolve(self, capability: ToolCapability) -> Tool | None:
        """Return the tool registered for this capability, or None.

        None means unavailable, never "close enough". The caller decides what
        to do about an unavailable capability; this does not decide for it.
        """
        if not isinstance(capability, ToolCapability):
            raise ResearchError("A tool capability must be a bounded value.")
        if not capability.invocable:
            raise ResearchError("The 'none' capability cannot be resolved.")
        return self._tools.get(capability)

    def registered(self, capability: ToolCapability) -> bool:
        """Return whether a tool is bound to this capability."""
        return isinstance(capability, ToolCapability) and capability in self._tools

    @property
    def registered_capabilities(self) -> tuple[ToolCapability, ...]:
        """Return registered capabilities in declared enum order.

        Declared order rather than insertion order, so the listing is the same
        whatever sequence the runtime happened to register things in.
        """
        return tuple(
            capability for capability in ToolCapability if capability in self._tools
        )
