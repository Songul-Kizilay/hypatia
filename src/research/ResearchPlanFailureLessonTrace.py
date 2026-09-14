"""Explain lexical links between remembered failures and authored plan steps.

This trace is deliberately weaker than a coverage judgement. A shared phrase
can show why a prior lesson may be worth rereading, but it cannot prove that an
authored step addresses the lesson, fixes the old failure, or is a good plan.
"""

from __future__ import annotations

from dataclasses import dataclass

from research.FailureMemoryTokens import failure_memory_tokens
from research.ResearchFailureLesson import ResearchFailureLesson
from research.ResearchPlan import ResearchPlan

MIN_STEP_SHARED_TOKENS = 2


@dataclass(frozen=True, slots=True)
class ResearchPlanFailureLessonReference:
    """One explainable lexical link from a lesson to one authored step."""

    lesson_id: str
    step_id: str
    shared_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResearchPlanFailureLessonTrace:
    """Bounded read-only trace for the lessons shown beside one plan."""

    plan_id: str
    lesson_ids: tuple[str, ...]
    references: tuple[ResearchPlanFailureLessonReference, ...]

    def references_for(
        self,
        lesson_id: str,
    ) -> tuple[ResearchPlanFailureLessonReference, ...]:
        """Return references in authored step order for one exact lesson."""
        return tuple(
            reference
            for reference in self.references
            if reference.lesson_id == lesson_id
        )

    @property
    def unreferenced_lesson_ids(self) -> tuple[str, ...]:
        """Return shown lessons with no meaningful authored-step word overlap."""
        referenced = {reference.lesson_id for reference in self.references}
        return tuple(
            lesson_id for lesson_id in self.lesson_ids if lesson_id not in referenced
        )


class ResearchPlanFailureLessonTracer:
    """Derive an explainable lexical trace without judging plan adequacy."""

    def trace(
        self,
        plan: ResearchPlan,
        lessons: tuple[ResearchFailureLesson, ...],
    ) -> ResearchPlanFailureLessonTrace:
        """Compare lesson wording with authored step instructions only."""
        references: list[ResearchPlanFailureLessonReference] = []
        for lesson in lessons:
            lesson_terms = lesson.tokens()
            for step in plan.steps:
                shared_terms = tuple(
                    sorted(lesson_terms & failure_memory_tokens(step.instruction))
                )
                if len(shared_terms) < MIN_STEP_SHARED_TOKENS:
                    continue
                references.append(
                    ResearchPlanFailureLessonReference(
                        lesson_id=lesson.lesson_id,
                        step_id=step.step_id,
                        shared_terms=shared_terms,
                    )
                )
        return ResearchPlanFailureLessonTrace(
            plan_id=plan.plan_id,
            lesson_ids=tuple(lesson.lesson_id for lesson in lessons),
            references=tuple(references),
        )
