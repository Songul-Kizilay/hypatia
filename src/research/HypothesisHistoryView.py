"""What happened to one hypothesis, and what still stands now.

Everything here is derived. The hypothesis holds the three collections that say
what currently stands and a log of what was taken back; this puts the two side
by side so an operator can read a correction without opening a store file.

The distinction it exists to keep is between *now* and *was*. A retracted
relation is history and must never be presentable as active, and a relation that
was retracted and then authored again is active — showing it as retracted
because an older cycle ended would be a different and wronger story than showing
nothing at all.

Authoring times are shown where they exist and named as missing where they do
not. Relations authored since times were kept carry one; relations carried
forward from before that do not, and there is no number anywhere that would
truthfully fill the gap — the hypothesis's update time moves with every later
change, a retraction's time is when a statement ended rather than began, and a
load time is when a file was read. So the two kinds sit side by side and are
told apart, rather than one being made to look like the other.

That also means this cannot present one complete ordering. Events with known
times can be read in order among themselves; an event with no time cannot be
placed between them, and guessing a position would be inventing the very thing
the record is missing.

No reason is recorded either, because none is stored. A retraction says a
statement no longer stands and nothing about why, and inventing a plausible
explanation is the one thing an audit view must never do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

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
    "Relationships authored before this was recorded show no authoring time. "
    "That is unknown rather than estimated, so events without a time are not "
    "placed in order among those that have one, and no complete ordering is "
    "claimed for a mixture of the two."
)

UNKNOWN_TIME_LABEL = "authoring time not recorded"

NO_CONCLUSION_NOTICE = (
    "This describes the record, not the world. Nothing here says the "
    "hypothesis is true or false, and a retraction says only that somebody "
    "took a statement back — never why, which is not stored."
)


def _time_key(evidence_id: str, relation: HypothesisEvidenceRelation) -> str:
    """Return the lookup key pairing one evidence identifier with one relation.

    Keyed by both because the same evidence can stand in more than one relation
    at once, each authored at its own moment.
    """
    return f"{relation.value}:{evidence_id}"


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
    assertion_times: dict[str, datetime] = field(default_factory=dict)
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
                + (
                    ", ".join(
                        f"{self._label(value)} [{self._authored_text(value, relation)}]"
                        for value in current
                    )
                    or "none"
                )
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

    def authored_at(
        self,
        evidence_id: str,
        relation: HypothesisEvidenceRelation,
    ) -> datetime | None:
        """Return when that standing relation was authored, or None if unknown."""
        return self.assertion_times.get(_time_key(evidence_id, relation))

    def _authored_text(
        self,
        evidence_id: str,
        relation: HypothesisEvidenceRelation,
    ) -> str:
        moment = self.authored_at(evidence_id, relation)
        return (
            f"authored {moment.isoformat()}"
            if moment is not None
            else UNKNOWN_TIME_LABEL
        )

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
