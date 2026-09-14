"""Bounded observability for the security agent.

Payloads carry counts, bounded finding kinds, and the worst severity found. They
never carry a source URL, a claim, an evidence excerpt, a research question, or
an exception message — a security event naming a URL is the one most likely to
be forwarded somewhere it should not go.

The scope counts travel with every payload for the same reason the report shows
them: an event saying zero findings is uninterpretable without knowing whether
anything was examined.
"""

from __future__ import annotations

from eventbus.EventBus import EventBus
from security.SecurityPostureReport import SecurityPostureReport

POSTURE_AUDITED = "security_agent.posture_audited"

EVENT_SOURCE = "security.agent"


class SecurityAgentEvents:
    """Publish bounded audit events, or nothing without a bus."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def posture_audited(self, report: SecurityPostureReport) -> None:
        highest = report.highest_severity
        self._emit(
            POSTURE_AUDITED,
            {
                "finding_count": len(report.findings),
                "action_count": len(report.needing_action),
                "highest_severity": None if highest is None else highest.value,
                "finding_kinds": report.counts(),
                "checks_run": report.checks_run,
                "runs_examined": report.runs_examined,
                "sources_examined": report.sources_examined,
                "external_systems_contacted": 0,
                "records_modified": 0,
                "executed": False,
            },
        )

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
