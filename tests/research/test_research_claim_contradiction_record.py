"""Contracts for explicit user-reviewed research-claim contradictions."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimContradictionPreview import (
    ResearchClaimContradictionPreview,
)
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimContradictionWritePreview import (
    ResearchClaimContradictionWritePreview,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRunStatus import ResearchRunStatus


class ResearchClaimContradictionRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 21, 21, 0, tzinfo=UTC)
        self.claims = (
            ResearchClaimRecord(
                "claim-1",
                "The intervention improves the outcome.",
                ResearchEpistemicState.LIKELY,
                ResearchClaimConfidence.MEDIUM,
                ("document-1",),
                ("evidence-1",),
                self.now,
            ),
            ResearchClaimRecord(
                "claim-2",
                "The intervention does not improve the outcome.",
                ResearchEpistemicState.LIKELY,
                ResearchClaimConfidence.MEDIUM,
                ("document-2",),
                ("evidence-2",),
                self.now,
            ),
        )
        self.evidence = (
            ResearchEvidenceRecord(
                "evidence-1",
                "document-1",
                "chunk-1",
                0,
                "Positive result.",
                False,
                "a" * 64,
                "Supports claim one.",
                self.now,
            ),
            ResearchEvidenceRecord(
                "evidence-2",
                "document-2",
                "chunk-2",
                0,
                "No measurable result.",
                False,
                "b" * 64,
                "Supports claim two.",
                self.now,
            ),
        )

    def test_record_normalizes_exact_authored_relationship(self) -> None:
        record = ResearchClaimContradictionRecord(
            " contradiction-1 ",
            (" claim-1 ", " claim-2 "),
            (" evidence-1 ", " evidence-2 "),
            "  The reported outcomes conflict under the same condition.  ",
            self.now,
        )

        self.assertEqual(record.contradiction_id, "contradiction-1")
        self.assertEqual(record.claim_ids, ("claim-1", "claim-2"))
        self.assertEqual(record.evidence_ids, ("evidence-1", "evidence-2"))
        self.assertEqual(
            record.note,
            "The reported outcomes conflict under the same condition.",
        )

    def test_record_requires_two_distinct_claims_evidence_and_note(self) -> None:
        invalid_values = (
            (("claim-1",), ("evidence-1",), "Note."),
            (("claim-1", "claim-1"), ("evidence-1",), "Note."),
            (("claim-1", "claim-2"), (), "Note."),
            (("claim-1", "claim-2"), ("evidence-1",), " "),
        )
        for claim_ids, evidence_ids, note in invalid_values:
            with self.subTest(claim_ids=claim_ids, evidence_ids=evidence_ids):
                with self.assertRaises(ResearchError):
                    ResearchClaimContradictionRecord(
                        "contradiction-1",
                        claim_ids,  # type: ignore[arg-type]
                        evidence_ids,
                        note,
                        self.now,
                    )

    def test_write_preview_requires_exact_combined_claim_evidence_order(self) -> None:
        with self.assertRaisesRegex(ResearchError, "provenance"):
            ResearchClaimContradictionWritePreview(
                run_id="run-1",
                run_status=ResearchRunStatus.COLLECTING,
                claims=self.claims,
                evidence=(self.evidence[1], self.evidence[0]),
                note="These claims conflict.",
                allowed=True,
                reason="Allowed.",
            )

    def test_history_preview_rejects_unknown_claim_references(self) -> None:
        record = ResearchClaimContradictionRecord(
            "contradiction-1",
            ("claim-1", "claim-missing"),
            ("evidence-1", "evidence-2"),
            "These claims conflict.",
            self.now,
        )
        with self.assertRaisesRegex(ResearchError, "unknown claims"):
            ResearchClaimContradictionPreview(
                run_id="run-1",
                question="Question",
                run_status=ResearchRunStatus.COLLECTING,
                claims=self.claims,
                contradictions=(record,),
                reason="One relationship.",
            )


if __name__ == "__main__":
    unittest.main()
