"""Recorded candidates survive desktop review, approval and execution exactly."""

import unittest
from dataclasses import replace
from unittest.mock import patch

from desktop.AcquisitionResearchDraft import AcquisitionResearchDraft
from research.ResearchPlanDigest import plan_digest
from research.ResearchRunStatus import ResearchRunStatus
from tests.e2e import test_question_research_handoff as opening


class Selector:
    def __init__(self):
        self.index = -1

    def current(self, index=None):
        if index is not None:
            self.index = index
        return self.index

    def configure(self, **kwargs):
        if not kwargs.get("values"):
            self.index = -1


class AcquisitionDesktopHandoffTests(unittest.TestCase):
    def setUp(self):
        self.fixture = opening.QuestionResearchHandoffTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture.fixture
        self.run = f.run_manager.add_discovery(
            self.fixture.run.run_id,
            self.fixture.run.question,
            f.discovery_provider.provider_name,
            f.discovery_provider.discover(self.fixture.run.question, limit=2),
        )
        self.window, self.widgets = self.fixture._window()
        self.window._controller = self.fixture.controller
        self.window._research_run_id.set(self.run.run_id)
        self.window._append_response = lambda _response: None
        self.window._research_candidate_selector = Selector()
        self.window._show_research_run_candidates(self.run)

    def click(self, text):
        next(w for w in self.widgets if w.text == text).command()

    def select_batch(self):
        for index in (0, 1):
            self.window._research_candidate_selector.current(index)
            self.click("Add to fetch batch")
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            self.click("Review fetch batch")
        return self.window._question_plan_draft

    def test_real_buttons_select_then_existing_controller_approves_and_fetches(self):
        draft = self.select_batch()
        self.assertIsInstance(draft, AcquisitionResearchDraft)
        self.assertEqual(self.fixture.store.load(), [])
        self.assertEqual(self.fixture.fixture.source_fetcher.urls, [])
        self.assertEqual(
            self.window._research_plan_instructions.value, draft.instruction_text
        )
        options = self.window._opening_plan_options()
        args = (self.run.question, draft.instruction_text, "", self.run.run_id)
        controller = self.fixture.controller
        response = controller.preview_plan_authorization(*args, **options)
        self.assertTrue(response.success, response.message)
        auth = response.research_plan_authorization
        self.assertEqual(auth.plan_digest, plan_digest(draft.plan))
        confirmed = controller.confirm_plan_authorization(
            auth.authorization_id, *args, **options
        )
        self.assertTrue(confirmed.success, confirmed.message)
        started = controller.start_authorized_execution(
            auth.authorization_id, *args, **options
        )
        self.assertTrue(started.success, started.message)
        self.assertEqual(self.fixture.fixture.source_fetcher.urls, [])
        done = controller.continue_research_execution(
            started.research_plan_execution.plan_id, "2"
        )
        self.assertTrue(done.success, done.message)
        self.assertEqual(
            self.fixture.fixture.source_fetcher.urls, list(draft.selected_urls)
        )
        self.assertEqual(len(done.research_source_previews), 2)
        self.assertEqual(
            self.fixture.fixture.run_manager.get(self.run.run_id).sources, ()
        )

    def test_duplicate_and_mixed_discovery_do_not_expand_basket(self):
        self.click("Add to fetch batch")
        first = self.window._batch_source_urls
        self.click("Add to fetch batch")
        self.assertEqual(self.window._batch_source_urls, first)
        self.window._research_candidate_selector.current(1)
        self.window._research_candidate_discovery_ids = ("first", "other")
        self.click("Add to fetch batch")
        self.assertEqual(self.window._batch_source_urls, first)
        self.click("Clear batch")
        self.assertEqual(self.window._batch_source_urls, ())

    def test_declined_review_does_not_select_or_authorize(self):
        self.click("Add to fetch batch")
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ):
            self.click("Review fetch batch")
        self.assertIsNone(self.window._question_plan_draft)
        self.assertEqual(self.fixture.store.load(), [])

    def test_preserves_constraints_and_previous_draft(self):
        self.click("Add to fetch batch")
        self.window._research_plan_constraints.value = "Do not go online"
        with patch("desktop.TkinterDesktopWindow.messagebox.askyesno") as confirm:
            self.click("Review fetch batch")
        confirm.assert_not_called()
        self.assertIsNone(self.window._question_plan_draft)
        self.window._research_plan_constraints.value = ""
        self.select_batch()
        self.window._clear_question_plan()
        self.assertEqual(
            self.window._research_plan_instructions.value, "previous instructions"
        )
        self.assertEqual(
            self.window._research_plan_source_ids.value, "previous sources"
        )

    def test_refresh_clears_basket_and_changed_run_is_refused(self):
        self.click("Add to fetch batch")
        self.window._clear_research_candidates()
        self.assertEqual(self.window._batch_source_urls, ())
        self.assertIsNone(self.window._research_candidate_snapshot)
        self.window._show_research_run_candidates(self.run)
        self.click("Add to fetch batch")
        self.window._research_run_id.set("another-run")
        self.click("Review fetch batch")
        self.assertIsNone(self.window._question_plan_draft)

    def test_changed_run_or_canonical_selection_refused_before_approval(self):
        draft = self.select_batch()
        args = (self.run.question, draft.instruction_text, "")
        with self.assertRaises(ValueError):
            self.fixture.controller.preview_plan_authorization(
                *args, "wrong-run", opening_draft=draft
            )
        service = self.fixture.fixture.run_manager
        with patch.object(
            service,
            "get",
            return_value=replace(self.run, status=ResearchRunStatus.COMPLETED),
        ):
            with self.assertRaises(ValueError):
                self.fixture.controller.preview_plan_authorization(
                    *args, self.run.run_id, opening_draft=draft
                )
        self.assertEqual(self.fixture.store.load(), [])
        self.assertEqual(self.fixture.fixture.source_fetcher.urls, [])

    def test_tampered_draft_is_rejected(self):
        draft = self.select_batch()
        with self.assertRaises(ValueError):
            replace(draft, selected_urls=draft.selected_urls[::-1])
        with self.assertRaises(ValueError):
            draft.metadata(draft.plan.question, "edited", "")


if __name__ == "__main__":
    unittest.main()
