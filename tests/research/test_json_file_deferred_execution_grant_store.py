from __future__ import annotations

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
from research.DeferredExecutionGrant import DeferredExecutionGrant
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.JsonFileDeferredExecutionGrantStore import (
    JsonFileDeferredExecutionGrantStore,
    _BoundedUtf8Writer,
)
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

GRANTED_AT = datetime(2026, 9, 2, tzinfo=UTC)


def grant(
    grant_id: str = "grant-1",
    task_id: str = "task-1",
) -> DeferredExecutionGrant:
    return DeferredExecutionGrant(
        grant_id=grant_id,
        task_id=task_id,
        execution_id="execution-1",
        plan_digest="a" * 64,
        capabilities=frozenset({ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH}),
        approved_restrictions=frozenset(),
        task_budget=ResearchAutonomyBudget(),
        granted_at=GRANTED_AT,
        granted_by=DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR,
    )


class JsonFileDeferredExecutionGrantStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "grants.json"
        self.store = JsonFileDeferredExecutionGrantStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_round_trip_is_lossless(self) -> None:
        original = [grant(grant_id="grant-1", task_id="task-1")]

        self.store.save(original)

        self.assertEqual(self.store.load(), original)

    def test_truncated_valid_prefix_on_load_fails_safely(self) -> None:
        self.store.save(
            [
                grant(grant_id="grant-1", task_id="task-1"),
                grant(grant_id="grant-2", task_id="task-2"),
            ]
        )
        original_bytes = self.path.read_bytes()

        self.path.write_bytes(original_bytes[: len(original_bytes) // 2])

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_partial_write_failure_preserves_previous_document_byte_for_byte(
        self,
    ) -> None:
        self.store.save([grant(grant_id="grant-original", task_id="task-original")])
        original = self.path.read_bytes()
        real_write = _BoundedUtf8Writer.write
        call_count = {"calls": 0}

        def flaky_write(self: _BoundedUtf8Writer, value: str) -> int:
            call_count["calls"] += 1
            if call_count["calls"] == 1:
                return real_write(self, value)
            raise OSError("simulated mid-write failure")

        with (
            patch.object(
                _BoundedUtf8Writer, "write", autospec=True, side_effect=flaky_write
            ),
            self.assertRaises(ResearchError),
        ):
            self.store.save(
                [grant(grant_id="grant-replacement", task_id="task-replacement")]
            )

        self.assertGreaterEqual(
            call_count["calls"],
            2,
            "the failure must occur after a real write, not before one",
        )
        self.assertEqual(self.path.read_bytes(), original)

    def test_partial_write_failure_leaves_no_temporary_file(self) -> None:
        self.store.save([grant(grant_id="grant-original", task_id="task-original")])
        real_write = _BoundedUtf8Writer.write
        call_count = {"calls": 0}

        def flaky_write(self: _BoundedUtf8Writer, value: str) -> int:
            call_count["calls"] += 1
            if call_count["calls"] == 1:
                return real_write(self, value)
            raise OSError("simulated mid-write failure")

        with (
            patch.object(
                _BoundedUtf8Writer, "write", autospec=True, side_effect=flaky_write
            ),
            self.assertRaises(ResearchError),
        ):
            self.store.save(
                [grant(grant_id="grant-replacement", task_id="task-replacement")]
            )

        self.assertGreaterEqual(call_count["calls"], 2)
        leftovers = [
            entry
            for entry in self.path.parent.iterdir()
            if entry.name.startswith(f".{self.path.name}.")
        ]
        self.assertEqual(leftovers, [])

    def test_cleanup_unlink_failure_does_not_mask_the_original_research_error(
        self,
    ) -> None:
        self.store.save([grant(grant_id="grant-original", task_id="task-original")])

        with (
            patch(
                "research.JsonFileDeferredExecutionGrantStore.os.replace",
                side_effect=OSError("replace failed"),
            ),
            patch.object(Path, "unlink", side_effect=OSError("cleanup failed")),
        ):
            with self.assertRaises(ResearchError) as context:
                self.store.save(
                    [grant(grant_id="grant-replacement", task_id="task-replacement")]
                )

        cause = context.exception.__cause__
        self.assertIsInstance(cause, OSError)
        self.assertEqual(str(cause), "replace failed")


if __name__ == "__main__":
    unittest.main()
