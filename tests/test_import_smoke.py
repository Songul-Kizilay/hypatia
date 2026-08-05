"""Fresh-process smoke tests for the runtime import graph."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"


class ImportSmokeTests(unittest.TestCase):
    def assert_clean_import(self, statement: str, expected_output: str) -> None:
        """Run one import in a new Python process."""
        environment = {**os.environ, "PYTHONPATH": str(SRC_DIR)}
        result = subprocess.run(
            [sys.executable, "-c", statement],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), expected_output)

    def test_response_composer_imports_in_a_clean_process(self) -> None:
        self.assert_clean_import(
            "from response.ResponseComposer import ResponseComposer; "
            "print('ResponseComposer import OK')",
            "ResponseComposer import OK",
        )

    def test_cognitive_engine_imports_in_a_clean_process(self) -> None:
        self.assert_clean_import(
            "from cognition.CognitiveEngine import CognitiveEngine; "
            "print('CognitiveEngine import OK')",
            "CognitiveEngine import OK",
        )

    def test_session_manager_imports_in_a_clean_process(self) -> None:
        self.assert_clean_import(
            "from session.SessionManager import SessionManager; "
            "print('SessionManager import OK')",
            "SessionManager import OK",
        )

    def test_bootstrap_initializes_in_a_clean_process(self) -> None:
        self.assert_clean_import(
            "from core.Bootstrap import Bootstrap; Bootstrap().initialize(); "
            "print('Bootstrap OK')",
            "Bootstrap OK",
        )
