"""The button an operator presses must call the handler the architecture means.

Every research handler in this window is already tested by calling it. That
leaves exactly one thing unproven, and it is the thing a person actually does:
press a control. A button wired to the wrong method — a renamed handler still
referenced, two controls sharing one command, an acceptance button pointed at
the generic loader — would leave every one of those handler tests green while
the desktop did something else entirely.

So this drives Hypatia's real construction code. The window is built by its own
`__init__` and `_build_layout`, with the tkinter widget classes replaced by
recorders that capture what the production builder asks to bind. Nothing here
constructs a button itself; a test that did would only be checking its own
fixture.

The binding that matters most is Preview & load. It is the control standing
between a discovered candidate and a network fetch of it, and its handler is the
one that previews, asks, and only then accepts. Bound to the generic loader
beside it, the same button would still load something — just without the
confirmation, and without the candidate ever being revalidated against the
discovery that returned it. That is why it is asserted by identity here rather
than by behaviour somewhere else.
"""

from __future__ import annotations

import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from tests.desktop.test_paired_research_journey import (
    DETAIL_URL,
    DOI_URL,
    PairedJourneyFixture,
)


class RecordingWidget:
    """Accept anything Tk accepts and remember only what a binding needs.

    Deliberately permissive. The point is to let the real builder run to
    completion unchanged, not to model Tk — so unknown attributes answer with a
    callable that returns another recorder, and the widget tree simply forms
    itself as the production code lays it out.
    """

    instances: list[RecordingWidget] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.parent = args[0] if args else None
        self.text = kwargs.get("text", "")
        self.command = kwargs.get("command")
        self.textvariable = kwargs.get("textvariable")
        self.kwargs = kwargs
        RecordingWidget.instances.append(self)

    def __getattr__(self, name: str) -> Any:
        # Dunders must genuinely be absent. Answering them turns the recorder
        # into something iterable and sized, and the builder's own recursive
        # walk over `winfo_children` then never reaches the bottom.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        def call(*args: Any, **kwargs: Any) -> None:
            return None

        return call

    def winfo_children(self) -> list[Any]:
        return []

    def configure(self, *args: Any, **kwargs: Any) -> None:
        # Real code may rebind a command after construction; if it ever does,
        # this keeps the recorded binding the effective one rather than the
        # first one.
        if "command" in kwargs:
            self.command = kwargs["command"]
        self.kwargs.update(kwargs)

    def __setitem__(self, key: str, value: Any) -> None:
        self.configure(**{key: value})

    def __getitem__(self, key: str) -> Any:
        return self.kwargs.get(key)


class RecordingVariable:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._value = kwargs.get("value", "")

    def get(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        self._value = value

    def trace_add(self, *args: Any, **kwargs: Any) -> str:
        return "trace"


class RecordingStyle(RecordingWidget):
    """A theme engine that answers the two questions the window asks it."""

    def theme_names(self) -> tuple[str, ...]:
        return ("clam", "default")

    def lookup(self, *args: Any, **kwargs: Any) -> str:
        return ""


class RecordingRoot(RecordingWidget):
    """A root that answers the few questions the window asks about the screen."""

    def winfo_screenwidth(self) -> int:
        return 1920

    def winfo_screenheight(self) -> int:
        return 1080

    def winfo_children(self) -> list[Any]:
        return []


class RecordingFont:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._configuration: dict[str, Any] = {"size": 10, "family": "TkDefaultFont"}

    def copy(self) -> RecordingFont:
        return RecordingFont()

    def configure(self, **kwargs: Any) -> None:
        self._configuration.update(kwargs)

    def cget(self, key: str) -> Any:
        return self._configuration.get(key, "")

    def actual(self, *args: Any, **kwargs: Any) -> Any:
        return self._configuration


def build_real_window(**features: bool) -> tuple[Any, list[RecordingWidget]]:
    """Run Hypatia's own construction with recorder widgets in place of Tk.

    Feature flags are passed through because several panels are built only
    when their capability is enabled; a window built with the defaults simply
    does not contain those controls, and asserting against it would prove
    nothing about them.
    """
    RecordingWidget.instances = []
    module = "desktop.TkinterDesktopWindow"
    widget_names = (
        "ttk.Frame",
        "ttk.LabelFrame",
        "ttk.Notebook",
        "ttk.Button",
        "ttk.Label",
        "ttk.Entry",
        "ttk.Combobox",
        "ttk.Radiobutton",
        "ttk.Checkbutton",
        "ttk.Scrollbar",
        "ttk.Separator",
        "ttk.Progressbar",
        "tk.Text",
        "tk.Listbox",
        "tk.Canvas",
        "tk.Menu",
    )
    variable_names = ("tk.StringVar", "tk.BooleanVar", "tk.IntVar")
    with ExitStack() as stack:
        for name in widget_names:
            stack.enter_context(patch(f"{module}.{name}", RecordingWidget))
        for name in variable_names:
            stack.enter_context(patch(f"{module}.{name}", RecordingVariable))
        stack.enter_context(
            patch(f"{module}.font.nametofont", lambda *a, **k: RecordingFont())
        )
        stack.enter_context(patch(f"{module}.ttk.Style", RecordingStyle))
        stack.enter_context(
            patch(f"{module}.scrolledtext.ScrolledText", RecordingWidget)
        )
        stack.enter_context(patch(f"{module}.font.Font", RecordingFont))
        window = TkinterDesktopWindow(object(), root=RecordingRoot(), **features)
    return window, list(RecordingWidget.instances)


class ResearchCommandBindingTests(unittest.TestCase):
    """Each labelled control resolves to the handler the journey depends on."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.window, cls.widgets = build_real_window()

    #: Labels that legitimately appear more than once, each on its own panel.
    #: The simple Research tab and Research (Advanced) offer the same two
    #: gestures against different handlers, and three panels each contribute a
    #: different kind of record to a comparison. Sharing a label is fine;
    #: sharing a handler would not be, which the aliasing test below checks.
    DUPLICATED_LABELS = {
        "Find sources": 2,
        "Start research": 2,
        "Add to comparison": 3,
        "Use selected pair": 2,
    }

    def _controls(self, label: str) -> list[RecordingWidget]:
        matches = [
            widget
            for widget in self.widgets
            if widget.text == label and widget.command is not None
        ]
        self.assertEqual(
            len(matches),
            self.DUPLICATED_LABELS.get(label, 1),
            f"unexpected number of command controls named {label!r}",
        )
        return matches

    def _handlers_for(self, label: str) -> list[Any]:
        return [
            getattr(widget.command, "__func__", None)
            for widget in self._controls(label)
        ]

    def _assert_bound(self, label: str, handler_name: str) -> None:
        """Exactly one control with this label calls exactly this handler."""
        expected = getattr(type(self.window), handler_name)
        handlers = self._handlers_for(label)
        self.assertEqual(
            handlers.count(expected),
            1,
            f"{label!r} resolves to "
            f"{[getattr(handler, '__name__', handler) for handler in handlers]}, "
            f"which does not name {handler_name!r} exactly once",
        )
        [widget] = [
            widget
            for widget in self._controls(label)
            if getattr(widget.command, "__func__", None) is expected
        ]
        self.assertIs(getattr(widget.command, "__self__", None), self.window)

    def test_the_real_builder_produced_command_controls(self) -> None:
        """Guards the harness: an empty widget list would pass every test below."""
        commanded = [widget for widget in self.widgets if widget.command is not None]

        self.assertGreater(len(commanded), 20)
        self.assertIn("Preview & load", [widget.text for widget in commanded])

    def test_preview_and_load_is_bound_to_the_confirming_handler(self) -> None:
        """The safety boundary: candidate, then preview, then a person, then load.

        Bound to `_load_research_source` instead, this button would fetch the
        URL in the entry box with no preview and no revalidation of the
        candidate against the discovery that produced it.
        """
        self._assert_bound("Preview & load", "_preview_and_accept_research_candidate")

    def test_preview_and_load_is_not_bound_to_any_bypassing_handler(self) -> None:
        [control] = self._controls("Preview & load")
        command = control.command

        for bypass in (
            "_load_research_source",
            "_discover_research_sources",
            "_use_selected_research_candidate",
        ):
            with self.subTest(handler=bypass):
                self.assertIsNot(
                    getattr(command, "__func__", None),
                    getattr(type(self.window), bypass),
                )

    def test_the_discovery_control_is_bound_to_the_discovery_handler(self) -> None:
        self._assert_bound("Find sources", "_discover_research_sources")

    def test_using_a_candidate_url_is_bound_to_the_copy_handler(self) -> None:
        self._assert_bound("Use selected URL", "_use_selected_research_candidate")

    def test_the_manual_url_control_is_bound_to_the_manual_loader(self) -> None:
        """A separate control for a URL a person typed, and separately bound."""
        self._assert_bound("Load source", "_load_research_source")

    def test_the_assessment_target_control_is_bound_to_its_handler(self) -> None:
        self._assert_bound(
            "Use for assessment", "_use_selected_research_source_for_assessment"
        )

    def test_the_evidence_controls_are_bound_to_their_own_handlers(self) -> None:
        self._assert_bound("View evidence", "_show_research_evidence")
        self._assert_bound("Save evidence", "_record_research_evidence")

    def test_the_assessment_and_claim_controls_are_bound_separately(self) -> None:
        self._assert_bound("Preview assessment", "_preview_research_source_assessment")
        self._assert_bound(
            "Preview & save assessment",
            "_preview_and_record_research_source_assessment",
        )
        self._assert_bound("Preview & save claim", "_preview_and_record_research_claim")

    def _hypothesis_control(self, label: str) -> RecordingWidget:
        _window, widgets = build_real_window(hypothesis_enabled=True)
        [control] = [
            widget
            for widget in widgets
            if widget.text == label and widget.command is not None
        ]
        return control

    def test_the_hypothesis_controls_are_bound_separately(self) -> None:
        """Addressing the test is its own statement, so it is its own control.

        Bound to Support or Oppose, the button would file an observation about
        the discriminating test as a mere position on the hypothesis, and the
        distinction the association exists for would vanish at the one place a
        person actually uses it.
        """
        expected = {
            "Support": "_support_hypothesis",
            "Oppose": "_oppose_hypothesis",
            "Addresses test": "_associate_hypothesis_test_evidence",
            "Retract relation": "_retract_hypothesis_relation",
            "View history": "_view_hypothesis_history",
            "Withdraw": "_withdraw_hypothesis",
        }

        bound = {
            label: getattr(self._hypothesis_control(label).command, "__name__", "")
            for label in expected
        }

        self.assertEqual(bound, expected)
        self.assertEqual(len(set(bound.values())), len(expected))

    def test_the_curiosity_proposal_control_is_bound_and_stands_alone(self) -> None:
        """Preparing a proposal is its own decision, so it is its own control.

        Bound to the accept handler it would collapse two operator decisions
        into one, which is the distinction this capability exists to keep.
        """
        _window, widgets = build_real_window(curiosity_enabled=True)
        by_label = {
            widget.text: getattr(widget.command, "__name__", "")
            for widget in widgets
            if widget.command is not None
        }

        self.assertEqual(
            by_label.get("Prepare research proposal"),
            "_prepare_curiosity_research_proposal",
        )
        self.assertEqual(by_label.get("Worth pursuing"), "_accept_curiosity_question")
        # Scoped to proposal actions. "Start research" is a pre-existing control
        # that creates a research run and has nothing to do with proposals; what
        # this milestone must not add is a way to approve or run one.
        proposal_handlers = {
            handler
            for label, handler in by_label.items()
            if "proposal" in label.casefold()
        }
        self.assertEqual(
            proposal_handlers,
            {
                "_prepare_curiosity_research_proposal",
                "_authorize_curiosity_research_proposal",
                "_start_authorized_curiosity_research_proposal",
            },
        )
        # Starting is now explicit, but it must not be collapsed with the
        # separate step-execution boundary.
        self.assertNotIn(
            "advance",
            " ".join(proposal_handlers).casefold(),
        )
        self.assertEqual(
            by_label.get("Authorize this proposal"),
            "_authorize_curiosity_research_proposal",
        )
        self.assertEqual(
            by_label.get("Start authorized proposal"),
            "_start_authorized_curiosity_research_proposal",
        )

    def test_the_resume_control_is_its_own_explicit_handler(self) -> None:
        """Recovering an execution is a separate press from running a step.

        Bound to advancing, one press would recover *and* perform work, which
        is the automatic resume this milestone exists to not have.
        """
        _window, widgets = build_real_window(
            curiosity_enabled=True,
            plan_authorization_enabled=True,
        )
        by_label = {
            widget.text: getattr(widget.command, "__name__", "")
            for widget in widgets
            if widget.command is not None
        }

        self.assertEqual(by_label.get("Resume after restart"), "_resume_execution")
        self.assertEqual(
            by_label.get("Advance one step"),
            "_advance_execution_one_step",
        )
        self.assertNotEqual(
            by_label.get("Resume after restart"),
            by_label.get("Advance one step"),
        )

    def test_no_control_resumes_the_latest_execution(self) -> None:
        """There is one resume control, and it resumes what was named."""
        _window, widgets = build_real_window(
            curiosity_enabled=True,
            plan_authorization_enabled=True,
        )
        labels = [
            widget.text.casefold()
            for widget in widgets
            if widget.command is not None and isinstance(widget.text, str)
        ]

        resuming = [label for label in labels if "resume" in label]

        self.assertEqual(resuming, ["resume after restart"])

    def test_the_interrupted_panel_states_what_is_not_known(self) -> None:
        """The operator is told the four facts before being asked to rule."""
        from desktop.TkinterDesktopWindow import _INTERRUPTED_PANEL_NOTE

        note = _INTERRUPTED_PANEL_NOTE.casefold()

        self.assertIn("interrupted", note)
        self.assertIn("may have occurred", note)
        self.assertIn("result is unknown", note)
        self.assertIn("already been charged", note)
        self.assertIn("retries nothing", note)

    def test_the_ruling_control_is_bound_to_its_own_handler(self) -> None:
        _window, widgets = build_real_window(plan_authorization_enabled=True)
        by_label = {
            widget.text: getattr(widget.command, "__name__", "")
            for widget in widgets
            if widget.command is not None
        }

        self.assertEqual(by_label.get("Record ruling"), "_resolve_interrupted_attempt")

    def test_recording_a_ruling_requires_explicit_confirmation(self) -> None:
        """Declining the dialog records nothing and reaches no controller."""
        window, _widgets = build_real_window(plan_authorization_enabled=True)
        window._execution_id.set("plan-1")
        window._interrupted_step_id.set("step-1")
        requested: list[Any] = []
        window._approval_request = requested.append

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=False,
        ):
            window._resolve_interrupted_attempt()
        self.assertEqual(requested, [])

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=True,
        ):
            window._resolve_interrupted_attempt()
        self.assertEqual(len(requested), 1)

    def test_the_comparison_controls_are_bound_to_their_own_handlers(self) -> None:
        self._assert_bound("Compare sources", "_preview_research_source_comparison")
        self._assert_bound(
            "Compare Crossref + NVD — preview only",
            "_preview_provider_comparison_plan",
        )

    def test_the_paired_comparison_control_only_previews(self) -> None:
        """Its label promises a preview, so it must not reach an executing path."""
        [control] = self._controls("Compare Crossref + NVD — preview only")
        command = control.command

        self.assertIn("preview", getattr(command, "__name__", ""))

    def test_no_two_research_controls_share_one_handler_by_accident(self) -> None:
        """Every command control in the window resolves to its own handler.

        A shared handler is how a renamed method leaves one button silently
        doing another button's work, so this is asserted across every research
        control rather than over a chosen list.

        Scoped to research deliberately. The Appearance tab legitimately points
        three radiobuttons at one apply handler and steps the font size with two
        small lambdas, and neither is this milestone's business to change.
        """
        handlers = [
            getattr(widget.command, "__func__", None)
            for widget in self.widgets
            if widget.command is not None
            and getattr(widget.command, "__func__", None) is not None
            and "research" in getattr(widget.command, "__name__", "")
        ]
        duplicated = {
            getattr(handler, "__name__", handler)
            for handler in handlers
            if handlers.count(handler) > 1
        }

        self.assertGreater(len(handlers), 20)
        self.assertEqual(duplicated, set())

    def test_a_shared_label_never_means_a_shared_handler(self) -> None:
        """The simple tab and the advanced tab must not call each other's code."""
        for label, expected_count in self.DUPLICATED_LABELS.items():
            with self.subTest(label=label):
                handlers = self._handlers_for(label)
                self.assertEqual(len(set(handlers)), expected_count)

    def test_the_simple_tab_keeps_its_own_research_handlers(self) -> None:
        self._assert_bound("Find sources", "_simple_find_sources")
        self._assert_bound("Start research", "_simple_start_research")
        self._assert_bound("Start research", "_create_research_run")


class BindingResolutionTests(unittest.TestCase):
    """Commands must read the selection when pressed, not when they were built."""

    def test_every_research_command_is_a_bound_method_not_a_closure(self) -> None:
        """A lambda built during layout is where a stale run or provider hides.

        Direct bound methods cannot capture a selection, because there is
        nothing to capture: each reads its Tk variables when it runs. This is
        the structural reason the provider, run and source switches below are
        safe, so it is asserted rather than assumed.
        """
        window, widgets = build_real_window()
        research_labels = {
            "Find sources",
            "Use selected URL",
            "Preview & load",
            "Load source",
            "Use for assessment",
            "View evidence",
            "Save evidence",
        }

        for widget in widgets:
            if widget.text in research_labels and widget.command is not None:
                with self.subTest(control=widget.text):
                    self.assertIs(getattr(widget.command, "__self__", None), window)
                    self.assertNotEqual(
                        getattr(widget.command, "__name__", ""), "<lambda>"
                    )


class BoundCommandSelectionTests(PairedJourneyFixture):
    """The function the button carries, run against state that changes.

    The tests above prove which function each control holds; the paired journey
    module proves what that function does. Neither proves the join, and the join
    is the operator's actual question: after switching provider, does pressing
    this button act on what is selected *now*?

    So the command is lifted off the real widget and invoked against the live
    journey window. Nothing is called by name here — if the builder rebinds the
    control, this drives whatever it rebound it to.
    """

    @staticmethod
    def _command_named(label: str, handler_name: str) -> Any:
        """Return the unbound function the real builder put on that control."""
        window, widgets = build_real_window()
        expected = getattr(type(window), handler_name)
        matches = [
            widget.command
            for widget in widgets
            if widget.text == label
            and getattr(widget.command, "__func__", None) is expected
        ]
        assert len(matches) == 1, f"{label!r} did not resolve to {handler_name!r}"
        return matches[0].__func__

    def _press_preview_and_load(self) -> None:
        command = self._command_named(
            "Preview & load", "_preview_and_accept_research_candidate"
        )
        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            command(self.window)
        self.window._poll_requests()

    def test_the_bound_command_loads_the_candidate_selected_when_pressed(
        self,
    ) -> None:
        """Switch Crossref to NVD, then press: the NVD record must be the one."""
        self._discover("crossref")
        self._discover("nvd")

        self._select_candidate(DETAIL_URL)
        self._press_preview_and_load()

        self.assertEqual(self.fetcher.urls, [DETAIL_URL])
        self.assertEqual(
            [source.url for source in self.manager.get(self.run_id).sources],
            [DETAIL_URL],
        )

    def test_switching_back_presses_against_the_other_provider(self) -> None:
        self._discover("crossref")
        self._discover("nvd")
        self._select_candidate(DETAIL_URL)
        self._press_preview_and_load()

        self._select_candidate(DOI_URL)
        self._press_preview_and_load()

        self.assertEqual(self.fetcher.urls, [DETAIL_URL, DOI_URL])
        self.assertEqual(
            sorted(source.url for source in self.manager.get(self.run_id).sources),
            sorted((DETAIL_URL, DOI_URL)),
        )

    def test_the_bound_command_binds_the_candidates_own_discovery(self) -> None:
        """A candidate accepted under the other provider's discovery is refused.

        Pressed after a provider switch, the command must carry the discovery
        that returned the selected candidate rather than the one that happened
        to be selected first.
        """
        self._discover("crossref")
        self._discover("nvd")
        self._select_candidate(DETAIL_URL)

        self._press_preview_and_load()

        run = self.manager.get(self.run_id)
        nvd_discovery = [
            discovery for discovery in run.discoveries if discovery.provider == "nvd"
        ]
        self.assertEqual(len(nvd_discovery), 1)
        self.assertEqual(
            self.manager.preview_candidate_acceptance(
                self.run_id, nvd_discovery[0].discovery_id, DETAIL_URL
            ).discovery_id,
            nvd_discovery[0].discovery_id,
        )

    def test_the_bound_assessment_command_targets_the_source_selected_now(
        self,
    ) -> None:
        command = self._command_named(
            "Use for assessment", "_use_selected_research_source_for_assessment"
        )
        self._discover("crossref")
        self._discover("nvd")
        for url in (DOI_URL, DETAIL_URL):
            self._select_candidate(url)
            self._press_preview_and_load()

        targets = {}
        for url in (DOI_URL, DETAIL_URL):
            index = [
                position
                for position, source in enumerate(self.window._research_sources)
                if source.url == url
            ]
            self.window._research_source_selector.current(index[0])
            command(self.window)
            targets[url] = self.window._research_source_document_id.get()

        for url, document_id in targets.items():
            with self.subTest(url=url):
                [source] = [
                    source
                    for source in self.manager.get(self.run_id).sources
                    if source.url == url
                ]
                self.assertEqual(document_id, source.document_id)
        self.assertNotEqual(targets[DOI_URL], targets[DETAIL_URL])


if __name__ == "__main__":
    unittest.main()
