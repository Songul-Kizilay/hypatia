"""Bounded observability for the hypothesis lifecycle.

Payloads carry hypothesis and run identifiers, bounded statuses, and evidence
counts on each side kept separate. They never carry the hypothesis statement,
its discriminating test, a research question, claim text, a URL, or an exception
message.
"""

from __future__ import annotations

from eventbus.EventBus import EventBus
from research.HypothesisAppraisal import HypothesisAppraisal

HYPOTHESIS_PROPOSED = "hypothesis.proposed"
HYPOTHESIS_EVIDENCE_ENTERED = "hypothesis.evidence_entered"
HYPOTHESIS_WITHDRAWN = "hypothesis.withdrawn"

EVENT_SOURCE = "research.hypothesis"


class HypothesisEvents:
    """Publish bounded hypothesis events, or nothing without a bus."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def proposed(self, appraisal: HypothesisAppraisal) -> None:
        self._emit(HYPOTHESIS_PROPOSED, self._payload(appraisal))

    def evidence_entered(
        self,
        appraisal: HypothesisAppraisal,
        supporting: bool,
    ) -> None:
        payload = self._payload(appraisal)
        payload["side"] = "supporting" if supporting else "opposing"
        self._emit(HYPOTHESIS_EVIDENCE_ENTERED, payload)

    def withdrawn(self, appraisal: HypothesisAppraisal) -> None:
        self._emit(HYPOTHESIS_WITHDRAWN, self._payload(appraisal))

    @staticmethod
    def _payload(appraisal: HypothesisAppraisal) -> dict[str, object]:
        hypothesis = appraisal.hypothesis
        return {
            "hypothesis_id": hypothesis.hypothesis_id,
            "run_id": hypothesis.run_id,
            "status": appraisal.status.value,
            "supporting_evidence_count": len(hypothesis.supporting_evidence_ids),
            "opposing_evidence_count": len(hypothesis.opposing_evidence_ids),
            "supporting_source_count": appraisal.supporting_source_count,
            "opposing_source_count": appraisal.opposing_source_count,
            "asserts_truth": False,
            "executed": False,
        }

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
