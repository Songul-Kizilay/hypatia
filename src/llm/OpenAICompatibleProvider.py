"""OpenAI-compatible provider adapter with an injected transport boundary."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

from llm.LLMConversationMessage import LLMConversationMessage
from llm.LLMProvider import LLMError

ChatCompletionResponse = object
ChatCompletionTransport = Callable[
    [str, dict[str, str], dict[str, object]],
    ChatCompletionResponse,
]


def _extract_content(response: object) -> str:
    try:
        choices = cast(dict[str, object], response)["choices"]
        first_choice = cast(list[object], choices)[0]
        message = cast(dict[str, object], first_choice)["message"]
        content = cast(dict[str, object], message)["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise LLMError("LLM response invalid.") from error
    if not isinstance(content, str):
        raise LLMError("LLM response invalid.")
    return content


class OpenAICompatibleProvider:
    """Generate text through an OpenAI-compatible injected transport."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        transport: ChatCompletionTransport,
        system_prompt: str | None = None,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key if api_key is not None and api_key.strip() else None
        self._model = model
        self._transport = transport
        self._system_prompt = system_prompt

    def generate(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
    ) -> str:
        """Generate a response from optional history and one user message."""
        messages: list[dict[str, str]] = []
        if self._system_prompt is not None:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.extend(
            {"role": message.role, "content": message.content} for message in history
        )
        messages.append({"role": "user", "content": prompt})
        headers = (
            {"Authorization": f"Bearer {self._api_key}"}
            if self._api_key is not None
            else {}
        )
        try:
            response = self._transport(
                self._base_url,
                headers,
                {
                    "model": self._model,
                    "messages": messages,
                },
            )
        except OSError as error:
            raise LLMError("LLM transport failed.") from error
        except json.JSONDecodeError as error:
            raise LLMError("LLM response invalid.") from error
        return _extract_content(response)
