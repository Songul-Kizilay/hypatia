"""Exact prior observation binding for one explicitly approved revalidation.

The binding is an audit copy of the canonical observation identity, not a URL
selection mechanism.  The operation re-reads the named source record before it
reaches the fetcher and refuses if any copied field differs.  In particular, a
caller cannot turn an approval for one observation into an approval for an
arbitrary URL by constructing a different binding.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchCapabilityCost import cost_for
from research.ResearchOperationCost import ResearchOperationCost
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap

_MAXIMUM_ID_CHARACTERS = 200
_MAXIMUM_URL_CHARACTERS = 2_048
_MAXIMUM_SOURCES = 20


@dataclass(frozen=True, slots=True)
class SourceRevalidationStepBinding:
    """Bind one re-fetch to one recorded source observation in one run."""

    research_run_id: str
    prior_observation_id: str
    requested_url: str
    max_sources: int
    declared_cost: ResearchOperationCost = ResearchOperationCost(network_operations=1)

    def __post_init__(self) -> None:
        for value, label in (
            (self.research_run_id, "Revalidation research run ID"),
            (self.prior_observation_id, "Revalidation prior observation ID"),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or value != value.strip()
                or len(value) > _MAXIMUM_ID_CHARACTERS
            ):
                raise ResearchError(f"{label} is invalid.")
        if (
            not isinstance(self.requested_url, str)
            or not self.requested_url.strip()
            or self.requested_url != self.requested_url.strip()
            or len(self.requested_url) > _MAXIMUM_URL_CHARACTERS
            or any(character in self.requested_url for character in ("\r", "\n", "\t"))
        ):
            raise ResearchError("Revalidation requested URL is invalid.")
        if (
            type(self.max_sources) is not int
            or not 1 <= self.max_sources <= _MAXIMUM_SOURCES
        ):
            raise ResearchError("Revalidation source limit is invalid.")
        if not isinstance(
            self.declared_cost, ResearchOperationCost
        ) or self.declared_cost != cost_for(Cap.SOURCE_REVALIDATION):
            raise ResearchError("Revalidation declared cost is inconsistent.")

    def lines(self) -> tuple[str, ...]:
        """Render only the approved authority, never a temporal conclusion."""
        return (
            "Source revalidation: one explicitly approved re-fetch only.",
            f"Prior observation: {self.prior_observation_id}",
            f"Bound research run: {self.research_run_id}",
            f"Recorded requested URL: {self.requested_url}",
            f"Normal maximum sources: {self.max_sources}",
            "Declared attempt cost: 1 advance and 1 network operation; "
            "subject to the existing cumulative allowance, not a separate budget.",
            "The URL is re-derived and checked from the exact recorded observation "
            "before fetching. No automatic or scheduled revalidation is approved.",
        )
