"""Read-only facts needed to bind deferred permission."""

from typing import Protocol

from research.BackgroundResearchTask import BackgroundResearchTask
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanExecutionState import ResearchPlanExecutionState


class ReadsDeferredExecutionContext(Protocol):
    def background_research_task(
        self, task_id: str
    ) -> BackgroundResearchTask | None: ...

    def live_research_execution(
        self, execution_id: str
    ) -> ResearchPlanExecutionState | None: ...

    def live_research_plan(self, execution_id: str) -> ResearchPlan | None: ...

    def research_execution_allowance(
        self, execution_id: str
    ) -> ResearchExecutionAllowance | None: ...
