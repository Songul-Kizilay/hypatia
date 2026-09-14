"""The default conversation instruction states properties, not one language.

These assertions deliberately describe what the prompt must require rather than
pinning its exact wording. The wording will keep changing as local models
improve; the properties must not. Nothing here claims the prompt makes a weak
model obedient — the runtime enforces the honesty guarantees separately.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.HypatiaSystemPrompt import HYPATIA_DEFAULT_SYSTEM_PROMPT


class HypatiaSystemPromptTests(unittest.TestCase):
    def test_the_prompt_names_hypatia(self) -> None:
        self.assertIn("Hypatia", HYPATIA_DEFAULT_SYSTEM_PROMPT)

    def test_the_prompt_follows_the_user_language_without_naming_one(self) -> None:
        prompt = HYPATIA_DEFAULT_SYSTEM_PROMPT

        self.assertIn("same language the user wrote in", prompt)
        for language in ("English", "Turkish", "Türkçe"):
            self.assertNotIn(language, prompt)

    def test_the_prompt_forbids_mixing_languages(self) -> None:
        self.assertIn("Never mix two languages", HYPATIA_DEFAULT_SYSTEM_PROMPT)

    def test_the_prompt_asks_for_proportionate_answers(self) -> None:
        self.assertIn("Match the length of the request", HYPATIA_DEFAULT_SYSTEM_PROMPT)

    def test_the_prompt_answers_the_latest_message(self) -> None:
        self.assertIn(
            "Answer the message you were just sent",
            HYPATIA_DEFAULT_SYSTEM_PROMPT,
        )

    def test_the_prompt_denies_browsing_and_forbids_research_claims(self) -> None:
        prompt = HYPATIA_DEFAULT_SYSTEM_PROMPT

        self.assertIn("cannot browse the web", prompt)
        self.assertIn("Never say you researched", prompt)
        self.assertIn("collected evidence", prompt)

    def test_the_prompt_permits_admitting_ignorance(self) -> None:
        self.assertIn("say you do not know", HYPATIA_DEFAULT_SYSTEM_PROMPT)
