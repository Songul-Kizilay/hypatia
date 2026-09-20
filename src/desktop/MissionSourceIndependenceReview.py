"""Tkinter-independent review of a mission's source-independence judgements.

The review only reads one canonical research run and prepares arguments for the
existing operator assessment preview/record path.  It never infers independence,
calls a provider or model, spends budget, or touches mission authority.  The
caveat shown is the same derivation the teaching report uses.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.ResearchEvidenceCompletionEvaluation import (
    source_independence_caveats,
)
from research.ResearchRun import ResearchRun
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceIndependence import ResearchSourceIndependence

_CAVEAT_TEXT = {
    "source_not_independent": (
        "at least one evidence-bearing source is recorded as derivative or a "
        "likely duplicate, so corroboration may not be independent"
    ),
    "source_independence_unverified": (
        "source independence was not established for every evidence-bearing "
        "source; corroboration independence remains unverified"
    ),
}


@dataclass(frozen=True, slots=True)
class MissionSourceIndependenceRow:
    """One accepted, evidence-bearing mission source and its current judgement."""

    document_id: str
    url: str
    evidence_ids: tuple[str, ...]
    current_assessment: ResearchSourceAssessmentRecord | None

    @property
    def independence(self) -> ResearchSourceIndependence:
        """Absent judgement is unknown, never independent."""
        if self.current_assessment is None:
            return ResearchSourceIndependence.UNKNOWN
        return self.current_assessment.independence

    @property
    def label(self) -> str:
        return f"{self.document_id} — {self.url}"


def independence_review_rows(
    run: ResearchRun,
) -> tuple[MissionSourceIndependenceRow, ...]:
    """Return only accepted sources that contributed canonical evidence."""
    if not isinstance(run, ResearchRun):
        raise ValueError("Independence review requires a research run.")
    superseded = {
        record.supersedes_assessment_id
        for record in run.assessments
        if record.supersedes_assessment_id is not None
    }
    rows = []
    for source in run.sources:
        evidence_ids = tuple(
            record.evidence_id
            for record in run.evidence
            if record.source_document_id == source.document_id
        )
        if not evidence_ids:
            continue
        current = next(
            (
                record
                for record in reversed(run.assessments)
                if record.source_document_id == source.document_id
                and record.assessment_id not in superseded
            ),
            None,
        )
        rows.append(
            MissionSourceIndependenceRow(
                source.document_id, source.url, evidence_ids, current
            )
        )
    return tuple(rows)


def independence_review_text(run: ResearchRun) -> str:
    """Render current canonical judgements and the derived caveat."""
    rows = independence_review_rows(run)
    lines = [f"Source independence review for run {run.run_id}:"]
    lines.extend(
        f"- {row.label}: independence={row.independence.value} "
        f"(current assessment "
        f"{row.current_assessment.assessment_id if row.current_assessment else 'none'})"
        for row in rows
    )
    if not rows:
        lines.append("- No evidence-bearing accepted source to review.")
    caveats = source_independence_caveats(run)
    lines.append(
        "Caveat: "
        + ("; ".join(_CAVEAT_TEXT[caveat.value] for caveat in caveats) or "none")
        + "."
    )
    lines.append(
        "An operator judgement is not model truth or a verified claim. "
        "Independent does not mean true; derivative or duplicate does not mean "
        "false. Recording one does not change mission authority, budget or goal "
        "status."
    )
    return "\n".join(lines)


def independence_assessment_arguments(
    run: ResearchRun,
    document_id: str,
    independence: str,
) -> tuple[str, ...]:
    """Build existing assessment-path arguments for one reviewed mission source.

    The source must be one of the reviewed rows.  The newest current assessment
    is superseded exactly, so a stale review is refused by the existing
    already-superseded check.  Other judgement dimensions are carried forward
    rather than silently reset.
    """
    row = next(
        (
            row
            for row in independence_review_rows(run)
            if row.document_id == document_id
        ),
        None,
    )
    if row is None:
        raise ValueError("Choose an evidence-bearing source from this mission.")
    try:
        value = ResearchSourceIndependence(independence.strip())
    except (AttributeError, ValueError) as error:
        raise ValueError("Source independence judgement is invalid.") from error
    current = row.current_assessment
    return (
        run.run_id,
        row.document_id,
        ", ".join(row.evidence_ids),
        (
            f"Operator source-independence judgement: {value.value}. Human "
            "judgement from the mission review; not model output, not a verified "
            "claim, and not a statement that the source is true or false."
        ),
        current.assessment_id if current else "",
        current.information_trust.value if current else "unassessed",
        current.usefulness.value if current else "unknown",
        current.applicability.value if current else "unknown",
        value.value,
        current.publication_status.value if current else "unknown",
    )
