"""Strict bounded-state tests for durable contradiction investigation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint


def checkpoint(**changes: object) -> ResearchMissionRecoveryCheckpoint:
    fingerprint = "a" * 64
    values: dict[str, object] = {
        "discovery_id": "discovery-1",
        "acquired_urls": (
            "https://first.example/reference",
            "https://second.example/reference",
            "https://third.example/reference",
        ),
        "body_hashes": ("1" * 64, "2" * 64, "3" * 64),
        "inspected_bytes": 900,
        "evidence_ids": ("evidence-1", "evidence-2", "evidence-3"),
        "assessment_ids": ("assessment-1", "assessment-2", "assessment-3"),
        "semantic_note_id": "note-initial",
        "semantic_input_fingerprint": fingerprint,
        "semantic_relation": "possible_conflict",
        "contradiction_initial_note_id": "note-initial",
        "contradiction_initial_evidence_ids": ("evidence-1", "evidence-2"),
        "contradiction_initial_source_document_ids": ("document-1", "document-2"),
        "contradiction_initial_assessment_ids": (
            "assessment-1",
            "assessment-2",
        ),
        "contradiction_initial_input_fingerprint": fingerprint,
        "contradiction_initial_relation": "possible_conflict",
        "contradiction_followup_note_id": "note-followup",
        "contradiction_followup_evidence_id": "evidence-3",
        "contradiction_followup_source_document_id": "document-3",
        "contradiction_followup_assessment_id": "assessment-3",
        "contradiction_followup_input_fingerprint": "b" * 64,
        "contradiction_followup_relation": "possible_agreement",
        "contradiction_outcome": "structurally_clarified",
    }
    values.update(changes)
    return ResearchMissionRecoveryCheckpoint(**values)  # type: ignore[arg-type]


class ResearchMissionRecoveryCheckpointTests(unittest.TestCase):
    def test_valid_outcome_contains_only_bounded_canonical_fields(self) -> None:
        value = checkpoint()

        self.assertEqual(value.contradiction_outcome, "structurally_clarified")
        self.assertEqual(value.contradiction_initial_relation, "possible_conflict")
        self.assertNotIn("rationale", repr(value))
        self.assertNotIn("winner", repr(value))

    def test_legacy_checkpoint_without_outcome_remains_readable(self) -> None:
        value = ResearchMissionRecoveryCheckpoint(
            discovery_id="discovery-1",
            acquired_urls=("https://first.example/reference",),
            body_hashes=("1" * 64,),
        )

        self.assertEqual(value.contradiction_outcome, "")
        self.assertEqual(value.contradiction_initial_note_id, "")

    def test_inconsistent_initial_binding_is_rejected(self) -> None:
        with self.assertRaises(ResearchError):
            checkpoint(contradiction_initial_note_id="different-note")

    def test_followup_cannot_exist_without_the_initial_conflict(self) -> None:
        with self.assertRaises(ResearchError):
            checkpoint(
                contradiction_initial_note_id="",
                contradiction_initial_evidence_ids=(),
                contradiction_initial_source_document_ids=(),
                contradiction_initial_assessment_ids=(),
                contradiction_initial_input_fingerprint="",
                contradiction_initial_relation="",
            )

    def test_outcome_must_match_a_complete_typed_followup(self) -> None:
        with self.assertRaises(ResearchError):
            checkpoint(contradiction_outcome="resolved")
        with self.assertRaises(ResearchError):
            checkpoint(contradiction_followup_assessment_id="")


if __name__ == "__main__":
    unittest.main()
