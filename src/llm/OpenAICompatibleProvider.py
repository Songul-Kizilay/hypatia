"""OpenAI-compatible provider adapter with an injected transport boundary."""

from __future__ import annotations

import json
from collections.abc import Callable

from llm.LLMProvider import LLMError

ChatCompletionResponse = dict[str, list[dict[str, dict[str, str]]]]
ChatCompletionTransport = Callable[
    [str, dict[str, str], dict[str, object]],
    ChatCompletionResponse,
]


class OpenAICompatibleProvider:
    """Generate text through an OpenAI-compatible injected transport."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        transport: ChatCompletionTransport,
        system_prompt: str | None = None,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._transport = transport
        self._system_prompt = system_prompt

    def generate(self, prompt: str) -> str:
        """Generate a response from one user message."""
        messages = [{"role": "user", "content": prompt}]
        if self._system_prompt is not None:
            messages.insert(0, {"role": "system", "content": self._system_prompt})
        try:
            response = self._transport(
                self._base_url,
                {"Authorization": f"Bearer {self._api_key}"},
                {
                    "model": self._model,
                    "messages": messages,
                },
            )
        except OSError as error:
            raise LLMError("LLM transport failed.") from error
        except json.JSONDecodeError as error:
            raise LLMError("LLM response invalid.") from error
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as error:
            raise LLMError("LLM response invalid.") from error
