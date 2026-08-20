"""Offline contract tests for bounded Crossref metadata discovery."""

from __future__ import annotations

import json
import unittest
from http.client import HTTPMessage
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

from core.Exceptions import ResearchError
from research.CrossrefResearchSourceDiscoveryProvider import (
    CROSSREF_USER_AGENT,
    CrossrefResearchSourceDiscoveryProvider,
    _CrossrefRedirectHandler,
)
from research.PinnedHttpsTransport import PinnedHttpsHandler
from research.PublicHttpsUrlValidator import PublicHttpsUrlValidator


class FakeCrossrefResponse:
    def __init__(
        self,
        *,
        payload: bytes,
        url: str = "https://api.crossref.org/v1/works?rows=2",
        content_type: str = "application/json; charset=utf-8",
    ) -> None:
        self._payload = payload
        self._url = url
        self.headers = HTTPMessage()
        self.headers["Content-Type"] = content_type
        self.read_limits: list[int] = []

    def __enter__(self) -> FakeCrossrefResponse:
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def geturl(self) -> str:
        return self._url

    def read(self, amt: int = -1) -> bytes:
        self.read_limits.append(amt)
        return self._payload[:amt]


class FakeCrossrefOpener:
    def __init__(self, response: FakeCrossrefResponse | Exception) -> None:
        self._response = response
        self.calls: list[tuple[Request, float]] = []

    def open(
        self,
        fullurl: Request,
        data: bytes | None = None,
        timeout: float = 0.0,
    ) -> FakeCrossrefResponse:
        del data
        self.calls.append((fullurl, timeout))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _payload(items: list[object], *, status: str = "ok") -> bytes:
    return json.dumps({"status": status, "message": {"items": items}}).encode()


class CrossrefResearchSourceDiscoveryProviderTests(unittest.TestCase):
    def test_discovers_ordered_bounded_doi_metadata_without_source_fetching(
        self,
    ) -> None:
        response = FakeCrossrefResponse(
            payload=_payload(
                [
                    {
                        "DOI": "10.1000/first paper",
                        "title": ["  First\nresearch paper  "],
                        "container-title": ["Journal of Local AI"],
                        "published": {"date-parts": [[2025, 7]]},
                    },
                    {
                        "DOI": "10.1000/second",
                        "title": ["Second paper"],
                        "container-title": [],
                        "published": {"date-parts": [[2024]]},
                    },
                ]
            )
        )
        opener = FakeCrossrefOpener(response)
        provider = CrossrefResearchSourceDiscoveryProvider(
            timeout_seconds=3.5,
            maximum_bytes=4_096,
            opener=opener,
        )

        candidates = provider.discover("  local AI safety  ", limit=2)

        self.assertEqual(provider.provider_name, "crossref-rest-v1")
        self.assertEqual(
            [candidate.url for candidate in candidates],
            [
                "https://doi.org/10.1000/first%20paper",
                "https://doi.org/10.1000/second",
            ],
        )
        self.assertEqual(candidates[0].title, "First research paper")
        self.assertEqual(candidates[0].snippet, "Journal of Local AI · 2025")
        self.assertEqual(candidates[1].snippet, "2024")
        self.assertEqual(response.read_limits, [4_097])
        request, timeout = opener.calls[0]
        self.assertEqual(timeout, 3.5)
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(request.get_header("User-agent"), CROSSREF_USER_AGENT)
        parsed_request = urlparse(request.full_url)
        self.assertEqual(parsed_request.scheme, "https")
        self.assertEqual(parsed_request.hostname, "api.crossref.org")
        self.assertEqual(parsed_request.path, "/v1/works")
        self.assertEqual(
            parse_qs(parsed_request.query),
            {
                "query.bibliographic": ["local AI safety"],
                "rows": ["2"],
                "select": ["DOI,title,container-title,published"],
            },
        )

    def test_skips_incomplete_invalid_and_duplicate_items(self) -> None:
        response = FakeCrossrefResponse(
            payload=_payload(
                [
                    None,
                    {"DOI": "", "title": ["Missing DOI"]},
                    {"DOI": "10.1000/valid", "title": []},
                    {"DOI": "10.1000/valid", "title": ["Valid paper"]},
                    {"DOI": "10.1000/valid", "title": ["Duplicate paper"]},
                ]
            )
        )
        provider = CrossrefResearchSourceDiscoveryProvider(
            opener=FakeCrossrefOpener(response)
        )

        candidates = provider.discover("query", limit=5)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, "Valid paper")

    def test_bounds_provider_generated_title_and_snippet(self) -> None:
        response = FakeCrossrefResponse(
            payload=_payload(
                [
                    {
                        "DOI": "10.1000/bounded",
                        "title": ["T" * 700],
                        "container-title": ["J" * 1_200],
                        "published": {"date-parts": [[2026]]},
                    }
                ]
            )
        )
        provider = CrossrefResearchSourceDiscoveryProvider(
            opener=FakeCrossrefOpener(response)
        )

        candidate = provider.discover("query", limit=1)[0]

        self.assertEqual(len(candidate.title), 500)
        self.assertLessEqual(len(candidate.snippet), 1_000)

    def test_rejects_empty_queries_and_out_of_contract_limits_pre_network(self) -> None:
        opener = FakeCrossrefOpener(URLError("must not run"))
        provider = CrossrefResearchSourceDiscoveryProvider(opener=opener)

        for query in ("", " \t "):
            with self.subTest(query=query):
                with self.assertRaisesRegex(ResearchError, "query cannot be empty"):
                    provider.discover(query, limit=1)
        with self.assertRaisesRegex(ResearchError, "query is too long"):
            provider.discover("q" * 2_001, limit=1)
        for limit in (0, 6, True):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(ResearchError, "between 1 and 5"):
                    provider.discover("query", limit=limit)

        self.assertEqual(opener.calls, [])

    def test_rejects_unbounded_transport_and_payload_failures_safely(self) -> None:
        cases: list[tuple[FakeCrossrefResponse | Exception, str]] = [
            (URLError("secret transport detail"), "source discovery failed"),
            (
                FakeCrossrefResponse(
                    payload=b"{}",
                    content_type="text/html",
                ),
                "unsupported content type",
            ),
            (FakeCrossrefResponse(payload=b"x" * 65), "response is too large"),
            (FakeCrossrefResponse(payload=b"not-json"), "response is invalid"),
            (FakeCrossrefResponse(payload=_payload([], status="error")), "invalid"),
        ]
        for response, expected in cases:
            with self.subTest(expected=expected):
                provider = CrossrefResearchSourceDiscoveryProvider(
                    maximum_bytes=64,
                    opener=FakeCrossrefOpener(response),
                )
                with self.assertRaisesRegex(ResearchError, expected):
                    provider.discover("query", limit=1)

    def test_rejects_cross_origin_or_wrong_path_final_urls_and_redirects(self) -> None:
        for invalid_url in (
            "https://example.com/v1/works",
            "https://api.crossref.org/v1/worksevil",
        ):
            with self.subTest(invalid_url=invalid_url):
                provider = CrossrefResearchSourceDiscoveryProvider(
                    opener=FakeCrossrefOpener(
                        FakeCrossrefResponse(
                            payload=_payload([]),
                            url=invalid_url,
                        )
                    )
                )
                with self.assertRaisesRegex(ResearchError, "response URL is invalid"):
                    provider.discover("query", limit=1)

        handler = _CrossrefRedirectHandler()
        with self.assertRaisesRegex(ResearchError, "response URL is invalid"):
            handler.redirect_request(
                Request("https://api.crossref.org/v1/works"),
                BytesIO(),
                302,
                "Found",
                HTTPMessage(),
                "https://example.com/redirect",
            )

    def test_constructor_rejects_invalid_transport_bounds(self) -> None:
        for timeout in (0.0, -1.0, float("nan"), True):
            with self.subTest(timeout=timeout):
                with self.assertRaisesRegex(ValueError, "timeout must be positive"):
                    CrossrefResearchSourceDiscoveryProvider(timeout_seconds=timeout)
        for maximum_bytes in (0, -1, True, 1.5):
            with self.subTest(maximum_bytes=maximum_bytes):
                with self.assertRaisesRegex(
                    ValueError, "maximum bytes must be positive"
                ):
                    CrossrefResearchSourceDiscoveryProvider(
                        maximum_bytes=maximum_bytes  # type: ignore[arg-type]
                    )

    def test_crossref_destination_is_public_validated_for_connection_pinning(
        self,
    ) -> None:
        resolved_hosts: list[str] = []

        def resolve(hostname: str) -> tuple[str, ...]:
            resolved_hosts.append(hostname)
            return ("93.184.216.34",)

        provider = CrossrefResearchSourceDiscoveryProvider(
            validator=PublicHttpsUrlValidator(resolve)
        )

        destination = provider._validate_and_resolve_destination(
            "https://api.crossref.org/v1/works?rows=1"
        )

        self.assertEqual(resolved_hosts, ["api.crossref.org"])
        self.assertEqual(destination.hostname, "api.crossref.org")
        self.assertEqual(destination.addresses, ("93.184.216.34",))

    def test_crossref_pinning_rejects_private_dns_and_wrong_origin(self) -> None:
        provider = CrossrefResearchSourceDiscoveryProvider(
            validator=PublicHttpsUrlValidator(lambda _host: ("127.0.0.1",))
        )

        with self.assertRaisesRegex(ResearchError, "public internet addresses"):
            provider._validate_and_resolve_destination(
                "https://api.crossref.org/v1/works?rows=1"
            )
        with self.assertRaisesRegex(ResearchError, "response URL is invalid"):
            provider._validate_and_resolve_destination(
                "https://example.com/v1/works?rows=1"
            )

    def test_default_crossref_opener_installs_the_pinned_https_handler(self) -> None:
        validator = PublicHttpsUrlValidator(lambda _host: ("93.184.216.34",))
        fake_opener = FakeCrossrefOpener(URLError("offline"))

        with patch(
            "research.CrossrefResearchSourceDiscoveryProvider.build_opener",
            return_value=fake_opener,
        ) as build_opener:
            CrossrefResearchSourceDiscoveryProvider(validator=validator)

        handlers = build_opener.call_args.args
        pinned_handler = next(
            handler for handler in handlers if isinstance(handler, PinnedHttpsHandler)
        )
        with patch.object(pinned_handler, "do_open") as do_open:
            pinned_handler.https_open(
                Request("https://api.crossref.org/v1/works?rows=1")
            )

        connection_factory, request = do_open.call_args.args
        connection = connection_factory(request.host, timeout=3.0)
        self.assertEqual(connection.pinned_address, "93.184.216.34")


if __name__ == "__main__":
    unittest.main()
