"""Vulnerability discovery that finds better sources without gaining authority.

The provider is the easy half. The half these tests are about is the boundary
around it: one host, one request, no reference ever fetched, no key in a URL, and
an approval that names Crossref never becoming an approval to contact anywhere
else. A discovery provider whose destination can be influenced from outside is an
SSRF primitive with a research feature wrapped around it, so most of what follows
is about proving this one cannot be.

Every fixture below is shaped from the live NVD CVE API 2.0 response verified on
26 August 2026. Nothing here touches the network.
"""

from __future__ import annotations

import ast
import json
import sys
import unittest
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.NvdResearchSourceDiscoveryProvider import (
    NVD_API_KEY_HEADER,
    NVD_CVE_ENDPOINT,
    NVD_KEYED_REQUESTS_PER_WINDOW,
    NVD_PUBLIC_REQUESTS_PER_WINDOW,
    NVD_RATE_WINDOW_SECONDS,
    NvdResearchSourceDiscoveryProvider,
)
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceDiscoveryProvider import ResearchSourceDiscoveryProvider
from research.ResearchSourceRelevanceRanker import ResearchSourceRelevanceRanker
from tests.SourceVocabulary import mentions, working_vocabulary

PROVIDER_SOURCE = (
    SRC_DIR / "research" / "NvdResearchSourceDiscoveryProvider.py"
).read_text(encoding="utf-8")

RESPONSE_URL = f"{NVD_CVE_ENDPOINT}?cveId=CVE-2025-29927"


def vulnerability(**overrides: Any) -> dict[str, Any]:
    """One CVE item shaped exactly like the live response."""
    item = {
        "id": "CVE-2025-29927",
        "sourceIdentifier": "security@vercel.com",
        "published": "2025-03-21T18:15:27.560",
        "lastModified": "2025-04-10T12:00:00.000",
        "vulnStatus": "Analyzed",
        "descriptions": [
            {"lang": "es", "value": "Omision de autorizacion en middleware."},
            {"lang": "en", "value": "Next.js middleware authorization bypass."},
        ],
        "weaknesses": [
            {
                "source": "nvd@nist.gov",
                "type": "Primary",
                "description": [{"lang": "en", "value": "CWE-285"}],
            }
        ],
        "metrics": {
            "cvssMetricV31": [
                {
                    "source": "nvd@nist.gov",
                    "type": "Primary",
                    "cvssData": {
                        "version": "3.1",
                        "baseScore": 9.1,
                        "baseSeverity": "CRITICAL",
                        "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:N",
                    },
                }
            ]
        },
        "references": [
            {
                "url": "https://github.test/advisory",
                "source": "security@vercel.com",
                "tags": ["Patch", "Vendor Advisory"],
            }
        ],
    }
    item.update(overrides)
    return item


def payload(*items: dict[str, Any], total: int | None = None) -> bytes:
    return json.dumps(
        {
            "resultsPerPage": len(items),
            "startIndex": 0,
            "totalResults": len(items) if total is None else total,
            "format": "NVD_CVE",
            "version": "2.0",
            "timestamp": "2026-08-26T12:00:00.000",
            "vulnerabilities": [{"cve": item} for item in items],
        }
    ).encode("utf-8")


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        url: str = RESPONSE_URL,
        content_type: str = "application/json",
    ) -> None:
        self._body = body
        self._url = url
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def geturl(self) -> str:
        return self._url

    def read(self, amt: int = -1) -> bytes:
        return self._body if amt < 0 else self._body[:amt]

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class RecordingOpener:
    """Records every request without ever opening a socket."""

    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.requests: list[Any] = []
        self._response = response
        self._error = error

    def open(self, fullurl: Any, data: Any = None, timeout: float = 0.0) -> Any:
        self.requests.append((fullurl, timeout))
        if self._error is not None:
            raise self._error
        return self._response


def provider(
    body: bytes | None = None,
    *,
    api_key: str | None = None,
    error: Exception | None = None,
    response: Any = None,
    **kwargs: Any,
) -> tuple[NvdResearchSourceDiscoveryProvider, RecordingOpener]:
    opener = RecordingOpener(
        response if response is not None else FakeResponse(body or payload()),
        error=error,
    )
    return (
        NvdResearchSourceDiscoveryProvider(api_key=api_key, opener=opener, **kwargs),
        opener,
    )


def query_of(request: Any) -> dict[str, str]:
    from urllib.parse import parse_qs, urlparse

    return {
        key: values[0]
        for key, values in parse_qs(urlparse(request.full_url).query).items()
    }


class ArchitectureTests(unittest.TestCase):
    def test_it_satisfies_the_same_discovery_contract_as_crossref(self) -> None:
        """Structurally, since the protocol is not runtime-checkable."""
        from research.CrossrefResearchSourceDiscoveryProvider import (
            CrossrefResearchSourceDiscoveryProvider,
        )

        instance, _ = provider()
        contract = tuple(
            name
            for name in dir(ResearchSourceDiscoveryProvider)
            if not name.startswith("_")
        )

        self.assertEqual(contract, ("discover", "provider_name"))
        for member in contract:
            with self.subTest(member=member):
                self.assertTrue(hasattr(instance, member))
                self.assertTrue(
                    hasattr(CrossrefResearchSourceDiscoveryProvider, member)
                )
        self.assertEqual(instance.provider_name, "nvd")

    def test_the_provider_name_comes_from_the_closed_vocabulary(self) -> None:
        instance, _ = provider()

        self.assertEqual(
            instance.provider_name, ResearchDiscoveryProviderName.NVD.value
        )

    def test_no_vulnerability_parsing_leaks_into_the_ranker(self) -> None:
        """The ranker sees candidates, never a provider's response shape."""
        ranker_source = (
            SRC_DIR / "research" / "ResearchSourceRelevanceRanker.py"
        ).read_text(encoding="utf-8")
        vocabulary = working_vocabulary(ranker_source, "rank", "_measure")

        for forbidden in ("cve", "cvss", "nvd", "vulnerability", "kev"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])


class NetworkBoundaryTests(unittest.TestCase):
    def test_one_discovery_makes_exactly_one_request(self) -> None:
        """No pagination, no retry, no second page for a large result set."""
        instance, opener = provider(payload(vulnerability(), total=10_000))

        instance.discover("Next.js middleware", limit=5)

        self.assertEqual(len(opener.requests), 1)

    def test_the_request_goes_to_the_official_endpoint_over_https(self) -> None:
        instance, opener = provider()

        instance.discover("Next.js middleware", limit=5)

        [(request, _)] = opener.requests
        self.assertTrue(
            request.full_url.startswith(
                "https://services.nvd.nist.gov/rest/json/cves/2.0?"
            )
        )

    def test_the_endpoint_is_fixed_in_code_and_takes_no_configuration(self) -> None:
        signature = ast.parse(PROVIDER_SOURCE)
        names = {
            argument.arg
            for node in ast.walk(signature)
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
            for argument in node.args.args + node.args.kwonlyargs
        }

        for forbidden in ("host", "endpoint", "url", "base_url", "origin"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, names)

    def test_a_bounded_timeout_reaches_the_transport(self) -> None:
        instance, opener = provider(timeout_seconds=4.5)

        instance.discover("Next.js middleware", limit=5)

        self.assertEqual(opener.requests[0][1], 4.5)

    def test_an_oversized_response_is_refused_rather_than_read(self) -> None:
        instance, _ = provider(payload(vulnerability()), maximum_bytes=10)

        with self.assertRaises(ResearchError):
            instance.discover("Next.js middleware", limit=5)

    def test_a_response_from_another_host_is_refused(self) -> None:
        instance, _ = provider(
            response=FakeResponse(payload(), url="https://attacker.example/rest")
        )

        with self.assertRaises(ResearchError):
            instance.discover("Next.js middleware", limit=5)

    def test_a_response_from_the_right_host_but_wrong_path_is_refused(self) -> None:
        instance, _ = provider(
            response=FakeResponse(
                payload(), url="https://services.nvd.nist.gov/rest/json/other"
            )
        )

        with self.assertRaises(ResearchError):
            instance.discover("Next.js middleware", limit=5)

    def test_a_non_json_response_is_refused(self) -> None:
        instance, _ = provider(
            response=FakeResponse(payload(), content_type="text/html")
        )

        with self.assertRaises(ResearchError):
            instance.discover("Next.js middleware", limit=5)

    def test_no_reference_is_fetched_however_tempting_its_address(self) -> None:
        """A link-local address in a response is data, not a destination."""
        instance, opener = provider(
            payload(
                vulnerability(
                    references=[
                        {"url": "http://169.254.169.254/latest/meta-data/"},
                        {"url": "http://127.0.0.1:8080/admin"},
                    ]
                )
            )
        )

        [candidate] = instance.discover("Next.js middleware", limit=5)

        self.assertEqual(len(opener.requests), 1)
        assert candidate.vulnerability is not None
        self.assertEqual(
            [reference.url for reference in candidate.vulnerability.references],
            [
                "http://169.254.169.254/latest/meta-data/",
                "http://127.0.0.1:8080/admin",
            ],
        )

    def test_the_provider_never_fetches_anything_it_was_told_about(self) -> None:
        vocabulary = working_vocabulary(
            PROVIDER_SOURCE, "_references", "_candidate_from_item", "_parse_candidates"
        )

        for forbidden in ("open", "urlopen", "fetch", "download", "follow"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])


class ApiKeyTests(unittest.TestCase):
    KEY = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"

    def test_discovery_works_with_no_key_configured(self) -> None:
        instance, opener = provider()

        instance.discover("Next.js middleware", limit=5)

        self.assertFalse(instance.has_api_key)
        [(request, _)] = opener.requests
        self.assertNotIn(NVD_API_KEY_HEADER.casefold(), request.headers)

    def test_a_configured_key_travels_in_the_official_header(self) -> None:
        instance, opener = provider(api_key=self.KEY)

        instance.discover("Next.js middleware", limit=5)

        [(request, _)] = opener.requests
        self.assertEqual(request.headers.get(NVD_API_KEY_HEADER.capitalize()), self.KEY)

    def test_a_key_never_reaches_the_url(self) -> None:
        """A key in a URL is a key in a log, a referrer, and an error message."""
        instance, opener = provider(api_key=self.KEY)

        instance.discover("Next.js middleware", limit=5)

        [(request, _)] = opener.requests
        self.assertNotIn(self.KEY, request.full_url)
        self.assertNotIn("apikey", request.full_url.casefold())

    def test_a_key_never_reaches_an_error_message(self) -> None:
        from urllib.error import HTTPError

        instance, _ = provider(
            api_key=self.KEY,
            error=HTTPError(RESPONSE_URL, 403, "Forbidden", Message(), None),
        )

        with self.assertRaises(ResearchError) as raised:
            instance.discover("Next.js middleware", limit=5)

        self.assertNotIn(self.KEY, str(raised.exception))

    def test_the_provider_never_reveals_the_key_it_holds(self) -> None:
        instance, _ = provider(api_key=self.KEY)

        self.assertTrue(instance.has_api_key)
        self.assertNotIn(self.KEY, repr(instance))

    def test_a_malformed_key_is_refused_at_construction(self) -> None:
        for bad in ("", "   ", "key with spaces", "line\nbreak"):
            with self.subTest(key=bad):
                with self.assertRaises(ValueError):
                    NvdResearchSourceDiscoveryProvider(api_key=bad)

    def test_the_published_rate_limits_are_recorded_as_constants(self) -> None:
        """Verified against the official documentation, not assumed."""
        self.assertEqual(NVD_PUBLIC_REQUESTS_PER_WINDOW, 5)
        self.assertEqual(NVD_KEYED_REQUESTS_PER_WINDOW, 50)
        self.assertEqual(NVD_RATE_WINDOW_SECONDS, 30)


class RoutingTests(unittest.TestCase):
    def test_an_exact_cve_uses_the_exact_lookup(self) -> None:
        instance, opener = provider()

        instance.discover("What is CVE-2025-29927?", limit=5)

        query = query_of(opener.requests[0][0])
        self.assertEqual(query["cveId"], "CVE-2025-29927")
        self.assertNotIn("keywordSearch", query)

    def test_a_lowercase_identifier_is_canonicalised(self) -> None:
        instance, opener = provider()

        instance.discover("cve-2025-29927", limit=5)

        self.assertEqual(query_of(opener.requests[0][0])["cveId"], "CVE-2025-29927")

    def test_a_malformed_identifier_never_enters_the_exact_route(self) -> None:
        """A near-miss is a different vulnerability, not a typo to be repaired."""
        for query in ("CVE-25-1234", "CVE-2025-", "CVE-2025-ABC", "CVE2025-29927"):
            with self.subTest(query=query):
                instance, opener = provider()
                instance.discover(query, limit=5)
                self.assertNotIn("cveId", query_of(opener.requests[0][0]))

    def test_two_identifiers_are_ambiguous_and_fall_through(self) -> None:
        instance, opener = provider()

        instance.discover("compare CVE-2025-29927 and CVE-2024-51479", limit=5)

        self.assertNotIn("cveId", query_of(opener.requests[0][0]))

    def test_a_general_question_uses_the_keyword_mechanism(self) -> None:
        instance, opener = provider()

        instance.discover("Next.js middleware authorization bypass", limit=5)

        query = query_of(opener.requests[0][0])
        self.assertIn("keywordSearch", query)
        self.assertNotIn("cveId", query)

    def test_technical_identifiers_reach_the_provider_intact(self) -> None:
        instance, opener = provider()

        instance.discover("ASP.NET and HTTP/2 request smuggling", limit=5)

        keyword = query_of(opener.requests[0][0])["keywordSearch"]
        self.assertIn("asp.net", keyword)
        self.assertIn("http/2", keyword)

    def test_the_page_size_is_bounded_and_never_paginated(self) -> None:
        instance, opener = provider()

        instance.discover("Next.js middleware", limit=4)

        query = query_of(opener.requests[0][0])
        self.assertEqual(query["resultsPerPage"], "4")
        self.assertEqual(query["startIndex"], "0")

    def test_an_oversized_limit_is_refused(self) -> None:
        instance, _ = provider()

        with self.assertRaises(ResearchError):
            instance.discover("Next.js middleware", limit=50)

    def test_an_empty_query_is_refused_before_any_request(self) -> None:
        instance, opener = provider()

        with self.assertRaises(ResearchError):
            instance.discover("   ", limit=5)

        self.assertEqual(opener.requests, [])


class ParsingTests(unittest.TestCase):
    def one(self, **overrides: Any) -> ResearchSourceCandidate:
        instance, _ = provider(payload(vulnerability(**overrides)))
        [candidate] = instance.discover("Next.js middleware", limit=5)
        return candidate

    def test_the_english_description_is_chosen_by_language_code(self) -> None:
        """The first entry is not reliably English, and order is not evidence."""
        candidate = self.one()

        self.assertEqual(candidate.snippet, "Next.js middleware authorization bypass.")

    def test_a_record_with_no_english_description_fabricates_none(self) -> None:
        candidate = self.one(descriptions=[{"lang": "es", "value": "Solo en espanol."}])

        self.assertEqual(candidate.snippet, "")
        self.assertEqual(candidate.title, "CVE-2025-29927")

    def test_the_identity_is_the_cve_and_not_a_position_or_a_hash(self) -> None:
        candidate = self.one()

        self.assertEqual(
            candidate.url, "https://nvd.nist.gov/vuln/detail/CVE-2025-29927"
        )
        assert candidate.vulnerability is not None
        self.assertEqual(candidate.vulnerability.cve_id, "CVE-2025-29927")

    def test_publication_and_modification_are_kept_apart(self) -> None:
        candidate = self.one()

        assert candidate.vulnerability is not None
        self.assertEqual(candidate.published_year, 2025)
        self.assertEqual(
            candidate.vulnerability.last_modified,
            datetime(2025, 4, 10, 12, 0, tzinfo=UTC),
        )

    def test_a_timestamp_without_an_offset_is_read_as_utc(self) -> None:
        """NVD writes UTC without saying so; guessing local would move dates."""
        candidate = self.one()

        assert candidate.vulnerability is not None
        assert candidate.vulnerability.last_modified is not None
        self.assertEqual(candidate.vulnerability.last_modified.utcoffset().seconds, 0)

    def test_the_provider_record_status_is_preserved(self) -> None:
        candidate = self.one()

        assert candidate.vulnerability is not None
        self.assertEqual(candidate.vulnerability.status, "Analyzed")

    def test_a_rejected_record_stays_visible_and_stays_labelled(self) -> None:
        """A rejection is a fact worth seeing, not an error to hide."""
        candidate = self.one(vulnStatus="Rejected")

        assert candidate.vulnerability is not None
        self.assertEqual(candidate.vulnerability.status, "Rejected")

    def test_structured_weaknesses_are_kept(self) -> None:
        candidate = self.one()

        assert candidate.vulnerability is not None
        self.assertEqual(candidate.vulnerability.weaknesses, ("CWE-285",))

    def test_a_record_without_weaknesses_invents_none(self) -> None:
        candidate = self.one(weaknesses=[])

        assert candidate.vulnerability is not None
        self.assertEqual(candidate.vulnerability.weaknesses, ())

    def test_no_weakness_is_inferred_from_the_description(self) -> None:
        candidate = self.one(
            weaknesses=[],
            descriptions=[
                {"lang": "en", "value": "This is an improper authorization flaw."}
            ],
        )

        assert candidate.vulnerability is not None
        self.assertEqual(candidate.vulnerability.weaknesses, ())

    def test_every_scored_metric_is_kept_with_its_own_source(self) -> None:
        candidate = self.one(
            metrics={
                "cvssMetricV31": [
                    {
                        "source": "nvd@nist.gov",
                        "cvssData": {
                            "version": "3.1",
                            "baseScore": 9.1,
                            "baseSeverity": "CRITICAL",
                        },
                    },
                    {
                        "source": "security@vercel.com",
                        "cvssData": {
                            "version": "3.1",
                            "baseScore": 7.5,
                            "baseSeverity": "HIGH",
                        },
                    },
                ],
                "cvssMetricV2": [
                    {
                        "source": "nvd@nist.gov",
                        "baseSeverity": "HIGH",
                        "cvssData": {"version": "2.0", "baseScore": 7.5},
                    }
                ],
            }
        )

        assert candidate.vulnerability is not None
        metrics = candidate.vulnerability.metrics
        self.assertEqual(len(metrics), 3)
        self.assertEqual(
            {(metric.version, metric.score) for metric in metrics},
            {("3.1", 9.1), ("3.1", 7.5), ("2.0", 7.5)},
        )

    def test_a_metrics_entry_without_a_score_is_skipped_not_defaulted(self) -> None:
        """The live response carries `ssvcV203`, which has no CVSS in it."""
        candidate = self.one(
            metrics={
                "ssvcV203": [{"source": "cisa", "ssvcData": {"id": "CVE-1"}}],
                "cvssMetricV31": [
                    {
                        "source": "nvd@nist.gov",
                        "cvssData": {"version": "3.1", "baseScore": 9.1},
                    }
                ],
            }
        )

        assert candidate.vulnerability is not None
        self.assertEqual(len(candidate.vulnerability.metrics), 1)
        self.assertEqual(candidate.vulnerability.metrics[0].version, "3.1")

    def test_a_record_without_metrics_carries_none(self) -> None:
        candidate = self.one(metrics={})

        assert candidate.vulnerability is not None
        self.assertEqual(candidate.vulnerability.metrics, ())

    def test_reference_tags_are_kept_only_when_the_provider_sent_them(self) -> None:
        candidate = self.one(
            references=[
                {"url": "https://a.test/x", "source": "s", "tags": ["Patch"]},
                {"url": "https://b.test/y", "source": "s"},
            ]
        )

        assert candidate.vulnerability is not None
        first, second = candidate.vulnerability.references
        self.assertEqual(first.tags, ("Patch",))
        self.assertEqual(second.tags, ())

    def test_a_long_reference_list_is_bounded_and_says_so(self) -> None:
        candidate = self.one(
            references=[
                {"url": f"https://example.test/{index}"} for index in range(103)
            ]
        )

        assert candidate.vulnerability is not None
        record = candidate.vulnerability
        self.assertEqual(len(record.references), 25)
        self.assertEqual(record.reference_total, 103)
        self.assertTrue(record.references_truncated)
        self.assertIn("25 shown of 103", " ".join(record.lines()))

    def test_the_cisa_fields_are_kept_when_they_are_actually_there(self) -> None:
        candidate = self.one(
            cisaExploitAdd="2025-03-25",
            cisaVulnerabilityName="Next.js Authorization Bypass",
            cisaActionDue="2025-04-15",
            cisaRequiredAction="Apply mitigations.",
        )

        assert candidate.vulnerability is not None
        self.assertTrue(candidate.vulnerability.known_exploited)
        self.assertEqual(candidate.vulnerability.known_exploited_at, "2025-03-25")

    def test_a_record_without_cisa_fields_claims_no_exploitation(self) -> None:
        candidate = self.one()

        assert candidate.vulnerability is not None
        self.assertFalse(candidate.vulnerability.known_exploited)

    def test_a_malformed_item_is_skipped_and_the_readable_ones_survive(self) -> None:
        instance, _ = provider(
            payload(
                {"id": "not-a-cve"},
                vulnerability(),
                {"descriptions": "wrong shape"},
            )
        )

        candidates = instance.discover("Next.js middleware", limit=5)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].vulnerability.cve_id, "CVE-2025-29927")

    def test_zero_results_is_an_empty_answer_and_not_a_failure(self) -> None:
        instance, _ = provider(payload())

        self.assertEqual(instance.discover("nothing matches this", limit=5), [])

    def test_malformed_json_is_refused(self) -> None:
        instance, _ = provider(b"{not json")

        with self.assertRaises(ResearchError):
            instance.discover("Next.js middleware", limit=5)

    def test_a_response_of_the_wrong_shape_is_refused(self) -> None:
        instance, _ = provider(json.dumps({"unexpected": True}).encode())

        with self.assertRaises(ResearchError):
            instance.discover("Next.js middleware", limit=5)

    def test_the_title_leads_with_the_identifier_rather_than_inventing_one(
        self,
    ) -> None:
        """A CVE record has no title, and a fabricated one would read like one."""
        candidate = self.one()

        self.assertTrue(candidate.title.startswith("CVE-2025-29927"))


class RefusalTests(unittest.TestCase):
    def _http_error(self, code: int) -> Exception:
        from urllib.error import HTTPError

        return HTTPError(RESPONSE_URL, code, "refused", Message(), None)

    def test_a_rate_limit_refusal_is_reported_rather_than_slept_through(self) -> None:
        """A retry inside one advance is a request the budget never approved."""
        for code in (403, 429):
            with self.subTest(code=code):
                instance, opener = provider(error=self._http_error(code))
                with self.assertRaises(ResearchError) as raised:
                    instance.discover("Next.js middleware", limit=5)
                self.assertIn("rate limit", str(raised.exception).casefold())
                self.assertEqual(len(opener.requests), 1)

    def test_a_missing_record_is_reported_as_missing(self) -> None:
        instance, _ = provider(error=self._http_error(404))

        with self.assertRaises(ResearchError) as raised:
            instance.discover("CVE-2025-29927", limit=5)

        self.assertIn("no record", str(raised.exception).casefold())

    def test_the_provider_never_sleeps_or_retries(self) -> None:
        vocabulary = working_vocabulary(
            PROVIDER_SOURCE, "discover", "_refusal", "_parameters"
        )

        for forbidden in ("sleep", "retry", "backoff", "attempt", "wait"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])

    def test_a_transport_failure_is_reported_without_its_details(self) -> None:
        instance, _ = provider(error=OSError("connect to 10.0.0.1 failed"))

        with self.assertRaises(ResearchError) as raised:
            instance.discover("Next.js middleware", limit=5)

        self.assertNotIn("10.0.0.1", str(raised.exception))


class RankingSeparationTests(unittest.TestCase):
    """Severity, exploitation and provenance are not relevance."""

    def _candidates(self, instance: Any, body: bytes) -> list[ResearchSourceCandidate]:
        instance, _ = provider(body)
        return instance.discover("Next.js middleware authorization bypass", limit=5)

    def test_an_exact_cve_match_ranks_strongly(self) -> None:
        instance, _ = provider(
            payload(
                vulnerability(),
                vulnerability(
                    id="CVE-2024-51479",
                    descriptions=[
                        {"lang": "en", "value": "An unrelated path traversal."}
                    ],
                ),
            )
        )
        candidates = instance.discover("CVE-2025-29927", limit=5)

        ranked = ResearchSourceRelevanceRanker().rank("CVE-2025-29927", candidates)

        self.assertEqual(ranked[0].candidate.vulnerability.cve_id, "CVE-2025-29927")
        self.assertGreater(ranked[0].relevance.score, ranked[1].relevance.score)

    def test_a_higher_severity_alone_does_not_improve_relevance(self) -> None:
        low = vulnerability(
            id="CVE-2024-51479",
            metrics={
                "cvssMetricV31": [
                    {"source": "n", "cvssData": {"version": "3.1", "baseScore": 2.0}}
                ]
            },
        )
        high = vulnerability(
            id="CVE-2024-51480",
            metrics={
                "cvssMetricV31": [
                    {"source": "n", "cvssData": {"version": "3.1", "baseScore": 10.0}}
                ]
            },
        )
        instance, _ = provider(payload(low, high))
        candidates = instance.discover("Next.js middleware", limit=5)

        ranked = ResearchSourceRelevanceRanker().rank(
            "Next.js middleware authorization bypass", candidates
        )

        self.assertEqual(ranked[0].relevance.score, ranked[1].relevance.score)

    def test_known_exploitation_alone_does_not_improve_relevance(self) -> None:
        plain = vulnerability(id="CVE-2024-51479")
        exploited = vulnerability(
            id="CVE-2024-51480",
            cisaExploitAdd="2025-01-01",
            cisaVulnerabilityName="Exploited thing",
        )
        instance, _ = provider(payload(plain, exploited))
        candidates = instance.discover("Next.js middleware", limit=5)

        ranked = ResearchSourceRelevanceRanker().rank(
            "Next.js middleware authorization bypass", candidates
        )

        self.assertEqual(ranked[0].relevance.score, ranked[1].relevance.score)

    def test_the_provider_order_survives_being_reranked(self) -> None:
        """NVD returns publication order, so its own answer is worth keeping."""
        instance, _ = provider(
            payload(
                vulnerability(
                    id="CVE-2024-51479",
                    descriptions=[{"lang": "en", "value": "Unrelated."}],
                ),
                vulnerability(),
            )
        )
        candidates = instance.discover("Next.js middleware", limit=5)

        ranked = ResearchSourceRelevanceRanker().rank(
            "Next.js middleware authorization bypass", candidates
        )

        self.assertEqual(ranked[0].provider_rank, 2)
        self.assertEqual(ranked[0].relevance_rank, 1)
        self.assertEqual(sorted(entry.provider_rank for entry in ranked), [1, 2])


class SeparationTests(unittest.TestCase):
    def test_discovery_accepts_nothing_and_records_no_judgement(self) -> None:
        vocabulary = working_vocabulary(
            PROVIDER_SOURCE, "discover", "_candidate_from_item"
        )

        for forbidden in (
            "accept",
            "evidence",
            "claim",
            "confidence",
            "assessment",
            "reputation",
            "trust",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])

    def test_the_provider_record_status_is_not_an_operator_judgement(self) -> None:
        """NIST's word about its own record is not what a person concluded."""
        instance, _ = provider(payload(vulnerability(vulnStatus="Rejected")))

        [candidate] = instance.discover("Next.js middleware", limit=5)

        assert candidate.vulnerability is not None
        self.assertEqual(candidate.vulnerability.status, "Rejected")
        self.assertNotIn("publication_status", PROVIDER_SOURCE)

    def test_nothing_grants_nvd_a_trust_level(self) -> None:
        for forbidden in ("HIGH_TRUST", "information_trust", "SourceReputation"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, PROVIDER_SOURCE)

    def test_no_model_participates_in_discovery(self) -> None:
        imported = {
            name.name.split(".")[0]
            for node in ast.walk(ast.parse(PROVIDER_SOURCE))
            if isinstance(node, ast.Import)
            for name in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(ast.parse(PROVIDER_SOURCE))
            if isinstance(node, ast.ImportFrom)
        }

        self.assertNotIn("llm", imported)
        vocabulary = working_vocabulary(PROVIDER_SOURCE, "discover", "_parameters")
        for forbidden in ("llm", "model", "prompt", "completion"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])


if __name__ == "__main__":
    unittest.main()
