"""Mission outcome projections must never masquerade as goal satisfaction."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from research.BackgroundTaskOutcome import BackgroundTaskOutcome
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchMissionCompletionReadiness import (
    ResearchMissionCompletionReadinessStatus,
)
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus,
)
from research.ResearchMissionOutcome import mission_outcome_for
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceRecord import ResearchSourceRecord

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


def run() -> ResearchRun:
    excerpt = "An exact recorded excerpt."
    return ResearchRun(
        run_id="run-1",
        question="What happened?",
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
        evidence=(
            ResearchEvidenceRecord(
                "evidence-1",
                "doc-1",
                "chunk-1",
                0,
                excerpt,
                False,
                sha256(excerpt.encode("utf-8")).hexdigest(),
                "Grounded only.",
                NOW,
            ),
        ),
    )


class ResearchMissionOutcomeTests(unittest.TestCase):
    def test_delivered_execution_with_incomplete_evidence_is_not_satisfied(self):
        outcome = mission_outcome_for(
            run(), AutonomyStopReason.RESEARCH_DELIVERABLE_READY
        )

        self.assertIs(outcome.execution_outcome, BackgroundTaskOutcome.COMPLETED)
        self.assertFalse(outcome.goal_satisfied)
        self.assertIs(
            outcome.goal_satisfaction.status,
            ResearchMissionGoalSatisfactionStatus.PARTIALLY_SATISFIED,
        )
        self.assertIn(
            "Mission goal satisfaction: Partially satisfied", outcome.summary()
        )
        self.assertIs(
            outcome.completion_readiness.status,
            ResearchMissionCompletionReadinessStatus.NOT_READY_EVIDENCE,
        )
        self.assertIn("Mission completion readiness: Not ready", outcome.summary())

    def test_budget_exhaustion_is_incomplete_work_not_a_failed_goal(self):
        outcome = mission_outcome_for(
            run(), AutonomyStopReason.NETWORK_BUDGET_EXHAUSTED
        )

        self.assertIs(
            outcome.execution_outcome,
            BackgroundTaskOutcome.RETRYABLE_BUDGET_EXHAUSTED,
        )
        self.assertFalse(outcome.goal_satisfied)
        self.assertIs(
            outcome.goal_satisfaction.status,
            ResearchMissionGoalSatisfactionStatus.BUDGET_LIMITED,
        )

    def test_cancelled_execution_remains_distinct_from_evidence_readiness(self):
        outcome = mission_outcome_for(run(), AutonomyStopReason.CANCELLED)

        self.assertIs(outcome.execution_outcome, BackgroundTaskOutcome.CANCELLED)
        self.assertFalse(outcome.goal_satisfied)
        self.assertIs(
            outcome.goal_satisfaction.status,
            ResearchMissionGoalSatisfactionStatus.CANCELLED,
        )


if __name__ == "__main__":
    unittest.main()
