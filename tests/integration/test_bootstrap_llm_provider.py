from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cognition.CognitiveEngine import CognitiveEngine
from core.Bootstrap import Bootstrap
from llm.LLMProvider import LLMProvider


class FakeLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.generate_calls = 0

    def generate(self, prompt: str) -> str:
        self.generate_calls += 1
        return "unused"


class BootstrapLLMProviderTests(unittest.TestCase):
    def test_bootstrap_passes_the_supplied_provider_to_cognitive_engine(self) -> None:
        provider = FakeLLMProvider()

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bootstrap = Bootstrap(
                memory_path=temporary_path / "memory.json",
                session_path=temporary_path / "sessions.json",
                llm_provider=provider,
            )
            bootstrap.initialize()

            cognitive_engine = bootstrap.container.resolve(CognitiveEngine)

        self.assertIs(cognitive_engine._llm_provider, provider)
        self.assertEqual(provider.generate_calls, 0)
