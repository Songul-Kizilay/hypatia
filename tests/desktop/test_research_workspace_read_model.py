"""Direct headless coverage for immutable Research workspace projections."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from desktop.ResearchWorkspaceReadModel import (
    ResearchRunSort,
    ResearchSourceCoverageFacet,
    ResearchWorkspaceReadModel,
)
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceRecord import ResearchSourceRecord


class ResearchWorkspaceReadModelTests(unittest.TestCase):
    def test_empty_catalog_projection_is_complete_and_immutable(self) -> None:
        model = ResearchWorkspaceReadModel(())

        self.assertEqual(
            model.catalog_summary_text(),
            "Loaded catalog: All 0 · Collecting 0 · Completed 0 · Failed 0 · "
            "Cancelled 0",
        )
        self.assertEqual(model.filter_runs("anything"), ())
        self.assertEqual(model.sort_runs(ResearchRunSort.UPDATED_NEWEST), ())
        with self.assertRaises(FrozenInstanceError):
            _set_attribute(model, "runs", ())

    def test_filter_matches_question_or_exact_status_and_id_without_mutation(
        self,
    ) -> None:
        first = _run("run-alpha", "Local model research")
        second = _run(
            "run-beta",
            "Source review",
            status=ResearchRunStatus.COMPLETED,
        )
        model = ResearchWorkspaceReadModel((first, second))

        self.assertEqual(model.filter_runs("LOCAL"), (first,))
        self.assertEqual(model.filter_runs("completed"), (second,))
        self.assertEqual(model.filter_runs("RUN-BETA"), (second,))
        self.assertEqual(model.filter_runs("beta"), ())
        self.assertEqual(model.filter_runs("  "), (first, second))
        self.assertEqual(model.runs, (first, second))

    def test_sort_uses_deterministic_exact_id_ties(self) -> None:
        now = datetime(2026, 8, 22, 10, tzinfo=UTC)
        upper = _run("RUN-A", "same", updated_at=now)
        lower = _run("run-a", "same", updated_at=now)
        later = _run(
            "run-z",
            "later",
            created_at=now + timedelta(minutes=1),
            updated_at=now + timedelta(minutes=1),
        )

        model = ResearchWorkspaceReadModel((later, lower, upper))

        self.assertEqual(
            model.sort_runs(ResearchRunSort.UPDATED_OLDEST),
            (upper, lower, later),
        )
        self.assertEqual(
            model.sort_runs(ResearchRunSort.UPDATED_NEWEST),
            (later, upper, lower),
        )
        self.assertEqual(
            model.sort_runs(ResearchRunSort.QUESTION),
            (later, upper, lower),
        )

    def test_run_view_counts_duplicate_evidence_source_once(self) -> None:
        source = _source("document-1", "Accepted")
        run = _run(
            "run-coverage",
            "Coverage",
            sources=(source,),
            evidence=(
                _evidence("evidence-1", source.document_id),
                _evidence("evidence-2", source.document_id),
            ),
        )

        view = ResearchWorkspaceReadModel.run_view(run)

        self.assertEqual(
            view.evidence_coverage,
            "Evidence coverage — Accepted sources: 1 · With evidence: 1 · "
            "Without evidence: 0",
        )
        self.assertEqual(view.progress, "Sources: 1 · Evidence: 2 · Claims: 0")
        with self.assertRaises(FrozenInstanceError):
            _set_attribute(view, "progress", "changed")

    def test_current_assessment_projection_ignores_superseded_and_foreign_records(
        self,
    ) -> None:
        source = _source("document-1", "Accepted")
        original = _assessment("assessment-1", source.document_id, "evidence-1")
        correction = _assessment(
            "assessment-2",
            source.document_id,
            "evidence-1",
            supersedes=original.assessment_id,
            trust=ResearchInformationTrust.LOW,
        )
        foreign = _assessment(
            "assessment-foreign",
            "foreign",
            "evidence-foreign",
        )

        current_ids = ResearchWorkspaceReadModel.current_assessment_source_ids(
            (source,),
            (original, correction, foreign),
        )

        self.assertEqual(current_ids, frozenset({source.document_id}))

    def test_source_coverage_can_hide_active_membership_without_changing_catalog(
        self,
    ) -> None:
        represented = _source("document-1", "Represented")
        hidden_view_member = _source("document-2", "Without evidence")
        sources = (represented, hidden_view_member)
        evidence = (_evidence("evidence-1", represented.document_id),)

        visible = ResearchWorkspaceReadModel.filter_sources_by_coverage(
            sources,
            evidence,
            (),
            ResearchSourceCoverageFacet.WITHOUT_EVIDENCE,
        )

        self.assertEqual(visible, (hidden_view_member,))
        self.assertEqual(sources, (represented, hidden_view_member))

    def test_source_view_rejects_changed_copy_with_same_id(self) -> None:
        accepted = _source("document-1", "Accepted")
        changed_copy = _source("document-1", "Changed")
        run = _run("run-1", "Canonical membership", sources=(accepted,))

        view = ResearchWorkspaceReadModel.source_view(run, changed_copy)

        self.assertFalse(view.canonical)
        self.assertIsNone(view.details)
        self.assertEqual(
            view.summary,
            "Selected-source records unavailable until an accepted source is "
            "selected.",
        )

    def test_source_view_uses_current_assessments_and_excludes_url(self) -> None:
        source = _source(
            "document-1",
            "  Accepted\n source  ",
            url="https://secret.example/path",
        )
        evidence = (
            _evidence("evidence-1", source.document_id),
            _evidence("evidence-2", source.document_id),
        )
        original = _assessment(
            "assessment-1",
            source.document_id,
            evidence[0].evidence_id,
            trust=ResearchInformationTrust.HIGH,
        )
        correction = _assessment(
            "assessment-2",
            source.document_id,
            evidence[1].evidence_id,
            supersedes=original.assessment_id,
            trust=ResearchInformationTrust.LOW,
        )
        run = _run(
            "run-1",
            "Source projection",
            sources=(source,),
            evidence=evidence,
            assessments=(original, correction),
        )

        view = ResearchWorkspaceReadModel.source_view(run, source)

        self.assertTrue(view.canonical)
        self.assertIn("Selected source — Accepted source", view.summary)
        self.assertIn("Assessments: 2 history / 1 current", view.summary)
        self.assertIn("Evidence cited by current: 1 of 2", view.summary)
        self.assertIn("Unassessed: 0 · Low: 1 · Medium: 0 · High: 0", view.summary)
        self.assertIn("Fetched: 2026-08-22T10:00:00+00:00", view.details or "")
        self.assertNotIn(source.url, view.summary)
        self.assertNotIn(source.url, view.details or "")

    def test_malformed_foreign_evidence_cannot_change_accepted_coverage(self) -> None:
        source = _source("document-1", "Accepted")
        run = Mock(spec=ResearchRun)
        run.sources = (source,)
        run.evidence = (
            _evidence("evidence-1", source.document_id),
            _evidence("evidence-foreign", "foreign"),
        )

        self.assertEqual(
            ResearchWorkspaceReadModel.evidence_coverage_text(run),
            "Evidence coverage — Accepted sources: 1 · With evidence: 1 · "
            "Without evidence: 0",
        )


def _run(
    run_id: str,
    question: str,
    *,
    status: ResearchRunStatus = ResearchRunStatus.COLLECTING,
    sources: tuple[ResearchSourceRecord, ...] = (),
    evidence: tuple[ResearchEvidenceRecord, ...] = (),
    assessments: tuple[ResearchSourceAssessmentRecord, ...] = (),
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> ResearchRun:
    created = created_at or datetime(2026, 8, 22, 10, tzinfo=UTC)
    updated = updated_at or created
    return ResearchRun(
        run_id,
        question,
        status,
        sources,
        (),
        created,
        updated,
        evidence=evidence,
        assessments=assessments,
    )


def _source(
    document_id: str,
    title: str,
    *,
    url: str | None = None,
) -> ResearchSourceRecord:
    now = datetime(2026, 8, 22, 10, tzinfo=UTC)
    return ResearchSourceRecord(
        document_id,
        url or f"https://example.com/{document_id}",
        title,
        "text/plain",
        now,
        now + timedelta(minutes=1),
    )


def _evidence(evidence_id: str, source_document_id: str) -> ResearchEvidenceRecord:
    return ResearchEvidenceRecord(
        evidence_id,
        source_document_id,
        f"{source_document_id}:paragraph:0",
        0,
        "Bounded evidence",
        False,
        "0" * 64,
        "User note",
        datetime(2026, 8, 22, 10, tzinfo=UTC),
    )


def _assessment(
    assessment_id: str,
    source_document_id: str,
    evidence_id: str,
    *,
    supersedes: str | None = None,
    trust: ResearchInformationTrust = ResearchInformationTrust.UNASSESSED,
) -> ResearchSourceAssessmentRecord:
    return ResearchSourceAssessmentRecord(
        assessment_id,
        source_document_id,
        (evidence_id,),
        "User-authored assessment",
        datetime(2026, 8, 22, 10, tzinfo=UTC),
        supersedes_assessment_id=supersedes,
        information_trust=trust,
    )


def _set_attribute(target: object, name: str, value: object) -> None:
    setattr(target, name, value)


if __name__ == "__main__":
    unittest.main()
