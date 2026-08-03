"""Unit tests for the development configuration loader."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Config import Config


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config()

    def test_loads_application_name(self) -> None:
        self.assertEqual(self.config.get("app_name"), "Hypatia")

    def test_loads_version(self) -> None:
        self.assertEqual(self.config.get("version"), "0.1.0")

    def test_returns_default_for_missing_key(self) -> None:
        self.assertEqual(self.config.get("missing", "fallback"), "fallback")
