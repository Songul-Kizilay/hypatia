from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.JsonFileResearchExecutionStore import (
    MAX_RESEARCH_EXECUTION_STORE_BYTES,
    MAX_RESEARCH_EXECUTION_STORE_EXECUTIONS,
    JsonFileResearchExecutionStore,
)
from research.ResearchPlanExecutionCodec import encode_execution_snapshot
from research.ResearchPlanExecutionSnapshot import (
    ResearchPlanExecutionSnapshot,
    ResearchPlanExecutionStepSnapshot,
)
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepStatus import ResearchPlanStepStatus

RECORDED_AT = datetime(2026, 8, 23, tzinfo=UTC)


def snapshot(
    plan_id: str = "plan-1",
    status: ResearchPlanExecutionStatus = ResearchPlanExecutionStatus.RUNNING,
    step_status: ResearchPlanStepStatus = ResearchPlanStepStatus.PENDING,
    work_performed: bool = False,
    operation: str = "",
) -> ResearchPlanExecutionSnapshot:
    return ResearchPlanExecutionSnapshot(
        plan_id=plan_id,
        question="Does the ring system have a measured age?",
        status=status,
        steps=(
            ResearchPlanExecutionStepSnapshot(
                step_id="step-1",
                capability=ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                status=step_status,
                detail="bounded detail",
                operation=operation,
                work_performed=work_performed,
            ),
        ),
        recorded_at=RECORDED_AT,
        research_run_id="run-1",
    )


class JsonFileResearchExecutionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "executions.json"
        self.store = JsonFileResearchExecutionStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _write(self, document: object) -> None:
        self.path.write_text(json.dumps(document), encoding="utf-8")

    def test_absent_file_is_no_persisted_executions(self) -> None:
        self.assertFalse(self.path.exists())

        self.assertEqual(self.store.load(), [])

    def test_round_trip_is_lossless(self) -> None:
        original = [
            snapshot(
                plan_id="plan-1",
                step_status=ResearchPlanStepStatus.COMPLETED,
                work_performed=True,
                operation="local_knowledge_search",
            ),
            snapshot(plan_id="plan-2"),
        ]

        self.store.save(original)

        self.assertEqual(self.store.load(), original)

    def test_interrupted_state_round_trips(self) -> None:
        original = [
            snapshot(
                status=ResearchPlanExecutionStatus.INTERRUPTED,
                step_status=ResearchPlanStepStatus.INTERRUPTED,
            )
        ]

        self.store.save(original)
        restored = self.store.load()

        self.assertEqual(restored, original)
        self.assertIs(restored[0].status, ResearchPlanExecutionStatus.INTERRUPTED)
        self.assertIs(
            restored[0].steps[0].status,
            ResearchPlanStepStatus.INTERRUPTED,
        )

    def test_saving_an_empty_list_clears_the_document(self) -> None:
        self.store.save([snapshot()])

        self.store.save([])

        self.assertEqual(self.store.load(), [])

    def test_document_is_versioned(self) -> None:
        self.store.save([snapshot()])

        document = json.loads(self.path.read_text(encoding="utf-8"))

        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(set(document), {"schema_version", "executions"})

    def test_corrupted_json_fails_safely(self) -> None:
        self.path.write_text("{ this is not json", encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_unknown_schema_version_is_rejected(self) -> None:
        """Newer than this build understands is refused, not guessed at."""
        self._write({"schema_version": 3, "executions": []})

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_a_version_one_document_loads_as_budget_unenforced(self) -> None:
        """Reading a missing allowance as a full budget is the dangerous way.

        A version 1 record was written before any budget was enforced, so it
        truthfully had none. Defaulting it to a fresh full allowance would make
        an old execution look like it had everything left.
        """
        self.store.save([snapshot()])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        for entry in document["executions"]:
            entry.pop("allowance")
        document["schema_version"] = 1
        self._write(document)

        loaded = self.store.load()

        self.assertEqual(len(loaded), 1)
        self.assertIsNone(loaded[0].allowance)

    def test_unexpected_document_fields_are_rejected(self) -> None:
        self._write({"schema_version": 1, "executions": [], "extra": 1})

        with self.assertRaises(ResearchError):
            self.store.load()
        self._write({"schema_version": 1})
        with self.assertRaises(ResearchError):
            self.store.load()
        self._write(["not", "a", "document"])
        with self.assertRaises(ResearchError):
            self.store.load()

    def test_non_list_executions_are_rejected(self) -> None:
        self._write({"schema_version": 1, "executions": {"plan-1": {}}})

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_oversized_file_is_rejected(self) -> None:
        self.path.write_bytes(b"x" * (MAX_RESEARCH_EXECUTION_STORE_BYTES + 1))

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_too_many_executions_are_rejected_on_load(self) -> None:
        encoded = encode_execution_snapshot(snapshot())
        self._write(
            {
                "schema_version": 1,
                "executions": [
                    {**encoded, "plan_id": f"plan-{index}"}
                    for index in range(MAX_RESEARCH_EXECUTION_STORE_EXECUTIONS + 1)
                ],
            }
        )

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_too_many_executions_are_rejected_on_save(self) -> None:
        overflow = [
            snapshot(plan_id=f"plan-{index}")
            for index in range(MAX_RESEARCH_EXECUTION_STORE_EXECUTIONS + 1)
        ]

        with self.assertRaises(ResearchError):
            self.store.save(overflow)

        self.assertFalse(self.path.exists())

    def test_duplicate_execution_ids_are_rejected_on_load(self) -> None:
        encoded = encode_execution_snapshot(snapshot())
        self._write({"schema_version": 1, "executions": [encoded, dict(encoded)]})

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_duplicate_execution_ids_are_rejected_on_save(self) -> None:
        with self.assertRaises(ResearchError):
            self.store.save([snapshot(), snapshot()])

        self.assertFalse(self.path.exists())

    def test_non_snapshot_values_are_rejected_on_save(self) -> None:
        with self.assertRaises(ResearchError):
            self.store.save(["not-a-snapshot"])  # type: ignore[list-item]
        with self.assertRaises(ResearchError):
            self.store.save({"plan-1": snapshot()})  # type: ignore[arg-type]

    def test_malformed_execution_entry_is_rejected(self) -> None:
        encoded = encode_execution_snapshot(snapshot())
        encoded["status"] = "imaginary"
        self._write({"schema_version": 1, "executions": [encoded]})

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_failed_write_leaves_the_previous_document_intact(self) -> None:
        self.store.save([snapshot(plan_id="plan-original")])
        original_bytes = self.path.read_bytes()

        with (
            patch(
                "research.JsonFileResearchExecutionStore.os.replace",
                side_effect=OSError("replace failed"),
            ),
            self.assertRaises(ResearchError),
        ):
            self.store.save([snapshot(plan_id="plan-replacement")])

        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(self.store.load()[0].plan_id, "plan-original")

    def test_failed_write_leaves_no_temporary_file_behind(self) -> None:
        self.store.save([snapshot()])

        with (
            patch(
                "research.JsonFileResearchExecutionStore.os.replace",
                side_effect=OSError("replace failed"),
            ),
            self.assertRaises(ResearchError),
        ):
            self.store.save([snapshot(plan_id="plan-replacement")])

        leftovers = [
            entry
            for entry in self.path.parent.iterdir()
            if entry.name.startswith(f".{self.path.name}.")
        ]
        self.assertEqual(leftovers, [])

    def test_no_partial_document_when_encoding_fails(self) -> None:
        self.store.save([snapshot(plan_id="plan-original")])
        original_bytes = self.path.read_bytes()

        with (
            patch(
                "research.JsonFileResearchExecutionStore.json.dump",
                side_effect=OverflowError("too large"),
            ),
            self.assertRaises(ResearchError),
        ):
            self.store.save([snapshot(plan_id="plan-replacement")])

        self.assertEqual(self.path.read_bytes(), original_bytes)

    def test_store_creates_its_parent_directory(self) -> None:
        nested = Path(self.temporary_directory.name) / "nested" / "executions.json"
        store = JsonFileResearchExecutionStore(nested)

        store.save([snapshot()])

        self.assertTrue(nested.exists())
        self.assertEqual(len(store.load()), 1)

    def test_stored_document_carries_no_research_content(self) -> None:
        self.store.save(
            [
                snapshot(
                    step_status=ResearchPlanStepStatus.COMPLETED,
                    work_performed=True,
                    operation="local_knowledge_search",
                )
            ]
        )

        raw = self.path.read_text(encoding="utf-8")

        self.assertIn("local_knowledge_search", raw)
        self.assertIn("run-1", raw)
        self.assertNotIn("excerpt", raw)
        self.assertNotIn("claim", raw)
        self.assertNotIn("instruction", raw)


if __name__ == "__main__":
    unittest.main()
