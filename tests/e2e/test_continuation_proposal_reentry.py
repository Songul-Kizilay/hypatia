"""Re-entry via a continuation proposal carries no privilege manual entry lacks.

`ResearchMissionContinuationProposal.seed_question` is exactly `run.question`,
repeated verbatim. This proves that feeding it back into the ordinary
question-preview -> authorization -> start path produces the exact same plan
digest and the exact same authorization behavior a person typing the
identical words would get: no elevated capability, no bypassed authorization
step, no different digest-derivation behavior.
"""

from __future__ import annotations

import sys
import unittest
from hashlib import sha256
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from cognition.CognitiveEngine import CognitiveEngine
from desktop.DesktopController import DesktopController
from desktop.QuestionResearchDraft import QuestionResearchDraft
from planner.Planner import Planner
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
)
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchMissionContinuationProposal import continuation_proposal_for
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus,
)
from research.ResearchMissionOutcome import mission_outcome_for
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from response.ResponseComposer import ResponseComposer
from session.SessionRenameTransactionService import SessionRenameTransactionService
from tests.cognition import test_research_mission_audit_application_service as fixture
from tests.e2e import test_explicit_research_execution_scenario as scenario

#: Typed independently of the proposal machinery below, so the comparison
#: against it proves nothing about re-entry was special-cased. This is
#: exactly what `fixture._run()`'s default question already is; naming it
#: separately here means the "manual" side of every comparison never reads
#: `proposal` at all.
MANUALLY_TYPED_QUESTION = "What do the recorded sources support?"

#: A syntactically valid origin-plan digest for the fixture mission the
#: proposal cites. Its exact bytes are irrelevant here: this test is about
#: what happens downstream of `seed_question`, not the origin citation.
ORIGIN_PLAN_DIGEST = sha256(b"reentry-origin-plan").hexdigest()


class ContinuationProposalReentryTests(unittest.TestCase):
    """`seed_question` fed back in is indistinguishable from manual entry."""

    def setUp(self) -> None:
        self.fixture = scenario.ExplicitResearchExecutionScenarioTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        f = self.fixture
        self.store = JsonFileResearchPlanAuthorizationStore(
            Path(f.temporary_directory.name) / "approvals.json"
        )
        self.engine = CognitiveEngine(
            f.knowledge_engine,
            f.memory_manager,
            Planner(),
            f.event_bus,
            ResponseComposer(),
            f.session_manager,
            SessionRenameTransactionService(
                session_manager=f.session_manager,
                memory_manager=f.memory_manager,
                event_bus=f.event_bus,
            ),
            research_run_manager=f.run_manager,
            research_source_discovery_provider=f.discovery_provider,
            research_source_discovery_providers={
                ResearchDiscoveryProviderName.CROSSREF: f.discovery_provider,
            },
            research_source_fetcher=f.source_fetcher,
            plan_authorization_store=self.store,
        )
        self.controller = DesktopController(self.engine)

    def _unresolved_proposal(self):
        """Derive a proposal from an unresolved mission built by the existing fixture.

        Reuses `fixture._run`, already exercised by
        `test_research_mission_audit_application_service`, rather than
        hand-rolling a new production-shaped `ResearchRun`.
        """
        run = fixture._run(with_note=False)
        outcome = mission_outcome_for(run, AutonomyStopReason.STEP_INTERRUPTED, None)
        self.assertIs(
            outcome.goal_satisfaction.status,
            ResearchMissionGoalSatisfactionStatus.UNRESOLVED,
        )
        proposal = continuation_proposal_for(
            run, outcome, ORIGIN_PLAN_DIGEST, AutonomyStopReason.STEP_INTERRUPTED
        )
        self.assertIsNotNone(proposal)
        return proposal

    def test_reentry_preview_matches_a_fresh_manual_preview_byte_for_byte(self):
        proposal = self._unresolved_proposal()
        self.assertEqual(proposal.seed_question, MANUALLY_TYPED_QUESTION)

        reentry_response = self.controller.preview_question_plan(
            proposal.seed_question, "crossref"
        )
        manual_response = self.controller.preview_question_plan(
            MANUALLY_TYPED_QUESTION, "crossref"
        )

        self.assertTrue(reentry_response.success, reentry_response.message)
        self.assertTrue(manual_response.success, manual_response.message)
        reentry_plan = reentry_response.research_plan_draft_preview.plan
        manual_plan = manual_response.research_plan_draft_preview.plan

        self.assertEqual(plan_digest(reentry_plan), plan_digest(manual_plan))
        self.assertEqual(
            [step.capability for step in reentry_plan.steps],
            [step.capability for step in manual_plan.steps],
        )
        self.assertEqual(
            [step.capability for step in reentry_plan.steps],
            [
                ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                ResearchPlanStepCapability.SOURCE_DISCOVERY,
            ],
        )
        self.assertEqual(reentry_plan.constraints, ())
        self.assertIsNone(reentry_plan.target_binding)
        self.assertIsNone(reentry_plan.mission_scope)

    def test_reentry_question_reaches_authorization_and_start_unremarkably(self):
        proposal = self._unresolved_proposal()

        preview = self.controller.preview_question_plan(
            proposal.seed_question, "crossref"
        )
        self.assertTrue(preview.success, preview.message)
        plan = preview.research_plan_draft_preview.plan
        draft = QuestionResearchDraft(plan)
        run = self.fixture.run_manager.create(proposal.seed_question)
        args = (proposal.seed_question, draft.instruction_text, "", run.run_id)

        authorization_preview = self.controller.preview_plan_authorization(
            *args, opening_draft=draft
        )
        self.assertTrue(authorization_preview.success, authorization_preview.message)
        approval = authorization_preview.research_plan_authorization
        self.assertEqual(approval.plan_digest, plan_digest(plan))
        self.assertEqual(self.store.load(), [])

        confirmed = self.controller.confirm_plan_authorization(
            approval.authorization_id, *args, opening_draft=draft
        )
        self.assertTrue(confirmed.success, confirmed.message)
        self.assertIsNone(self.store.load()[0].consumption)

        started = self.controller.start_authorized_execution(
            approval.authorization_id, *args, opening_draft=draft
        )
        self.assertTrue(started.success, started.message)
        state = started.research_plan_execution
        self.assertEqual(state.status.value, "running")
        self.assertTrue(all(s.status.value == "pending" for s in state.steps))
        self.assertIsNotNone(self.store.load()[0].consumption)
        self.assertEqual(self.fixture.discovery_provider.queries, [])


if __name__ == "__main__":
    unittest.main()
