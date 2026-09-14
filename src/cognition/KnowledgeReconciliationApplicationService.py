"""Report how local knowledge and research membership line up. Read only.

There is no delete intent, no cleanup intent, and no method here that removes
anything. That absence is the design for this milestone: a knowledge-only
document is very often exactly what someone wanted, and automatically tidying
away data whose consequences nobody has worked out is how good material
disappears quietly.

So the service answers a question and returns text. What to do about anything it
reports stays a decision a person makes with the list in front of them.
"""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.KnowledgeReconciliationEvents import KnowledgeReconciliationEvents
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.KnowledgeAttachmentReconciler import KnowledgeAttachmentReconciler
from research.KnowledgeReconciliationReport import KnowledgeReconciliationReport
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

KNOWLEDGE_RECONCILE_INTENT = "knowledge_reconciliation_report"
KNOWLEDGE_ONLY_LIST_INTENT = "knowledge_only_list"


class KnowledgeReconciliationApplicationService:
    """Classify indexed resources against research runs, changing nothing."""

    def __init__(
        self,
        knowledge_engine: KnowledgeEngine,
        response_composer: ResponseComposer,
        *,
        run_manager: ResearchRunManager | None = None,
        reconciler: KnowledgeAttachmentReconciler | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._knowledge_engine = knowledge_engine
        self._response_composer = response_composer
        self._run_manager = run_manager
        self._reconciler = reconciler or KnowledgeAttachmentReconciler()
        self._events = KnowledgeReconciliationEvents(event_bus)

    @staticmethod
    def is_report_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == KNOWLEDGE_RECONCILE_INTENT

    @staticmethod
    def is_knowledge_only_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == KNOWLEDGE_ONLY_LIST_INTENT

    def process_report(self, request: BrainRequest) -> BrainResponse:
        """Report the counts, deleting and repairing nothing."""
        report = self._reconcile()
        self._events.reported(report)
        return self._response_composer.knowledge_reconciliation(request, report)

    def process_knowledge_only(self, request: BrainRequest) -> BrainResponse:
        """List the indexed resources no research run references."""
        report = self._reconcile()
        self._events.reported(report)
        return self._response_composer.knowledge_only_resources(
            request,
            report,
        )

    def _reconcile(self) -> KnowledgeReconciliationReport:
        runs: tuple[ResearchRun, ...] = ()
        if self._run_manager is not None:
            try:
                runs = tuple(self._run_manager.list())
            except ResearchError:
                runs = ()
        return self._reconciler.reconcile(self._knowledge_engine.documents(), runs)
