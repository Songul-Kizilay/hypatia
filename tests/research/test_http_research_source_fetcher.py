"""Tests for bounded HTTP research-source acquisition."""

from __future__ import annotations

import unittest
from http.client import HTTPMessage
from io import BytesIO
from urllib.error import URLError
from urllib.request import Request

from core.Exceptions import ResearchError
from research.HttpResearchSourceFetcher import (
    RESEARCH_USER_AGENT,
    HttpResearchSourceFetcher,
    _ValidatedRedirectHandler,
)
from research.PublicHttpsUrlValidator import PublicHttpsUrlValidator


class FakeResponse:
    def __init__(
        self,
        *,
        url: str = "https://example.com/research",
        payload: bytes = b"<title>Example</title><main><p>Evidence.</p></main>",
        content_type: str = "text/html; charset=utf-8",
        include_content_type: bool = True,
    ) -> None:
        self._url = url
        self._payload = payload
        self.headers = HTTPMessage()
        if include_content_type:
            self.headers["Content-Type"] = content_type
        self.read_limits: list[int] = []

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def geturl(self) -> str:
        return self._url

    def read(self, amt: int = -1) -> bytes:
        self.read_limits.append(amt)
        return self._payload[:amt]


class FakeOpener:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self._response = response
        self.calls: list[tuple[Request, float]] = []

    def open(
        self,
        fullurl: Request,
        data: bytes | None = None,
        timeout: float = 0.0,
    ) -> FakeResponse:
        del data
        self.calls.append((fullurl, timeout))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class HttpResearchSourceFetcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = PublicHttpsUrlValidator(lambda _host: ("93.184.216.34",))
        self.fetcher = HttpResearchSourceFetcher(
            validator=self.validator,
            timeout_seconds=3.0,
            maximum_bytes=64,
        )

    def test_fetches_html_with_traceable_final_url_and_bounded_read(self) -> None:
        response = FakeResponse()
        opener = FakeOpener(response)
        fetcher = HttpResearchSourceFetcher(
            validator=self.validator,
            timeout_seconds=3.0,
            maximum_bytes=64,
            opener=opener,
        )

        source = fetcher.fetch("https://EXAMPLE.com/research#fragment")

        self.assertEqual(source.url, "https://example.com/research")
        self.assertEqual(source.title, "Example")
        self.assertEqual(source.content, "Evidence.")
        self.assertEqual(source.content_type, "text/html")
        self.assertEqual(response.read_limits, [65])
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, "https://example.com/research")
        self.assertEqual(timeout, 3.0)
        self.assertEqual(request.get_header("User-agent"), RESEARCH_USER_AGENT)

    def test_rejects_unsupported_content_type_before_reading(self) -> None:
        response = FakeResponse(content_type="application/pdf")
        fetcher = HttpResearchSourceFetcher(
            validator=self.validator,
            maximum_bytes=64,
            opener=FakeOpener(response),
        )

        with self.assertRaisesRegex(ResearchError, "Unsupported.*application/pdf"):
            fetcher.fetch("https://example.com/report.pdf")

        self.assertEqual(response.read_limits, [])

    def test_rejects_a_missing_content_type_before_reading(self) -> None:
        response = FakeResponse(include_content_type=False)
        fetcher = HttpResearchSourceFetcher(
            validator=self.validator,
            opener=FakeOpener(response),
        )

        with self.assertRaisesRegex(ResearchError, "must declare"):
            fetcher.fetch("https://example.com/no-type")

        self.assertEqual(response.read_limits, [])

    def test_rejects_a_response_larger_than_the_configured_limit(self) -> None:
        response = FakeResponse(payload=b"x" * 65, content_type="text/plain")
        fetcher = HttpResearchSourceFetcher(
            validator=self.validator,
            maximum_bytes=64,
            opener=FakeOpener(response),
        )

        with self.assertRaisesRegex(ResearchError, "maximum size"):
            fetcher.fetch("https://example.com/large.txt")

    def test_converts_transport_failures_to_a_controlled_research_error(self) -> None:
        fetcher = HttpResearchSourceFetcher(
            validator=self.validator,
            opener=FakeOpener(URLError("offline")),
        )

        with self.assertRaisesRegex(ResearchError, "could not be fetched"):
            fetcher.fetch("https://example.com/research")

    def test_redirect_handler_validates_destination_before_following_it(self) -> None:
        handler = _ValidatedRedirectHandler(
            PublicHttpsUrlValidator(lambda _host: ("127.0.0.1",))
        )

        with self.assertRaisesRegex(ResearchError, "public internet addresses"):
            handler.redirect_request(
                Request("https://example.com/start"),
                BytesIO(),
                302,
                "Found",
                HTTPMessage(),
                "https://internal.example/private",
            )


if __name__ == "__main__":
    unittest.main()
