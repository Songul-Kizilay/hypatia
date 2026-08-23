"""Bounded observability for claim calibration.

Payloads carry the run identifier, bounded verdict counts, and how many claims
need a second look. They never carry claim text, a research question, a URL, an
evidence excerpt, or an exception message.
"""

from __future__ import annotations

from eventbus.EventBus import EventBus
from research.ResearchCalibrationReport import ResearchCalibrationReport

CALIBRATION_REPORTED = "calibration.reported"

EVENT_SOURCE = "research.calibration"


class CalibrationEvents:
    """Publish bounded calibration events, or nothing without a bus."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def reported(self, report: ResearchCalibrationReport) -> None:
        self._emit(
            CALIBRATION_REPORTED,
            {
                "run_id": report.run_id,
                "claim_count": len(report.calibrations),
                "attention_count": len(report.needing_attention),
                "overstated_count": len(report.overstated),
                "verdicts": report.counts(),
                "claims_modified": 0,
                "executed": False,
            },
        )

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
