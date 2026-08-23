"""The shape of the evidence behind one claim, counted rather than judged.

This is a structural description and nothing more: how many distinct sources,
how many evidence records, how those sources were assessed, whether anything
contradicts the claim. It contains no opinion about whether the claim is right.

The distinction matters because the profile is what calibration reasons over. A
profile can say "one source, never assessed", and that is a checkable fact about
our record. It cannot say "therefore the claim is false", because the number of
sources behind a claim has never settled whether the claim is true.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchInformationTrust import ResearchInformationTrust


@dataclass(frozen=True, slots=True)
class EvidenceSupportProfile:
    """Count what stands behind one claim, without interpreting it."""

    source_count: int = 0
    evidence_count: int = 0
    assessed_source_count: int = 0
    lowest_trust: ResearchInformationTrust = ResearchInformationTrust.UNASSESSED
    highest_trust: ResearchInformationTrust = ResearchInformationTrust.UNASSESSED
    contradicted: bool = False
    superseded: bool = False

    def __post_init__(self) -> None:
        for value, label in (
            (self.source_count, "source count"),
            (self.evidence_count, "evidence count"),
            (self.assessed_source_count, "assessed source count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Evidence {label} must be a whole number.")
        if self.assessed_source_count > self.source_count:
            raise ResearchError("More sources were assessed than exist.")
        for trust in (self.lowest_trust, self.highest_trust):
            if not isinstance(trust, ResearchInformationTrust):
                raise ResearchError("Evidence trust must be a bounded label.")

    @property
    def corroborated(self) -> bool:
        """Return whether more than one distinct source stands behind this."""
        return self.source_count > 1

    @property
    def fully_assessed(self) -> bool:
        """Return whether every source behind this claim carries a judgement."""
        return self.source_count > 0 and self.assessed_source_count == self.source_count

    def lines(self) -> tuple[str, ...]:
        """Render the profile as bounded, separately labelled lines."""
        return (
            f"Distinct sources: {self.source_count}",
            f"Evidence records: {self.evidence_count}",
            f"Sources assessed: {self.assessed_source_count}",
            f"Lowest trust: {self.lowest_trust.value}",
            f"Highest trust: {self.highest_trust.value}",
            f"Contradicted: {'yes' if self.contradicted else 'no'}",
            f"Superseded: {'yes' if self.superseded else 'no'}",
        )
