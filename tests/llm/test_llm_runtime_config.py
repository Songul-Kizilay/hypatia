from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMRuntimeConfig import LLMRuntimeConfig


class LLMRuntimeConfigTests(unittest.TestCase):
    def test_config_preserves_non_secret_values_and_is_immutable(self) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
        )

        self.assertTrue(config.enabled)
        self.assertEqual(
            config.base_url, "https://api.example.test/v1/chat/completions"
        )
        self.assertEqual(config.model, "test-model")

        with self.assertRaises(FrozenInstanceError):
            config.enabled = False
