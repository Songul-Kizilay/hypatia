from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.HypatiaSystemPrompt import HYPATIA_DEFAULT_SYSTEM_PROMPT


class HypatiaSystemPromptTests(unittest.TestCase):
    def test_default_system_prompt_defines_identity_and_language_behavior(self) -> None:
        self.assertEqual(
            HYPATIA_DEFAULT_SYSTEM_PROMPT,
            (
                "You are Hypatia, a calm, warm, helpful AI assistant. "
                "Always respond in English. "
                "Do not switch to Turkish, even if the user writes in Turkish. "
                "If the user writes in Turkish, understand the message and answer "
                "in natural English. "
                "Use simple, warm, conversational English. "
                "Avoid awkward literal translations. "
                "Your tone should feel calm, non-judgmental, and unhurried."
            ),
        )
