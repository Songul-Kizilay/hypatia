from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from llm.LLMConversationMessage import LLMConversationMessage
from llm.LLMProvider import LLMError, LLMProvider


class DeterministicFakeLLMProvider:
    def __init__(self) -> None:
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
        return f"Generated: {prompt}"


def generate_response(provider: LLMProvider, prompt: str) -> str:
    return provider.generate(prompt)


class LLMProviderTests(unittest.TestCase):
    def test_llm_error_is_the_generation_domain_exception(self) -> None:
        error = LLMError("Generation unavailable.")

        self.assertIsInstance(error, Exception)
        self.assertEqual(str(error), "Generation unavailable.")

    def test_provider_is_usable_through_the_generation_contract(self) -> None:
        provider: LLMProvider = DeterministicFakeLLMProvider()

        response = generate_response(provider, "Describe Hypatia.")

        self.assertEqual(response, "Generated: Describe Hypatia.")

    def test_provider_contract_accepts_optional_conversation_history(self) -> None:
        provider = DeterministicFakeLLMProvider()
        history = (
            LLMConversationMessage(role="user", content="hello"),
            LLMConversationMessage(role="assistant", content="hi"),
        )

        single_turn_response = provider.generate("hello")
        history_response = provider.generate("follow up", history=history)

        self.assertEqual(single_turn_response, "Generated: hello")
        self.assertEqual(history_response, "Generated: follow up")
        self.assertEqual(
            provider.calls,
            [
                ("hello", ()),
                ("follow up", history),
            ],
        )
