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
from memory.LearnedMemoryCandidateParser import (
    parse_learned_memory_candidate_batch,
)
from memory.LearnedMemoryCandidatePrompt import (
    EXTRACTION_MAX_TOKENS,
    LEARNED_MEMORY_EXTRACTION_SYSTEM_INSTRUCTION,
    build_learned_memory_candidate_prompt,
    build_learned_memory_candidate_response_schema,
)
from memory.LLMLearnedMemoryCandidateExtractor import (
    LLMLearnedMemoryCandidateExtractor,
)

_VALID_PAYLOAD = (
    '{"candidates":[{"kind":"preference","key":"favorite_planet",' '"value":"Saturn"}]}'
)


class StructuredJSONProvider:
    """Provider exposing the optional structured-JSON capability."""

    def __init__(self, payload: str = _VALID_PAYLOAD) -> None:
        self.payload = payload
        self.generate_calls: list[tuple[str, tuple[LLMConversationMessage, ...]]] = []
        self.generate_json_calls: list[dict[str, object]] = []

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
    ) -> str:
        del system_instruction
        self.generate_calls.append((prompt, history))
        return self.payload

    def generate_json(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
        max_tokens: int = 512,
        response_schema: dict[str, object] | None = None,
    ) -> str:
        self.generate_json_calls.append(
            {
                "prompt": prompt,
                "history": history,
                "system_instruction": system_instruction,
                "max_tokens": max_tokens,
                "response_schema": response_schema,
            }
        )
        return self.payload


class FailingStructuredJSONProvider(StructuredJSONProvider):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def generate_json(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
        max_tokens: int = 512,
        response_schema: dict[str, object] | None = None,
    ) -> str:
        super().generate_json(
            prompt,
            history,
            system_instruction=system_instruction,
            max_tokens=max_tokens,
            response_schema=response_schema,
        )
        raise self.error


class GenerateOnlyProvider:
    """Provider without the optional structured-JSON capability."""

    def __init__(self, payload: str = _VALID_PAYLOAD) -> None:
        self.payload = payload
        self.calls: list[tuple[str, tuple[LLMConversationMessage, ...]]] = []
        self.system_instructions: list[str | None] = []

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
    ) -> str:
        self.calls.append((prompt, history))
        self.system_instructions.append(system_instruction)
        return self.payload


class StructuredExtractionTests(unittest.TestCase):
    def test_structured_provider_uses_generate_json_with_exact_arguments(
        self,
    ) -> None:
        source_text = "  My favorite planet is Saturn.  "
        provider = StructuredJSONProvider()
        extractor = LLMLearnedMemoryCandidateExtractor(provider)

        batch = extractor.extract(source_text)

        self.assertEqual(provider.generate_calls, [])
        self.assertEqual(len(provider.generate_json_calls), 1)
        call = provider.generate_json_calls[0]
        self.assertEqual(
            call["prompt"],
            build_learned_memory_candidate_prompt(source_text),
        )
        self.assertEqual(call["history"], ())
        self.assertEqual(
            call["system_instruction"],
            LEARNED_MEMORY_EXTRACTION_SYSTEM_INSTRUCTION,
        )
        self.assertEqual(call["max_tokens"], EXTRACTION_MAX_TOKENS)
        self.assertEqual(
            call["response_schema"],
            build_learned_memory_candidate_response_schema(),
        )
        self.assertEqual(batch.source_text, source_text)
        self.assertEqual(len(batch.candidates), 1)
        self.assertEqual(batch.candidates[0].memory.key, "favorite_planet")
        self.assertEqual(batch.candidates[0].memory.value, "Saturn")

    def test_generate_only_provider_preserves_exact_fallback_call(self) -> None:
        source_text = "  My favorite planet is Saturn.  "
        provider = GenerateOnlyProvider()
        extractor = LLMLearnedMemoryCandidateExtractor(provider)

        batch = extractor.extract(source_text)

        self.assertEqual(
            provider.calls,
            [(build_learned_memory_candidate_prompt(source_text), ())],
        )
        self.assertEqual(provider.system_instructions, [None])
        self.assertEqual(len(batch.candidates), 1)

    def test_structured_provider_llm_error_is_normalized_with_exact_cause(
        self,
    ) -> None:
        provider_error = LLMError("provider unavailable")
        provider = FailingStructuredJSONProvider(provider_error)
        extractor = LLMLearnedMemoryCandidateExtractor(provider)

        with self.assertRaisesRegex(
            LearnedMemoryCandidateExtractionError,
            "^Learned memory candidate extraction failed\\.$",
        ) as context:
            extractor.extract("exact source")

        self.assertIs(context.exception.__cause__, provider_error)
        self.assertEqual(len(provider.generate_json_calls), 1)
        self.assertEqual(provider.generate_calls, [])

    def test_structured_provider_type_error_propagates_unchanged(self) -> None:
        provider_error = TypeError("incompatible generate_json signature")
        extractor = LLMLearnedMemoryCandidateExtractor(
            FailingStructuredJSONProvider(provider_error)
        )

        with self.assertRaises(TypeError) as context:
            extractor.extract("exact source")

        self.assertIs(context.exception, provider_error)

    def test_reasoning_preamble_output_is_still_rejected_by_parser(self) -> None:
        provider = StructuredJSONProvider(
            f"<think>The user likes Saturn.</think>{_VALID_PAYLOAD}"
        )
        extractor = LLMLearnedMemoryCandidateExtractor(provider)

        with self.assertRaises(LearnedMemoryCandidateExtractionError) as context:
            extractor.extract("exact source")

        self.assertIsInstance(context.exception.__cause__, ValueError)
        self.assertEqual(
            str(context.exception.__cause__),
            "Learned memory candidate payload invalid.",
        )

    def test_markdown_fenced_output_is_still_rejected_by_parser(self) -> None:
        provider = StructuredJSONProvider(f"```json\n{_VALID_PAYLOAD}\n```")
        extractor = LLMLearnedMemoryCandidateExtractor(provider)

        with self.assertRaises(LearnedMemoryCandidateExtractionError):
            extractor.extract("exact source")

    def test_schema_is_fresh_and_deterministic_per_call(self) -> None:
        first = build_learned_memory_candidate_response_schema()
        second = build_learned_memory_candidate_response_schema()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)

        first["candidates_mutated"] = True
        self.assertEqual(
            build_learned_memory_candidate_response_schema(),
            second,
        )

    def test_schema_kinds_match_the_parser_allowed_kinds(self) -> None:
        schema = build_learned_memory_candidate_response_schema()
        properties = schema["properties"]
        assert isinstance(properties, dict)
        candidates = properties["candidates"]
        assert isinstance(candidates, dict)
        items = candidates["items"]
        assert isinstance(items, dict)
        item_properties = items["properties"]
        assert isinstance(item_properties, dict)
        kind = item_properties["kind"]
        assert isinstance(kind, dict)

        for allowed_kind in kind["enum"]:
            batch = parse_learned_memory_candidate_batch(
                source_text="source",
                payload=(
                    '{"candidates":[{"kind":"'
                    + str(allowed_kind)
                    + '","key":"k","value":"v"}]}'
                ),
            )
            self.assertEqual(batch.candidates[0].memory.kind, allowed_kind)


if __name__ == "__main__":
    unittest.main()
