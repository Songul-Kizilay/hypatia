"""The new provenance-graph widget: read-only, additive, and safely bounded.

Three things matter here that a mocked-controller test alone cannot show:
the tree is really populated from a real `ResearchMissionAuditTraceabilityGraph`
(including an edge the graph itself reports unresolved, which must render as
an explicit leaf rather than crash or vanish), selecting an already-loaded
row never reaches the controller, and a hostile title or URL (an embedded
directional-override control character, or an unbounded length) is bounded
by the same safe-text normalization the rest of this file's mission audit
rendering already relies on -- never a second, weaker path.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from desktop.DesktopController import DesktopController
from desktop.TkinterDesktopWindow import (
    _MAX_TRACEABILITY_TEXT_CHARACTERS,
    TkinterDesktopWindow,
    _populate_mission_audit_traceability_tree,
    _traceability_text,
)
from research.ResearchMissionAuditTraceabilityGraph import traceability_graph_for
from tests.desktop.test_research_command_bindings import build_real_window

#: An embedded right-to-left override, the same family of character the
#: mission audit's own Markdown rendering strips.
_HOSTILE_CONTROL_CHARACTER = "‮"
_HOSTILE_TITLE = f"Evil{_HOSTILE_CONTROL_CHARACTER}title" + ("x" * 5_000)
_HOSTILE_URL = f"https://example.test/{_HOSTILE_CONTROL_CHARACTER}" + ("y" * 5_000)
_TIMESTAMP = "2026-09-20T00:00:00+00:00"


def _traceability_dict() -> dict[str, Any]:
    """Hand-built exactly to `_traceability()`'s own documented shape.

    One resolved claim -> evidence -> source -> discovery-candidate chain
    (the candidate carries the hostile title/URL), one evidence reference the
    dict itself reports unresolved, and one revalidation with both endpoints,
    covering every branch the widget must render.
    """
    resolved_source = {
        "observation_id": "observation-1",
        "document_id": "document-1",
        "requested_url": _HOSTILE_URL,
        "url": _HOSTILE_URL,
        "content_sha256": "c" * 64,
        "fetched_at": _TIMESTAMP,
        "added_at": _TIMESTAMP,
        "discovery_candidate": {
            "candidate_id": "candidate-1",
            "resolved": True,
            "discovery_id": "discovery-1",
            "url": _HOSTILE_URL,
            "title": _HOSTILE_TITLE,
        },
    }
    return {
        "mission_comparison_note_id": None,
        "mission_comparison_review_id": None,
        "goal_basis": {
            "comparison_notes": [
                {
                    "role": "supporting",
                    "note_id": "note-1",
                    "recorded_relation": "supports",
                    "resolved": True,
                    "evidence": [],
                }
            ],
            "contradiction_outcome": "unresolved",
            "evidence_gap_outcome": None,
            "supporting_review_id": None,
        },
        "source_observations": [resolved_source],
        "comparison_reviews": [],
        "claims": [
            {
                "claim_id": "claim-1",
                "epistemic_state": "hypothesis",
                "current": True,
                "supersedes_claim_id": None,
                "source_document_ids": ["document-1"],
                "unrecorded_evidence_ids": ["evidence-missing"],
                "evidence": [
                    {
                        "evidence_id": "evidence-1",
                        "resolved": True,
                        "chunk_id": "chunk-1",
                        "chunk_sha256": "d" * 64,
                        "source": resolved_source,
                    },
                    {"evidence_id": "evidence-missing", "resolved": False},
                ],
            }
        ],
        "claim_contradictions": [
            {
                "contradiction_id": "contradiction-1",
                "recorded_at": _TIMESTAMP,
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "resolved": True,
                        "epistemic_state": "hypothesis",
                        "current": True,
                    }
                ],
                "evidence": [],
            }
        ],
        "source_revalidations": [
            {
                "revalidation_id": "revalidation-1",
                "outcome": "unchanged",
                "recorded_at": _TIMESTAMP,
                "earlier": {
                    "run_id": "run-0",
                    "observation_id": "observation-0",
                    "document_id": "document-1",
                    "requested_url": _HOSTILE_URL,
                    "url": _HOSTILE_URL,
                    "content_sha256": "c" * 64,
                    "fetched_at": _TIMESTAMP,
                    "added_at": _TIMESTAMP,
                },
                "later": {
                    "run_id": "run-1",
                    "observation_id": "observation-1",
                    "document_id": "document-1",
                    "requested_url": _HOSTILE_URL,
                    "url": _HOSTILE_URL,
                    "content_sha256": "c" * 64,
                    "fetched_at": _TIMESTAMP,
                    "added_at": _TIMESTAMP,
                },
            }
        ],
    }


class FakeTreeview:
    """Just enough of `ttk.Treeview`'s API for the builder and the handlers."""

    def __init__(self) -> None:
        self._children: dict[str, list[str]] = {"": []}
        self._text: dict[str, str] = {}
        self._selected: tuple[str, ...] = ()

    def insert(
        self, parent: str, index: str, iid: str | None = None, text: str = "", **_: Any
    ) -> str:
        assert iid is not None
        self._children.setdefault(parent, []).append(iid)
        self._children.setdefault(iid, [])
        self._text[iid] = text
        return iid

    def get_children(self, item: str = "") -> tuple[str, ...]:
        return tuple(self._children.get(item, ()))

    def delete(self, *items: str) -> None:
        for item in items:
            for child in list(self._children.get(item, ())):
                self.delete(child)
            self._children.pop(item, None)
            self._text.pop(item, None)
            for siblings in self._children.values():
                if item in siblings:
                    siblings.remove(item)

    def selection(self) -> tuple[str, ...]:
        return self._selected

    def select(self, iid: str) -> None:
        self._selected = (iid,)

    def text_of(self, iid: str) -> str:
        return self._text[iid]

    def all_texts(self) -> list[str]:
        return list(self._text.values())


class TraceabilityTextSafetyTests(unittest.TestCase):
    """The one funnel every rendered field must go through."""

    def test_a_directional_override_control_character_is_stripped(self) -> None:
        text = _traceability_text(f"Title{_HOSTILE_CONTROL_CHARACTER}Tail")

        self.assertNotIn(_HOSTILE_CONTROL_CHARACTER, text)

    def test_an_unbounded_length_field_is_truncated(self) -> None:
        text = _traceability_text("x" * 10_000)

        self.assertLessEqual(len(text), _MAX_TRACEABILITY_TEXT_CHARACTERS + 20)
        self.assertIn("truncated", text)

    def test_none_and_booleans_render_without_crashing(self) -> None:
        self.assertEqual(_traceability_text(None), "unavailable")
        self.assertEqual(_traceability_text(True), "yes")
        self.assertEqual(_traceability_text(False), "no")

    def test_markdown_special_characters_are_not_escaped(self) -> None:
        # `_inline` (the Markdown renderer's helper) would backslash-escape
        # this to 'My\\_Title \\[draft\\] \\*note\\* (v1)'. This is a plain
        # `ttk.Treeview` label, not Markdown, so no escaping is expected.
        text = _traceability_text("My_Title [draft] *note* (v1)")

        self.assertEqual(text, "My_Title [draft] *note* (v1)")

    def test_markdown_chars_unescaped_hostile_control_and_length_still_bounded(
        self,
    ) -> None:
        payload = f"My_Title {_HOSTILE_CONTROL_CHARACTER}[draft] *note* (v1)" + (
            "z" * 5_000
        )

        text = _traceability_text(payload)

        self.assertNotIn("\\_", text)
        self.assertNotIn("\\[", text)
        self.assertNotIn("\\*", text)
        self.assertIn("My_Title", text)
        self.assertNotIn(_HOSTILE_CONTROL_CHARACTER, text)
        self.assertLessEqual(len(text), _MAX_TRACEABILITY_TEXT_CHARACTERS + 20)
        self.assertIn("truncated", text)


class PopulateMissionAuditTraceabilityTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = traceability_graph_for(_traceability_dict())
        self.tree = FakeTreeview()
        self.details = _populate_mission_audit_traceability_tree(self.tree, self.graph)

    def test_the_claim_evidence_source_candidate_chain_is_nested(self) -> None:
        claims_root = self.tree.get_children("")[0]
        (claim_iid,) = self.tree.get_children(claims_root)
        evidence_children = self.tree.get_children(claim_iid)
        # One resolved evidence node and one explicit unresolved leaf, plus
        # no supersession leaf (this claim supersedes nothing).
        self.assertEqual(len(evidence_children), 2)
        resolved_evidence = next(
            iid
            for iid in evidence_children
            if "evidence-1" in self.tree.text_of(iid)
            and "unresolved" not in self.tree.text_of(iid)
        )
        unresolved_evidence = next(
            iid for iid in evidence_children if "unresolved" in self.tree.text_of(iid)
        )
        self.assertIn("evidence-missing", self.tree.text_of(unresolved_evidence))
        (source_iid,) = self.tree.get_children(resolved_evidence)
        self.assertIn("document-1", self.tree.text_of(source_iid))
        (candidate_iid,) = self.tree.get_children(source_iid)
        self.assertIn("candidate-1", self.tree.text_of(candidate_iid))

    def test_revalidation_endpoints_are_both_present(self) -> None:
        revalidation_root = next(
            iid
            for iid in self.tree.get_children("")
            if "Source revalidations" in self.tree.text_of(iid)
        )
        (revalidation_iid,) = self.tree.get_children(revalidation_root)
        endpoints = self.tree.get_children(revalidation_iid)
        self.assertEqual(len(endpoints), 2)
        texts = {self.tree.text_of(iid) for iid in endpoints}
        self.assertTrue(any(text.startswith("Earlier observation") for text in texts))
        self.assertTrue(any(text.startswith("Later observation") for text in texts))

    def test_no_rendered_text_carries_the_hostile_control_character(self) -> None:
        for text in self.tree.all_texts():
            self.assertNotIn(_HOSTILE_CONTROL_CHARACTER, text)
        for text in self.details.values():
            self.assertNotIn(_HOSTILE_CONTROL_CHARACTER, text)

    def test_no_rendered_field_is_unbounded_in_length(self) -> None:
        # A generous bound: several safe fields may be concatenated onto one
        # line, but none may carry the raw 5,000-character hostile title/URL.
        for text in self.tree.all_texts():
            self.assertLess(len(text), 1_000)

    def test_the_goal_basis_root_carries_a_tentativeness_caveat(self) -> None:
        goal_basis_root = next(
            iid
            for iid in self.tree.get_children("")
            if self.tree.text_of(iid) == "Goal evaluation basis"
        )
        children_text = [
            self.tree.text_of(iid) for iid in self.tree.get_children(goal_basis_root)
        ]
        caveats = [text for text in children_text if text.startswith("Note:")]
        self.assertEqual(len(caveats), 1)
        self.assertIn("tentative model", caveats[0])
        self.assertIn("verified fact", caveats[0])

    def test_the_contradictions_root_carries_a_does_not_decide_caveat(self) -> None:
        contradictions_root = next(
            iid
            for iid in self.tree.get_children("")
            if self.tree.text_of(iid).startswith("Contradictions (")
        )
        children_text = [
            self.tree.text_of(iid)
            for iid in self.tree.get_children(contradictions_root)
        ]
        caveats = [text for text in children_text if text.startswith("Note:")]
        self.assertEqual(len(caveats), 1)
        self.assertIn("does not decide which claim is true", caveats[0])


class MissionAuditTraceabilityUnresolvedGraphTests(unittest.TestCase):
    """An edge the graph reports unresolved must render, never crash."""

    def test_a_run_with_nothing_recorded_still_produces_an_empty_tree(self) -> None:
        empty = {
            "mission_comparison_note_id": None,
            "mission_comparison_review_id": None,
            "goal_basis": {
                "comparison_notes": [],
                "contradiction_outcome": None,
                "evidence_gap_outcome": None,
                "supporting_review_id": None,
            },
            "source_observations": [],
            "comparison_reviews": [],
            "claims": [],
            "claim_contradictions": [],
            "source_revalidations": [],
        }
        graph = traceability_graph_for(empty)
        tree = FakeTreeview()

        details = _populate_mission_audit_traceability_tree(tree, graph)

        self.assertEqual(tree.get_children(""), ())
        self.assertEqual(details, {})


class Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class ForbiddenController:
    """Any attribute access proves an unwanted Brain/network/provider call."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"selecting a row must never call controller.{name}.")


def _traceability_response(success: bool = True) -> BrainResponse:
    graph = traceability_graph_for(_traceability_dict()) if success else None
    return BrainResponse(
        message="loaded" if success else "unavailable",
        request_id="traceability",
        intent="research_mission_audit_traceability_view",
        memory_count=0,
        success=success,
        research_mission_audit_traceability_graph=graph,
    )


class RenderAndSelectHandlerTests(unittest.TestCase):
    def window(self) -> SimpleNamespace:
        window = SimpleNamespace(
            _controller=Mock(),
            _status=Mock(),
            _root=None,
            _mission_plan_id="",
            _execution_id=Var("plan-1"),
            _mission_audit_traceability_tree=FakeTreeview(),
            _mission_audit_traceability_details={},
            _mission_audit_traceability_detail=Var(),
        )
        window._audit_plan_id = lambda: TkinterDesktopWindow._audit_plan_id(window)
        window._render_mission_audit_traceability = (
            lambda response: TkinterDesktopWindow._render_mission_audit_traceability(
                window, response
            )
        )
        return window

    def test_no_plan_id_never_calls_the_controller(self) -> None:
        window = self.window()
        window._execution_id = Var("")

        TkinterDesktopWindow._view_mission_audit_traceability(window)

        window._controller.mission_audit_traceability_view.assert_not_called()

    def test_a_named_plan_calls_the_controller_exactly_once(self) -> None:
        window = self.window()
        window._controller.mission_audit_traceability_view.return_value = (
            _traceability_response()
        )

        TkinterDesktopWindow._view_mission_audit_traceability(window)

        window._controller.mission_audit_traceability_view.assert_called_once_with(
            "plan-1"
        )

    def test_an_unavailable_response_clears_the_tree_and_shows_the_message(
        self,
    ) -> None:
        window = self.window()
        window._mission_audit_traceability_tree.insert(
            "", "end", iid="stale", text="stale"
        )
        window._mission_audit_traceability_details = {"stale": "stale detail"}

        TkinterDesktopWindow._render_mission_audit_traceability(
            window, _traceability_response(success=False)
        )

        self.assertEqual(window._mission_audit_traceability_tree.get_children(""), ())
        self.assertEqual(window._mission_audit_traceability_details, {})
        window._status.set.assert_called_once_with("unavailable")

    def test_a_successful_response_populates_the_tree(self) -> None:
        window = self.window()

        TkinterDesktopWindow._render_mission_audit_traceability(
            window, _traceability_response()
        )

        self.assertGreater(
            len(window._mission_audit_traceability_tree.get_children("")), 0
        )
        self.assertGreater(len(window._mission_audit_traceability_details), 0)
        self.assertIn("loaded", window._status.set.call_args.args[0])

    def test_selecting_nothing_shows_the_default_prompt(self) -> None:
        window = self.window()
        window._controller = ForbiddenController()

        TkinterDesktopWindow._on_mission_audit_traceability_select(window)

        self.assertIn("Select a row", window._mission_audit_traceability_detail.get())

    def test_selecting_a_loaded_row_shows_its_detail_and_calls_no_controller(
        self,
    ) -> None:
        window = self.window()
        window._controller = ForbiddenController()
        TkinterDesktopWindow._render_mission_audit_traceability(
            window, _traceability_response()
        )
        first_iid = next(iter(window._mission_audit_traceability_details))
        window._mission_audit_traceability_tree.select(first_iid)

        # No exception means `ForbiddenController` was never touched.
        TkinterDesktopWindow._on_mission_audit_traceability_select(window)

        self.assertEqual(
            window._mission_audit_traceability_detail.get(),
            window._mission_audit_traceability_details[first_iid],
        )


class DesktopControllerTraceabilityViewTests(unittest.TestCase):
    class RecordingBrain:
        def __init__(self, response: BrainResponse) -> None:
            self.requests: list[BrainRequest | str] = []
            self._response = response

        def process(self, request: BrainRequest | str) -> BrainResponse:
            self.requests.append(request)
            return self._response

    def test_sends_exactly_the_intent_and_plan_id(self) -> None:
        brain = self.RecordingBrain(_traceability_response())
        controller = DesktopController(brain)

        controller.mission_audit_traceability_view("  plan-1  ")

        request = brain.requests[-1]
        assert isinstance(request, BrainRequest)
        self.assertEqual(
            request.metadata,
            {
                "intent": "research_mission_audit_traceability_view",
                "research_plan_id": "plan-1",
            },
        )
        self.assertEqual(request.source, "desktop")

    def test_an_empty_plan_id_is_refused_before_the_brain_is_reached(self) -> None:
        brain = self.RecordingBrain(_traceability_response())
        controller = DesktopController(brain)

        with self.assertRaises(ValueError):
            controller.mission_audit_traceability_view("   ")

        self.assertEqual(brain.requests, [])


class RealWindowWiringTests(unittest.TestCase):
    """The real construction path must build the button and the tree."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.window, cls.widgets = build_real_window()

    def test_the_view_provenance_graph_button_is_bound_to_its_own_handler(
        self,
    ) -> None:
        matches = [
            widget for widget in self.widgets if widget.text == "View provenance graph"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(
            matches[0].command, self.window._view_mission_audit_traceability
        )

    def test_a_tree_widget_is_constructed_for_the_provenance_graph(self) -> None:
        trees = [
            widget for widget in self.widgets if widget.kwargs.get("show") == "tree"
        ]
        self.assertEqual(len(trees), 1)

    def test_selecting_never_starts_a_request_even_on_the_real_window(self) -> None:
        self.window._controller = ForbiddenController()
        self.window._mission_audit_traceability_tree = FakeTreeview()
        self.window._mission_audit_traceability_details = {"row-1": "detail"}
        self.window._mission_audit_traceability_tree.insert(
            "", "end", iid="row-1", text="row"
        )
        self.window._mission_audit_traceability_tree.select("row-1")

        # No exception means the real bound method never touched the
        # (forbidden) controller.
        self.window._on_mission_audit_traceability_select()


if __name__ == "__main__":
    unittest.main()
