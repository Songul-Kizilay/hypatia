"""One remembered lesson, and the records that make it checkable.

The provenance tuple is the whole point of this type. A lesson without it is an
opinion that will outlive the reasoning behind it and quietly harden into a
belief nobody can audit. So an empty provenance is refused at construction: if
you cannot name the persisted records a lesson came from, it is not a lesson
Hypatia is willing to keep.

A lesson is still not a claim about the world. It records that something did not
work here, not that it cannot work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.DisplayText import one_line
from research.FailureLessonKind import FailureLessonKind

MAX_LESSON_STATEMENT_LENGTH = 300
MAX_LESSON_CONTEXT_LENGTH = 200
MAX_LESSON_PROVENANCE = 12


@dataclass(frozen=True, slots=True)
class ResearchFailureLesson:
    """Record one bounded lesson together with its canonical provenance."""

    lesson_id: str
    kind: FailureLessonKind
    run_id: str
    subject_id: str
    statement: str
    provenance: tuple[str, ...]
    context: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        # Collapsed rather than refused. Lessons are rendered one per line, so
        # a statement containing a line break would forge an entry in the
        # report it appears in — a typed failure reason arriving as a lesson
        # nobody derived. Refusing here would instead turn an awkward reason
        # into an exception, and would make an already-stored lesson written
        # before this rule unreadable.
        object.__setattr__(self, "statement", one_line(self.statement))
        object.__setattr__(self, "context", one_line(self.context))
        for value, label in (
            (self.lesson_id, "lesson ID"),
            (self.run_id, "run ID"),
            (self.statement, "statement"),
        ):
            if not value.strip():
                raise ResearchError(f"Failure lesson {label} cannot be empty.")
        if not isinstance(self.kind, FailureLessonKind):
            raise ResearchError("Failure lesson kind must be a bounded category.")
        if len(self.statement) > MAX_LESSON_STATEMENT_LENGTH:
            raise ResearchError("Failure lesson statement is too long.")
        if len(self.context) > MAX_LESSON_CONTEXT_LENGTH:
            raise ResearchError("Failure lesson context is too long.")
        self._validate_provenance()
        if self.recorded_at.tzinfo is None:
            raise ResearchError("Failure lesson time must be timezone aware.")
        if self.recorded_at > datetime.now(UTC):
            raise ResearchError("Failure lesson cannot be recorded in the future.")

    def _validate_provenance(self) -> None:
        if not self.provenance:
            raise ResearchError(
                "A failure lesson without provenance is an opinion, not a lesson."
            )
        if len(self.provenance) > MAX_LESSON_PROVENANCE:
            raise ResearchError("Failure lesson provenance is too long.")
        if any(not value.strip() for value in self.provenance):
            raise ResearchError("Failure lesson provenance cannot be empty.")
        if len(set(self.provenance)) != len(self.provenance):
            raise ResearchError("Failure lesson provenance repeats a record.")

    @property
    def weight(self) -> int:
        """Return the recall weight of this lesson's kind."""
        return self.kind.weight

    @property
    def concerns_belief(self) -> bool:
        """Return whether this lesson is about what we believed."""
        return self.kind.concerns_belief

    def tokens(self) -> frozenset[str]:
        """Return the lowercase words recall matches against."""
        words = f"{self.context} {self.statement}".casefold().split()
        return frozenset(word.strip(".,;:()[]\"'") for word in words if len(word) > 3)


def lesson_identity(run_id: str, kind: FailureLessonKind, subject_id: str) -> str:
    """Return a stable identity so re-deriving a lesson yields the same ID."""
    return f"lesson:{run_id}:{kind.value}:{subject_id}"
