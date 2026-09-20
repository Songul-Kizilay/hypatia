"""Tkinter-independent preview of one mission's operator comparison review.

The mission's comparison note comes from its canonical checkpoint, loaded by the
runtime; this module never chooses a note, never infers support and writes
nothing.  It only turns the loaded run, that exact note and the operator's
proposed decision and reason into a preview and the arguments for the existing
canonical review record path, which revalidates everything again.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.ResearchComparisonReviewRecord import (
    ResearchComparisonReviewDecision,
    current_comparison_review,
)
from research.ResearchRun import ResearchRun


@dataclass(frozen=True, slots=True)
class MissionComparisonReviewPreview:
    """What confirming would record; not a review and not support."""

    text: str
    arguments: tuple[str, str, str, str, str]


def mission_comparison_review_preview(
    run: ResearchRun,
    plan_id: str,
    note_id: str,
    decision: str,
    reason: str,
) -> MissionComparisonReviewPreview:
    """Describe one exact proposed review of the mission's comparison note."""
    if not isinstance(run, ResearchRun):
        raise ValueError("Load the mission comparison review first.")
    if not note_id:
        raise ValueError("This mission has no recorded comparison note to review.")
    note = next(
        (value for value in run.comparison_notes if value.note_id == note_id), None
    )
    if note is None:
        raise ValueError("The mission comparison note is unavailable; reload it.")
    try:
        proposed = ResearchComparisonReviewDecision(decision.strip())
    except (AttributeError, ValueError) as error:
        raise ValueError("Choose a valid operator review decision.") from error
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("An operator review reason is required.")
    if run.status.terminal:
        raise ValueError(
            "This research run is closed; a new comparison review would be refused."
        )
    current = current_comparison_review(run.comparison_reviews, note.note_id)
    current_text = (
        "none recorded"
        if current is None
        else (
            f"{current.review_id} ({current.decision.value}, recorded "
            f"{current.recorded_at.isoformat()})"
        )
    )
    action = (
        f"supersede current review {current.review_id}"
        if current is not None
        else "record the first review of this note"
    )
    text = "\n".join(
        (
            "Preview only: nothing is saved until you confirm.",
            f"Mission plan: {plan_id}",
            f"Research run: {run.run_id}",
            f"Mission comparison note: {note.note_id}",
            f"Sources: {', '.join(note.source_document_ids)}",
            f"Evidence IDs: {', '.join(note.evidence_ids)}",
            f"Current review: {current_text}",
            f"Proposed decision: {proposed.value}",
            f"Operator reason: {reason.strip()}",
            f"Action: {action}.",
            "A supported review is a bounded operator judgement that this exact "
            "comparison is supported for this mission; it is not model output or a "
            "factual-truth decision. The service revalidates the run, note and "
            "evidence and refuses a stale review.",
        )
    )
    return MissionComparisonReviewPreview(
        text=text,
        arguments=(
            run.run_id,
            note.note_id,
            proposed.value,
            reason.strip(),
            current.review_id if current is not None else "",
        ),
    )
