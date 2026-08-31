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
from research.DisplayText import one_bounded_line
from research.HypothesisEvidenceAssertion import HypothesisEvidenceAssertion
from research.HypothesisEvidenceRelation import HypothesisEvidenceRelation
from research.HypothesisEvidenceRetraction import (
    MAX_HYPOTHESIS_RETRACTIONS,
    HypothesisEvidenceRetraction,
)

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
    #: Evidence an operator has stated addresses the discriminating test. Kept
    #: apart from the two sides above because bearing on a hypothesis and
    #: answering the question it was built around are different claims, and the
    #: second is the one that says the hypothesis has actually been examined.
    #: Membership here is authored and never inferred; nothing in this codebase
    #: compares the wording of a test against the wording of evidence.
    discriminating_test_evidence_ids: tuple[str, ...] = ()
    #: Statements an operator has taken back. The three collections above are
    #: the current projection — an identifier sits in one exactly while that
    #: relation is active — and this is the history, so a corrected hypothesis
    #: reads as one where something was authored and withdrawn rather than one
    #: where nothing was ever said.
    retractions: tuple[HypothesisEvidenceRetraction, ...] = ()
    #: When each currently standing relation was authored, where that is known.
    #: Membership stays in the three collections above; this only annotates it,
    #: so a relation carried forward from before times were kept simply has no
    #: record here and reads as authored at an unknown time. Filling those in
    #: would need a number nobody wrote down.
    assertions: tuple[HypothesisEvidenceAssertion, ...] = ()
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
        self._validate_retractions()
        self._validate_assertions()
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
            (self.discriminating_test_evidence_ids, "discriminating test"),
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
        # Deliberately no rule tying test evidence to a side. An observation can
        # address the discriminating test and support the hypothesis, or address
        # it and oppose it, or address it while the operator has not yet said
        # which way it cuts. Requiring a side would be a rule this codebase
        # never had, invented to make the new relationship tidier.

    def _validate_retractions(self) -> None:
        if not isinstance(self.retractions, tuple):
            raise ResearchError("Hypothesis retractions must be an immutable tuple.")
        if len(self.retractions) > MAX_HYPOTHESIS_RETRACTIONS:
            raise ResearchError("This hypothesis records too many retractions.")
        if not all(
            isinstance(entry, HypothesisEvidenceRetraction)
            for entry in self.retractions
        ):
            raise ResearchError("A hypothesis retraction record is invalid.")

    def _validate_assertions(self) -> None:
        """Refuse a time for a statement that does not currently stand.

        The collections remain the single answer to what stands; this keeps the
        annotation from outliving what it annotates, so an assertion time can
        never be read for a relation that was retracted.
        """
        if not isinstance(self.assertions, tuple):
            raise ResearchError("Hypothesis assertions must be an immutable tuple.")
        if not all(
            isinstance(entry, HypothesisEvidenceAssertion) for entry in self.assertions
        ):
            raise ResearchError("A hypothesis assertion record is invalid.")
        seen: set[tuple[str, HypothesisEvidenceRelation]] = set()
        for entry in self.assertions:
            key = (entry.evidence_id, entry.relation)
            if key in seen:
                raise ResearchError("A hypothesis assertion is recorded twice.")
            seen.add(key)
            if entry.evidence_id not in self.active_evidence_ids(entry.relation):
                raise ResearchError(
                    "A hypothesis assertion names a relation that does not stand."
                )

    def authored_at(
        self,
        evidence_id: str,
        relation: HypothesisEvidenceRelation,
    ) -> datetime | None:
        """Return when that standing relation was authored, or None if unknown.

        None means nobody recorded it, never that it happened at some default
        moment. Callers that want to say something about the time must be able
        to say "not recorded" too.
        """
        for entry in self.assertions:
            if entry.describes(evidence_id, relation):
                return entry.authored_at
        return None

    def _asserted(
        self,
        added: tuple[str, ...],
        relation: HypothesisEvidenceRelation,
        moment: datetime,
    ) -> tuple[HypothesisEvidenceAssertion, ...]:
        """Return the annotations after newly authored members are timed."""
        return (
            *self.assertions,
            *(HypothesisEvidenceAssertion(value, relation, moment) for value in added),
        )

    def active_evidence_ids(
        self,
        relation: HypothesisEvidenceRelation,
    ) -> tuple[str, ...]:
        """Return the evidence currently standing in that relation."""
        if relation is HypothesisEvidenceRelation.SUPPORTS:
            return self.supporting_evidence_ids
        if relation is HypothesisEvidenceRelation.OPPOSES:
            return self.opposing_evidence_ids
        return self.discriminating_test_evidence_ids

    def retracted(
        self,
        evidence_id: str,
        relation: HypothesisEvidenceRelation,
        moment: datetime,
    ) -> ResearchHypothesis:
        """Take back one statement, keeping the fact that it was made.

        Only a currently active statement can be taken back, which is also what
        keeps the history honest: a retraction record always corresponds to a
        relation that really stood, and retracting twice in a row is refused
        rather than written down twice.

        Nothing moves. Retracting support does not create opposition, and
        retracting either says nothing about the discriminating test — a
        correction is two authored events, not one hidden flip.
        """
        if not isinstance(relation, HypothesisEvidenceRelation):
            raise ResearchError("A retraction needs a known evidence relation.")
        identifier = evidence_id.strip() if isinstance(evidence_id, str) else ""
        if not identifier:
            raise ResearchError("A retracted evidence ID cannot be empty.")
        active = self.active_evidence_ids(relation)
        if identifier not in active:
            raise ResearchError(
                "That evidence does not currently stand in that relation."
            )
        remaining = tuple(value for value in active if value != identifier)
        # Spelled out rather than assembled from the relation's field name. A
        # dynamic keyword would say the same thing to a reader and nothing at
        # all to a type checker, and this is the one place where putting a
        # value in the wrong collection would silently move evidence between
        # relations.
        supporting = self.supporting_evidence_ids
        opposing = self.opposing_evidence_ids
        addressing = self.discriminating_test_evidence_ids
        if relation is HypothesisEvidenceRelation.SUPPORTS:
            supporting = remaining
        elif relation is HypothesisEvidenceRelation.OPPOSES:
            opposing = remaining
        else:
            addressing = remaining
        return replace(
            self,
            supporting_evidence_ids=supporting,
            opposing_evidence_ids=opposing,
            discriminating_test_evidence_ids=addressing,
            # The annotation goes with the statement it annotated. Keeping it
            # would leave an authoring time attached to something that no longer
            # stands, which is the one way this record could mislead.
            assertions=tuple(
                entry
                for entry in self.assertions
                if not entry.describes(identifier, relation)
            ),
            retractions=(
                *self.retractions,
                HypothesisEvidenceRetraction(identifier, relation, moment),
            ),
            updated_at=moment,
        )

    def was_retracted(
        self,
        evidence_id: str,
        relation: HypothesisEvidenceRelation,
    ) -> bool:
        """Say whether this exact statement was ever taken back."""
        return any(entry.describes(evidence_id, relation) for entry in self.retractions)

    @property
    def evidence_count(self) -> int:
        """Return how much evidence has been entered on either side."""
        return len(self.supporting_evidence_ids) + len(self.opposing_evidence_ids)

    @property
    def has_discriminating_test_evidence(self) -> bool:
        """Say whether anyone has stated that evidence addresses the test.

        Not whether the test passed. A hypothesis can have evidence addressing
        its test and still be wrong, still be unresolved, and still be argued
        about; this says only that the question it was built around has been
        looked at rather than left alone.
        """
        return bool(self.discriminating_test_evidence_ids)

    def one_line_statement(self, limit: int) -> str:
        """Return the statement as a single line, bounded for display."""
        if limit < 1:
            raise ResearchError("A hypothesis display limit must be positive.")
        return one_bounded_line(self.statement, limit)

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

    def addresses_test_by(
        self,
        evidence_ids: tuple[str, ...],
        moment: datetime,
    ) -> ResearchHypothesis:
        """Record that an operator says this evidence addresses the test.

        Bookkeeping after an observation, never an instruction to make one. The
        discriminating test is inert prose describing what somebody would have
        to see; nothing here reads it, parses it, or acts on it.
        """
        if self.withdrawn:
            raise ResearchError("A withdrawn hypothesis takes no further evidence.")
        if not evidence_ids:
            raise ResearchError("At least one evidence ID is required.")
        existing = set(self.discriminating_test_evidence_ids)
        repeated = [value for value in evidence_ids if value in existing]
        if repeated:
            raise ResearchError(
                "This evidence is already recorded as addressing the test."
            )
        return replace(
            self,
            discriminating_test_evidence_ids=(
                *self.discriminating_test_evidence_ids,
                *evidence_ids,
            ),
            assertions=self._asserted(
                evidence_ids,
                HypothesisEvidenceRelation.ADDRESSES_DISCRIMINATING_TEST,
                moment,
            ),
            updated_at=moment,
        )

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
        added: list[str] = []
        for value in evidence_ids:
            if value not in merged:
                merged.append(value)
                added.append(value)
        relation = (
            HypothesisEvidenceRelation.SUPPORTS
            if supporting
            else HypothesisEvidenceRelation.OPPOSES
        )
        # Only what is newly standing is timed. An identifier already in the
        # collection keeps the time it was first given, because re-sending it
        # authored nothing.
        assertions = self._asserted(tuple(added), relation, moment)
        if supporting:
            return replace(
                self,
                updated_at=moment,
                supporting_evidence_ids=tuple(merged),
                assertions=assertions,
            )
        return replace(
            self,
            updated_at=moment,
            opposing_evidence_ids=tuple(merged),
            assertions=assertions,
        )
