"""One explicit operator review of one exact retained comparison note.

A comparison note from a mission is a tentative model interpretation.  This
record is the structured, auditable human judgement about that exact note: it
names the note, copies the note's evidence identities, states a typed decision
and keeps the operator's reason.  It is written only through the canonical
run-manager path after revalidation.  It is never created by a model response,
by note prose, by trust or independence labels, or by claim confidence.

A later review of the same note supersedes the current one, so support can be
withdrawn without deleting history.  At most one review of a note is current.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from core.Exceptions import ResearchError
from research.ResearchSensitiveInputPolicy import ResearchSensitiveInputPolicy

MAX_COMPARISON_REVIEW_NOTE_CHARACTERS = 2_000

_SENSITIVE_INPUT_POLICY = ResearchSensitiveInputPolicy()


def _refuse_sensitive_input(value: str, label: str) -> None:
    sensitive_class = _SENSITIVE_INPUT_POLICY.classify(value)
    if sensitive_class.refused:
        raise ResearchError(f"{label} was refused as {sensitive_class.operator_label}.")


class ResearchComparisonReviewDecision(StrEnum):
    """The operator's typed decision about one exact comparison note."""

    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"


@dataclass(frozen=True, slots=True)
class ResearchComparisonReviewRecord:
    """Append-only operator review bound to one comparison note's evidence."""

    review_id: str
    note_id: str
    evidence_ids: tuple[str, ...]
    decision: ResearchComparisonReviewDecision
    note: str
    recorded_at: datetime
    supersedes_review_id: str | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.review_id, "Research comparison review ID"),
            (self.note_id, "Research comparison review note ID"),
            (self.note, "Research comparison review note"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"{label} cannot be empty.")
        if len(self.note.strip()) > MAX_COMPARISON_REVIEW_NOTE_CHARACTERS:
            raise ResearchError("Research comparison review note is too long.")
        _refuse_sensitive_input(self.note.strip(), "Research comparison review note")
        if (
            not isinstance(self.evidence_ids, tuple)
            or not self.evidence_ids
            or not all(
                isinstance(evidence_id, str) and evidence_id.strip()
                for evidence_id in self.evidence_ids
            )
            or len({value.strip() for value in self.evidence_ids})
            != len(self.evidence_ids)
        ):
            raise ResearchError("Research comparison review evidence IDs are invalid.")
        if not isinstance(self.decision, ResearchComparisonReviewDecision):
            raise ResearchError("Research comparison review decision is invalid.")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError(
                "Research comparison review time must be timezone-aware."
            )
        superseded = self.supersedes_review_id
        if superseded is not None:
            if not isinstance(superseded, str) or not superseded.strip():
                raise ResearchError(
                    "Superseded research comparison review ID cannot be empty."
                )
            if superseded.strip() == self.review_id.strip():
                raise ResearchError("A comparison review cannot supersede itself.")
            object.__setattr__(self, "supersedes_review_id", superseded.strip())
        object.__setattr__(self, "review_id", self.review_id.strip())
        object.__setattr__(self, "note_id", self.note_id.strip())
        object.__setattr__(self, "note", self.note.strip())
        object.__setattr__(
            self, "evidence_ids", tuple(value.strip() for value in self.evidence_ids)
        )


def current_comparison_review(
    reviews: Iterable[ResearchComparisonReviewRecord], note_id: str
) -> ResearchComparisonReviewRecord | None:
    """Return the one review of ``note_id`` that nothing supersedes, if any."""
    records = tuple(reviews)
    superseded = {
        record.supersedes_review_id
        for record in records
        if record.supersedes_review_id is not None
    }
    return next(
        (
            record
            for record in records
            if record.note_id == note_id and record.review_id not in superseded
        ),
        None,
    )
