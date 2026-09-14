"""Bounded observability for provider quality evaluation.

Structure only. The payload says how many profiles were built and how many
appraised samples they rest on; it never carries a provider's numbers, because a
log line reading `nvd useful 8` is exactly the artefact that gets quoted later
without its denominator, its sample size, or the sentence explaining that the
operator chose every one of those samples themselves.

No question text, no source title, no CVE description, no assessment prose, and
no document identifier either. The report shows a person what they need to see;
telemetry only needs to say that a report happened and how large it was.
"""

from __future__ import annotations

from eventbus.EventBus import EventBus
from research.ResearchProviderQualityReport import ResearchProviderQualityReport

PROVIDER_QUALITY_REPORTED = "provider_quality.reported"

EVENT_SOURCE = "research.provider_quality"


class ProviderQualityEvents:
    """Publish bounded provider-quality events, or nothing without a bus."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def reported(self, report: ResearchProviderQualityReport) -> None:
        self._emit(
            PROVIDER_QUALITY_REPORTED,
            {
                **report.counts(),
                "providers_selected": 0,
                "rankings_changed": 0,
                "executed": False,
            },
        )

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
