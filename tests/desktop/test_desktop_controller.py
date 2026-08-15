"""Headless regression coverage for the narrow desktop-to-Brain adapter."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainResponse import BrainResponse
from desktop.DesktopController import DesktopController


class RecordingBrain:
    """Minimal deterministic Brain substitute for desktop adapter tests."""

    def __init__(self, response: BrainResponse) -> None:
        self.requests: list[str] = []
        self._response = response

    def process(self, request: str) -> BrainResponse:
        self.requests.append(request)
        return self._response


class DesktopControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.response = BrainResponse(
            message="Completed.",
            request_id="desktop-test",
            intent="message",
            memory_count=0,
        )
        self.brain = RecordingBrain(self.response)
        self.controller = DesktopController(self.brain)

    def test_submit_message_preserves_non_empty_composer_text(self) -> None:
        message = "  Explain my active project.  "

        response = self.controller.submit_message(message)

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, [message])

    def test_submit_message_rejects_empty_text_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.submit_message(" \t\n ")

        self.assertEqual(self.brain.requests, [])

    def test_select_session_uses_existing_explicit_session_command(self) -> None:
        response = self.controller.select_session("  Work-1  ")

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["use session Work-1"])

    def test_select_session_rejects_empty_id_without_calling_brain(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.controller.select_session("   ")

        self.assertEqual(self.brain.requests, [])

    def test_session_overview_uses_the_read_only_runtime_command(self) -> None:
        response = self.controller.session_overview()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["session overview"])

    def test_semantic_status_uses_the_read_only_runtime_command(self) -> None:
        response = self.controller.semantic_status()

        self.assertIs(response, self.response)
        self.assertEqual(self.brain.requests, ["semantic recall status"])


if __name__ == "__main__":
    unittest.main()
