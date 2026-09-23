"""Mission source-independence review reuses the existing assessment path."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch

from brain.BrainResponse import BrainResponse
from desktop.MissionSourceIndependenceReview import (
    independence_assessment_arguments,
    independence_review_rows,
    independence_review_text,
)
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceEvidenceType import ResearchSourceEvidenceType
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourceRecord import ResearchSourceRecord
from research.ResearchSourceUsefulness import ResearchSourceUsefulness

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


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


def assessment(
    number: int,
    suffix: str = "",
    *,
    independence: ResearchSourceIndependence = ResearchSourceIndependence.UNKNOWN,
    evidence_type: ResearchSourceEvidenceType = ResearchSourceEvidenceType.UNKNOWN,
    supersedes: str | None = None,
) -> ResearchSourceAssessmentRecord:
    return ResearchSourceAssessmentRecord(
        assessment_id=f"assessment-{number}{suffix}",
        source_document_id=f"doc-{number}",
        evidence_ids=(f"evidence-{number}",),
        text="Exact-source grounding only.",
        recorded_at=NOW,
        supersedes_assessment_id=supersedes,
        information_trust=ResearchInformationTrust.MEDIUM,
        usefulness=ResearchSourceUsefulness.USEFUL,
        independence=independence,
        evidence_type=evidence_type,
    )


def mission_run(*assessments: ResearchSourceAssessmentRecord) -> ResearchRun:
    return ResearchRun(
        run_id="run-1",
        question="What do the recorded sources support?",
        status=ResearchRunStatus.COLLECTING,
        sources=(source(1), source(2), source(3)),
        failures=(),
        created_at=NOW,
        updated_at=NOW,
        evidence=(evidence(1), evidence(2)),
        assessments=assessments or (assessment(1), assessment(2)),
    )


class Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class MissionSourceIndependenceReviewTests(unittest.TestCase):
    def test_rows_are_only_evidence_bearing_sources_with_current_judgement(self):
        run = mission_run(
            assessment(1),
            assessment(
                1,
                "-b",
                independence=ResearchSourceIndependence.INDEPENDENT,
                supersedes="assessment-1",
            ),
            assessment(2),
        )

        rows = independence_review_rows(run)

        self.assertEqual([row.document_id for row in rows], ["doc-1", "doc-2"])
        self.assertEqual(rows[0].current_assessment.assessment_id, "assessment-1-b")
        self.assertIs(rows[0].independence, ResearchSourceIndependence.INDEPENDENT)
        self.assertIs(rows[1].independence, ResearchSourceIndependence.UNKNOWN)

    def test_unknown_review_text_is_bounded_and_never_claims_independence(self):
        text = independence_review_text(mission_run())

        self.assertIn("independence=unknown", text)
        self.assertIn("source independence was not established", text)
        self.assertIn("not model truth or a verified claim", text)
        self.assertNotIn("independently confirmed", text.lower())

    def test_derivative_review_text_keeps_the_stronger_caveat(self):
        text = independence_review_text(
            mission_run(
                assessment(1, independence=ResearchSourceIndependence.DERIVATIVE),
                assessment(2, independence=ResearchSourceIndependence.INDEPENDENT),
            )
        )

        self.assertIn("derivative or a likely duplicate", text)
        self.assertNotIn("was not established", text)

    def test_arguments_supersede_current_and_carry_other_judgements(self):
        values = independence_assessment_arguments(
            mission_run(), "doc-1", "independent"
        )

        self.assertEqual(values[:3], ("run-1", "doc-1", "evidence-1"))
        self.assertIn("not model output, not a verified claim", values[3])
        self.assertEqual(
            values[4:],
            (
                "assessment-1",
                "medium",
                "useful",
                "unknown",
                "independent",
                "unknown",
                "unknown",
            ),
        )

    def test_arguments_carry_a_non_default_evidence_type_forward_unchanged(self):
        """`evidence_type` is not part of the independence question being asked.

        Revising only `independence` must not reset or drop whatever the
        operator separately recorded about how far the source stands from its
        subject -- that is a different dimension, answered independently.
        """
        run = mission_run(
            assessment(1, evidence_type=ResearchSourceEvidenceType.PRIMARY),
            assessment(2),
        )

        values = independence_assessment_arguments(run, "doc-1", "independent")

        self.assertEqual(
            values[4:],
            (
                "assessment-1",
                "medium",
                "useful",
                "unknown",
                "independent",
                "unknown",
                "primary",
            ),
        )

    def test_arguments_refuse_injected_source_and_invalid_value(self):
        run = mission_run()
        for document_id, value in (
            ("doc-3", "independent"),
            ("doc-arbitrary", "independent"),
            ("doc-1", "verified"),
        ):
            with self.subTest(document_id=document_id, value=value):
                with self.assertRaises(ValueError):
                    independence_assessment_arguments(run, document_id, value)


class MissionSourceIndependenceWindowTests(unittest.TestCase):
    def window(self, run: ResearchRun | None = None) -> SimpleNamespace:
        window = SimpleNamespace(
            _controller=Mock(),
            _status=Mock(),
            _append_response=Mock(),
            _root=None,
            _mission_independence_run_id="",
            _mission_independence_run=None,
            _mission_independence_source=Var(),
            _mission_independence_value=Var("unknown"),
            _mission_independence_selector=Mock(),
            _research_plan_preview=Mock(),
        )
        window._render_mission_source_independence = (
            lambda value: TkinterDesktopWindow._render_mission_source_independence(
                window, value
            )
        )
        if run is not None:
            window._controller.list_research_runs.return_value = response(run)
        return window

    def reviewed(self) -> tuple[SimpleNamespace, ResearchRun]:
        run = mission_run()
        window = self.window(run)
        TkinterDesktopWindow._render_learning_research_result(window, response(run))
        TkinterDesktopWindow._review_mission_source_independence(window)
        return window, run

    def test_review_requires_a_mission_result(self):
        window = self.window()

        TkinterDesktopWindow._review_mission_source_independence(window)

        window._controller.list_research_runs.assert_not_called()
        self.assertIn("mission first", window._status.set.call_args.args[0])

    def test_named_recovered_mission_reviews_its_reported_run(self):
        window = self.window(mission_run())
        window._execution_id = Var()
        window._execution_id.set("plan-2")
        TkinterDesktopWindow._render_recovered_research_missions(
            window,
            BrainResponse(
                message="Missions recovered at startup (this session):",
                request_id="recovered",
                intent="research_plan_execution_recovered",
                memory_count=0,
                research_recovered_mission_ids=("plan-1", "plan-2"),
                research_recovered_mission_run_ids=("run-other", "run-1"),
            ),
        )

        TkinterDesktopWindow._review_mission_source_independence(window)

        self.assertEqual(window._mission_run_ids["plan-2"], "run-1")
        self.assertEqual(window._mission_independence_run.run_id, "run-1")

    def test_named_execution_without_reported_run_is_refused(self):
        window = self.window(mission_run())
        window._execution_id = Var("plan-unknown")
        window._mission_independence_run_id = "run-1"

        TkinterDesktopWindow._review_mission_source_independence(window)

        window._controller.list_research_runs.assert_not_called()
        self.assertIn("No research run is known", window._status.set.call_args.args[0])

    def test_review_lists_only_mission_sources_from_canonical_state(self):
        window, _ = self.reviewed()

        labels = window._mission_independence_selector.configure.call_args.kwargs[
            "values"
        ]
        self.assertEqual(
            labels,
            ("doc-1 — https://example.test/1", "doc-2 — https://example.test/2"),
        )
        rendered = window._research_plan_preview.insert.call_args.args[1]
        self.assertIn("source independence was not established", rendered)

    def test_injected_source_label_is_refused_before_any_write(self):
        window, _ = self.reviewed()
        window._mission_independence_source.set("doc-3 — https://example.test/3")
        window._mission_independence_value.set("independent")

        TkinterDesktopWindow._record_mission_source_independence(window)

        window._controller.preview_research_source_assessment_write.assert_not_called()
        window._controller.record_research_source_assessment.assert_not_called()

    def test_declining_confirmation_records_nothing(self):
        window, run = self.reviewed()
        window._mission_independence_value.set("independent")
        window._controller.preview_research_source_assessment_write.return_value = (
            allowed_preview()
        )

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ):
            TkinterDesktopWindow._record_mission_source_independence(window)

        window._controller.preview_research_source_assessment_write.assert_called_once_with(
            *independence_assessment_arguments(run, "doc-1", "independent")
        )
        window._controller.record_research_source_assessment.assert_not_called()

    def test_confirmed_judgement_uses_existing_record_path_and_rerenders(self):
        window, run = self.reviewed()
        window._mission_independence_value.set("likely_duplicate")
        expected = independence_assessment_arguments(run, "doc-1", "likely_duplicate")
        updated = mission_run(
            assessment(1),
            assessment(2),
            assessment(
                1,
                "-b",
                independence=ResearchSourceIndependence.LIKELY_DUPLICATE,
                supersedes="assessment-1",
            ),
        )
        window._controller.preview_research_source_assessment_write.return_value = (
            allowed_preview()
        )
        window._controller.record_research_source_assessment.return_value = response(
            updated
        )

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            TkinterDesktopWindow._record_mission_source_independence(window)

        window._controller.record_research_source_assessment.assert_called_once_with(
            *expected
        )
        self.assertIs(window._mission_independence_run, updated)
        rendered = window._research_plan_preview.insert.call_args.args[1]
        self.assertIn("independence=likely_duplicate", rendered)
        self.assertIn("derivative or a likely duplicate", rendered)

    def test_refused_stale_record_does_not_rerender_as_saved(self):
        window, run = self.reviewed()
        window._mission_independence_value.set("independent")
        window._controller.preview_research_source_assessment_write.return_value = (
            allowed_preview()
        )
        window._controller.record_research_source_assessment.return_value = (
            BrainResponse(
                message="Research source assessment could not be validated or saved.",
                request_id="record",
                intent="research_source_assessment_record",
                memory_count=0,
                success=False,
            )
        )

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            TkinterDesktopWindow._record_mission_source_independence(window)

        self.assertIs(window._mission_independence_run, run)
        self.assertEqual(window._research_plan_preview.insert.call_count, 1)


def response(run: ResearchRun) -> BrainResponse:
    return BrainResponse(
        message="ok",
        request_id="request",
        intent="research_run_list",
        memory_count=0,
        research_runs=[run],
    )


def allowed_preview() -> BrainResponse:
    return BrainResponse(
        message="Preview",
        request_id="preview",
        intent="research_source_assessment_write_preview",
        memory_count=0,
        research_source_assessment_write_preview=SimpleNamespace(allowed=True),
    )


if __name__ == "__main__":
    unittest.main()
