from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMConversationMessage import LLMConversationMessage


class LLMConversationMessageTests(unittest.TestCase):
    def test_message_preserves_role_and_content_unchanged(self) -> None:
        user_message = LLMConversationMessage(
            role="user",
            content="  Merhaba Hypatia!  ",
        )
        assistant_message = LLMConversationMessage(
            role="assistant",
            content="  Merhaba!  ",
        )

        self.assertEqual(user_message.role, "user")
        self.assertEqual(user_message.content, "  Merhaba Hypatia!  ")
        self.assertEqual(assistant_message.role, "assistant")
        self.assertEqual(assistant_message.content, "  Merhaba!  ")

    def test_message_is_immutable(self) -> None:
        message = LLMConversationMessage(role="user", content="unchanged")

        with self.assertRaises(FrozenInstanceError):
            message.content = "changed"  # type: ignore[misc]
