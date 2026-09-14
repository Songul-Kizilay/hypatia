"""What one run did, taken from the outcome rather than from the button press.

A console makes it very easy to report that something worked, because the
operator pressed a button and nothing threw. So nothing here is derived from the
interaction: the status comes from the execution outcome, the values come from
the result, and a refusal keeps its own words rather than being softened into a
sentence about having tried.

The audit lines carry the same counts the lifecycle events carry and nothing
else. They are the operator's answer to "what actually happened", and they must
stay safe to read aloud — no paths, no argument values, no result payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from desktop.FilesystemContentPreview import FilesystemContentPreview
from desktop.ToolRunStatus import ToolRunStatus


@dataclass(frozen=True, slots=True)
class ToolRunView:
    """Report one run: what was asked, what was allowed, what came back."""

    capability: str
    status: ToolRunStatus
    performed: bool
    succeeded: bool
    detail: str
    declared_effects: tuple[str, ...] = field(default_factory=tuple)
    authorized_effects: tuple[str, ...] = field(default_factory=tuple)
    values: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    events: tuple[str, ...] = field(default_factory=tuple)
    request_id: str = ""
    content_preview: FilesystemContentPreview | None = field(
        default=None,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.status, ToolRunStatus):
            raise ResearchError("A tool run view needs a bounded status.")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ResearchError("A tool run view needs a detail.")
        if self.succeeded and not self.performed:
            raise ResearchError("A run that performed nothing cannot have succeeded.")
        if self.succeeded and self.status is not ToolRunStatus.SUCCEEDED:
            raise ResearchError("A successful run must report the success status.")
        if self.values and not self.performed:
            raise ResearchError("A run that performed nothing returned values.")
        if not isinstance(self.request_id, str):
            raise ResearchError("A tool run request identifier must be text.")
        if self.content_preview is not None:
            if not isinstance(self.content_preview, FilesystemContentPreview):
                raise ResearchError("A tool run content preview is invalid.")
            if (
                self.capability != "filesystem_read"
                or not self.succeeded
                or self.values
                or not self.request_id
                or self.content_preview.request_id != self.request_id
            ):
                raise ResearchError("A tool run content preview is inconsistent.")

    @property
    def headline(self) -> str:
        """Return the fixed status sentence an operator reads first."""
        return self.status.label

    @property
    def value_count(self) -> int:
        """Return how many values came back."""
        return len(self.values)

    def lines(self) -> tuple[str, ...]:
        """Render returned values as bounded labelled lines."""
        return tuple(f"{name}: {value}" for name, value in self.values)

    def audit_lines(self) -> tuple[str, ...]:
        """Render the questions an operator needs answered after a run.

        Declared and authorized are shown separately even though this console
        always grants exactly what was declared. Showing them as one line would
        make the two look like the same fact, and the whole point of the gate is
        that they are not.
        """
        return (
            f"Capability requested: {self.capability}",
            f"Effects declared: {', '.join(self.declared_effects) or 'none'}",
            f"Effects authorized: {', '.join(self.authorized_effects) or 'none'}",
            f"Execution began: {'yes' if self.performed else 'no'}",
            f"Performed: {'yes' if self.performed else 'no'}",
            f"Succeeded: {'yes' if self.succeeded else 'no'}",
            f"Work attempted: {'yes' if self.status.attempted_the_work else 'no'}",
            f"Outcome: {self.status.value}",
            f"Values returned: {self.value_count}",
            f"Lifecycle: {' -> '.join(self.events) or 'none'}",
        )
