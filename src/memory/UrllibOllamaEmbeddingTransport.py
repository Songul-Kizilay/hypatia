"""Stdlib HTTP transport for one Ollama embedding request."""

from __future__ import annotations

import json
from math import isfinite
from typing import cast
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SECONDS = 120.0


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
        with urlopen(request, timeout=self._timeout_seconds) as response:
            return cast(object, json.loads(response.read()))
