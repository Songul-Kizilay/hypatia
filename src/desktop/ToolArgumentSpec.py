"""One argument a capability accepts, described well enough to ask for it.

The specs are written down rather than derived, because a tool declares which
argument *names* it accepts and nothing about which are required or what shape
they take. Writing them down risks drift, so a test asserts every spec set
matches its tool's own ACCEPTED_ARGUMENTS exactly. The authoritative list stays
in the tool; this adds only what a form needs on top of it.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from desktop.ToolArgumentKind import ToolArgumentKind


@dataclass(frozen=True, slots=True)
class ToolArgumentSpec:
    """Describe one bounded argument the operator may supply."""

    name: str
    label: str
    kind: ToolArgumentKind
    required: bool = False
    hint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ResearchError("A tool argument spec needs a name.")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ResearchError("A tool argument spec needs a label.")
        if not isinstance(self.kind, ToolArgumentKind):
            raise ResearchError("A tool argument spec needs a bounded kind.")
        if not isinstance(self.required, bool):
            raise ResearchError("A tool argument requirement must be boolean.")

    def missing(self, value: str) -> bool:
        """Return whether a required value was not supplied."""
        return self.required and not value.strip()

    def malformed(self, value: str) -> bool:
        """Return whether the supplied value is obviously the wrong shape."""
        return self.kind.rejects(value)
