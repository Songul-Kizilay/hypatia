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
from research.JsonFileCuriosityQuestionStore import (
    JsonFileCuriosityQuestionStore,
    _BoundedUtf8Writer,
)
from research.ResearchCuriosityQuestion import ResearchCuriosityQuestion
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind

RECORDED_AT = datetime(2026, 8, 23, tzinfo=UTC)


def question(question_id: str = "question-1") -> ResearchCuriosityQuestion:
    return ResearchCuriosityQuestion(
        question_id=question_id,
        gap_id=f"gap:{question_id}",
        run_id="run-1",
        kind=ResearchKnowledgeGapKind.UNUSED_SOURCE,
        subject_id="doc-1",
        text="What evidence, if any, does this so-far unused source support?",
        rank_score=100,
        generated_at=RECORDED_AT,
    )


class JsonFileCuriosityQuestionStoreFailurePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "questions.json"
        self.store = JsonFileCuriosityQuestionStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_round_trip_is_lossless(self) -> None:
        original = [question()]

        self.store.save(original)

        self.assertEqual(self.store.load(), original)

    def test_partial_write_failure_preserves_previous_snapshot_byte_for_byte(
        self,
    ) -> None:
        self.store.save([question("question-original")])
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
            self.store.save([question("question-replacement")])

        self.assertGreaterEqual(
            call_count["calls"],
            2,
            "the failure must occur after a real write, not before one",
        )
        self.assertEqual(self.path.read_bytes(), original)

    def test_partial_write_failure_leaves_no_temporary_file(self) -> None:
        self.store.save([question("question-original")])
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
            self.store.save([question("question-replacement")])

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
        self.store.save([question("question-original")])

        with (
            patch(
                "research.JsonFileCuriosityQuestionStore.os.replace",
                side_effect=OSError("replace failed"),
            ),
            patch.object(Path, "unlink", side_effect=OSError("cleanup failed")),
        ):
            with self.assertRaises(ResearchError) as context:
                self.store.save([question("question-replacement")])

        cause = context.exception.__cause__
        self.assertIsInstance(cause, OSError)
        self.assertEqual(str(cause), "replace failed")


if __name__ == "__main__":
    unittest.main()
