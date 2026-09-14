"""Persistence boundary for immutable program-scope revision history."""

from typing import Protocol

from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision


class ResearchProgramScopeRevisionStore(Protocol):
    def load(self) -> list[ResearchProgramScopeRevision]: ...

    def save(self, revisions: list[ResearchProgramScopeRevision]) -> None: ...
