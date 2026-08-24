"""Tests for the inert, bounded local-file content payload contract."""

from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchSourceRecord import (
    EXTERNAL_SOURCE_INSTRUCTION_AUTHORITY,
    EXTERNAL_SOURCE_TAINT_LABEL,
)
from tools.FilesystemContentPayload import (
    FILESYSTEM_CONTENT_DISCLOSURE_CLASS,
    FILESYSTEM_CONTENT_ENCODING,
    FILESYSTEM_CONTENT_INSTRUCTION_AUTHORITY,
    FILESYSTEM_CONTENT_KIND,
    FILESYSTEM_CONTENT_SOURCE_KIND,
    FILESYSTEM_CONTENT_TAINT_LABEL,
    MAX_CONTENT_BYTES,
    MAX_CONTENT_OFFSET,
    FilesystemContentPayload,
)
from tools.FilesystemRoot import (
    MAX_PATH_DEPTH,
    MAX_RELATIVE_PATH_LENGTH,
    MAX_ROOT_ID_LENGTH,
)

ROOT_DIR = Path(__file__).resolve().parents[2]


class FilesystemContentPayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.modified_at = datetime(2026, 8, 24, 18, 0, tzinfo=UTC)
        self.read_at = datetime(2026, 8, 24, 18, 1, tzinfo=UTC)

    def payload(self, text: str = "Merhaba, dünya.\n") -> FilesystemContentPayload:
        byte_count = len(text.encode("utf-8"))
        return FilesystemContentPayload(
            root_id="workspace",
            resource="src/example.py",
            offset=0,
            bytes_requested=byte_count,
            bytes_returned=byte_count,
            truncated=False,
            file_size_bytes=byte_count,
            modified_utc=self.modified_at,
            bom_stripped=False,
            read_at_utc=self.read_at,
            text=text,
        )

    def test_binds_exact_utf8_text_to_fixed_local_only_provenance(self) -> None:
        payload = self.payload()

        self.assertEqual(payload.root_id, "workspace")
        self.assertEqual(payload.resource, "src/example.py")
        self.assertEqual(payload.source_kind, FILESYSTEM_CONTENT_SOURCE_KIND)
        self.assertEqual(payload.kind, FILESYSTEM_CONTENT_KIND)
        self.assertEqual(payload.encoding, FILESYSTEM_CONTENT_ENCODING)
        self.assertEqual(payload.taint_label, FILESYSTEM_CONTENT_TAINT_LABEL)
        self.assertEqual(
            payload.instruction_authority,
            FILESYSTEM_CONTENT_INSTRUCTION_AUTHORITY,
        )
        self.assertEqual(
            payload.disclosure_class,
            FILESYSTEM_CONTENT_DISCLOSURE_CLASS,
        )
        self.assertEqual(payload.modified_utc, self.modified_at)
        self.assertEqual(payload.read_at_utc, self.read_at)

    def test_is_frozen_slotted_and_fixed_labels_are_not_constructor_inputs(
        self,
    ) -> None:
        payload = self.payload()

        self.assertFalse(hasattr(payload, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            payload.text = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            replace(payload, taint_label="trusted")

    def test_accepts_the_exact_content_and_offset_bounds(self) -> None:
        text = "a" * MAX_CONTENT_BYTES
        maximum = FilesystemContentPayload(
            root_id="r" * MAX_ROOT_ID_LENGTH,
            resource="a" * MAX_RELATIVE_PATH_LENGTH,
            offset=MAX_CONTENT_OFFSET,
            bytes_requested=MAX_CONTENT_BYTES,
            bytes_returned=MAX_CONTENT_BYTES,
            truncated=False,
            file_size_bytes=MAX_CONTENT_OFFSET,
            modified_utc=self.modified_at,
            bom_stripped=False,
            read_at_utc=self.read_at,
            text=text,
        )

        self.assertEqual(len(maximum.text.encode("utf-8")), MAX_CONTENT_BYTES)

    def test_rejects_out_of_range_and_boolean_whole_numbers(self) -> None:
        payload = self.payload("a")

        for field_name, value in (
            ("offset", -1),
            ("offset", MAX_CONTENT_OFFSET + 1),
            ("offset", True),
            ("bytes_requested", MAX_CONTENT_BYTES + 1),
            ("bytes_requested", False),
            ("bytes_returned", 2),
            ("bytes_returned", True),
            ("file_size_bytes", -1),
            ("file_size_bytes", True),
        ):
            with self.subTest(field_name=field_name, value=value):
                with self.assertRaisesRegex(ResearchError, "invalid"):
                    replace(payload, **cast(Any, {field_name: value}))

    def test_rejects_non_boolean_flags_and_inconsistent_truncation(self) -> None:
        payload = self.payload("a")

        with self.assertRaisesRegex(ResearchError, "flag must be boolean"):
            replace(payload, truncated=cast(Any, 1))
        with self.assertRaisesRegex(ResearchError, "flag must be boolean"):
            replace(payload, bom_stripped=cast(Any, 1))
        with self.assertRaisesRegex(ResearchError, "disagrees"):
            replace(payload, file_size_bytes=2)
        truncated = replace(payload, file_size_bytes=2, truncated=True)
        self.assertTrue(truncated.truncated)

    def test_accepts_zero_bytes_at_or_past_eof(self) -> None:
        at_eof = FilesystemContentPayload(
            root_id="workspace",
            resource="empty.txt",
            offset=0,
            bytes_requested=0,
            bytes_returned=0,
            truncated=False,
            file_size_bytes=0,
            modified_utc=self.modified_at,
            bom_stripped=False,
            read_at_utc=self.read_at,
            text="",
        )
        past_eof = replace(at_eof, offset=100)

        self.assertEqual(at_eof.text, "")
        self.assertFalse(past_eof.truncated)

    def test_bom_claim_reconciles_raw_and_decoded_byte_counts(self) -> None:
        payload = FilesystemContentPayload(
            root_id="workspace",
            resource="bom.txt",
            offset=0,
            bytes_requested=8,
            bytes_returned=8,
            truncated=False,
            file_size_bytes=8,
            modified_utc=self.modified_at,
            bom_stripped=True,
            read_at_utc=self.read_at,
            text="hello",
        )

        self.assertTrue(payload.bom_stripped)
        with self.assertRaisesRegex(ResearchError, "BOM claim"):
            replace(payload, offset=1)
        with self.assertRaisesRegex(ResearchError, "BOM claim"):
            replace(payload, bytes_requested=2, bytes_returned=2, file_size_bytes=2)

    def test_rejects_unstripped_bom_invalid_unicode_and_count_mismatch(self) -> None:
        payload = self.payload("a")

        with self.assertRaisesRegex(ResearchError, "leading BOM"):
            replace(
                payload,
                text="\ufeffa",
                bytes_requested=4,
                bytes_returned=4,
                file_size_bytes=4,
            )
        with self.assertRaisesRegex(ResearchError, "valid Unicode"):
            replace(payload, text="\ud800")
        with self.assertRaisesRegex(ResearchError, "byte count"):
            replace(payload, bytes_requested=2, bytes_returned=2, file_size_bytes=2)

    def test_rejects_naive_or_non_datetime_provenance_times(self) -> None:
        payload = self.payload("a")

        for field_name, value in (
            ("modified_utc", datetime(2026, 8, 24, 18, 0)),
            ("read_at_utc", datetime(2026, 8, 24, 18, 1)),
            ("read_at_utc", "2026-08-24T18:01:00Z"),
        ):
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ResearchError, "timezone-aware"):
                    replace(payload, **cast(Any, {field_name: value}))

    def test_bounds_root_and_requires_a_canonical_relative_resource(self) -> None:
        payload = self.payload("a")

        for changes in (
            {"root_id": " "},
            {"root_id": "r" * (MAX_ROOT_ID_LENGTH + 1)},
            {"root_id": "\ud800"},
            {"resource": ""},
            {"resource": "a" * (MAX_RELATIVE_PATH_LENGTH + 1)},
            {"resource": "\ud800.txt"},
            {"resource": "/absolute.txt"},
            {"resource": "C:/drive.txt"},
            {"resource": "parent\\file.txt"},
            {"resource": "parent//file.txt"},
            {"resource": "parent/../file.txt"},
            {"resource": "/".join("x" for _ in range(MAX_PATH_DEPTH + 1))},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ResearchError):
                    replace(payload, **cast(Any, changes))

    def test_uses_the_existing_untrusted_no_authority_class(self) -> None:
        payload = self.payload("a")

        self.assertEqual(payload.taint_label, EXTERNAL_SOURCE_TAINT_LABEL)
        self.assertEqual(
            payload.instruction_authority,
            EXTERNAL_SOURCE_INSTRUCTION_AUTHORITY,
        )


class FilesystemContentPayloadIsolationTests(unittest.TestCase):
    def test_no_production_module_uses_the_inert_payload_yet(self) -> None:
        offenders = []
        for path in (ROOT_DIR / "src").rglob("*.py"):
            if path.name == "FilesystemContentPayload.py":
                continue
            if "FilesystemContentPayload" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(ROOT_DIR).as_posix())

        self.assertEqual(offenders, [])

    def test_payload_source_has_no_filesystem_or_integration_operation(self) -> None:
        source = (ROOT_DIR / "src" / "tools" / "FilesystemContentPayload.py").read_text(
            encoding="utf-8"
        )

        for forbidden in (
            "open(",
            "os.read",
            "ReadFile",
            "NtReadFile",
            "subprocess",
            "ToolResult",
            "ToolCapability",
            "ToolEffect",
            "ToolRuntime",
            "LLMProvider",
            "MemoryManager",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
