"""How a hypothesis currently stands, derived from its own evidence.

The appraisal keeps the two sides apart and reports both counts. Nothing is
netted: three supporting sources and two opposing ones is a situation someone
has to read, and any single number describing it has thrown away the part that
mattered.

An appraisal never says a hypothesis is true. SUPPORTED means evidence has
accumulated on one side and none on the other, which is the position most
abandoned theories occupied right up until the observation that undid them.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.HypothesisStatus import HypothesisStatus
from research.ResearchHypothesis import ResearchHypothesis


@dataclass(frozen=True, slots=True)
class HypothesisAppraisal:
    """Report one hypothesis together with its derived, unnetted standing."""

    hypothesis: ResearchHypothesis
    status: HypothesisStatus
    supporting_source_count: int
    opposing_source_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, ResearchHypothesis):
            raise ResearchError("An appraisal requires a hypothesis.")
        if not isinstance(self.status, HypothesisStatus):
            raise ResearchError("Hypothesis status must be a bounded category.")
        for value, label in (
            (self.supporting_source_count, "supporting source count"),
            (self.opposing_source_count, "opposing source count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Hypothesis {label} must be whole.")

    @property
    def corroborated(self) -> bool:
        """Return whether more than one distinct source supports this."""
        return self.supporting_source_count > 1

    def lines(self) -> tuple[str, ...]:
        """Render the standing as bounded, separately labelled lines."""
        return (
            f"Hypothesis: {self.hypothesis.statement}",
            f"Would be countered by: {self.hypothesis.discriminating_test}",
            f"Status: {self.status.value}",
            f"Supporting: {len(self.hypothesis.supporting_evidence_ids)} evidence "
            f"across {self.supporting_source_count} source(s)",
            f"Opposing: {len(self.hypothesis.opposing_evidence_ids)} evidence "
            f"across {self.opposing_source_count} source(s)",
        )
