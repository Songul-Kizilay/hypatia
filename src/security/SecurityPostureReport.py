"""Everything the security agent checked, and everything it found.

The count of checks run is reported alongside the findings, and that is not
decoration. A report saying "no findings" is ambiguous — it could mean the state
is clean or that nothing was examined — and the difference matters most exactly
when someone is relying on the answer. Saying "seven checks over four sources,
no findings" is a claim; saying "no findings" is a mood.

A clean report is still not a guarantee. It says these specific properties held
in the data at this moment, and nothing at all about the properties nobody
thought to check.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from security.SecurityFinding import SecurityFinding
from security.SecurityFindingKind import SecurityFindingKind, SecurityFindingSeverity


@dataclass(frozen=True, slots=True)
class SecurityPostureReport:
    """Report what was examined and what was found, keeping both visible."""

    findings: tuple[SecurityFinding, ...]
    checks_run: int
    runs_examined: int
    sources_examined: int
    evidence_examined: int
    claims_examined: int

    def __post_init__(self) -> None:
        if not all(isinstance(finding, SecurityFinding) for finding in self.findings):
            raise ResearchError("A posture report accepts only security findings.")
        for value, label in (
            (self.checks_run, "check count"),
            (self.runs_examined, "run count"),
            (self.sources_examined, "source count"),
            (self.evidence_examined, "evidence count"),
            (self.claims_examined, "claim count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResearchError(f"Posture report {label} must be whole.")

    @property
    def clean(self) -> bool:
        """Return whether nothing was found. Not the same as being safe."""
        return not self.findings

    @property
    def needing_action(self) -> tuple[SecurityFinding, ...]:
        """Return the findings someone should look at before moving on."""
        return tuple(finding for finding in self.findings if finding.needs_action)

    @property
    def highest_severity(self) -> SecurityFindingSeverity | None:
        """Return the worst severity found, or None when nothing was."""
        if not self.findings:
            return None
        return max(
            (finding.severity for finding in self.findings),
            key=lambda severity: severity.rank,
        )

    def of_kind(self, kind: SecurityFindingKind) -> tuple[SecurityFinding, ...]:
        """Return the findings of one bounded kind."""
        return tuple(finding for finding in self.findings if finding.kind is kind)

    def counts(self) -> dict[str, int]:
        """Return bounded per-kind counts suitable for an event payload."""
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.kind.value] = counts.get(finding.kind.value, 0) + 1
        return dict(sorted(counts.items()))

    def scope_lines(self) -> tuple[str, ...]:
        """Render what was examined, so a clean result stays interpretable."""
        return (
            f"Checks run: {self.checks_run}",
            f"Runs examined: {self.runs_examined}",
            f"Sources examined: {self.sources_examined}",
            f"Evidence records examined: {self.evidence_examined}",
            f"Claims examined: {self.claims_examined}",
        )
