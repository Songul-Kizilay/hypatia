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
        self.assertIsNone(config.timeout_seconds)

        with self.assertRaises(FrozenInstanceError):
            config.enabled = False  # type: ignore[misc]

    def test_config_preserves_valid_explicit_timeout(self) -> None:
        config = LLMRuntimeConfig(
            enabled=True,
            base_url="https://api.example.test/v1/chat/completions",
            model="test-model",
            timeout_seconds=7.5,
        )

        self.assertEqual(config.timeout_seconds, 7.5)

    def test_config_rejects_invalid_timeouts(self) -> None:
        for timeout in (True, 0, -1, float("inf"), "30"):
            with self.subTest(timeout=timeout):
                with self.assertRaisesRegex(ValueError, "positive number"):
                    LLMRuntimeConfig(
                        enabled=True,
                        base_url="https://api.example.test/v1/chat/completions",
                        model="test-model",
                        timeout_seconds=timeout,  # type: ignore[arg-type]
                    )
