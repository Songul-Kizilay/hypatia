"""Stdlib HTTP transport for OpenAI-compatible chat completions."""

from __future__ import annotations

import json
from typing import cast
from urllib.request import Request, urlopen

from llm.OpenAICompatibleProvider import ChatCompletionResponse

DEFAULT_TIMEOUT_SECONDS = 30.0


class UrllibChatCompletionTransport:
    """Send one JSON chat-completion request through urllib."""

    def __call__(
        self,
        base_url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> ChatCompletionResponse:
        request = Request(
            base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            return cast(ChatCompletionResponse, json.loads(response.read()))
