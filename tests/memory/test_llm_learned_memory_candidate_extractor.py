from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMConversationMessage import LLMConversationMessage
from llm.LLMProvider import LLMError
from memory.LearnedMemoryCandidateExtractionError import (
    LearnedMemoryCandidateExtractionError,
)
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
        *,
        system_instruction: str | None = None,
    ) -> str:
        del system_instruction
        self.calls.append((prompt, history))
        return self.payload


class FailingProvider:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls: list[tuple[str, tuple[LLMConversationMessage, ...]]] = []

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
    ) -> str:
        del system_instruction
        self.calls.append((prompt, history))
        raise self.error


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

    def test_normalizes_provider_error_and_preserves_exact_cause(self) -> None:
        source_text = "  exact source  "
        provider_error = LLMError("provider unavailable")
        provider = FailingProvider(provider_error)
        extractor = LLMLearnedMemoryCandidateExtractor(provider)

        with self.assertRaisesRegex(
            LearnedMemoryCandidateExtractionError,
            "^Learned memory candidate extraction failed\\.$",
        ) as context:
            extractor.extract(source_text)

        self.assertIs(context.exception.__cause__, provider_error)
        self.assertEqual(
            provider.calls,
            [(build_learned_memory_candidate_prompt(source_text), ())],
        )

    def test_does_not_normalize_unrelated_provider_error(self) -> None:
        provider_error = RuntimeError("programming error")
        extractor = LLMLearnedMemoryCandidateExtractor(FailingProvider(provider_error))

        with self.assertRaises(RuntimeError) as context:
            extractor.extract("exact source")

        self.assertIs(context.exception, provider_error)

    def test_normalizes_parser_value_error_and_preserves_exact_cause(self) -> None:
        provider = RecordingProvider("not json")
        extractor = LLMLearnedMemoryCandidateExtractor(provider)

        with self.assertRaisesRegex(
            LearnedMemoryCandidateExtractionError,
            "^Learned memory candidate extraction failed\\.$",
        ) as context:
            extractor.extract("exact source")

        self.assertIsInstance(context.exception.__cause__, ValueError)
        self.assertEqual(
            str(context.exception.__cause__),
            "Learned memory candidate payload invalid.",
        )
        self.assertEqual(
            provider.calls,
            [(build_learned_memory_candidate_prompt("exact source"), ())],
        )


if __name__ == "__main__":
    unittest.main()
