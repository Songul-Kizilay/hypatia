"""Bounded scholarly-metadata discovery through the public Crossref REST API."""

from __future__ import annotations

import json
import re
from http.client import HTTPMessage
from math import isfinite
from typing import IO, Any, Protocol, Self, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from core.Exceptions import ResearchError
from core.Version import VERSION
from research.ResearchSourceCandidate import ResearchSourceCandidate

CROSSREF_API_ORIGIN = "https://api.crossref.org"
CROSSREF_WORKS_ENDPOINT = f"{CROSSREF_API_ORIGIN}/v1/works"
CROSSREF_PROVIDER_NAME = "crossref-rest-v1"
CROSSREF_USER_AGENT = f"Hypatia/{VERSION.short} research-source-discovery"
_CROSSREF_HOST = "api.crossref.org"
_DEFAULT_TIMEOUT_SECONDS = 10.0
_DEFAULT_MAXIMUM_BYTES = 500_000
_MAXIMUM_LIMIT = 5


class CrossrefHttpResponse(Protocol):
    """Minimal urllib response surface used by the discovery provider."""

    headers: HTTPMessage

    def geturl(self) -> str:
        """Return the final response URL."""

    def read(self, amt: int = -1) -> bytes:
        """Read at most the requested number of response bytes."""

    def __enter__(self) -> Self:
        """Enter the response context."""

    def __exit__(self, *args: object) -> None:
        """Close the response context."""


class CrossrefHttpOpener(Protocol):
    """Injectable transport surface that keeps provider tests offline."""

    def open(
        self,
        fullurl: Request,
        data: bytes | None = None,
        timeout: float = ...,
    ) -> CrossrefHttpResponse:
        """Open one request to the fixed Crossref endpoint."""


class _CrossrefRedirectHandler(HTTPRedirectHandler):
    """Permit redirects only within the fixed HTTPS Crossref API origin."""

    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        _validate_crossref_response_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class CrossrefResearchSourceDiscoveryProvider:
    """Return unaccepted DOI metadata without downloading source documents."""

    provider_name = CROSSREF_PROVIDER_NAME

    def __init__(
        self,
        *,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        maximum_bytes: int = _DEFAULT_MAXIMUM_BYTES,
        opener: CrossrefHttpOpener | None = None,
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("Crossref discovery timeout must be positive.")
        if (
            isinstance(maximum_bytes, bool)
            or not isinstance(maximum_bytes, int)
            or maximum_bytes <= 0
        ):
            raise ValueError("Crossref discovery maximum bytes must be positive.")
        self._timeout_seconds = timeout_seconds
        self._maximum_bytes = maximum_bytes
        self._opener = opener or cast(
            CrossrefHttpOpener,
            build_opener(ProxyHandler({}), _CrossrefRedirectHandler()),
        )

    def discover(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[ResearchSourceCandidate]:
        """Query bounded bibliographic metadata and return ordered DOI candidates."""
        normalized_query = query.strip() if isinstance(query, str) else ""
        if not normalized_query:
            raise ResearchError("Crossref discovery query cannot be empty.")
        if len(normalized_query) > 2_000:
            raise ResearchError("Crossref discovery query is too long.")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > _MAXIMUM_LIMIT
        ):
            raise ResearchError("Crossref discovery limit must be between 1 and 5.")

        encoded_parameters = urlencode(self._parameters(normalized_query, limit))
        request_url = f"{CROSSREF_WORKS_ENDPOINT}?{encoded_parameters}"
        request = Request(
            request_url,
            headers={
                "Accept": "application/json",
                "User-Agent": CROSSREF_USER_AGENT,
            },
        )
        try:
            with self._opener.open(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                _validate_crossref_response_url(response.geturl())
                content_type = response.headers.get_content_type().casefold()
                if content_type != "application/json":
                    raise ResearchError(
                        "Crossref discovery returned an unsupported content type."
                    )
                payload = response.read(self._maximum_bytes + 1)
                if len(payload) > self._maximum_bytes:
                    raise ResearchError("Crossref discovery response is too large.")
        except ResearchError:
            raise
        except (HTTPError, URLError, OSError) as error:
            raise ResearchError("Crossref source discovery failed.") from error

        return self._parse_candidates(payload, limit)

    @staticmethod
    def _parameters(query: str, limit: int) -> dict[str, str]:
        return {
            "query.bibliographic": query,
            "rows": str(limit),
            "select": "DOI,title,container-title,published",
        }

    @staticmethod
    def _parse_candidates(
        payload: bytes,
        limit: int,
    ) -> list[ResearchSourceCandidate]:
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ResearchError("Crossref discovery response is invalid.") from error
        if not isinstance(decoded, dict) or decoded.get("status") != "ok":
            raise ResearchError("Crossref discovery response is invalid.")
        message = decoded.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("items"), list):
            raise ResearchError("Crossref discovery response is invalid.")

        candidates: list[ResearchSourceCandidate] = []
        seen_urls: set[str] = set()
        for item in message["items"]:
            candidate = _candidate_from_item(item)
            if candidate is None or candidate.url in seen_urls:
                continue
            seen_urls.add(candidate.url)
            candidates.append(candidate)
            if len(candidates) == limit:
                break
        return candidates


def _validate_crossref_response_url(url: str) -> None:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as error:
        raise ResearchError("Crossref discovery response URL is invalid.") from error
    if (
        parsed.scheme.casefold() != "https"
        or parsed.hostname != _CROSSREF_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.path != "/v1/works"
    ):
        raise ResearchError("Crossref discovery response URL is invalid.")


def _candidate_from_item(value: Any) -> ResearchSourceCandidate | None:
    if not isinstance(value, dict):
        return None
    doi = value.get("DOI")
    titles = value.get("title")
    if (
        not isinstance(doi, str)
        or not doi.strip()
        or len(doi.strip()) > 255
        or not isinstance(titles, list)
        or not titles
        or not isinstance(titles[0], str)
        or not titles[0].strip()
    ):
        return None
    title = _normalized_bounded_text(titles[0], 500)
    if not title:
        return None
    url = f"https://doi.org/{quote(doi.strip(), safe='/():._-;')}"
    snippet = _bibliographic_snippet(value)
    try:
        return ResearchSourceCandidate(url=url, title=title, snippet=snippet)
    except ResearchError:
        return None


def _bibliographic_snippet(value: dict[str, Any]) -> str:
    parts: list[str] = []
    containers = value.get("container-title")
    if isinstance(containers, list) and containers and isinstance(containers[0], str):
        container = _normalized_bounded_text(containers[0], 700)
        if container:
            parts.append(container)
    year = _published_year(value.get("published"))
    if year is not None:
        parts.append(str(year))
    return _normalized_bounded_text(" · ".join(parts), 1_000)


def _published_year(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    date_parts = value.get("date-parts")
    if (
        not isinstance(date_parts, list)
        or not date_parts
        or not isinstance(date_parts[0], list)
        or not date_parts[0]
    ):
        return None
    year = date_parts[0][0]
    if isinstance(year, bool) or not isinstance(year, int) or not 1000 <= year <= 9999:
        return None
    return year


def _normalized_bounded_text(value: str, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized[:limit].rstrip()
