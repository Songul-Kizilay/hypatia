"""Headless unit coverage for desktop-only presentation helpers."""

from __future__ import annotations

import sys
import unittest
from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainResponse import BrainResponse
from core.CancellationSignal import CancellationToken
from desktop.DesktopController import DesktopController
from desktop.DesktopRequestRunner import DesktopRequestCompletion
from desktop.TkinterDesktopWindow import (
    _MAX_RESEARCH_RUN_FILTER_LENGTH,
    _RESEARCH_ANALYSIS_TAB_TITLES,
    _RESEARCH_WORKFLOW_TAB_TITLES,
    DesktopTheme,
    ResearchRunSort,
    ResearchRunStatusFacet,
    ResearchSourceCoverageFacet,
    TkinterDesktopWindow,
    _accessibility_palette,
    _format_citations,
    _initial_window_size,
    _next_font_size,
    _preview_and_confirm_knowledge_relation,
    _preview_and_confirm_knowledge_relation_removal,
    _preview_and_confirm_session_rename,
)
from knowledge.Document import DocumentType
from knowledge.KnowledgeCitation import KnowledgeCitation
from knowledge.KnowledgeDocumentReference import KnowledgeDocumentReference
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimContradictionCandidate import (
    ResearchClaimContradictionCandidate,
)
from research.ResearchClaimContradictionPreview import (
    ResearchClaimContradictionPreview,
)
from research.ResearchClaimContradictionProposalPreview import (
    ResearchClaimContradictionProposalPreview,
)
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimContradictionWritePreview import (
    ResearchClaimContradictionWritePreview,
)
from research.ResearchClaimPreview import ResearchClaimPreview
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchClaimWritePreview import ResearchClaimWritePreview
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunMarkdownExportPreview import (
    ResearchRunMarkdownExportPreview,
)
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchRunStatusTransitionPreview import (
    ResearchRunStatusTransitionPreview,
)
from research.ResearchSourceAssessmentPreview import ResearchSourceAssessmentPreview
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceAssessmentWritePreview import (
    ResearchSourceAssessmentWritePreview,
)
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceUsefulness import ResearchSourceUsefulness
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceCandidateAcceptancePreview import (
    ResearchSourceCandidateAcceptancePreview,
)
from research.ResearchSourceComparisonItem import ResearchSourceComparisonItem
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceComparisonNoteWritePreview import (
    ResearchSourceComparisonNoteWritePreview,
)
from research.ResearchSourceComparisonPreview import ResearchSourceComparisonPreview
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRecord import ResearchSourceRecord



def _configure_source_judgement(
    window: Any,
    usefulness: str = "unknown",
    applicability: str = "unknown",
    independence: str = "unknown",
    publication_status: str = "unknown",
) -> None:
    """Attach the four structured judgement inputs the assessment form reads.

    They default to `unknown` because that is what an operator who answered
    nothing has said. A fixture that defaulted them to a favourable value would
    make every unrelated assessment test quietly assert a judgement.
    """
    window._research_source_usefulness = RecordingInput(usefulness)
    window._research_source_applicability = RecordingInput(applicability)
    window._research_source_independence = RecordingInput(independence)
    window._research_source_publication_status = RecordingInput(publication_status)


ASSESSMENT_NOW = datetime(2026, 8, 21, tzinfo=UTC)


def _research_run_with(
    sources: tuple = (),
    assessments: tuple = (),
    discoveries: tuple = (),
) -> ResearchRun:
    """Build the smallest run that can carry a source and a judgement about it."""
    return ResearchRun(
        run_id="run-1",
        question="request smuggling",
        status=ResearchRunStatus.COLLECTING,
        sources=sources,
        failures=(),
        created_at=ASSESSMENT_NOW,
        updated_at=ASSESSMENT_NOW,
        discoveries=discoveries,
        # A judgement has to name evidence the run actually recorded, so a run
        # carrying one has to carry that evidence too.
        evidence=(
            ()
            if not assessments
            else (
                ResearchEvidenceRecord(
                    evidence_id="evidence-1",
                    source_document_id="document-1",
                    chunk_id="chunk-1",
                    chunk_index=0,
                    excerpt="Body text.",
                    excerpt_truncated=False,
                    chunk_sha256=sha256(b"Body text.").hexdigest(),
                    note="A note.",
                    recorded_at=ASSESSMENT_NOW,
                ),
            )
        ),
        assessments=assessments,
    )

class AccessibilityPreferenceTests(unittest.TestCase):
    def test_initial_window_prefers_1920_by_1080(self) -> None:
        self.assertEqual(_initial_window_size(1920, 1080), (1920, 1080))
        self.assertEqual(_initial_window_size(2560, 1440), (1920, 1080))

    def test_initial_window_fits_smaller_screen(self) -> None:
        self.assertEqual(_initial_window_size(1366, 768), (1366, 768))

    def test_initial_window_rejects_invalid_screen_dimensions(self) -> None:
        for dimensions in ((0, 1080), (1920, 0), (True, 1080), (1920, False)):
            with self.subTest(dimensions=dimensions):
                with self.assertRaisesRegex(
                    ValueError,
                    "Screen dimensions must be positive integers",
                ):
                    _initial_window_size(*dimensions)

    def test_text_size_adjustments_remain_within_a_readable_range(self) -> None:
        self.assertEqual(_next_font_size(12, 1), 13)
        self.assertEqual(_next_font_size(10, -1), 10)
        self.assertEqual(_next_font_size(20, 1), 20)

    def test_high_contrast_palette_uses_explicit_readable_colors(self) -> None:
        palette = _accessibility_palette(DesktopTheme.HIGH_CONTRAST)

        self.assertEqual(palette.background, "#000000")
        self.assertEqual(palette.foreground, "#FFFFFF")
        self.assertEqual(palette.field_background, "#000000")
        self.assertNotEqual(palette.selection_background, palette.background)
        self.assertNotEqual(palette.focus_color, palette.background)

    def test_eye_comfort_palette_avoids_pure_black_and_white(self) -> None:
        palette = _accessibility_palette(DesktopTheme.EYE_COMFORT)

        self.assertEqual(palette.background, "#20242B")
        self.assertEqual(palette.field_background, "#2B313A")
        self.assertNotEqual(palette.background, "#000000")
        self.assertNotEqual(palette.foreground, "#FFFFFF")
        self.assertNotEqual(palette.button_background, palette.field_background)
        self.assertNotEqual(palette.border_color, palette.background)

    def test_unknown_theme_falls_back_to_eye_comfort(self) -> None:
        self.assertEqual(
            _accessibility_palette("unknown"),
            _accessibility_palette(DesktopTheme.EYE_COMFORT),
        )

    def test_research_workflow_tabs_present_four_ordered_user_steps(self) -> None:
        self.assertEqual(
            _RESEARCH_WORKFLOW_TAB_TITLES,
            (
                "1  Overview",
                "2  Sources & evidence",
                "3  Authored analysis",
                "4  Review & export",
            ),
        )
        self.assertEqual(len(set(_RESEARCH_WORKFLOW_TAB_TITLES)), 4)
        self.assertEqual(
            _RESEARCH_ANALYSIS_TAB_TITLES,
            (
                "Saved records",
                "Comparison",
                "Assessment",
                "Claims & contradictions",
                "Plan draft",
            ),
        )
        self.assertEqual(len(set(_RESEARCH_ANALYSIS_TAB_TITLES)), 5)

    def test_selected_research_context_keeps_exact_run_id_and_bounds_question(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        run = ResearchRun(
            "run-exact-123",
            "Q" * 120,
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )

        context = TkinterDesktopWindow._research_run_context_text(run)

        self.assertEqual(
            context,
            f"Working on: {'Q' * 77}... [collecting] — run-exact-123",
        )

    def test_selected_research_progress_reports_complete_snapshot_counts(
        self,
    ) -> None:
        run = Mock(spec=ResearchRun)
        run.sources = (object(), object())
        run.evidence = (object(), object(), object())
        run.claims = (object(), object(), object(), object())

        progress = TkinterDesktopWindow._research_run_progress_text(run)

        self.assertEqual(progress, "Sources: 2 · Evidence: 3 · Claims: 4")

    def test_research_workflow_snapshot_reports_all_existing_stage_records(
        self,
    ) -> None:
        run = Mock(spec=ResearchRun)
        run.sources = (object(), object())
        run.evidence = (object(), object(), object())
        run.assessments = (object(),)
        run.comparison_notes = (object(), object())
        run.claims = (object(), object(), object(), object())
        run.claim_contradictions = (object(),)
        run.status = ResearchRunStatus.COLLECTING

        snapshot = TkinterDesktopWindow._research_workflow_snapshot_text(run)

        self.assertEqual(
            snapshot,
            "Sources & evidence — Sources: 2 · Evidence: 3 | "
            "Authored analysis — Assessments: 1 · Comparison notes: 2 · "
            "Claims: 4 · Contradictions: 1 | "
            "Review & export — Status: collecting",
        )

    def test_research_evidence_coverage_counts_each_source_once(self) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        first_source = _research_source_record("document-1", "First")
        second_source = _research_source_record("document-2", "Second")
        third_source = _research_source_record("document-3", "Third")
        run = ResearchRun(
            "run-coverage",
            "Inspect evidence coverage",
            ResearchRunStatus.COLLECTING,
            (first_source, second_source, third_source),
            (),
            now,
            now,
            evidence=(
                _research_evidence_record("evidence-1", "document-1", "One"),
                _research_evidence_record("evidence-2", "document-1", "Two"),
                _research_evidence_record("evidence-3", "document-2", "Three"),
            ),
        )

        self.assertEqual(
            TkinterDesktopWindow._research_evidence_coverage_text(run),
            "Evidence coverage — Accepted sources: 3 · With evidence: 2 · "
            "Without evidence: 1",
        )

    def test_empty_research_evidence_coverage_has_complete_zero_counts(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        run = ResearchRun(
            "run-empty-coverage",
            "Inspect empty coverage",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )

        self.assertEqual(
            TkinterDesktopWindow._research_evidence_coverage_text(run),
            "Evidence coverage — Accepted sources: 0 · With evidence: 0 · "
            "Without evidence: 0",
        )

    def test_research_evidence_coverage_ignores_foreign_malformed_record(
        self,
    ) -> None:
        run = Mock(spec=ResearchRun)
        run.sources = (_research_source_record("document-1", "Accepted"),)
        run.evidence = (
            _research_evidence_record("evidence-1", "document-1", "Accepted"),
            _research_evidence_record("evidence-2", "foreign", "Foreign"),
        )

        self.assertEqual(
            TkinterDesktopWindow._research_evidence_coverage_text(run),
            "Evidence coverage — Accepted sources: 1 · With evidence: 1 · "
            "Without evidence: 0",
        )

    def test_research_assessment_coverage_counts_only_current_sources_once(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        first_source = _research_source_record("document-1", "First")
        second_source = _research_source_record("document-2", "Second")
        third_source = _research_source_record("document-3", "Third")
        first_evidence = _research_evidence_record(
            "evidence-1", "document-1", "First evidence"
        )
        second_evidence = _research_evidence_record(
            "evidence-2", "document-2", "Second evidence"
        )
        original = _research_assessment_record(
            "assessment-1",
            "document-1",
            "evidence-1",
            "Original assessment",
        )
        correction = _research_assessment_record(
            "assessment-2",
            "document-1",
            "evidence-1",
            "Corrected assessment",
            supersedes_assessment_id=original.assessment_id,
        )
        second_assessment = _research_assessment_record(
            "assessment-3",
            "document-2",
            "evidence-2",
            "Second assessment",
        )
        repeated_current_source = _research_assessment_record(
            "assessment-4",
            "document-2",
            "evidence-2",
            "Another current assessment for the same source",
        )
        run = ResearchRun(
            "run-assessment-coverage",
            "Inspect assessment coverage",
            ResearchRunStatus.COLLECTING,
            (first_source, second_source, third_source),
            (),
            now,
            now,
            evidence=(first_evidence, second_evidence),
            assessments=(
                original,
                correction,
                second_assessment,
                repeated_current_source,
            ),
        )

        self.assertEqual(
            TkinterDesktopWindow._research_assessment_coverage_text(run),
            "Assessment coverage — Accepted sources: 3 · "
            "With current assessment: 2 · Without current assessment: 1",
        )

    def test_empty_research_assessment_coverage_has_complete_zero_counts(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        run = ResearchRun(
            "run-empty-assessment-coverage",
            "Inspect empty assessment coverage",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )

        self.assertEqual(
            TkinterDesktopWindow._research_assessment_coverage_text(run),
            "Assessment coverage — Accepted sources: 0 · "
            "With current assessment: 0 · Without current assessment: 0",
        )

    def test_research_assessment_coverage_ignores_superseded_only_and_foreign(
        self,
    ) -> None:
        original = _research_assessment_record(
            "assessment-1",
            "document-1",
            "evidence-1",
            "Original assessment",
        )
        malformed_foreign_correction = _research_assessment_record(
            "assessment-2",
            "foreign",
            "evidence-2",
            "Foreign correction",
            supersedes_assessment_id=original.assessment_id,
        )
        run = Mock(spec=ResearchRun)
        run.sources = (_research_source_record("document-1", "Accepted"),)
        run.assessments = (original, malformed_foreign_correction)

        self.assertEqual(
            TkinterDesktopWindow._research_assessment_coverage_text(run),
            "Assessment coverage — Accepted sources: 1 · "
            "With current assessment: 0 · Without current assessment: 1",
        )

    def test_selected_source_summary_counts_exact_records_and_corrections(
        self,
    ) -> None:
        source = _research_source_record("document-1", "Accepted")
        original = _research_assessment_record(
            "assessment-1",
            source.document_id,
            "evidence-1",
            "Original assessment",
        )
        correction = _research_assessment_record(
            "assessment-2",
            source.document_id,
            "evidence-1",
            "Corrected assessment",
            supersedes_assessment_id=original.assessment_id,
        )
        run = Mock(spec=ResearchRun)
        run.run_id = "run-123"
        run.sources = (source,)
        run.evidence = (
            _research_evidence_record("evidence-1", source.document_id, "First"),
            _research_evidence_record("evidence-2", source.document_id, "Second"),
            _research_evidence_record("evidence-3", "foreign", "Foreign"),
        )
        run.assessments = (
            original,
            correction,
            _research_assessment_record(
                "assessment-foreign",
                "foreign",
                "evidence-3",
                "Foreign assessment",
            ),
        )

        self.assertEqual(
            TkinterDesktopWindow._research_selected_source_summary_text(run, source),
            "Selected source — Accepted · Source ID: document-1 · "
            "Run ID: run-123\nSafety boundary — "
            "Data taint: external_untrusted_data · Instruction authority: none\n"
            "Records — Evidence: 2 · Assessments: 2 history / 1 current · "
            "Evidence cited by current: 1 of 2\nCurrent information trust — "
            "Unassessed: 1 · Low: 0 · Medium: 0 · High: 0",
        )

    def test_selected_source_summary_reports_complete_zero_counts(self) -> None:
        source = _research_source_record(
            "document-1",
            "  Accepted\nsource\t title  ",
        )
        run = Mock(spec=ResearchRun)
        run.run_id = "run-123"
        run.sources = (source,)
        run.evidence = ()
        run.assessments = ()

        self.assertEqual(
            TkinterDesktopWindow._research_selected_source_summary_text(run, source),
            "Selected source — Accepted source title · Source ID: document-1 · "
            "Run ID: run-123\nSafety boundary — "
            "Data taint: external_untrusted_data · Instruction authority: none\n"
            "Records — Evidence: 0 · Assessments: 0 history / 0 current · "
            "Evidence cited by current: 0 of 0\nCurrent information trust — "
            "Unassessed: 0 · Low: 0 · Medium: 0 · High: 0",
        )

    def test_selected_source_summary_keeps_none_authority_for_high_trust(
        self,
    ) -> None:
        source = _research_source_record("document-1", "Accepted")
        evidence = _research_evidence_record(
            "evidence-1",
            source.document_id,
            "Explicit evidence",
        )
        assessment = ResearchSourceAssessmentRecord(
            assessment_id="assessment-1",
            source_document_id=source.document_id,
            evidence_ids=(evidence.evidence_id,),
            text="User-authored high information trust",
            recorded_at=datetime(2026, 8, 21, tzinfo=UTC),
            information_trust=ResearchInformationTrust.HIGH,
        )
        run = Mock(spec=ResearchRun)
        run.run_id = "run-123"
        run.sources = (source,)
        run.evidence = (evidence,)
        run.assessments = (assessment,)

        summary = TkinterDesktopWindow._research_selected_source_summary_text(
            run,
            source,
        )

        self.assertIn("Data taint: external_untrusted_data", summary)
        self.assertIn("Instruction authority: none", summary)
        self.assertIn("Assessments: 1 history / 1 current", summary)
        self.assertIn("Unassessed: 0 · Low: 0 · Medium: 0 · High: 1", summary)
        self.assertIn("Evidence cited by current: 1 of 1", summary)
        self.assertNotIn("Instruction authority: high", summary)

    def test_selected_source_summary_counts_only_current_information_trust(
        self,
    ) -> None:
        source = _research_source_record("document-1", "Accepted")
        evidence = _research_evidence_record(
            "evidence-1",
            source.document_id,
            "Explicit evidence",
        )
        original = _research_assessment_record(
            "assessment-1",
            source.document_id,
            evidence.evidence_id,
            "Original high-trust assessment",
            information_trust=ResearchInformationTrust.HIGH,
        )
        correction = _research_assessment_record(
            "assessment-2",
            source.document_id,
            evidence.evidence_id,
            "Corrected low-trust assessment",
            supersedes_assessment_id=original.assessment_id,
            information_trust=ResearchInformationTrust.LOW,
        )
        medium = _research_assessment_record(
            "assessment-3",
            source.document_id,
            evidence.evidence_id,
            "Independent medium-trust assessment",
            information_trust=ResearchInformationTrust.MEDIUM,
        )
        foreign = _research_assessment_record(
            "assessment-foreign",
            "foreign",
            "evidence-foreign",
            "Foreign high-trust assessment",
            information_trust=ResearchInformationTrust.HIGH,
        )
        run = Mock(spec=ResearchRun)
        run.run_id = "run-123"
        run.sources = (source,)
        run.evidence = (evidence,)
        run.assessments = (original, correction, medium, foreign)

        summary = TkinterDesktopWindow._research_selected_source_summary_text(
            run,
            source,
        )

        self.assertIn("Assessments: 3 history / 2 current", summary)
        self.assertIn("Unassessed: 0 · Low: 1 · Medium: 1 · High: 0", summary)

    def test_selected_source_summary_counts_unique_current_assessment_evidence(
        self,
    ) -> None:
        source = _research_source_record("document-1", "Accepted")
        evidence = tuple(
            _research_evidence_record(
                f"evidence-{index}",
                source.document_id,
                f"Evidence {index}",
            )
            for index in range(1, 4)
        )
        original = ResearchSourceAssessmentRecord(
            assessment_id="assessment-1",
            source_document_id=source.document_id,
            evidence_ids=(evidence[0].evidence_id, evidence[1].evidence_id),
            text="Original assessment",
            recorded_at=datetime(2026, 8, 21, tzinfo=UTC),
        )
        correction = ResearchSourceAssessmentRecord(
            assessment_id="assessment-2",
            source_document_id=source.document_id,
            evidence_ids=(evidence[1].evidence_id,),
            text="Corrected assessment",
            recorded_at=datetime(2026, 8, 21, tzinfo=UTC),
            supersedes_assessment_id=original.assessment_id,
        )
        current = ResearchSourceAssessmentRecord(
            assessment_id="assessment-3",
            source_document_id=source.document_id,
            evidence_ids=(evidence[1].evidence_id, evidence[2].evidence_id),
            text="Independent assessment",
            recorded_at=datetime(2026, 8, 21, tzinfo=UTC),
        )
        malformed_unknown = ResearchSourceAssessmentRecord(
            assessment_id="assessment-4",
            source_document_id=source.document_id,
            evidence_ids=("evidence-unknown",),
            text="Malformed unknown evidence reference",
            recorded_at=datetime(2026, 8, 21, tzinfo=UTC),
        )
        foreign = _research_assessment_record(
            "assessment-foreign",
            "foreign",
            "evidence-foreign",
            "Foreign assessment",
        )
        run = Mock(spec=ResearchRun)
        run.run_id = "run-123"
        run.sources = (source,)
        run.evidence = (
            *evidence,
            _research_evidence_record(
                "evidence-foreign",
                "foreign",
                "Foreign evidence",
            ),
        )
        run.assessments = (
            original,
            correction,
            current,
            malformed_unknown,
            foreign,
        )

        summary = TkinterDesktopWindow._research_selected_source_summary_text(
            run,
            source,
        )

        self.assertIn("Evidence cited by current: 2 of 3", summary)

    def test_selected_source_summary_rejects_noncanonical_source_record(
        self,
    ) -> None:
        accepted = _research_source_record("document-1", "Accepted")
        changed_copy = _research_source_record("document-1", "Changed title")
        run = Mock(spec=ResearchRun)
        run.run_id = "run-123"
        run.sources = (accepted,)
        run.evidence = ()
        run.assessments = ()

        self.assertEqual(
            TkinterDesktopWindow._research_selected_source_summary_text(
                run,
                changed_copy,
            ),
            "Selected-source records unavailable until an accepted source is selected.",
        )

    def test_selected_source_title_is_normalized_and_bounded(self) -> None:
        source = _research_source_record(
            "document-1",
            f"  {'T' * 76}\nmore title text  ",
        )

        title = TkinterDesktopWindow._bounded_research_source_title(source)

        self.assertEqual(title, f"{'T' * 76} ...")
        self.assertEqual(len(title), 80)

    def test_selected_source_details_show_safe_timezone_aware_provenance(
        self,
    ) -> None:
        fetched = datetime(2026, 8, 21, 10, 11, 12, 345678, tzinfo=UTC)
        accepted = datetime(2026, 8, 21, 13, 14, 15, 987654, tzinfo=UTC)
        source = ResearchSourceRecord(
            "document-1",
            "https://secret.example/source-path",
            "  Accepted\nsource  ",
            "Text/Plain",
            fetched,
            accepted,
        )
        run = Mock(spec=ResearchRun)
        run.run_id = "run-123"
        run.sources = (source,)

        details = TkinterDesktopWindow._research_source_details_text(run, source)

        self.assertEqual(
            details,
            "Title: Accepted source\n"
            "Document ID: document-1\n"
            "Run ID: run-123\n"
            "Content type: text/plain\n"
            "Fetched: 2026-08-21T10:11:12+00:00\n"
            "Accepted: 2026-08-21T13:14:15+00:00",
        )
        self.assertNotIn(source.url, details or "")

    def test_selected_source_details_reject_noncanonical_record(self) -> None:
        accepted = _research_source_record("document-1", "Accepted")
        changed_copy = _research_source_record("document-1", "Changed title")
        run = Mock(spec=ResearchRun)
        run.run_id = "run-123"
        run.sources = (accepted,)

        self.assertIsNone(
            TkinterDesktopWindow._research_source_details_text(run, changed_copy)
        )

    def test_show_selected_source_details_is_read_only_and_local(self) -> None:
        source = _research_source_record("document-1", "Accepted")
        now = datetime(2026, 8, 21, tzinfo=UTC)
        run = ResearchRun(
            "run-123",
            "Inspect safe provenance",
            ResearchRunStatus.COLLECTING,
            (source,),
            (),
            now,
            now,
        )
        window: Any = object.__new__(TkinterDesktopWindow)
        window._root = object()
        window._controller = Mock()
        window._research_run_id = RecordingVariable(run.run_id)
        window._research_source_run_id = run.run_id
        window._research_runs = (run,)
        window._research_sources = (source,)
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_assessment_text = RecordingVariable("authored")
        window._status = RecordingStatus()
        expected = window._research_source_details_text(run, source)

        with patch("desktop.TkinterDesktopWindow.messagebox.showinfo") as show_details:
            window._show_selected_research_source_details()

        show_details.assert_called_once_with(
            "Selected source details",
            expected,
            parent=window._root,
        )
        self.assertEqual(window._research_assessment_text.value, "authored")
        self.assertEqual(
            window._status.values,
            ["accepted source details shown: document-1; no action started"],
        )
        window._controller.assert_not_called()

    def test_show_selected_source_details_without_selection_opens_nothing(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_id = RecordingVariable("run-123")
        window._research_source_run_id = "run-123"
        window._research_runs = ()
        window._research_sources = ()
        window._research_source_selector = RecordingCandidateSelector()
        window._status = RecordingStatus()

        with patch("desktop.TkinterDesktopWindow.messagebox.showinfo") as show_details:
            window._show_selected_research_source_details()

        show_details.assert_not_called()
        self.assertEqual(window._status.values, ["Select an accepted source first."])

    def test_research_run_metadata_is_timezone_aware_and_hides_failure_detail(
        self,
    ) -> None:
        created = datetime(2026, 8, 22, 8, 1, 2, 345678, tzinfo=UTC)
        updated = datetime(2026, 8, 22, 9, 3, 4, 987654, tzinfo=UTC)
        failure = ResearchFailureRecord(
            "source_fetch",
            "Safe detail that must not be presented here.",
            updated,
        )
        run = ResearchRun(
            "run-metadata",
            "Inspect metadata",
            ResearchRunStatus.COLLECTING,
            (),
            (failure,),
            created,
            updated,
        )

        metadata = TkinterDesktopWindow._research_run_metadata_text(run)

        self.assertEqual(
            metadata,
            "Run metadata — Created: 2026-08-22T08:01:02+00:00 · "
            "Updated: 2026-08-22T09:03:04+00:00 · Safe failures: 1",
        )
        self.assertNotIn(failure.stage, metadata)
        self.assertNotIn(failure.reason, metadata)

    def test_window_applies_text_size_and_high_contrast_to_text_controls(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._font_size = 18
        window._theme_mode = RecordingVariable(DesktopTheme.HIGH_CONTRAST.value)
        window._font_size_label = RecordingStatus()
        window._root = RecordingWidget()
        window._style = RecordingStyle()
        window._session_list = RecordingWidget()
        window._transcript = RecordingWidget()
        window._composer = RecordingWidget()
        window._research_plan_instructions = RecordingWidget()
        window._research_plan_source_ids = RecordingWidget()
        window._research_plan_preview = RecordingWidget()

        window._apply_accessibility_preferences()

        self.assertEqual(window._font_size_label.values, ["Text size: 18 pt"])
        self.assertEqual(window._root.configurations["background"], "#000000")
        self.assertEqual(
            window._session_list.configurations["font"], ("TkDefaultFont", 18)
        )
        self.assertEqual(window._composer.configurations["foreground"], "#FFFFFF")
        self.assertEqual(
            window._research_plan_preview.configurations["background"],
            "#000000",
        )
        self.assertEqual(
            window._research_plan_instructions.configurations["font"],
            ("TkDefaultFont", 18),
        )
        self.assertIn("TButton", window._style.configurations)
        self.assertIn("TEntry", window._style.mappings)
        self.assertIn("TCombobox", window._style.configurations)
        self.assertIn("TNotebook.Tab", window._style.mappings)


class ResearchPlanDesktopPreviewTests(unittest.TestCase):
    def test_editor_sends_exact_fields_and_shows_complete_runtime_rejection(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = Mock(spec=DesktopController)
        response = BrainResponse(
            message=(
                "Research plan draft rejected:\n"
                "Reason: Research plan step instruction cannot be empty.\n"
                "No plan was written or executed."
            ),
            request_id="plan-preview-1",
            intent="research_plan_draft_preview",
            memory_count=0,
            success=False,
        )
        controller.preview_research_plan_draft.return_value = response
        instruction_editor = Mock()
        instruction_editor.get.return_value = "Review evidence.\n"
        source_editor = Mock()
        source_editor.get.return_value = "document-2, document-1\n"
        preview_output = Mock()
        appended: list[BrainResponse] = []
        request_labels: list[str] = []
        window._controller = controller
        window._research_question = RecordingInput("Compare findings.")
        window._research_plan_instructions = instruction_editor
        window._research_plan_source_ids = source_editor
        window._research_plan_preview = preview_output
        window._append_response = appended.append

        def start_request(
            action: Callable[[], BrainResponse],
            on_success: Callable[[BrainResponse], None],
            label: str,
        ) -> None:
            request_labels.append(label)
            on_success(action())

        window._start_request = start_request

        window._preview_research_plan_draft()

        controller.preview_research_plan_draft.assert_called_once_with(
            "Compare findings.",
            "Review evidence.\n",
            "document-2, document-1\n",
        )
        self.assertEqual(request_labels, ["research plan preview"])
        instruction_editor.get.assert_called_once_with("1.0", "end-1c")
        source_editor.get.assert_called_once_with("1.0", "end-1c")
        preview_output.delete.assert_called_once_with("1.0", "end")
        preview_output.insert.assert_called_once_with("end", response.message)
        preview_output.see.assert_called_once_with("1.0")
        self.assertEqual(
            [call.kwargs["state"] for call in preview_output.configure.call_args_list],
            ["normal", "disabled"],
        )
        self.assertEqual(appended, [response])


class SessionPresentationTests(unittest.TestCase):
    def test_session_placeholder_cannot_be_selected_as_a_real_session(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._session_list = RecordingSessionList(selected_indices=(0,))
        window._session_summaries = []
        window._session_id = RecordingVariable("")

        window._choose_session(None)

        self.assertEqual(window._session_id.value, "")

    def test_empty_and_failed_session_views_explain_what_happened(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        session_list = RecordingSessionList()
        window._session_list = session_list
        window._session_summaries = []
        empty = BrainResponse(
            message="No sessions.",
            request_id="empty-sessions",
            intent="session_overview",
            memory_count=0,
        )

        window._render_session_summaries(empty)

        self.assertEqual(session_list.items, ["No saved sessions yet."])

        failed = BrainResponse(
            message="Unavailable.",
            request_id="failed-sessions",
            intent="session_overview",
            memory_count=0,
            success=False,
        )
        window._render_session_summaries(failed)

        self.assertEqual(session_list.items, ["Sessions are currently unavailable."])


class RecordingBoolean:
    def __init__(self, value: bool) -> None:
        self._value = value

    def get(self) -> bool:
        return self._value


class RecordingWidget:
    def __init__(self) -> None:
        self.configurations: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.configurations.update(kwargs)


class RecordingStyle:
    def __init__(self) -> None:
        self.configurations: dict[str, dict[str, object]] = {}
        self.mappings: dict[str, dict[str, object]] = {}

    def configure(self, style_name: str, **kwargs: object) -> None:
        self.configurations[style_name] = kwargs

    def map(self, style_name: str, **kwargs: object) -> None:
        self.mappings[style_name] = kwargs


class CitationFormattingTests(unittest.TestCase):
    def test_formats_existing_citations_in_response_order(self) -> None:
        citations = [
            KnowledgeCitation(
                document_id="project-notes",
                document_title="Project Notes",
                source="C:/knowledge/project.md",
                chunk_index=2,
                chunk_id="project-notes:2",
            ),
            KnowledgeCitation(
                document_id="ideas",
                document_title="Ideas",
                source="C:/knowledge/ideas.txt",
                chunk_index=0,
                chunk_id="ideas:0",
            ),
        ]

        rendered = _format_citations(citations)

        self.assertEqual(
            rendered,
            "1. Project Notes — C:/knowledge/project.md "
            "(paragraph 3; project-notes:2)\n"
            "2. Ideas — C:/knowledge/ideas.txt (paragraph 1; ideas:0)",
        )

    def test_uses_a_safe_source_fallback_and_keeps_empty_responses_empty(self) -> None:
        citation = KnowledgeCitation(
            document_id="untitled",
            document_title="(untitled)",
            source="",
            chunk_index=0,
            chunk_id="untitled:0",
        )

        self.assertEqual(_format_citations([]), "")
        self.assertEqual(
            _format_citations([citation]),
            "1. (untitled) — local source unavailable (paragraph 1; untitled:0)",
        )


class LocalKnowledgeFileSelectionTests(unittest.TestCase):
    def test_selected_file_is_passed_to_the_existing_controller_boundary(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingKnowledgeLoadController()
        responses: list[BrainResponse] = []
        window._root = object()
        window._controller = controller
        window._status = RecordingStatus()
        window._append_response = responses.append

        with patch(
            "desktop.TkinterDesktopWindow.filedialog.askopenfilename",
            return_value="C:/Local Notes/project plan.md",
        ) as choose_file:
            window._load_knowledge()

        self.assertEqual(controller.paths, ["C:/Local Notes/project plan.md"])
        self.assertEqual(responses, [controller.response])
        self.assertEqual(
            choose_file.call_args.kwargs["title"],
            "Load local knowledge source",
        )
        self.assertEqual(
            choose_file.call_args.kwargs["filetypes"][0],
            ("Knowledge files", "*.md *.txt"),
        )

    def test_cancelled_file_selection_does_not_call_the_controller(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingKnowledgeLoadController()
        status = RecordingStatus()
        window._root = object()
        window._controller = controller
        window._status = status
        window._append_response = lambda _response: self.fail("must not append")

        with patch(
            "desktop.TkinterDesktopWindow.filedialog.askopenfilename",
            return_value="",
        ):
            window._load_knowledge()

        self.assertEqual(controller.paths, [])
        self.assertEqual(status.values, ["knowledge load: cancelled"])


class ResearchContentStatusTests(unittest.TestCase):
    def test_status_button_appends_the_controller_response(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchContentStatusController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._append_response = responses.append

        window._show_research_content_status()

        self.assertEqual(controller.calls, 1)
        self.assertEqual(responses, [controller.response])

    def test_evidence_integrity_button_appends_the_controller_response(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchContentStatusController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._append_response = responses.append

        window._show_research_evidence_integrity()

        self.assertEqual(controller.evidence_calls, 1)
        self.assertEqual(responses, [controller.evidence_response])


class InternetResearchSourceSelectionTests(unittest.TestCase):
    def test_entered_url_is_passed_to_the_existing_controller_boundary(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_url = RecordingInput("https://example.com/research")
        window._research_run_id = RecordingInput("run-123")
        window._status = RecordingStatus()
        window._append_response = responses.append
        _configure_request_boundary(window)

        window._load_research_source()
        window._poll_requests()

        self.assertEqual(
            controller.sources,
            [("https://example.com/research", "run-123")],
        )
        self.assertEqual(len(controller.source_cancellation_tokens), 1)
        self.assertIsNotNone(controller.source_cancellation_tokens[0])
        self.assertEqual(responses, [controller.response])

    def test_empty_url_stays_local_and_is_shown_as_status(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._controller = controller
        window._research_url = RecordingInput("  ")
        window._research_run_id = RecordingInput("")
        window._status = status
        window._append_response = lambda _response: self.fail("must not append")
        _configure_request_boundary(window)

        window._load_research_source()
        window._poll_requests()

        self.assertEqual(controller.sources, [])
        self.assertEqual(status.values[-1], "A research source URL cannot be empty.")

    def test_created_run_identifier_is_selected_for_the_next_source(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        run_id = RecordingVariable("")
        window._controller = controller
        window._research_question = RecordingInput("Compare local models")
        window._research_run_id = run_id
        window._research_run_choice = RecordingVariable("")
        window._research_run_summary = RecordingVariable("Old summary")
        window._research_run_context = RecordingVariable("Old context")
        window._research_run_progress = RecordingVariable("Old progress")
        window._research_workflow_snapshot = RecordingVariable("Old workflow")
        window._research_evidence_coverage = RecordingVariable("Old coverage")
        window._research_assessment_coverage = RecordingVariable("Old assessment")
        window._research_run_metadata = RecordingVariable("Old metadata")
        window._research_run_filter = RecordingVariable("old filter")
        window._research_run_filter_summary = RecordingVariable("old filter summary")
        window._research_run_status_filter = RecordingVariable("old status")
        window._research_run_catalog_summary = RecordingVariable("old catalog")
        window._research_run_sort = RecordingVariable(
            ResearchRunSort.UPDATED_NEWEST.value
        )
        window._research_run_sort_summary = RecordingVariable("")
        window._research_run_selector = RecordingCandidateSelector()
        window._research_runs = ()
        window._visible_research_runs = ()
        window._research_source_choice = RecordingVariable("old source")
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_sources = ()
        window._research_source_run_id = "old-run"
        _configure_research_evidence_selector(window)
        window._research_candidate = RecordingVariable("old candidate")
        window._research_candidate_selector = RecordingCandidateSelector(
            selected_index=0
        )
        window._research_candidates = (
            ResearchSourceCandidate(
                url="https://doi.org/10.1000/old",
                title="Old paper",
                snippet="",
            ),
        )
        window._research_candidate_run_id = "old-run"
        window._research_claim_contradiction_proposal = RecordingVariable(
            "old proposal"
        )
        window._research_claim_contradiction_proposal_selector = (
            RecordingCandidateSelector(selected_index=0)
        )
        window._research_claim_contradiction_proposal_run_id = "old-run"
        window._research_claim_contradiction_proposals = ()
        window._research_markdown_export_preview = object()
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._create_research_run()

        self.assertEqual(controller.questions, ["Compare local models"])
        self.assertEqual(run_id.value, "run-123")
        self.assertEqual(window._research_candidates, ())
        self.assertEqual(window._research_candidate_run_id, "")
        self.assertEqual(
            window._research_run_selector.values,
            ("Compare local models [collecting] — run-123",),
        )
        self.assertEqual(window._research_run_selector.current(), 0)
        self.assertEqual(
            window._research_run_catalog_summary.value,
            "Loaded catalog: All 1 · Collecting 1 · Completed 0 · "
            "Failed 0 · Cancelled 0",
        )
        self.assertEqual(
            window._research_run_summary.value,
            "Status: collecting · Sources: 0 · Evidence: 0 · Claims: 0",
        )
        self.assertEqual(
            window._research_evidence_coverage.value,
            "Evidence coverage — Accepted sources: 0 · With evidence: 0 · "
            "Without evidence: 0",
        )
        self.assertEqual(
            window._research_assessment_coverage.value,
            "Assessment coverage — Accepted sources: 0 · "
            "With current assessment: 0 · Without current assessment: 0",
        )
        self.assertEqual(
            window._research_source_coverage_filter.value,
            ResearchSourceCoverageFacet.ALL.value,
        )
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "No accepted sources are available.",
        )
        self.assertEqual(
            window._research_source_catalog_summary.value,
            "Accepted-source coverage — All: 0 · Without evidence: 0 · "
            "Without current assessment: 0",
        )
        self.assertIsNone(window._research_markdown_export_preview)
        self.assertEqual(responses, [controller.create_response])

    def test_research_run_catalog_is_requested_without_network_fetch(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._append_response = responses.append
        window._research_run_id = RecordingVariable("")
        window._research_run_choice = RecordingVariable("")
        window._research_run_summary = RecordingVariable("")
        window._research_run_context = RecordingVariable("")
        window._research_run_progress = RecordingVariable("")
        window._research_workflow_snapshot = RecordingVariable("")
        window._research_evidence_coverage = RecordingVariable("")
        window._research_assessment_coverage = RecordingVariable("")
        window._research_run_metadata = RecordingVariable("")
        window._research_run_filter = RecordingVariable("old filter")
        window._research_run_filter_summary = RecordingVariable("")
        window._research_run_sort = RecordingVariable(
            ResearchRunSort.UPDATED_NEWEST.value
        )
        window._research_run_status_filter = RecordingVariable(
            ResearchRunStatusFacet.ALL.value
        )
        window._research_run_catalog_summary = RecordingVariable("")
        window._research_run_sort_summary = RecordingVariable("")
        window._research_run_selector = RecordingCandidateSelector()
        window._research_runs = ()
        window._visible_research_runs = ()
        window._research_source_choice = RecordingVariable("")
        window._research_source_selector = RecordingCandidateSelector()
        window._research_sources = ()
        window._research_source_run_id = ""
        _configure_research_evidence_selector(window)
        window._research_candidate = RecordingVariable("")
        window._research_candidate_selector = RecordingCandidateSelector()
        window._research_candidates = ()
        window._research_candidate_run_id = ""
        window._research_candidate_discovery_id = ""
        window._research_claim_contradiction_proposal = RecordingVariable("")
        window._research_claim_contradiction_proposal_selector = (
            RecordingCandidateSelector()
        )
        window._research_claim_contradiction_proposal_run_id = ""
        window._research_claim_contradiction_proposals = ()
        window._research_markdown_export_preview = None
        window._status = RecordingStatus()

        window._show_research_runs()

        self.assertEqual(controller.list_calls, 1)
        self.assertEqual(controller.sources, [])
        self.assertEqual(responses, [controller.list_response])
        self.assertEqual(window._research_run_id.value, "run-123")
        self.assertEqual(
            window._research_run_catalog_summary.value,
            "Loaded catalog: All 1 · Collecting 1 · Completed 0 · "
            "Failed 0 · Cancelled 0",
        )
        self.assertEqual(
            window._research_run_selector.values,
            ("Compare local models [collecting] — run-123",),
        )
        self.assertEqual(
            window._status.values,
            ["research run selected: run-123; no action started"],
        )
        self.assertEqual(
            window._research_run_summary.value,
            "Status: collecting · Sources: 0 · Evidence: 0 · Claims: 0",
        )
        self.assertEqual(
            window._research_evidence_coverage.value,
            "Evidence coverage — Accepted sources: 0 · With evidence: 0 · "
            "Without evidence: 0",
        )
        self.assertEqual(
            window._research_assessment_coverage.value,
            "Assessment coverage — Accepted sources: 0 · "
            "With current assessment: 0 · Without current assessment: 0",
        )
        self.assertEqual(
            window._research_source_coverage_filter.value,
            ResearchSourceCoverageFacet.ALL.value,
        )
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "No accepted sources are available.",
        )

    def test_research_run_filter_matches_question_status_or_exact_id_only(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        first_run = ResearchRun(
            "run-alpha-123",
            "Compare local models",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )
        second_run = ResearchRun(
            "run-beta-456",
            "Review evidence quality",
            ResearchRunStatus.COMPLETED,
            (),
            (),
            now,
            now,
        )
        runs = (first_run, second_run)

        self.assertEqual(
            TkinterDesktopWindow._filter_research_runs(runs, "LOCAL"),
            (first_run,),
        )
        self.assertEqual(
            TkinterDesktopWindow._filter_research_runs(runs, "completed"),
            (second_run,),
        )
        self.assertEqual(
            TkinterDesktopWindow._filter_research_runs(runs, "RUN-BETA-456"),
            (second_run,),
        )
        self.assertEqual(
            TkinterDesktopWindow._filter_research_runs(runs, "beta-456"),
            (),
        )
        self.assertIs(
            TkinterDesktopWindow._filter_research_runs(runs, "  "),
            runs,
        )

    def test_local_research_run_filter_preserves_visible_active_selection(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 22, tzinfo=UTC)
        first_run = ResearchRun(
            "run-1",
            "First question",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )
        second_run = ResearchRun(
            "run-2",
            "Second question",
            ResearchRunStatus.COMPLETED,
            (),
            (),
            now,
            now,
        )
        window._research_run_filter = RecordingVariable("second")
        window._research_run_filter_summary = RecordingVariable("")
        window._research_run_sort = RecordingVariable(
            ResearchRunSort.UPDATED_NEWEST.value
        )
        window._research_run_status_filter = RecordingVariable(
            ResearchRunStatusFacet.ALL.value
        )
        window._research_run_id = RecordingVariable("run-2")
        window._research_run_choice = RecordingVariable("Second question")
        window._research_run_selector = RecordingCandidateSelector()
        window._research_runs = (first_run, second_run)
        window._visible_research_runs = (first_run, second_run)
        window._status = RecordingStatus()

        window._apply_research_run_filter()

        self.assertEqual(window._visible_research_runs, (second_run,))
        self.assertEqual(
            window._research_run_selector.values,
            ("Second question [completed] — run-2",),
        )
        self.assertEqual(window._research_run_selector.current(), 0)
        self.assertEqual(window._research_run_id.value, "run-2")
        self.assertEqual(
            window._research_run_filter_summary.value,
            "1 of 2 loaded research runs match (All statuses).",
        )
        self.assertEqual(
            window._status.values,
            ["research run filter: 1 of 2 shown; active run unchanged"],
        )

    def test_no_match_filter_keeps_active_run_and_authored_fields_unchanged(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 22, tzinfo=UTC)
        run = ResearchRun(
            "run-1",
            "Only question",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )
        window._research_run_filter = RecordingVariable("missing")
        window._research_run_filter_summary = RecordingVariable("")
        window._research_run_sort = RecordingVariable(
            ResearchRunSort.UPDATED_NEWEST.value
        )
        window._research_run_status_filter = RecordingVariable(
            ResearchRunStatusFacet.ALL.value
        )
        window._research_run_id = RecordingVariable("run-1")
        window._research_run_choice = RecordingVariable("Only question")
        window._research_run_selector = RecordingCandidateSelector(0)
        window._research_runs = (run,)
        window._visible_research_runs = (run,)
        window._research_assessment_text = RecordingVariable("authored assessment")
        window._research_claim_text = RecordingVariable("authored claim")
        window._status = RecordingStatus()

        window._apply_research_run_filter()

        self.assertEqual(window._visible_research_runs, ())
        self.assertEqual(window._research_run_selector.values, ())
        self.assertEqual(window._research_run_choice.value, "")
        self.assertEqual(window._research_run_id.value, "run-1")
        self.assertEqual(
            window._research_run_filter_summary.value,
            "No loaded research runs match the current filters; "
            "the active run is unchanged.",
        )
        self.assertEqual(
            window._research_assessment_text.value,
            "authored assessment",
        )
        self.assertEqual(window._research_claim_text.value, "authored claim")

        window._clear_research_run_filter()

        self.assertEqual(window._research_run_filter.value, "")
        self.assertEqual(window._visible_research_runs, (run,))
        self.assertEqual(
            window._research_run_selector.values,
            ("Only question [collecting] — run-1",),
        )
        self.assertEqual(window._research_run_selector.current(), 0)
        self.assertEqual(window._research_run_id.value, "run-1")
        self.assertEqual(
            window._research_run_filter_summary.value,
            "All 1 loaded research runs are shown.",
        )
        self.assertEqual(
            window._research_assessment_text.value,
            "authored assessment",
        )
        self.assertEqual(window._research_claim_text.value, "authored claim")

    def test_overlong_research_run_filter_leaves_loaded_view_unchanged(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_filter = RecordingVariable(
            "x" * (_MAX_RESEARCH_RUN_FILTER_LENGTH + 1)
        )
        window._research_run_filter_summary = RecordingVariable("Old summary")
        window._research_run_selector = RecordingCandidateSelector(0)
        window._research_run_selector.values = ("Existing run",)
        window._research_runs = ()
        window._visible_research_runs = ()
        window._status = RecordingStatus()

        window._apply_research_run_filter()

        self.assertEqual(window._research_run_selector.values, ("Existing run",))
        self.assertEqual(
            window._research_run_filter_summary.value,
            "Filter is too long; the loaded catalog is unchanged.",
        )
        self.assertEqual(
            window._status.values,
            ["Research run filter cannot exceed 200 characters."],
        )

    def test_research_run_status_filter_matches_each_exact_lifecycle(self) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        runs = tuple(
            ResearchRun(
                f"run-{status.value}",
                f"Question {status.value}",
                status,
                (),
                (),
                now,
                now,
            )
            for status in ResearchRunStatus
        )

        self.assertIs(
            TkinterDesktopWindow._filter_research_runs_by_status(runs, None),
            runs,
        )
        for run in runs:
            with self.subTest(status=run.status.value):
                self.assertEqual(
                    TkinterDesktopWindow._filter_research_runs_by_status(
                        runs,
                        run.status,
                    ),
                    (run,),
                )

    def test_research_run_catalog_summary_counts_every_lifecycle(self) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        runs = tuple(
            ResearchRun(
                f"run-{index}",
                f"Question {index}",
                status,
                (),
                (),
                now,
                now,
            )
            for index, status in enumerate(
                (
                    ResearchRunStatus.COMPLETED,
                    ResearchRunStatus.COLLECTING,
                    ResearchRunStatus.FAILED,
                    ResearchRunStatus.CANCELLED,
                    ResearchRunStatus.COLLECTING,
                )
            )
        )

        self.assertEqual(
            TkinterDesktopWindow._research_run_catalog_summary_text(runs),
            "Loaded catalog: All 5 · Collecting 2 · Completed 1 · "
            "Failed 1 · Cancelled 1",
        )

    def test_empty_research_run_catalog_summary_has_complete_zero_counts(
        self,
    ) -> None:
        self.assertEqual(
            TkinterDesktopWindow._research_run_catalog_summary_text(()),
            "Loaded catalog: All 0 · Collecting 0 · Completed 0 · "
            "Failed 0 · Cancelled 0",
        )

    def test_status_filter_composes_with_text_sort_and_clear(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 22, tzinfo=UTC)
        completed_alpha = ResearchRun(
            "run-1",
            "Alpha plan",
            ResearchRunStatus.COMPLETED,
            (),
            (),
            now,
            now,
        )
        completed_zulu = ResearchRun(
            "run-2",
            "Zulu review",
            ResearchRunStatus.COMPLETED,
            (),
            (),
            now,
            now,
        )
        collecting_alpha = ResearchRun(
            "run-3",
            "Alpha draft",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )
        full_catalog = (completed_zulu, collecting_alpha, completed_alpha)
        window._research_run_filter = RecordingVariable("alpha")
        window._research_run_filter_summary = RecordingVariable("")
        window._research_run_status_filter = RecordingVariable(
            ResearchRunStatusFacet.COMPLETED.value
        )
        window._research_run_catalog_summary = RecordingVariable(
            "Loaded catalog: immutable"
        )
        window._research_run_sort = RecordingVariable(ResearchRunSort.QUESTION.value)
        window._research_run_id = RecordingVariable("run-1")
        window._research_run_choice = RecordingVariable("Alpha plan")
        window._research_run_selector = RecordingCandidateSelector(0)
        window._research_runs = full_catalog
        window._visible_research_runs = full_catalog
        window._research_assessment_text = RecordingVariable("authored")
        window._status = RecordingStatus()

        window._apply_research_run_status_filter()

        self.assertIs(window._research_runs, full_catalog)
        self.assertEqual(window._visible_research_runs, (completed_alpha,))
        self.assertEqual(window._research_run_selector.current(), 0)
        self.assertEqual(window._research_run_id.value, "run-1")
        self.assertEqual(window._research_assessment_text.value, "authored")
        self.assertEqual(
            window._research_run_catalog_summary.value,
            "Loaded catalog: immutable",
        )
        self.assertEqual(
            window._research_run_filter_summary.value,
            "1 of 3 loaded research runs match (Completed).",
        )

        window._clear_research_run_filter()

        self.assertEqual(window._research_run_filter.value, "")
        self.assertEqual(
            window._research_run_status_filter.value,
            ResearchRunStatusFacet.COMPLETED.value,
        )
        self.assertEqual(
            window._visible_research_runs,
            (completed_alpha, completed_zulu),
        )
        self.assertEqual(window._research_run_selector.current(), 0)
        self.assertEqual(window._research_assessment_text.value, "authored")
        self.assertEqual(
            window._research_run_catalog_summary.value,
            "Loaded catalog: immutable",
        )
        self.assertEqual(
            window._research_run_filter_summary.value,
            "2 of 3 loaded research runs match (Completed).",
        )

    def test_status_filter_no_match_preserves_hidden_active_run_and_fields(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 22, tzinfo=UTC)
        active = ResearchRun(
            "run-1",
            "Active",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )
        window._research_run_filter = RecordingVariable("")
        window._research_run_filter_summary = RecordingVariable("")
        window._research_run_status_filter = RecordingVariable(
            ResearchRunStatusFacet.FAILED.value
        )
        window._research_run_sort = RecordingVariable(
            ResearchRunSort.UPDATED_NEWEST.value
        )
        window._research_run_id = RecordingVariable("run-1")
        window._research_run_choice = RecordingVariable("Active")
        window._research_run_selector = RecordingCandidateSelector(0)
        window._research_runs = (active,)
        window._visible_research_runs = (active,)
        window._research_claim_text = RecordingVariable("authored claim")
        window._status = RecordingStatus()

        window._apply_research_run_status_filter()

        self.assertEqual(window._visible_research_runs, ())
        self.assertEqual(window._research_run_selector.values, ())
        self.assertEqual(window._research_run_choice.value, "")
        self.assertEqual(window._research_run_id.value, "run-1")
        self.assertEqual(window._research_claim_text.value, "authored claim")
        self.assertEqual(
            window._research_run_filter_summary.value,
            "No loaded research runs match the current filters; "
            "the active run is unchanged.",
        )

    def test_invalid_status_filter_leaves_loaded_view_unchanged(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_filter = RecordingVariable("")
        window._research_run_filter_summary = RecordingVariable("Old summary")
        window._research_run_status_filter = RecordingVariable("invalid")
        window._research_run_selector = RecordingCandidateSelector(0)
        window._research_run_selector.values = ("Existing run",)
        window._research_runs = ()
        window._visible_research_runs = ()
        window._status = RecordingStatus()

        window._apply_research_run_status_filter()

        self.assertEqual(window._research_run_selector.values, ("Existing run",))
        self.assertEqual(
            window._research_run_filter_summary.value,
            "Status filter is invalid; the loaded view is unchanged.",
        )
        self.assertEqual(
            window._status.values,
            ["Research run status filter is invalid."],
        )

    def test_reset_research_run_view_restores_defaults_and_active_row(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        base = datetime(2026, 8, 22, tzinfo=UTC)
        active = ResearchRun(
            "run-1",
            "Alpha",
            ResearchRunStatus.COMPLETED,
            (),
            (),
            base,
            base,
        )
        newer = ResearchRun(
            "run-2",
            "Zulu",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            base,
            base + timedelta(hours=1),
        )
        full_catalog = (active, newer)
        window._controller = Mock()
        window._research_run_filter = RecordingVariable("zulu")
        window._research_run_filter_summary = RecordingVariable("1 of 2 match")
        window._research_run_status_filter = RecordingVariable(
            ResearchRunStatusFacet.COLLECTING.value
        )
        window._research_run_catalog_summary = RecordingVariable(
            "Loaded catalog: immutable"
        )
        window._research_run_sort = RecordingVariable(ResearchRunSort.QUESTION.value)
        window._research_run_sort_summary = RecordingVariable("Old sort")
        window._research_run_id = RecordingVariable("run-1")
        window._research_run_choice = RecordingVariable("")
        window._research_run_selector = RecordingCandidateSelector(0)
        window._research_runs = full_catalog
        window._visible_research_runs = (newer,)
        window._research_assessment_text = RecordingVariable("authored assessment")
        window._research_claim_text = RecordingVariable("authored claim")
        window._status = RecordingStatus()

        window._reset_research_run_view()

        self.assertIs(window._research_runs, full_catalog)
        self.assertEqual(window._research_run_filter.value, "")
        self.assertEqual(
            window._research_run_status_filter.value,
            ResearchRunStatusFacet.ALL.value,
        )
        self.assertEqual(
            window._research_run_sort.value,
            ResearchRunSort.UPDATED_NEWEST.value,
        )
        self.assertEqual(window._visible_research_runs, (newer, active))
        self.assertEqual(window._research_run_selector.current(), 1)
        self.assertEqual(
            window._research_run_choice.value,
            "Alpha [completed] — run-1",
        )
        self.assertEqual(window._research_run_id.value, "run-1")
        self.assertEqual(
            window._research_run_filter_summary.value,
            "All 2 loaded research runs are shown.",
        )
        self.assertEqual(
            window._research_run_sort_summary.value,
            "Current sort: Updated — newest first.",
        )
        self.assertEqual(
            window._research_run_catalog_summary.value,
            "Loaded catalog: immutable",
        )
        self.assertEqual(
            window._research_assessment_text.value,
            "authored assessment",
        )
        self.assertEqual(window._research_claim_text.value, "authored claim")
        self.assertEqual(
            window._status.values,
            [
                "research run view reset: 2 loaded; filters cleared; "
                "default sort restored; active run shown: run-1"
            ],
        )
        window._controller.assert_not_called()

    def test_reset_empty_research_run_view_clears_invalid_local_state(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_filter = RecordingVariable("old")
        window._research_run_filter_summary = RecordingVariable("Old summary")
        window._research_run_status_filter = RecordingVariable("invalid")
        window._research_run_sort = RecordingVariable("invalid")
        window._research_run_sort_summary = RecordingVariable("Old sort")
        window._research_run_id = RecordingVariable("")
        window._research_run_choice = RecordingVariable("Old choice")
        window._research_run_selector = RecordingCandidateSelector(0)
        window._research_run_selector.values = ("Old row",)
        window._research_runs = ()
        window._visible_research_runs = ()
        window._research_assessment_text = RecordingVariable("authored")
        window._status = RecordingStatus()

        window._reset_research_run_view()

        self.assertEqual(window._research_run_filter.value, "")
        self.assertEqual(
            window._research_run_status_filter.value,
            ResearchRunStatusFacet.ALL.value,
        )
        self.assertEqual(
            window._research_run_sort.value,
            ResearchRunSort.UPDATED_NEWEST.value,
        )
        self.assertEqual(window._research_run_selector.values, ())
        self.assertEqual(window._research_run_choice.value, "")
        self.assertEqual(
            window._research_run_filter_summary.value,
            "No research runs are available.",
        )
        self.assertEqual(
            window._research_run_sort_summary.value,
            "Current sort: Updated — newest first.",
        )
        self.assertEqual(window._research_assessment_text.value, "authored")
        self.assertEqual(
            window._status.values,
            [
                "research run view reset: 0 loaded; filters cleared; "
                "default sort restored; no active run selected"
            ],
        )

    def test_reset_view_preserves_stale_active_identity_without_selecting_row(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 22, tzinfo=UTC)
        loaded = ResearchRun(
            "run-loaded",
            "Loaded",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )
        window._research_run_filter = RecordingVariable("missing")
        window._research_run_filter_summary = RecordingVariable("Old summary")
        window._research_run_status_filter = RecordingVariable(
            ResearchRunStatusFacet.FAILED.value
        )
        window._research_run_sort = RecordingVariable(ResearchRunSort.QUESTION.value)
        window._research_run_sort_summary = RecordingVariable("Old sort")
        window._research_run_id = RecordingVariable("run-stale")
        window._research_run_choice = RecordingVariable("Stale choice")
        window._research_run_selector = RecordingCandidateSelector(0)
        window._research_runs = (loaded,)
        window._visible_research_runs = ()
        window._research_claim_text = RecordingVariable("authored claim")
        window._status = RecordingStatus()

        window._reset_research_run_view()

        self.assertEqual(window._visible_research_runs, (loaded,))
        self.assertEqual(window._research_run_choice.value, "")
        self.assertEqual(window._research_run_id.value, "run-stale")
        self.assertEqual(window._research_claim_text.value, "authored claim")
        self.assertEqual(
            window._status.values,
            [
                "research run view reset: 1 loaded; filters cleared; "
                "default sort restored; active run not loaded: run-stale"
            ],
        )

    def test_show_active_run_clears_local_filters_and_preserves_sort_and_fields(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 22, tzinfo=UTC)
        other = ResearchRun(
            "run-2",
            "Zulu",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )
        active = ResearchRun(
            "run-1",
            "Alpha",
            ResearchRunStatus.COMPLETED,
            (),
            (),
            now,
            now,
        )
        full_catalog = (other, active)
        window._research_run_filter = RecordingVariable("zulu")
        window._research_run_filter_summary = RecordingVariable("1 of 2 match")
        window._research_run_status_filter = RecordingVariable(
            ResearchRunStatusFacet.COMPLETED.value
        )
        window._research_run_sort = RecordingVariable(ResearchRunSort.QUESTION.value)
        window._research_run_id = RecordingVariable("run-1")
        window._research_run_choice = RecordingVariable("")
        window._research_run_selector = RecordingCandidateSelector(0)
        window._research_runs = full_catalog
        window._visible_research_runs = (other,)
        window._research_assessment_text = RecordingVariable("authored assessment")
        window._research_claim_text = RecordingVariable("authored claim")
        window._status = RecordingStatus()

        window._show_active_research_run()

        self.assertIs(window._research_runs, full_catalog)
        self.assertEqual(window._research_run_filter.value, "")
        self.assertEqual(
            window._research_run_status_filter.value,
            ResearchRunStatusFacet.ALL.value,
        )
        self.assertEqual(
            window._research_run_sort.value, ResearchRunSort.QUESTION.value
        )
        self.assertEqual(window._visible_research_runs, (active, other))
        self.assertEqual(
            window._research_run_selector.values,
            (
                "Alpha [completed] — run-1",
                "Zulu [collecting] — run-2",
            ),
        )
        self.assertEqual(window._research_run_selector.current(), 0)
        self.assertEqual(
            window._research_run_choice.value,
            "Alpha [completed] — run-1",
        )
        self.assertEqual(window._research_run_id.value, "run-1")
        self.assertEqual(
            window._research_run_filter_summary.value,
            "All 2 loaded research runs are shown.",
        )
        self.assertEqual(
            window._research_assessment_text.value,
            "authored assessment",
        )
        self.assertEqual(window._research_claim_text.value, "authored claim")
        self.assertEqual(
            window._status.values,
            [
                "active research run shown: run-1; 2 loaded; "
                "filters cleared; sort preserved"
            ],
        )

    def test_show_active_run_without_selection_leaves_view_unchanged(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_filter = RecordingVariable("existing filter")
        window._research_run_filter_summary = RecordingVariable("Old summary")
        window._research_run_id = RecordingVariable("")
        window._research_runs = ()
        window._visible_research_runs = ()
        window._status = RecordingStatus()

        window._show_active_research_run()

        self.assertEqual(window._research_run_filter.value, "existing filter")
        self.assertEqual(
            window._research_run_filter_summary.value,
            "No active research run is selected.",
        )
        self.assertEqual(
            window._status.values,
            ["Select a research run before showing it."],
        )

    def test_show_active_run_rejects_unknown_loaded_run_without_changes(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_filter = RecordingVariable("existing filter")
        window._research_run_filter_summary = RecordingVariable("Old summary")
        window._research_run_id = RecordingVariable("run-missing")
        window._research_runs = ()
        window._visible_research_runs = ()
        window._status = RecordingStatus()

        window._show_active_research_run()

        self.assertEqual(window._research_run_filter.value, "existing filter")
        self.assertEqual(
            window._research_run_filter_summary.value,
            "The active research run is not in the loaded catalog; refresh runs.",
        )
        self.assertEqual(
            window._status.values,
            ["Active research run is not loaded."],
        )

    def test_show_active_run_rejects_invalid_sort_without_changes(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 22, tzinfo=UTC)
        active = ResearchRun(
            "run-1",
            "Alpha",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )
        window._research_run_filter = RecordingVariable("existing filter")
        window._research_run_filter_summary = RecordingVariable("Old summary")
        window._research_run_sort = RecordingVariable("invalid")
        window._research_run_id = RecordingVariable("run-1")
        window._research_runs = (active,)
        window._visible_research_runs = ()
        window._status = RecordingStatus()

        window._show_active_research_run()

        self.assertEqual(window._research_run_filter.value, "existing filter")
        self.assertEqual(window._visible_research_runs, ())
        self.assertEqual(
            window._research_run_filter_summary.value,
            "Current sort is invalid; the active run was not shown.",
        )
        self.assertEqual(window._status.values, ["Research run sort is invalid."])

    def test_research_run_sort_modes_use_deterministic_run_id_ties(self) -> None:
        base = datetime(2026, 8, 22, tzinfo=UTC)
        tie_z = ResearchRun(
            "run-z",
            "alpha",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            base,
            base + timedelta(hours=2),
        )
        tie_a = ResearchRun(
            "run-a",
            "Alpha",
            ResearchRunStatus.COMPLETED,
            (),
            (),
            base + timedelta(hours=2),
            base + timedelta(hours=2),
        )
        oldest = ResearchRun(
            "run-m",
            "Beta",
            ResearchRunStatus.CANCELLED,
            (),
            (),
            base + timedelta(hours=1),
            base + timedelta(hours=1),
        )
        runs = (tie_z, oldest, tie_a)

        self.assertEqual(
            TkinterDesktopWindow._sort_research_runs(
                runs,
                ResearchRunSort.UPDATED_NEWEST,
            ),
            (tie_a, tie_z, oldest),
        )
        self.assertEqual(
            TkinterDesktopWindow._sort_research_runs(
                runs,
                ResearchRunSort.UPDATED_OLDEST,
            ),
            (oldest, tie_a, tie_z),
        )
        self.assertEqual(
            TkinterDesktopWindow._sort_research_runs(
                runs,
                ResearchRunSort.CREATED_NEWEST,
            ),
            (tie_a, oldest, tie_z),
        )
        self.assertEqual(
            TkinterDesktopWindow._sort_research_runs(
                runs,
                ResearchRunSort.QUESTION,
            ),
            (tie_a, tie_z, oldest),
        )

    def test_local_sort_preserves_filter_membership_catalog_and_active_run(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        base = datetime(2026, 8, 22, tzinfo=UTC)
        hidden = ResearchRun(
            "run-hidden",
            "Hidden",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            base,
            base,
        )
        second = ResearchRun(
            "run-2",
            "Zulu",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            base,
            base,
        )
        active = ResearchRun(
            "run-1",
            "Alpha",
            ResearchRunStatus.COMPLETED,
            (),
            (),
            base,
            base,
        )
        full_catalog = (hidden, second, active)
        visible_membership = (second, active)
        window._research_run_sort = RecordingVariable(ResearchRunSort.QUESTION.value)
        window._research_run_sort_summary = RecordingVariable("")
        window._research_run_id = RecordingVariable("run-1")
        window._research_run_choice = RecordingVariable("Alpha")
        window._research_run_selector = RecordingCandidateSelector(1)
        window._research_runs = full_catalog
        window._visible_research_runs = visible_membership
        window._research_assessment_text = RecordingVariable("authored")
        window._status = RecordingStatus()

        window._apply_research_run_sort()

        self.assertIs(window._research_runs, full_catalog)
        self.assertEqual(window._visible_research_runs, (active, second))
        self.assertEqual(
            window._research_run_selector.values,
            (
                "Alpha [completed] — run-1",
                "Zulu [collecting] — run-2",
            ),
        )
        self.assertEqual(window._research_run_selector.current(), 0)
        self.assertEqual(window._research_run_id.value, "run-1")
        self.assertEqual(window._research_assessment_text.value, "authored")
        self.assertEqual(
            window._research_run_sort_summary.value,
            "Current sort: Question — A to Z.",
        )
        self.assertEqual(
            window._status.values,
            [
                "research run sort: Question — A to Z; "
                "2 visible; active run unchanged"
            ],
        )

    def test_invalid_local_sort_leaves_visible_view_unchanged(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_sort = RecordingVariable("invalid")
        window._research_run_sort_summary = RecordingVariable("Old sort")
        window._research_run_selector = RecordingCandidateSelector(0)
        window._research_run_selector.values = ("Existing",)
        window._visible_research_runs = ()
        window._status = RecordingStatus()

        window._apply_research_run_sort()

        self.assertEqual(window._research_run_selector.values, ("Existing",))
        self.assertEqual(
            window._research_run_sort_summary.value,
            "Invalid sort; the visible research runs are unchanged.",
        )
        self.assertEqual(window._status.values, ["Research run sort is invalid."])

    def test_empty_research_run_catalog_clears_only_run_bound_presentations(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_id = RecordingVariable("old-run")
        window._research_run_choice = RecordingVariable("Old run")
        window._research_run_summary = RecordingVariable("Old summary")
        window._research_run_context = RecordingVariable("Old context")
        window._research_run_progress = RecordingVariable("Old progress")
        window._research_workflow_snapshot = RecordingVariable("Old workflow")
        window._research_evidence_coverage = RecordingVariable("Old coverage")
        window._research_assessment_coverage = RecordingVariable("Old assessment")
        window._research_run_metadata = RecordingVariable("Old metadata")
        window._research_run_filter = RecordingVariable("old filter")
        window._research_run_filter_summary = RecordingVariable("old filter summary")
        window._research_run_status_filter = RecordingVariable("old status")
        window._research_run_catalog_summary = RecordingVariable("old catalog")
        window._research_run_sort = RecordingVariable(
            ResearchRunSort.UPDATED_NEWEST.value
        )
        window._research_run_sort_summary = RecordingVariable("")
        window._research_run_selector = RecordingCandidateSelector(selected_index=0)
        window._research_runs = ()
        window._visible_research_runs = ()
        window._research_source_choice = RecordingVariable("Old source")
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_sources = ()
        window._research_source_run_id = "old-run"
        _configure_research_evidence_selector(window)
        window._research_candidate = RecordingVariable("Old candidate")
        window._research_candidate_selector = RecordingCandidateSelector(
            selected_index=0
        )
        window._research_candidates = ()
        window._research_candidate_run_id = "old-run"
        window._research_candidate_discovery_id = "discovery-1"
        window._research_claim_contradiction_proposal = RecordingVariable(
            "Old proposal"
        )
        window._research_claim_contradiction_proposal_selector = (
            RecordingCandidateSelector(selected_index=0)
        )
        window._research_claim_contradiction_proposal_run_id = "old-run"
        window._research_claim_contradiction_proposals = ()
        window._research_markdown_export_preview = object()

        window._render_research_run_selector(())

        self.assertEqual(window._research_run_id.value, "")
        self.assertEqual(window._research_run_choice.value, "")
        self.assertEqual(window._research_source_choice.value, "")
        self.assertEqual(window._research_source_selector.values, ())
        self.assertEqual(window._research_source_run_id, "")
        self.assertEqual(
            window._research_run_summary.value,
            "No research runs available.",
        )
        self.assertEqual(
            window._research_run_context.value,
            "No research runs available. Return to Overview to start one.",
        )
        self.assertEqual(
            window._research_run_progress.value,
            "Progress unavailable: no research runs available.",
        )
        self.assertEqual(
            window._research_workflow_snapshot.value,
            "No research runs are available to summarize.",
        )
        self.assertEqual(
            window._research_evidence_coverage.value,
            "Evidence coverage unavailable: no research runs available.",
        )
        self.assertEqual(
            window._research_assessment_coverage.value,
            "Assessment coverage unavailable: no research runs available.",
        )
        self.assertEqual(
            window._research_run_metadata.value,
            "Run metadata unavailable: no research runs are available.",
        )
        self.assertEqual(
            window._research_run_catalog_summary.value,
            "Loaded catalog: All 0 · Collecting 0 · Completed 0 · "
            "Failed 0 · Cancelled 0",
        )
        self.assertEqual(window._research_source_catalog, ())
        self.assertEqual(window._active_research_source_document_id, "")
        self.assertEqual(
            window._research_source_coverage_filter.value,
            ResearchSourceCoverageFacet.ALL.value,
        )
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "No accepted sources are available.",
        )
        self.assertEqual(window._research_candidate_run_id, "")
        self.assertEqual(window._research_claim_contradiction_proposal_run_id, "")
        self.assertIsNone(window._research_markdown_export_preview)

    def test_selecting_another_catalogued_run_starts_no_runtime_action(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 21, tzinfo=UTC)
        first_run = ResearchRun(
            "run-1",
            "First question",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )
        second_run = ResearchRun(
            "run-2",
            "Second question",
            ResearchRunStatus.COMPLETED,
            (),
            (),
            now,
            now,
        )
        clears: list[bool] = []
        window._research_run_id = RecordingVariable("run-1")
        window._research_run_summary = RecordingVariable("")
        window._research_run_context = RecordingVariable("")
        window._research_run_progress = RecordingVariable("")
        window._research_workflow_snapshot = RecordingVariable("")
        window._research_evidence_coverage = RecordingVariable("")
        window._research_assessment_coverage = RecordingVariable("")
        window._research_run_metadata = RecordingVariable("")
        window._research_run_selector = RecordingCandidateSelector(selected_index=1)
        window._research_runs = (first_run, second_run)
        window._visible_research_runs = (first_run, second_run)
        window._research_source_choice = RecordingVariable("")
        window._research_source_selector = RecordingCandidateSelector()
        window._research_sources = ()
        window._research_source_run_id = ""
        _configure_research_evidence_selector(window)
        window._status = RecordingStatus()
        window._clear_research_run_dependent_presentations = lambda: clears.append(True)

        window._select_research_run()

        self.assertEqual(window._research_run_id.value, "run-2")
        self.assertEqual(clears, [True])
        self.assertEqual(
            window._research_run_summary.value,
            "Status: completed · Sources: 0 · Evidence: 0 · Claims: 0",
        )
        self.assertEqual(
            window._research_run_context.value,
            "Working on: Second question [completed] — run-2",
        )
        self.assertEqual(
            window._research_run_progress.value,
            "Sources: 0 · Evidence: 0 · Claims: 0",
        )
        self.assertEqual(
            window._research_workflow_snapshot.value,
            "Sources & evidence — Sources: 0 · Evidence: 0 | "
            "Authored analysis — Assessments: 0 · Comparison notes: 0 · "
            "Claims: 0 · Contradictions: 0 | "
            "Review & export — Status: completed",
        )
        self.assertEqual(
            window._research_evidence_coverage.value,
            "Evidence coverage — Accepted sources: 0 · With evidence: 0 · "
            "Without evidence: 0",
        )
        self.assertEqual(
            window._research_assessment_coverage.value,
            "Assessment coverage — Accepted sources: 0 · "
            "With current assessment: 0 · Without current assessment: 0",
        )
        self.assertEqual(
            window._research_run_metadata.value,
            "Run metadata — Created: 2026-08-21T00:00:00+00:00 · "
            "Updated: 2026-08-21T00:00:00+00:00 · Safe failures: 0",
        )
        self.assertEqual(
            window._status.values,
            ["research run selected: run-2; no action started"],
        )

    def test_invalid_research_run_selection_shows_no_snapshot_summary(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_selector = RecordingCandidateSelector(selected_index=-1)
        window._research_runs = ()
        window._visible_research_runs = ()
        window._research_source_choice = RecordingVariable("Old source")
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_sources = ()
        window._research_source_run_id = "old-run"
        _configure_research_evidence_selector(window)
        window._research_run_summary = RecordingVariable("Old summary")
        window._research_run_context = RecordingVariable("Old context")
        window._research_run_progress = RecordingVariable("Old progress")
        window._research_workflow_snapshot = RecordingVariable("Old workflow")
        window._research_evidence_coverage = RecordingVariable("Old coverage")
        window._research_assessment_coverage = RecordingVariable("Old assessment")
        window._research_run_metadata = RecordingVariable("Old metadata")
        window._status = RecordingStatus()

        window._select_research_run()

        self.assertEqual(
            window._research_run_summary.value,
            "Refresh and select a research run.",
        )
        self.assertEqual(
            window._research_run_context.value,
            "No research run selected. Return to Overview to refresh or choose one.",
        )
        self.assertEqual(
            window._research_run_progress.value,
            "Progress unavailable until a research run is selected.",
        )
        self.assertEqual(
            window._research_workflow_snapshot.value,
            "Refresh and select a research run to see stage records.",
        )
        self.assertEqual(
            window._research_evidence_coverage.value,
            "Evidence coverage unavailable until a research run is selected.",
        )
        self.assertEqual(
            window._research_assessment_coverage.value,
            "Assessment coverage unavailable until a research run is selected.",
        )
        self.assertEqual(
            window._research_run_metadata.value,
            "Run metadata unavailable until a research run is selected.",
        )
        self.assertEqual(
            window._status.values,
            ["Refresh and select a research run first."],
        )

    def test_selected_run_renders_accepted_sources_without_copying_ids(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 21, tzinfo=UTC)
        first_source = ResearchSourceRecord(
            "document-1",
            "https://example.com/first",
            "First accepted paper",
            "text/plain",
            now,
            now,
        )
        second_source = ResearchSourceRecord(
            "document-2",
            "https://example.com/second",
            "Second accepted paper",
            "text/plain",
            now,
            now,
        )
        evidence = _research_evidence_record(
            "evidence-1",
            "document-1",
            "First source evidence",
        )
        assessment = _research_assessment_record(
            "assessment-1",
            "document-1",
            "evidence-1",
            "First source assessment",
        )
        run = ResearchRun(
            "run-123",
            "Compare accepted papers",
            ResearchRunStatus.COLLECTING,
            (first_source, second_source),
            (),
            now,
            now,
            evidence=(evidence,),
            assessments=(assessment,),
        )
        window._research_run_id = RecordingVariable("run-123")
        window._research_run_summary = RecordingVariable("")
        window._research_run_context = RecordingVariable("")
        window._research_run_progress = RecordingVariable("")
        window._research_workflow_snapshot = RecordingVariable("")
        window._research_evidence_coverage = RecordingVariable("")
        window._research_assessment_coverage = RecordingVariable("")
        window._research_run_metadata = RecordingVariable("")
        window._research_run_selector = RecordingCandidateSelector(selected_index=0)
        window._research_runs = (run,)
        window._visible_research_runs = (run,)
        window._research_source_choice = RecordingVariable("")
        window._research_source_selector = RecordingCandidateSelector()
        window._research_sources = ()
        window._research_source_run_id = ""
        _configure_research_evidence_selector(window)
        window._research_source_document_id = RecordingVariable("manual-source")
        window._research_comparison_document_ids = RecordingVariable(
            "manual-comparison"
        )
        window._status = RecordingStatus()

        window._select_research_run()

        self.assertEqual(window._research_sources, (first_source, second_source))
        self.assertEqual(window._research_source_run_id, "run-123")
        self.assertEqual(
            window._research_source_selector.values,
            (
                "First accepted paper — document-1",
                "Second accepted paper — document-2",
            ),
        )
        self.assertEqual(window._research_source_selector.current(), 0)
        self.assertEqual(window._research_source_document_id.value, "manual-source")
        self.assertEqual(
            window._research_comparison_document_ids.value,
            "manual-comparison",
        )
        self.assertEqual(
            window._research_evidence_coverage.value,
            "Evidence coverage — Accepted sources: 2 · With evidence: 1 · "
            "Without evidence: 1",
        )
        self.assertEqual(
            window._research_assessment_coverage.value,
            "Assessment coverage — Accepted sources: 2 · "
            "With current assessment: 1 · Without current assessment: 1",
        )
        self.assertEqual(
            window._research_source_catalog_summary.value,
            "Accepted-source coverage — All: 2 · Without evidence: 1 · "
            "Without current assessment: 1",
        )
        self.assertEqual(
            window._status.values,
            ["research run selected: run-123; no action started"],
        )

    def test_source_catalog_summary_counts_complete_coverage_membership(
        self,
    ) -> None:
        first = _research_source_record("document-1", "Evidence only")
        second = _research_source_record("document-2", "Corrected")
        third = _research_source_record("document-3", "Repeated current")
        fourth = _research_source_record("document-4", "Superseded only")
        original = _research_assessment_record(
            "assessment-1", "document-2", "evidence-2", "Original"
        )
        correction = _research_assessment_record(
            "assessment-2",
            "document-2",
            "evidence-2",
            "Correction",
            supersedes_assessment_id=original.assessment_id,
        )
        repeated_current = (
            _research_assessment_record(
                "assessment-3", "document-3", "evidence-3", "Current one"
            ),
            _research_assessment_record(
                "assessment-4", "document-3", "evidence-3", "Current two"
            ),
        )
        superseded_only = _research_assessment_record(
            "assessment-5", "document-4", "evidence-4", "Old"
        )
        malformed_foreign_correction = _research_assessment_record(
            "assessment-6",
            "foreign",
            "foreign-evidence",
            "Foreign correction",
            supersedes_assessment_id=superseded_only.assessment_id,
        )
        run = Mock(spec=ResearchRun)
        run.sources = (first, second, third, fourth)
        run.evidence = (
            _research_evidence_record("evidence-1", "document-1", "One"),
            _research_evidence_record("evidence-duplicate", "document-1", "Two"),
            _research_evidence_record("evidence-foreign", "foreign", "Foreign"),
        )
        run.assessments = (
            original,
            correction,
            *repeated_current,
            superseded_only,
            malformed_foreign_correction,
        )

        self.assertEqual(
            TkinterDesktopWindow._research_source_catalog_summary_text(run),
            "Accepted-source coverage — All: 4 · Without evidence: 3 · "
            "Without current assessment: 2",
        )

    def test_empty_source_catalog_summary_has_complete_zero_counts(self) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        run = ResearchRun(
            "run-empty-source-summary",
            "Inspect empty source coverage",
            ResearchRunStatus.COLLECTING,
            (),
            (),
            now,
            now,
        )

        self.assertEqual(
            TkinterDesktopWindow._research_source_catalog_summary_text(run),
            "Accepted-source coverage — All: 0 · Without evidence: 0 · "
            "Without current assessment: 0",
        )

    def test_source_catalog_summary_stays_invariant_across_local_views(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        active = _research_source_record("document-1", "Covered active")
        uncovered = _research_source_record("document-2", "Uncovered")
        evidence = _research_evidence_record(
            "evidence-1", active.document_id, "Recorded"
        )
        assessment = _research_assessment_record(
            "assessment-1",
            active.document_id,
            evidence.evidence_id,
            "Current assessment",
        )
        run = ResearchRun(
            "run-123",
            "Keep source totals invariant",
            ResearchRunStatus.COLLECTING,
            (active, uncovered),
            (),
            now,
            now,
            evidence=(evidence,),
            assessments=(assessment,),
        )
        window: Any = object.__new__(TkinterDesktopWindow)
        window._controller = Mock()
        window._research_run_id = RecordingVariable(run.run_id)
        window._research_runs = (run,)
        window._research_source_run_id = ""
        window._research_sources = ()
        window._research_source_selector = RecordingCandidateSelector()
        window._research_source_choice = RecordingVariable("")
        _configure_research_evidence_selector(window)
        window._research_assessment_text = RecordingVariable("authored")
        window._status = RecordingStatus()

        window._render_research_source_selector(run)
        expected_summary = (
            "Accepted-source coverage — All: 2 · Without evidence: 1 · "
            "Without current assessment: 1"
        )
        self.assertEqual(
            window._research_source_catalog_summary.value, expected_summary
        )

        window._research_source_coverage_filter.set(
            ResearchSourceCoverageFacet.WITHOUT_EVIDENCE.value
        )
        window._apply_research_source_coverage_filter()
        window._research_source_coverage_filter.set(
            ResearchSourceCoverageFacet.WITHOUT_CURRENT_ASSESSMENT.value
        )
        window._apply_research_source_coverage_filter()

        self.assertEqual(
            window._research_source_catalog_summary.value, expected_summary
        )
        self.assertEqual(window._active_research_source_document_id, "document-1")
        self.assertEqual(window._research_assessment_text.value, "authored")
        window._controller.assert_not_called()

    def test_show_active_source_restores_all_view_identity_and_fields(self) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        active = _research_source_record("document-1", "Covered active")
        uncovered = _research_source_record("document-2", "Uncovered")
        evidence = _research_evidence_record(
            "evidence-1", active.document_id, "Recorded"
        )
        assessment = _research_assessment_record(
            "assessment-1",
            active.document_id,
            evidence.evidence_id,
            "Current assessment",
        )
        run = ResearchRun(
            "run-123",
            "Restore the active source",
            ResearchRunStatus.COLLECTING,
            (active, uncovered),
            (),
            now,
            now,
            evidence=(evidence,),
            assessments=(assessment,),
        )
        window: Any = object.__new__(TkinterDesktopWindow)
        window._controller = Mock()
        window._research_run_id = RecordingVariable(run.run_id)
        window._research_runs = (run,)
        window._research_source_run_id = ""
        window._research_sources = ()
        window._research_source_selector = RecordingCandidateSelector()
        window._research_source_choice = RecordingVariable("")
        _configure_research_evidence_selector(window)
        window._research_source_document_id = RecordingVariable("manual-source")
        window._research_comparison_document_ids = RecordingVariable("manual-list")
        window._research_assessment_text = RecordingVariable("authored assessment")
        window._status = RecordingStatus()
        window._render_research_source_selector(run)
        expected_catalog_summary = window._research_source_catalog_summary.value

        window._research_source_coverage_filter.set(
            ResearchSourceCoverageFacet.WITHOUT_CURRENT_ASSESSMENT.value
        )
        window._apply_research_source_coverage_filter()
        self.assertEqual(window._research_source_choice.value, "")
        self.assertEqual(
            window._research_selected_source_summary.value,
            "Selected-source records unavailable in the current source view.",
        )

        window._show_active_research_source()

        self.assertEqual(
            window._research_source_coverage_filter.value,
            ResearchSourceCoverageFacet.ALL.value,
        )
        self.assertIs(window._research_source_catalog, run.sources)
        self.assertIs(window._research_sources, run.sources)
        self.assertEqual(window._research_source_selector.current(), 0)
        self.assertEqual(
            window._research_source_choice.value,
            "Covered active — document-1",
        )
        self.assertEqual(window._active_research_source_document_id, "document-1")
        self.assertEqual(window._research_evidence_records, (evidence,))
        self.assertEqual(window._research_assessment_records, (assessment,))
        self.assertEqual(
            window._research_selected_source_summary.value,
            "Selected source — Covered active · Source ID: document-1 · "
            "Run ID: run-123\nSafety boundary — "
            "Data taint: external_untrusted_data · Instruction authority: none\n"
            "Records — Evidence: 1 · Assessments: 1 history / 1 current · "
            "Evidence cited by current: 1 of 1\nCurrent information trust — "
            "Unassessed: 1 · Low: 0 · Medium: 0 · High: 0",
        )
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "All 2 accepted sources are shown.",
        )
        self.assertEqual(
            window._research_source_catalog_summary.value,
            expected_catalog_summary,
        )
        self.assertEqual(window._research_source_document_id.value, "manual-source")
        self.assertEqual(window._research_comparison_document_ids.value, "manual-list")
        self.assertEqual(
            window._research_assessment_text.value,
            "authored assessment",
        )
        self.assertEqual(
            window._status.values,
            [
                "accepted source view: Without current assessment; 1 of 2 shown; "
                "active source unchanged; active source hidden",
                "active accepted source shown: document-1; 2 accepted sources; "
                "view restored to All sources",
            ],
        )
        window._controller.assert_not_called()

    def test_show_active_source_without_selection_leaves_view_unchanged(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        source = _research_source_record("document-1", "Existing")
        window._active_research_source_document_id = ""
        window._research_source_coverage_filter = RecordingVariable(
            ResearchSourceCoverageFacet.WITHOUT_EVIDENCE.value
        )
        window._research_source_coverage_summary = RecordingVariable("Old summary")
        window._research_sources = (source,)
        window._research_assessment_text = RecordingVariable("authored")
        window._status = RecordingStatus()

        window._show_active_research_source()

        self.assertEqual(
            window._research_source_coverage_filter.value,
            ResearchSourceCoverageFacet.WITHOUT_EVIDENCE.value,
        )
        self.assertEqual(window._research_sources, (source,))
        self.assertEqual(window._research_assessment_text.value, "authored")
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "No active accepted source is selected.",
        )
        self.assertEqual(
            window._status.values,
            ["Select an accepted source before showing it."],
        )

    def test_show_active_source_rejects_stale_snapshot_without_changes(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        source = _research_source_record("document-1", "Existing")
        window._active_research_source_document_id = source.document_id
        window._research_run_id = RecordingVariable("run-current")
        window._research_source_run_id = "run-stale"
        window._research_runs = ()
        window._research_source_catalog = (source,)
        window._research_sources = (source,)
        window._research_source_coverage_filter = RecordingVariable(
            ResearchSourceCoverageFacet.WITHOUT_EVIDENCE.value
        )
        window._research_source_coverage_summary = RecordingVariable("Old summary")
        window._research_assessment_text = RecordingVariable("authored")
        window._status = RecordingStatus()

        window._show_active_research_source()

        self.assertEqual(
            window._research_source_coverage_filter.value,
            ResearchSourceCoverageFacet.WITHOUT_EVIDENCE.value,
        )
        self.assertEqual(window._research_sources, (source,))
        self.assertEqual(window._research_assessment_text.value, "authored")
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "Accepted-source snapshot is stale; refresh research runs.",
        )
        self.assertEqual(
            window._status.values,
            ["Accepted-source snapshot is stale."],
        )

    def test_show_active_source_rejects_unknown_active_id_without_changes(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        source = _research_source_record("document-1", "Loaded")
        run = ResearchRun(
            "run-123",
            "Reject unknown active source",
            ResearchRunStatus.COLLECTING,
            (source,),
            (),
            now,
            now,
        )
        window: Any = object.__new__(TkinterDesktopWindow)
        window._active_research_source_document_id = "document-missing"
        window._research_run_id = RecordingVariable(run.run_id)
        window._research_source_run_id = run.run_id
        window._research_runs = (run,)
        window._research_source_catalog = run.sources
        window._research_sources = ()
        window._research_source_coverage_filter = RecordingVariable(
            ResearchSourceCoverageFacet.WITHOUT_EVIDENCE.value
        )
        window._research_source_coverage_summary = RecordingVariable("Old summary")
        window._research_assessment_text = RecordingVariable("authored")
        window._status = RecordingStatus()

        window._show_active_research_source()

        self.assertEqual(window._research_sources, ())
        self.assertEqual(window._research_assessment_text.value, "authored")
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "The active accepted source is not loaded; refresh research runs.",
        )
        self.assertEqual(
            window._status.values,
            ["Active accepted source is not loaded."],
        )

    def test_source_coverage_facet_deduplicates_evidence_and_keeps_order(
        self,
    ) -> None:
        first = _research_source_record("document-1", "First")
        second = _research_source_record("document-2", "Second")
        third = _research_source_record("document-3", "Third")
        sources = (first, second, third)
        evidence = (
            _research_evidence_record("evidence-1", "document-1", "One"),
            _research_evidence_record("evidence-2", "document-1", "Two"),
            _research_evidence_record("evidence-3", "foreign", "Foreign"),
        )

        self.assertIs(
            TkinterDesktopWindow._filter_research_sources_by_coverage(
                sources,
                evidence,
                (),
                ResearchSourceCoverageFacet.ALL,
            ),
            sources,
        )
        self.assertEqual(
            TkinterDesktopWindow._filter_research_sources_by_coverage(
                sources,
                evidence,
                (),
                ResearchSourceCoverageFacet.WITHOUT_EVIDENCE,
            ),
            (second, third),
        )

    def test_source_coverage_facet_uses_only_current_assessment_membership(
        self,
    ) -> None:
        first = _research_source_record("document-1", "Corrected")
        second = _research_source_record("document-2", "Repeated current")
        third = _research_source_record("document-3", "Superseded only")
        fourth = _research_source_record("document-4", "No assessment")
        sources = (first, second, third, fourth)
        original = _research_assessment_record(
            "assessment-1", "document-1", "evidence-1", "Original"
        )
        correction = _research_assessment_record(
            "assessment-2",
            "document-1",
            "evidence-1",
            "Correction",
            supersedes_assessment_id=original.assessment_id,
        )
        repeated_current = (
            _research_assessment_record(
                "assessment-3", "document-2", "evidence-2", "Current one"
            ),
            _research_assessment_record(
                "assessment-4", "document-2", "evidence-2", "Current two"
            ),
        )
        superseded_only = _research_assessment_record(
            "assessment-5", "document-3", "evidence-3", "Old"
        )
        malformed_foreign_correction = _research_assessment_record(
            "assessment-6",
            "foreign",
            "evidence-foreign",
            "Foreign",
            supersedes_assessment_id=superseded_only.assessment_id,
        )

        self.assertEqual(
            TkinterDesktopWindow._filter_research_sources_by_coverage(
                sources,
                (),
                (
                    original,
                    correction,
                    *repeated_current,
                    superseded_only,
                    malformed_foreign_correction,
                ),
                ResearchSourceCoverageFacet.WITHOUT_CURRENT_ASSESSMENT,
            ),
            (third, fourth),
        )

    def test_without_current_assessment_view_keeps_visible_active_and_fields(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        assessed = _research_source_record("document-1", "Assessed")
        active = _research_source_record("document-2", "Active unassessed")
        other = _research_source_record("document-3", "Other unassessed")
        evidence = _research_evidence_record(
            "evidence-1", assessed.document_id, "Recorded"
        )
        assessment = _research_assessment_record(
            "assessment-1",
            assessed.document_id,
            evidence.evidence_id,
            "Current assessment",
        )
        run = ResearchRun(
            "run-123",
            "Inspect unassessed sources",
            ResearchRunStatus.COLLECTING,
            (assessed, active, other),
            (),
            now,
            now,
            evidence=(evidence,),
            assessments=(assessment,),
        )
        window: Any = object.__new__(TkinterDesktopWindow)
        window._controller = Mock()
        window._research_run_id = RecordingVariable(run.run_id)
        window._research_runs = (run,)
        window._research_source_run_id = run.run_id
        window._research_sources = run.sources
        window._research_source_selector = RecordingCandidateSelector(selected_index=1)
        window._research_source_choice = RecordingVariable(
            "Active unassessed — document-2"
        )
        _configure_research_evidence_selector(window)
        window._research_source_coverage_filter.set(
            ResearchSourceCoverageFacet.WITHOUT_CURRENT_ASSESSMENT.value
        )
        window._research_source_document_id = RecordingVariable("manual-source")
        window._research_comparison_document_ids = RecordingVariable("manual-list")
        window._research_assessment_text = RecordingVariable("authored assessment")
        window._status = RecordingStatus()

        window._apply_research_source_coverage_filter()

        self.assertIs(window._research_source_catalog, run.sources)
        self.assertEqual(window._research_sources, (active, other))
        self.assertEqual(window._active_research_source_document_id, "document-2")
        self.assertEqual(window._research_source_selector.current(), 0)
        self.assertEqual(
            window._research_source_selector.values,
            (
                "Active unassessed — document-2",
                "Other unassessed — document-3",
            ),
        )
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "2 of 3 accepted sources have no current authored assessment.",
        )
        self.assertEqual(window._research_source_document_id.value, "manual-source")
        self.assertEqual(window._research_comparison_document_ids.value, "manual-list")
        self.assertEqual(window._research_assessment_text.value, "authored assessment")
        self.assertEqual(
            window._status.values,
            [
                "accepted source view: Without current assessment; 2 of 3 shown; "
                "active source unchanged"
            ],
        )
        window._controller.assert_not_called()

    def test_without_current_assessment_view_hides_and_restores_active_source(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        active = _research_source_record("document-1", "Active assessed")
        uncovered = _research_source_record("document-2", "Unassessed")
        evidence = _research_evidence_record(
            "evidence-1", active.document_id, "Recorded evidence"
        )
        assessment = _research_assessment_record(
            "assessment-1",
            active.document_id,
            evidence.evidence_id,
            "Current assessment",
        )
        run = ResearchRun(
            "run-123",
            "Switch assessment coverage",
            ResearchRunStatus.COLLECTING,
            (active, uncovered),
            (),
            now,
            now,
            evidence=(evidence,),
            assessments=(assessment,),
        )
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_id = RecordingVariable(run.run_id)
        window._research_runs = (run,)
        window._research_source_run_id = run.run_id
        window._research_sources = run.sources
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_source_choice = RecordingVariable(
            "Active assessed — document-1"
        )
        _configure_research_evidence_selector(window)
        window._render_research_evidence_selector(run, active)
        window._render_research_assessment_selector(run, active)
        window._research_assessment_text = RecordingVariable("authored")
        window._status = RecordingStatus()

        window._research_source_coverage_filter.set(
            ResearchSourceCoverageFacet.WITHOUT_CURRENT_ASSESSMENT.value
        )
        window._apply_research_source_coverage_filter()

        self.assertEqual(window._research_sources, (uncovered,))
        self.assertEqual(window._active_research_source_document_id, "document-1")
        self.assertEqual(window._research_source_choice.value, "")
        self.assertEqual(window._research_evidence_records, ())
        self.assertEqual(window._research_assessment_records, ())
        self.assertEqual(window._research_assessment_text.value, "authored")

        window._research_source_coverage_filter.set(
            ResearchSourceCoverageFacet.ALL.value
        )
        window._apply_research_source_coverage_filter()

        self.assertEqual(window._research_sources, run.sources)
        self.assertEqual(window._research_source_selector.current(), 0)
        self.assertEqual(window._active_research_source_document_id, "document-1")
        self.assertEqual(window._research_evidence_records, (evidence,))
        self.assertEqual(window._research_assessment_records, (assessment,))
        self.assertEqual(window._research_assessment_text.value, "authored")
        self.assertEqual(
            window._status.values,
            [
                "accepted source view: Without current assessment; 1 of 2 shown; "
                "active source unchanged; active source hidden",
                "accepted source view: All sources; 2 of 2 shown; "
                "active source unchanged",
            ],
        )

    def test_without_current_assessment_view_reports_no_match(self) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        source = _research_source_record("document-1", "Assessed")
        evidence = _research_evidence_record(
            "evidence-1", source.document_id, "Recorded"
        )
        assessment = _research_assessment_record(
            "assessment-1",
            source.document_id,
            evidence.evidence_id,
            "Current assessment",
        )
        run = ResearchRun(
            "run-123",
            "Inspect complete assessment coverage",
            ResearchRunStatus.COLLECTING,
            (source,),
            (),
            now,
            now,
            evidence=(evidence,),
            assessments=(assessment,),
        )
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_id = RecordingVariable(run.run_id)
        window._research_runs = (run,)
        window._research_source_run_id = run.run_id
        window._research_sources = run.sources
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_source_choice = RecordingVariable("Assessed — document-1")
        _configure_research_evidence_selector(window)
        window._research_source_coverage_filter.set(
            ResearchSourceCoverageFacet.WITHOUT_CURRENT_ASSESSMENT.value
        )
        window._research_claim_text = RecordingVariable("authored claim")
        window._status = RecordingStatus()

        window._apply_research_source_coverage_filter()

        self.assertEqual(window._research_sources, ())
        self.assertEqual(window._active_research_source_document_id, "document-1")
        self.assertEqual(window._research_claim_text.value, "authored claim")
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "All 1 accepted sources have a current authored assessment; "
            "no sources match this view.",
        )

    def test_source_coverage_view_keeps_visible_active_source_and_fields(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        represented = _research_source_record("document-1", "Represented")
        active = _research_source_record("document-2", "Active uncovered")
        other = _research_source_record("document-3", "Other uncovered")
        sources = (represented, active, other)
        run = ResearchRun(
            "run-123",
            "Inspect uncovered sources",
            ResearchRunStatus.COLLECTING,
            sources,
            (),
            now,
            now,
            evidence=(
                _research_evidence_record(
                    "evidence-1",
                    represented.document_id,
                    "Recorded",
                ),
            ),
        )
        window: Any = object.__new__(TkinterDesktopWindow)
        window._controller = Mock()
        window._research_run_id = RecordingVariable(run.run_id)
        window._research_runs = (run,)
        window._research_source_run_id = run.run_id
        window._research_sources = sources
        window._research_source_selector = RecordingCandidateSelector(selected_index=1)
        window._research_source_choice = RecordingVariable(
            "Active uncovered — document-2"
        )
        _configure_research_evidence_selector(window)
        window._research_source_coverage_filter.set(
            ResearchSourceCoverageFacet.WITHOUT_EVIDENCE.value
        )
        window._research_source_document_id = RecordingVariable("manual-source")
        window._research_comparison_document_ids = RecordingVariable("manual-list")
        window._research_assessment_text = RecordingVariable("authored assessment")
        window._status = RecordingStatus()

        window._apply_research_source_coverage_filter()

        self.assertIs(window._research_source_catalog, sources)
        self.assertEqual(window._research_sources, (active, other))
        self.assertEqual(window._active_research_source_document_id, "document-2")
        self.assertEqual(window._research_source_selector.current(), 0)
        self.assertEqual(
            window._research_source_selector.values,
            (
                "Active uncovered — document-2",
                "Other uncovered — document-3",
            ),
        )
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "2 of 3 accepted sources have no recorded evidence.",
        )
        self.assertEqual(window._research_source_document_id.value, "manual-source")
        self.assertEqual(
            window._research_comparison_document_ids.value,
            "manual-list",
        )
        self.assertEqual(
            window._research_assessment_text.value,
            "authored assessment",
        )
        self.assertEqual(
            window._status.values,
            [
                "accepted source view: Without evidence; 2 of 3 shown; "
                "active source unchanged"
            ],
        )
        window._controller.assert_not_called()

    def test_source_coverage_view_hides_and_restores_exact_active_source(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        active = _research_source_record("document-1", "Active represented")
        uncovered = _research_source_record("document-2", "Uncovered")
        evidence = _research_evidence_record(
            "evidence-1",
            active.document_id,
            "Recorded evidence",
        )
        run = ResearchRun(
            "run-123",
            "Switch source coverage",
            ResearchRunStatus.COLLECTING,
            (active, uncovered),
            (),
            now,
            now,
            evidence=(evidence,),
        )
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_id = RecordingVariable(run.run_id)
        window._research_runs = (run,)
        window._research_source_run_id = run.run_id
        window._research_sources = run.sources
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_source_choice = RecordingVariable(
            "Active represented — document-1"
        )
        _configure_research_evidence_selector(window)
        window._render_research_evidence_selector(run, active)
        window._research_assessment_text = RecordingVariable("authored")
        window._status = RecordingStatus()

        window._research_source_coverage_filter.set(
            ResearchSourceCoverageFacet.WITHOUT_EVIDENCE.value
        )
        window._apply_research_source_coverage_filter()

        self.assertEqual(window._research_sources, (uncovered,))
        self.assertEqual(window._active_research_source_document_id, "document-1")
        self.assertEqual(window._research_source_choice.value, "")
        self.assertEqual(window._research_evidence_records, ())
        self.assertEqual(window._research_assessment_text.value, "authored")

        window._research_source_coverage_filter.set(
            ResearchSourceCoverageFacet.ALL.value
        )
        window._apply_research_source_coverage_filter()

        self.assertEqual(window._research_sources, run.sources)
        self.assertEqual(window._research_source_selector.current(), 0)
        self.assertEqual(window._active_research_source_document_id, "document-1")
        self.assertEqual(window._research_evidence_records, (evidence,))
        self.assertEqual(window._research_assessment_text.value, "authored")
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "All 2 accepted sources are shown.",
        )
        self.assertEqual(
            window._status.values,
            [
                "accepted source view: Without evidence; 1 of 2 shown; "
                "active source unchanged; active source hidden",
                "accepted source view: All sources; 2 of 2 shown; "
                "active source unchanged",
            ],
        )

    def test_source_coverage_no_match_preserves_hidden_active_identity(
        self,
    ) -> None:
        now = datetime(2026, 8, 22, tzinfo=UTC)
        active = _research_source_record("document-1", "Active")
        run = ResearchRun(
            "run-123",
            "Inspect complete source coverage",
            ResearchRunStatus.COLLECTING,
            (active,),
            (),
            now,
            now,
            evidence=(
                _research_evidence_record(
                    "evidence-1",
                    active.document_id,
                    "Recorded",
                ),
            ),
        )
        window: Any = object.__new__(TkinterDesktopWindow)
        window._research_run_id = RecordingVariable(run.run_id)
        window._research_runs = (run,)
        window._research_source_run_id = run.run_id
        window._research_sources = run.sources
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_source_choice = RecordingVariable("Active — document-1")
        _configure_research_evidence_selector(window)
        window._research_source_coverage_filter.set(
            ResearchSourceCoverageFacet.WITHOUT_EVIDENCE.value
        )
        window._research_claim_text = RecordingVariable("authored claim")
        window._status = RecordingStatus()

        window._apply_research_source_coverage_filter()

        self.assertEqual(window._research_sources, ())
        self.assertEqual(window._research_source_selector.values, ())
        self.assertEqual(window._active_research_source_document_id, "document-1")
        self.assertEqual(window._research_claim_text.value, "authored claim")
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "All 1 accepted sources have recorded evidence; "
            "no sources match this view.",
        )

    def test_invalid_source_coverage_view_leaves_current_sources_unchanged(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        source = _research_source_record("document-1", "Existing")
        window._research_source_coverage_filter = RecordingVariable("invalid")
        window._research_source_coverage_summary = RecordingVariable("Old summary")
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_source_selector.values = ("Existing — document-1",)
        window._research_sources = (source,)
        window._status = RecordingStatus()

        window._apply_research_source_coverage_filter()

        self.assertEqual(window._research_sources, (source,))
        self.assertEqual(
            window._research_source_selector.values,
            ("Existing — document-1",),
        )
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "Source view is invalid; accepted sources are unchanged.",
        )
        self.assertEqual(
            window._status.values,
            ["Accepted-source coverage view is invalid."],
        )

    def test_stale_source_coverage_snapshot_leaves_view_and_fields_unchanged(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        source = _research_source_record("document-1", "Existing")
        window._research_source_coverage_filter = RecordingVariable(
            ResearchSourceCoverageFacet.WITHOUT_EVIDENCE.value
        )
        window._research_source_coverage_summary = RecordingVariable("Old summary")
        window._research_source_run_id = "run-stale"
        window._research_source_catalog = (source,)
        window._research_sources = (source,)
        window._research_runs = ()
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_source_selector.values = ("Existing — document-1",)
        window._research_assessment_text = RecordingVariable("authored")
        window._status = RecordingStatus()

        window._apply_research_source_coverage_filter()

        self.assertEqual(window._research_sources, (source,))
        self.assertEqual(
            window._research_source_selector.values,
            ("Existing — document-1",),
        )
        self.assertEqual(window._research_assessment_text.value, "authored")
        self.assertEqual(
            window._research_source_coverage_summary.value,
            "Accepted-source snapshot is stale; refresh research runs.",
        )
        self.assertEqual(
            window._status.values,
            ["Accepted-source snapshot is stale."],
        )

    def test_explicit_accepted_source_assessment_handoff_copies_exact_id(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 21, tzinfo=UTC)
        source = ResearchSourceRecord(
            "document-exact",
            "https://example.com/source",
            "Accepted paper",
            "text/plain",
            now,
            now,
        )
        window._research_run_id = RecordingVariable("run-123")
        window._research_source_run_id = "run-123"
        window._research_sources = (source,)
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_source_choice = RecordingVariable(
            "Accepted paper — document-exact"
        )
        window._research_source_document_id = RecordingVariable("manual-source")
        window._research_comparison_document_ids = RecordingVariable(
            "manual-comparison"
        )
        window._status = RecordingStatus()

        window._use_selected_research_source_for_assessment()

        self.assertEqual(window._research_source_document_id.value, "document-exact")
        self.assertEqual(
            window._research_comparison_document_ids.value,
            "manual-comparison",
        )
        self.assertEqual(
            window._status.values,
            ["accepted source ID copied for assessment; " "nothing requested or saved"],
        )

    def test_explicit_accepted_source_comparison_handoff_appends_once(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 21, tzinfo=UTC)
        source = ResearchSourceRecord(
            "document-2",
            "https://example.com/source",
            "Accepted paper",
            "text/plain",
            now,
            now,
        )
        window._research_run_id = RecordingVariable("run-123")
        window._research_source_run_id = "run-123"
        window._research_sources = (source,)
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_source_choice = RecordingVariable(
            "Accepted paper — document-2"
        )
        window._research_source_document_id = RecordingVariable("manual-source")
        window._research_comparison_document_ids = RecordingVariable("document-1")
        window._status = RecordingStatus()

        window._add_selected_research_source_to_comparison()
        window._add_selected_research_source_to_comparison()

        self.assertEqual(window._research_source_document_id.value, "manual-source")
        self.assertEqual(
            window._research_comparison_document_ids.value,
            "document-1, document-2",
        )
        self.assertEqual(
            window._status.values,
            [
                "accepted source ID added to comparison; nothing requested or saved",
                "accepted source ID is already in the comparison; nothing changed",
            ],
        )

    def test_accepted_source_handoff_preserves_five_id_comparison_limit(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 21, tzinfo=UTC)
        source = ResearchSourceRecord(
            "document-6",
            "https://example.com/source",
            "Sixth accepted paper",
            "text/plain",
            now,
            now,
        )
        window._research_run_id = RecordingVariable("run-123")
        window._research_source_run_id = "run-123"
        window._research_sources = (source,)
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_source_choice = RecordingVariable(
            "Sixth accepted paper — document-6"
        )
        original_ids = "document-1, document-2, document-3, document-4, document-5"
        window._research_comparison_document_ids = RecordingVariable(original_ids)
        window._status = RecordingStatus()

        window._add_selected_research_source_to_comparison()

        self.assertEqual(window._research_comparison_document_ids.value, original_ids)
        self.assertEqual(
            window._status.values,
            ["A research source comparison accepts at most 5 IDs."],
        )

    def test_stale_accepted_source_selection_cannot_overwrite_manual_field(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 21, tzinfo=UTC)
        source = ResearchSourceRecord(
            "document-old",
            "https://example.com/source",
            "Old accepted paper",
            "text/plain",
            now,
            now,
        )
        window._research_run_id = RecordingVariable("run-new")
        window._research_source_run_id = "run-old"
        window._research_sources = (source,)
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_source_choice = RecordingVariable(
            "Old accepted paper — document-old"
        )
        _configure_research_evidence_selector(window)
        window._research_source_document_id = RecordingVariable("manual-source")
        window._status = RecordingStatus()

        window._use_selected_research_source_for_assessment()

        self.assertEqual(window._research_source_document_id.value, "manual-source")
        self.assertEqual(window._research_sources, ())
        self.assertEqual(window._research_source_selector.values, ())
        self.assertEqual(window._research_source_choice.value, "")
        self.assertEqual(
            window._status.values,
            ["Select an accepted source first."],
        )

    def test_selected_source_filters_loaded_evidence_without_copying_ids(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 21, tzinfo=UTC)
        first_source = ResearchSourceRecord(
            "document-1",
            "https://example.com/first",
            "First paper",
            "text/plain",
            now,
            now,
        )
        second_source = ResearchSourceRecord(
            "document-2",
            "https://example.com/second",
            "Second paper",
            "text/plain",
            now,
            now,
        )
        first_evidence = _research_evidence_record(
            "evidence-1",
            "document-1",
            "First source evidence.",
        )
        second_evidence = _research_evidence_record(
            "evidence-2",
            "document-2",
            "Second source\nrecorded evidence.",
        )
        run = ResearchRun(
            "run-123",
            "Compare evidence",
            ResearchRunStatus.COLLECTING,
            (first_source, second_source),
            (),
            now,
            now,
            evidence=(first_evidence, second_evidence),
        )
        window._research_run_id = RecordingVariable("run-123")
        window._research_runs = (run,)
        window._visible_research_runs = (run,)
        window._research_source_run_id = "run-123"
        window._research_sources = (first_source, second_source)
        window._research_source_selector = RecordingCandidateSelector(selected_index=1)
        window._research_source_choice = RecordingVariable("Second paper — document-2")
        _configure_research_evidence_selector(window)
        window._research_assessment_evidence_ids = RecordingVariable("manual-a")
        window._research_claim_evidence_ids = RecordingVariable("manual-c")
        window._research_comparison_evidence_ids = RecordingVariable("manual-x")
        window._status = RecordingStatus()

        window._select_research_source()

        self.assertEqual(window._research_evidence_records, (second_evidence,))
        self.assertEqual(window._research_evidence_run_id, "run-123")
        self.assertEqual(
            window._research_evidence_source_document_id,
            "document-2",
        )
        self.assertEqual(
            window._research_evidence_selector.values,
            ("Second source recorded evidence. — evidence-2",),
        )
        self.assertEqual(window._research_evidence_selector.current(), 0)
        self.assertEqual(window._research_assessment_evidence_ids.value, "manual-a")
        self.assertEqual(window._research_claim_evidence_ids.value, "manual-c")
        self.assertEqual(window._research_comparison_evidence_ids.value, "manual-x")
        self.assertEqual(
            window._active_research_source_document_id,
            "document-2",
        )
        self.assertEqual(
            window._status.values,
            ["accepted source selected: document-2; no action started"],
        )

    def test_assessment_evidence_handoff_requires_source_and_appends_once(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        source = _research_source_record("document-1", "Accepted paper")
        record = _research_evidence_record(
            "evidence-2",
            source.document_id,
            "Assessment evidence.",
        )
        _configure_selected_research_evidence(window, source, record)
        window._research_source_document_id = RecordingVariable("document-other")
        window._research_assessment_evidence_ids = RecordingVariable("evidence-1")
        window._status = RecordingStatus()

        window._add_selected_research_evidence_to_assessment()
        window._research_source_document_id.set("document-1")
        window._add_selected_research_evidence_to_assessment()
        window._add_selected_research_evidence_to_assessment()

        self.assertEqual(
            window._research_assessment_evidence_ids.value,
            "evidence-1, evidence-2",
        )
        self.assertEqual(
            window._status.values,
            [
                "Use the accepted source for assessment first.",
                "evidence ID added to assessment; nothing requested or saved",
                "evidence ID is already in the assessment; nothing changed",
            ],
        )

    def test_claim_evidence_handoff_appends_once_and_preserves_limit(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        source = _research_source_record("document-1", "Accepted paper")
        record = _research_evidence_record(
            "evidence-21",
            source.document_id,
            "Claim evidence.",
        )
        _configure_selected_research_evidence(window, source, record)
        window._research_claim_evidence_ids = RecordingVariable("evidence-old")
        window._status = RecordingStatus()

        window._add_selected_research_evidence_to_claim()
        window._add_selected_research_evidence_to_claim()
        bounded_ids = ", ".join(f"evidence-{index}" for index in range(1, 21))
        window._research_claim_evidence_ids.set(bounded_ids)
        window._add_selected_research_evidence_to_claim()

        self.assertEqual(window._research_claim_evidence_ids.value, bounded_ids)
        self.assertEqual(
            window._status.values,
            [
                "evidence ID added to claim; nothing requested or saved",
                "evidence ID is already in the claim; nothing changed",
                "The claim accepts at most 20 evidence IDs.",
            ],
        )

    def test_comparison_evidence_handoff_requires_source_and_preserves_limit(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        source = _research_source_record("document-1", "Accepted paper")
        record = _research_evidence_record(
            "evidence-101",
            source.document_id,
            "Comparison evidence.",
        )
        _configure_selected_research_evidence(window, source, record)
        window._research_comparison_document_ids = RecordingVariable("document-2")
        window._research_comparison_evidence_ids = RecordingVariable("evidence-old")
        window._status = RecordingStatus()

        window._add_selected_research_evidence_to_comparison()
        window._research_comparison_document_ids.set("document-1, document-2")
        window._add_selected_research_evidence_to_comparison()
        bounded_ids = ", ".join(f"evidence-{index}" for index in range(1, 101))
        window._research_comparison_evidence_ids.set(bounded_ids)
        window._add_selected_research_evidence_to_comparison()

        self.assertEqual(window._research_comparison_evidence_ids.value, bounded_ids)
        self.assertEqual(
            window._status.values,
            [
                "Add the accepted source to the comparison first.",
                "evidence ID added to comparison; nothing requested or saved",
                "The comparison accepts at most 100 evidence IDs.",
            ],
        )

    def test_stale_evidence_selection_cannot_overwrite_manual_field(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        source = _research_source_record("document-old", "Old paper")
        record = _research_evidence_record(
            "evidence-old",
            source.document_id,
            "Old evidence.",
        )
        _configure_selected_research_evidence(window, source, record)
        window._research_run_id.set("run-new")
        window._research_claim_evidence_ids = RecordingVariable("manual-evidence")
        window._status = RecordingStatus()

        window._add_selected_research_evidence_to_claim()

        self.assertEqual(window._research_claim_evidence_ids.value, "manual-evidence")
        self.assertEqual(window._research_sources, ())
        self.assertEqual(window._research_evidence_records, ())
        self.assertEqual(window._research_evidence_selector.values, ())
        self.assertEqual(
            window._status.values,
            ["Select recorded evidence first."],
        )

    def test_the_panel_shows_relevance_judgement_reputation_and_acceptance_apart(
        self,
    ) -> None:
        """Four lines, four labels, no arithmetic between them.

        The failure this guards against is a panel that reads `Relevance:
        strong` and lets somebody conclude the source is sound. Each line names
        what produced it, and the operator's own verdict sits next to the
        ranker's without either one being folded into the other.
        """
        window: Any = object.__new__(TkinterDesktopWindow)
        _configure_research_assessment_selector(window)
        source = _research_source_record("document-1", "A paper")
        source = replace(source, url="https://doi.org/10.1000/exact")
        assessment = ResearchSourceAssessmentRecord(
            assessment_id="assessment-1",
            source_document_id="document-1",
            evidence_ids=("evidence-1",),
            text="Weak on a second read.",
            recorded_at=ASSESSMENT_NOW,
            information_trust=ResearchInformationTrust.LOW,
            usefulness=ResearchSourceUsefulness.NOT_USEFUL,
            applicability=ResearchSourceApplicability.BACKGROUND_ONLY,
            publication_status=ResearchSourcePublicationStatus.RETRACTED,
        )
        run = _research_run_with(
            sources=(source,),
            assessments=(assessment,),
            discoveries=(
                ResearchSourceDiscoveryRecord(
                    "discovery-1",
                    "request smuggling",
                    "crossref-rest-v1",
                    (
                        ResearchSourceCandidate(
                            url="https://doi.org/10.1000/exact",
                            title="Request smuggling",
                            snippet="",
                        ),
                    ),
                    ASSESSMENT_NOW,
                ),
            ),
        )

        window._render_research_source_dimensions(run, source)

        rendered = window._research_source_dimensions.get()
        self.assertIn("Relevance:", rendered)
        self.assertIn("deterministic lexical ranking", rendered)
        self.assertIn("Operator assessment:", rendered)
        self.assertIn("human judgement", rendered)
        self.assertIn("usefulness=not_useful", rendered)
        self.assertIn("publication=retracted", rendered)
        self.assertIn("Source reputation:", rendered)
        self.assertIn("Evidence status:", rendered)

    def test_a_strong_relevance_line_never_speaks_for_the_operator(self) -> None:
        """Case A on screen: the ranker says strong, the person says not useful."""
        window: Any = object.__new__(TkinterDesktopWindow)
        _configure_research_assessment_selector(window)
        source = replace(
            _research_source_record("document-1", "A paper"),
            url="https://doi.org/10.1000/exact",
        )
        run = _research_run_with(
            sources=(source,),
            assessments=(
                ResearchSourceAssessmentRecord(
                    assessment_id="assessment-1",
                    source_document_id="document-1",
                    evidence_ids=("evidence-1",),
                    text="Not worth citing.",
                    recorded_at=ASSESSMENT_NOW,
                    usefulness=ResearchSourceUsefulness.NOT_USEFUL,
                ),
            ),
            discoveries=(
                ResearchSourceDiscoveryRecord(
                    "discovery-1",
                    "request smuggling",
                    "crossref-rest-v1",
                    (
                        ResearchSourceCandidate(
                            url="https://doi.org/10.1000/exact",
                            title="Request smuggling",
                            snippet="",
                        ),
                    ),
                    ASSESSMENT_NOW,
                ),
            ),
        )

        window._render_research_source_dimensions(run, source)

        rendered = window._research_source_dimensions.get()
        relevance_line, assessment_line = rendered.splitlines()[:2]
        self.assertIn("strong", relevance_line)
        self.assertIn("usefulness=not_useful", assessment_line)
        self.assertNotIn("not_useful", relevance_line)

    def test_a_source_never_discovered_says_so_rather_than_scoring_zero(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        _configure_research_assessment_selector(window)
        source = _research_source_record("document-1", "A paper")
        run = _research_run_with(sources=(source,))

        window._render_research_source_dimensions(run, source)

        self.assertIn(
            "not among the latest discovered candidates",
            window._research_source_dimensions.get(),
        )

    def test_the_history_list_shows_which_judgement_stands_and_what_it_said(
        self,
    ) -> None:
        original = ResearchSourceAssessmentRecord(
            assessment_id="assessment-1",
            source_document_id="document-1",
            evidence_ids=("evidence-1",),
            text="Looked strong.",
            recorded_at=ASSESSMENT_NOW,
            usefulness=ResearchSourceUsefulness.USEFUL,
        )
        revised = ResearchSourceAssessmentRecord(
            assessment_id="assessment-2",
            source_document_id="document-1",
            evidence_ids=("evidence-1",),
            text="Weak after all.",
            recorded_at=ASSESSMENT_NOW,
            supersedes_assessment_id="assessment-1",
            usefulness=ResearchSourceUsefulness.NOT_USEFUL,
            publication_status=ResearchSourcePublicationStatus.RETRACTED,
        )

        superseded_label = TkinterDesktopWindow._research_assessment_label(
            original, is_current=False
        )
        current_label = TkinterDesktopWindow._research_assessment_label(
            revised, is_current=True
        )

        self.assertIn("[superseded]", superseded_label)
        self.assertIn("usefulness=useful", superseded_label)
        self.assertIn("[current]", current_label)
        self.assertIn("usefulness=not_useful", current_label)
        self.assertIn("publication=retracted", current_label)

    def test_an_unanswered_dimension_is_left_out_rather_than_shown_as_a_verdict(
        self,
    ) -> None:
        record = ResearchSourceAssessmentRecord(
            assessment_id="assessment-1",
            source_document_id="document-1",
            evidence_ids=("evidence-1",),
            text="Just a note.",
            recorded_at=ASSESSMENT_NOW,
        )

        label = TkinterDesktopWindow._research_assessment_label(
            record, is_current=True
        )

        self.assertNotIn("unknown", label)
        self.assertIn("Just a note.", label)

    def test_selected_source_renders_current_and_superseded_assessments(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 21, tzinfo=UTC)
        source = _research_source_record("document-1", "Accepted paper")
        evidence = _research_evidence_record(
            "evidence-1",
            source.document_id,
            "Assessment evidence.",
        )
        original = _research_assessment_record(
            "assessment-1",
            source.document_id,
            evidence.evidence_id,
            "Original assessment.",
        )
        correction = _research_assessment_record(
            "assessment-2",
            source.document_id,
            evidence.evidence_id,
            "Corrected\nauthored assessment.",
            supersedes_assessment_id=original.assessment_id,
        )
        run = ResearchRun(
            "run-123",
            "Review assessments",
            ResearchRunStatus.COLLECTING,
            (source,),
            (),
            now,
            now,
            evidence=(evidence,),
            assessments=(original, correction),
        )
        window._research_run_id = RecordingVariable("run-123")
        window._research_runs = (run,)
        window._visible_research_runs = (run,)
        window._research_source_run_id = "run-123"
        window._research_sources = (source,)
        window._research_source_selector = RecordingCandidateSelector(selected_index=0)
        window._research_source_choice = RecordingVariable(
            "Accepted paper — document-1"
        )
        _configure_research_evidence_selector(window)
        window._research_assessment_supersedes_id = RecordingVariable(
            "manual-predecessor"
        )
        window._research_comparison_assessment_ids = RecordingVariable(
            "manual-comparison"
        )
        window._status = RecordingStatus()

        window._select_research_source()

        self.assertEqual(
            window._research_assessment_records,
            (original, correction),
        )
        self.assertEqual(
            window._research_current_assessment_ids,
            frozenset({"assessment-2"}),
        )
        self.assertEqual(
            window._research_assessment_selector.values,
            (
                "[superseded] Original assessment. — assessment-1",
                "[current] Corrected authored assessment. — assessment-2",
            ),
        )
        self.assertEqual(window._research_assessment_selector.current(), 1)
        self.assertEqual(
            window._research_assessment_supersedes_id.value,
            "manual-predecessor",
        )
        self.assertEqual(
            window._research_comparison_assessment_ids.value,
            "manual-comparison",
        )

    def test_correction_target_handoff_requires_current_same_source_record(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        source = _research_source_record("document-1", "Accepted paper")
        original = _research_assessment_record(
            "assessment-1",
            source.document_id,
            "evidence-1",
            "Original assessment.",
        )
        correction = _research_assessment_record(
            "assessment-2",
            source.document_id,
            "evidence-1",
            "Current correction.",
            supersedes_assessment_id=original.assessment_id,
        )
        _configure_selected_research_assessments(
            window,
            source,
            (original, correction),
            current_ids=frozenset({correction.assessment_id}),
            selected_index=0,
        )
        window._research_source_document_id = RecordingVariable("document-other")
        window._research_assessment_supersedes_id = RecordingVariable(
            "manual-predecessor"
        )
        window._status = RecordingStatus()

        window._use_selected_research_assessment_as_correction_target()
        window._research_assessment_selector.current(1)
        window._use_selected_research_assessment_as_correction_target()
        window._research_source_document_id.set(source.document_id)
        window._use_selected_research_assessment_as_correction_target()

        self.assertEqual(
            window._research_assessment_supersedes_id.value,
            correction.assessment_id,
        )
        self.assertEqual(
            window._status.values,
            [
                "Only a current assessment can be corrected.",
                "Use the accepted source for assessment first.",
                "assessment ID copied as correction target; "
                "nothing requested or saved",
            ],
        )

    def test_comparison_assessment_handoff_guards_state_source_and_limit(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        source = _research_source_record("document-1", "Accepted paper")
        old = _research_assessment_record(
            "assessment-old",
            source.document_id,
            "evidence-1",
            "Superseded assessment.",
        )
        current = _research_assessment_record(
            "assessment-51",
            source.document_id,
            "evidence-1",
            "Current assessment.",
            supersedes_assessment_id=old.assessment_id,
        )
        _configure_selected_research_assessments(
            window,
            source,
            (old, current),
            current_ids=frozenset({current.assessment_id}),
            selected_index=0,
        )
        window._research_comparison_document_ids = RecordingVariable("document-2")
        window._research_comparison_assessment_ids = RecordingVariable(
            "assessment-existing"
        )
        window._status = RecordingStatus()

        window._add_selected_research_assessment_to_comparison()
        window._research_assessment_selector.current(1)
        window._add_selected_research_assessment_to_comparison()
        window._research_comparison_document_ids.set("document-1, document-2")
        window._add_selected_research_assessment_to_comparison()
        window._add_selected_research_assessment_to_comparison()
        bounded_ids = ", ".join(f"assessment-{index}" for index in range(1, 51))
        window._research_comparison_assessment_ids.set(bounded_ids)
        window._add_selected_research_assessment_to_comparison()

        self.assertEqual(
            window._research_comparison_assessment_ids.value,
            bounded_ids,
        )
        self.assertEqual(
            window._status.values,
            [
                "Only a current assessment can be compared.",
                "Add the accepted source to the comparison first.",
                "assessment ID added to comparison; nothing requested or saved",
                "assessment ID is already in the comparison; nothing changed",
                "The comparison accepts at most 50 assessment IDs.",
            ],
        )

    def test_stale_assessment_selection_cannot_overwrite_manual_field(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        source = _research_source_record("document-old", "Old paper")
        record = _research_assessment_record(
            "assessment-old",
            source.document_id,
            "evidence-old",
            "Old assessment.",
        )
        _configure_selected_research_assessments(
            window,
            source,
            (record,),
            current_ids=frozenset({record.assessment_id}),
        )
        window._research_run_id.set("run-new")
        window._research_assessment_supersedes_id = RecordingVariable(
            "manual-predecessor"
        )
        window._status = RecordingStatus()

        window._use_selected_research_assessment_as_correction_target()

        self.assertEqual(
            window._research_assessment_supersedes_id.value,
            "manual-predecessor",
        )
        self.assertEqual(window._research_sources, ())
        self.assertEqual(window._research_assessment_records, ())
        self.assertEqual(window._research_assessment_selector.values, ())
        self.assertEqual(
            window._status.values,
            ["Select an authored assessment first."],
        )

    def test_selected_run_renders_current_and_superseded_claims(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 21, tzinfo=UTC)
        source = _research_source_record("document-1", "Accepted paper")
        evidence = _research_evidence_record(
            "evidence-1",
            source.document_id,
            "Claim evidence.",
        )
        original = _research_claim_record(
            "claim-1",
            source.document_id,
            evidence.evidence_id,
            "x" * 101,
            epistemic_state=ResearchEpistemicState.HYPOTHESIS,
            confidence=ResearchClaimConfidence.LOW,
        )
        correction = _research_claim_record(
            "claim-2",
            source.document_id,
            evidence.evidence_id,
            "Corrected\nauthored claim.",
            epistemic_state=ResearchEpistemicState.STRONG_EVIDENCE,
            confidence=ResearchClaimConfidence.HIGH,
            supersedes_claim_id=original.claim_id,
        )
        run = ResearchRun(
            "run-123",
            "Review claims",
            ResearchRunStatus.COLLECTING,
            (source,),
            (),
            now,
            now,
            evidence=(evidence,),
            claims=(original, correction),
        )
        window._research_run_id = RecordingVariable("run-123")
        window._research_run_summary = RecordingVariable("")
        window._research_run_context = RecordingVariable("")
        window._research_run_progress = RecordingVariable("")
        window._research_workflow_snapshot = RecordingVariable("")
        window._research_evidence_coverage = RecordingVariable("")
        window._research_assessment_coverage = RecordingVariable("")
        window._research_run_metadata = RecordingVariable("")
        window._research_run_selector = RecordingCandidateSelector(selected_index=0)
        window._research_runs = (run,)
        window._visible_research_runs = (run,)
        window._research_source_choice = RecordingVariable("")
        window._research_source_selector = RecordingCandidateSelector()
        window._research_sources = ()
        window._research_source_run_id = ""
        _configure_research_evidence_selector(window)
        window._research_claim_supersedes_id = RecordingVariable("manual-predecessor")
        window._research_claim_contradiction_ids = RecordingVariable("manual-pair")
        window._status = RecordingStatus()

        window._select_research_run()

        self.assertEqual(window._research_claim_records, (original, correction))
        self.assertEqual(
            window._research_current_claim_ids,
            frozenset({correction.claim_id}),
        )
        self.assertEqual(
            window._research_claim_selector.values,
            (
                f"[superseded] [hypothesis/low] {'x' * 97}... — claim-1",
                "[current] [strong_evidence/high] Corrected authored claim. — claim-2",
            ),
        )
        self.assertEqual(window._research_claim_selector.current(), 1)
        self.assertEqual(
            window._research_claim_supersedes_id.value,
            "manual-predecessor",
        )
        self.assertEqual(
            window._research_claim_contradiction_ids.value,
            "manual-pair",
        )

    def test_claim_predecessor_handoff_requires_current_record(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        original = _research_claim_record(
            "claim-1",
            "document-1",
            "evidence-1",
            "Original claim.",
        )
        correction = _research_claim_record(
            "claim-2",
            "document-1",
            "evidence-1",
            "Current correction.",
            supersedes_claim_id=original.claim_id,
        )
        _configure_selected_research_claims(
            window,
            (original, correction),
            current_ids=frozenset({correction.claim_id}),
            selected_index=0,
        )
        window._research_claim_supersedes_id = RecordingVariable("manual-predecessor")
        window._status = RecordingStatus()

        window._use_selected_research_claim_as_predecessor()
        window._research_claim_selector.current(1)
        window._use_selected_research_claim_as_predecessor()

        self.assertEqual(
            window._research_claim_supersedes_id.value,
            correction.claim_id,
        )
        self.assertEqual(
            window._status.values,
            [
                "Only a current claim can be superseded.",
                "claim ID copied as predecessor; nothing requested or saved",
            ],
        )

    def test_claim_contradiction_handoff_guards_state_duplicate_and_limit(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        old = _research_claim_record(
            "claim-old",
            "document-1",
            "evidence-1",
            "Superseded claim.",
        )
        first = _research_claim_record(
            "claim-first",
            "document-1",
            "evidence-1",
            "First current claim.",
            supersedes_claim_id=old.claim_id,
        )
        second = _research_claim_record(
            "claim-second",
            "document-1",
            "evidence-1",
            "Second current claim.",
        )
        third = _research_claim_record(
            "claim-third",
            "document-1",
            "evidence-1",
            "Third current claim.",
        )
        _configure_selected_research_claims(
            window,
            (old, first, second, third),
            current_ids=frozenset({first.claim_id, second.claim_id, third.claim_id}),
            selected_index=0,
        )
        window._research_claim_contradiction_ids = RecordingVariable("")
        window._status = RecordingStatus()

        window._add_selected_research_claim_to_contradiction()
        window._research_claim_selector.current(1)
        window._add_selected_research_claim_to_contradiction()
        window._add_selected_research_claim_to_contradiction()
        window._research_claim_selector.current(2)
        window._add_selected_research_claim_to_contradiction()
        window._research_claim_selector.current(3)
        window._add_selected_research_claim_to_contradiction()

        self.assertEqual(
            window._research_claim_contradiction_ids.value,
            "claim-first, claim-second",
        )
        self.assertEqual(
            window._status.values,
            [
                "Only a current claim can be used in a contradiction.",
                "claim ID added to contradiction; nothing requested or saved",
                "claim ID is already in the contradiction; nothing changed",
                "claim ID added to contradiction; nothing requested or saved",
                "A contradiction accepts exactly two claim IDs.",
            ],
        )

    def test_stale_claim_selection_cannot_overwrite_manual_fields(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        record = _research_claim_record(
            "claim-old",
            "document-old",
            "evidence-old",
            "Old claim.",
        )
        _configure_selected_research_claims(
            window,
            (record,),
            current_ids=frozenset({record.claim_id}),
        )
        window._research_run_id.set("run-new")
        window._research_claim_supersedes_id = RecordingVariable("manual-predecessor")
        window._research_claim_contradiction_ids = RecordingVariable("manual-pair")
        window._status = RecordingStatus()

        window._use_selected_research_claim_as_predecessor()

        self.assertEqual(
            window._research_claim_supersedes_id.value,
            "manual-predecessor",
        )
        self.assertEqual(
            window._research_claim_contradiction_ids.value,
            "manual-pair",
        )
        self.assertEqual(window._research_claim_records, ())
        self.assertEqual(window._research_current_claim_ids, frozenset())
        self.assertEqual(window._research_claim_run_id, "")
        self.assertEqual(window._research_claim_selector.values, ())
        self.assertEqual(
            window._status.values,
            ["Select an authored claim first."],
        )

    def test_selected_run_renders_recorded_contradictions_from_snapshot(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 21, tzinfo=UTC)
        source = _research_source_record("document-1", "Accepted paper")
        first_evidence = _research_evidence_record(
            "evidence-1",
            source.document_id,
            "First claim evidence.",
        )
        second_evidence = _research_evidence_record(
            "evidence-2",
            source.document_id,
            "Second claim evidence.",
        )
        first_claim = _research_claim_record(
            "claim-1",
            source.document_id,
            first_evidence.evidence_id,
            "First claim.",
        )
        second_claim = _research_claim_record(
            "claim-2",
            source.document_id,
            second_evidence.evidence_id,
            "Second claim.",
        )
        contradiction = _research_claim_contradiction_record(
            "contradiction-1",
            first_claim.claim_id,
            second_claim.claim_id,
            (first_evidence.evidence_id, second_evidence.evidence_id),
            "x" * 101,
        )
        run = ResearchRun(
            "run-123",
            "Review contradictions",
            ResearchRunStatus.COLLECTING,
            (source,),
            (),
            now,
            now,
            evidence=(first_evidence, second_evidence),
            claims=(first_claim, second_claim),
            claim_contradictions=(contradiction,),
        )
        window._research_run_id = RecordingVariable("run-123")
        window._research_run_summary = RecordingVariable("")
        window._research_run_context = RecordingVariable("")
        window._research_run_progress = RecordingVariable("")
        window._research_workflow_snapshot = RecordingVariable("")
        window._research_evidence_coverage = RecordingVariable("")
        window._research_assessment_coverage = RecordingVariable("")
        window._research_run_metadata = RecordingVariable("")
        window._research_run_selector = RecordingCandidateSelector(selected_index=0)
        window._research_runs = (run,)
        window._visible_research_runs = (run,)
        window._research_source_choice = RecordingVariable("")
        window._research_source_selector = RecordingCandidateSelector()
        window._research_sources = ()
        window._research_source_run_id = ""
        _configure_research_evidence_selector(window)
        window._research_claim_contradiction_ids = RecordingVariable("manual-pair")
        window._research_claim_contradiction_note = RecordingVariable("manual-note")
        window._status = RecordingStatus()

        window._select_research_run()

        self.assertEqual(
            window._research_persisted_contradiction_records,
            (contradiction,),
        )
        self.assertEqual(
            window._research_persisted_contradiction_run_id,
            run.run_id,
        )
        self.assertEqual(
            window._research_persisted_contradiction_selector.values,
            (
                f"[2026-08-21T00:00:00+00:00] claim-1 ↔ claim-2 | "
                f"{'x' * 97}... — contradiction-1",
            ),
        )
        self.assertEqual(
            window._research_persisted_contradiction_selector.current(),
            0,
        )
        self.assertEqual(window._research_claim_contradiction_ids.value, "manual-pair")
        self.assertEqual(window._research_claim_contradiction_note.value, "manual-note")

    def test_recorded_contradiction_handoff_copies_pair_and_preserves_note(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        record = _research_claim_contradiction_record(
            "contradiction-1",
            "claim-1",
            "claim-2",
            ("evidence-1", "evidence-2"),
            "Recorded contradiction.",
        )
        _configure_selected_persisted_contradictions(window, (record,))
        window._research_claim_contradiction_ids = RecordingVariable("manual-pair")
        window._research_claim_contradiction_note = RecordingVariable("manual-note")
        window._status = RecordingStatus()

        window._use_selected_persisted_contradiction_pair()

        self.assertEqual(
            window._research_claim_contradiction_ids.value,
            "claim-1, claim-2",
        )
        self.assertEqual(window._research_claim_contradiction_note.value, "manual-note")
        self.assertEqual(
            window._status.values,
            [
                "recorded claim pair copied; note unchanged; "
                "nothing requested or saved"
            ],
        )

    def test_stale_recorded_contradiction_cannot_overwrite_manual_fields(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        record = _research_claim_contradiction_record(
            "contradiction-old",
            "claim-old-1",
            "claim-old-2",
            ("evidence-old-1", "evidence-old-2"),
            "Old contradiction.",
        )
        _configure_selected_persisted_contradictions(window, (record,))
        window._research_run_id.set("run-new")
        window._research_claim_contradiction_ids = RecordingVariable("manual-pair")
        window._research_claim_contradiction_note = RecordingVariable("manual-note")
        window._status = RecordingStatus()

        window._use_selected_persisted_contradiction_pair()

        self.assertEqual(window._research_claim_contradiction_ids.value, "manual-pair")
        self.assertEqual(window._research_claim_contradiction_note.value, "manual-note")
        self.assertEqual(window._research_persisted_contradiction_records, ())
        self.assertEqual(window._research_persisted_contradiction_run_id, "")
        self.assertEqual(
            window._research_persisted_contradiction_selector.values,
            (),
        )
        self.assertEqual(
            window._status.values,
            ["Select a recorded contradiction first."],
        )

    def test_invalid_recorded_contradiction_selection_preserves_manual_fields(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        record = _research_claim_contradiction_record(
            "contradiction-1",
            "claim-1",
            "claim-2",
            ("evidence-1", "evidence-2"),
            "Recorded contradiction.",
        )
        _configure_selected_persisted_contradictions(
            window,
            (record,),
            selected_index=-1,
        )
        window._research_claim_contradiction_ids = RecordingVariable("manual-pair")
        window._research_claim_contradiction_note = RecordingVariable("manual-note")
        window._status = RecordingStatus()

        window._use_selected_persisted_contradiction_pair()

        self.assertEqual(window._research_claim_contradiction_ids.value, "manual-pair")
        self.assertEqual(window._research_claim_contradiction_note.value, "manual-note")
        self.assertEqual(
            window._status.values,
            ["Select a recorded contradiction first."],
        )

    def test_selected_run_renders_recorded_comparison_notes_and_exact_references(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        now = datetime(2026, 8, 21, tzinfo=UTC)
        first_source = _research_source_record("document-1", "First paper")
        second_source = _research_source_record("document-2", "Second paper")
        first_evidence = _research_evidence_record(
            "evidence-1",
            first_source.document_id,
            "First evidence.",
        )
        second_evidence = _research_evidence_record(
            "evidence-2",
            second_source.document_id,
            "Second evidence.",
        )
        first_assessment = _research_assessment_record(
            "assessment-1",
            first_source.document_id,
            first_evidence.evidence_id,
            "First assessment.",
        )
        second_assessment = _research_assessment_record(
            "assessment-2",
            second_source.document_id,
            second_evidence.evidence_id,
            "Second assessment.",
        )
        note = _research_comparison_note_record(
            "note-1",
            (first_source.document_id, second_source.document_id),
            (first_evidence.evidence_id, second_evidence.evidence_id),
            (first_assessment.assessment_id, second_assessment.assessment_id),
            "x" * 101,
        )
        run = ResearchRun(
            "run-123",
            "Review comparison notes",
            ResearchRunStatus.COLLECTING,
            (first_source, second_source),
            (),
            now,
            now,
            evidence=(first_evidence, second_evidence),
            assessments=(first_assessment, second_assessment),
            comparison_notes=(note,),
        )
        window._research_run_id = RecordingVariable("run-123")
        window._research_run_summary = RecordingVariable("")
        window._research_run_context = RecordingVariable("")
        window._research_run_progress = RecordingVariable("")
        window._research_workflow_snapshot = RecordingVariable("")
        window._research_evidence_coverage = RecordingVariable("")
        window._research_assessment_coverage = RecordingVariable("")
        window._research_run_metadata = RecordingVariable("")
        window._research_run_selector = RecordingCandidateSelector(selected_index=0)
        window._research_runs = (run,)
        window._visible_research_runs = (run,)
        window._research_source_choice = RecordingVariable("")
        window._research_source_selector = RecordingCandidateSelector()
        window._research_sources = ()
        window._research_source_run_id = ""
        _configure_research_evidence_selector(window)
        window._research_comparison_document_ids = RecordingVariable("manual-sources")
        window._research_comparison_evidence_ids = RecordingVariable("manual-evidence")
        window._research_comparison_assessment_ids = RecordingVariable(
            "manual-assessments"
        )
        window._research_comparison_note_text = RecordingVariable("manual-note")
        window._status = RecordingStatus()

        window._select_research_run()

        self.assertEqual(
            window._research_persisted_comparison_note_records,
            (note,),
        )
        self.assertEqual(
            window._research_persisted_comparison_note_run_id,
            run.run_id,
        )
        self.assertEqual(
            window._research_persisted_comparison_note_selector.values,
            (f"[2026-08-21T00:00:00+00:00] {'x' * 97}... — note-1",),
        )
        self.assertEqual(
            window._research_persisted_comparison_note_references.value,
            "Sources: document-1, document-2\n"
            "Evidence: evidence-1, evidence-2\n"
            "Assessments: assessment-1, assessment-2",
        )
        self.assertEqual(
            window._research_comparison_document_ids.value, "manual-sources"
        )
        self.assertEqual(
            window._research_comparison_evidence_ids.value, "manual-evidence"
        )
        self.assertEqual(
            window._research_comparison_assessment_ids.value,
            "manual-assessments",
        )
        self.assertEqual(window._research_comparison_note_text.value, "manual-note")

    def test_recorded_comparison_note_selection_updates_read_only_references(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        first = _research_comparison_note_record(
            "note-1",
            ("document-1", "document-2"),
            ("evidence-1", "evidence-2"),
            ("assessment-1", "assessment-2"),
            "First comparison.",
        )
        second = _research_comparison_note_record(
            "note-2",
            ("document-2", "document-3"),
            ("evidence-2", "evidence-3"),
            ("assessment-2", "assessment-3"),
            "Second comparison.",
        )
        _configure_selected_persisted_comparison_notes(
            window,
            (first, second),
            selected_index=1,
        )
        window._research_comparison_document_ids = RecordingVariable("manual-sources")
        window._research_comparison_evidence_ids = RecordingVariable("manual-evidence")
        window._research_comparison_assessment_ids = RecordingVariable(
            "manual-assessments"
        )
        window._research_comparison_note_text = RecordingVariable("manual-note")
        window._status = RecordingStatus()

        window._select_persisted_research_comparison_note()

        self.assertEqual(
            window._research_persisted_comparison_note_references.value,
            "Sources: document-2, document-3\n"
            "Evidence: evidence-2, evidence-3\n"
            "Assessments: assessment-2, assessment-3",
        )
        self.assertEqual(
            window._research_comparison_document_ids.value, "manual-sources"
        )
        self.assertEqual(
            window._research_comparison_evidence_ids.value, "manual-evidence"
        )
        self.assertEqual(
            window._research_comparison_assessment_ids.value,
            "manual-assessments",
        )
        self.assertEqual(window._research_comparison_note_text.value, "manual-note")
        self.assertEqual(
            window._status.values,
            ["recorded comparison note selected: note-2; no action started"],
        )

    def test_recorded_comparison_note_handoffs_copy_only_selected_references(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        record = _research_comparison_note_record(
            "note-1",
            ("document-1", "document-2"),
            ("evidence-1", "evidence-2"),
            ("assessment-1", "assessment-2"),
            "Recorded comparison.",
        )
        _configure_selected_persisted_comparison_notes(window, (record,))
        window._research_comparison_document_ids = RecordingVariable("old-sources")
        window._research_comparison_evidence_ids = RecordingVariable("old-evidence")
        window._research_comparison_assessment_ids = RecordingVariable(
            "old-assessments"
        )
        window._research_comparison_note_text = RecordingVariable("manual-note")
        window._status = RecordingStatus()

        window._use_selected_persisted_comparison_note_sources()
        window._use_selected_persisted_comparison_note_evidence()
        window._use_selected_persisted_comparison_note_assessments()

        self.assertEqual(
            window._research_comparison_document_ids.value,
            "document-1, document-2",
        )
        self.assertEqual(
            window._research_comparison_evidence_ids.value,
            "evidence-1, evidence-2",
        )
        self.assertEqual(
            window._research_comparison_assessment_ids.value,
            "assessment-1, assessment-2",
        )
        self.assertEqual(window._research_comparison_note_text.value, "manual-note")
        self.assertEqual(
            window._status.values,
            [
                "recorded comparison source IDs copied; other fields unchanged; "
                "nothing requested or saved",
                "recorded comparison evidence IDs copied; other fields unchanged; "
                "nothing requested or saved",
                "recorded comparison assessment IDs copied; other fields unchanged; "
                "nothing requested or saved",
            ],
        )

    def test_stale_recorded_comparison_note_cannot_overwrite_manual_fields(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        record = _research_comparison_note_record(
            "note-old",
            ("document-old-1", "document-old-2"),
            ("evidence-old-1", "evidence-old-2"),
            ("assessment-old-1", "assessment-old-2"),
            "Old comparison.",
        )
        _configure_selected_persisted_comparison_notes(window, (record,))
        window._research_run_id.set("run-new")
        window._research_comparison_document_ids = RecordingVariable("manual-sources")
        window._research_comparison_evidence_ids = RecordingVariable("manual-evidence")
        window._research_comparison_assessment_ids = RecordingVariable(
            "manual-assessments"
        )
        window._research_comparison_note_text = RecordingVariable("manual-note")
        window._status = RecordingStatus()

        window._use_selected_persisted_comparison_note_sources()

        self.assertEqual(
            window._research_comparison_document_ids.value, "manual-sources"
        )
        self.assertEqual(
            window._research_comparison_evidence_ids.value, "manual-evidence"
        )
        self.assertEqual(
            window._research_comparison_assessment_ids.value,
            "manual-assessments",
        )
        self.assertEqual(window._research_comparison_note_text.value, "manual-note")
        self.assertEqual(window._research_persisted_comparison_note_records, ())
        self.assertEqual(window._research_persisted_comparison_note_run_id, "")
        self.assertEqual(
            window._research_persisted_comparison_note_selector.values,
            (),
        )
        self.assertEqual(
            window._research_persisted_comparison_note_references.value,
            "",
        )
        self.assertEqual(
            window._status.values,
            ["Select a recorded comparison note first."],
        )

    def test_research_markdown_export_preview_uses_selected_run_only(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._preview_research_run_markdown_export()

        self.assertEqual(controller.export_previews, ["run-123"])
        self.assertEqual(controller.sources, [])
        self.assertEqual(responses, [controller.export_preview_response])
        self.assertIs(
            window._research_markdown_export_preview,
            controller.export_preview_response.research_run_markdown_export_preview,
        )

    def test_research_markdown_export_preview_reports_empty_selection_locally(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        status = RecordingStatus()
        window._controller = controller
        window._research_run_id = RecordingInput("  ")
        window._status = status
        window._append_response = responses.append

        window._preview_research_run_markdown_export()

        self.assertEqual(controller.export_previews, [])
        self.assertIn("run ID cannot be empty", status.values[-1])
        self.assertEqual(responses, [])

    def test_research_markdown_export_save_uses_only_confirmed_current_preview(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        destination = str(Path.cwd() / "saved-research.md")
        preview = (
            controller.export_preview_response.research_run_markdown_export_preview
        )
        assert preview is not None
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_markdown_export_preview = preview
        window._status = RecordingStatus()
        window._append_response = responses.append

        with (
            patch(
                "desktop.TkinterDesktopWindow.filedialog.asksaveasfilename",
                return_value=destination,
            ) as choose_file,
            patch(
                "desktop.TkinterDesktopWindow.messagebox.askyesno",
                return_value=True,
            ) as confirm,
        ):
            window._save_research_run_markdown_export()

        self.assertEqual(controller.export_saves, [(preview, destination)])
        self.assertEqual(responses, [controller.export_save_response])
        self.assertEqual(
            choose_file.call_args.kwargs["initialfile"],
            preview.suggested_filename,
        )
        self.assertIn(destination, confirm.call_args.args[1])
        self.assertIn(preview.content_sha256, confirm.call_args.args[1])

    def test_research_markdown_export_save_requires_matching_preview(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        preview = (
            controller.export_preview_response.research_run_markdown_export_preview
        )
        assert preview is not None
        window._controller = controller
        window._research_run_id = RecordingInput("different-run")
        window._research_markdown_export_preview = preview
        window._status = status

        with patch(
            "desktop.TkinterDesktopWindow.filedialog.asksaveasfilename"
        ) as choose_file:
            window._save_research_run_markdown_export()

        choose_file.assert_not_called()
        self.assertEqual(controller.export_saves, [])
        self.assertIn("Preview the selected", status.values[-1])

    def test_research_markdown_export_verification_uses_selected_file_read_only(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        source = str(Path.cwd() / "existing-research.md")
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._status = RecordingStatus()
        window._append_response = responses.append

        with patch(
            "desktop.TkinterDesktopWindow.filedialog.askopenfilename",
            return_value=source,
        ) as choose_file:
            window._verify_research_run_markdown_export()

        self.assertEqual(controller.export_verifications, [("run-123", source)])
        self.assertEqual(responses, [controller.export_verification_response])
        self.assertEqual(
            choose_file.call_args.kwargs["title"],
            "Verify existing research Markdown export",
        )
        self.assertEqual(
            choose_file.call_args.kwargs["filetypes"],
            [("Markdown files", "*.md")],
        )

    def test_research_markdown_export_verification_handles_empty_or_cancelled_choice(
        self,
    ) -> None:
        controller = RecordingResearchSourceLoadController()
        for run_id, selected_path, expected_status in (
            ("", "unused.md", "run ID cannot be empty"),
            ("run-123", "", "verification: cancelled"),
        ):
            window: Any = object.__new__(TkinterDesktopWindow)
            status = RecordingStatus()
            window._root = object()
            window._controller = controller
            window._research_run_id = RecordingInput(run_id)
            window._status = status
            window._append_response = lambda _response: self.fail("must not append")

            with patch(
                "desktop.TkinterDesktopWindow.filedialog.askopenfilename",
                return_value=selected_path,
            ) as choose_file:
                window._verify_research_run_markdown_export()

            if not run_id:
                choose_file.assert_not_called()
            self.assertIn(expected_status, status.values[-1])

        self.assertEqual(controller.export_verifications, [])

    def test_discovery_renders_unaccepted_candidates_without_loading_them(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        selector = RecordingCandidateSelector()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_candidate = RecordingVariable("stale")
        window._research_candidate_selector = selector
        window._research_candidates = ()
        window._research_candidate_run_id = ""
        window._status = RecordingStatus()
        window._append_response = responses.append
        _configure_request_boundary(window)

        window._discover_research_sources()
        window._poll_requests()

        self.assertEqual(controller.discovery_calls, ["run-123"])
        self.assertEqual(len(controller.discovery_cancellation_tokens), 1)
        self.assertIsNotNone(controller.discovery_cancellation_tokens[0])
        self.assertEqual(controller.sources, [])
        self.assertEqual(responses, [controller.discovery_response])
        self.assertEqual(
            set(window._research_candidates), set(controller.candidates)
        )
        self.assertEqual(window._research_candidate_run_id, "run-123")
        # The exact label text is no longer asserted, because the list is now
        # ordered by relevance rather than by arrival and the label carries the
        # score that produced the order. What has to stay true is what this
        # test is named for: every discovered candidate is offered, each row
        # still shows its title and its URL, and nothing was fetched.
        self.assertEqual(len(selector.values), len(controller.candidates))
        for candidate in controller.candidates:
            with self.subTest(candidate=candidate.url):
                self.assertTrue(
                    any(
                        candidate.title in label and candidate.url in label
                        for label in selector.values
                    )
                )
        for position, label in enumerate(selector.values, start=1):
            with self.subTest(row=position):
                self.assertTrue(label.startswith(f"{position}. "))
                self.assertIn("provider #", label)
        self.assertEqual(selector.selected_index, 0)
        self.assertEqual(controller.sources, [])

    def test_selected_candidate_only_copies_its_url_until_load_is_separate(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        selector = RecordingCandidateSelector(selected_index=1)
        url = RecordingVariable("")
        status = RecordingStatus()
        window._controller = controller
        window._research_candidate_selector = selector
        window._research_candidates = controller.candidates
        window._research_candidate_run_id = "run-123"
        window._research_run_id = RecordingInput("run-123")
        window._research_url = url
        window._status = status

        window._use_selected_research_candidate()

        self.assertEqual(url.value, "https://doi.org/10.1000/second")
        self.assertEqual(controller.sources, [])
        self.assertEqual(
            status.values,
            ["research candidate: URL copied; source not loaded"],
        )

    def test_missing_candidate_selection_does_not_copy_or_load_a_url(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        url = RecordingVariable("https://example.com/existing")
        status = RecordingStatus()
        window._controller = controller
        window._research_candidate_selector = RecordingCandidateSelector()
        window._research_candidates = ()
        window._research_candidate_run_id = "run-123"
        window._research_run_id = RecordingInput("run-123")
        window._research_url = url
        window._status = status

        window._use_selected_research_candidate()

        self.assertEqual(url.value, "https://example.com/existing")
        self.assertEqual(controller.sources, [])
        self.assertEqual(
            status.values,
            ["Select a discovered source candidate first."],
        )

    def test_candidate_from_another_run_cannot_be_copied(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        url = RecordingVariable("")
        status = RecordingStatus()
        window._controller = controller
        window._research_candidate_selector = RecordingCandidateSelector(
            selected_index=0
        )
        window._research_candidates = controller.candidates
        window._research_candidate_run_id = "run-123"
        window._research_run_id = RecordingInput("run-456")
        window._research_url = url
        window._status = status

        window._use_selected_research_candidate()

        self.assertEqual(url.value, "")
        self.assertEqual(controller.sources, [])
        self.assertEqual(
            status.values,
            ["Select a discovered source candidate first."],
        )

    def test_empty_run_id_stays_local_before_candidate_discovery(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._controller = controller
        window._research_run_id = RecordingInput("  ")
        window._status = status
        window._append_response = lambda _response: self.fail("must not append")
        _configure_request_boundary(window)

        window._discover_research_sources()
        window._poll_requests()

        self.assertEqual(controller.discovery_calls, [])
        self.assertEqual(status.values[-1], "A research run ID cannot be empty.")

    def test_selected_chunk_and_note_are_passed_to_evidence_boundary(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_chunk_id = RecordingInput("chunk-456")
        window._research_evidence_note = RecordingInput("Supports the comparison.")
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._record_research_evidence()

        self.assertEqual(
            controller.evidence_calls,
            [("run-123", "chunk-456", "Supports the comparison.")],
        )
        self.assertEqual(responses, [controller.evidence_response])

    def test_empty_evidence_note_stays_local_and_is_shown_as_status(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_chunk_id = RecordingInput("chunk-456")
        window._research_evidence_note = RecordingInput(" ")
        window._status = status
        window._append_response = lambda _response: self.fail("must not append")

        window._record_research_evidence()

        self.assertEqual(controller.evidence_calls, [])
        self.assertEqual(
            status.values,
            ["A research evidence note cannot be empty."],
        )

    def test_selected_run_evidence_catalog_is_requested_read_only(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._show_research_evidence()

        self.assertEqual(controller.evidence_list_calls, ["run-123"])
        self.assertEqual(responses, [controller.evidence_list_response])

    def test_source_assessment_preview_uses_selected_run_and_document(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_source_document_id = RecordingInput("document-123")
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._preview_research_source_assessment()

        self.assertEqual(
            controller.assessment_previews,
            [("run-123", "document-123")],
        )
        self.assertEqual(responses, [controller.assessment_preview_response])

    def test_source_comparison_uses_selected_run_and_explicit_source_ids(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_comparison_document_ids = RecordingInput(
            "document-2, document-1"
        )
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._preview_research_source_comparison()

        self.assertEqual(
            controller.comparison_previews,
            [("run-123", "document-2, document-1")],
        )
        self.assertEqual(responses, [controller.comparison_preview_response])

    def test_allowed_comparison_note_requires_confirmation_before_record(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        values = (
            "run-123",
            "document-2, document-1",
            "evidence-2, evidence-1",
            "assessment-2, assessment-1",
            "My comparison note.",
        )
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput(values[0])
        window._research_comparison_document_ids = RecordingInput(values[1])
        window._research_comparison_evidence_ids = RecordingInput(values[2])
        window._research_comparison_assessment_ids = RecordingInput(values[3])
        window._research_comparison_note_text = RecordingInput(values[4])
        window._status = RecordingStatus()
        window._append_response = responses.append

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=True,
        ) as confirm:
            window._preview_and_record_research_source_comparison_note()

        self.assertEqual(controller.comparison_note_previews, [values])
        self.assertEqual(controller.comparison_note_records, [values])
        self.assertEqual(
            responses,
            [
                controller.comparison_note_preview_response,
                controller.comparison_note_record_response,
            ],
        )
        confirm.assert_called_once()

    def test_declined_comparison_note_preview_never_records(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_comparison_document_ids = RecordingInput(
            "document-1,document-2"
        )
        window._research_comparison_evidence_ids = RecordingInput(
            "evidence-1,evidence-2"
        )
        window._research_comparison_assessment_ids = RecordingInput(
            "assessment-1,assessment-2"
        )
        window._research_comparison_note_text = RecordingInput("Note.")
        window._status = RecordingStatus()
        window._append_response = lambda _response: None

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=False,
        ):
            window._preview_and_record_research_source_comparison_note()

        self.assertEqual(controller.comparison_note_records, [])

    def test_accepted_load_selects_its_source_document_for_assessment(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        selected = RecordingVariable("")
        window._research_source_document_id = selected
        now = datetime(2026, 8, 20, tzinfo=UTC)
        source = ResearchSourceRecord(
            "document-123",
            "https://example.com/paper",
            "Paper",
            "text/plain",
            now,
            now,
        )
        run = ResearchRun(
            "run-123",
            "Question",
            ResearchRunStatus.COLLECTING,
            (source,),
            (),
            now,
            now,
        )
        response = BrainResponse(
            message="Loaded.",
            request_id="load",
            intent="research_source_load",
            memory_count=0,
            knowledge_documents=[
                KnowledgeDocumentReference(
                    "document-123",
                    "Paper",
                    "https://example.com/paper",
                    DocumentType.WEB,
                    1,
                )
            ],
            research_runs=[run],
        )

        window._capture_accepted_research_source(response)

        self.assertEqual(selected.value, "document-123")

    def test_empty_source_assessment_document_stays_local(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_source_document_id = RecordingInput(" ")
        window._status = status
        window._append_response = lambda _response: self.fail("must not append")

        window._preview_research_source_assessment()

        self.assertEqual(controller.assessment_previews, [])
        self.assertEqual(
            status.values,
            ["A research source document ID cannot be empty."],
        )

    def test_allowed_authored_assessment_requires_confirmation_before_record(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        values = (
            "run-123",
            "document-123",
            "evidence-123",
            "Corrected assessment.",
            "assessment-original",
            "high",
            # The structured judgement travels with the text, and it travels
            # exactly as chosen: two dimensions answered, two left unknown.
            "useful",
            "direct",
            "unknown",
            "unknown",
        )
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput(values[0])
        window._research_source_document_id = RecordingInput(values[1])
        window._research_assessment_evidence_ids = RecordingInput(values[2])
        window._research_assessment_text = RecordingInput(values[3])
        window._research_assessment_supersedes_id = RecordingInput(values[4])
        window._research_information_trust = RecordingInput(values[5])
        _configure_source_judgement(window, "useful", "direct")
        window._status = RecordingStatus()
        window._append_response = responses.append

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=True,
        ) as confirm:
            window._preview_and_record_research_source_assessment()

        self.assertEqual(controller.assessment_write_previews, [values])
        self.assertEqual(controller.assessment_records, [values])
        self.assertEqual(
            responses,
            [
                controller.assessment_write_preview_response,
                controller.assessment_record_response,
            ],
        )
        confirm.assert_called_once()

    def test_declined_or_blocked_assessment_preview_never_records(self) -> None:
        for blocked in (False, True):
            with self.subTest(blocked=blocked):
                window: Any = object.__new__(TkinterDesktopWindow)
                controller = RecordingResearchSourceLoadController()
                if blocked:
                    preview = controller.assessment_write_preview_response
                    assert preview.research_source_assessment_write_preview is not None
                    blocked_preview = ResearchSourceAssessmentWritePreview(
                        run_id="run-123",
                        run_status=ResearchRunStatus.CANCELLED,
                        source=(
                            preview.research_source_assessment_write_preview.source
                        ),
                        evidence=(
                            preview.research_source_assessment_write_preview.evidence
                        ),
                        text="Assessment.",
                        allowed=False,
                        reason="A closed research run cannot accept new assessments.",
                    )
                    controller.assessment_write_preview_response = BrainResponse(
                        message="Assessment preview blocked.",
                        request_id="assessment-preview-blocked",
                        intent="research_source_assessment_write_preview",
                        memory_count=0,
                        success=False,
                        research_source_assessment_write_preview=blocked_preview,
                    )
                window._root = object()
                window._controller = controller
                window._research_run_id = RecordingInput("run-123")
                window._research_source_document_id = RecordingInput("document-123")
                window._research_assessment_evidence_ids = RecordingInput(
                    "evidence-123"
                )
                window._research_assessment_text = RecordingInput("Assessment.")
                window._research_assessment_supersedes_id = RecordingInput("")
                window._research_information_trust = RecordingInput("medium")
                _configure_source_judgement(window)
                window._status = RecordingStatus()
                window._append_response = lambda _response: None

                with patch(
                    "desktop.TkinterDesktopWindow.messagebox.askyesno",
                    return_value=False,
                ) as confirm:
                    window._preview_and_record_research_source_assessment()

                self.assertEqual(controller.assessment_records, [])
                if blocked:
                    confirm.assert_not_called()
                else:
                    confirm.assert_called_once()

    def test_empty_authored_assessment_stays_local(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_source_document_id = RecordingInput("document-123")
        window._research_assessment_evidence_ids = RecordingInput("")
        window._research_assessment_text = RecordingInput("Assessment.")
        window._research_assessment_supersedes_id = RecordingInput("")
        window._research_information_trust = RecordingInput("unassessed")
        _configure_source_judgement(window)
        window._status = status
        window._append_response = lambda _response: self.fail("must not append")

        window._preview_and_record_research_source_assessment()

        self.assertEqual(controller.assessment_write_previews, [])
        self.assertEqual(controller.assessment_records, [])
        self.assertEqual(
            status.values,
            ["Research assessment evidence IDs cannot be empty."],
        )

    def test_claim_history_preview_uses_selected_run(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._preview_research_claims()

        self.assertEqual(controller.claim_previews, ["run-123"])
        self.assertEqual(responses, [controller.claim_preview_response])

    def test_allowed_claim_requires_confirmation_before_record(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        values = (
            "run-123",
            "evidence-123",
            "The evidence supports a bounded claim.",
            "strong_evidence",
            "high",
            "claim-original",
        )
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput(values[0])
        window._research_claim_evidence_ids = RecordingInput(values[1])
        window._research_claim_text = RecordingInput(values[2])
        window._research_claim_epistemic_state = RecordingInput(values[3])
        window._research_claim_confidence = RecordingInput(values[4])
        window._research_claim_supersedes_id = RecordingInput(values[5])
        window._status = RecordingStatus()
        window._append_response = responses.append

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=True,
        ) as confirm:
            window._preview_and_record_research_claim()

        self.assertEqual(controller.claim_write_previews, [values])
        self.assertEqual(controller.claim_records, [values])
        self.assertEqual(
            responses,
            [controller.claim_write_preview_response, controller.claim_record_response],
        )
        confirm.assert_called_once()

    def test_declined_or_blocked_claim_preview_never_records(self) -> None:
        for blocked in (False, True):
            with self.subTest(blocked=blocked):
                window: Any = object.__new__(TkinterDesktopWindow)
                controller = RecordingResearchSourceLoadController()
                if blocked:
                    preview = controller.claim_write_preview_response
                    assert preview.research_claim_write_preview is not None
                    allowed_preview = preview.research_claim_write_preview
                    controller.claim_write_preview_response = BrainResponse(
                        message="Claim preview blocked.",
                        request_id="claim-preview-blocked",
                        intent="research_claim_write_preview",
                        memory_count=0,
                        success=False,
                        research_claim_write_preview=ResearchClaimWritePreview(
                            run_id=allowed_preview.run_id,
                            run_status=ResearchRunStatus.CANCELLED,
                            sources=allowed_preview.sources,
                            evidence=allowed_preview.evidence,
                            text=allowed_preview.text,
                            epistemic_state=allowed_preview.epistemic_state,
                            confidence=allowed_preview.confidence,
                            allowed=False,
                            reason="A closed run cannot accept claims.",
                        ),
                    )
                window._root = object()
                window._controller = controller
                window._research_run_id = RecordingInput("run-123")
                window._research_claim_evidence_ids = RecordingInput("evidence-123")
                window._research_claim_text = RecordingInput("Claim.")
                window._research_claim_epistemic_state = RecordingInput("unknown")
                window._research_claim_confidence = RecordingInput("unassessed")
                window._research_claim_supersedes_id = RecordingInput("")
                window._status = RecordingStatus()
                window._append_response = lambda _response: None

                with patch(
                    "desktop.TkinterDesktopWindow.messagebox.askyesno",
                    return_value=False,
                ) as confirm:
                    window._preview_and_record_research_claim()

                self.assertEqual(controller.claim_records, [])
                if blocked:
                    confirm.assert_not_called()
                else:
                    confirm.assert_called_once()

    def test_claim_contradiction_history_preview_uses_selected_run(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._status = RecordingStatus()
        window._append_response = responses.append

        window._preview_research_claim_contradictions()

        self.assertEqual(controller.claim_contradiction_previews, ["run-123"])
        self.assertEqual(
            responses,
            [controller.claim_contradiction_preview_response],
        )

    def test_claim_contradiction_suggestion_runs_on_cancellable_worker(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._status = RecordingStatus()
        window._append_response = responses.append
        window._research_claim_contradiction_proposal = RecordingVariable("")
        window._research_claim_contradiction_proposal_selector = (
            RecordingCandidateSelector()
        )
        window._research_claim_contradiction_proposal_run_id = ""
        window._research_claim_contradiction_proposals = ()
        _configure_request_boundary(window)

        window._suggest_research_claim_contradictions()
        window._poll_requests()

        self.assertEqual(controller.claim_contradiction_suggestions, ["run-123"])
        self.assertEqual(len(controller.claim_contradiction_cancellation_tokens), 1)
        self.assertIsNotNone(controller.claim_contradiction_cancellation_tokens[0])
        self.assertEqual(
            responses,
            [controller.claim_contradiction_proposal_response],
        )
        self.assertEqual(
            window._research_claim_contradiction_proposal_run_id,
            "run-123",
        )
        self.assertEqual(
            window._research_claim_contradiction_proposal_selector.values,
            ("1. claim-1 ↔ claim-2",),
        )

    def test_selected_contradiction_proposal_only_copies_ids_into_manual_form(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        candidate = ResearchClaimContradictionCandidate(
            ("claim-1", "claim-2"),
            ("evidence-1", "evidence-2"),
            "Possible conflict.",
        )
        window._research_run_id = RecordingInput("run-123")
        window._research_claim_contradiction_proposal_run_id = "run-123"
        window._research_claim_contradiction_proposals = (candidate,)
        window._research_claim_contradiction_proposal_selector = (
            RecordingCandidateSelector(selected_index=0)
        )
        window._research_claim_contradiction_proposal = RecordingVariable(
            "1. claim-1 ↔ claim-2"
        )
        window._research_claim_contradiction_ids = RecordingVariable("old IDs")
        window._research_claim_contradiction_note = RecordingVariable(
            "User-authored note stays unchanged."
        )
        window._status = RecordingStatus()

        window._use_selected_research_claim_contradiction_proposal()

        self.assertEqual(
            window._research_claim_contradiction_ids.value,
            "claim-1, claim-2",
        )
        self.assertEqual(
            window._research_claim_contradiction_note.value,
            "User-authored note stays unchanged.",
        )
        self.assertEqual(
            window._status.values,
            ["suggested claim IDs copied; note unchanged; nothing recorded"],
        )

    def test_stale_contradiction_proposal_never_changes_manual_form(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        candidate = ResearchClaimContradictionCandidate(
            ("claim-1", "claim-2"),
            ("evidence-1", "evidence-2"),
            "Possible conflict.",
        )
        window._research_run_id = RecordingInput("different-run")
        window._research_claim_contradiction_proposal_run_id = "run-123"
        window._research_claim_contradiction_proposals = (candidate,)
        window._research_claim_contradiction_proposal_selector = (
            RecordingCandidateSelector(selected_index=0)
        )
        window._research_claim_contradiction_proposal = RecordingVariable(
            "1. claim-1 ↔ claim-2"
        )
        window._research_claim_contradiction_ids = RecordingVariable("old IDs")
        window._status = RecordingStatus()

        window._use_selected_research_claim_contradiction_proposal()

        self.assertEqual(window._research_claim_contradiction_ids.value, "old IDs")
        self.assertEqual(window._research_claim_contradiction_proposals, ())
        self.assertEqual(window._research_claim_contradiction_proposal.value, "")
        self.assertEqual(
            window._status.values,
            ["Request and select a contradiction suggestion first."],
        )

    def test_allowed_claim_contradiction_requires_confirmation_before_record(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        values = (
            "run-123",
            "claim-1, claim-2",
            "The conclusions conflict under the same conditions.",
        )
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput(values[0])
        window._research_claim_contradiction_ids = RecordingInput(values[1])
        window._research_claim_contradiction_note = RecordingInput(values[2])
        window._status = RecordingStatus()
        window._append_response = responses.append

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=True,
        ) as confirm:
            window._preview_and_record_research_claim_contradiction()

        self.assertEqual(controller.claim_contradiction_write_previews, [values])
        self.assertEqual(controller.claim_contradiction_records, [values])
        self.assertEqual(
            responses,
            [
                controller.claim_contradiction_write_preview_response,
                controller.claim_contradiction_record_response,
            ],
        )
        confirm.assert_called_once()

    def test_declined_or_blocked_claim_contradiction_never_records(self) -> None:
        for blocked in (False, True):
            with self.subTest(blocked=blocked):
                window: Any = object.__new__(TkinterDesktopWindow)
                controller = RecordingResearchSourceLoadController()
                if blocked:
                    preview_response = (
                        controller.claim_contradiction_write_preview_response
                    )
                    preview = (
                        preview_response.research_claim_contradiction_write_preview
                    )
                    assert preview is not None
                    controller.claim_contradiction_write_preview_response = (
                        BrainResponse(
                            message="Contradiction preview blocked.",
                            request_id="contradiction-preview-blocked",
                            intent="research_claim_contradiction_write_preview",
                            memory_count=0,
                            success=False,
                            research_claim_contradiction_write_preview=(
                                ResearchClaimContradictionWritePreview(
                                    run_id=preview.run_id,
                                    run_status=ResearchRunStatus.CANCELLED,
                                    claims=preview.claims,
                                    evidence=preview.evidence,
                                    note=preview.note,
                                    allowed=False,
                                    reason=(
                                        "A closed run cannot accept claim "
                                        "contradictions."
                                    ),
                                )
                            ),
                        )
                    )
                window._root = object()
                window._controller = controller
                window._research_run_id = RecordingInput("run-123")
                window._research_claim_contradiction_ids = RecordingInput(
                    "claim-1, claim-2"
                )
                window._research_claim_contradiction_note = RecordingInput("Note.")
                window._status = RecordingStatus()
                window._append_response = lambda _response: None

                with patch(
                    "desktop.TkinterDesktopWindow.messagebox.askyesno",
                    return_value=False,
                ) as confirm:
                    window._preview_and_record_research_claim_contradiction()

                self.assertEqual(controller.claim_contradiction_records, [])
                if blocked:
                    confirm.assert_not_called()
                else:
                    confirm.assert_called_once()

    def test_allowed_research_status_preview_requires_confirmation_before_update(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_target_status = RecordingInput("cancelled")
        window._status = RecordingStatus()
        window._append_response = responses.append

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=True,
        ) as confirm:
            window._preview_and_update_research_status()

        self.assertEqual(controller.status_previews, [("run-123", "cancelled")])
        self.assertEqual(controller.status_updates, [("run-123", "cancelled")])
        self.assertEqual(
            responses,
            [controller.status_preview_response, controller.status_update_response],
        )
        confirm.assert_called_once()

    def test_declined_research_status_preview_does_not_update(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_target_status = RecordingInput("cancelled")
        window._status = status
        window._append_response = lambda _response: None

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno",
            return_value=False,
        ):
            window._preview_and_update_research_status()

        self.assertEqual(controller.status_updates, [])
        self.assertEqual(status.values, ["research status: not updated"])

    def test_blocked_research_status_preview_cannot_request_confirmation(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        blocked = ResearchRunStatusTransitionPreview(
            run_id="run-123",
            current_status=ResearchRunStatus.COLLECTING,
            target_status=ResearchRunStatus.COMPLETED,
            allowed=False,
            reason="A completed research run requires evidence.",
        )
        controller.status_preview_response = BrainResponse(
            message="Preview blocked.",
            request_id="research-status-preview-blocked",
            intent="research_run_status_preview",
            memory_count=0,
            research_run_status_transition_preview=blocked,
        )
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_target_status = RecordingInput("completed")
        window._status = RecordingStatus()
        window._append_response = lambda _response: None

        with patch("desktop.TkinterDesktopWindow.messagebox.askyesno") as confirm:
            window._preview_and_update_research_status()

        confirm.assert_not_called()
        self.assertEqual(controller.status_updates, [])

    def test_allowed_candidate_preview_requires_confirmation_before_accept(
        self,
    ) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        responses: list[BrainResponse] = []
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_candidate_run_id = "run-123"
        window._research_candidate_discovery_id = "discovery-1"
        window._research_candidates = controller.candidates
        window._research_candidate_selector = RecordingCandidateSelector(0)
        window._status = RecordingStatus()
        window._append_response = responses.append
        _configure_request_boundary(window)

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ) as confirm:
            window._preview_and_accept_research_candidate()
        window._poll_requests()

        expected = ("run-123", "discovery-1", controller.candidates[0].url)
        self.assertEqual(controller.candidate_previews, [expected])
        self.assertEqual(controller.candidate_accepts, [expected])
        self.assertEqual(len(controller.candidate_cancellation_tokens), 1)
        self.assertIsNotNone(controller.candidate_cancellation_tokens[0])
        self.assertEqual(
            responses,
            [
                controller.candidate_preview_response,
                controller.candidate_accept_response,
            ],
        )
        confirm.assert_called_once()

    def test_declined_candidate_preview_does_not_accept(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._root = object()
        window._controller = controller
        window._research_run_id = RecordingInput("run-123")
        window._research_candidate_run_id = "run-123"
        window._research_candidate_discovery_id = "discovery-1"
        window._research_candidates = controller.candidates
        window._research_candidate_selector = RecordingCandidateSelector(0)
        window._status = status
        window._append_response = lambda _response: None

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ):
            window._preview_and_accept_research_candidate()

        self.assertEqual(controller.candidate_accepts, [])
        self.assertEqual(status.values, ["research candidate: not loaded"])

    def test_stale_candidate_selection_never_requests_preview(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)
        controller = RecordingResearchSourceLoadController()
        status = RecordingStatus()
        window._controller = controller
        window._research_run_id = RecordingInput("other-run")
        window._research_candidate_run_id = "run-123"
        window._research_candidate_discovery_id = "discovery-1"
        window._research_candidates = controller.candidates
        window._research_candidate_selector = RecordingCandidateSelector(0)
        window._status = status

        window._preview_and_accept_research_candidate()

        self.assertEqual(controller.candidate_previews, [])
        self.assertEqual(status.values, ["Select a discovered source candidate first."])


class RecordingKnowledgeLoadController:
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.response = BrainResponse(
            message="Loaded.",
            request_id="load",
            intent="knowledge_load",
            memory_count=0,
        )

    def load_knowledge(self, path: str) -> BrainResponse:
        self.paths.append(path)
        return self.response


class RecordingResearchContentStatusController:
    def __init__(self) -> None:
        self.calls = 0
        self.evidence_calls = 0
        self.response = BrainResponse(
            message="Research content restoration status.",
            request_id="research-content-status",
            intent="research_source_content_restoration_status",
            memory_count=0,
        )
        self.evidence_response = BrainResponse(
            message="Research evidence integrity status.",
            request_id="research-evidence-status",
            intent="research_evidence_integrity_status",
            memory_count=0,
        )

    def research_content_status(self) -> BrainResponse:
        self.calls += 1
        return self.response

    def research_evidence_status(self) -> BrainResponse:
        self.evidence_calls += 1
        return self.evidence_response


class RecordingResearchSourceLoadController:
    def __init__(self) -> None:
        self.sources: list[tuple[str, str]] = []
        self.source_cancellation_tokens: list[CancellationToken | None] = []
        self.questions: list[str] = []
        self.list_calls = 0
        self.export_previews: list[str] = []
        self.discovery_calls: list[str] = []
        self.discovery_providers: list[str] = []
        self.discovery_cancellation_tokens: list[CancellationToken | None] = []
        self.export_saves: list[tuple[ResearchRunMarkdownExportPreview, str]] = []
        self.export_verifications: list[tuple[str, str]] = []
        self.evidence_calls: list[tuple[str, str, str]] = []
        self.evidence_list_calls: list[str] = []
        self.status_previews: list[tuple[str, str]] = []
        self.status_updates: list[tuple[str, str]] = []
        self.candidate_previews: list[tuple[str, str, str]] = []
        self.candidate_accepts: list[tuple[str, str, str]] = []
        self.candidate_cancellation_tokens: list[CancellationToken | None] = []
        self.assessment_previews: list[tuple[str, str]] = []
        self.comparison_previews: list[tuple[str, str]] = []
        self.comparison_note_previews: list[tuple[str, str, str, str, str]] = []
        self.comparison_note_records: list[tuple[str, str, str, str, str]] = []
        self.assessment_write_previews: list[tuple[str, str, str, str, str, str]] = []
        self.assessment_records: list[tuple[str, str, str, str, str, str]] = []
        self.claim_previews: list[str] = []
        self.claim_write_previews: list[tuple[str, str, str, str, str, str]] = []
        self.claim_records: list[tuple[str, str, str, str, str, str]] = []
        self.claim_contradiction_previews: list[str] = []
        self.claim_contradiction_suggestions: list[str] = []
        self.claim_contradiction_cancellation_tokens: list[CancellationToken | None] = (
            []
        )
        self.claim_contradiction_write_previews: list[tuple[str, str, str]] = []
        self.claim_contradiction_records: list[tuple[str, str, str]] = []
        self.response = BrainResponse(
            message="Loaded.",
            request_id="research-source-load",
            intent="research_source_load",
            memory_count=0,
        )
        now = datetime(2026, 8, 20, tzinfo=UTC)
        run = ResearchRun(
            run_id="run-123",
            question="Compare local models",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=now,
            updated_at=now,
        )
        self.candidates = (
            ResearchSourceCandidate(
                url="https://doi.org/10.1000/first",
                title="First paper",
                snippet="Journal · 2025",
            ),
            ResearchSourceCandidate(
                url="https://doi.org/10.1000/second",
                title="Second paper",
                snippet="Journal · 2024",
            ),
        )
        discovered_run = ResearchRun(
            run_id=run.run_id,
            question=run.question,
            status=run.status,
            sources=run.sources,
            failures=run.failures,
            created_at=run.created_at,
            updated_at=run.updated_at,
            discoveries=(
                ResearchSourceDiscoveryRecord(
                    discovery_id="discovery-1",
                    query=run.question,
                    provider="crossref-rest-v1",
                    candidates=self.candidates,
                    discovered_at=now,
                ),
            ),
        )
        accepted_source = ResearchSourceRecord(
            document_id="document-123",
            url="https://example.com/paper",
            title="Accepted paper",
            content_type="text/plain",
            fetched_at=now,
            added_at=now,
        )
        accepted_run = ResearchRun(
            run_id=run.run_id,
            question=run.question,
            status=run.status,
            sources=(accepted_source,),
            failures=run.failures,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
        self.create_response = BrainResponse(
            message="Created.",
            request_id="research-run-create",
            intent="research_run_create",
            memory_count=0,
            research_runs=[run],
        )
        self.list_response = BrainResponse(
            message="Listed.",
            request_id="research-run-list",
            intent="research_run_list",
            memory_count=0,
            research_runs=[run],
        )
        markdown = "# Hypatia Research Export\n"
        export_preview = ResearchRunMarkdownExportPreview(
            run_id="run-123",
            run_status=ResearchRunStatus.CANCELLED,
            snapshot_updated_at=now,
            suggested_filename="hypatia-research-run-123.md",
            markdown_preview=markdown,
            total_character_count=len(markdown),
            omitted_character_count=0,
            content_sha256="a" * 64,
        )
        self.export_preview_response = BrainResponse(
            message="Markdown export preview.",
            request_id="research-export-preview",
            intent="research_run_markdown_export_preview",
            memory_count=0,
            research_run_markdown_export_preview=export_preview,
        )
        self.export_save_response = BrainResponse(
            message="Markdown export saved.",
            request_id="research-export-save",
            intent="research_run_markdown_export_save",
            memory_count=0,
        )
        self.export_verification_response = BrainResponse(
            message="Markdown export verified.",
            request_id="research-export-verify",
            intent="research_run_markdown_export_verify",
            memory_count=0,
        )
        self.discovery_response = BrainResponse(
            message="Candidates discovered.",
            request_id="research-source-discover",
            intent="research_source_discover",
            memory_count=0,
            research_runs=[discovered_run],
        )
        candidate_preview = ResearchSourceCandidateAcceptancePreview(
            "run-123",
            "discovery-1",
            self.candidates[0],
            True,
            "Candidate can be loaded.",
        )
        self.candidate_preview_response = BrainResponse(
            message="Candidate preview allowed.",
            request_id="candidate-preview",
            intent="research_source_candidate_acceptance_preview",
            memory_count=0,
            research_source_candidate_acceptance_preview=candidate_preview,
        )
        self.candidate_accept_response = BrainResponse(
            message="Candidate accepted.",
            request_id="candidate-accept",
            intent="research_source_candidate_accept",
            memory_count=0,
        )
        self.evidence_response = BrainResponse(
            message="Evidence recorded.",
            request_id="research-evidence-record",
            intent="research_evidence_record",
            memory_count=0,
            research_runs=[run],
        )
        self.evidence_list_response = BrainResponse(
            message="Evidence listed.",
            request_id="research-evidence-list",
            intent="research_evidence_list",
            memory_count=0,
            research_runs=[run],
        )
        assessment_preview = ResearchSourceAssessmentPreview(
            run_id=run.run_id,
            run_status=run.status,
            source=accepted_source,
            evidence=(),
            has_recorded_evidence=False,
            reason="No evidence has been selected.",
        )
        self.assessment_preview_response = BrainResponse(
            message="Assessment preview.",
            request_id="research-source-assessment-preview",
            intent="research_source_assessment_preview",
            memory_count=0,
            research_runs=[accepted_run],
            research_source_assessment_preview=assessment_preview,
        )
        self.comparison_preview_response = BrainResponse(
            message="Comparison preview.",
            request_id="research-source-comparison-preview",
            intent="research_source_comparison_preview",
            memory_count=0,
        )
        assessment_evidence = ResearchEvidenceRecord(
            evidence_id="evidence-123",
            source_document_id="document-123",
            chunk_id="chunk-123",
            chunk_index=0,
            excerpt="Evidence.",
            excerpt_truncated=False,
            chunk_sha256="a" * 64,
            note="Supports the assessment.",
            recorded_at=now,
        )
        second_source = ResearchSourceRecord(
            document_id="document-2",
            url="https://example.com/second",
            title="Second source",
            content_type="text/plain",
            fetched_at=now,
            added_at=now,
        )
        second_evidence = ResearchEvidenceRecord(
            evidence_id="evidence-2",
            source_document_id="document-2",
            chunk_id="chunk-2",
            chunk_index=0,
            excerpt="Second evidence.",
            excerpt_truncated=False,
            chunk_sha256="b" * 64,
            note="Supports the second assessment.",
            recorded_at=now,
        )
        comparison_assessments = (
            ResearchSourceAssessmentRecord(
                "assessment-1",
                accepted_source.document_id,
                (assessment_evidence.evidence_id,),
                "First assessment.",
                now,
            ),
            ResearchSourceAssessmentRecord(
                "assessment-2",
                second_source.document_id,
                (second_evidence.evidence_id,),
                "Second assessment.",
                now,
            ),
        )
        comparison = ResearchSourceComparisonPreview(
            run_id=run.run_id,
            question=run.question,
            run_status=run.status,
            sources=(
                ResearchSourceComparisonItem(
                    accepted_source,
                    (assessment_evidence,),
                    (comparison_assessments[0],),
                ),
                ResearchSourceComparisonItem(
                    second_source,
                    (second_evidence,),
                    (comparison_assessments[1],),
                ),
            ),
            reason="Two sources selected.",
        )
        comparison_note_preview = ResearchSourceComparisonNoteWritePreview(
            comparison=comparison,
            evidence=(assessment_evidence, second_evidence),
            assessments=comparison_assessments,
            text="My comparison note.",
            allowed=True,
            reason="Research comparison note can be recorded after confirmation.",
        )
        self.comparison_note_preview_response = BrainResponse(
            message="Comparison note preview allowed.",
            request_id="comparison-note-preview",
            intent="research_source_comparison_note_write_preview",
            memory_count=0,
            research_source_comparison_note_write_preview=comparison_note_preview,
        )
        self.comparison_note_record_response = BrainResponse(
            message="Comparison note recorded.",
            request_id="comparison-note-record",
            intent="research_source_comparison_note_record",
            memory_count=0,
        )
        assessment_write_preview = ResearchSourceAssessmentWritePreview(
            run_id=run.run_id,
            run_status=run.status,
            source=accepted_source,
            evidence=(assessment_evidence,),
            text="Assessment.",
            allowed=True,
            reason="Research source assessment can be recorded after confirmation.",
        )
        self.assessment_write_preview_response = BrainResponse(
            message="Assessment write preview allowed.",
            request_id="research-source-assessment-write-preview",
            intent="research_source_assessment_write_preview",
            memory_count=0,
            research_source_assessment_write_preview=assessment_write_preview,
        )
        self.assessment_record_response = BrainResponse(
            message="Assessment recorded.",
            request_id="research-source-assessment-record",
            intent="research_source_assessment_record",
            memory_count=0,
        )
        claim_preview = ResearchClaimPreview(
            run_id=run.run_id,
            question=run.question,
            run_status=run.status,
            claims=(),
            reason="No claims recorded.",
        )
        self.claim_preview_response = BrainResponse(
            message="Claim history preview.",
            request_id="research-claim-preview",
            intent="research_claim_preview",
            memory_count=0,
            research_claim_preview=claim_preview,
        )
        claim_write_preview = ResearchClaimWritePreview(
            run_id=run.run_id,
            run_status=run.status,
            sources=(accepted_source,),
            evidence=(assessment_evidence,),
            text="The evidence supports a bounded claim.",
            epistemic_state=ResearchEpistemicState.STRONG_EVIDENCE,
            confidence=ResearchClaimConfidence.HIGH,
            allowed=True,
            reason="Research claim can be recorded after confirmation.",
        )
        self.claim_write_preview_response = BrainResponse(
            message="Claim write preview allowed.",
            request_id="research-claim-write-preview",
            intent="research_claim_write_preview",
            memory_count=0,
            research_claim_write_preview=claim_write_preview,
        )
        self.claim_record_response = BrainResponse(
            message="Claim recorded.",
            request_id="research-claim-record",
            intent="research_claim_record",
            memory_count=0,
        )
        contradiction_claims = (
            ResearchClaimRecord(
                "claim-1",
                "The outcome improves.",
                ResearchEpistemicState.LIKELY,
                ResearchClaimConfidence.MEDIUM,
                (accepted_source.document_id,),
                (assessment_evidence.evidence_id,),
                now,
            ),
            ResearchClaimRecord(
                "claim-2",
                "The outcome does not improve.",
                ResearchEpistemicState.LIKELY,
                ResearchClaimConfidence.MEDIUM,
                (second_source.document_id,),
                (second_evidence.evidence_id,),
                now,
            ),
        )
        contradiction_history = ResearchClaimContradictionPreview(
            run_id=run.run_id,
            question=run.question,
            run_status=run.status,
            claims=contradiction_claims,
            contradictions=(),
            reason="No contradictions recorded.",
        )
        self.claim_contradiction_preview_response = BrainResponse(
            message="Claim contradiction history.",
            request_id="research-claim-contradiction-preview",
            intent="research_claim_contradiction_preview",
            memory_count=0,
            research_claim_contradiction_preview=contradiction_history,
        )
        contradiction_proposal = ResearchClaimContradictionProposalPreview(
            run_id=run.run_id,
            question=run.question,
            run_status=run.status,
            snapshot_updated_at=run.updated_at,
            provider_name="configured_llm",
            claims=contradiction_claims,
            candidates=(
                ResearchClaimContradictionCandidate(
                    ("claim-1", "claim-2"),
                    (assessment_evidence.evidence_id, second_evidence.evidence_id),
                    "The conclusions may conflict.",
                ),
            ),
            reason="One candidate requires review.",
        )
        self.claim_contradiction_proposal_response = BrainResponse(
            message="Possible contradiction candidates.",
            request_id="research-claim-contradiction-proposal",
            intent="research_claim_contradiction_proposal",
            memory_count=0,
            research_claim_contradiction_proposal_preview=contradiction_proposal,
        )
        contradiction_write_preview = ResearchClaimContradictionWritePreview(
            run_id=run.run_id,
            run_status=run.status,
            claims=contradiction_claims,
            evidence=(assessment_evidence, second_evidence),
            note="The conclusions conflict under the same conditions.",
            allowed=True,
            reason=("Research claim contradiction can be recorded after confirmation."),
        )
        self.claim_contradiction_write_preview_response = BrainResponse(
            message="Claim contradiction preview allowed.",
            request_id="research-claim-contradiction-write-preview",
            intent="research_claim_contradiction_write_preview",
            memory_count=0,
            research_claim_contradiction_write_preview=(contradiction_write_preview),
        )
        self.claim_contradiction_record_response = BrainResponse(
            message="Claim contradiction recorded.",
            request_id="research-claim-contradiction-record",
            intent="research_claim_contradiction_record",
            memory_count=0,
        )
        status_preview = ResearchRunStatusTransitionPreview(
            run_id="run-123",
            current_status=ResearchRunStatus.COLLECTING,
            target_status=ResearchRunStatus.CANCELLED,
            allowed=True,
            reason="Research run can be marked cancelled.",
        )
        self.status_preview_response = BrainResponse(
            message="Preview allowed.",
            request_id="research-status-preview",
            intent="research_run_status_preview",
            memory_count=0,
            research_run_status_transition_preview=status_preview,
        )
        self.status_update_response = BrainResponse(
            message="Updated.",
            request_id="research-status-update",
            intent="research_run_status_update",
            memory_count=0,
            research_runs=[run],
        )

    def load_research_source(
        self,
        url: str,
        research_run_id: str = "",
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> BrainResponse:
        if not url.strip():
            raise ValueError("A research source URL cannot be empty.")
        self.sources.append((url, research_run_id))
        self.source_cancellation_tokens.append(cancellation_token)
        return self.response

    def create_research_run(self, question: str) -> BrainResponse:
        if not question.strip():
            raise ValueError("A research question cannot be empty.")
        self.questions.append(question)
        return self.create_response

    def list_research_runs(self) -> BrainResponse:
        self.list_calls += 1
        return self.list_response

    def preview_research_run_markdown_export(self, run_id: str) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        self.export_previews.append(run_id)
        return self.export_preview_response

    def save_research_run_markdown_export(
        self,
        preview: ResearchRunMarkdownExportPreview,
        destination_path: str,
    ) -> BrainResponse:
        if not destination_path.strip():
            raise ValueError("A research export destination cannot be empty.")
        self.export_saves.append((preview, destination_path))
        return self.export_save_response

    def verify_research_run_markdown_export(
        self,
        run_id: str,
        source_path: str,
    ) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        if not source_path.strip():
            raise ValueError("A research export verification file cannot be empty.")
        self.export_verifications.append((run_id, source_path))
        return self.export_verification_response

    def discover_research_sources(
        self,
        run_id: str,
        provider: str = "",
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        self.discovery_providers.append(provider)
        self.discovery_calls.append(run_id)
        self.discovery_cancellation_tokens.append(cancellation_token)
        return self.discovery_response

    def record_research_evidence(
        self,
        run_id: str,
        chunk_id: str,
        note: str,
    ) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        if not chunk_id.strip():
            raise ValueError("A research chunk ID cannot be empty.")
        if not note.strip():
            raise ValueError("A research evidence note cannot be empty.")
        self.evidence_calls.append((run_id, chunk_id, note))
        return self.evidence_response

    def list_research_evidence(self, run_id: str) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        self.evidence_list_calls.append(run_id)
        return self.evidence_list_response

    def preview_research_source_assessment(
        self,
        run_id: str,
        document_id: str,
    ) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        if not document_id.strip():
            raise ValueError("A research source document ID cannot be empty.")
        self.assessment_previews.append((run_id, document_id))
        return self.assessment_preview_response

    def preview_research_claims(self, run_id: str) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        self.claim_previews.append(run_id)
        return self.claim_preview_response

    def preview_research_claim_write(
        self,
        run_id: str,
        evidence_ids: str,
        text: str,
        epistemic_state: str,
        confidence: str = "unassessed",
        supersedes_claim_id: str = "",
    ) -> BrainResponse:
        values = (
            run_id,
            evidence_ids,
            text,
            epistemic_state,
            confidence,
            supersedes_claim_id,
        )
        self.claim_write_previews.append(values)
        return self.claim_write_preview_response

    def record_research_claim(
        self,
        run_id: str,
        evidence_ids: str,
        text: str,
        epistemic_state: str,
        confidence: str = "unassessed",
        supersedes_claim_id: str = "",
    ) -> BrainResponse:
        values = (
            run_id,
            evidence_ids,
            text,
            epistemic_state,
            confidence,
            supersedes_claim_id,
        )
        self.claim_records.append(values)
        return self.claim_record_response

    def preview_research_claim_contradictions(self, run_id: str) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        self.claim_contradiction_previews.append(run_id)
        return self.claim_contradiction_preview_response

    def suggest_research_claim_contradictions(
        self,
        run_id: str,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        self.claim_contradiction_suggestions.append(run_id)
        self.claim_contradiction_cancellation_tokens.append(cancellation_token)
        return self.claim_contradiction_proposal_response

    def preview_research_claim_contradiction_write(
        self,
        run_id: str,
        claim_ids: str,
        note: str,
    ) -> BrainResponse:
        values = (run_id, claim_ids, note)
        self.claim_contradiction_write_previews.append(values)
        return self.claim_contradiction_write_preview_response

    def record_research_claim_contradiction(
        self,
        run_id: str,
        claim_ids: str,
        note: str,
    ) -> BrainResponse:
        values = (run_id, claim_ids, note)
        self.claim_contradiction_records.append(values)
        return self.claim_contradiction_record_response

    def preview_research_source_comparison(
        self,
        run_id: str,
        document_ids: str,
    ) -> BrainResponse:
        if not run_id.strip():
            raise ValueError("A research run ID cannot be empty.")
        if len([value for value in document_ids.split(",") if value.strip()]) < 2:
            raise ValueError("Enter 2 to 5 research source document IDs.")
        self.comparison_previews.append((run_id, document_ids))
        return self.comparison_preview_response

    def preview_research_source_assessment_write(
        self,
        run_id: str,
        document_id: str,
        evidence_ids: str,
        text: str,
        supersedes_assessment_id: str = "",
        information_trust: str = "unassessed",
        usefulness: str = "unknown",
        applicability: str = "unknown",
        independence: str = "unknown",
        publication_status: str = "unknown",
    ) -> BrainResponse:
        if not evidence_ids.strip():
            raise ValueError("Research assessment evidence IDs cannot be empty.")
        values = (
            run_id,
            document_id,
            evidence_ids,
            text,
            supersedes_assessment_id,
            information_trust,
            usefulness,
            applicability,
            independence,
            publication_status,
        )
        self.assessment_write_previews.append(values)
        return self.assessment_write_preview_response

    def preview_research_source_comparison_note_write(
        self,
        run_id: str,
        document_ids: str,
        evidence_ids: str,
        assessment_ids: str,
        text: str,
    ) -> BrainResponse:
        values = (run_id, document_ids, evidence_ids, assessment_ids, text)
        self.comparison_note_previews.append(values)
        return self.comparison_note_preview_response

    def record_research_source_comparison_note(
        self,
        run_id: str,
        document_ids: str,
        evidence_ids: str,
        assessment_ids: str,
        text: str,
    ) -> BrainResponse:
        values = (run_id, document_ids, evidence_ids, assessment_ids, text)
        self.comparison_note_records.append(values)
        return self.comparison_note_record_response

    def record_research_source_assessment(
        self,
        run_id: str,
        document_id: str,
        evidence_ids: str,
        text: str,
        supersedes_assessment_id: str = "",
        information_trust: str = "unassessed",
        usefulness: str = "unknown",
        applicability: str = "unknown",
        independence: str = "unknown",
        publication_status: str = "unknown",
    ) -> BrainResponse:
        values = (
            run_id,
            document_id,
            evidence_ids,
            text,
            supersedes_assessment_id,
            information_trust,
            usefulness,
            applicability,
            independence,
            publication_status,
        )
        self.assessment_records.append(values)
        return self.assessment_record_response

    def preview_research_run_status(
        self,
        run_id: str,
        target_status: str,
    ) -> BrainResponse:
        self.status_previews.append((run_id, target_status))
        return self.status_preview_response

    def update_research_run_status(
        self,
        run_id: str,
        target_status: str,
    ) -> BrainResponse:
        self.status_updates.append((run_id, target_status))
        return self.status_update_response

    def preview_research_source_candidate_acceptance(
        self, run_id: str, discovery_id: str, candidate_url: str
    ) -> BrainResponse:
        self.candidate_previews.append((run_id, discovery_id, candidate_url))
        return self.candidate_preview_response

    def accept_research_source_candidate(
        self,
        run_id: str,
        discovery_id: str,
        candidate_url: str,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> BrainResponse:
        self.candidate_accepts.append((run_id, discovery_id, candidate_url))
        self.candidate_cancellation_tokens.append(cancellation_token)
        return self.candidate_accept_response


def _configure_research_evidence_selector(window: Any) -> None:
    _configure_research_source_coverage(window)
    window._research_evidence_choice = RecordingVariable("")
    window._research_evidence_selector = RecordingCandidateSelector()
    window._research_evidence_records = ()
    window._research_evidence_run_id = ""
    window._research_evidence_source_document_id = ""
    _configure_research_assessment_selector(window)
    _configure_research_claim_selector(window)


def _configure_research_source_coverage(window: Any) -> None:
    sources = getattr(window, "_research_sources", ())
    window._research_source_catalog = sources
    window._research_source_coverage_filter = RecordingVariable(
        ResearchSourceCoverageFacet.ALL.value
    )
    window._research_source_coverage_summary = RecordingVariable("")
    window._research_source_catalog_summary = RecordingVariable(
        "Accepted-source coverage — All: 0 · Without evidence: 0 · "
        "Without current assessment: 0"
    )
    window._research_selected_source_summary = RecordingVariable(
        "Selected-source records unavailable until an accepted source is selected."
    )
    selected_index = (
        window._research_source_selector.current()
        if hasattr(window, "_research_source_selector")
        else -1
    )
    window._active_research_source_document_id = (
        sources[selected_index].document_id
        if 0 <= selected_index < len(sources)
        else ""
    )


def _configure_research_assessment_selector(window: Any) -> None:
    # The panel now renders relevance, judgement, reputation and acceptance as
    # four separate lines beside the selector, so a window that can render the
    # selector has to be able to render those too.
    window._research_source_dimensions = RecordingVariable("")
    window._research_assessment_choice = RecordingVariable("")
    window._research_assessment_selector = RecordingCandidateSelector()
    window._research_assessment_records = ()
    window._research_current_assessment_ids = frozenset()
    window._research_assessment_run_id = ""
    window._research_assessment_source_document_id = ""


def _configure_research_claim_selector(window: Any) -> None:
    window._research_claim_choice = RecordingVariable("")
    window._research_claim_selector = RecordingCandidateSelector()
    window._research_claim_records = ()
    window._research_current_claim_ids = frozenset()
    window._research_claim_run_id = ""
    _configure_research_persisted_contradiction_selector(window)


def _configure_research_persisted_contradiction_selector(window: Any) -> None:
    window._research_persisted_contradiction_choice = RecordingVariable("")
    window._research_persisted_contradiction_selector = RecordingCandidateSelector()
    window._research_persisted_contradiction_records = ()
    window._research_persisted_contradiction_run_id = ""
    _configure_research_persisted_comparison_note_selector(window)


def _configure_research_persisted_comparison_note_selector(window: Any) -> None:
    window._research_persisted_comparison_note_choice = RecordingVariable("")
    window._research_persisted_comparison_note_references = RecordingVariable("")
    window._research_persisted_comparison_note_selector = RecordingCandidateSelector()
    window._research_persisted_comparison_note_records = ()
    window._research_persisted_comparison_note_run_id = ""


def _configure_selected_persisted_comparison_notes(
    window: Any,
    records: tuple[ResearchSourceComparisonNoteRecord, ...],
    *,
    selected_index: int = 0,
) -> None:
    window._research_run_id = RecordingVariable("run-123")
    window._research_persisted_comparison_note_records = records
    window._research_persisted_comparison_note_run_id = "run-123"
    window._research_persisted_comparison_note_selector = RecordingCandidateSelector(
        selected_index=selected_index
    )
    window._research_persisted_comparison_note_choice = RecordingVariable("")
    window._research_persisted_comparison_note_references = RecordingVariable("")


def _configure_selected_persisted_contradictions(
    window: Any,
    records: tuple[ResearchClaimContradictionRecord, ...],
    *,
    selected_index: int = 0,
) -> None:
    window._research_run_id = RecordingVariable("run-123")
    window._research_persisted_contradiction_records = records
    window._research_persisted_contradiction_run_id = "run-123"
    window._research_persisted_contradiction_selector = RecordingCandidateSelector(
        selected_index=selected_index
    )
    window._research_persisted_contradiction_choice = RecordingVariable("")


def _configure_selected_research_claims(
    window: Any,
    records: tuple[ResearchClaimRecord, ...],
    *,
    current_ids: frozenset[str],
    selected_index: int = 0,
) -> None:
    window._research_run_id = RecordingVariable("run-123")
    window._research_claim_records = records
    window._research_current_claim_ids = current_ids
    window._research_claim_run_id = "run-123"
    window._research_claim_selector = RecordingCandidateSelector(
        selected_index=selected_index
    )
    window._research_claim_choice = RecordingVariable("")


def _configure_selected_research_evidence(
    window: Any,
    source: ResearchSourceRecord,
    record: ResearchEvidenceRecord,
) -> None:
    window._research_run_id = RecordingVariable("run-123")
    window._research_source_run_id = "run-123"
    window._research_sources = (source,)
    window._research_source_selector = RecordingCandidateSelector(selected_index=0)
    window._research_source_choice = RecordingVariable(
        f"{source.title} — {source.document_id}"
    )
    _configure_research_source_coverage(window)
    window._research_evidence_records = (record,)
    window._research_evidence_run_id = "run-123"
    window._research_evidence_source_document_id = source.document_id
    window._research_evidence_selector = RecordingCandidateSelector(selected_index=0)
    window._research_evidence_choice = RecordingVariable(
        f"{record.excerpt} — {record.evidence_id}"
    )
    _configure_research_assessment_selector(window)


def _configure_selected_research_assessments(
    window: Any,
    source: ResearchSourceRecord,
    records: tuple[ResearchSourceAssessmentRecord, ...],
    *,
    current_ids: frozenset[str],
    selected_index: int = 0,
) -> None:
    window._research_run_id = RecordingVariable("run-123")
    window._research_source_run_id = "run-123"
    window._research_sources = (source,)
    window._research_source_selector = RecordingCandidateSelector(selected_index=0)
    window._research_source_choice = RecordingVariable(
        f"{source.title} — {source.document_id}"
    )
    _configure_research_source_coverage(window)
    _configure_research_evidence_selector(window)
    window._research_assessment_records = records
    window._research_current_assessment_ids = current_ids
    window._research_assessment_run_id = "run-123"
    window._research_assessment_source_document_id = source.document_id
    window._research_assessment_selector = RecordingCandidateSelector(
        selected_index=selected_index
    )
    window._research_source_dimensions = RecordingVariable("")
    window._research_assessment_choice = RecordingVariable("")


def _research_source_record(
    document_id: str,
    title: str,
) -> ResearchSourceRecord:
    now = datetime(2026, 8, 21, tzinfo=UTC)
    return ResearchSourceRecord(
        document_id=document_id,
        url=f"https://example.com/{document_id}",
        title=title,
        content_type="text/plain",
        fetched_at=now,
        added_at=now,
    )


def _research_assessment_record(
    assessment_id: str,
    source_document_id: str,
    evidence_id: str,
    text: str,
    *,
    supersedes_assessment_id: str | None = None,
    information_trust: ResearchInformationTrust = ResearchInformationTrust.UNASSESSED,
) -> ResearchSourceAssessmentRecord:
    return ResearchSourceAssessmentRecord(
        assessment_id=assessment_id,
        source_document_id=source_document_id,
        evidence_ids=(evidence_id,),
        text=text,
        recorded_at=datetime(2026, 8, 21, tzinfo=UTC),
        supersedes_assessment_id=supersedes_assessment_id,
        information_trust=information_trust,
    )


def _research_claim_record(
    claim_id: str,
    source_document_id: str,
    evidence_id: str,
    text: str,
    *,
    epistemic_state: ResearchEpistemicState = ResearchEpistemicState.UNKNOWN,
    confidence: ResearchClaimConfidence = ResearchClaimConfidence.UNASSESSED,
    supersedes_claim_id: str | None = None,
) -> ResearchClaimRecord:
    return ResearchClaimRecord(
        claim_id=claim_id,
        text=text,
        epistemic_state=epistemic_state,
        confidence=confidence,
        source_document_ids=(source_document_id,),
        evidence_ids=(evidence_id,),
        recorded_at=datetime(2026, 8, 21, tzinfo=UTC),
        supersedes_claim_id=supersedes_claim_id,
    )


def _research_claim_contradiction_record(
    contradiction_id: str,
    first_claim_id: str,
    second_claim_id: str,
    evidence_ids: tuple[str, ...],
    note: str,
) -> ResearchClaimContradictionRecord:
    return ResearchClaimContradictionRecord(
        contradiction_id=contradiction_id,
        claim_ids=(first_claim_id, second_claim_id),
        evidence_ids=evidence_ids,
        note=note,
        recorded_at=datetime(2026, 8, 21, tzinfo=UTC),
    )


def _research_comparison_note_record(
    note_id: str,
    source_document_ids: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    assessment_ids: tuple[str, ...],
    text: str,
) -> ResearchSourceComparisonNoteRecord:
    return ResearchSourceComparisonNoteRecord(
        note_id=note_id,
        source_document_ids=source_document_ids,
        evidence_ids=evidence_ids,
        assessment_ids=assessment_ids,
        text=text,
        recorded_at=datetime(2026, 8, 21, tzinfo=UTC),
    )


def _research_evidence_record(
    evidence_id: str,
    source_document_id: str,
    excerpt: str,
) -> ResearchEvidenceRecord:
    return ResearchEvidenceRecord(
        evidence_id=evidence_id,
        source_document_id=source_document_id,
        chunk_id=f"chunk-{evidence_id}",
        chunk_index=0,
        excerpt=excerpt,
        excerpt_truncated=False,
        chunk_sha256="0" * 64,
        note="User-selected evidence.",
        recorded_at=datetime(2026, 8, 21, tzinfo=UTC),
    )


class RecordingInput:
    def __init__(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        return self._value


class RecordingVariable(RecordingInput):
    @property
    def value(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class RecordingCandidateSelector:
    def __init__(self, selected_index: int = -1) -> None:
        self.selected_index = selected_index
        self.values: tuple[str, ...] = ()

    def configure(self, *, values: tuple[str, ...]) -> None:
        self.values = values

    def current(self, selected_index: int | None = None) -> int:
        if selected_index is not None:
            self.selected_index = selected_index
        return self.selected_index


class RecordingSessionList:
    def __init__(self, selected_indices: tuple[int, ...] = ()) -> None:
        self.selected_indices = selected_indices
        self.items: list[str] = []

    def curselection(self) -> tuple[int, ...]:
        return self.selected_indices

    def delete(self, _start: object, _end: object) -> None:
        self.items.clear()

    def insert(self, _position: object, value: str) -> None:
        self.items.append(value)


class RecordingStatus:
    def __init__(self) -> None:
        self.values: list[str] = []

    def set(self, value: str) -> None:
        self.values.append(value)


class ImmediateRequestRunner:
    """Deterministic worker seam for presentation-only unit tests."""

    def __init__(self) -> None:
        self.completions: list[DesktopRequestCompletion[object]] = []
        self.stopped = False

    def start(
        self,
        action: Callable[[], object],
        *,
        cancel_callback: Callable[[], None] | None = None,
    ) -> Literal["started", "busy", "stopped", "failed"]:
        del cancel_callback
        if self.stopped:
            return "stopped"
        try:
            completion = DesktopRequestCompletion(value=action())
        except Exception as error:
            completion = DesktopRequestCompletion(error=error)
        self.completions.append(completion)
        return "started"

    def drain(self) -> tuple[DesktopRequestCompletion[object], ...]:
        completions = tuple(self.completions)
        self.completions.clear()
        return completions

    def is_running(self) -> bool:
        return False

    def is_cancellation_requested(self) -> bool:
        return False

    def request_cancel(self) -> Literal["idle", "stopped"]:
        return "stopped" if self.stopped else "idle"

    def stop(self) -> None:
        self.stopped = True
        self.completions.clear()


class RecordingRequestRoot:
    def __init__(self) -> None:
        self.after_calls: list[tuple[int, Callable[[], None]]] = []
        self.destroyed = False

    def after(self, delay_ms: int, callback: Callable[[], None]) -> None:
        self.after_calls.append((delay_ms, callback))

    def destroy(self) -> None:
        self.destroyed = True


def _configure_request_boundary(window: Any) -> None:
    # Discovery now asks which provider to contact before it contacts one, so a
    # window that can issue a request has to be able to answer that.
    window._research_discovery_provider = RecordingInput("crossref")
    window._request_runner = ImmediateRequestRunner()
    window._request_completion_handler = None
    window._request_controls = []
    window._request_label = None
    window._request_started_at = None
    window._closing = False
    window._root = RecordingRequestRoot()


class RelationConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview = BrainResponse(
            message="Changes: ready",
            request_id="preview",
            intent="knowledge_relation_preview",
            memory_count=0,
        )
        self.application = BrainResponse(
            message="Graph state: updated",
            request_id="apply",
            intent="knowledge_relation_apply",
            memory_count=0,
        )
        self.controller = RecordingRelationController(self.preview, self.application)

    def test_applies_only_after_a_successful_preview_is_confirmed(self) -> None:
        preview, application = _preview_and_confirm_knowledge_relation(
            self.controller,
            "source",
            "target",
            lambda response: response is self.preview,
        )

        self.assertIs(preview, self.preview)
        self.assertIs(application, self.application)
        self.assertEqual(
            self.controller.calls,
            [("preview", "source", "target"), ("apply", "source", "target")],
        )

    def test_does_not_apply_when_the_user_declines_the_preview(self) -> None:
        preview, application = _preview_and_confirm_knowledge_relation(
            self.controller,
            "source",
            "target",
            lambda _response: False,
        )

        self.assertIs(preview, self.preview)
        self.assertIsNone(application)
        self.assertEqual(self.controller.calls, [("preview", "source", "target")])

    def test_does_not_offer_or_apply_a_failed_preview(self) -> None:
        failed_preview = BrainResponse(
            message="The relation is invalid.",
            request_id="failed-preview",
            intent="knowledge_relation_preview",
            memory_count=0,
            success=False,
        )
        controller = RecordingRelationController(failed_preview, self.application)
        confirmations: list[BrainResponse] = []

        def confirm(response: BrainResponse) -> bool:
            confirmations.append(response)
            return True

        preview, application = _preview_and_confirm_knowledge_relation(
            controller,
            "source",
            "target",
            confirm,
        )

        self.assertIs(preview, failed_preview)
        self.assertIsNone(application)
        self.assertEqual(confirmations, [])
        self.assertEqual(controller.calls, [("preview", "source", "target")])


class RecordingRelationController:
    def __init__(self, preview: BrainResponse, application: BrainResponse) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._preview = preview
        self._application = application

    def preview_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        self.calls.append(("preview", source_document_id, target_document_id))
        return self._preview

    def apply_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        self.calls.append(("apply", source_document_id, target_document_id))
        return self._application


class RelationRemovalConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview = BrainResponse(
            message="Changes: ready to remove",
            request_id="removal-preview",
            intent="knowledge_relation_removal_preview",
            memory_count=0,
        )
        self.removal = BrainResponse(
            message="Graph state: updated",
            request_id="remove",
            intent="knowledge_relation_remove",
            memory_count=0,
        )
        self.controller = RecordingRelationRemovalController(
            self.preview,
            self.removal,
        )

    def test_removes_only_after_a_successful_preview_is_confirmed(self) -> None:
        preview, removal = _preview_and_confirm_knowledge_relation_removal(
            self.controller,
            "source",
            "target",
            lambda response: response is self.preview,
        )

        self.assertIs(preview, self.preview)
        self.assertIs(removal, self.removal)
        self.assertEqual(
            self.controller.calls,
            [("preview", "source", "target"), ("remove", "source", "target")],
        )

    def test_does_not_remove_when_the_user_declines_the_preview(self) -> None:
        preview, removal = _preview_and_confirm_knowledge_relation_removal(
            self.controller,
            "source",
            "target",
            lambda _response: False,
        )

        self.assertIs(preview, self.preview)
        self.assertIsNone(removal)
        self.assertEqual(self.controller.calls, [("preview", "source", "target")])

    def test_does_not_offer_or_remove_a_failed_preview(self) -> None:
        failed_preview = BrainResponse(
            message="The relation is unavailable.",
            request_id="failed-removal-preview",
            intent="knowledge_relation_removal_preview",
            memory_count=0,
            success=False,
        )
        controller = RecordingRelationRemovalController(failed_preview, self.removal)
        confirmations: list[BrainResponse] = []

        def confirm(response: BrainResponse) -> bool:
            confirmations.append(response)
            return True

        preview, removal = _preview_and_confirm_knowledge_relation_removal(
            controller,
            "source",
            "target",
            confirm,
        )

        self.assertIs(preview, failed_preview)
        self.assertIsNone(removal)
        self.assertEqual(confirmations, [])
        self.assertEqual(controller.calls, [("preview", "source", "target")])


class RecordingRelationRemovalController:
    def __init__(self, preview: BrainResponse, removal: BrainResponse) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._preview = preview
        self._removal = removal

    def preview_knowledge_relation_removal(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        self.calls.append(("preview", source_document_id, target_document_id))
        return self._preview

    def remove_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        self.calls.append(("remove", source_document_id, target_document_id))
        return self._removal


class SessionRenameConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview = BrainResponse(
            message="Changes: ready",
            request_id="rename-preview",
            intent="session_rename_preview",
            memory_count=2,
        )
        self.renamed = BrainResponse(
            message="Status: committed",
            request_id="rename",
            intent="session_rename",
            memory_count=2,
        )
        self.controller = RecordingSessionRenameController(self.preview, self.renamed)

    def test_renames_only_after_a_successful_preview_is_confirmed(self) -> None:
        preview, renamed = _preview_and_confirm_session_rename(
            self.controller,
            "work",
            "archive",
            lambda response: response is self.preview,
        )

        self.assertIs(preview, self.preview)
        self.assertIs(renamed, self.renamed)
        self.assertEqual(
            self.controller.calls,
            [("preview", "work", "archive"), ("rename", "work", "archive")],
        )

    def test_does_not_rename_when_the_user_declines_or_preview_fails(self) -> None:
        preview, renamed = _preview_and_confirm_session_rename(
            self.controller,
            "work",
            "archive",
            lambda _response: False,
        )

        self.assertIs(preview, self.preview)
        self.assertIsNone(renamed)
        self.assertEqual(self.controller.calls, [("preview", "work", "archive")])

        failed = BrainResponse(
            message="Session already exists.",
            request_id="failed-preview",
            intent="session_rename_preview",
            memory_count=0,
            success=False,
        )
        failed_controller = RecordingSessionRenameController(failed, self.renamed)
        preview, renamed = _preview_and_confirm_session_rename(
            failed_controller,
            "work",
            "archive",
            lambda _response: True,
        )

        self.assertIs(preview, failed)
        self.assertIsNone(renamed)
        self.assertEqual(failed_controller.calls, [("preview", "work", "archive")])


class RecordingSessionRenameController:
    def __init__(self, preview: BrainResponse, renamed: BrainResponse) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._preview = preview
        self._renamed = renamed

    def preview_session_rename(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        self.calls.append(("preview", source_session_id, target_session_id))
        return self._preview

    def rename_session(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        self.calls.append(("rename", source_session_id, target_session_id))
        return self._renamed
