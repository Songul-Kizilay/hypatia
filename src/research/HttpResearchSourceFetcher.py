"""Bounded HTTPS acquisition for one explicitly selected research source."""

from __future__ import annotations

from datetime import UTC, datetime
from http.client import HTTPMessage
from typing import IO, Protocol, Self, cast
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from core.Exceptions import ResearchError
from core.Version import VERSION
from research.PublicHttpsUrlValidator import PublicHttpsUrlValidator
from research.ResearchHtmlExtractor import ResearchHtmlExtractor
from research.ResearchSource import ResearchSource

_ALLOWED_CONTENT_TYPES = {
    "application/xhtml+xml",
    "text/html",
    "text/markdown",
    "text/plain",
}
RESEARCH_USER_AGENT = f"Hypatia/{VERSION.short} research-source-fetcher"


class ResearchHttpResponse(Protocol):
    """Minimal urllib response surface needed by the bounded fetcher."""

    headers: HTTPMessage

    def geturl(self) -> str:
        """Return the final response URL."""

    def read(self, amt: int = -1) -> bytes:
        """Read at most the requested response bytes."""

    def __enter__(self) -> Self:
        """Enter the response context."""

    def __exit__(self, *args: object) -> None:
        """Close the response context."""


class ResearchHttpOpener(Protocol):
    """Injectable opener surface that keeps transport tests offline."""

    def open(
        self,
        fullurl: Request,
        data: bytes | None = None,
        timeout: float = ...,
    ) -> ResearchHttpResponse:
        """Open one already validated research request."""


class _ValidatedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, validator: PublicHttpsUrlValidator) -> None:
        super().__init__()
        self._validator = validator

    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        validated_url = self._validator.validate(newurl)
        return super().redirect_request(req, fp, code, msg, headers, validated_url)


class HttpResearchSourceFetcher:
    """Fetch public HTTPS text with redirect, type, and size boundaries."""

    def __init__(
        self,
        *,
        validator: PublicHttpsUrlValidator | None = None,
        timeout_seconds: float = 10.0,
        maximum_bytes: int = 1_000_000,
        opener: ResearchHttpOpener | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Research fetch timeout must be positive.")
        if isinstance(maximum_bytes, bool) or maximum_bytes <= 0:
            raise ValueError("Research fetch maximum bytes must be positive.")
        self._validator = validator or PublicHttpsUrlValidator()
        self._timeout_seconds = timeout_seconds
        self._maximum_bytes = maximum_bytes
        self._opener = opener or cast(
            ResearchHttpOpener,
            build_opener(
                ProxyHandler({}),
                _ValidatedRedirectHandler(self._validator),
            ),
        )

    def fetch(self, url: str) -> ResearchSource:
        """Fetch and extract one source after validating every requested URL."""
        normalized_url = self._validator.validate(url)
        request = Request(
            normalized_url,
            headers={
                "Accept": "text/html,text/plain,text/markdown,application/xhtml+xml",
                "User-Agent": RESEARCH_USER_AGENT,
            },
        )
        try:
            with self._opener.open(request, timeout=self._timeout_seconds) as response:
                final_url = self._validator.validate(response.geturl())
                if response.headers.get("Content-Type") is None:
                    raise ResearchError(
                        "Research source must declare a supported content type."
                    )
                content_type = response.headers.get_content_type().casefold()
                if content_type not in _ALLOWED_CONTENT_TYPES:
                    raise ResearchError(
                        f"Unsupported research source content type: {content_type}"
                    )
                payload = response.read(self._maximum_bytes + 1)
                if len(payload) > self._maximum_bytes:
                    raise ResearchError("Research source exceeds the maximum size.")
                charset = response.headers.get_content_charset() or "utf-8"
        except ResearchError:
            raise
        except (HTTPError, URLError, OSError) as error:
            raise ResearchError("Research source could not be fetched.") from error
        try:
            decoded = payload.decode(charset)
        except (LookupError, UnicodeDecodeError) as error:
            raise ResearchError(
                "Research source text encoding is unsupported."
            ) from error
        title, content = self._extract(decoded, content_type, final_url)
        return ResearchSource(
            url=final_url,
            title=title,
            content=content,
            content_type=content_type,
            fetched_at=datetime.now(UTC),
        )

    @staticmethod
    def _extract(
        payload: str, content_type: str, fallback_title: str
    ) -> tuple[str, str]:
        if content_type in {"text/html", "application/xhtml+xml"}:
            parser = ResearchHtmlExtractor()
            try:
                parser.feed(payload)
                parser.close()
            except (ValueError, AssertionError) as error:
                raise ResearchError(
                    "Research source HTML could not be parsed."
                ) from error
            title, content = parser.extracted()
            return title or fallback_title, content
        content = payload.strip()
        if not content:
            raise ResearchError("Research source did not contain readable text.")
        return fallback_title, content
