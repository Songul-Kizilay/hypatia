"""The contract every tool implements.

A tool declares itself through a descriptor and does one thing. It never checks
its own authorisation — that happens at the registry boundary, before the tool
is reached — because a tool that policed itself would be the only thing standing
between a mistake and its consequences, and every new tool would have to get
that right again.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from tools.ToolDescriptor import ToolDescriptor
from tools.ToolInvocation import ToolInvocation
from tools.ToolResult import ToolResult


@runtime_checkable
class Tool(Protocol):
    """Provide one declared capability with one declared set of effects."""

    @property
    def descriptor(self) -> ToolDescriptor:
        """Return this tool's own declaration, read before it is invoked."""
        ...

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        """Do the one thing this tool does, reporting honestly what happened."""
        ...
