"""Explicit authorization to close one research run.

A human declares which terminal status the run should reach. Nothing about the
execution state machine reaching its last step may close a run, and this
authorization never relaxes the existing lifecycle rules: the canonical domain
still decides whether the transition is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchRunStatus import ResearchRunStatus


@dataclass(frozen=True, slots=True)
class ResearchCompletionAuthorization:
    """One explicitly declared terminal status for the bound run."""

    target_status: ResearchRunStatus

    def __post_init__(self) -> None:
        status = self.target_status
        if isinstance(status, str) and not isinstance(status, ResearchRunStatus):
            try:
                status = ResearchRunStatus(status)
            except ValueError as error:
                raise ResearchError(
                    "Completion authorization target status is invalid."
                ) from error
        if not isinstance(status, ResearchRunStatus):
            raise ResearchError("Completion authorization target status is invalid.")
        if not status.terminal:
            raise ResearchError(
                "Completion authorization requires a terminal target status."
            )
        object.__setattr__(self, "target_status", status)
