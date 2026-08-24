"""Assemble the tools this installation actually has, once, at startup.

Composition lives here rather than in the desktop so that the set of registered
capabilities is decided in one reviewable place. A surface that could add a tool
would be a surface that could add authority, and there are going to be more
surfaces than there are people who read them.

Registration is explicit and by construction. There is no scan of the package,
no entry-point discovery, no name-to-class table, and nothing that turns a
string into a tool. Adding a capability means editing this file, which is the
cost that keeps the list short.

The filesystem tool is conditional on a configured root and nothing else. When
no root resolves, the capability is absent rather than present-and-refusing,
because an absent capability cannot be switched on by a configuration mistake.
"""

from __future__ import annotations

from collections.abc import Callable

from eventbus.EventBus import EventBus
from tools.ClockReadTool import ClockReadTool
from tools.FilesystemListTool import FilesystemListTool
from tools.FilesystemRoot import FilesystemRoot
from tools.TextStatisticsTool import TextStatisticsTool
from tools.Tool import Tool
from tools.ToolCapability import ToolCapability
from tools.ToolExecutionService import ToolExecutionService
from tools.ToolRegistry import ToolRegistry


class ToolRuntime:
    """Hold the registered tools and the one service that may run them."""

    def __init__(
        self,
        filesystem_root: FilesystemRoot | None = None,
        *,
        event_bus: EventBus | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._filesystem_root = filesystem_root
        self._registry = ToolRegistry()
        for tool in self._build(filesystem_root):
            self._registry.register(tool)
        self._service = ToolExecutionService(
            self._registry,
            event_bus=event_bus,
            id_factory=id_factory,
        )

    @property
    def registry(self) -> ToolRegistry:
        """Return the registry, which resolves but never executes."""
        return self._registry

    @property
    def service(self) -> ToolExecutionService:
        """Return the single seam every invocation passes through."""
        return self._service

    @property
    def filesystem_root_id(self) -> str:
        """Return the opaque root identity, or empty when none is configured.

        The identity rather than the path. A caller that needs to tell the
        operator which scope is in force does not need to be told where it is,
        and the path has a way of ending up in places that outlive the question.
        """
        if self._filesystem_root is None:
            return ""
        return self._filesystem_root.root_id

    @property
    def capabilities(self) -> tuple[ToolCapability, ...]:
        """Return what this installation can actually do, in declared order."""
        return self._registry.registered_capabilities

    @staticmethod
    def _build(filesystem_root: FilesystemRoot | None) -> tuple[Tool, ...]:
        """List every tool this installation registers, by construction."""
        tools: list[Tool] = [ClockReadTool(), TextStatisticsTool()]
        if filesystem_root is not None:
            tools.append(FilesystemListTool(filesystem_root))
        return tuple(tools)
