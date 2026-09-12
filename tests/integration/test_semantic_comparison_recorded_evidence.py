"""Real recorded inputs into a fake adapter, NOT automatic model execution.

The explicit test-side call is not a mission authorization. Runtime mission
composition remains unchanged and disallows model spend in this milestone.
"""

import json
import unittest
from unittest.mock import Mock

from research.LLMSemanticComparisonProposalProvider import (
    LLMSemanticComparisonProposalProvider,
)
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.SemanticComparisonRequest import SemanticComparisonRequest
from tests.integration import test_research_mission_comparison as mission


class RecordedSemanticComparisonTests(unittest.TestCase):
    make_engine = mission.MissionComparisonTests.make_engine
    execution = mission.MissionComparisonTests.execution
    start = mission.MissionComparisonTests.start
    setUp = mission.MissionComparisonTests.setUp

    def test_real_evidence_provenance_without_canonical_writes(self):
        response = self.start()
        run = response.research_runs[0]
        before = self.manager.get(run.run_id)
        approvals = self.approval_store.load()
        snapshots = self.store.load()
        request = SemanticComparisonRequest(run.run_id, run.question, run.evidence)
        model = Mock()
        model.generate_json.return_value = json.dumps(
            {
                "comparisons": [
                    {
                        "relation": "possible_conflict",
                        "left_quote": run.evidence[0].excerpt,
                        "right_quote": run.evidence[1].excerpt,
                        "rationale": (
                            "The excerpts appear to differ; investigate conditions."
                        ),
                    }
                ]
            }
        )
        proposals = LLMSemanticComparisonProposalProvider(model).propose_prepared(
            request, request.content_fingerprint
        )
        self.assertEqual(
            proposals[0].evidence_ids, tuple(e.evidence_id for e in run.evidence)
        )
        self.assertEqual(self.manager.get(run.run_id), before)
        self.assertEqual(self.approval_store.load(), approvals)
        self.assertEqual(self.store.load(), snapshots)
        self.assertEqual(self.fetcher.fetch.call_count, 2)
        self.provider.discover.assert_called_once()
        model.generate_json.assert_called_once()

    def test_original_mission_still_rejects_model_budget(self):
        response = self.start(
            ResearchAutonomyBudget(
                max_step_advances=11, max_network_operations=5, max_llm_operations=1
            )
        )
        self.assertFalse(response.success)
        self.provider.discover.assert_not_called()
        self.fetcher.fetch.assert_not_called()
        self.assertEqual(self.approval_store.load(), [])

    def test_ordinary_mission_keeps_lexical_output_and_zero_model_spend(self):
        response = self.start()
        self.assertEqual(response.research_plan_execution.completed_steps, 11)
        self.assertEqual(self.store.load()[0].allowance.spend.llm_operations, 0)
        run = response.research_runs[0]
        self.assertEqual(len(run.comparison_notes), 1)
        self.assertIn("not a semantic verdict", run.comparison_notes[0].text)
        self.assertEqual((run.claims, run.claim_contradictions), ((), ()))
