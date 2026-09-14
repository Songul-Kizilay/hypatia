"""Bounded observability for human plan approvals.

Payloads carry identifiers, counts, and bounded enum values: which approval,
which plan digest, which run, how many capabilities, what disclosure decision,
and how long the approval is valid. They never carry a research question, a
plan instruction, a source URL, a filesystem path, a model prompt, or an
exception message.

The plan digest is included deliberately. It is a hash of approved content
rather than the content itself, so it identifies exactly what was approved
without disclosing what the approval was about.
"""

from __future__ import annotations

from eventbus.EventBus import EventBus
from research.ResearchPlanAuthorization import ResearchPlanAuthorization

AUTHORIZATION_PREVIEWED = "research_plan_authorization.previewed"
AUTHORIZATION_CONFIRMED = "research_plan_authorization.confirmed"
AUTHORIZATION_REFUSED = "research_plan_authorization.refused"
AUTHORIZATION_CONSUMPTION_ATTEMPTED = (
    "research_plan_authorization.consumption_attempted"
)
AUTHORIZATION_CONSUMED = "research_plan_authorization.consumed"
AUTHORIZATION_CONSUMPTION_REFUSED = "research_plan_authorization.consumption_refused"

EVENT_SOURCE = "research.plan_authorization"


class ResearchPlanAuthorizationEvents:
    """Publish bounded approval events, or nothing without a bus."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    def previewed(self, authorization: ResearchPlanAuthorization) -> None:
        payload = self._payload(authorization)
        payload["stored"] = False
        self._emit(AUTHORIZATION_PREVIEWED, payload)

    def confirmed(
        self,
        authorization: ResearchPlanAuthorization,
        stored_count: int,
        persisted: bool,
    ) -> None:
        payload = self._payload(authorization)
        payload["stored"] = persisted
        payload["stored_count"] = stored_count
        # Stated on every confirmation rather than inferred from the absence of
        # an execution event, because absence is not something a reader notices.
        payload["execution_started"] = False
        self._emit(AUTHORIZATION_CONFIRMED, payload)

    def refused(self, verdict: str) -> None:
        self._emit(AUTHORIZATION_REFUSED, {"verdict": verdict, "stored": False})

    def consumption_attempted(self, authorization: ResearchPlanAuthorization) -> None:
        payload = self._payload(authorization)
        payload["execution_id"] = self._execution_id(authorization)
        self._emit(AUTHORIZATION_CONSUMPTION_ATTEMPTED, payload)

    def consumed(self, authorization: ResearchPlanAuthorization) -> None:
        payload = self._payload(authorization)
        payload["execution_id"] = self._execution_id(authorization)
        payload["stored"] = True
        self._emit(AUTHORIZATION_CONSUMED, payload)

    def consumption_refused(self, verdict: str) -> None:
        self._emit(
            AUTHORIZATION_CONSUMPTION_REFUSED,
            {"verdict": verdict, "consumed": False, "execution_started": False},
        )

    @staticmethod
    def _execution_id(authorization: ResearchPlanAuthorization) -> str:
        consumption = authorization.consumption
        return "" if consumption is None else consumption.execution_id

    @staticmethod
    def _payload(authorization: ResearchPlanAuthorization) -> dict[str, object]:
        return {
            "authorization_id": authorization.authorization_id,
            "plan_digest": authorization.plan_digest,
            "run_id": authorization.research_run_id,
            "capability_count": len(authorization.capabilities),
            "capabilities": sorted(
                capability.value for capability in authorization.capabilities
            ),
            "disclosure": authorization.disclosure.value,
            "authorized_by": authorization.authorized_by.value,
            "validity_seconds": authorization.validity.total_seconds(),
            "max_llm_operations": authorization.budget.max_llm_operations,
        }

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.emit(name, payload, source=EVENT_SOURCE)
