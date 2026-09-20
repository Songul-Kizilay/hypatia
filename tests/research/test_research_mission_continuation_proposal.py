"""A continuation proposal must cite evidence, never author new authority."""

from __future__ import annotations

import dataclasses
import sys
import unittest
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.BackgroundTaskOutcome import BackgroundTaskOutcome
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionEvaluation,
)
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionLimitation as Limitation,
)
from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionStatus as EvidenceStatus,
)
from research.ResearchMissionCompletionReadiness import (
    evaluate_mission_completion_readiness,
)
from research.ResearchMissionContinuationProposal import (
    ResearchMissionContinuationProposal,
    continuation_eligible,
    continuation_proposal_for,
)
from research.ResearchMissionGoalSatisfaction import ResearchMissionGoalSatisfaction
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus as GoalStatus,
)
from research.ResearchMissionOutcome import ResearchMissionOutcome
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceRecord import ResearchSourceRecord

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
PLAN_DIGEST = sha256(b"plan-content").hexdigest()

#: The eligible statuses, in one canonical place so every test that needs
#: "the other five" derives it the same way.
ELIGIBLE_STATUSES = frozenset({GoalStatus.UNRESOLVED, GoalStatus.PARTIALLY_SATISFIED})

EXPECTED_FIELDS = frozenset(
    {
        "proposal_id",
        "origin_run_id",
        "origin_plan_digest",
        "origin_stop_reason",
        "origin_goal_status",
        "origin_evidence_status",
        "origin_evidence_limitations",
        "seed_question",
        "generated_at",
    }
)


def run(question: str = "What happened at the site?") -> ResearchRun:
    return ResearchRun(
        run_id="run-1",
        question=question,
        status=ResearchRunStatus.COLLECTING,
        sources=(
            ResearchSourceRecord(
                "doc-1",
                "https://example.test/1",
                "Source",
                "text/plain",
                NOW,
                NOW,
            ),
        ),
        failures=(),
        created_at=NOW,
        updated_at=NOW,
    )


def evidence_evaluation(
    status: EvidenceStatus,
    limitations: tuple[Limitation, ...] = (),
) -> ResearchEvidenceCompletionEvaluation:
    return ResearchEvidenceCompletionEvaluation(
        status=status,
        supports_bounded_teaching=status
        in {EvidenceStatus.SUFFICIENTLY_SUPPORTED, EvidenceStatus.CONFLICTING},
        source_count=2,
        evidence_count=2,
        evidence_source_count=2,
        assessed_source_count=2,
        comparison_note_count=1,
        recorded_claim_contradiction_count=0,
        limitations=limitations,
    )


#: One outcome fixture per `ResearchMissionGoalSatisfactionStatus` member,
#: built directly from parts (as `ResearchMissionOutcome` allows) so each
#: status can be exercised without constructing a full, differently-shaped
#: `ResearchRun` for every case.
_OUTCOME_BY_STATUS: dict[
    GoalStatus, tuple[ResearchMissionOutcome, AutonomyStopReason]
] = {}


def _register(
    goal_status: GoalStatus,
    execution: BackgroundTaskOutcome,
    evidence_status: EvidenceStatus,
    limitations: tuple[Limitation, ...],
    stop_reason: AutonomyStopReason,
) -> None:
    evaluation = evidence_evaluation(evidence_status, limitations)
    satisfaction = ResearchMissionGoalSatisfaction(
        status=goal_status,
        evidence_status=evidence_status,
        execution_outcome=execution,
    )
    outcome = ResearchMissionOutcome(
        execution,
        evaluation,
        satisfaction,
        evaluate_mission_completion_readiness(goal_status, evidence_status, execution),
    )
    _OUTCOME_BY_STATUS[goal_status] = (outcome, stop_reason)


_register(
    GoalStatus.SATISFIED,
    BackgroundTaskOutcome.COMPLETED,
    EvidenceStatus.SUFFICIENTLY_SUPPORTED,
    (),
    AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
)
_register(
    GoalStatus.PARTIALLY_SATISFIED,
    BackgroundTaskOutcome.COMPLETED,
    EvidenceStatus.PARTIALLY_SUPPORTED,
    (Limitation.MISSING_CORROBORATION,),
    AutonomyStopReason.RESEARCH_DELIVERABLE_READY,
)
_register(
    GoalStatus.UNRESOLVED,
    BackgroundTaskOutcome.COMPLETED,
    EvidenceStatus.MATERIALLY_UNRESOLVED,
    (Limitation.MISSING_EVIDENCE,),
    AutonomyStopReason.STEP_INTERRUPTED,
)
_register(
    GoalStatus.BLOCKED,
    BackgroundTaskOutcome.BLOCKED,
    EvidenceStatus.INCOMPLETE,
    (Limitation.EXECUTION_INCOMPLETE,),
    AutonomyStopReason.STEP_BLOCKED,
)
_register(
    GoalStatus.BUDGET_LIMITED,
    BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED,
    EvidenceStatus.BUDGET_LIMITED,
    (Limitation.BUDGET_LIMITED,),
    AutonomyStopReason.NETWORK_BUDGET_EXHAUSTED,
)
_register(
    GoalStatus.FAILED,
    BackgroundTaskOutcome.FAILED,
    EvidenceStatus.INCOMPLETE,
    (Limitation.EXECUTION_INCOMPLETE,),
    AutonomyStopReason.STEP_FAILED,
)
_register(
    GoalStatus.CANCELLED,
    BackgroundTaskOutcome.CANCELLED,
    EvidenceStatus.INCOMPLETE,
    (Limitation.EXECUTION_INCOMPLETE,),
    AutonomyStopReason.CANCELLED,
)

assert set(_OUTCOME_BY_STATUS) == set(GoalStatus)


def valid_kwargs(**overrides: object) -> dict[str, object]:
    """A baseline set of valid constructor arguments for direct tests."""
    kwargs: dict[str, object] = {
        "proposal_id": "proposal-1",
        "origin_run_id": "run-1",
        "origin_plan_digest": PLAN_DIGEST,
        "origin_stop_reason": AutonomyStopReason.STEP_INTERRUPTED,
        "origin_goal_status": GoalStatus.UNRESOLVED,
        "origin_evidence_status": EvidenceStatus.MATERIALLY_UNRESOLVED,
        "origin_evidence_limitations": (Limitation.MISSING_EVIDENCE,),
        "seed_question": "What happened at the site?",
        "generated_at": NOW,
    }
    kwargs.update(overrides)
    return kwargs


class ResearchMissionContinuationProposalConstructionTests(unittest.TestCase):
    def test_valid_construction_succeeds(self):
        proposal = ResearchMissionContinuationProposal(**valid_kwargs())

        self.assertEqual(proposal.proposal_id, "proposal-1")
        self.assertEqual(proposal.seed_question, "What happened at the site?")

    def test_empty_or_non_string_proposal_id_is_rejected(self):
        for bad in ("", "   ", None, 123):
            with self.subTest(bad=bad):
                with self.assertRaises(ResearchError):
                    ResearchMissionContinuationProposal(**valid_kwargs(proposal_id=bad))

    def test_empty_or_non_string_origin_run_id_is_rejected(self):
        for bad in ("", "   ", None, 123):
            with self.subTest(bad=bad):
                with self.assertRaises(ResearchError):
                    ResearchMissionContinuationProposal(
                        **valid_kwargs(origin_run_id=bad)
                    )

    def test_malformed_plan_digest_is_rejected(self):
        for bad in ("", "not-a-digest", PLAN_DIGEST.upper(), PLAN_DIGEST[:-1], 123):
            with self.subTest(bad=bad):
                with self.assertRaises(ResearchError):
                    ResearchMissionContinuationProposal(
                        **valid_kwargs(origin_plan_digest=bad)
                    )

    def test_non_enum_stop_reason_is_rejected(self):
        for bad in ("step_interrupted", None, 1):
            with self.subTest(bad=bad):
                with self.assertRaises(ResearchError):
                    ResearchMissionContinuationProposal(
                        **valid_kwargs(origin_stop_reason=bad)
                    )

    def test_non_enum_goal_status_is_rejected(self):
        for bad in ("unresolved", None, 1):
            with self.subTest(bad=bad):
                with self.assertRaises(ResearchError):
                    ResearchMissionContinuationProposal(
                        **valid_kwargs(origin_goal_status=bad)
                    )

    def test_ineligible_goal_status_is_rejected_for_every_other_member(self):
        for status in GoalStatus:
            with self.subTest(status=status):
                if status in ELIGIBLE_STATUSES:
                    ResearchMissionContinuationProposal(
                        **valid_kwargs(origin_goal_status=status)
                    )
                else:
                    with self.assertRaises(ResearchError):
                        ResearchMissionContinuationProposal(
                            **valid_kwargs(origin_goal_status=status)
                        )

    def test_non_enum_evidence_status_is_rejected(self):
        for bad in ("materially_unresolved", None, 1):
            with self.subTest(bad=bad):
                with self.assertRaises(ResearchError):
                    ResearchMissionContinuationProposal(
                        **valid_kwargs(origin_evidence_status=bad)
                    )

    def test_evidence_limitations_must_be_a_tuple_of_the_limitation_enum(self):
        bad_values = (
            [Limitation.MISSING_EVIDENCE],
            (1, 2),
            ("missing_evidence",),
            None,
        )
        for bad in bad_values:
            with self.subTest(bad=bad):
                with self.assertRaises(ResearchError):
                    ResearchMissionContinuationProposal(
                        **valid_kwargs(origin_evidence_limitations=bad)
                    )

    def test_empty_or_padded_seed_question_is_rejected(self):
        for bad in ("", "   ", " leading space", "trailing space ", None, 123):
            with self.subTest(bad=bad):
                with self.assertRaises(ResearchError):
                    ResearchMissionContinuationProposal(
                        **valid_kwargs(seed_question=bad)
                    )

    def test_seed_question_over_max_length_is_rejected(self):
        too_long = "a" * 2_001
        with self.assertRaises(ResearchError):
            ResearchMissionContinuationProposal(**valid_kwargs(seed_question=too_long))

    def test_seed_question_at_max_length_is_accepted(self):
        exactly_max = "a" * 2_000
        proposal = ResearchMissionContinuationProposal(
            **valid_kwargs(seed_question=exactly_max)
        )
        self.assertEqual(len(proposal.seed_question), 2_000)

    def test_naive_generated_at_is_rejected(self):
        naive = datetime(2026, 9, 14, 12, 0)
        with self.assertRaises(ResearchError):
            ResearchMissionContinuationProposal(**valid_kwargs(generated_at=naive))

    def test_future_generated_at_is_rejected(self):
        future = datetime.now(UTC) + timedelta(days=1)
        with self.assertRaises(ResearchError):
            ResearchMissionContinuationProposal(**valid_kwargs(generated_at=future))

    def test_non_datetime_generated_at_is_rejected(self):
        with self.assertRaises(ResearchError):
            ResearchMissionContinuationProposal(
                **valid_kwargs(generated_at="2026-09-14T12:00:00+00:00")
            )


class ResearchMissionContinuationEligibleTests(unittest.TestCase):
    def test_only_unresolved_and_partially_satisfied_are_eligible(self):
        for status in GoalStatus:
            with self.subTest(status=status):
                self.assertEqual(
                    continuation_eligible(status), status in ELIGIBLE_STATUSES
                )


class ResearchMissionContinuationProposalForTests(unittest.TestCase):
    def test_returns_none_for_every_ineligible_status(self):
        for status in GoalStatus:
            if status in ELIGIBLE_STATUSES:
                continue
            with self.subTest(status=status):
                outcome, stop_reason = _OUTCOME_BY_STATUS[status]
                result = continuation_proposal_for(
                    run(), outcome, PLAN_DIGEST, stop_reason
                )
                self.assertIsNone(result)

    def test_returns_a_fully_populated_proposal_for_each_eligible_status(self):
        for status in ELIGIBLE_STATUSES:
            with self.subTest(status=status):
                outcome, stop_reason = _OUTCOME_BY_STATUS[status]
                subject = run("Why did the incident recur?")

                proposal = continuation_proposal_for(
                    subject, outcome, PLAN_DIGEST, stop_reason, generated_at=NOW
                )

                self.assertIsNotNone(proposal)
                self.assertEqual(proposal.origin_run_id, subject.run_id)
                self.assertEqual(proposal.origin_plan_digest, PLAN_DIGEST)
                self.assertIs(proposal.origin_stop_reason, stop_reason)
                self.assertIs(proposal.origin_goal_status, status)
                self.assertIs(
                    proposal.origin_evidence_status, outcome.evidence_evaluation.status
                )
                self.assertEqual(
                    proposal.origin_evidence_limitations,
                    outcome.evidence_evaluation.limitations,
                )
                self.assertEqual(proposal.seed_question, subject.question)
                self.assertEqual(proposal.generated_at, NOW)
                self.assertTrue(proposal.proposal_id)

    def test_generated_at_defaults_to_now_when_not_supplied(self):
        outcome, stop_reason = _OUTCOME_BY_STATUS[GoalStatus.UNRESOLVED]
        before = datetime.now(UTC)

        proposal = continuation_proposal_for(run(), outcome, PLAN_DIGEST, stop_reason)

        after = datetime.now(UTC)
        self.assertLessEqual(before, proposal.generated_at)
        self.assertLessEqual(proposal.generated_at, after)

    def test_determinism_with_identical_inputs_and_fixed_generated_at(self):
        outcome, stop_reason = _OUTCOME_BY_STATUS[GoalStatus.PARTIALLY_SATISFIED]
        subject = run()

        first = continuation_proposal_for(
            subject, outcome, PLAN_DIGEST, stop_reason, generated_at=NOW
        )
        second = continuation_proposal_for(
            subject, outcome, PLAN_DIGEST, stop_reason, generated_at=NOW
        )

        self.assertEqual(
            dataclasses.replace(first, proposal_id="fixed"),
            dataclasses.replace(second, proposal_id="fixed"),
        )

    def test_seed_question_tracks_run_question_and_nothing_else_changes(self):
        outcome, stop_reason = _OUTCOME_BY_STATUS[GoalStatus.UNRESOLVED]

        first = continuation_proposal_for(
            run("Original question?"),
            outcome,
            PLAN_DIGEST,
            stop_reason,
            generated_at=NOW,
        )
        second = continuation_proposal_for(
            run("A different question?"),
            outcome,
            PLAN_DIGEST,
            stop_reason,
            generated_at=NOW,
        )

        self.assertEqual(first.seed_question, "Original question?")
        self.assertEqual(second.seed_question, "A different question?")
        for field in dataclasses.fields(ResearchMissionContinuationProposal):
            if field.name in {"seed_question", "proposal_id"}:
                continue
            self.assertEqual(
                getattr(first, field.name),
                getattr(second, field.name),
                f"Field {field.name} unexpectedly changed with the question.",
            )

    def test_rejects_a_non_research_run(self):
        outcome, stop_reason = _OUTCOME_BY_STATUS[GoalStatus.UNRESOLVED]
        with self.assertRaises(ResearchError):
            continuation_proposal_for(object(), outcome, PLAN_DIGEST, stop_reason)

    def test_rejects_a_non_mission_outcome(self):
        with self.assertRaises(ResearchError):
            continuation_proposal_for(
                run(), object(), PLAN_DIGEST, AutonomyStopReason.STEP_INTERRUPTED
            )


class ResearchMissionContinuationProposalFieldAllowlistTests(unittest.TestCase):
    def test_field_set_is_exactly_the_approved_nine(self):
        actual = {
            field.name
            for field in dataclasses.fields(ResearchMissionContinuationProposal)
        }

        self.assertEqual(actual, EXPECTED_FIELDS)


if __name__ == "__main__":
    unittest.main()
