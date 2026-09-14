"""Presentation contract for one local-only filesystem content preview."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from desktop.FilesystemContentPreview import FilesystemContentPreview

SENTINEL = "do not execute this text 4821"


def preview(**changes: object) -> FilesystemContentPreview:
    values: dict[str, object] = {
        "request_id": "request-1",
        "root_id": "workspace",
        "resource": "notes/readme.txt",
        "offset": 0,
        "bytes_requested": len(SENTINEL.encode()),
        "bytes_returned": len(SENTINEL.encode()),
        "truncated": False,
        "file_size_bytes": len(SENTINEL.encode()),
        "modified_utc": datetime(2026, 8, 24, 19, 0, tzinfo=UTC),
        "bom_stripped": False,
        "read_at_utc": datetime(2026, 8, 24, 19, 1, tzinfo=UTC),
        "source_kind": "local_filesystem",
        "encoding": "utf-8",
        "taint_label": "external_untrusted_data",
        "instruction_authority": "none",
        "disclosure_class": "local_only",
        "text": SENTINEL,
    }
    values.update(changes)
    return FilesystemContentPreview(**values)  # type: ignore[arg-type]


class FilesystemContentPreviewTests(unittest.TestCase):
    def test_text_is_deliberately_absent_from_repr_and_provenance(self) -> None:
        value = preview()

        self.assertNotIn(SENTINEL, repr(value))
        self.assertNotIn(SENTINEL, " ".join(value.provenance_lines()))

    def test_provenance_is_explicit_and_local_only(self) -> None:
        lines = " | ".join(preview().provenance_lines())

        for expected in (
            "Request ID: request-1",
            "Scope: workspace",
            "Entry: notes/readme.txt",
            "Instruction authority: none",
            "Disclosure: local_only",
        ):
            self.assertIn(expected, lines)

    def test_truncation_is_visible(self) -> None:
        value = preview(truncated=True, file_size_bytes=100)

        self.assertEqual(value.completion_label, "truncated")

    def test_invalid_identity_count_or_time_is_rejected(self) -> None:
        for changes in (
            {"request_id": ""},
            {"bytes_returned": 99},
            {"modified_utc": datetime(2026, 8, 24, 19, 0)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ResearchError):
                preview(**changes)


if __name__ == "__main__":
    unittest.main()
