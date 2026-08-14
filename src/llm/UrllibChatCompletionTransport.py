"""Stdlib HTTP transport for OpenAI-compatible chat completions."""

from __future__ import annotations

import json
from email.message import Message
from math import isfinite
from types import TracebackType
from typing import Protocol, Self, cast
from urllib.request import HTTPRedirectHandler, Request, build_opener

from llm.OpenAICompatibleProvider import ChatCompletionResponse

DEFAULT_TIMEOUT_SECONDS = 30.0
LOCAL_DEFAULT_TIMEOUT_SECONDS = 120.0


class _ReadableResponse(Protocol):
    """Minimum response interface used by the transport."""

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def read(self) -> bytes: ...


class _NoRedirectHandler(HTTPRedirectHandler):
    """Reject redirects so bearer credentials never cross an endpoint boundary."""

    def redirect_request(
        self,
        request: Request,
        file_pointer: object,
        code: int,
        message: str,
        headers: Message,
        new_url: str,
    ) -> Request | None:
        return None


def _open_without_redirects(
    request: Request,
    *,
    timeout: float,
) -> _ReadableResponse:
    """Open one request without urllib's default redirect-following behavior."""
    return cast(
        _ReadableResponse,
        build_opener(_NoRedirectHandler).open(request, timeout=timeout),
    )


class UrllibChatCompletionTransport:
    """Send one JSON chat-completion request through urllib."""

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError(
                "Chat completion transport timeout must be a positive number."
            )
        self._timeout_seconds = float(timeout_seconds)

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
        with _open_without_redirects(
            request,
            timeout=self._timeout_seconds,
        ) as response:
            return cast(ChatCompletionResponse, json.loads(response.read()))
