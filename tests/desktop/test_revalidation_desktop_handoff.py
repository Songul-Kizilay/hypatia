"""Desktop wiring for source revalidation: picker, propose button, full chain.

Mirrors `tests/desktop/test_acquisition_batch_handoff.py`'s shape for the twin
"recorded selection becomes an inert plan, reviewed through the unchanged
preview -> authorize -> start chain" pattern, but for a prior OBSERVATION
rather than a discovered candidate -- the property that matters most here is
that the resulting binding can never name a run or observation the operator
did not actually select (no source-identity substitution), and that nothing
about proposing a revalidation itself approves or starts anything.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from desktop.ResearchWorkspaceReadModel import ResearchWorkspaceReadModel
from desktop.RevalidationResearchDraft import RevalidationResearchDraft
from research.ResearchPlanDigest import plan_digest
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from research.ResearchSourceRevalidationOutcome import ResearchSourceRevalidationOutcome
from tests.e2e import test_explicit_research_execution_scenario as scenario
from tests.e2e import test_question_research_handoff as opening

#: The scenario fetcher only knows this fixed set of bodies; using one of its
#: own URLs lets the real `source_revalidation` operation actually re-fetch.
REQUESTED_URL = scenario.FIRST_URL
#: Strictly before the scenario fetcher's own fixed `fetched_at` (2026-08-01),
#: so the later revalidated observation is unambiguously later, as
#: `ResearchRunManager.add_revalidated_source` requires.
FETCHED_AT = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


class Selector:
    """A minimal stand-in for a real `ttk.Combobox`'s selection index only."""

    def __init__(self) -> None:
        self.index = -1

    def current(self, index: int | None = None) -> int:
        if index is not None:
            self.index = index
        return self.index

    def configure(self, **kwargs: object) -> None:
        if not kwargs.get("values"):
            self.index = -1


class RevalidationDesktopHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = opening.QuestionResearchHandoffTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture.fixture
        acceptance = ResearchSourceAcceptanceService(f.knowledge_engine, f.run_manager)
        accepted = acceptance.accept(
            ResearchSource(
                url=REQUESTED_URL,
                title="Advisory",
                content="Version one.",
                content_type="text/plain",
                fetched_at=FETCHED_AT,
            ),
            self.fixture.run.run_id,
            requested_url=REQUESTED_URL,
        )
        assert accepted.accepted and accepted.document_id is not None
        self.run = f.run_manager.get(self.fixture.run.run_id)
        self.prior_observation_id = self.run.sources[0].observation_id
        assert self.prior_observation_id is not None
        self.window, self.widgets = self.fixture._window()
        self.window._controller = self.fixture.controller
        self.window._research_run_id.set(self.run.run_id)
        self.window._append_response = lambda _response: None
        self.window._revalidation_source_selector = Selector()
        self.window._research_runs = (self.run,)
        self.window._render_research_source_selector(self.run)

    def click(self, text: str) -> None:
        next(w for w in self.widgets if w.text == text).command()

    def propose(self, index: int = 0):  # type: ignore[no-untyped-def]
        self.window._revalidation_source_selector.current(index)
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            self.click("Propose revalidation")
        return self.window._question_plan_draft

    def test_real_button_is_bound_to_the_real_handler(self) -> None:
        matches = [w for w in self.widgets if w.text == "Propose revalidation"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].command, self.window._propose_source_revalidation)

    def test_the_picker_excludes_legacy_and_ineligible_sources(self) -> None:
        legacy = self.window._research_source_catalog[0]
        run = replace(
            self.run,
            sources=(
                legacy,
                replace(
                    legacy,
                    document_id="legacy-no-observation",
                    observation_id=None,
                    requested_url=None,
                ),
                replace(
                    legacy,
                    document_id="legacy-no-requested-url",
                    observation_id="observation-legacy",
                    requested_url=None,
                ),
            ),
        )

        self.window._render_research_source_selector(run)

        self.assertEqual(self.window._revalidation_sources, (legacy,))

    def test_revalidation_eligible_sources_keeps_only_eligible_in_order(self) -> None:
        eligible = self.window._research_source_catalog[0]
        legacy_no_observation = replace(
            eligible, document_id="legacy-no-observation", observation_id=None
        )
        legacy_no_requested_url = replace(
            eligible, document_id="legacy-no-requested-url", requested_url=None
        )
        other_eligible = replace(
            eligible,
            document_id="other-eligible",
            observation_id="observation-other",
        )

        self.assertEqual(
            ResearchWorkspaceReadModel.revalidation_eligible_sources(()), ()
        )
        self.assertEqual(
            ResearchWorkspaceReadModel.revalidation_eligible_sources(
                (
                    legacy_no_observation,
                    eligible,
                    legacy_no_requested_url,
                    other_eligible,
                )
            ),
            (eligible, other_eligible),
        )

    def test_proposing_selects_a_draft_and_makes_exactly_one_preview_call(
        self,
    ) -> None:
        spy = Mock(wraps=self.fixture.controller)
        self.window._controller = spy

        draft = self.propose()

        self.assertIsInstance(draft, RevalidationResearchDraft)
        self.assertEqual(draft.run.run_id, self.run.run_id)
        self.assertEqual(draft.prior_observation_id, self.prior_observation_id)
        spy.preview_source_revalidation.assert_called_once_with(
            self.run.run_id, self.prior_observation_id
        )
        spy.preview_plan_authorization.assert_not_called()
        spy.confirm_plan_authorization.assert_not_called()
        spy.start_authorized_execution.assert_not_called()

    def test_declined_confirmation_selects_nothing(self) -> None:
        self.window._revalidation_source_selector.current(0)
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ):
            self.click("Propose revalidation")
        self.assertIsNone(self.window._question_plan_draft)
        self.assertEqual(self.fixture.store.load(), [])

    def test_stale_draft_construction_is_rejected(self) -> None:
        current = self.fixture.controller.preview_source_revalidation(
            self.run.run_id, self.prior_observation_id
        )
        stale_plan = current.research_plan_draft_preview.plan
        f = self.fixture.fixture
        widened = f.run_manager.add_source(
            self.run.run_id,
            ResearchSource(
                url="https://example.test/other",
                title="Other",
                content="Other content.",
                content_type="text/plain",
                fetched_at=FETCHED_AT,
            ),
            "document-other",
            requested_url="https://example.test/other",
        )

        with self.assertRaises(ValueError):
            RevalidationResearchDraft(widened, self.prior_observation_id, stale_plan)

    def test_controller_rechecks_and_refuses_a_draft_staled_after_it_was_built(
        self,
    ) -> None:
        """A separate, controller-level re-check, distinct from the dataclass's own.

        `RevalidationResearchDraft.__post_init__` only checks the plan at
        construction time. This proves the controller's `_plan_authorization_request`
        independently re-derives the current canonical preview and refuses a
        draft that was valid when built but whose run changed afterward --
        e.g. gained more sources or went terminal -- before authorization was
        previewed.
        """
        draft = self.propose()
        args = (self.run.question, draft.instruction_text, "", self.run.run_id)
        f = self.fixture.fixture
        with patch.object(
            f.run_manager,
            "get",
            return_value=replace(self.run, status=ResearchRunStatus.COMPLETED),
        ):
            with self.assertRaises(ValueError) as ctx:
                self.fixture.controller.preview_plan_authorization(
                    *args, opening_draft=draft
                )
        self.assertEqual(
            str(ctx.exception),
            "The recorded selection changed. Review a new proposal.",
        )
        self.assertEqual(self.fixture.store.load(), [])
        self.assertEqual(f.source_fetcher.urls, [])

    def test_full_chain_performs_a_genuine_revalidation(self) -> None:
        draft = self.propose()
        args = (self.run.question, draft.instruction_text, "", self.run.run_id)
        controller = self.fixture.controller
        preview = controller.preview_plan_authorization(*args, opening_draft=draft)
        self.assertTrue(preview.success, preview.message)
        auth = preview.research_plan_authorization
        self.assertEqual(auth.plan_digest, plan_digest(draft.plan))
        confirmed = controller.confirm_plan_authorization(
            auth.authorization_id, *args, opening_draft=draft
        )
        self.assertTrue(confirmed.success, confirmed.message)
        started = controller.start_authorized_execution(
            auth.authorization_id, *args, opening_draft=draft
        )
        self.assertTrue(started.success, started.message)
        f = self.fixture.fixture
        self.assertEqual(f.source_fetcher.urls, [])
        done = controller.continue_research_execution(
            started.research_plan_execution.plan_id, "2"
        )
        self.assertTrue(done.success, done.message)
        self.assertEqual(f.source_fetcher.urls, [REQUESTED_URL])
        run = f.run_manager.get(self.run.run_id)
        self.assertEqual(len(run.sources), 2)
        self.assertEqual(
            run.sources[1].revalidation_of_observation_id, self.prior_observation_id
        )
        relations = f.run_manager.source_revalidations()
        self.assertEqual(len(relations), 1)
        # The scenario fetcher returns the fixed first-study body, which
        # differs from the "Version one." content accepted in setUp for the
        # same URL, so the two observations genuinely differ.
        self.assertEqual(
            relations[0].record.outcome,
            ResearchSourceRevalidationOutcome.CONTENT_CHANGED,
        )

    def test_cross_run_mismatch_is_refused_end_to_end(self) -> None:
        draft = self.propose()
        f = self.fixture.fixture
        other_run = f.run_manager.create("A different question entirely?")
        args = (self.run.question, draft.instruction_text, "")

        with self.assertRaisesRegex(ValueError, "another research run"):
            self.fixture.controller.preview_plan_authorization(
                *args, other_run.run_id, opening_draft=draft
            )
        self.assertEqual(self.fixture.store.load(), [])
        self.assertEqual(f.source_fetcher.urls, [])


if __name__ == "__main__":
    unittest.main()
