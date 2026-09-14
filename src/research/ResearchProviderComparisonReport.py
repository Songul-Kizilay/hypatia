"""Both sides of one question, presented for a person to judge.

Derived and never stored: everything here recomputes from the run's own discovery
records, and a persisted comparison would be a second copy of them that could
drift — and one step from a persisted conclusion about which provider won.

There is no winner. No field names a better, preferred or recommended provider,
nothing counts one side's candidates against the other's, and the two ranked
lists are never merged into a single order. A rank across providers would be a
verdict about providers dressed as a sort order, and this report exists precisely
so that the verdict stays with the person reading it.

A partial comparison is reported as partial. One side complete and the other
pending is the ordinary state between two advances, and neither an empty result
set nor a failure is invented to fill the gap. New discovery failures carry
their recorded provider and can mark that exact side failed. Legacy failures
without provider provenance remain separately counted and unattributed.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchProviderComparisonSide import ResearchProviderComparisonSide
from research.ResearchQueryCategory import ResearchQueryCategory

NO_WINNER_NOTICE = (
    "No provider was judged better. The two result sets are ranked separately "
    "and never merged into one order, no default was changed, and nothing here "
    "chooses which provider to use next."
)

SEPARATE_RANKING_NOTICE = (
    "Each list is ranked within its own provider. A rank across providers would "
    "be a conclusion about providers rather than about results."
)


@dataclass(frozen=True, slots=True)
class ResearchProviderComparisonReport:
    """Report one question put to two providers, judging neither."""

    run_id: str
    question: str
    category: ResearchQueryCategory
    sides: tuple[ResearchProviderComparisonSide, ...]
    failed_discovery_count: int = 0
    unattributed_failed_discovery_count: int = 0

    def __post_init__(self) -> None:
        for name in ("run_id", "question"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"A provider comparison needs a {name}.")
        if not isinstance(self.category, ResearchQueryCategory):
            raise ResearchError("A provider comparison needs a query category.")
        if not isinstance(self.sides, tuple) or not self.sides:
            raise ResearchError("A provider comparison needs its sides.")
        if not all(
            isinstance(side, ResearchProviderComparisonSide) for side in self.sides
        ):
            raise ResearchError("A provider comparison side is invalid.")
        providers = [side.provider for side in self.sides]
        if len(providers) != len(set(providers)):
            raise ResearchError("A provider comparison reports one side twice.")
        for name in (
            "failed_discovery_count",
            "unattributed_failed_discovery_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError("A failed discovery count must be whole.")
        if self.unattributed_failed_discovery_count > self.failed_discovery_count:
            raise ResearchError("Unattributed failures exceed all discovery failures.")

    @property
    def complete(self) -> bool:
        """Say whether both providers produced a discovery record."""
        return all(side.completed for side in self.sides)

    @property
    def partial(self) -> bool:
        """Say whether some side completed or verifiably failed."""
        return not self.complete and any(
            side.completed or side.failed for side in self.sides
        )

    def counts(self) -> dict[str, int]:
        """Return bounded structural counts suitable for an event payload."""
        return {
            "side_count": len(self.sides),
            "completed_side_count": sum(1 for side in self.sides if side.completed),
            "candidate_count": sum(side.candidate_count for side in self.sides),
            "accepted_count": sum(side.accepted_count for side in self.sides),
            "assessed_count": sum(side.assessed_count for side in self.sides),
            "failed_discovery_count": self.failed_discovery_count,
            "unattributed_failed_discovery_count": (
                self.unattributed_failed_discovery_count
            ),
        }

    def lines(self) -> tuple[str, ...]:
        """Render both sides with their provenance and neither one preferred."""
        state = (
            "complete"
            if self.complete
            else ("partial" if self.partial else "not started")
        )
        rendered = [
            f"Provider comparison — {state}",
            f"Run: {self.run_id}",
            f"Question: {self.question}",
            f"Question category: {self.category.label}",
            "",
        ]
        for side in self.sides:
            rendered.extend(side.lines())
            rendered.append("")
        if self.unattributed_failed_discovery_count:
            rendered.append(
                "Discovery failures whose provider is unavailable in legacy audit "
                f"records: {self.unattributed_failed_discovery_count}. None is "
                "attributed to a side here."
            )
            rendered.append("")
        rendered.extend((SEPARATE_RANKING_NOTICE, "", NO_WINNER_NOTICE))
        return tuple(rendered)
