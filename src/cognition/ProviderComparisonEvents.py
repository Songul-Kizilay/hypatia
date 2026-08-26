"""Bounded observability for provider comparison.

Structure only. How many sides ran, how many candidates and acceptances they
hold, and nothing about what any of them said: no question text, no source
title, no CVE description, no document identifier. A comparison is precisely the
place where a log line naming one provider beside a count would later be quoted
as a result, without the question it answered or the fact that a person chose
every one of those sources.

`providers_selected` and `plans_created` are zero on purpose and are asserted to
stay zero. Viewing a comparison decides nothing and starts nothing.
"""

from __future__ import annotations

from eventbus.EventBus import EventBus
from research.ResearchProviderComparisonReport import ResearchProviderComparisonReport

PROVIDER_COMPARISON_REPORTED = "provider_comparison.reported"

EVENT_SOURCE = "research.provider_comparison"


class ProviderComparisonEvents:
    """Publish bounded comparison events, or nothing without a bus."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def reported(self, report: ResearchProviderComparisonReport) -> None:
        self._emit(
            PROVIDER_COMPARISON_REPORTED,
            {
                **report.counts(),
                "complete": report.complete,
                "partial": report.partial,
                "providers_selected": 0,
                "plans_created": 0,
                "executed": False,
            },
        )

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
