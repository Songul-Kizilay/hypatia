"""Bounded reflection: report how a run went, and change nothing about it.

Reflection reads persisted research state and produces an account of the
process — what failed, what contradicted what, which beliefs were revised, what
rests on thin evidence, what stayed uncertain, what effort went unused, what
worked, and what curiosity would ask next. Producing or storing that account
performs no research operation, mutates no run, and promotes nothing.

There is no recursive reflection. The only thing this service will reflect on is
a research run; a stored reflection report is not a run, and no intent here
accepts one. A system that reflects on its reflections generates infinite
commentary and no new knowledge, which is the opposite of the point.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.ReflectionEvents import ReflectionEvents
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.JsonFileReflectionReportStore import MAX_REFLECTION_STORE_REPORTS
from research.ReflectionReportStore import ReflectionReportStore
from research.ResearchReflectionGenerator import ResearchReflectionGenerator
from research.ResearchReflectionReport import ResearchReflectionReport
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

REFLECTION_PREVIEW_INTENT = "research_reflection_preview"
REFLECTION_STORE_INTENT = "research_reflection_store"
REFLECTION_LIST_INTENT = "research_reflection_list"


class ReflectionApplicationService:
    """Produce and optionally persist bounded reflection reports."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        generator: ResearchReflectionGenerator | None = None,
        report_store: ReflectionReportStore | None = None,
        event_bus: EventBus | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._generator = generator or ResearchReflectionGenerator()
        self._report_store = report_store
        self._events = ReflectionEvents(event_bus)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._reports: dict[str, ResearchReflectionReport] = {}
        self._restore()

    @staticmethod
    def is_preview_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == REFLECTION_PREVIEW_INTENT

    @staticmethod
    def is_store_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == REFLECTION_STORE_INTENT

    @staticmethod
    def is_list_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == REFLECTION_LIST_INTENT

    def reports(self) -> tuple[ResearchReflectionReport, ...]:
        """Return every known report, oldest reflection first."""
        return tuple(
            sorted(
                self._reports.values(),
                key=lambda report: (report.reflected_at, report.report_id),
            )
        )

    def process_preview(self, request: BrainRequest) -> BrainResponse:
        """Report how one run went without storing the account."""
        report = self._reflect(request)
        self._events.produced(report)
        return self._response_composer.research_reflection(request, report, False)

    def process_store(self, request: BrainRequest) -> BrainResponse:
        """Persist one reflection, still changing nothing about the run."""
        report = self._reflect(request)
        self._events.produced(report)
        if len(self._reports) >= MAX_REFLECTION_STORE_REPORTS:
            return self._response_composer.research_reflection_rejected(
                request,
                "Reflection history is full.",
            )
        self._reports[report.report_id] = report
        self._persist()
        self._events.stored(report, len(self._reports))
        return self._response_composer.research_reflection(request, report, True)

    def process_list(self, request: BrainRequest) -> BrainResponse:
        """Report stored reflections without producing a new one."""
        return self._response_composer.research_reflection_list(
            request,
            self.reports(),
        )

    def _reflect(self, request: BrainRequest) -> ResearchReflectionReport:
        """Reflect on exactly one research run, never on a reflection."""
        run_id = request.metadata.get("research_run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            raise ResearchError("Reflection requires a research run ID.")
        run = self._run_manager.get(run_id.strip())
        return self._generator.reflect(run, self._clock())

    def _restore(self) -> None:
        if self._report_store is None:
            return
        for report in self._report_store.load():
            self._reports[report.report_id] = report

    def _persist(self) -> None:
        """Write durable reflections, never erasing them silently on failure."""
        if self._report_store is None:
            return
        try:
            self._report_store.save(list(self._reports.values()))
        except ResearchError:
            return
