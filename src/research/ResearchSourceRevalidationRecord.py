"""Durable, directional provenance between two exact source observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchSourceRecord import ResearchSourceRecord
from research.ResearchSourceRevalidationOutcome import ResearchSourceRevalidationOutcome

_MAXIMUM_ID_LENGTH = 200


@dataclass(frozen=True, slots=True)
class ResearchSourceRevalidationRecord:
    """Record an explicit comparison of two observations, not source freshness.

    Observation IDs are unique only within their own research run.  Both owner
    run IDs are therefore part of the durable identity rather than an inferred
    lookup convenience.
    """

    revalidation_id: str
    earlier_run_id: str
    earlier_observation_id: str
    later_run_id: str
    later_observation_id: str
    outcome: ResearchSourceRevalidationOutcome
    recorded_at: datetime

    def __post_init__(self) -> None:
        for value, label in (
            (self.revalidation_id, "Research source revalidation ID"),
            (self.earlier_run_id, "Earlier research run ID"),
            (self.earlier_observation_id, "Earlier source observation ID"),
            (self.later_run_id, "Later research run ID"),
            (self.later_observation_id, "Later source observation ID"),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or value != value.strip()
                or len(value) > _MAXIMUM_ID_LENGTH
            ):
                raise ResearchError(f"{label} is invalid.")
        if (
            self.earlier_run_id == self.later_run_id
            and self.earlier_observation_id == self.later_observation_id
        ):
            raise ResearchError("A source observation cannot revalidate itself.")
        if not isinstance(self.outcome, ResearchSourceRevalidationOutcome):
            raise ResearchError("Research source revalidation outcome is invalid.")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError(
                "Research source revalidation time must be timezone-aware."
            )


@dataclass(frozen=True, slots=True)
class ResearchSourceRevalidationInspection:
    """Read-only canonical relation with the two records it names."""

    record: ResearchSourceRevalidationRecord
    earlier_source: ResearchSourceRecord
    later_source: ResearchSourceRecord

    def __post_init__(self) -> None:
        if not isinstance(self.record, ResearchSourceRevalidationRecord):
            raise ResearchError("Source revalidation inspection record is invalid.")
        if not isinstance(self.earlier_source, ResearchSourceRecord) or not isinstance(
            self.later_source, ResearchSourceRecord
        ):
            raise ResearchError("Source revalidation inspection sources are invalid.")
