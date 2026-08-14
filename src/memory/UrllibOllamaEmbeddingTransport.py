"""Stdlib HTTP transport for one Ollama embedding request."""

from __future__ import annotations

import json
from typing import cast
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SECONDS = 30.0


class UrllibOllamaEmbeddingTransport:
    """Send one JSON embedding request through urllib."""

    def __call__(self, endpoint: str, payload: dict[str, object]) -> object:
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            return cast(object, json.loads(response.read()))
