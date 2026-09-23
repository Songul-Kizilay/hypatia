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
from research.FailureLessonKind import FailureLessonKind
from research.JsonFileFailureLessonStore import (
    JsonFileFailureLessonStore,
    _BoundedUtf8Writer,
)
from research.ResearchFailureLesson import ResearchFailureLesson

RECORDED_AT = datetime(2026, 8, 23, tzinfo=UTC)


def lesson(lesson_id: str = "lesson-1") -> ResearchFailureLesson:
    return ResearchFailureLesson(
        lesson_id=lesson_id,
        kind=FailureLessonKind.OPERATION_FAILURE,
        run_id="run-1",
        subject_id="stage-1",
        statement="The fetch stage failed here.",
        provenance=("failure:stage-1",),
        context="Saturn rings question",
        recorded_at=RECORDED_AT,
    )


class JsonFileFailureLessonStoreFailurePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "lessons.json"
        self.store = JsonFileFailureLessonStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_round_trip_is_lossless(self) -> None:
        original = [lesson()]

        self.store.save(original)

        self.assertEqual(self.store.load(), original)

    def test_truncated_valid_prefix_on_load_fails_safely(self) -> None:
        self.store.save([lesson("lesson-1"), lesson("lesson-2")])
        original_bytes = self.path.read_bytes()

        self.path.write_bytes(original_bytes[: len(original_bytes) // 2])

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_partial_write_failure_preserves_previous_snapshot_byte_for_byte(
        self,
    ) -> None:
        self.store.save([lesson("lesson-original")])
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
            self.store.save([lesson("lesson-replacement")])

        self.assertGreaterEqual(
            call_count["calls"],
            2,
            "the failure must occur after a real write, not before one",
        )
        self.assertEqual(self.path.read_bytes(), original)

    def test_partial_write_failure_leaves_no_temporary_file(self) -> None:
        self.store.save([lesson("lesson-original")])
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
            self.store.save([lesson("lesson-replacement")])

        self.assertGreaterEqual(
            call_count["calls"],
            2,
            "the failure must occur after a real write, not before one",
        )
        leftovers = [
            entry
            for entry in self.path.parent.iterdir()
            if entry.name.startswith(f".{self.path.name}.")
        ]
        self.assertEqual(leftovers, [])

    def test_cleanup_unlink_failure_does_not_mask_the_original_research_error(
        self,
    ) -> None:
        self.store.save([lesson("lesson-original")])

        with (
            patch(
                "research.JsonFileFailureLessonStore.os.replace",
                side_effect=OSError("replace failed"),
            ),
            patch.object(Path, "unlink", side_effect=OSError("cleanup failed")),
        ):
            with self.assertRaises(ResearchError) as context:
                self.store.save([lesson("lesson-replacement")])

        cause = context.exception.__cause__
        self.assertIsInstance(cause, OSError)
        self.assertEqual(str(cause), "replace failed")


if __name__ == "__main__":
    unittest.main()
