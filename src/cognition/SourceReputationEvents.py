"""Bounded observability for source reputation.

Payloads carry counts and bounded standing categories. They deliberately do not
carry origins: a log line naming a host alongside a low standing is exactly the
artefact that gets quoted later without its sample size, and reputation is the
one place in this system where that would do real damage.
"""

from __future__ import annotations

from collections import Counter

from eventbus.EventBus import EventBus
from research.SourceReputation import SourceReputation

REPUTATION_REPORTED = "source_reputation.reported"

EVENT_SOURCE = "research.source_reputation"


class SourceReputationEvents:
    """Publish bounded reputation events, or nothing without a bus."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def reported(self, reputations: tuple[SourceReputation, ...]) -> None:
        standings = Counter(reputation.standing.value for reputation in reputations)
        self._emit(
            REPUTATION_REPORTED,
            {
                "origin_count": len(reputations),
                "established_count": sum(
                    1 for entry in reputations if entry.standing.established
                ),
                "assessed_total": sum(entry.assessed_count for entry in reputations),
                "standings": dict(sorted(standings.items())),
                "sources_gated": 0,
                "executed": False,
            },
        )

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
