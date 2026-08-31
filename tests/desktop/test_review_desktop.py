"""Looking back at a run becomes possible without becoming interference.

Calibration, reflection and curiosity have all been runtime-only. Each answers
a different question about work already done — how far a claim outruns its
evidence, how the run went, what was never asked — and none of them could be
asked by the person doing the work.

What the tests below mostly assert is what this surface still refuses to do.
Nothing here adjusts a claim, edits a run, changes a confidence, or starts any
research: calibration reports a mismatch and leaves the judgement where it was,
and a ruling on a proposed question records an opinion rather than acting on it.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.CognitiveEngine import CognitiveEngine
from core.RuntimeOptIn import (
    CURIOSITY_ENABLED_VARIABLE,
    REFLECTION_ENABLED_VARIABLE,
    curiosity_enabled,
    reflection_enabled,
)
from desktop.DesktopController import DesktopController
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.JsonFileCuriosityQuestionStore import JsonFileCuriosityQuestionStore
from research.JsonFileReflectionReportStore import JsonFileReflectionReportStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService
from tests.SourceVocabulary import mentions, working_vocabulary

WINDOW_SOURCE = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
    encoding="utf-8"
)
QUESTION = "Does the Saturn ring system have a measured age?"


class RecordingBrain:
    """Records every request instead of processing one."""

    def __init__(self) -> None:
        self.requests: list[BrainRequest] = []

    def process(self, request: BrainRequest | str) -> BrainResponse:
        assert isinstance(request, BrainRequest)
        self.requests.append(request)
        return BrainResponse(
            message="recorded",
            request_id=request.request_id,
            intent="review",
            memory_count=0,
        )


class ControllerFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.brain = RecordingBrain()
        self.controller = DesktopController(self.brain)

    @property
    def last(self) -> BrainRequest:
        return self.brain.requests[-1]


class RunScopedCommandTests(ControllerFixture):
    def test_each_command_carries_only_the_run(self) -> None:
        for method, intent in (
            (self.controller.report_claim_calibration, "research_calibration_report"),
            (self.controller.preview_reflection, "research_reflection_preview"),
            (self.controller.store_reflection, "research_reflection_store"),
            (self.controller.detect_curiosity_gaps, "curiosity_gap_detect"),
            (
                self.controller.preview_curiosity_questions,
                "curiosity_question_preview",
            ),
            (self.controller.store_curiosity_questions, "curiosity_question_store"),
        ):
            with self.subTest(intent=intent):
                method(" run-1 ")
                self.assertEqual(
                    self.last.metadata,
                    {"intent": intent, "research_run_id": "run-1"},
                )
                self.assertEqual(self.last.source, "desktop")

    def test_an_empty_run_is_refused_before_the_brain(self) -> None:
        for method in (
            self.controller.report_claim_calibration,
            self.controller.preview_reflection,
            self.controller.store_reflection,
            self.controller.detect_curiosity_gaps,
            self.controller.preview_curiosity_questions,
            self.controller.store_curiosity_questions,
        ):
            with self.subTest(method=method.__name__):
                with self.assertRaises(ValueError):
                    method("   ")

        self.assertEqual(self.brain.requests, [])


class ListingCommandTests(ControllerFixture):
    def test_listings_name_no_run(self) -> None:
        for method, intent in (
            (self.controller.list_reflections, "research_reflection_list"),
            (self.controller.list_curiosity_questions, "curiosity_question_list"),
            (
                self.controller.report_paired_provider_quality,
                "paired_provider_quality_report",
            ),
        ):
            with self.subTest(intent=intent):
                method()
                self.assertEqual(self.last.metadata, {"intent": intent})


class RulingCommandTests(ControllerFixture):
    def test_a_ruling_carries_only_the_question(self) -> None:
        for method, intent in (
            (self.controller.accept_curiosity_question, "curiosity_question_accept"),
            (self.controller.dismiss_curiosity_question, "curiosity_question_dismiss"),
        ):
            with self.subTest(intent=intent):
                method(" q-1 ")
                self.assertEqual(
                    self.last.metadata,
                    {"intent": intent, "curiosity_question_id": "q-1"},
                )

    def test_an_empty_question_is_refused_before_the_brain(self) -> None:
        with self.assertRaises(ValueError):
            self.controller.accept_curiosity_question("  ")
        with self.assertRaises(ValueError):
            self.controller.dismiss_curiosity_question("")

        self.assertEqual(self.brain.requests, [])

    def test_starting_an_authorized_proposal_carries_only_exact_identities(
        self,
    ) -> None:
        self.controller.start_authorized_curiosity_research_proposal(
            " q-1 ",
            f" {'a' * 64} ",
            " approval-1 ",
        )

        self.assertEqual(
            self.last.metadata,
            {
                "intent": "curiosity_start_authorized_proposal",
                "curiosity_question_id": "q-1",
                "expected_plan_digest": "a" * 64,
                "authorization_id": "approval-1",
            },
        )

    def test_start_refuses_any_missing_identity_before_reaching_the_brain(self) -> None:
        for values in (
            ("", "a" * 64, "approval-1"),
            ("q-1", "", "approval-1"),
            ("q-1", "a" * 64, ""),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.controller.start_authorized_curiosity_research_proposal(*values)

        self.assertEqual(self.brain.requests, [])


class NothingHereAdjustsAnythingTests(unittest.TestCase):
    """The panel reports. It has no control that changes what it reports on."""

    def test_the_panel_offers_no_way_to_adjust_a_claim(self) -> None:
        """Read the code, not the prose around it.

        The docstrings here say the panel changes no confidence, so a text
        search would fail on the sentence promising the absence it is checking.
        """
        vocabulary = working_vocabulary(
            WINDOW_SOURCE,
            "_build_review_tab",
            "_build_curiosity_ruling_section",
            "_build_review_history_section",
        )

        for forbidden in (
            "confidence",
            "epistemic",
            "downgrade",
            "adjust",
            "claim_record",
        ):
            with self.subTest(name=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])

    def test_the_panel_offers_provider_quality_without_promising_a_choice(
        self,
    ) -> None:
        """The one thing a provider statistic must never quietly become."""
        self.assertIn(
            '("Provider quality", self._report_provider_quality)', WINDOW_SOURCE
        )
        self.assertIn(
            '("Paired quality", self._report_paired_provider_quality)', WINDOW_SOURCE
        )
        self.assertIn("selects no provider", WINDOW_SOURCE)
        self.assertIn("changes no default", WINDOW_SOURCE)
        self.assertIn("updates no reputation", WINDOW_SOURCE)

    def test_the_panel_promises_every_denominator(self) -> None:
        self.assertIn("shows every denominator", WINDOW_SOURCE)

    def test_provider_quality_is_not_scoped_to_one_run(self) -> None:
        """Provider experience accumulates; one run is never a sample."""
        start = WINDOW_SOURCE.index("def _report_provider_quality")
        end = WINDOW_SOURCE.index("def ", start + 10)
        handler = WINDOW_SOURCE[start:end]

        self.assertNotIn("_review_run_id", handler)

    def test_paired_quality_is_not_scoped_to_one_selected_run(self) -> None:
        start = WINDOW_SOURCE.index("def _report_paired_provider_quality")
        end = WINDOW_SOURCE.index("def ", start + 10)
        handler = WINDOW_SOURCE[start:end]

        self.assertNotIn("_review_run_id", handler)

    def test_the_panel_says_what_calibration_will_not_do(self) -> None:
        self.assertIn("never adjusts one", WINDOW_SOURCE)
        self.assertIn("starts no research", WINDOW_SOURCE)

    def test_the_panel_promises_warnings_without_promising_correction(self) -> None:
        """It now reads a second thing, and must disclaim that one too."""
        self.assertIn("changes nothing about those either", WINDOW_SOURCE)
        self.assertIn("has not been checked and found sound", WINDOW_SOURCE)


class TabPresenceTests(unittest.TestCase):
    def test_calibration_alone_earns_the_tab(self) -> None:
        """It stores nothing, so there is no opt-in for it to wait on."""
        start = WINDOW_SOURCE.index("def _build_layout")
        end = WINDOW_SOURCE.index("chat_tab.rowconfigure")
        section = WINDOW_SOURCE[start:end]

        self.assertIn('text="Review"', section)
        self.assertNotIn("if self._review", section)

    def test_a_window_defaults_to_neither_kept_surface(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)

        self.assertFalse(window._reflection_enabled)
        self.assertFalse(window._curiosity_enabled)

    def test_each_kept_section_waits_for_its_own_opt_in(self) -> None:
        start = WINDOW_SOURCE.index("def _build_review_tab")
        end = WINDOW_SOURCE.index("def _review_request")
        section = WINDOW_SOURCE[start:end]

        self.assertIn("if self._reflection_enabled:", section)
        self.assertIn("if self._curiosity_enabled:", section)

    def test_the_flags_reach_the_window_from_composition(self) -> None:
        entry = (SRC_DIR / "desktop_main.py").read_text(encoding="utf-8")

        self.assertIn("reflection_enabled=reflection_enabled", entry)
        self.assertIn("curiosity_enabled=curiosity_enabled", entry)


class PanelBehaviourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.window: Any = object.__new__(TkinterDesktopWindow)
        self.window._controller = Mock()
        self.window._review_status = Mock()
        self.window._review_output = Mock()
        self.window._append_response = Mock()
        self.window._review_run_id = Mock()
        self.window._review_run_id.get.return_value = "run-1"
        self.window._curiosity_question_id = Mock()
        self.window._curiosity_question_id.get.return_value = "q-1"
        self.window._curiosity_plan_digest = Mock()
        self.window._curiosity_plan_digest.get.return_value = "a" * 64
        self.window._curiosity_authorization_id = Mock()
        self.window._curiosity_authorization_id.get.return_value = "approval-1"
        self.window._root = Mock()

    def test_calibration_passes_the_run(self) -> None:
        self.window._report_claim_calibration()

        self.window._controller.report_claim_calibration.assert_called_once_with(
            "run-1"
        )

    def test_a_ruling_passes_the_question(self) -> None:
        self.window._accept_curiosity_question()

        self.window._controller.accept_curiosity_question.assert_called_once_with("q-1")

    @patch("desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False)
    def test_declining_start_keeps_the_approval_unused(self, _ask: Mock) -> None:
        self.window._start_authorized_curiosity_research_proposal()

        self.window._controller.start_authorized_curiosity_research_proposal.assert_not_called()
        self.window._review_status.set.assert_called_once_with(
            "curiosity proposal: not started; approval remains unused"
        )

    @patch("desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True)
    def test_confirming_start_sends_one_zero_step_start_request(
        self,
        _ask: Mock,
    ) -> None:
        self.window._review_request = Mock(side_effect=lambda call: call())

        self.window._start_authorized_curiosity_research_proposal()

        self.window._controller.start_authorized_curiosity_research_proposal.assert_called_once_with(
            "q-1",
            "a" * 64,
            "approval-1",
        )

    @patch("desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True)
    def test_authorizing_captures_the_exact_returned_approval_id(
        self,
        _ask: Mock,
    ) -> None:
        authorization = Mock()
        authorization.authorization_id = "approval-returned"
        response = Mock()
        response.research_plan_authorization = authorization
        self.window._review_request = Mock(return_value=response)

        self.window._authorize_curiosity_research_proposal()

        self.window._curiosity_authorization_id.set.assert_called_once_with(
            "approval-returned"
        )

    def test_a_local_refusal_is_shown_and_reaches_no_transcript(self) -> None:
        self.window._controller.preview_reflection.side_effect = ValueError(
            "A research run ID cannot be empty."
        )

        self.window._preview_reflection()

        self.window._review_status.set.assert_called_once_with(
            "A research run ID cannot be empty."
        )
        self.window._append_response.assert_not_called()

    def test_an_unsuccessful_response_is_not_restated_as_success(self) -> None:
        response = Mock()
        response.success = False
        response.message = "This reflection was not durably written."
        self.window._controller.store_reflection.return_value = response

        self.window._store_reflection()

        self.window._review_status.set.assert_called_once_with(
            "That request did not complete."
        )
        self.assertIn(
            "not durably written",
            self.window._review_output.insert.call_args[0][1],
        )


class EndToEndTests(unittest.TestCase):
    """The adapter's metadata keys must be the ones the runtime actually reads."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        document = root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        knowledge_engine = KnowledgeEngine()
        knowledge_engine.load(document)
        self.run_path = root / "runs.json"
        self.manager = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        self.manager.load()
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        session_manager = SessionManager(event_bus)
        engine = CognitiveEngine(
            knowledge_engine,
            memory_manager,
            Planner(),
            event_bus,
            ResponseComposer(),
            session_manager,
            SessionRenameTransactionService(
                session_manager=session_manager,
                memory_manager=memory_manager,
                event_bus=event_bus,
            ),
            research_run_manager=self.manager,
            reflection_report_store=JsonFileReflectionReportStore(
                root / "reflections.json"
            ),
            curiosity_question_store=JsonFileCuriosityQuestionStore(
                root / "questions.json"
            ),
        )
        self.controller = DesktopController(engine)
        self.addCleanup(self.temporary_directory.cleanup)

    def new_run(self) -> str:
        return self.manager.create(QUESTION).run_id

    def test_every_run_scoped_command_reaches_its_service(self) -> None:
        run_id = self.new_run()

        for method in (
            self.controller.report_claim_calibration,
            self.controller.preview_reflection,
            self.controller.store_reflection,
            self.controller.detect_curiosity_gaps,
            self.controller.preview_curiosity_questions,
            self.controller.store_curiosity_questions,
        ):
            with self.subTest(method=method.__name__):
                self.assertTrue(method(run_id).success, method.__name__)

    def test_paired_provider_quality_reaches_its_read_only_service(self) -> None:
        response = self.controller.report_paired_provider_quality()

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "paired_provider_quality")
        self.assertIsNotNone(response.research_paired_provider_quality)

    def test_an_unknown_run_is_refused_by_the_runtime(self) -> None:
        """A misspelled key would be refused for lacking a run ID instead."""
        response = self.controller.report_claim_calibration("run-does-not-exist")

        self.assertFalse(response.success)
        self.assertNotIn("required", response.message.casefold())

    def test_reviewing_changes_nothing_about_the_run(self) -> None:
        run_id = self.new_run()
        before = self.run_path.read_bytes()
        summary = CanonicalResearchSummary.from_runs(self.manager.list())

        self.controller.report_claim_calibration(run_id)
        self.controller.preview_reflection(run_id)
        self.controller.store_reflection(run_id)
        self.controller.store_curiosity_questions(run_id)

        self.assertEqual(self.run_path.read_bytes(), before)
        self.assertEqual(
            CanonicalResearchSummary.from_runs(self.manager.list()),
            summary,
        )

    def test_a_ruling_reaches_the_question_it_names(self) -> None:
        run_id = self.new_run()
        self.controller.store_curiosity_questions(run_id)
        listed = self.controller.list_curiosity_questions()

        # Asserted rather than skipped. A skip here would quietly stop testing
        # the ruling path the day question generation changed.
        self.assertTrue(listed.curiosity_questions)
        question_id = listed.curiosity_questions[0].question_id
        response = self.controller.accept_curiosity_question(question_id)

        self.assertTrue(response.success)
        self.assertIn(question_id, response.message)

    def test_an_unknown_question_is_reported_as_unknown(self) -> None:
        response = self.controller.accept_curiosity_question("q-does-not-exist")

        self.assertFalse(response.success)


class ReviewOptInPolicyTests(unittest.TestCase):
    def test_only_the_exact_opt_in_value_keeps_each_surface(self) -> None:
        self.assertTrue(reflection_enabled({REFLECTION_ENABLED_VARIABLE: "true"}))
        self.assertTrue(curiosity_enabled({CURIOSITY_ENABLED_VARIABLE: "true"}))

    def test_an_unset_or_approximate_value_leaves_them_off(self) -> None:
        for value in ("True", "1", "yes", "", " true "):
            with self.subTest(value=value):
                self.assertFalse(
                    reflection_enabled({REFLECTION_ENABLED_VARIABLE: value})
                )
                self.assertFalse(curiosity_enabled({CURIOSITY_ENABLED_VARIABLE: value}))
        self.assertFalse(reflection_enabled({}))
        self.assertFalse(curiosity_enabled({}))

    def test_the_two_surfaces_are_independent(self) -> None:
        environment = {REFLECTION_ENABLED_VARIABLE: "true"}

        self.assertTrue(reflection_enabled(environment))
        self.assertFalse(curiosity_enabled(environment))


if __name__ == "__main__":
    unittest.main()
