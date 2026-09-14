"""Bounded structural telemetry for same-question provider quality reports."""

from __future__ import annotations

from eventbus.EventBus import EventBus
from research.ResearchPairedProviderQualityReport import (
    ResearchPairedProviderQualityReport,
)

PAIRED_PROVIDER_QUALITY_REPORTED = "paired_provider_quality.reported"
EVENT_SOURCE = "research.paired_provider_quality"


class PairedProviderQualityEvents:
    """Emit counts only: never questions, providers, documents, or judgements."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def reported(self, report: ResearchPairedProviderQualityReport) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(
            PAIRED_PROVIDER_QUALITY_REPORTED,
            {
                **report.counts(),
                "providers_selected": 0,
                "rankings_changed": 0,
                "executed": False,
            },
            source=EVENT_SOURCE,
        )
