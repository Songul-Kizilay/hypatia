"""What our own assessments say about one origin, counted not scored.

There is no number here on purpose. A single reputation score would compress
"we assessed three pages from this host, two low and one high" into something
that looks precise, travels easily, and cannot be argued with. The counts stay
separate so the reader can see the sample they are being asked to generalise
from.

A reputation is about our record of judging, not about the publisher, and it
never gates anything: no fetch is refused, no evidence discounted, and no new
source pre-assessed because of what this says.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchInformationTrust import ResearchInformationTrust
from research.SourceStanding import MIN_ASSESSMENTS_FOR_STANDING, SourceStanding


@dataclass(frozen=True, slots=True)
class SourceReputation:
    """Report the pattern of our assessments for one origin."""

    origin: str
    accepted_count: int = 0
    assessed_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    evidence_count: int = 0
    run_count: int = 0

    def __post_init__(self) -> None:
        if not self.origin.strip():
            raise ResearchError("Source reputation requires an origin.")
        for value, label in (
            (self.accepted_count, "accepted count"),
            (self.assessed_count, "assessed count"),
            (self.high_count, "high count"),
            (self.medium_count, "medium count"),
            (self.low_count, "low count"),
            (self.evidence_count, "evidence count"),
            (self.run_count, "run count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Source reputation {label} must be whole.")
        graded = self.high_count + self.medium_count + self.low_count
        if graded > self.assessed_count:
            raise ResearchError("More assessments were graded than exist.")
        if self.assessed_count > self.accepted_count:
            raise ResearchError("More sources were assessed than accepted.")

    @property
    def standing(self) -> SourceStanding:
        """Return the bounded pattern, which decides nothing on its own."""
        if not self.assessed_count:
            return SourceStanding.UNKNOWN
        if self.assessed_count < MIN_ASSESSMENTS_FOR_STANDING:
            return SourceStanding.PROVISIONAL
        trusted = self.high_count + self.medium_count
        if self.low_count and trusted:
            return SourceStanding.MIXED
        if self.low_count:
            return SourceStanding.CONSISTENTLY_LOW
        if trusted:
            return SourceStanding.CONSISTENTLY_TRUSTED
        return SourceStanding.PROVISIONAL

    @property
    def unassessed_count(self) -> int:
        """Return how many accepted sources carry no judgement at all."""
        return self.accepted_count - self.assessed_count

    def lines(self) -> tuple[str, ...]:
        """Render the counts as bounded, separately labelled lines."""
        return (
            f"Origin: {self.origin}",
            f"Standing: {self.standing.value}",
            f"Accepted: {self.accepted_count}",
            f"Assessed: {self.assessed_count} "
            f"(high {self.high_count}, medium {self.medium_count}, "
            f"low {self.low_count})",
            f"Never assessed: {self.unassessed_count}",
            f"Evidence recorded: {self.evidence_count}",
            f"Seen in runs: {self.run_count}",
        )

    @staticmethod
    def trust_field(trust: ResearchInformationTrust) -> str:
        """Return the counter a trust label increments, or an empty name."""
        return {
            ResearchInformationTrust.HIGH: "high_count",
            ResearchInformationTrust.MEDIUM: "medium_count",
            ResearchInformationTrust.LOW: "low_count",
        }.get(trust, "")
