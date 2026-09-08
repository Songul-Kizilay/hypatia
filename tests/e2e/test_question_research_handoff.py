"""Exact opening preview -> ordinary approval -> zero-step start -> discovery."""

import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from cognition.CognitiveEngine import CognitiveEngine
from desktop.DesktopController import DesktopController
from desktop.QuestionResearchDraft import QuestionResearchDraft
from planner.Planner import Planner
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
)
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchPlanDigest import plan_digest
from response.ResponseComposer import ResponseComposer
from session.SessionRenameTransactionService import SessionRenameTransactionService
from tests.desktop.test_research_command_bindings import build_real_window
from tests.desktop.test_target_research_plan_ui import _Text
from tests.e2e import test_explicit_research_execution_scenario as scenario

QUESTION = "Research indirect prompt injection defenses."


class QuestionResearchHandoffTests(unittest.TestCase):
    def setUp(self):
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
        self.plan = self.controller.preview_question_plan(
            QUESTION, "crossref"
        ).research_plan_draft_preview.plan
        self.draft = QuestionResearchDraft(self.plan)
        self.run = f.run_manager.create(QUESTION)

    def test_exact_preview_can_be_approved_started_and_bounded_to_candidates(self):
        args = (QUESTION, self.draft.instruction_text, "", self.run.run_id)
        preview = self.controller.preview_plan_authorization(
            *args, opening_draft=self.draft
        )
        self.assertTrue(preview.success, preview.message)
        approval = preview.research_plan_authorization
        self.assertEqual(approval.plan_digest, plan_digest(self.plan))
        self.assertEqual(self.store.load(), [])
        confirmed = self.controller.confirm_plan_authorization(
            approval.authorization_id, *args, opening_draft=self.draft
        )
        self.assertTrue(confirmed.success, confirmed.message)
        self.assertIsNone(self.store.load()[0].consumption)
        self.assertEqual(self.fixture.discovery_provider.queries, [])
        started = self.controller.start_authorized_execution(
            approval.authorization_id, *args, opening_draft=self.draft
        )
        self.assertTrue(started.success, started.message)
        state = started.research_plan_execution
        self.assertEqual(state.status.value, "running")
        self.assertTrue(all(s.status.value == "pending" for s in state.steps))
        self.assertEqual(self.fixture.discovery_provider.queries, [])
        self.assertIsNotNone(self.store.load()[0].consumption)
        done = self.controller.continue_research_execution(state.plan_id, "2")
        self.assertTrue(done.success, done.message)
        self.assertEqual(done.research_plan_execution.status.value, "completed")
        self.assertEqual(self.fixture.discovery_provider.queries, [QUESTION])
        self.assertEqual(self.fixture.source_fetcher.urls, [])
        replay = self.controller.start_authorized_execution(
            approval.authorization_id, *args, opening_draft=self.draft
        )
        self.assertFalse(replay.success)
        self.assertEqual(self.fixture.discovery_provider.queries, [QUESTION])

    def test_changed_fields_and_mixed_constraints_refused_before_runtime(self):
        brain = Mock()
        controller = DesktopController(brain)
        for question, instructions, sources, options in (
            ("changed", self.draft.instruction_text, "", {}),
            (QUESTION, "changed", "", {}),
            (QUESTION, self.draft.instruction_text, "doc", {}),
            (
                QUESTION,
                self.draft.instruction_text,
                "",
                {"constraint_lines": "offline"},
            ),
            (
                QUESTION,
                self.draft.instruction_text,
                "",
                {"restriction": "no_external_source_access"},
            ),
        ):
            with self.assertRaises(ValueError):
                controller.preview_plan_authorization(
                    question,
                    instructions,
                    sources,
                    self.run.run_id,
                    opening_draft=self.draft,
                    **options,
                )
        brain.process.assert_not_called()

    def test_tampered_opening_is_not_a_valid_handoff(self):
        with self.assertRaises(ValueError):
            QuestionResearchDraft(replace(self.plan, steps=(self.plan.steps[1],)))
        with self.assertRaises(ValueError):
            QuestionResearchDraft(
                replace(
                    self.plan,
                    steps=(
                        replace(self.plan.steps[0], instruction="changed"),
                        self.plan.steps[1],
                    ),
                )
            )

    def _window(self):
        window, widgets = build_real_window(plan_authorization_enabled=True)
        window._controller = Mock()
        window._research_question.set(QUESTION)
        window._research_plan_instructions = _Text("previous instructions")
        window._research_plan_source_ids = _Text("previous sources")
        window._research_plan_constraints = _Text()
        window._plan_restriction.set("advisory")
        window._previewed_question_opening = self.plan
        return window, widgets

    def test_real_buttons_select_and_restore_without_runtime_calls(self):
        window, widgets = self._window()
        window._plan_approval_id.set("old approval")
        next(
            w for w in widgets if w.text == "Başlangıç planını onay alanına aktar"
        ).command()
        self.assertEqual(window._question_plan_draft.plan, self.plan)
        self.assertEqual(
            window._research_plan_instructions.value, self.draft.instruction_text
        )
        self.assertEqual(window._research_plan_instructions.state, "disabled")
        self.assertEqual(window._plan_approval_id.get(), "")
        next(w for w in widgets if w.text == "Önceki taslağa dön").command()
        self.assertIsNone(window._question_plan_draft)
        self.assertEqual(
            window._research_plan_instructions.value, "previous instructions"
        )
        self.assertEqual(window._research_plan_source_ids.value, "previous sources")
        window._controller.assert_not_called()
        self.assertEqual(window._controller.method_calls, [])

    def test_selection_preserves_existing_restrictions(self):
        window, _ = self._window()
        window._research_plan_constraints.value = "Keep local"
        window._select_question_plan()
        self.assertIsNone(window._question_plan_draft)
        self.assertEqual(
            window._research_plan_instructions.value, "previous instructions"
        )

    def test_selection_refuses_stale_question(self):
        window, _ = self._window()
        window._research_question.set("new question")
        window._select_question_plan()
        self.assertIsNone(window._question_plan_draft)

    def test_selected_draft_reaches_existing_approval_and_start_handlers(self):
        window, _ = self._window()
        window._select_question_plan()
        window._approval_request = lambda call: call()
        window._preview_plan_authorization()
        self.assertEqual(
            window._controller.preview_plan_authorization.call_args.kwargs[
                "opening_draft"
            ],
            window._question_plan_draft,
        )
        window._plan_approval_id.set("approval-id")
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            window._start_authorized_execution()
        self.assertEqual(
            window._controller.start_authorized_execution.call_args.kwargs[
                "opening_draft"
            ],
            window._question_plan_draft,
        )

    def test_failed_new_preview_clears_pending_selection(self):
        window, _ = self._window()
        window._append_response = Mock()
        response = self.controller.preview_question_plan(QUESTION, "invalid")
        window._complete_question_plan_preview(response)
        window._select_question_plan()
        self.assertIsNone(window._question_plan_draft)


if __name__ == "__main__":
    unittest.main()
