"""How a hypothesis currently stands, derived from its own evidence.

The appraisal keeps the two sides apart and reports both counts. Nothing is
netted: three supporting sources and two opposing ones is a situation someone
has to read, and any single number describing it has thrown away the part that
mattered.

An appraisal never says a hypothesis is true. SUPPORTED means evidence has
accumulated from more than one independent source, every one has an active
authored trust assessment of at least medium, and none opposes it. This is still
the position most abandoned theories occupied right up until the observation
that undid them.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.HypothesisStatus import HypothesisStatus
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchInformationTrust import ResearchInformationTrust

_SUPPORTING_TRUST = {
    ResearchInformationTrust.MEDIUM,
    ResearchInformationTrust.HIGH,
}


@dataclass(frozen=True, slots=True)
class HypothesisAppraisal:
    """Report one hypothesis together with its derived, unnetted standing."""

    hypothesis: ResearchHypothesis
    status: HypothesisStatus
    supporting_source_count: int
    opposing_source_count: int
    supporting_assessed_source_count: int = 0
    opposing_assessed_source_count: int = 0
    lowest_supporting_trust: ResearchInformationTrust = (
        ResearchInformationTrust.UNASSESSED
    )
    lowest_opposing_trust: ResearchInformationTrust = (
        ResearchInformationTrust.UNASSESSED
    )

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, ResearchHypothesis):
            raise ResearchError("An appraisal requires a hypothesis.")
        if not isinstance(self.status, HypothesisStatus):
            raise ResearchError("Hypothesis status must be a bounded category.")
        for value, label in (
            (self.supporting_source_count, "supporting source count"),
            (self.opposing_source_count, "opposing source count"),
            (
                self.supporting_assessed_source_count,
                "supporting assessed source count",
            ),
            (
                self.opposing_assessed_source_count,
                "opposing assessed source count",
            ),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Hypothesis {label} must be whole.")
        if self.supporting_assessed_source_count > self.supporting_source_count:
            raise ResearchError("More supporting sources were assessed than exist.")
        if self.opposing_assessed_source_count > self.opposing_source_count:
            raise ResearchError("More opposing sources were assessed than exist.")
        for trust in (
            self.lowest_supporting_trust,
            self.lowest_opposing_trust,
        ):
            if not isinstance(trust, ResearchInformationTrust):
                raise ResearchError("Hypothesis source trust must be a bounded label.")
        for assessed, trust, side in (
            (
                self.supporting_assessed_source_count,
                self.lowest_supporting_trust,
                "supporting",
            ),
            (
                self.opposing_assessed_source_count,
                self.lowest_opposing_trust,
                "opposing",
            ),
        ):
            if assessed == 0 and trust is not ResearchInformationTrust.UNASSESSED:
                raise ResearchError(
                    f"Hypothesis {side} trust requires an assessed source."
                )

    @property
    def corroborated(self) -> bool:
        """Return whether more than one distinct source supports this."""
        return self.supporting_source_count > 1

    @property
    def supporting_sources_fully_assessed(self) -> bool:
        """Return whether every supporting resource has an authored assessment."""
        return (
            self.supporting_source_count > 0
            and self.supporting_assessed_source_count == self.supporting_source_count
        )

    @property
    def support_boundary_met(self) -> bool:
        """Return whether positive support reaches the explicit trust boundary."""
        return (
            self.corroborated
            and self.supporting_sources_fully_assessed
            and self.lowest_supporting_trust in _SUPPORTING_TRUST
        )

    def lines(self) -> tuple[str, ...]:
        """Render the standing as bounded, separately labelled lines."""
        return (
            f"Hypothesis: {self.hypothesis.statement}",
            f"Would be countered by: {self.hypothesis.discriminating_test}",
            f"Status: {self.status.value}",
            f"Supporting: {len(self.hypothesis.supporting_evidence_ids)} evidence "
            f"across {self.supporting_source_count} source(s)",
            "Supporting trust: "
            f"{self.supporting_assessed_source_count}/"
            f"{self.supporting_source_count} source(s) assessed; lowest "
            f"{self.lowest_supporting_trust.value}",
            f"Opposing: {len(self.hypothesis.opposing_evidence_ids)} evidence "
            f"across {self.opposing_source_count} source(s)",
            "Opposing trust: "
            f"{self.opposing_assessed_source_count}/"
            f"{self.opposing_source_count} source(s) assessed; lowest "
            f"{self.lowest_opposing_trust.value}",
        )
