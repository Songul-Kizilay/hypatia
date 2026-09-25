"""Persistence tests for research session contexts."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from core.Exceptions import ResearchError
from research.JsonFileResearchSessionContextStore import (
    JsonFileResearchSessionContextStore,
    ResearchSessionContextDocument,
)
from research.ResearchAuthenticationState import ResearchAuthenticationState
from research.ResearchSessionContextRecord import ResearchSessionContextRecord


def context(
    *, context_id: str = "context-1", program_id: str = "program-a"
) -> ResearchSessionContextRecord:
    return ResearchSessionContextRecord(
        session_context_id=context_id,
        program_id=program_id,
        authentication_state=ResearchAuthenticationState.AUTHENTICATED,
        identity_label="test-user-1",
        evidence_ids=("a" * 64,),
        note="Observed context",
        recorded_at=datetime(2026, 9, 25, 8, tzinfo=UTC),
    )


class ResearchSessionContextStoreTests(unittest.TestCase):
    def test_missing_store_is_empty_and_round_trip_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contexts.json"
            self.assertEqual(
                JsonFileResearchSessionContextStore(path).load().records, ()
            )
            JsonFileResearchSessionContextStore(path).save(
                ResearchSessionContextDocument(records=(context(),))
            )

            reloaded = JsonFileResearchSessionContextStore(path).load()

            self.assertEqual(reloaded.records, (context(),))

    def test_store_is_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contexts.json"
            store = JsonFileResearchSessionContextStore(path)
            first = context()
            store.save(ResearchSessionContextDocument(records=(first,)))
            with self.assertRaisesRegex(ResearchError, "append-only"):
                store.save(ResearchSessionContextDocument())
            second = context(context_id="context-2")
            store.save(ResearchSessionContextDocument(records=(first, second)))
            self.assertEqual(store.load().records, (first, second))

    def test_duplicate_context_ids_are_rejected(self) -> None:
        value = context()
        with self.assertRaisesRegex(ResearchError, "duplicate context IDs"):
            ResearchSessionContextDocument(records=(value, value))

    def test_unknown_fields_and_schema_versions_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contexts.json"
            path.write_text(
                json.dumps({"schema_version": 1, "records": [], "extra": True})
            )
            with self.assertRaises(ResearchError):
                JsonFileResearchSessionContextStore(path).load()
            path.write_text(json.dumps({"schema_version": 2, "records": []}))
            with self.assertRaisesRegex(ResearchError, "schema version"):
                JsonFileResearchSessionContextStore(path).load()
            path.write_text(json.dumps({"schema_version": 1.0, "records": []}))
            with self.assertRaisesRegex(ResearchError, "schema version"):
                JsonFileResearchSessionContextStore(path).load()


if __name__ == "__main__":
    unittest.main()
