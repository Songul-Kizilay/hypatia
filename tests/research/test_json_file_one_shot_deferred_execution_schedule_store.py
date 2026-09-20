from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.DeferredGrantAuthorizer import DeferredGrantAuthorizer
from research.JsonFileOneShotDeferredExecutionScheduleStore import (
    JsonFileOneShotDeferredExecutionScheduleStore,
    _BoundedUtf8Writer,
)
from research.OneShotDeferredExecutionSchedule import OneShotDeferredExecutionSchedule

CREATED_AT = datetime(2026, 9, 2, tzinfo=UTC)


def schedule(
    schedule_id: str = "schedule-1",
    task_id: str = "task-1",
) -> OneShotDeferredExecutionSchedule:
    return OneShotDeferredExecutionSchedule(
        schedule_id=schedule_id,
        task_id=task_id,
        grant_id="grant-1",
        run_at=CREATED_AT + timedelta(hours=1),
        created_at=CREATED_AT,
        created_by=DeferredGrantAuthorizer.TRUSTED_LOCAL_OPERATOR,
    )


class JsonFileOneShotDeferredExecutionScheduleStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "schedules.json"
        self.store = JsonFileOneShotDeferredExecutionScheduleStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_round_trip_is_lossless(self) -> None:
        original = [schedule(schedule_id="schedule-1", task_id="task-1")]

        self.store.save(original)

        self.assertEqual(self.store.load(), original)

    def test_partial_write_failure_preserves_previous_document_byte_for_byte(
        self,
    ) -> None:
        self.store.save(
            [schedule(schedule_id="schedule-original", task_id="task-original")]
        )
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
                [
                    schedule(
                        schedule_id="schedule-replacement",
                        task_id="task-replacement",
                    )
                ]
            )

        self.assertGreaterEqual(
            call_count["calls"],
            2,
            "the failure must occur after a real write, not before one",
        )
        self.assertEqual(self.path.read_bytes(), original)

    def test_partial_write_failure_leaves_no_temporary_file(self) -> None:
        self.store.save(
            [schedule(schedule_id="schedule-original", task_id="task-original")]
        )
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
                [
                    schedule(
                        schedule_id="schedule-replacement",
                        task_id="task-replacement",
                    )
                ]
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
        self.store.save(
            [schedule(schedule_id="schedule-original", task_id="task-original")]
        )

        with (
            patch(
                "research.JsonFileOneShotDeferredExecutionScheduleStore.os.replace",
                side_effect=OSError("replace failed"),
            ),
            patch.object(Path, "unlink", side_effect=OSError("cleanup failed")),
        ):
            with self.assertRaises(ResearchError) as context:
                self.store.save(
                    [
                        schedule(
                            schedule_id="schedule-replacement",
                            task_id="task-replacement",
                        )
                    ]
                )

        cause = context.exception.__cause__
        self.assertIsInstance(cause, OSError)
        self.assertEqual(str(cause), "replace failed")


if __name__ == "__main__":
    unittest.main()
