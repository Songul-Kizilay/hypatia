"""Network-safety policy for optional authenticated LLM endpoints."""

from __future__ import annotations

from urllib.parse import urlparse

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def is_loopback_llm_endpoint(base_url: str) -> bool:
    """Return whether a URL explicitly targets the local machine.

    Callers must still validate the URL with ``validate_llm_endpoint`` before
    using it as a network destination.
    """
    return urlparse(base_url).hostname in _LOOPBACK_HOSTS


def validate_llm_endpoint(base_url: str) -> str:
    """Return a safe OpenAI-compatible endpoint or raise ``ValueError``.

    An enabled remote provider receives the user's API key in an Authorization
    header. Remote endpoints must therefore use HTTPS. Plain HTTP remains
    available only for explicitly local runtimes such as Ollama.
    """
    if not isinstance(base_url, str) or not base_url or base_url != base_url.strip():
        raise ValueError("LLM base URL must be a non-empty HTTP(S) URL.")

    try:
        endpoint = urlparse(base_url)
        port = endpoint.port
    except ValueError as error:
        raise ValueError("LLM base URL must be a valid HTTP(S) URL.") from error

    if endpoint.username is not None or endpoint.password is not None:
        raise ValueError("LLM base URL must not include credentials.")
    if endpoint.scheme not in {"http", "https"} or endpoint.hostname is None:
        raise ValueError("LLM base URL must be a valid HTTP(S) URL.")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("LLM base URL must be a valid HTTP(S) URL.")
    if endpoint.scheme == "http" and not is_loopback_llm_endpoint(base_url):
        raise ValueError(
            "LLM base URL must use HTTPS unless it targets localhost, "
            "127.0.0.1, or ::1."
        )

    return base_url
