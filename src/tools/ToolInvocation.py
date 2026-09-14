"""One request to run one tool, with the effects the caller authorised.

The authorisation travels with the call rather than being ambient. A tool layer
where permission is configured once and then applies to everything is a layer
where nobody can tell, at any particular call site, what was allowed — and the
answer drifts upward over time because widening the global grant is always the
easiest fix.

Arguments are bounded strings keyed by name. There is deliberately no
free-form object: a tool that needed arbitrary structure passed to it would be
a tool whose inputs nobody could review.

"Strings" is checked rather than assumed. A length bound alone lets an empty
list or dict through — both have a length — and the tool downstream then either
crashes or quietly stringifies whatever it was handed. Coercion is the worse
outcome of the two, because it succeeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from tools.ToolCapability import ToolCapability
from tools.ToolEffect import ToolEffect

MAX_ARGUMENTS = 10
MAX_ARGUMENT_LENGTH = 4000


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """Ask for one capability, authorising exactly these effects."""

    capability: ToolCapability
    authorized_effects: frozenset[ToolEffect]
    arguments: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.capability, ToolCapability):
            raise ResearchError("A tool invocation capability must be bounded.")
        if not self.capability.invocable:
            raise ResearchError("The 'none' capability cannot be invoked.")
        if not isinstance(self.authorized_effects, frozenset):
            raise ResearchError("Authorized tool effects must be an immutable set.")
        if not all(
            isinstance(effect, ToolEffect) for effect in self.authorized_effects
        ):
            raise ResearchError("An authorized tool effect must be bounded.")
        self._validate_arguments()

    def _validate_arguments(self) -> None:
        if len(self.arguments) > MAX_ARGUMENTS:
            raise ResearchError("A tool invocation passed too many arguments.")
        for name, value in self.arguments:
            if not isinstance(name, str) or not isinstance(value, str):
                raise ResearchError("A tool argument name and value must be text.")
            if not name.strip():
                raise ResearchError("A tool argument name cannot be empty.")
            if len(value) > MAX_ARGUMENT_LENGTH:
                raise ResearchError("A tool argument is too long.")
        names = [name for name, _ in self.arguments]
        if len(names) != len(set(names)):
            raise ResearchError("A tool invocation repeated an argument name.")

    def argument(self, name: str) -> str:
        """Return one argument, or empty when it was not supplied."""
        for candidate, value in self.arguments:
            if candidate == name:
                return value
        return ""

    def require(self, name: str) -> str:
        """Return one argument, refusing the call when it is missing."""
        value = self.argument(name)
        if not value.strip():
            raise ResearchError(f"Tool argument '{name}' is required.")
        return value
