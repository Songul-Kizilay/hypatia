"""Stdlib HTTP transport for one Ollama embedding request."""

from __future__ import annotations

import json
from email.message import Message
from math import isfinite
from types import TracebackType
from typing import Protocol, Self, cast
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_RESPONSE_BYTES = 1_048_576


class _ReadableResponse(Protocol):
    """Minimum response interface used by the transport."""

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def read(self, size: int = -1) -> bytes: ...


class _NoRedirectHandler(HTTPRedirectHandler):
    """Keep embedding traffic at the validated local Ollama endpoint."""

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
    """Open one embedding request without following endpoint redirects."""
    return cast(
        _ReadableResponse,
        build_opener(_NoRedirectHandler).open(request, timeout=timeout),
    )


def _read_response_body(response: _ReadableResponse) -> bytes:
    """Read one bounded embedding response before JSON parsing."""
    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise OSError("Embedding response exceeds the maximum allowed size.")
    return body


class UrllibOllamaEmbeddingTransport:
    """Send one JSON embedding request through urllib."""

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("Embedding transport timeout must be a positive number.")
        self._timeout_seconds = float(timeout_seconds)

    def __call__(self, endpoint: str, payload: dict[str, object]) -> object:
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _open_without_redirects(
            request,
            timeout=self._timeout_seconds,
        ) as response:
            return cast(object, json.loads(_read_response_body(response)))
