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
from research.JsonFileResearchKaliOperationAuthorizationStore import (
    JsonFileResearchKaliOperationAuthorizationStore,
    _BoundedUtf8Writer,
)
from research.ResearchKaliOperationAuthorization import (
    ResearchKaliOperationAuthorization,
)

AUTHORIZED_AT = datetime(2026, 9, 2, tzinfo=UTC)


def authorization(
    authorization_id: str = "authorization-1",
    operation_digest: str = "a" * 64,
    authorized_at: datetime = AUTHORIZED_AT,
) -> ResearchKaliOperationAuthorization:
    return ResearchKaliOperationAuthorization(
        authorization_id=authorization_id,
        operation_digest=operation_digest,
        program_id="program-1",
        scope_revision_id="scope-1",
        scope_revision_digest="b" * 64,
        execution_policy_digest="c" * 64,
        authorized_at=authorized_at,
        expires_at=authorized_at + timedelta(seconds=60),
    )


class JsonFileResearchKaliOperationAuthorizationStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "kali_authorizations.json"
        self.store = JsonFileResearchKaliOperationAuthorizationStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_round_trip_is_lossless(self) -> None:
        original = [authorization(authorization_id="authorization-1")]

        self.store.save(original)

        self.assertEqual(self.store.load(), original)

    def test_truncated_valid_prefix_on_load_fails_safely(self) -> None:
        self.store.save(
            [
                authorization(authorization_id="authorization-1"),
                authorization(authorization_id="authorization-2"),
            ]
        )
        original_bytes = self.path.read_bytes()

        self.path.write_bytes(original_bytes[: len(original_bytes) // 2])

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_partial_write_failure_preserves_previous_document_byte_for_byte(
        self,
    ) -> None:
        self.store.save([authorization(authorization_id="authorization-original")])
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
                [authorization(authorization_id="authorization-replacement")]
            )

        self.assertGreaterEqual(
            call_count["calls"],
            2,
            "the failure must occur after a real write, not before one",
        )
        self.assertEqual(self.path.read_bytes(), original)

    def test_partial_write_failure_leaves_no_temporary_file(self) -> None:
        self.store.save([authorization(authorization_id="authorization-original")])
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
                [authorization(authorization_id="authorization-replacement")]
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
        self.store.save([authorization(authorization_id="authorization-original")])

        with (
            patch(
                "research.JsonFileResearchKaliOperationAuthorizationStore.os.replace",
                side_effect=OSError("replace failed"),
            ),
            patch.object(Path, "unlink", side_effect=OSError("cleanup failed")),
        ):
            with self.assertRaises(ResearchError) as context:
                self.store.save(
                    [authorization(authorization_id="authorization-replacement")]
                )

        cause = context.exception.__cause__
        self.assertIsInstance(cause, OSError)
        self.assertEqual(str(cause), "replace failed")


if __name__ == "__main__":
    unittest.main()
