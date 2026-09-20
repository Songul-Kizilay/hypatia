"""Mission comparison review binds the checkpoint note and previews before writing."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch

from brain.BrainResponse import BrainResponse
from desktop.MissionComparisonReview import mission_comparison_review_preview
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from research.ResearchComparisonReviewRecord import (
    ResearchComparisonReviewDecision,
    ResearchComparisonReviewRecord,
)
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceRecord import ResearchSourceRecord

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def source(number: int) -> ResearchSourceRecord:
    return ResearchSourceRecord(
        document_id=f"doc-{number}",
        url=f"https://example.test/{number}",
        title=f"Source {number}",
        content_type="text/plain",
        fetched_at=NOW,
        added_at=NOW,
    )


def evidence(number: int) -> ResearchEvidenceRecord:
    excerpt = f"Recorded excerpt {number}."
    return ResearchEvidenceRecord(
        evidence_id=f"evidence-{number}",
        source_document_id=f"doc-{number}",
        chunk_id=f"chunk-{number}",
        chunk_index=0,
        excerpt=excerpt,
        excerpt_truncated=False,
        chunk_sha256=sha256(excerpt.encode("utf-8")).hexdigest(),
        note="Grounded excerpt only.",
        recorded_at=NOW,
    )


def assessment(number: int) -> ResearchSourceAssessmentRecord:
    return ResearchSourceAssessmentRecord(
        assessment_id=f"assessment-{number}",
        source_document_id=f"doc-{number}",
        evidence_ids=(f"evidence-{number}",),
        text="Exact-source grounding only.",
        recorded_at=NOW,
    )


def note(note_id: str, first: int, second: int) -> ResearchSourceComparisonNoteRecord:
    return ResearchSourceComparisonNoteRecord(
        note_id=note_id,
        source_document_ids=(f"doc-{first}", f"doc-{second}"),
        evidence_ids=(f"evidence-{first}", f"evidence-{second}"),
        assessment_ids=(f"assessment-{first}", f"assessment-{second}"),
        text="Tentative model comparison.",
        recorded_at=NOW,
    )


def review(
    review_id: str,
    decision: str,
    *,
    minutes: int = 1,
    supersedes: str | None = None,
) -> ResearchComparisonReviewRecord:
    return ResearchComparisonReviewRecord(
        review_id=review_id,
        note_id="note-mission",
        evidence_ids=("evidence-1", "evidence-2"),
        decision=ResearchComparisonReviewDecision(decision),
        note="Operator reason.",
        recorded_at=NOW + timedelta(minutes=minutes),
        supersedes_review_id=supersedes,
    )


def mission_run(*reviews: ResearchComparisonReviewRecord) -> ResearchRun:
    return ResearchRun(
        run_id="run-1",
        question="What do the recorded sources support?",
        status=ResearchRunStatus.COLLECTING,
        sources=(source(1), source(2), source(3)),
        failures=(),
        created_at=NOW,
        updated_at=NOW + timedelta(minutes=5),
        evidence=(evidence(1), evidence(2), evidence(3)),
        assessments=(assessment(1), assessment(2), assessment(3)),
        comparison_notes=(note("note-other", 1, 3), note("note-mission", 1, 2)),
        comparison_reviews=reviews,
    )


class Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


def target(
    run: ResearchRun, note_id: str = "note-mission", message: str = ""
) -> BrainResponse:
    return BrainResponse(
        message=message or "Mission goal satisfaction: Unresolved",
        request_id="target",
        intent="research_mission_comparison_review",
        memory_count=0,
        research_runs=[run],
        research_mission_comparison_note_id=note_id,
    )


def refusal(message: str) -> BrainResponse:
    return BrainResponse(
        message=message,
        request_id="refused",
        intent="research_comparison_review_record",
        memory_count=0,
        success=False,
    )


class MissionComparisonReviewPreviewTests(unittest.TestCase):
    def test_preview_names_run_plan_note_evidence_decision_and_reason(self):
        preview = mission_comparison_review_preview(
            mission_run(), "plan-1", "note-mission", "supported", " Checked quotes. "
        )

        for line in (
            "nothing is saved until you confirm",
            "Mission plan: plan-1",
            "Research run: run-1",
            "Mission comparison note: note-mission",
            "Evidence IDs: evidence-1, evidence-2",
            "Current review: none recorded",
            "Proposed decision: supported",
            "Operator reason: Checked quotes.",
            "not model output or a factual-truth decision",
        ):
            self.assertIn(line, preview.text)
        self.assertEqual(
            preview.arguments,
            ("run-1", "note-mission", "supported", "Checked quotes.", ""),
        )

    def test_preview_supersedes_the_current_review_for_revocation(self):
        run = mission_run(review("review-1", "supported"))

        preview = mission_comparison_review_preview(
            run, "plan-1", "note-mission", "not_supported", "Withdrawn."
        )

        self.assertIn("Current review: review-1 (supported", preview.text)
        self.assertIn("supersede current review review-1", preview.text)
        self.assertEqual(preview.arguments[4], "review-1")

    def test_preview_refuses_missing_note_invalid_input_and_closed_run(self):
        run = mission_run()
        cases = (
            (run, "", "supported", "Reason."),
            (run, "note-missing", "supported", "Reason."),
            (run, "note-mission", "verified", "Reason."),
            (run, "note-mission", "supported", "  "),
            (
                replace(run, status=ResearchRunStatus.COMPLETED),
                "note-mission",
                "supported",
                "Reason.",
            ),
        )
        for value, note_id, decision, reason in cases:
            with self.subTest(note_id=note_id, decision=decision, reason=reason):
                with self.assertRaises(ValueError):
                    mission_comparison_review_preview(
                        value, "plan-1", note_id, decision, reason
                    )


class MissionComparisonReviewWindowTests(unittest.TestCase):
    def window(self) -> SimpleNamespace:
        window = SimpleNamespace(
            _controller=Mock(),
            _status=Mock(),
            _append_response=Mock(),
            _root=None,
            _mission_plan_id="",
            _mission_independence_run_id="",
            _mission_review_run=None,
            _mission_review_note_id="",
            _mission_review_plan_id="",
            _execution_id=Var(),
            _research_comparison_review_decision=Var("supported"),
            _research_comparison_review_note=Var("Checked both quotes."),
            _research_plan_preview=Mock(),
        )
        for name in (
            "_render_mission_comparison_review",
            "_load_mission_comparison_review",
        ):
            method = getattr(TkinterDesktopWindow, name)
            setattr(
                window,
                name,
                lambda *args, _method=method: _method(window, *args),
            )
        return window

    def loaded(self, run: ResearchRun | None = None) -> SimpleNamespace:
        window = self.window()
        window._mission_plan_id = "plan-1"
        window._controller.mission_comparison_review.return_value = target(
            run or mission_run()
        )
        TkinterDesktopWindow._load_mission_comparison_review(window)
        return window

    def test_load_requires_a_mission_and_calls_nothing(self):
        window = self.window()

        TkinterDesktopWindow._load_mission_comparison_review(window)

        window._controller.mission_comparison_review.assert_not_called()
        self.assertIn("mission first", window._status.set.call_args.args[0])

    def test_live_result_binds_plan_and_load_uses_runtime_note(self):
        window = self.window()
        run = mission_run()
        TkinterDesktopWindow._render_learning_research_result(
            window,
            BrainResponse(
                message="report",
                request_id="start",
                intent="research_goal_start",
                memory_count=0,
                research_runs=[run],
                research_plan_execution=SimpleNamespace(plan_id="plan-live"),
            ),
        )
        window._controller.mission_comparison_review.return_value = target(run)

        TkinterDesktopWindow._load_mission_comparison_review(window)

        window._controller.mission_comparison_review.assert_called_once_with(
            "plan-live"
        )
        self.assertEqual(window._mission_review_note_id, "note-mission")
        self.assertIs(window._mission_review_run, run)

    def test_recovered_single_mission_binds_its_plan(self):
        window = self.window()
        window._controller = Mock()
        response = BrainResponse(
            message="Missions recovered at startup (this session):",
            request_id="recovered",
            intent="research_plan_execution_recovered",
            memory_count=0,
            research_recovered_mission_ids=("plan-recovered",),
            research_recovered_mission_run_ids=("run-1",),
        )

        TkinterDesktopWindow._render_recovered_research_missions(window, response)

        self.assertEqual(window._mission_plan_id, "plan-recovered")

    def test_execution_panel_names_any_restored_mission_for_review(self):
        window = self.window()
        window._mission_plan_id = "plan-last-live"
        window._execution_id.set(" plan-restored-2 ")
        window._controller.mission_comparison_review.return_value = target(
            mission_run()
        )

        TkinterDesktopWindow._load_mission_comparison_review(window)

        window._controller.mission_comparison_review.assert_called_once_with(
            "plan-restored-2"
        )
        self.assertEqual(window._mission_review_plan_id, "plan-restored-2")

    def test_record_previews_and_reloads_the_loaded_mission_not_a_renamed_one(self):
        window = self.window()
        window._execution_id.set("plan-a")
        window._controller.mission_comparison_review.return_value = target(
            mission_run()
        )
        TkinterDesktopWindow._load_mission_comparison_review(window)
        window._execution_id.set("plan-b")
        window._controller.record_research_comparison_review.return_value = target(
            mission_run(review("review-1", "supported"))
        )

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ) as confirm:
            TkinterDesktopWindow._record_mission_comparison_review(window)

        self.assertIn("Mission plan: plan-a", confirm.call_args.args[1])
        self.assertEqual(
            [
                call.args[0]
                for call in window._controller.mission_comparison_review.call_args_list
            ],
            ["plan-a", "plan-a"],
        )

    def test_live_result_names_its_execution_in_the_panel(self):
        window = self.window()

        TkinterDesktopWindow._render_learning_research_result(
            window,
            BrainResponse(
                message="report",
                request_id="start",
                intent="research_goal_start",
                memory_count=0,
                research_plan_execution=SimpleNamespace(plan_id="plan-live"),
            ),
        )

        self.assertEqual(window._execution_id.get(), "plan-live")

    def test_declined_preview_writes_nothing(self):
        window = self.loaded()

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ) as confirm:
            TkinterDesktopWindow._record_mission_comparison_review(window)

        text = confirm.call_args.args[1]
        self.assertIn("Mission comparison note: note-mission", text)
        self.assertIn("Evidence IDs: evidence-1, evidence-2", text)
        self.assertIn("Proposed decision: supported", text)
        window._controller.record_research_comparison_review.assert_not_called()

    def test_selected_other_note_is_never_the_review_target(self):
        window = self.loaded()
        window._research_persisted_comparison_note_choice = Var("note-other")

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            window._controller.record_research_comparison_review.return_value = target(
                mission_run(review("review-1", "supported"))
            )
            TkinterDesktopWindow._record_mission_comparison_review(window)

        window._controller.record_research_comparison_review.assert_called_once_with(
            "run-1", "note-mission", "supported", "Checked both quotes.", ""
        )

    def test_confirmed_review_records_then_reloads_canonical_report(self):
        window = self.loaded()
        recorded = mission_run(review("review-1", "supported"))
        window._controller.record_research_comparison_review.return_value = target(
            recorded
        )
        window._controller.mission_comparison_review.return_value = target(
            recorded, message="Mission goal satisfaction: Satisfied (canonical)"
        )

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            TkinterDesktopWindow._record_mission_comparison_review(window)

        self.assertEqual(window._controller.mission_comparison_review.call_count, 2)
        self.assertIs(window._mission_review_run, recorded)
        rendered = window._research_plan_preview.insert.call_args.args[1]
        self.assertEqual(rendered, "Mission goal satisfaction: Satisfied (canonical)")

    def test_stale_refusal_reloads_current_review_with_bounded_message(self):
        window = self.loaded()
        current = mission_run(review("review-other", "not_supported"))
        window._controller.record_research_comparison_review.return_value = refusal(
            "Research comparison review could not be validated or saved."
        )
        window._controller.mission_comparison_review.return_value = target(current)

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            TkinterDesktopWindow._record_mission_comparison_review(window)

        self.assertIs(window._mission_review_run, current)
        message = window._status.set.call_args.args[0]
        self.assertIn("may be stale", message)
        self.assertIn("reloaded", message)
        self.assertEqual(
            window._research_comparison_review_note.get(), "Checked both quotes."
        )

    def test_refused_target_clears_review_binding(self):
        window = self.loaded()
        window._controller.mission_comparison_review.return_value = refusal(
            "This mission's canonical result is unavailable in this session."
        )

        TkinterDesktopWindow._load_mission_comparison_review(window)

        self.assertIsNone(window._mission_review_run)
        with patch("desktop.TkinterDesktopWindow.messagebox.askyesno") as confirm:
            TkinterDesktopWindow._record_mission_comparison_review(window)
        confirm.assert_not_called()
        window._controller.record_research_comparison_review.assert_not_called()


if __name__ == "__main__":
    unittest.main()
