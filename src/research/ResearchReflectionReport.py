"""What one research run taught us about the research, not about the subject.

A reflection report is an account of process: what failed, what contradicted
what, which beliefs were revised, what rests on thin evidence, what stayed
uncertain, what effort went unused, what worked, and what to ask next.

It is not research output. Producing one performs no operation, establishes no
evidence, and promotes nothing. Reading it tells you how a run went; it does not
tell you whether the run's conclusions are true, and it deliberately provides no
way to find out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.ReflectionFindingKind import ReflectionFindingKind
from research.ResearchReflectionFinding import ResearchReflectionFinding

MAX_REFLECTION_FINDINGS = 60


@dataclass(frozen=True, slots=True)
class ResearchReflectionReport:
    """Report bounded process observations for exactly one research run."""

    report_id: str
    run_id: str
    question: str
    findings: tuple[ResearchReflectionFinding, ...]
    summary: CanonicalResearchSummary
    reflected_at: datetime

    def __post_init__(self) -> None:
        for value, label in (
            (self.report_id, "report ID"),
            (self.run_id, "run ID"),
            (self.question, "question"),
        ):
            if not value.strip():
                raise ResearchError(f"Reflection report {label} cannot be empty.")
        if len(self.findings) > MAX_REFLECTION_FINDINGS:
            raise ResearchError("Reflection report has too many findings.")
        if not all(
            isinstance(finding, ResearchReflectionFinding) for finding in self.findings
        ):
            raise ResearchError("Reflection report accepts only findings.")
        if not isinstance(self.summary, CanonicalResearchSummary):
            raise ResearchError("Reflection report requires canonical counts.")
        if self.reflected_at.tzinfo is None:
            raise ResearchError("Reflection time must be timezone aware.")
        if self.reflected_at > datetime.now(UTC):
            raise ResearchError("Reflection cannot happen in the future.")

    @property
    def lessons(self) -> tuple[ResearchReflectionFinding, ...]:
        """Return only the findings that describe something to learn from."""
        return tuple(finding for finding in self.findings if finding.is_lesson)

    def of_kind(
        self,
        kind: ReflectionFindingKind,
    ) -> tuple[ResearchReflectionFinding, ...]:
        """Return the findings of one bounded kind, in report order."""
        return tuple(finding for finding in self.findings if finding.kind is kind)

    def counts(self) -> dict[str, int]:
        """Return bounded per-kind counts suitable for an event payload."""
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.kind.value] = counts.get(finding.kind.value, 0) + 1
        return dict(sorted(counts.items()))


def reflection_identity(run_id: str, reflected_at: datetime) -> str:
    """Return a readable identity that keeps repeated reflections distinct."""
    return f"reflection:{run_id}:{reflected_at.isoformat()}"
