"""One capability as the console presents it, before anything runs.

Everything here is plain text and booleans, projected from a tool's own
descriptor. That keeps the window free of tool-layer types, so the Tk code
cannot construct an invocation, name an effect, or reach a registry even by
accident — the only module that can do those things is the controller.

The description is the tool's declared summary, unchanged. It is not generated,
not rephrased, and not expanded: a capability that cannot describe itself in one
sentence should have that fixed in its descriptor rather than papered over in a
panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from desktop.ToolArgumentSpec import ToolArgumentSpec


@dataclass(frozen=True, slots=True)
class ToolConsoleEntry:
    """Present one registered capability and the effects it will require."""

    capability: str
    description: str
    effects: tuple[str, ...]
    read_only: bool
    reaches_outside: bool
    arguments: tuple[ToolArgumentSpec, ...] = field(default_factory=tuple)
    scope_label: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ResearchError("A tool console entry needs a capability.")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ResearchError("A tool console entry needs a description.")
        if not isinstance(self.effects, tuple) or not self.effects:
            raise ResearchError(
                "A tool console entry must name the effects it will require."
            )
        if not all(isinstance(effect, str) and effect for effect in self.effects):
            raise ResearchError("A tool console effect must be text.")

    @property
    def authorization_prompt(self) -> str:
        """Return the sentence shown next to the button that runs this.

        It names every effect. An operator authorising something should be able
        to read what they are authorising without opening anything else.
        """
        return f"Requires: {', '.join(self.effects)}"

    @property
    def safety_note(self) -> str:
        """Return a fixed sentence describing reach, derived from the descriptor."""
        if self.reaches_outside:
            return "Reaches outside this machine."
        if self.read_only:
            return "Reads only. Changes nothing."
        return "Stays on this machine."

    def argument(self, name: str) -> ToolArgumentSpec | None:
        """Return one declared argument spec, or None when undeclared."""
        for spec in self.arguments:
            if spec.name == name:
                return spec
        return None
