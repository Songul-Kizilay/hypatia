"""Strict bounded-state tests for the existing mission follow-up decision."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchMissionFollowupDecision import (
    ResearchMissionFollowupDecision,
    ResearchMissionFollowupDecisionStatus,
)
from research.ResearchPlanStepCapability import ResearchPlanStepCapability as Cap


def decision(**changes: object) -> ResearchMissionFollowupDecision:
    values: dict[str, object] = {
        "status": ResearchMissionFollowupDecisionStatus.PROPOSED,
        "plan_digest": "a" * 64,
        "step_id": "mission-10-source_fetch",
        "capability": Cap.SOURCE_FETCH,
        "semantic_note_id": "comparison-note-1",
        "semantic_input_fingerprint": "b" * 64,
        "semantic_relation": "possible_conflict",
    }
    values.update(changes)
    return ResearchMissionFollowupDecision(**values)  # type: ignore[arg-type]


class ResearchMissionFollowupDecisionTests(unittest.TestCase):
    def test_proposed_decision_names_only_the_existing_fetch_capability(self) -> None:
        value = decision()

        self.assertTrue(value.proposed)
        self.assertEqual(value.capability, Cap.SOURCE_FETCH)
        self.assertNotIn("url", repr(value).lower())
        self.assertNotIn("provider", repr(value).lower())

    def test_blocked_predecessor_never_invents_a_semantic_binding(self) -> None:
        value = decision(
            status=ResearchMissionFollowupDecisionStatus.BLOCKED_PREDECESSOR,
            semantic_note_id="",
            semantic_input_fingerprint="",
            semantic_relation="",
        )

        self.assertFalse(value.proposed)
        self.assertEqual(value.semantic_note_id, "")

    def test_arbitrary_capability_or_partial_binding_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            decision(capability=Cap.SOURCE_DISCOVERY)
        with self.assertRaises(ResearchError):
            decision(semantic_relation="")


if __name__ == "__main__":
    unittest.main()
