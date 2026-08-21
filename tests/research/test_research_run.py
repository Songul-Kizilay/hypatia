"""Validation tests for persistent research-run records."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRecord import ResearchSourceRecord


class ResearchRunTests(unittest.TestCase):
    def test_normalizes_identity_and_question(self) -> None:
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

        run = ResearchRun(
            run_id=" run-1 ",
            question="  What evidence supports the finding?  ",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=now,
            updated_at=now,
        )

        self.assertEqual(run.run_id, "run-1")
        self.assertEqual(run.question, "What evidence supports the finding?")

    def test_rejects_invalid_time_order_and_duplicate_sources(self) -> None:
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        with self.assertRaisesRegex(ResearchError, "cannot precede"):
            ResearchRun(
                run_id="run-1",
                question="Question",
                status=ResearchRunStatus.COLLECTING,
                sources=(),
                failures=(),
                created_at=now,
                updated_at=datetime(2026, 8, 20, 11, 0, tzinfo=UTC),
            )

        source = ResearchSourceRecord(
            document_id="document-1",
            url="https://example.com/source",
            title="Example",
            content_type="text/plain",
            fetched_at=now,
            added_at=now,
        )
        duplicate = ResearchSourceRecord(
            document_id="document-1",
            url="https://example.org/duplicate",
            title="Duplicate",
            content_type="text/html",
            fetched_at=now,
            added_at=now,
        )
        with self.assertRaisesRegex(ResearchError, "duplicate source documents"):
            ResearchRun(
                run_id="run-1",
                question="Question",
                status=ResearchRunStatus.COLLECTING,
                sources=(source, duplicate),
                failures=(),
                created_at=now,
                updated_at=now,
            )

    def test_rejects_duplicate_discovery_ids(self) -> None:
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        discovery = ResearchSourceDiscoveryRecord(
            discovery_id="discovery-1",
            query="Question",
            provider="Provider",
            candidates=(),
            discovered_at=now,
        )

        with self.assertRaisesRegex(ResearchError, "duplicate discovery IDs"):
            ResearchRun(
                run_id="run-1",
                question="Question",
                status=ResearchRunStatus.COLLECTING,
                sources=(),
                failures=(),
                created_at=now,
                updated_at=now,
                discoveries=(discovery, discovery),
            )

    def test_assessment_requires_evidence_from_the_same_accepted_source(self) -> None:
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        sources = tuple(
            ResearchSourceRecord(
                f"document-{number}",
                f"https://example.com/{number}",
                f"Source {number}",
                "text/plain",
                now,
                now,
            )
            for number in (1, 2)
        )
        evidence = ResearchEvidenceRecord(
            "evidence-1",
            "document-2",
            "chunk-1",
            0,
            "Evidence.",
            False,
            "a" * 64,
            "Relevant.",
            now,
        )
        assessment = ResearchSourceAssessmentRecord(
            "assessment-1",
            "document-1",
            ("evidence-1",),
            "Assessment.",
            now,
        )

        with self.assertRaisesRegex(ResearchError, "belong to its source"):
            ResearchRun(
                "run-1",
                "Question",
                ResearchRunStatus.COLLECTING,
                sources,
                (),
                now,
                now,
                evidence=(evidence,),
                assessments=(assessment,),
            )

    def test_assessment_supersession_is_append_only_and_single_successor(self) -> None:
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        source = ResearchSourceRecord(
            "document-1",
            "https://example.com/source",
            "Source",
            "text/plain",
            now,
            now,
        )
        evidence = ResearchEvidenceRecord(
            "evidence-1",
            "document-1",
            "chunk-1",
            0,
            "Evidence.",
            False,
            "a" * 64,
            "Relevant.",
            now,
        )
        original = ResearchSourceAssessmentRecord(
            "assessment-1",
            "document-1",
            ("evidence-1",),
            "Original.",
            now,
        )
        correction = ResearchSourceAssessmentRecord(
            "assessment-2",
            "document-1",
            ("evidence-1",),
            "Correction.",
            now,
            "assessment-1",
        )

        run = ResearchRun(
            "run-1",
            "Question",
            ResearchRunStatus.COLLECTING,
            (source,),
            (),
            now,
            now,
            evidence=(evidence,),
            assessments=(original, correction),
        )

        self.assertEqual(run.assessments, (original, correction))

        competing_correction = ResearchSourceAssessmentRecord(
            "assessment-3",
            "document-1",
            ("evidence-1",),
            "Competing correction.",
            now,
            "assessment-1",
        )
        with self.assertRaisesRegex(ResearchError, "multiple superseding"):
            ResearchRun(
                "run-1",
                "Question",
                ResearchRunStatus.COLLECTING,
                (source,),
                (),
                now,
                now,
                evidence=(evidence,),
                assessments=(original, correction, competing_correction),
            )

    def test_assessment_supersession_requires_an_earlier_same_source_target(
        self,
    ) -> None:
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        sources = tuple(
            ResearchSourceRecord(
                f"document-{number}",
                f"https://example.com/{number}",
                f"Source {number}",
                "text/plain",
                now,
                now,
            )
            for number in (1, 2)
        )
        evidence = tuple(
            ResearchEvidenceRecord(
                f"evidence-{number}",
                f"document-{number}",
                f"chunk-{number}",
                0,
                "Evidence.",
                False,
                str(number) * 64,
                "Relevant.",
                now,
            )
            for number in (1, 2)
        )
        original = ResearchSourceAssessmentRecord(
            "assessment-1",
            "document-1",
            ("evidence-1",),
            "Original.",
            now,
        )
        invalid_records = (
            (
                ResearchSourceAssessmentRecord(
                    "assessment-2",
                    "document-1",
                    ("evidence-1",),
                    "Missing target.",
                    now,
                    "assessment-missing",
                ),
                "earlier assessment",
            ),
            (
                ResearchSourceAssessmentRecord(
                    "assessment-2",
                    "document-2",
                    ("evidence-2",),
                    "Cross-source correction.",
                    now,
                    "assessment-1",
                ),
                "within one source",
            ),
        )
        for correction, message in invalid_records:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ResearchError, message):
                    ResearchRun(
                        "run-1",
                        "Question",
                        ResearchRunStatus.COLLECTING,
                        sources,
                        (),
                        now,
                        now,
                        evidence=evidence,
                        assessments=(original, correction),
                    )

    def test_comparison_note_references_cover_every_selected_source(self) -> None:
        now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        sources = tuple(
            ResearchSourceRecord(
                f"document-{number}",
                f"https://example.com/{number}",
                f"Source {number}",
                "text/plain",
                now,
                now,
            )
            for number in (1, 2)
        )
        evidence = tuple(
            ResearchEvidenceRecord(
                f"evidence-{number}",
                f"document-{number}",
                f"chunk-{number}",
                0,
                f"Evidence {number}.",
                False,
                str(number) * 64,
                f"Note {number}.",
                now,
            )
            for number in (1, 2)
        )
        assessments = tuple(
            ResearchSourceAssessmentRecord(
                f"assessment-{number}",
                f"document-{number}",
                (f"evidence-{number}",),
                f"Assessment {number}.",
                now,
            )
            for number in (1, 2)
        )
        note = ResearchSourceComparisonNoteRecord(
            "note-1",
            ("document-1", "document-2"),
            ("evidence-1", "evidence-2"),
            ("assessment-1", "assessment-2"),
            "Comparison.",
            now,
        )

        run = ResearchRun(
            "run-1",
            "Question",
            ResearchRunStatus.COLLECTING,
            sources,
            (),
            now,
            now,
            evidence=evidence,
            assessments=assessments,
            comparison_notes=(note,),
        )

        self.assertEqual(run.comparison_notes, (note,))

        incomplete = ResearchSourceComparisonNoteRecord(
            "note-2",
            ("document-1", "document-2"),
            ("evidence-1",),
            ("assessment-1", "assessment-2"),
            "Incomplete comparison.",
            now,
        )
        with self.assertRaisesRegex(ResearchError, "evidence must cover"):
            ResearchRun(
                "run-1",
                "Question",
                ResearchRunStatus.COLLECTING,
                sources,
                (),
                now,
                now,
                evidence=evidence,
                assessments=assessments,
                comparison_notes=(incomplete,),
            )

    def test_claim_sources_must_exactly_follow_evidence_provenance(self) -> None:
        now = datetime(2026, 8, 21, 20, 0, tzinfo=UTC)
        sources = tuple(
            ResearchSourceRecord(
                f"document-{number}",
                f"https://example.com/{number}",
                f"Source {number}",
                "text/plain",
                now,
                now,
            )
            for number in (1, 2)
        )
        evidence = tuple(
            ResearchEvidenceRecord(
                f"evidence-{number}",
                f"document-{number}",
                f"chunk-{number}",
                0,
                f"Evidence {number}.",
                False,
                str(number) * 64,
                "Relevant.",
                now,
            )
            for number in (1, 2)
        )
        claim = ResearchClaimRecord(
            "claim-1",
            "The sources support different parts of the finding.",
            ResearchEpistemicState.STRONG_EVIDENCE,
            ResearchClaimConfidence.HIGH,
            ("document-2", "document-1"),
            ("evidence-2", "evidence-1"),
            now,
        )

        run = ResearchRun(
            "run-1",
            "Question",
            ResearchRunStatus.COLLECTING,
            sources,
            (),
            now,
            now,
            evidence=evidence,
            claims=(claim,),
        )

        self.assertEqual(run.claims, (claim,))
        mismatched = ResearchClaimRecord(
            "claim-2",
            "Mismatched provenance.",
            ResearchEpistemicState.UNKNOWN,
            ResearchClaimConfidence.LOW,
            ("document-1", "document-2"),
            ("evidence-2", "evidence-1"),
            now,
        )
        with self.assertRaisesRegex(ResearchError, "match its evidence"):
            ResearchRun(
                "run-1",
                "Question",
                ResearchRunStatus.COLLECTING,
                sources,
                (),
                now,
                now,
                evidence=evidence,
                claims=(mismatched,),
            )

    def test_claim_supersession_is_append_only_and_single_successor(self) -> None:
        now = datetime(2026, 8, 21, 20, 0, tzinfo=UTC)
        source = ResearchSourceRecord(
            "document-1",
            "https://example.com/source",
            "Source",
            "text/plain",
            now,
            now,
        )
        evidence = ResearchEvidenceRecord(
            "evidence-1",
            "document-1",
            "chunk-1",
            0,
            "Evidence.",
            False,
            "a" * 64,
            "Relevant.",
            now,
        )
        original = ResearchClaimRecord(
            "claim-1",
            "Original claim.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
            ("document-1",),
            ("evidence-1",),
            now,
        )
        correction = ResearchClaimRecord(
            "claim-2",
            "Evidence contradicts the claim.",
            ResearchEpistemicState.CONTRADICTED,
            ResearchClaimConfidence.HIGH,
            ("document-1",),
            ("evidence-1",),
            now,
            "claim-1",
        )

        run = ResearchRun(
            "run-1",
            "Question",
            ResearchRunStatus.COLLECTING,
            (source,),
            (),
            now,
            now,
            evidence=(evidence,),
            claims=(original, correction),
        )

        self.assertEqual(run.claims, (original, correction))
        competing = ResearchClaimRecord(
            "claim-3",
            "Competing correction.",
            ResearchEpistemicState.LIKELY,
            ResearchClaimConfidence.MEDIUM,
            ("document-1",),
            ("evidence-1",),
            now,
            "claim-1",
        )
        with self.assertRaisesRegex(ResearchError, "multiple superseding"):
            ResearchRun(
                "run-1",
                "Question",
                ResearchRunStatus.COLLECTING,
                (source,),
                (),
                now,
                now,
                evidence=(evidence,),
                claims=(original, correction, competing),
            )

    def test_claim_contradictions_require_exact_claim_evidence_and_unique_pair(
        self,
    ) -> None:
        now = datetime(2026, 8, 21, 21, 0, tzinfo=UTC)
        sources = tuple(
            ResearchSourceRecord(
                f"document-{number}",
                f"https://example.com/{number}",
                f"Source {number}",
                "text/plain",
                now,
                now,
            )
            for number in (1, 2)
        )
        evidence = tuple(
            ResearchEvidenceRecord(
                f"evidence-{number}",
                f"document-{number}",
                f"chunk-{number}",
                0,
                f"Evidence {number}.",
                False,
                str(number) * 64,
                "Relevant.",
                now,
            )
            for number in (1, 2)
        )
        claims = tuple(
            ResearchClaimRecord(
                f"claim-{number}",
                f"Claim {number}.",
                ResearchEpistemicState.LIKELY,
                ResearchClaimConfidence.MEDIUM,
                (f"document-{number}",),
                (f"evidence-{number}",),
                now,
            )
            for number in (1, 2)
        )
        contradiction = ResearchClaimContradictionRecord(
            "contradiction-1",
            ("claim-1", "claim-2"),
            ("evidence-1", "evidence-2"),
            "The conclusions conflict.",
            now,
        )

        run = ResearchRun(
            "run-1",
            "Question",
            ResearchRunStatus.COLLECTING,
            sources,
            (),
            now,
            now,
            evidence=evidence,
            claims=claims,
            claim_contradictions=(contradiction,),
        )

        self.assertEqual(run.claim_contradictions, (contradiction,))
        invalid_relationships = (
            ResearchClaimContradictionRecord(
                "contradiction-2",
                ("claim-2", "claim-1"),
                ("evidence-1", "evidence-2"),
                "Mismatched evidence order.",
                now,
            ),
            ResearchClaimContradictionRecord(
                "contradiction-3",
                ("claim-1", "claim-missing"),
                ("evidence-1", "evidence-2"),
                "Unknown claim.",
                now,
            ),
        )
        with self.assertRaisesRegex(ResearchError, "evidence must match"):
            ResearchRun(
                "run-1",
                "Question",
                ResearchRunStatus.COLLECTING,
                sources,
                (),
                now,
                now,
                evidence=evidence,
                claims=claims,
                claim_contradictions=(invalid_relationships[0],),
            )
        with self.assertRaisesRegex(ResearchError, "persisted claims"):
            ResearchRun(
                "run-1",
                "Question",
                ResearchRunStatus.COLLECTING,
                sources,
                (),
                now,
                now,
                evidence=evidence,
                claims=claims,
                claim_contradictions=(invalid_relationships[1],),
            )
        duplicate = ResearchClaimContradictionRecord(
            "contradiction-4",
            ("claim-2", "claim-1"),
            ("evidence-2", "evidence-1"),
            "Same pair again.",
            now,
        )
        with self.assertRaisesRegex(ResearchError, "duplicate.*pair"):
            ResearchRun(
                "run-1",
                "Question",
                ResearchRunStatus.COLLECTING,
                sources,
                (),
                now,
                now,
                evidence=evidence,
                claims=claims,
                claim_contradictions=(contradiction, duplicate),
            )


if __name__ == "__main__":
    unittest.main()
