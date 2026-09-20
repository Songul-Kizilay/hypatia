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
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
    _BoundedUtf8Writer,
)
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchPlanAuthorization import ResearchPlanAuthorization
from research.ResearchPlanStepCapability import ResearchPlanStepCapability

AUTHORIZED_AT = datetime(2026, 9, 2, tzinfo=UTC)


def authorization(
    authorization_id: str = "authorization-1",
    research_run_id: str = "run-1",
) -> ResearchPlanAuthorization:
    return ResearchPlanAuthorization(
        authorization_id=authorization_id,
        plan_digest="a" * 64,
        research_run_id=research_run_id,
        capabilities=frozenset({ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH}),
        budget=ResearchAutonomyBudget(),
        authorized_at=AUTHORIZED_AT,
        expires_at=AUTHORIZED_AT + timedelta(minutes=30),
        approved_restrictions=frozenset(),
        disclosure=ResearchDisclosure.NONE,
        authorized_by=ResearchAuthorizer.HUMAN,
    )


class JsonFileResearchPlanAuthorizationStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "authorizations.json"
        self.store = JsonFileResearchPlanAuthorizationStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_round_trip_is_lossless(self) -> None:
        original = [authorization(authorization_id="authorization-1")]

        self.store.save(original)

        self.assertEqual(self.store.load(), original)

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
                "research.JsonFileResearchPlanAuthorizationStore.os.replace",
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
