"""The learning loop becomes drivable by the person it was built for.

Hypotheses and failure memory have been in the runtime through several
increments, reachable only from tests. That made the loop real and unusable at
the same time: hypothesis outcomes feed failure memory, failure memory surfaces
itself when a new run begins, and no half of it could be driven from the
application.

The end-to-end tests here matter more than the wiring ones. A controller test
asserts the dictionary the controller builds and a service test builds its own,
so a metadata key the two spelled differently would satisfy both and fail only
in front of a person. The tests at the bottom drive the real runtime instead.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.RuntimeOptIn import (
    FAILURE_MEMORY_ENABLED_VARIABLE,
    HYPOTHESIS_ENABLED_VARIABLE,
    failure_memory_enabled,
    hypothesis_engine_enabled,
)
from desktop.DesktopController import DesktopController
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileFailureLessonStore import JsonFileFailureLessonStore
from research.JsonFileHypothesisStore import JsonFileHypothesisStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

WINDOW_SOURCE = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
    encoding="utf-8"
)
FETCHED = datetime(2026, 8, 1, tzinfo=UTC)

QUESTION = "Does the Saturn ring system have a measured age?"
STATEMENT = "The rings formed within the last hundred million years."
DEFEATER = "A dated ring particle older than one billion years would count against it."


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
            intent="research_hypothesis",
            memory_count=0,
        )


class ControllerFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.brain = RecordingBrain()
        self.controller = DesktopController(self.brain)

    @property
    def last(self) -> BrainRequest:
        return self.brain.requests[-1]


class HypothesisCommandTests(ControllerFixture):
    def test_proposing_carries_the_statement_and_its_defeater(self) -> None:
        self.controller.propose_hypothesis(" run-1 ", f" {STATEMENT} ", f" {DEFEATER} ")

        self.assertEqual(
            self.last.metadata,
            {
                "intent": "research_hypothesis_propose",
                "research_run_id": "run-1",
                "hypothesis_statement": STATEMENT,
                "hypothesis_discriminating_test": DEFEATER,
            },
        )
        self.assertEqual(self.last.source, "desktop")

    def test_a_conjecture_without_a_defeater_is_refused_here(self) -> None:
        """The runtime requires it, so the adapter never sends one without."""
        with self.assertRaises(ValueError):
            self.controller.propose_hypothesis("run-1", STATEMENT, "   ")

        self.assertEqual(self.brain.requests, [])

    def test_supporting_and_opposing_use_the_same_shape(self) -> None:
        self.controller.support_hypothesis("h-1", "e-1")
        supporting = self.last.metadata
        self.controller.oppose_hypothesis("h-1", "e-1")

        self.assertEqual(supporting["intent"], "research_hypothesis_support")
        self.assertEqual(self.last.metadata["intent"], "research_hypothesis_oppose")
        self.assertEqual(self.last.metadata["hypothesis_id"], "h-1")
        self.assertEqual(self.last.metadata["evidence_ids"], ("e-1",))

    def test_withdrawing_names_only_the_hypothesis(self) -> None:
        self.controller.withdraw_hypothesis(" h-1 ")

        self.assertEqual(
            self.last.metadata,
            {"intent": "research_hypothesis_withdraw", "hypothesis_id": "h-1"},
        )

    def test_listing_derives_rather_than_naming_a_run(self) -> None:
        self.controller.list_hypotheses()

        self.assertEqual(self.last.metadata, {"intent": "research_hypothesis_list"})

    def test_an_empty_identifier_is_refused_before_the_brain(self) -> None:
        for call in (
            lambda: self.controller.withdraw_hypothesis("  "),
            lambda: self.controller.support_hypothesis("  ", "e-1"),
            lambda: self.controller.oppose_hypothesis("  ", "e-1"),
        ):
            with self.subTest(call=call):
                with self.assertRaises(ValueError):
                    call()

        self.assertEqual(self.brain.requests, [])


class EvidenceFieldTests(ControllerFixture):
    """One typed field has to become the list the runtime expects."""

    def evidence(self, typed: str) -> tuple[str, ...]:
        self.controller.support_hypothesis("h-1", typed)
        value = self.last.metadata["evidence_ids"]
        assert isinstance(value, tuple)
        return value

    def test_commas_and_spaces_both_separate(self) -> None:
        for typed in ("e-1,e-2", "e-1 e-2", " e-1 , e-2 ", "e-1,  ,e-2"):
            with self.subTest(typed=typed):
                self.assertEqual(self.evidence(typed), ("e-1", "e-2"))

    def test_one_identifier_stays_one_identifier(self) -> None:
        self.assertEqual(self.evidence("  e-1  "), ("e-1",))

    def test_a_field_naming_nothing_is_refused_before_the_brain(self) -> None:
        for typed in ("", "   ", " , ", ",,,"):
            with self.subTest(typed=typed):
                with self.assertRaises(ValueError):
                    self.controller.support_hypothesis("h-1", typed)

        self.assertEqual(self.brain.requests, [])


class FailureMemoryCommandTests(ControllerFixture):
    def test_each_run_command_carries_only_the_run(self) -> None:
        for method, intent in (
            (self.controller.preview_failure_lessons, "failure_memory_preview"),
            (self.controller.store_failure_lessons, "failure_memory_store"),
            (
                self.controller.remember_hypothesis_outcomes,
                "failure_memory_hypothesis_store",
            ),
        ):
            with self.subTest(intent=intent):
                method(" run-1 ")
                self.assertEqual(
                    self.last.metadata,
                    {"intent": intent, "research_run_id": "run-1"},
                )

    def test_recall_carries_the_question(self) -> None:
        self.controller.recall_failure_lessons(f"  {QUESTION}  ")

        self.assertEqual(
            self.last.metadata,
            {"intent": "failure_memory_recall", "research_question": QUESTION},
        )

    def test_listing_lessons_derives_nothing(self) -> None:
        self.controller.list_failure_lessons()

        self.assertEqual(self.last.metadata, {"intent": "failure_memory_list"})

    def test_an_empty_run_or_question_is_refused_before_the_brain(self) -> None:
        for call in (
            lambda: self.controller.preview_failure_lessons("  "),
            lambda: self.controller.store_failure_lessons(""),
            lambda: self.controller.remember_hypothesis_outcomes(" "),
            lambda: self.controller.recall_failure_lessons("   "),
        ):
            with self.subTest(call=call):
                with self.assertRaises(ValueError):
                    call()

        self.assertEqual(self.brain.requests, [])


class TabPresenceTests(unittest.TestCase):
    """Each half is a separate opt-in with its own store."""

    def window(self, hypothesis: bool, lessons: bool) -> Any:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._hypothesis_enabled = hypothesis
        window._failure_memory_enabled = lessons
        return window

    def test_a_window_defaults_to_neither_learning_surface(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)

        self.assertFalse(window._hypothesis_enabled)
        self.assertFalse(window._failure_memory_enabled)
        self.assertFalse(window._learning_visible)

    def test_either_opt_in_earns_the_tab_and_neither_hides_it(self) -> None:
        for hypothesis, lessons, expected in (
            (False, False, False),
            (True, False, True),
            (False, True, True),
            (True, True, True),
        ):
            with self.subTest(hypothesis=hypothesis, lessons=lessons):
                self.assertIs(
                    self.window(hypothesis, lessons)._learning_visible,
                    expected,
                )

    def test_the_tab_is_built_only_when_a_surface_is_durable(self) -> None:
        start = WINDOW_SOURCE.index("def _build_layout")
        end = WINDOW_SOURCE.index("chat_tab.rowconfigure")
        section = WINDOW_SOURCE[start:end]

        self.assertEqual(section.count("if self._learning_visible:"), 2)
        self.assertIn('text="Learning"', section)

    def test_hypothesis_outcomes_are_offered_only_with_a_hypothesis_store(self) -> None:
        """That command reads the durable hypothesis store on every request."""
        start = WINDOW_SOURCE.index("def _build_lesson_section")
        end = WINDOW_SOURCE.index("def _learning_request")
        section = WINDOW_SOURCE[start:end]

        self.assertIn("if self._hypothesis_enabled:", section)
        self.assertIn("Remember hypothesis outcomes", section)

    def test_the_flags_reach_the_window_from_composition(self) -> None:
        entry = (SRC_DIR / "desktop_main.py").read_text(encoding="utf-8")

        self.assertIn("hypothesis_enabled=hypothesis_engine_enabled", entry)
        self.assertIn("failure_memory_enabled=failure_memory_enabled", entry)


class PanelBehaviourTests(unittest.TestCase):
    """Handlers are exercised without a display, as the other panels are."""

    def setUp(self) -> None:
        self.window: Any = object.__new__(TkinterDesktopWindow)
        self.window._controller = Mock()
        self.window._learning_status = Mock()
        self.window._learning_output = Mock()
        self.window._append_response = Mock()
        self.window._hypothesis_run_id = Mock()
        self.window._hypothesis_run_id.get.return_value = "run-1"
        self.window._hypothesis_statement_text = Mock()
        self.window._hypothesis_statement_text.get.return_value = f" {STATEMENT} \n"
        self.window._hypothesis_test_text = Mock()
        self.window._hypothesis_test_text.get.return_value = f" {DEFEATER} \n"
        self.window._lesson_question = Mock()
        self.window._lesson_question.get.return_value = QUESTION

    def test_proposing_passes_the_multi_line_fields_trimmed(self) -> None:
        self.window._propose_hypothesis()

        self.window._controller.propose_hypothesis.assert_called_once_with(
            "run-1",
            STATEMENT,
            DEFEATER,
        )

    def test_a_local_refusal_is_shown_and_reaches_no_transcript(self) -> None:
        self.window._controller.propose_hypothesis.side_effect = ValueError(
            "A hypothesis needs a research run."
        )

        self.window._propose_hypothesis()

        self.window._learning_status.set.assert_called_once_with(
            "A hypothesis needs a research run."
        )
        self.window._append_response.assert_not_called()

    def test_an_unsuccessful_response_is_not_restated_as_success(self) -> None:
        response = Mock()
        response.success = False
        response.message = "Hypotheses were not durably written."
        self.window._controller.recall_failure_lessons.return_value = response

        self.window._recall_failure_lessons()

        self.window._learning_status.set.assert_called_once_with(
            "That request did not complete."
        )
        self.assertIn(
            "not durably written",
            self.window._learning_output.insert.call_args[0][1],
        )


class EndToEndTests(unittest.TestCase):
    """The adapter's metadata keys must be the ones the runtime actually reads."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        document = root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(document)
        self.manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        self.manager.load()
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            None,  # type: ignore[arg-type]
        )
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        session_manager = SessionManager(event_bus)
        engine = CognitiveEngine(
            self.knowledge_engine,
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
            hypothesis_store=JsonFileHypothesisStore(root / "hypotheses.json"),
            failure_lesson_store=JsonFileFailureLessonStore(root / "lessons.json"),
        )
        self.controller = DesktopController(engine)
        self.addCleanup(self.temporary_directory.cleanup)

    def new_run(self) -> str:
        return self.manager.create(QUESTION).run_id

    def evidence(self, run_id: str, slug: str) -> str:
        result = self.acceptance.accept(
            ResearchSource(
                url=f"https://example.test/{slug}",
                title=f"Source {slug}",
                content="Saturn's rings have a debated age.",
                content_type="text/html",
                fetched_at=FETCHED,
            ),
            run_id,
        )
        assert result.document_id is not None
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == result.document_id and candidate.index == 0
        )
        return (
            self.manager.add_evidence(run_id, chunk, "Directly relevant.")
            .evidence[-1]
            .evidence_id
        )

    def propose(self, run_id: str) -> BrainResponse:
        return self.controller.propose_hypothesis(run_id, STATEMENT, DEFEATER)

    def first_hypothesis_id(self) -> str:
        """Read one identifier back the way the panel does: from the listing."""
        appraisals = self.controller.list_hypotheses().hypothesis_appraisals
        return appraisals[0].hypothesis.hypothesis_id

    def test_the_whole_path_proposes_opposes_and_reviews(self) -> None:
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "opposing")

        proposed = self.propose(run_id)
        listed = self.controller.list_hypotheses()
        hypothesis_id = listed.hypothesis_appraisals[0].hypothesis.hypothesis_id
        opposed = self.controller.oppose_hypothesis(hypothesis_id, evidence_id)

        self.assertTrue(proposed.success)
        self.assertTrue(opposed.success)
        self.assertIn(STATEMENT, listed.message)
        self.assertIn("contradicted", opposed.message)

    def test_unrecorded_evidence_is_refused_by_the_runtime_not_the_adapter(
        self,
    ) -> None:
        """This is what proves the evidence field reaches the key that reads it.

        A misspelled key would produce "at least one evidence ID is required",
        because the runtime would see no field at all. Only the right key can
        produce a complaint about the ID not being in the run.
        """
        run_id = self.new_run()
        self.propose(run_id)
        hypothesis_id = self.first_hypothesis_id()

        response = self.controller.support_hypothesis(hypothesis_id, "not-recorded")

        self.assertFalse(response.success)
        self.assertIn("must already be recorded", response.message)

    def test_an_outcome_becomes_a_lesson_and_the_next_run_meets_it(self) -> None:
        """The loop, end to end, through the surface a person actually uses."""
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "against")
        self.propose(run_id)
        hypothesis_id = self.first_hypothesis_id()
        self.controller.oppose_hypothesis(hypothesis_id, evidence_id)

        remembered = self.controller.remember_hypothesis_outcomes(run_id)
        recalled = self.controller.recall_failure_lessons(QUESTION)

        self.assertTrue(remembered.success)
        self.assertTrue(remembered.failure_lessons)
        self.assertIn(STATEMENT, remembered.failure_lessons[0].statement)
        self.assertTrue(recalled.failure_lessons)

    def test_previewing_lessons_remembers_nothing(self) -> None:
        run_id = self.new_run()

        previewed = self.controller.preview_failure_lessons(run_id)
        listed = self.controller.list_failure_lessons()

        self.assertTrue(previewed.success)
        self.assertEqual(listed.failure_lessons, ())


class LearningOptInPolicyTests(unittest.TestCase):
    """One rule per capability, read the same way everywhere."""

    def test_only_the_exact_opt_in_value_keeps_each_surface(self) -> None:
        self.assertTrue(
            hypothesis_engine_enabled({HYPOTHESIS_ENABLED_VARIABLE: "true"})
        )
        self.assertTrue(
            failure_memory_enabled({FAILURE_MEMORY_ENABLED_VARIABLE: "true"})
        )

    def test_an_unset_or_approximate_value_leaves_them_off(self) -> None:
        for value in ("True", "1", "yes", "", " true "):
            with self.subTest(value=value):
                self.assertFalse(
                    hypothesis_engine_enabled({HYPOTHESIS_ENABLED_VARIABLE: value})
                )
                self.assertFalse(
                    failure_memory_enabled({FAILURE_MEMORY_ENABLED_VARIABLE: value})
                )
        self.assertFalse(hypothesis_engine_enabled({}))
        self.assertFalse(failure_memory_enabled({}))

    def test_the_two_surfaces_are_independent(self) -> None:
        environment = {HYPOTHESIS_ENABLED_VARIABLE: "true"}

        self.assertTrue(hypothesis_engine_enabled(environment))
        self.assertFalse(failure_memory_enabled(environment))


class HypothesisRetractionConfirmationTests(unittest.TestCase):
    """A canonical correction is confirmed, exactly as other mutations are."""

    def _window(self, evidence: str = "evidence-1"):
        window: Any = object.__new__(TkinterDesktopWindow)
        window._root = object()
        window._controller = SimpleNamespace(
            retract_hypothesis_evidence_relation=lambda *args: self.calls.append(args)
        )
        window._hypothesis_id = SimpleNamespace(get=lambda: "hypothesis-1")
        window._hypothesis_evidence_ids = SimpleNamespace(get=lambda: evidence)
        window._hypothesis_relation = SimpleNamespace(get=lambda: "supports")
        window._learning_status = SimpleNamespace(
            set=lambda value: self.statuses.append(value)
        )
        window._learning_request = lambda call: call()
        return window

    def setUp(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.statuses: list[str] = []

    def test_declining_records_nothing(self) -> None:
        window = self._window()

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ) as confirm:
            window._retract_hypothesis_relation()

        confirm.assert_called_once()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.statuses, ["hypothesis relation: not retracted"])

    def test_confirming_records_exactly_one_retraction(self) -> None:
        window = self._window()

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            window._retract_hypothesis_relation()

        self.assertEqual(self.calls, [("hypothesis-1", "evidence-1", "supports")])

    def test_the_dialog_names_what_will_be_taken_back(self) -> None:
        window = self._window()

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ) as confirm:
            window._retract_hypothesis_relation()

        message = confirm.call_args[0][1]
        for expected in ("hypothesis-1", "evidence-1", "supports", "RETRACT"):
            with self.subTest(expected=expected):
                self.assertIn(expected, message)

    def test_several_evidence_ids_are_refused_before_confirming(self) -> None:
        """A retraction is about one statement, not a field-full of them."""
        window = self._window(evidence="evidence-1, evidence-2")

        with patch("desktop.TkinterDesktopWindow.messagebox.askyesno") as confirm:
            window._retract_hypothesis_relation()

        confirm.assert_not_called()
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
