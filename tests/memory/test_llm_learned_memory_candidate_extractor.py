from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMConversationMessage import LLMConversationMessage
from memory.LearnedMemoryCandidateExtractor import LearnedMemoryCandidateExtractor
from memory.LearnedMemoryCandidatePrompt import (
    build_learned_memory_candidate_prompt,
)
from memory.LLMLearnedMemoryCandidateExtractor import (
    LLMLearnedMemoryCandidateExtractor,
)


class RecordingProvider:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls: list[tuple[str, tuple[LLMConversationMessage, ...]]] = []

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
    ) -> str:
        self.calls.append((prompt, history))
        return self.payload


class LLMLearnedMemoryCandidateExtractorTests(unittest.TestCase):
    def test_calls_provider_once_with_exact_prompt_and_empty_history(self) -> None:
        source_text = "  Ben Python tercih ediyorum.  "
        payload = (
            '{"candidates":['
            '{"kind":"preference",'
            '"key":"preferred_language",'
            '"value":"Python"}'
            "]}"
        )
        provider = RecordingProvider(payload)
        extractor: LearnedMemoryCandidateExtractor = LLMLearnedMemoryCandidateExtractor(
            provider
        )

        batch = extractor.extract(source_text)

        self.assertEqual(
            provider.calls,
            [(build_learned_memory_candidate_prompt(source_text), ())],
        )
        self.assertEqual(batch.source_text, source_text)
        self.assertEqual(len(batch.candidates), 1)
        candidate = batch.candidates[0]
        self.assertEqual(candidate.source_text, source_text)
        self.assertEqual(candidate.memory.kind, "preference")
        self.assertEqual(candidate.memory.key, "preferred_language")
        self.assertEqual(candidate.memory.value, "Python")

    def test_returns_exact_empty_batch_from_empty_payload(self) -> None:
        source_text = "  no supported memory  "
        provider = RecordingProvider('{"candidates":[]}')
        extractor = LLMLearnedMemoryCandidateExtractor(provider)

        batch = extractor.extract(source_text)

        self.assertEqual(
            provider.calls,
            [(build_learned_memory_candidate_prompt(source_text), ())],
        )
        self.assertEqual(batch.source_text, source_text)
        self.assertEqual(batch.candidates, ())

    def test_propagates_parser_value_error_unchanged(self) -> None:
        provider = RecordingProvider("not json")
        extractor = LLMLearnedMemoryCandidateExtractor(provider)

        with self.assertRaisesRegex(
            ValueError,
            "^Learned memory candidate payload invalid\\.$",
        ):
            extractor.extract("exact source")


if __name__ == "__main__":
    unittest.main()
