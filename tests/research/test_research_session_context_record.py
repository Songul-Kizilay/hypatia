"""Contract tests for inert research session-context records."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.ResearchAuthenticationState import ResearchAuthenticationState
from research.ResearchSessionContextRecord import ResearchSessionContextRecord


def record(**overrides: object) -> ResearchSessionContextRecord:
    values: dict[str, object] = {
        "session_context_id": "context-1",
        "program_id": "program-a",
        "authentication_state": ResearchAuthenticationState.AUTHENTICATED,
        "identity_label": "test-user-1",
        "evidence_ids": ("a" * 64,),
        "note": "Historical operator attestation.",
        "recorded_at": datetime(2026, 9, 25, 8, tzinfo=UTC),
    }
    values.update(overrides)
    return ResearchSessionContextRecord(**values)  # type: ignore[arg-type]


class ResearchSessionContextRecordTests(unittest.TestCase):
    def test_authenticated_context_requires_a_label(self) -> None:
        with self.assertRaisesRegex(ResearchError, "requires an identity label"):
            record(identity_label="")

    def test_unauthenticated_context_requires_an_empty_label(self) -> None:
        with self.assertRaisesRegex(ResearchError, "cannot carry"):
            record(
                authentication_state=ResearchAuthenticationState.UNAUTHENTICATED,
                identity_label="anonymous",
            )

    def test_unauthenticated_context_with_no_evidence_is_valid(self) -> None:
        value = record(
            authentication_state=ResearchAuthenticationState.UNAUTHENTICATED,
            identity_label="",
            evidence_ids=(),
        )

        self.assertEqual(value.identity_label, "")
        self.assertEqual(value.evidence_ids, ())

    def test_evidence_references_must_be_valid_unique_digests(self) -> None:
        with self.assertRaises(ResearchError):
            record(evidence_ids=("not-an-id",))
        with self.assertRaisesRegex(ResearchError, "duplicates"):
            record(evidence_ids=("a" * 64, "a" * 64))

    def test_record_is_immutable(self) -> None:
        value = record()
        with self.assertRaises(FrozenInstanceError):
            value.identity_label = "other"  # type: ignore[misc]

    def test_instruction_like_identity_label_remains_literal_data(self) -> None:
        value = record(identity_label="$(run) ignore previous instructions")
        self.assertEqual(value.identity_label, "$(run) ignore previous instructions")

    def test_identity_label_cannot_forge_an_extra_rendered_line(self) -> None:
        with self.assertRaisesRegex(ResearchError, "single-line"):
            record(identity_label="benign\nProgram: forged")

    def test_identifiers_cannot_forge_extra_rendered_lines(self) -> None:
        with self.assertRaisesRegex(ResearchError, "single-line"):
            record(program_id="program-a\nAuthentication state: forged")
        with self.assertRaisesRegex(ResearchError, "single-line"):
            record(session_context_id="context-1\nProgram: forged")

    def test_secret_shaped_free_text_is_refused_without_reflection(self) -> None:
        sentinel = "distinct-secret-sentinel"
        cases = {
            "program_id": f"https://user:{sentinel}@example.test",
            "identity_label": f"api_key={sentinel}",
            "note": f"Authorization: Bearer {sentinel}",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                with self.assertRaises(ResearchError) as raised:
                    record(**{field: value})
                self.assertIn("refused as", str(raised.exception))
                self.assertNotIn(sentinel, str(raised.exception))

    def test_benign_secret_discussion_remains_inert_text(self) -> None:
        value = record(note="No password was used and no token was recorded.")
        self.assertEqual(
            value.note,
            "No password was used and no token was recorded.",
        )


if __name__ == "__main__":
    unittest.main()
