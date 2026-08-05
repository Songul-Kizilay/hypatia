"""Unit tests for the read-only SessionMemoryPolicy."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.MemoryRecord import MemoryRecord
from memory.SessionMemoryPolicy import SessionMemoryPolicy


class SessionMemoryPolicyTests(unittest.TestCase):
    def _record(
        self,
        *,
        metadata: dict[str, object] | None = None,
        tags: frozenset[str] | None = None,
    ) -> MemoryRecord:
        return MemoryRecord(
            memory_id="record-1",
            content="Conversation",
            metadata={} if metadata is None else metadata,
            tags=frozenset({"brain", "conversation"}) if tags is None else tags,
        )

    def test_is_conversation_accepts_required_tags_with_extra_tags(self) -> None:
        record = self._record(tags=frozenset({"brain", "conversation", "extra"}))

        self.assertTrue(SessionMemoryPolicy.is_conversation(record))

    def test_is_conversation_rejects_missing_required_tags(self) -> None:
        self.assertFalse(
            SessionMemoryPolicy.is_conversation(self._record(tags=frozenset({"brain"})))
        )
        self.assertFalse(
            SessionMemoryPolicy.is_conversation(
                self._record(tags=frozenset({"conversation"}))
            )
        )

    def test_default_session_accepts_missing_or_explicit_default_metadata(self) -> None:
        self.assertTrue(SessionMemoryPolicy.matches(self._record(), "default"))
        self.assertTrue(
            SessionMemoryPolicy.matches(
                self._record(metadata={"session_id": "default"}), "default"
            )
        )

    def test_custom_session_requires_an_exact_case_sensitive_string_match(self) -> None:
        record = self._record(metadata={"session_id": "work research"})

        self.assertTrue(SessionMemoryPolicy.matches(record, "work research"))
        self.assertFalse(SessionMemoryPolicy.matches(record, "Work Research"))
        self.assertFalse(SessionMemoryPolicy.matches(record, "default"))

    def test_none_and_non_string_session_metadata_never_belong_to_a_session(
        self,
    ) -> None:
        for value in (None, 123, ["work"], {"id": "work"}):
            with self.subTest(value=value):
                record = self._record(metadata={"session_id": value})

                self.assertFalse(
                    SessionMemoryPolicy.belongs_to_session(record, "default")
                )
                self.assertFalse(SessionMemoryPolicy.belongs_to_session(record, "work"))

    def test_matches_requires_both_conversation_tags_and_session_ownership(
        self,
    ) -> None:
        record = self._record(
            metadata={"session_id": "work"}, tags=frozenset({"brain"})
        )

        self.assertTrue(SessionMemoryPolicy.belongs_to_session(record, "work"))
        self.assertFalse(SessionMemoryPolicy.matches(record, "work"))

    def test_orphan_session_id_does_not_match_another_session(self) -> None:
        record = self._record(metadata={"session_id": "orphan"})

        self.assertFalse(SessionMemoryPolicy.matches(record, "default"))
        self.assertFalse(SessionMemoryPolicy.matches(record, "work"))
