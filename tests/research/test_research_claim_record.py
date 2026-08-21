"""Contracts for evidence-linked user-authored research claims."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchClaimWritePreview import ResearchClaimWritePreview
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceRecord import ResearchSourceRecord


class ResearchClaimRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 21, 19, 0, tzinfo=UTC)
        self.source = ResearchSourceRecord(
            "document-1",
            "https://example.com/source",
            "Source",
            "text/plain",
            self.now,
            self.now,
        )
        self.evidence = ResearchEvidenceRecord(
            "evidence-1",
            "document-1",
            "chunk-1",
            0,
            "Evidence.",
            False,
            "a" * 64,
            "Relevant.",
            self.now,
        )

    def test_record_normalizes_auditable_authored_metadata(self) -> None:
        record = ResearchClaimRecord(
            " claim-1 ",
            "  The finding is reproducible.  ",
            ResearchEpistemicState.STRONG_EVIDENCE,
            ResearchClaimConfidence.HIGH,
            (" document-1 ",),
            (" evidence-1 ",),
            self.now,
        )

        self.assertEqual(record.claim_id, "claim-1")
        self.assertEqual(record.text, "The finding is reproducible.")
        self.assertEqual(
            record.epistemic_state,
            ResearchEpistemicState.STRONG_EVIDENCE,
        )
        self.assertEqual(record.confidence, ResearchClaimConfidence.HIGH)
        self.assertEqual(record.source_document_ids, ("document-1",))
        self.assertEqual(record.evidence_ids, ("evidence-1",))

    def test_all_plan_epistemic_states_are_explicit(self) -> None:
        self.assertEqual(
            tuple(state.value for state in ResearchEpistemicState),
            (
                "fact",
                "strong_evidence",
                "likely",
                "hypothesis",
                "speculation",
                "unknown",
                "contradicted",
            ),
        )

    def test_record_rejects_unsupported_or_duplicate_provenance(self) -> None:
        invalid_values = (
            ((), ("evidence-1",)),
            (("document-1",), ()),
            (("document-1", "document-1"), ("evidence-1",)),
            (("document-1",), ("evidence-1", "evidence-1")),
        )
        for source_ids, evidence_ids in invalid_values:
            with self.subTest(source_ids=source_ids, evidence_ids=evidence_ids):
                with self.assertRaises(ResearchError):
                    ResearchClaimRecord(
                        "claim-1",
                        "Claim.",
                        ResearchEpistemicState.UNKNOWN,
                        ResearchClaimConfidence.UNASSESSED,
                        source_ids,
                        evidence_ids,
                        self.now,
                    )

    def test_record_requires_typed_state_and_confidence(self) -> None:
        with self.assertRaisesRegex(ResearchError, "epistemic state"):
            ResearchClaimRecord(
                "claim-1",
                "Claim.",
                "fact",  # type: ignore[arg-type]
                ResearchClaimConfidence.HIGH,
                ("document-1",),
                ("evidence-1",),
                self.now,
            )
        with self.assertRaisesRegex(ResearchError, "confidence"):
            ResearchClaimRecord(
                "claim-1",
                "Claim.",
                ResearchEpistemicState.FACT,
                "high",  # type: ignore[arg-type]
                ("document-1",),
                ("evidence-1",),
                self.now,
            )

    def test_write_preview_requires_evidence_source_order_consistency(self) -> None:
        with self.assertRaisesRegex(ResearchError, "provenance"):
            ResearchClaimWritePreview(
                run_id="run-1",
                run_status=ResearchRunStatus.COLLECTING,
                sources=(
                    ResearchSourceRecord(
                        "document-2",
                        "https://example.com/other",
                        "Other",
                        "text/plain",
                        self.now,
                        self.now,
                    ),
                ),
                evidence=(self.evidence,),
                text="Claim.",
                epistemic_state=ResearchEpistemicState.UNKNOWN,
                confidence=ResearchClaimConfidence.UNASSESSED,
                allowed=True,
                reason="Allowed.",
            )


if __name__ == "__main__":
    unittest.main()
