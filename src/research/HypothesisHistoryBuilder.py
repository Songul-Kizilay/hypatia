"""Assemble one hypothesis's history from state that already exists.

Pure reading. Nothing is stored, nothing is fetched, and the view is rebuilt on
each request rather than cached, so it cannot go stale behind a correction the
operator just made.

The two optional halves are optional on purpose. A caller holding the run can
supply the appraisal and whether the discriminating test still has nothing
recorded against it; a caller that cannot reach the run gets a view that says
those were not derived rather than one that guesses at them.
"""

from __future__ import annotations

from collections.abc import Sequence

from core.Exceptions import ResearchError
from research.HypothesisEvidenceRetraction import HypothesisEvidenceRetraction
from research.HypothesisHistoryView import (
    MAX_HISTORY_RETRACTIONS,
    MAX_STATEMENT_LENGTH,
    HypothesisHistoryView,
)
from research.HypothesisStatus import HypothesisStatus
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchHypothesis import ResearchHypothesis

MAX_EVIDENCE_NOTE_LENGTH = 80


class HypothesisHistoryBuilder:
    """Project one hypothesis as current standing beside withdrawn statements."""

    def build(
        self,
        hypothesis: ResearchHypothesis,
        *,
        status: HypothesisStatus | None = None,
        evidence_gap_open: bool | None = None,
        evidence: Sequence[ResearchEvidenceRecord] = (),
        limit: int = MAX_HISTORY_RETRACTIONS,
    ) -> HypothesisHistoryView:
        """Return the derived history, inventing nothing that is not recorded."""
        if not isinstance(hypothesis, ResearchHypothesis):
            raise ResearchError("A hypothesis history requires a hypothesis.")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ResearchError("A hypothesis history limit must be whole.")
        if limit < 1 or limit > MAX_HISTORY_RETRACTIONS:
            raise ResearchError("A hypothesis history limit is out of range.")
        ordered = _ordered(hypothesis.retractions)
        return HypothesisHistoryView(
            hypothesis_id=hypothesis.hypothesis_id,
            run_id=hypothesis.run_id,
            statement=hypothesis.one_line_statement(MAX_STATEMENT_LENGTH),
            withdrawn=hypothesis.withdrawn,
            supporting_evidence_ids=hypothesis.supporting_evidence_ids,
            opposing_evidence_ids=hypothesis.opposing_evidence_ids,
            discriminating_test_evidence_ids=(
                hypothesis.discriminating_test_evidence_ids
            ),
            # The newest kept when there are too many, because a correction made
            # a moment ago is the one somebody is looking for.
            retractions=ordered[-limit:],
            total_retraction_count=len(ordered),
            status=status,
            evidence_gap_open=evidence_gap_open,
            evidence_notes=_notes(hypothesis, evidence),
        )


def _ordered(
    retractions: tuple[HypothesisEvidenceRetraction, ...],
) -> tuple[HypothesisEvidenceRetraction, ...]:
    """Return withdrawals oldest first, deterministically.

    Sorted by the only time these records carry, with the evidence identifier
    and relation breaking ties so two withdrawals recorded in the same instant
    do not swap places between reads.
    """
    return tuple(
        sorted(
            retractions,
            key=lambda entry: (
                entry.retracted_at,
                entry.evidence_id,
                entry.relation.value,
            ),
        )
    )


def _notes(
    hypothesis: ResearchHypothesis,
    evidence: Sequence[ResearchEvidenceRecord],
) -> dict[str, str]:
    """Label only the evidence this hypothesis actually mentions.

    The operator's own note, bounded for display. Excerpts are deliberately not
    included: this view is about what was said regarding a hypothesis, and
    reprinting source content here would put an unread quotation next to a
    withdrawal and invite reading one as the reason for the other.
    """
    mentioned = {
        *hypothesis.supporting_evidence_ids,
        *hypothesis.opposing_evidence_ids,
        *hypothesis.discriminating_test_evidence_ids,
        *(entry.evidence_id for entry in hypothesis.retractions),
    }
    return {
        record.evidence_id: record.note.strip()[:MAX_EVIDENCE_NOTE_LENGTH]
        for record in evidence
        if record.evidence_id in mentioned and record.note.strip()
    }
