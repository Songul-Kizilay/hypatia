"""A hypothesis, and the observation that would count against it.

`discriminating_test` is required and cannot be empty. A conjecture that names
nothing capable of counting against it is not a hypothesis, it is a belief with
better manners, and it will survive any amount of evidence because nothing was
ever allowed to threaten it. Requiring the defeater up front — before any
evidence arrives, while it is still cheap to be honest — is the one structural
defence against that.

Supporting and opposing evidence are kept in separate lists and never netted
against each other. A count of three-for and two-against is a real situation
someone has to look at; a score of "+1" is that situation destroyed. The same
evidence record cannot appear on both sides.

Status is not stored here. It is derived from the evidence each time, so it can
never drift from the record it summarises.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from core.Exceptions import ResearchError

MAX_HYPOTHESIS_STATEMENT_LENGTH = 400
MAX_DISCRIMINATING_TEST_LENGTH = 400
MAX_HYPOTHESIS_EVIDENCE = 50


@dataclass(frozen=True, slots=True)
class ResearchHypothesis:
    """One authored conjecture, its defeater, and the evidence on each side."""

    hypothesis_id: str
    run_id: str
    statement: str
    discriminating_test: str
    created_at: datetime
    updated_at: datetime
    supporting_evidence_ids: tuple[str, ...] = ()
    opposing_evidence_ids: tuple[str, ...] = ()
    withdrawn: bool = False

    def __post_init__(self) -> None:
        for value, label in (
            (self.hypothesis_id, "ID"),
            (self.run_id, "run ID"),
            (self.statement, "statement"),
        ):
            if not value.strip():
                raise ResearchError(f"Hypothesis {label} cannot be empty.")
        if not self.discriminating_test.strip():
            raise ResearchError(
                "A hypothesis must state what observation would count against "
                "it. Without one it is a belief, not a hypothesis."
            )
        if len(self.statement) > MAX_HYPOTHESIS_STATEMENT_LENGTH:
            raise ResearchError("Hypothesis statement is too long.")
        if len(self.discriminating_test) > MAX_DISCRIMINATING_TEST_LENGTH:
            raise ResearchError("Hypothesis discriminating test is too long.")
        self._validate_evidence()
        for moment, label in (
            (self.created_at, "creation time"),
            (self.updated_at, "update time"),
        ):
            if moment.tzinfo is None:
                raise ResearchError(f"Hypothesis {label} must be timezone aware.")
            if moment > datetime.now(UTC):
                raise ResearchError(f"Hypothesis {label} cannot be in the future.")
        if self.updated_at < self.created_at:
            raise ResearchError("Hypothesis cannot be updated before it existed.")

    def _validate_evidence(self) -> None:
        for values, label in (
            (self.supporting_evidence_ids, "supporting"),
            (self.opposing_evidence_ids, "opposing"),
        ):
            if len(values) > MAX_HYPOTHESIS_EVIDENCE:
                raise ResearchError(f"Too much {label} hypothesis evidence.")
            if any(not value.strip() for value in values):
                raise ResearchError(f"A {label} evidence ID cannot be empty.")
            if len(set(values)) != len(values):
                raise ResearchError(f"Repeated {label} hypothesis evidence.")
        both = set(self.supporting_evidence_ids) & set(self.opposing_evidence_ids)
        if both:
            raise ResearchError(
                "The same evidence cannot both support and oppose a hypothesis."
            )

    @property
    def evidence_count(self) -> int:
        """Return how much evidence has been entered on either side."""
        return len(self.supporting_evidence_ids) + len(self.opposing_evidence_ids)

    def one_line_statement(self, limit: int) -> str:
        """Return the statement as a single line, bounded for display.

        Anywhere a hypothesis appears among others it is one line among many,
        so a statement containing newlines could otherwise forge entries in
        that report. Collapsing here rather than at each call site means every
        such report inherits the guarantee instead of remembering it.
        """
        if limit < 1:
            raise ResearchError("A hypothesis display limit must be positive.")
        collapsed = " ".join(self.statement.split())
        if len(collapsed) <= limit:
            return collapsed
        return collapsed[: max(limit - 3, 1)] + "..."

    def supported_by(
        self,
        evidence_ids: tuple[str, ...],
        moment: datetime,
    ) -> ResearchHypothesis:
        """Enter evidence on the supporting side."""
        return self._extended(evidence_ids, moment, supporting=True)

    def opposed_by(
        self,
        evidence_ids: tuple[str, ...],
        moment: datetime,
    ) -> ResearchHypothesis:
        """Enter evidence on the opposing side."""
        return self._extended(evidence_ids, moment, supporting=False)

    def withdrawn_at(self, moment: datetime) -> ResearchHypothesis:
        """Stop working on this hypothesis without deleting what it recorded."""
        if self.withdrawn:
            raise ResearchError("This hypothesis is already withdrawn.")
        return replace(self, withdrawn=True, updated_at=moment)

    def _extended(
        self,
        evidence_ids: tuple[str, ...],
        moment: datetime,
        *,
        supporting: bool,
    ) -> ResearchHypothesis:
        if self.withdrawn:
            raise ResearchError("A withdrawn hypothesis takes no further evidence.")
        if not evidence_ids:
            raise ResearchError("At least one evidence ID is required.")
        existing = (
            self.supporting_evidence_ids if supporting else self.opposing_evidence_ids
        )
        merged = list(existing)
        for value in evidence_ids:
            if value not in merged:
                merged.append(value)
        if supporting:
            return replace(
                self,
                updated_at=moment,
                supporting_evidence_ids=tuple(merged),
            )
        return replace(
            self,
            updated_at=moment,
            opposing_evidence_ids=tuple(merged),
        )
