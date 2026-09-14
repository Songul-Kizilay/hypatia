"""Counts of what canonical research state actually contains.

This is the only admissible answer to "what did you research?". It is derived
from persisted runs, never from a model's account of itself, so it cannot report
work that did not happen. A model can describe evidence it invented; it cannot
increment these numbers, because only the research operations do that.

Every count is kept separate on purpose. A discovered candidate is not an
accepted source, an accepted source is not evidence, evidence is not an
assessment, and an assessment is not a verified claim. Collapsing them into one
"research done" number would destroy exactly the distinction the rest of the
system is built to preserve.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from research.ResearchRun import ResearchRun


@dataclass(frozen=True, slots=True)
class CanonicalResearchSummary:
    """Report bounded counts of persisted research state."""

    run_count: int = 0
    discovery_count: int = 0
    source_count: int = 0
    evidence_count: int = 0
    assessment_count: int = 0
    claim_count: int = 0
    contradiction_count: int = 0

    @classmethod
    def from_runs(cls, runs: Iterable[ResearchRun]) -> CanonicalResearchSummary:
        """Count persisted research state without interpreting any of it."""
        totals = [0, 0, 0, 0, 0, 0, 0]
        for run in runs:
            totals[0] += 1
            totals[1] += len(run.discoveries)
            totals[2] += len(run.sources)
            totals[3] += len(run.evidence)
            totals[4] += len(run.assessments)
            totals[5] += len(run.claims)
            totals[6] += len(run.claim_contradictions)
        return cls(*totals)

    @property
    def has_evidence(self) -> bool:
        """Return whether any evidence record exists at all."""
        return self.evidence_count > 0

    @property
    def empty(self) -> bool:
        """Return whether no research operation has ever recorded anything."""
        return not any(
            (
                self.run_count,
                self.discovery_count,
                self.source_count,
                self.evidence_count,
                self.assessment_count,
                self.claim_count,
                self.contradiction_count,
            )
        )

    def lines(self) -> tuple[str, ...]:
        """Render the counts as bounded, separately labelled lines."""
        return (
            f"Research runs: {self.run_count}",
            f"Candidates discovered: {self.discovery_count}",
            f"Sources accepted: {self.source_count}",
            f"Evidence records: {self.evidence_count}",
            f"Source assessments: {self.assessment_count}",
            f"Claims recorded: {self.claim_count}",
            f"Contradictions recorded: {self.contradiction_count}",
        )
