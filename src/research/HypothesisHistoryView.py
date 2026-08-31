"""What happened to one hypothesis, and what still stands now.

Everything here is derived. The hypothesis holds the three collections that say
what currently stands and a log of what was taken back; this puts the two side
by side so an operator can read a correction without opening a store file.

The distinction it exists to keep is between *now* and *was*. A retracted
relation is history and must never be presentable as active, and a relation that
was retracted and then authored again is active — showing it as retracted
because an older cycle ended would be a different and wronger story than showing
nothing at all.

There is one thing this cannot tell anyone, and it says so rather than
implying otherwise. Relationships are recorded as membership in a collection,
so nothing anywhere states when one was authored. A retraction carries its own
time, so the record can say a relation existed and ended at T; it cannot say
when it began. The alternatives were to leave the gap silent or to fill it with
the hypothesis's update time, a file timestamp, or the retraction's own — each
of which would print a number that looks like an answer and is not one.

No reason is recorded either, because none is stored. A retraction says a
statement no longer stands and nothing about why, and inventing a plausible
explanation is the one thing an audit view must never do.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from research.HypothesisEvidenceRelation import HypothesisEvidenceRelation
from research.HypothesisEvidenceRetraction import HypothesisEvidenceRetraction
from research.HypothesisStatus import HypothesisStatus

#: Enough to read a long correction history without turning a panel into a log
#: file. When more exist the newest are kept and the count says how many there
#: were, because a list that silently ends is a list that lies about its length.
MAX_HISTORY_RETRACTIONS = 20

MAX_STATEMENT_LENGTH = 200

ASSERTION_TIME_NOTICE = (
    "When each relationship was authored is not recorded anywhere, so this "
    "view does not state it. A retraction carries its own time, so a withdrawn "
    "relationship can be shown as having existed and ended; when it began is "
    "unknown rather than estimated."
)

NO_CONCLUSION_NOTICE = (
    "This describes the record, not the world. Nothing here says the "
    "hypothesis is true or false, and a retraction says only that somebody "
    "took a statement back — never why, which is not stored."
)


@dataclass(frozen=True, slots=True)
class HypothesisHistoryView:
    """Present one hypothesis's standing beside what was withdrawn from it."""

    hypothesis_id: str
    run_id: str
    statement: str
    withdrawn: bool
    supporting_evidence_ids: tuple[str, ...] = ()
    opposing_evidence_ids: tuple[str, ...] = ()
    discriminating_test_evidence_ids: tuple[str, ...] = ()
    retractions: tuple[HypothesisEvidenceRetraction, ...] = ()
    total_retraction_count: int = 0
    status: HypothesisStatus | None = None
    evidence_gap_open: bool | None = None
    evidence_notes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("hypothesis_id", "run_id", "statement"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"A hypothesis history needs a {name}.")
        if not isinstance(self.withdrawn, bool):
            raise ResearchError("A hypothesis history needs a withdrawal flag.")
        for name in (
            "supporting_evidence_ids",
            "opposing_evidence_ids",
            "discriminating_test_evidence_ids",
        ):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise ResearchError(f"A hypothesis history {name} is invalid.")
        if not isinstance(self.retractions, tuple) or not all(
            isinstance(entry, HypothesisEvidenceRetraction)
            for entry in self.retractions
        ):
            raise ResearchError("A hypothesis history retraction is invalid.")
        if len(self.retractions) > MAX_HISTORY_RETRACTIONS:
            raise ResearchError("A hypothesis history shows too many retractions.")
        if (
            isinstance(self.total_retraction_count, bool)
            or not isinstance(self.total_retraction_count, int)
            or self.total_retraction_count < len(self.retractions)
        ):
            raise ResearchError("A hypothesis history retraction total is invalid.")
        if self.status is not None and not isinstance(self.status, HypothesisStatus):
            raise ResearchError("A hypothesis history status is invalid.")
        if self.evidence_gap_open is not None and not isinstance(
            self.evidence_gap_open, bool
        ):
            raise ResearchError("A hypothesis history gap flag is invalid.")

    @property
    def retractions_truncated(self) -> bool:
        """Say whether more retractions exist than are shown here."""
        return self.total_retraction_count > len(self.retractions)

    def current_evidence_ids(
        self,
        relation: HypothesisEvidenceRelation,
    ) -> tuple[str, ...]:
        """Return the evidence currently standing in that relation."""
        if relation is HypothesisEvidenceRelation.SUPPORTS:
            return self.supporting_evidence_ids
        if relation is HypothesisEvidenceRelation.OPPOSES:
            return self.opposing_evidence_ids
        return self.discriminating_test_evidence_ids

    def is_current(
        self,
        evidence_id: str,
        relation: HypothesisEvidenceRelation,
    ) -> bool:
        """Say whether that exact statement stands right now."""
        return evidence_id in self.current_evidence_ids(relation)

    def lines(self) -> tuple[str, ...]:
        """Render current standing and withdrawn statements as separate parts."""
        rendered = [
            "Hypothesis history",
            f"ID: {self.hypothesis_id}",
            f"Run: {self.run_id}",
            f"Hypothesis: {self.statement}",
            f"Working state: {'withdrawn' if self.withdrawn else 'open'}",
            "",
            "Currently standing:",
        ]
        for relation in HypothesisEvidenceRelation:
            current = self.current_evidence_ids(relation)
            rendered.append(
                f"- {relation.label}: "
                + (", ".join(self._label(value) for value in current) or "none")
            )
        rendered.extend(
            (
                "",
                (
                    f"Current standing: {self.status.value}"
                    if self.status is not None
                    else "Current standing: not derived for this view"
                ),
                f"Current research gap: {self._gap_text()}",
                "",
                "Withdrawn statements:",
            )
        )
        if not self.retractions:
            rendered.append("- none recorded")
        rendered.extend(
            f"- {self._label(entry.evidence_id)} no longer "
            f"{entry.relation.label}, withdrawn "
            f"{entry.retracted_at.isoformat()}"
            + (
                " (this evidence stands in that relation again)"
                if self.is_current(entry.evidence_id, entry.relation)
                else ""
            )
            for entry in self.retractions
        )
        if self.retractions_truncated:
            rendered.append(
                f"- showing {len(self.retractions)} of "
                f"{self.total_retraction_count} recorded withdrawals"
            )
        rendered.extend(("", ASSERTION_TIME_NOTICE, "", NO_CONCLUSION_NOTICE))
        return tuple(rendered)

    def _gap_text(self) -> str:
        if self.evidence_gap_open is None:
            return "not derived for this view"
        return (
            "the discriminating test has no evidence recorded against it"
            if self.evidence_gap_open
            else "none open"
        )

    def _label(self, evidence_id: str) -> str:
        """Name evidence by its own note where one exists, else by identifier."""
        note = self.evidence_notes.get(evidence_id, "")
        return f"{evidence_id} ({note})" if note else evidence_id
