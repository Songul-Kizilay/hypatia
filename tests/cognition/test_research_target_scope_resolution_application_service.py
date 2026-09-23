"""Target scope resolution previews read a caller-supplied scope; nothing else."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.ResearchTargetScopeResolutionApplicationService import (
    RESEARCH_TARGET_SCOPE_RESOLUTION_PREVIEW_INTENT,
    ResearchTargetScopeResolutionApplicationService,
)
from research.ResearchTargetScope import ResearchTargetScope, TargetHostRule
from research.ResearchTargetScopeResolutionStatus import (
    ResearchTargetScopeResolutionStatus,
)
from response.ResponseComposer import ResponseComposer


def scope_fixture() -> ResearchTargetScope:
    return ResearchTargetScope(
        allowed_hosts=(TargetHostRule("example.test"),),
        excluded_hosts=(TargetHostRule("admin.example.test"),),
    )


class ResearchTargetScopeResolutionApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ResearchTargetScopeResolutionApplicationService(
            ResponseComposer()
        )

    def request(self, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="preview target scope resolution",
            metadata={
                "intent": RESEARCH_TARGET_SCOPE_RESOLUTION_PREVIEW_INTENT,
                "research_target_scope": scope_fixture(),
                "hostname": "example.test",
                **metadata,
            },
        )

    def test_preview_is_explicit_structured_intent_only(self) -> None:
        self.assertTrue(self.service.is_preview_request(self.request()))
        self.assertFalse(
            self.service.is_preview_request(
                BrainRequest(message="hello", metadata={"intent": "message"})
            )
        )

    def test_allowed_host_resolves_in_scope_with_no_side_effects(self) -> None:
        response = self.service.process_preview(self.request())

        self.assertTrue(response.success, response.message)
        resolution = response.research_target_scope_resolution
        assert resolution is not None
        self.assertEqual(
            resolution.status, ResearchTargetScopeResolutionStatus.IN_SCOPE
        )
        self.assertEqual(resolution.matched_rule, "example.test")
        self.assertIn("in_scope", response.message)
        self.assertIn("not an authorization", response.message)

    def test_excluded_host_resolves_out_of_scope(self) -> None:
        response = self.service.process_preview(
            self.request(hostname="admin.example.test")
        )

        self.assertTrue(response.success, response.message)
        resolution = response.research_target_scope_resolution
        assert resolution is not None
        self.assertEqual(
            resolution.status, ResearchTargetScopeResolutionStatus.OUT_OF_SCOPE
        )
        self.assertEqual(resolution.matched_rule, "admin.example.test")

    def test_unaddressed_host_resolves_uncertain_never_out_of_scope(self) -> None:
        response = self.service.process_preview(self.request(hostname="unrelated.test"))

        self.assertTrue(response.success, response.message)
        resolution = response.research_target_scope_resolution
        assert resolution is not None
        self.assertEqual(
            resolution.status, ResearchTargetScopeResolutionStatus.UNCERTAIN
        )
        self.assertIsNone(resolution.matched_rule)
        self.assertIn("none", response.message)

    def test_missing_or_wrong_typed_scope_refuses(self) -> None:
        for metadata in (
            {"research_target_scope": None},
            {"research_target_scope": "not-a-scope"},
        ):
            with self.subTest(metadata=metadata):
                response = self.service.process_preview(self.request(**metadata))
                self.assertFalse(response.success)
                self.assertIsNone(response.research_target_scope_resolution)

    def test_missing_or_wrong_typed_hostname_refuses(self) -> None:
        for metadata in ({"hostname": None}, {"hostname": 123}):
            with self.subTest(metadata=metadata):
                response = self.service.process_preview(self.request(**metadata))
                self.assertFalse(response.success)
                self.assertIsNone(response.research_target_scope_resolution)

    def test_invalid_hostname_syntax_refuses_without_a_resolution(self) -> None:
        response = self.service.process_preview(
            self.request(hostname="host%with%percent")
        )

        self.assertFalse(response.success)
        self.assertIsNone(response.research_target_scope_resolution)


if __name__ == "__main__":
    unittest.main()
