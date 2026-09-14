"""Bounded vulnerability discovery through the official NVD CVE API 2.0.

Everything built before this improved what happened *after* retrieval. This
changes what can be retrieved: a question naming a CVE now reaches the
vulnerability record itself instead of the scholarly papers that happen to share
its tokens. What it deliberately does not change is authority. One approved
discovery step performs one request to one fixed host and stops.

The endpoint is fixed in code. Not configurable, not supplied by a model, not
read out of a response, and not taken from an operator's free text — a discovery
provider whose destination can be influenced from outside is an SSRF primitive
with a research feature wrapped around it. The same pinned-transport, redirect
revalidation and address checks the Crossref provider uses are reused here
rather than reimplemented more loosely beside them.

Two routes, chosen by looking at the question rather than by asking anything.
A question containing exactly one well-formed CVE identifier is an exact lookup
through `cveId`; everything else is a bounded `keywordSearch`. An exact request
is never quietly degraded into a keyword search, because a person who typed a
CVE number wants that vulnerability and a near-miss list is worse than nothing.

One request. No pagination, no retry loop, no reference following. A query
matching ten thousand vulnerabilities still retrieves one bounded page, and a
rate-limit response is reported as a rate-limit response rather than slept
through — the operator advances the next attempt, so every request stays
something a person asked for and the budget stays honest.

Verified against the live API on 26 August 2026: the envelope carries `format`,
`version`, `timestamp`, `resultsPerPage`, `startIndex`, `totalResults` and
`vulnerabilities`; each item wraps one `cve` object with `id`, `descriptions`,
`published`, `lastModified`, `vulnStatus`, `sourceIdentifier`, `weaknesses`,
`metrics`, `references` and the four CISA fields. Results come back ordered by
publication date, not by relevance, which is why the provider's own order is
preserved as provenance and the ranking is done locally afterwards.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from http.client import HTTPMessage
from math import isfinite
from typing import IO, Any, Protocol, Self, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from core.Exceptions import ResearchError
from core.Version import VERSION
from research.NvdVulnerabilityDocument import NvdVulnerabilityDocument
from research.PinnedHttpsTransport import PinnedHttpsHandler
from research.PublicHttpsUrlValidator import (
    PublicHttpsUrlValidator,
    ValidatedPublicHttpsDestination,
)
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchQueryTerms import ResearchQueryTerms
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchVulnerabilityMetric import ResearchVulnerabilityMetric
from research.ResearchVulnerabilityRecord import (
    MAX_VULNERABILITY_METRICS,
    MAX_VULNERABILITY_REFERENCES,
    MAX_VULNERABILITY_WEAKNESSES,
    ResearchVulnerabilityRecord,
    is_cve_id,
)
from research.ResearchVulnerabilityReference import ResearchVulnerabilityReference

NVD_API_ORIGIN = "https://services.nvd.nist.gov"
NVD_CVE_ENDPOINT = f"{NVD_API_ORIGIN}/rest/json/cves/2.0"
NVD_PROVIDER_NAME = ResearchDiscoveryProviderName.NVD.value
NVD_USER_AGENT = f"Hypatia/{VERSION.short} research-source-discovery"

#: The official key header field. A header and never a query parameter: a key in
#: a URL is a key in a log, in a referrer, and in an error message.
NVD_API_KEY_HEADER = "apiKey"

#: Where a person can read the record a candidate points at. A stable public
#: detail page rather than the API endpoint, because the URL is what somebody
#: opens when they want to look.
NVD_DETAIL_PREFIX = "https://nvd.nist.gov/vuln/detail/"

#: NVD publishes 5 requests per rolling 30 seconds without a key and 50 with
#: one. Nothing here polls, retries, or paginates, so one operator-triggered
#: discovery costs exactly one request against that allowance.
NVD_PUBLIC_REQUESTS_PER_WINDOW = 5
NVD_KEYED_REQUESTS_PER_WINDOW = 50
NVD_RATE_WINDOW_SECONDS = 30

_NVD_HOST = "services.nvd.nist.gov"
_NVD_PATH = "/rest/json/cves/2.0"
_DEFAULT_TIMEOUT_SECONDS = 15.0
_DEFAULT_MAXIMUM_BYTES = 2_000_000
_MAXIMUM_LIMIT = 10
_RESEARCH_LANGUAGE = "en"
_MAX_DESCRIPTION_CHARACTERS = 1_000
_MAX_TITLE_CHARACTERS = 500
#: The keyword string NVD is asked to match. Long enough for a real question,
#: short enough that nothing unbounded reaches the query string.
_MAX_KEYWORD_CHARACTERS = 512


class NvdHttpResponse(Protocol):
    """Minimal urllib response surface used by the vulnerability provider."""

    headers: HTTPMessage

    def geturl(self) -> str:
        """Return the final response URL."""

    def read(self, amt: int = -1) -> bytes:
        """Read at most the requested number of response bytes."""

    def __enter__(self) -> Self:
        """Enter the response context."""

    def __exit__(self, *args: object) -> None:
        """Close the response context."""


class NvdHttpOpener(Protocol):
    """Injectable transport surface that keeps provider tests offline."""

    def open(
        self,
        fullurl: Request,
        data: bytes | None = None,
        timeout: float = ...,
    ) -> NvdHttpResponse:
        """Open one request to the fixed NVD endpoint."""


class _NvdRedirectHandler(HTTPRedirectHandler):
    """Permit redirects only within the fixed HTTPS NVD API origin."""

    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        _validate_nvd_response_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class NvdResearchSourceDiscoveryProvider:
    """Return unaccepted vulnerability metadata without fetching any reference."""

    provider_name = NVD_PROVIDER_NAME

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        maximum_bytes: int = _DEFAULT_MAXIMUM_BYTES,
        opener: NvdHttpOpener | None = None,
        validator: PublicHttpsUrlValidator | None = None,
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("NVD discovery timeout must be positive.")
        if (
            isinstance(maximum_bytes, bool)
            or not isinstance(maximum_bytes, int)
            or maximum_bytes <= 0
        ):
            raise ValueError("NVD discovery maximum bytes must be positive.")
        if api_key is not None and (
            not isinstance(api_key, str)
            or not api_key.strip()
            or not api_key.isprintable()
            or any(character.isspace() for character in api_key)
        ):
            raise ValueError("NVD API key is invalid.")
        self._api_key = api_key.strip() if api_key else None
        self._timeout_seconds = timeout_seconds
        self._maximum_bytes = maximum_bytes
        self._validator = validator or PublicHttpsUrlValidator()
        self._opener = opener or cast(
            NvdHttpOpener,
            build_opener(
                ProxyHandler({}),
                _NvdRedirectHandler(),
                PinnedHttpsHandler(self._validate_and_resolve_destination),
            ),
        )

    @property
    def has_api_key(self) -> bool:
        """Say whether a key is configured, without revealing anything about it."""
        return self._api_key is not None

    def _validate_and_resolve_destination(
        self,
        url: str,
    ) -> ValidatedPublicHttpsDestination:
        _validate_nvd_response_url(url)
        destination = self._validator.validate_and_resolve(url)
        _validate_nvd_response_url(destination.url)
        return destination

    def discover(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[ResearchSourceCandidate]:
        """Query bounded vulnerability metadata and return ordered candidates."""
        normalized_query = query.strip() if isinstance(query, str) else ""
        if not normalized_query:
            raise ResearchError("NVD discovery query cannot be empty.")
        if len(normalized_query) > 2_000:
            raise ResearchError("NVD discovery query is too long.")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
            or limit > _MAXIMUM_LIMIT
        ):
            raise ResearchError("NVD discovery limit must be between 1 and 10.")

        payload = self._payload_for(self._parameters(normalized_query, limit))
        return _parse_candidates(payload, limit)

    def materialize(self, cve_id: str) -> NvdVulnerabilityDocument:
        """Retrieve one accepted CVE in full, for reading rather than for a list.

        Deliberately a second request rather than a reuse of what discovery
        already holds. The candidate projection drops everything past the first
        thousand characters of the description and keeps only the publication
        year, because that is what a ranked list needs; a source a person cites
        needs the description NVD published and the date it published it. Asking
        again is the honest way to have them, and the request is one ordinary
        network operation that the caller accounts for as such.

        The exact-lookup route only. A keyword search could return a different
        vulnerability, and a source materialized from a near miss would be
        attached under the identifier of one the operator never accepted.
        """
        if not is_cve_id(cve_id):
            raise ResearchError("An NVD lookup needs a valid CVE ID.")
        payload = self._payload_for(
            {"cveId": cve_id, "resultsPerPage": "1", "startIndex": "0"}
        )
        return _parse_vulnerability_document(payload, cve_id)

    def _payload_for(self, parameters: dict[str, str]) -> bytes:
        """Perform exactly one bounded request to the fixed NVD endpoint."""
        request = Request(
            f"{NVD_CVE_ENDPOINT}?{urlencode(parameters)}",
            headers=self._headers(),
        )
        try:
            with self._opener.open(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                _validate_nvd_response_url(response.geturl())
                content_type = response.headers.get_content_type().casefold()
                if content_type != "application/json":
                    raise ResearchError(
                        "NVD discovery returned an unsupported content type."
                    )
                payload = response.read(self._maximum_bytes + 1)
                if len(payload) > self._maximum_bytes:
                    raise ResearchError("NVD discovery response is too large.")
        except ResearchError:
            raise
        except HTTPError as error:
            raise _refusal(error) from error
        except (URLError, OSError) as error:
            raise ResearchError("NVD source discovery failed.") from error
        return payload

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": NVD_USER_AGENT}
        if self._api_key is not None:
            headers[NVD_API_KEY_HEADER] = self._api_key
        return headers

    @staticmethod
    def _parameters(query: str, limit: int) -> dict[str, str]:
        """Route to an exact lookup or a bounded keyword search, and never both.

        A question naming exactly one CVE is that CVE. Two of them are ambiguous
        and one malformed one is a typo, and both fall through to keyword search
        rather than being guessed at, because researching a vulnerability
        somebody did not ask about is worse than returning a weaker list.
        """
        parameters = {"resultsPerPage": str(limit), "startIndex": "0"}
        exact = _exact_cve_id(query)
        if exact is not None:
            parameters["cveId"] = exact
            return parameters
        parameters["keywordSearch"] = _keyword_query(query)
        return parameters


def _exact_cve_id(query: str) -> str | None:
    """Return the one CVE this question names, or nothing at all."""
    identifiers = {
        token.upper()
        for raw in query.split()
        # Sentence punctuation only. Nothing inside an identifier is touched,
        # because `CVE-2025-29927?` is a question about a vulnerability and
        # `CVE-2025-29927` is that vulnerability.
        if is_cve_id(token := raw.strip(".,;:!?()[]{}<>\"'").upper())
    }
    return identifiers.pop() if len(identifiers) == 1 else None


def _keyword_query(query: str) -> str:
    """Return the bounded keyword string, with identifiers left intact.

    The same shallow normalisation the relevance ranker uses: function words
    removed, everything else left exactly as written. `Next.js`, `ASP.NET` and
    `HTTP/2` reach NVD as themselves, because splitting them is how a search for
    a framework becomes a search for the word `next`.
    """
    try:
        terms = ResearchQueryTerms.of(query)
    except ResearchError:
        return query.strip()[:_MAX_KEYWORD_CHARACTERS]
    keyword = " ".join(terms.terms)
    return (keyword or query.strip())[:_MAX_KEYWORD_CHARACTERS]


def _refusal(error: HTTPError) -> ResearchError:
    """Classify a provider rejection without echoing its body back to anyone.

    NVD answers an exceeded allowance with a refusal rather than a wait, so this
    reports one. Nothing sleeps and retries: a second request inside one advance
    would be a network operation the approved budget never accounted for, and an
    operator who can see `rate limited` can decide to try again themselves.
    """
    if error.code in (403, 429):
        return ResearchError(
            "NVD refused the request, which is how it reports an exceeded rate "
            "limit. Nothing was retried."
        )
    if error.code == 404:
        return ResearchError("NVD has no record matching this request.")
    return ResearchError(f"NVD source discovery failed with status {error.code}.")


def _validate_nvd_response_url(url: str) -> None:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as error:
        raise ResearchError("NVD discovery response URL is invalid.") from error
    if (
        parsed.scheme.casefold() != "https"
        or parsed.hostname != _NVD_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.path != _NVD_PATH
    ):
        raise ResearchError("NVD discovery response URL is invalid.")


def _parse_candidates(payload: bytes, limit: int) -> list[ResearchSourceCandidate]:
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ResearchError("NVD discovery response is invalid.") from error
    if not isinstance(decoded, dict) or not isinstance(
        decoded.get("vulnerabilities"), list
    ):
        raise ResearchError("NVD discovery response is invalid.")

    candidates: list[ResearchSourceCandidate] = []
    seen: set[str] = set()
    for item in decoded["vulnerabilities"]:
        candidate = _candidate_from_item(item)
        if candidate is None or candidate.url in seen:
            continue
        seen.add(candidate.url)
        candidates.append(candidate)
        if len(candidates) == limit:
            break
    return candidates


def _parse_vulnerability_document(
    payload: bytes,
    expected_cve_id: str,
) -> NvdVulnerabilityDocument:
    """Return the one requested CVE, or refuse — never the nearest thing to it.

    Where discovery skips an unreadable entry so the other nine stay usable,
    ingestion cannot: there is one record here and it is the one a person
    accepted. So each way this can go wrong is refused separately and by name,
    because "missing" and "malformed" and "a different CVE" call for different
    things from whoever reads the failure.

    The identity check is the important one. An exact lookup that answers with
    another identifier means the request, the response, or the accepted
    candidate is not what it appears to be, and attaching that record under the
    accepted CVE's identity would file one vulnerability's facts under another's
    name. There is no repair for that worth attempting, so it fails closed.
    """
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ResearchError("NVD vulnerability response is invalid.") from error
    if not isinstance(decoded, dict) or not isinstance(
        decoded.get("vulnerabilities"), list
    ):
        raise ResearchError("NVD vulnerability response is invalid.")
    if not decoded["vulnerabilities"]:
        raise ResearchError(f"NVD holds no record for {expected_cve_id}.")

    item = decoded["vulnerabilities"][0]
    if not isinstance(item, dict) or not isinstance(item.get("cve"), dict):
        raise ResearchError("NVD vulnerability record is malformed.")
    cve = item["cve"]
    if not is_cve_id(cve.get("id")):
        raise ResearchError("NVD vulnerability record is malformed.")
    if cve["id"] != expected_cve_id:
        raise ResearchError(
            f"NVD returned {cve['id']} for {expected_cve_id}; nothing was attached."
        )
    try:
        record = _vulnerability_record(cve)
    except ResearchError as error:
        raise ResearchError("NVD vulnerability record is malformed.") from error
    return NvdVulnerabilityDocument(
        record=record,
        description=_english_description(cve.get("descriptions")),
        published=_timestamp(cve.get("published")),
        api_resource=NVD_CVE_ENDPOINT,
    )


def _vulnerability_record(cve: dict[str, Any]) -> ResearchVulnerabilityRecord:
    """Map one CVE object onto the structured record both routes share."""
    return ResearchVulnerabilityRecord(
        cve_id=cve["id"],
        status=_text(cve.get("vulnStatus")),
        source_identifier=_text(cve.get("sourceIdentifier")),
        last_modified=_timestamp(cve.get("lastModified")),
        weaknesses=_weaknesses(cve.get("weaknesses")),
        metrics=_metrics(cve.get("metrics")),
        references=_references(cve.get("references")),
        reference_total=(
            len(cve["references"]) if isinstance(cve.get("references"), list) else 0
        ),
        known_exploited_at=_text(cve.get("cisaExploitAdd")),
        known_exploited_name=_text(cve.get("cisaVulnerabilityName")),
    )


def _candidate_from_item(value: Any) -> ResearchSourceCandidate | None:
    """Map one vulnerability, or skip it when it is not one we can read.

    A malformed entry is skipped rather than failing the whole response. One
    unreadable record among ten should not hide the nine a person could have
    used, and the entry is not silently repaired either — it is simply absent.
    """
    if not isinstance(value, dict) or not isinstance(value.get("cve"), dict):
        return None
    cve = value["cve"]
    cve_id = cve.get("id")
    if not is_cve_id(cve_id):
        return None
    description = _english_description(cve.get("descriptions"))
    published = _timestamp(cve.get("published"))
    try:
        record = _vulnerability_record(cve)
        return ResearchSourceCandidate(
            url=f"{NVD_DETAIL_PREFIX}{cve_id}",
            title=_title(cve_id, description),
            snippet=description[:_MAX_DESCRIPTION_CHARACTERS],
            container=_text(cve.get("sourceIdentifier")),
            published_year=published.year if published is not None else None,
            vulnerability=record,
        )
    except ResearchError:
        return None


def _title(cve_id: str, description: str) -> str:
    """Return a readable label, without pretending NVD supplied a title.

    A CVE record has no title. Inventing something that reads like one would
    give a machine-assembled string the authority of a published heading, so the
    identifier leads and the description follows it as an excerpt.
    """
    if not description:
        return cve_id
    excerpt = description[: _MAX_TITLE_CHARACTERS - len(cve_id) - 3]
    return f"{cve_id}: {excerpt}".strip()[:_MAX_TITLE_CHARACTERS]


def _english_description(value: Any) -> str:
    """Return the English description, chosen by language code rather than order.

    NVD returns the same text in several languages and the first entry is not
    reliably English. Nothing is translated and nothing is substituted: a record
    with no English description has none.
    """
    if not isinstance(value, list):
        return ""
    for entry in value:
        if (
            isinstance(entry, dict)
            and entry.get("lang") == _RESEARCH_LANGUAGE
            and isinstance(entry.get("value"), str)
        ):
            return " ".join(entry["value"].split())
    return ""


def _weaknesses(value: Any) -> tuple[str, ...]:
    """Return the CWE identifiers actually present, inferring none from prose."""
    if not isinstance(value, list):
        return ()
    found: list[str] = []
    for weakness in value:
        if not isinstance(weakness, dict):
            continue
        for entry in weakness.get("description") or ():
            if not isinstance(entry, dict):
                continue
            identifier = entry.get("value")
            if (
                isinstance(identifier, str)
                and identifier.startswith("CWE-")
                and identifier not in found
            ):
                found.append(identifier[:40])
            if len(found) == MAX_VULNERABILITY_WEAKNESSES:
                return tuple(found)
    return tuple(found)


def _metrics(value: Any) -> tuple[ResearchVulnerabilityMetric, ...]:
    """Return every scored metric, attributed, choosing no favourite among them.

    Entries without a score are skipped rather than defaulted: the response
    carries non-CVSS assessments alongside the CVSS ones, and giving those an
    invented number would be the most persuasive possible kind of fabrication.
    """
    if not isinstance(value, dict):
        return ()
    metrics: list[ResearchVulnerabilityMetric] = []
    for key in sorted(value):
        entries = value[key]
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(
                entry.get("cvssData"), dict
            ):
                continue
            data = entry["cvssData"]
            version = data.get("version")
            score = data.get("baseScore")
            if not isinstance(version, str) or isinstance(score, bool):
                continue
            if not isinstance(score, (int, float)):
                continue
            severity = data.get("baseSeverity") or entry.get("baseSeverity") or ""
            try:
                metrics.append(
                    ResearchVulnerabilityMetric(
                        version=version,
                        source=_text(entry.get("source")),
                        score=float(score),
                        severity=_text(severity),
                    )
                )
            except ResearchError:
                continue
            if len(metrics) == MAX_VULNERABILITY_METRICS:
                return tuple(metrics)
    return tuple(metrics)


def _references(value: Any) -> tuple[ResearchVulnerabilityReference, ...]:
    """Return bounded reference metadata. Nothing here is fetched or followed."""
    if not isinstance(value, list):
        return ()
    references: list[ResearchVulnerabilityReference] = []
    for entry in value:
        if not isinstance(entry, dict) or not isinstance(entry.get("url"), str):
            continue
        tags = entry.get("tags")
        try:
            references.append(
                ResearchVulnerabilityReference(
                    url=entry["url"],
                    source=_text(entry.get("source")),
                    tags=(
                        tuple(tag for tag in tags if isinstance(tag, str))
                        if isinstance(tags, list)
                        else ()
                    ),
                )
            )
        except ResearchError:
            continue
        if len(references) == MAX_VULNERABILITY_REFERENCES:
            break
    return tuple(references)


def _timestamp(value: Any) -> datetime | None:
    """Parse one NVD timestamp as UTC.

    NVD writes these without an offset — `2021-12-10T10:15:09.143` — while the
    values are UTC. The offset is attached explicitly rather than left off,
    because a naive datetime here would be refused downstream and a guessed
    local offset would silently move every publication date.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _text(value: Any) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""
