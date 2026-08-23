"""The security agent audits Hypatia, and only Hypatia.

It reads this system's own persisted research state and checks that the
boundaries the rest of the architecture depends on still hold there: sources
obtained over HTTPS, no loopback or private address accepted, no embedded
credentials kept, external text still labelled untrusted and still carrying no
instruction authority, evidence and claims pointing at records that exist.

It contacts nothing. There is no scan intent, no probe intent, no target
parameter, and no domain type anywhere in this component with a field for
someone else's system. An agent that reached outward would need authorisation
this software has no way to establish, so it does not have the vocabulary to
try.

It also repairs nothing. A finding says what is wrong; deciding what to do about
a source already accepted, cited, and reasoned from is a judgement with
consequences the auditor cannot see. Every response reports what was examined
alongside what was found, because "no findings" over nothing examined and "no
findings" over four hundred sources are very different sentences.
"""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.SecurityAgentEvents import SecurityAgentEvents
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer
from security.SecurityPostureAuditor import SecurityPostureAuditor

SECURITY_POSTURE_AUDIT_INTENT = "security_posture_audit"


class SecurityAgentApplicationService:
    """Audit this system's own state, contacting and changing nothing."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        auditor: SecurityPostureAuditor | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._auditor = auditor or SecurityPostureAuditor()
        self._events = SecurityAgentEvents(event_bus)

    @staticmethod
    def is_audit_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == SECURITY_POSTURE_AUDIT_INTENT

    def process_audit(self, request: BrainRequest) -> BrainResponse:
        """Audit every run, or one named run, and report scope with findings."""
        report = self._auditor.audit(self._runs(request))
        self._events.posture_audited(report)
        return self._response_composer.security_posture(request, report)

    def _runs(self, request: BrainRequest) -> tuple[ResearchRun, ...]:
        run_id = request.metadata.get("research_run_id")
        if run_id is None:
            return tuple(self._run_manager.list())
        if not isinstance(run_id, str) or not run_id.strip():
            raise ResearchError("A security audit run ID cannot be empty.")
        return (self._run_manager.get(run_id.strip()),)
