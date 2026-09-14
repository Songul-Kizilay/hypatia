"""The Simple mode workflow, driven through the real window handlers.

These build bare windows and stub only the Tk edges — the status line, the
background request runner, the confirmation dialog. Everything between is the
code that ships: the same controller methods the Advanced tab calls, the same
preview, the same guarded loader.

The point of testing at this level rather than through the read model alone is
that the read model cannot lie about which service was called. Half of what
Simple mode promises is about routing — that a card reaches the canonical
loader, that a run is not inherited from somewhere else, that chat text does not
become an action — and routing is only observable from here.

Nothing here touches a network. The controller is a double, so discovery and
fetching return fixtures rather than reaching Crossref or any website.
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainResponse import BrainResponse
from cognition.LiveInformationRequestKind import LiveInformationRequestKind
from desktop.SimpleResearchActivity import SimpleResearchActivity
from desktop.SimpleResearchPhrasebook import phrase, stage_phrase
from desktop.SimpleResearchStep import SimpleResearchStep
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceCandidateAcceptancePreview import (
    ResearchSourceCandidateAcceptancePreview,
)
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRecord import ResearchSourceRecord
from research.SourceLoadStage import SourceLoadStage
from response.ResponseLanguage import ResponseLanguage

NOW = datetime(2026, 8, 24, 10, tzinfo=UTC)
URL = "https://portswigger.net/web-security"
EN = ResponseLanguage.ENGLISH


class RecordingVariable:
    """Stand in for a Tk StringVar without a Tk interpreter."""

    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class RecordingStatus(RecordingVariable):
    def __init__(self) -> None:
        super().__init__("")
        self.values: list[str] = []

    def set(self, value: str) -> None:
        super().set(value)
        self.values.append(value)


def _window(controller: Any) -> Any:
    """Build a bare window wired to a controller double and nothing else."""
    window: Any = object.__new__(TkinterDesktopWindow)
    window._root = object()
    window._controller = controller
    window._status = RecordingStatus()
    window._simple_question = RecordingVariable()
    window._simple_run_id = ""
    window._simple_run = None
    window._simple_discovery_id = ""
    window._simple_cards = ()
    window._simple_activity = SimpleResearchActivity.IDLE
    window._simple_last_stage = None
    window._simple_language = EN
    window._append_response = Mock()
    window.started: list[tuple[str, Any]] = []

    def start_request(action, on_success, label, **_kwargs):
        window.started.append((label, action))
        window.pending = (action, on_success)

    window._start_request = start_request
    return window


def _drain(window: Any, response: BrainResponse) -> None:
    """Run the captured background action's completion handler."""
    _, on_success = window.pending
    on_success(response)


class SimpleRunContextTests(unittest.TestCase):
    """The panel keeps its own run, and never borrows one."""

    def test_starting_research_creates_a_run_and_keeps_it(self) -> None:
        controller = Mock()
        controller.create_research_run.return_value = _response(runs=[_run()])
        window = _window(controller)
        window._simple_question.set("What are current web security practices?")

        window._simple_start_research()

        controller.create_research_run.assert_called_once_with(
            "What are current web security practices?"
        )
        self.assertEqual(window._simple_run_id, "run-1")
        self.assertEqual(window._simple_run.run_id, "run-1")

    def test_starting_research_never_asks_the_user_to_select_a_run(self) -> None:
        """The whole 'No research run selected' dead end is what this removes."""
        controller = Mock()
        controller.create_research_run.return_value = _response(runs=[_run()])
        window = _window(controller)
        window._simple_question.set("A question")

        window._simple_start_research()

        self.assertNotIn(
            "no research run selected",
            " ".join(window._status.values).casefold(),
        )

    def test_starting_research_immediately_looks_for_sources(self) -> None:
        controller = Mock()
        controller.create_research_run.return_value = _response(runs=[_run()])
        window = _window(controller)
        window._simple_question.set("A question")

        window._simple_start_research()

        self.assertEqual(
            [label for label, _ in window.started],
            ["simple research discovery"],
        )

    def test_an_empty_question_starts_nothing(self) -> None:
        controller = Mock()
        window = _window(controller)
        window._simple_question.set("   ")

        window._simple_start_research()

        controller.create_research_run.assert_not_called()
        self.assertEqual(window.started, [])
        self.assertEqual(window._status.values, [phrase("question_required", EN)])

    def test_a_failed_creation_leaves_no_run_context(self) -> None:
        controller = Mock()
        controller.create_research_run.return_value = _response(success=False)
        window = _window(controller)
        window._simple_question.set("A question")

        window._simple_start_research()

        self.assertEqual(window._simple_run_id, "")
        self.assertEqual(window.started, [])

    def test_an_unrelated_run_never_becomes_the_context(self) -> None:
        """A response carrying other runs must not move the panel onto one."""
        window = _window(Mock())
        window._simple_run_id = "run-1"

        window._simple_adopt_canonical(_response(runs=[_run(run_id="run-other")]))

        self.assertIsNone(window._simple_run)

    def test_the_language_follows_the_question(self) -> None:
        controller = Mock()
        controller.create_research_run.return_value = _response(runs=[_run()])
        window = _window(controller)
        window._simple_question.set("Güncel siber güvenlik haberlerini araştır")

        window._simple_start_research()

        self.assertIs(window._simple_language, ResponseLanguage.TURKISH)


class SimpleDiscoveryTests(unittest.TestCase):
    def test_discovery_calls_the_existing_canonical_service(self) -> None:
        controller = Mock()
        window = _window(controller)
        window._simple_run_id = "run-1"

        window._simple_find_sources()

        _, action = window.started[0]
        action()
        controller.discover_research_sources.assert_called_once()
        self.assertEqual(
            controller.discover_research_sources.call_args.args[0],
            "run-1",
        )

    def test_discovery_in_flight_is_an_activity_not_a_step(self) -> None:
        window = _window(Mock())
        window._simple_run_id = "run-1"

        window._simple_find_sources()

        self.assertIs(window._simple_activity, SimpleResearchActivity.FINDING_SOURCES)
        self.assertIs(
            SimpleResearchStep.for_run(window._simple_run),
            SimpleResearchStep.NOT_STARTED,
        )

    def test_completed_discovery_adopts_the_canonical_discovery_id(self) -> None:
        window = _window(Mock())
        window._simple_run_id = "run-1"
        window._simple_find_sources()

        _drain(window, _response(runs=[_run(discoveries=(_discovery(),))]))

        self.assertEqual(window._simple_discovery_id, "discovery-1")
        self.assertIs(window._simple_activity, SimpleResearchActivity.IDLE)

    def test_the_cards_come_from_canonical_state(self) -> None:
        window = _window(Mock())
        window._simple_run_id = "run-1"
        window._simple_find_sources()
        _drain(window, _response(runs=[_run(discoveries=(_discovery(),))]))

        cards = window._simple_model().candidate_cards()
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].site, "portswigger.net")


class SimpleUseSourceTests(unittest.TestCase):
    """One button for the user; every boundary still underneath it."""

    def _prepared(self, controller: Any) -> Any:
        window = _window(controller)
        window._simple_run_id = "run-1"
        window._simple_find_sources()
        _drain(window, _response(runs=[_run(discoveries=(_discovery(),))]))
        window._simple_cards = window._simple_model().candidate_cards()
        window.started.clear()
        return window

    def test_using_a_source_needs_no_manual_url_copy(self) -> None:
        """The card carries the canonical URL through the typed workflow."""
        controller = _accepting_controller()
        window = self._prepared(controller)

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=True,
        ):
            window._simple_use_source(0)

        preview_args = (
            controller.preview_research_source_candidate_acceptance.call_args.args
        )
        self.assertEqual(preview_args, ("run-1", "discovery-1", URL))

    def test_using_a_source_previews_before_confirming(self) -> None:
        controller = _accepting_controller()
        window = self._prepared(controller)

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=True,
        ) as confirm:
            window._simple_use_source(0)

        controller.preview_research_source_candidate_acceptance.assert_called_once()
        confirm.assert_called_once()

    def test_a_refused_preview_never_reaches_a_confirmation(self) -> None:
        controller = _accepting_controller(allowed=False)
        window = self._prepared(controller)

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
        ) as confirm:
            window._simple_use_source(0)

        confirm.assert_not_called()
        self.assertEqual(window.started, [])

    def test_declining_the_confirmation_fetches_nothing(self) -> None:
        """The security confirmation is shown, not bypassed for convenience."""
        controller = _accepting_controller()
        window = self._prepared(controller)

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=False,
        ):
            window._simple_use_source(0)

        controller.accept_research_source_candidate.assert_not_called()
        self.assertEqual(window.started, [])
        self.assertEqual(window._status.values[-1], phrase("cancelled_by_user", EN))

    def test_confirming_routes_through_the_canonical_acceptance_service(self) -> None:
        controller = _accepting_controller()
        window = self._prepared(controller)

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=True,
        ):
            window._simple_use_source(0)
        _, action = window.started[0]
        action()

        controller.accept_research_source_candidate.assert_called_once()
        self.assertEqual(
            controller.accept_research_source_candidate.call_args.args,
            ("run-1", "discovery-1", URL),
        )

    def test_using_a_source_without_a_discovery_does_nothing(self) -> None:
        controller = _accepting_controller()
        window = self._prepared(controller)
        window._simple_discovery_id = ""

        window._simple_use_source(0)

        controller.preview_research_source_candidate_acceptance.assert_not_called()

    def test_an_out_of_range_card_does_nothing(self) -> None:
        controller = _accepting_controller()
        window = self._prepared(controller)

        window._simple_use_source(7)

        controller.preview_research_source_candidate_acceptance.assert_not_called()
        self.assertEqual(window._status.values[-1], phrase("select_source_first", EN))

    def test_each_card_button_acts_on_its_own_source(self) -> None:
        """A closure over the loop variable would load the last card every time."""
        window = _window(Mock())
        captured: list[int] = []
        window._simple_use_source = captured.append

        commands = [window._simple_card_command(index) for index in range(3)]
        for command in commands:
            command()

        self.assertEqual(captured, [0, 1, 2])


class SimpleCanonicalRefreshTests(unittest.TestCase):
    """Success is read back from the store, never inferred from a return value."""

    def _loaded(self, stage: SourceLoadStage, canonical_run: ResearchRun) -> Any:
        controller = _accepting_controller()
        controller.list_research_runs.return_value = _response(runs=[canonical_run])
        window = _window(controller)
        window._simple_run_id = "run-1"
        window._complete_simple_source_load(_response(runs=[], stage=stage))
        return window, controller

    def test_a_completed_load_re_reads_the_persisted_run(self) -> None:
        accepted = _run(discoveries=(_discovery(),), sources=(_source(url=URL),))
        window, controller = self._loaded(
            SourceLoadStage.ACCEPTED_INTO_RUN,
            accepted,
        )

        controller.list_research_runs.assert_called_once()
        self.assertEqual(window._simple_run.run_id, "run-1")
        self.assertEqual(len(window._simple_run.sources), 1)

    def test_an_accepted_source_shows_as_accepted_after_refresh(self) -> None:
        accepted = _run(discoveries=(_discovery(),), sources=(_source(url=URL),))
        window, _ = self._loaded(SourceLoadStage.ACCEPTED_INTO_RUN, accepted)

        card = window._simple_model().candidate_cards()[0]
        self.assertTrue(card.accepted)
        self.assertEqual(card.status_text, phrase("candidate_accepted", EN))

    def test_an_indexed_only_source_is_not_shown_as_accepted(self) -> None:
        """A local document exists. The run did not take it. Both are said."""
        untouched = _run(discoveries=(_discovery(),))
        window, _ = self._loaded(SourceLoadStage.INDEXED_WITHOUT_RUN, untouched)

        card = window._simple_model().candidate_cards()[0]
        self.assertFalse(card.accepted)
        self.assertEqual(card.status_text, phrase("candidate_discovered", EN))

    def test_an_indexed_only_load_is_never_described_as_loaded(self) -> None:
        untouched = _run(discoveries=(_discovery(),))
        window, _ = self._loaded(SourceLoadStage.INDEXED_WITHOUT_RUN, untouched)

        text = window._simple_model().stage_text()
        self.assertIn("not added to this research", text)
        self.assertNotIn("loaded", text.casefold())

    def test_an_indexed_only_load_does_not_advance_the_ladder(self) -> None:
        untouched = _run(discoveries=(_discovery(),))
        window, _ = self._loaded(SourceLoadStage.INDEXED_WITHOUT_RUN, untouched)

        reached = dict(window._simple_model().ladder())
        self.assertFalse(reached[phrase("step_source_accepted", EN)])

    def test_a_failed_attach_renders_deterministic_plain_text(self) -> None:
        untouched = _run(discoveries=(_discovery(),))
        window, _ = self._loaded(SourceLoadStage.RUN_ATTACH_FAILED, untouched)

        self.assertEqual(
            window._simple_model().stage_text(),
            stage_phrase(SourceLoadStage.RUN_ATTACH_FAILED, EN),
        )

    def test_a_refused_fetch_explains_the_safety_rule(self) -> None:
        untouched = _run(discoveries=(_discovery(),))
        window, _ = self._loaded(SourceLoadStage.FETCH_REFUSED, untouched)

        self.assertIn("network safety rules", window._simple_model().stage_text())

    def test_the_technical_code_is_moved_not_hidden(self) -> None:
        untouched = _run(discoveries=(_discovery(),))
        window, _ = self._loaded(SourceLoadStage.RUN_ATTACH_FAILED, untouched)

        details = window._simple_model().advanced_details()
        self.assertIn(("Technical code", "run_attach_failed"), details)

    def test_an_accepted_source_is_still_not_evidence(self) -> None:
        accepted = _run(sources=(_source(url=URL),))
        window, _ = self._loaded(SourceLoadStage.ACCEPTED_INTO_RUN, accepted)

        self.assertEqual(
            window._simple_model().evidence_text(),
            phrase("evidence_none", EN),
        )

    def test_refresh_without_a_run_asks_the_store_for_nothing(self) -> None:
        controller = Mock()
        window = _window(controller)

        window._simple_refresh_canonical()

        controller.list_research_runs.assert_not_called()


class SimpleIdentifierVisibilityTests(unittest.TestCase):
    def test_identifiers_are_hidden_from_the_simple_surface(self) -> None:
        window = _window(Mock())
        window._simple_run_id = "run-1"
        window._simple_adopt_canonical(
            _response(runs=[_run(discoveries=(_discovery(),), sources=(_source(),))])
        )

        self.assertTrue(window._simple_model().hides_identifiers())

    def test_advanced_details_expose_them_unchanged(self) -> None:
        window = _window(Mock())
        window._simple_run_id = "run-1"
        window._simple_adopt_canonical(
            _response(runs=[_run(discoveries=(_discovery(),), sources=(_source(),))])
        )

        values = [value for _, value in window._simple_model().advanced_details()]
        self.assertIn("run-1", values)
        self.assertIn("discovery-1", values)
        self.assertIn("document-1", values)


class ChatHandoffTests(unittest.TestCase):
    """Chat may offer research. It may not perform it."""

    def test_the_handoff_creates_nothing(self) -> None:
        controller = Mock()
        window = _window(controller)

        window._offer_simple_research_handoff("Find today's security news")

        controller.create_research_run.assert_not_called()
        controller.discover_research_sources.assert_not_called()
        controller.load_research_source.assert_not_called()
        self.assertEqual(window.started, [])

    def test_the_handoff_only_drafts_the_question(self) -> None:
        window = _window(Mock())

        window._offer_simple_research_handoff("  Find today's security news  ")

        self.assertEqual(
            window._simple_question.get(),
            "Find today's security news",
        )
        self.assertEqual(window._simple_run_id, "")

    def test_the_handoff_carries_the_question_language(self) -> None:
        window = _window(Mock())

        window._offer_simple_research_handoff(
            "Bugün yayımlanan siber güvenlik haberlerini bul"
        )

        self.assertIs(window._simple_language, ResponseLanguage.TURKISH)

    def test_chat_text_alone_never_reaches_the_network(self) -> None:
        """Natural language is a draft, not authority to run anything."""
        controller = Mock()
        window = _window(controller)

        window._offer_simple_research_handoff("Load https://example.com now")

        controller.assert_not_called()
        self.assertEqual(window.started, [])


class ResearchThisOfferTests(unittest.TestCase):
    """Chat may notice research was wanted. It still may not perform it."""

    def _window_with_offer(self, kind: LiveInformationRequestKind | None) -> Any:
        window = _window(Mock())
        window._pending_research_question = ""
        window._offer_research_this("Find today's security news", _response(kind=kind))
        return window

    def test_an_unresearched_question_becomes_offerable(self) -> None:
        window = self._window_with_offer(LiveInformationRequestKind.CURRENT_EVENTS)

        self.assertEqual(
            window._pending_research_question,
            "Find today's security news",
        )

    def test_an_ordinary_answer_offers_nothing(self) -> None:
        window = self._window_with_offer(LiveInformationRequestKind.NONE)

        self.assertEqual(window._pending_research_question, "")

    def test_no_detected_request_offers_nothing(self) -> None:
        window = self._window_with_offer(None)

        self.assertEqual(window._pending_research_question, "")

    def test_offering_starts_no_request(self) -> None:
        """Noticing is not acting. Nothing is created and nothing is fetched."""
        window = self._window_with_offer(LiveInformationRequestKind.CURRENT_EVENTS)

        window._controller.assert_not_called()
        self.assertEqual(window.started, [])

    def test_pressing_it_only_drafts_the_question(self) -> None:
        window = self._window_with_offer(LiveInformationRequestKind.CURRENT_EVENTS)

        window._research_this()

        self.assertEqual(
            window._simple_question.get(),
            "Find today's security news",
        )
        self.assertEqual(window._simple_run_id, "")
        window._controller.create_research_run.assert_not_called()

    def test_pressing_it_with_nothing_pending_does_nothing(self) -> None:
        window = self._window_with_offer(LiveInformationRequestKind.NONE)

        window._research_this()

        self.assertEqual(window._simple_question.get(), "")


class AdvancedModePreservedTests(unittest.TestCase):
    """Complexity moved out of the default path; nothing was removed."""

    def test_the_advanced_candidate_workflow_still_exists(self) -> None:
        for name in (
            "_discover_research_sources",
            "_use_selected_research_candidate",
            "_preview_and_accept_research_candidate",
            "_render_research_candidates",
        ):
            with self.subTest(method=name):
                self.assertTrue(hasattr(TkinterDesktopWindow, name))

    def test_the_advanced_run_selector_is_untouched_by_simple_mode(self) -> None:
        """Separate fields, so a click in one cannot redirect the other."""
        window = _window(Mock())
        window._research_run_id = RecordingVariable("run-advanced")
        window._simple_run_id = "run-1"
        window._simple_adopt_canonical(_response(runs=[_run()]))

        self.assertEqual(window._research_run_id.get(), "run-advanced")

    def test_advanced_analysis_controls_remain(self) -> None:
        for name in (
            "_preview_research_source_assessment",
            "_preview_research_claims",
            "_preview_research_claim_contradictions",
            "_show_research_runs",
        ):
            with self.subTest(method=name):
                self.assertTrue(hasattr(TkinterDesktopWindow, name))

    def test_simple_mode_adds_no_second_load_path(self) -> None:
        """It calls the same controller methods, not new ones."""
        controller_methods = {
            "create_research_run",
            "discover_research_sources",
            "preview_research_source_candidate_acceptance",
            "accept_research_source_candidate",
            "list_research_runs",
        }
        from desktop.DesktopController import DesktopController

        for name in controller_methods:
            with self.subTest(method=name):
                self.assertTrue(hasattr(DesktopController, name))


def _response(
    *,
    success: bool = True,
    runs: list[ResearchRun] | None = None,
    stage: SourceLoadStage | None = None,
    preview: ResearchSourceCandidateAcceptancePreview | None = None,
    kind: LiveInformationRequestKind | None = None,
) -> BrainResponse:
    return BrainResponse(
        message="",
        request_id="request-1",
        intent="research",
        memory_count=0,
        success=success,
        research_runs=list(runs or []),
        source_load_stage=stage,
        research_source_candidate_acceptance_preview=preview,
        live_information_request=kind,
    )


def _accepting_controller(*, allowed: bool = True) -> Any:
    controller = Mock()
    controller.preview_research_source_candidate_acceptance.return_value = _response(
        preview=ResearchSourceCandidateAcceptancePreview(
            run_id="run-1",
            discovery_id="discovery-1",
            candidate=_candidate(),
            allowed=allowed,
            reason="Allowed." if allowed else "Refused by policy.",
        )
    )
    controller.accept_research_source_candidate.return_value = _response()
    controller.list_research_runs.return_value = _response(runs=[_run()])
    return controller


def _candidate(url: str = URL) -> ResearchSourceCandidate:
    return ResearchSourceCandidate(
        url,
        "Modern web application security in practice",
        "A bounded snippet.",
    )


def _discovery(
    discovery_id: str = "discovery-1",
) -> ResearchSourceDiscoveryRecord:
    return ResearchSourceDiscoveryRecord(
        discovery_id,
        "web application security",
        "test-provider",
        (_candidate(),),
        NOW,
    )


def _source(
    document_id: str = "document-1",
    url: str = "https://example.com/paper",
) -> ResearchSourceRecord:
    return ResearchSourceRecord(
        document_id,
        url,
        "Accepted source title",
        "text/html",
        NOW,
        NOW + timedelta(minutes=1),
    )


def _run(
    run_id: str = "run-1",
    *,
    sources: tuple[ResearchSourceRecord, ...] = (),
    discoveries: tuple[ResearchSourceDiscoveryRecord, ...] = (),
) -> ResearchRun:
    return ResearchRun(
        run_id,
        "What are the current web application security practices?",
        ResearchRunStatus.COLLECTING,
        sources,
        (),
        NOW,
        NOW,
        discoveries=discoveries,
    )


if __name__ == "__main__":
    unittest.main()
