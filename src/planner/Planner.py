"""Deterministic planning for the first Hypatia Planner sprint."""

from __future__ import annotations

from planner.Goal import Goal
from planner.Plan import Plan
from planner.Task import Task


class Planner:
    """Transforms a user goal into an ordered plan without executing tasks."""

    def create_plan(self, goal: Goal | str) -> Plan:
        """Create a deterministic plan for a Goal or goal description."""
        if isinstance(goal, str):
            goal = Goal(description=goal)
        if not isinstance(goal, Goal):
            raise TypeError("Planner expects a Goal or goal description.")

        plan = Plan(goal=goal)
        for order, title in enumerate(self._task_titles_for(goal), start=1):
            plan.add_task(Task(title=title, order=order))
        return plan

    @staticmethod
    def _task_titles_for(goal: Goal) -> tuple[str, ...]:
        description = goal.description.casefold()
        titles: list[str] = []

        if "read" in description or "pdf" in description:
            titles.extend(("Locate file", "Read document", "Extract text"))
        if "summarize" in description:
            titles.append("Summarize")

        if titles:
            titles.append("Return response")
        else:
            titles.append("Clarify goal")

        return tuple(titles)
