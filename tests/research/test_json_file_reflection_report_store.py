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
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.JsonFileReflectionReportStore import (
    JsonFileReflectionReportStore,
    _BoundedUtf8Writer,
)
from research.ReflectionFindingKind import ReflectionFindingKind
from research.ResearchReflectionFinding import ResearchReflectionFinding
from research.ResearchReflectionReport import ResearchReflectionReport

RECORDED_AT = datetime(2026, 8, 23, tzinfo=UTC)


def report(report_id: str = "reflection-1") -> ResearchReflectionReport:
    return ResearchReflectionReport(
        report_id=report_id,
        run_id="run-1",
        question="Does the ring system have a measured age?",
        findings=(
            ResearchReflectionFinding(
                kind=ReflectionFindingKind.WORKED,
                subject_id="sources",
                detail="1 source accepted.",
            ),
        ),
        summary=CanonicalResearchSummary(run_count=1, source_count=1),
        reflected_at=RECORDED_AT,
    )


class JsonFileReflectionReportStoreFailurePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "reflections.json"
        self.store = JsonFileReflectionReportStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_round_trip_is_lossless(self) -> None:
        original = [report()]

        self.store.save(original)

        self.assertEqual(self.store.load(), original)

    def test_truncated_valid_prefix_on_load_fails_safely(self) -> None:
        self.store.save([report("reflection-1"), report("reflection-2")])
        original_bytes = self.path.read_bytes()

        self.path.write_bytes(original_bytes[: len(original_bytes) // 2])

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_partial_write_failure_preserves_previous_snapshot_byte_for_byte(
        self,
    ) -> None:
        self.store.save([report("reflection-original")])
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
            self.store.save([report("reflection-replacement")])

        self.assertGreaterEqual(
            call_count["calls"],
            2,
            "the failure must occur after a real write, not before one",
        )
        self.assertEqual(self.path.read_bytes(), original)

    def test_partial_write_failure_leaves_no_temporary_file(self) -> None:
        self.store.save([report("reflection-original")])
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
            self.store.save([report("reflection-replacement")])

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
        self.store.save([report("reflection-original")])

        with (
            patch(
                "research.JsonFileReflectionReportStore.os.replace",
                side_effect=OSError("replace failed"),
            ),
            patch.object(Path, "unlink", side_effect=OSError("cleanup failed")),
        ):
            with self.assertRaises(ResearchError) as context:
                self.store.save([report("reflection-replacement")])

        cause = context.exception.__cause__
        self.assertIsInstance(cause, OSError)
        self.assertEqual(str(cause), "replace failed")


if __name__ == "__main__":
    unittest.main()
