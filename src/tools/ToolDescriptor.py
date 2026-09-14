"""What a tool says about itself before anyone runs it.

A descriptor is the tool's own declaration: which capability it provides, what
it does to the world, and one sentence about what it is for. It is read before
invocation and is what an authorisation is checked against, so a tool cannot
acquire an effect by acquiring behaviour.

A tool declaring no effects at all is refused. Something that genuinely touches
nothing does not need to be a tool, and in practice a blank declaration means
nobody filled it in.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from tools.ToolCapability import ToolCapability
from tools.ToolEffect import ToolEffect

MAX_TOOL_SUMMARY_LENGTH = 200


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    """Declare one tool's capability, its effects, and its purpose."""

    capability: ToolCapability
    effects: frozenset[ToolEffect]
    summary: str

    def __post_init__(self) -> None:
        if not isinstance(self.capability, ToolCapability):
            raise ResearchError("A tool capability must be a bounded value.")
        if not self.capability.invocable:
            raise ResearchError("A tool cannot declare the 'none' capability.")
        if not isinstance(self.effects, frozenset):
            raise ResearchError("Tool effects must be an immutable set.")
        if not self.effects:
            raise ResearchError(
                "A tool must declare at least one effect. A blank declaration "
                "means nobody filled it in."
            )
        if not all(isinstance(effect, ToolEffect) for effect in self.effects):
            raise ResearchError("A tool effect must be a bounded value.")
        if not self.summary.strip():
            raise ResearchError("A tool summary cannot be empty.")
        if len(self.summary) > MAX_TOOL_SUMMARY_LENGTH:
            raise ResearchError("A tool summary is too long.")

    @property
    def read_only(self) -> bool:
        """Return whether this tool leaves nothing changed behind."""
        return not any(effect.irreversible for effect in self.effects)

    @property
    def reaches_outside(self) -> bool:
        """Return whether running this tool is visible beyond this machine."""
        return any(effect.observable_outside for effect in self.effects)

    def within(self, authorized: frozenset[ToolEffect]) -> bool:
        """Return whether every declared effect was authorised in advance."""
        return self.effects <= authorized

    def unauthorized(self, authorized: frozenset[ToolEffect]) -> frozenset[ToolEffect]:
        """Return the declared effects the caller did not authorise."""
        return frozenset(self.effects - authorized)
