"""Offline target-scope rules and actual fetch/redirect/connection boundaries."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from http.client import HTTPMessage
from io import BytesIO
from unittest.mock import Mock, patch
from urllib.request import Request

from core.Exceptions import ResearchError
from research.HttpResearchSourceFetcher import (
    HttpResearchSourceFetcher,
    _ValidatedRedirectHandler,
)
from research.PinnedHttpsTransport import PinnedHttpsHandler
from research.ResearchTargetScope import (
    MAX_SCOPE_RULES,
    ResearchTargetScope,
    TargetHostRule,
)
from research.ScopedPublicHttpsUrlValidator import ScopedPublicHttpsUrlValidator
from tests.research.test_http_research_source_fetcher import FakeOpener, FakeResponse

PUBLIC = "93.184.216.34"


class TargetScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = ResearchTargetScope(
            allowed_hosts=(TargetHostRule("example.test"),)
        )
        self.resolver = Mock(return_value=(PUBLIC,))
        self.validator = ScopedPublicHttpsUrlValidator(self.scope, self.resolver)
        self.dns = patch("socket.getaddrinfo", side_effect=AssertionError("Live DNS"))
        self.dns.start()
        self.addCleanup(self.dns.stop)

    def test_exact_host_normalizes_case_and_one_root_dot(self) -> None:
        result = self.validator.validate_and_resolve("https://EXAMPLE.TEST./article")
        self.assertEqual(result.url, "https://example.test/article")
        self.assertEqual(result.addresses, (PUBLIC,))
        self.resolver.assert_called_once_with("example.test")

    def test_host_rule_is_canonical_and_immutable(self) -> None:
        rule = TargetHostRule("EXAMPLE.TEST.")
        self.assertEqual(rule.host, "example.test")
        with self.assertRaises(FrozenInstanceError):
            rule.host = "attacker.test"  # type: ignore[misc]

    def test_exact_host_never_implies_children_or_similar_names(self) -> None:
        for host in (
            "api.example.test",
            "evil-example.test",
            "example.test.attacker.test",
            "other.test",
            PUBLIC,
        ):
            with self.subTest(host=host), self.assertRaises(ResearchError):
                self.validator.validate("https://" + host)
        self.resolver.assert_not_called()

    def test_descendants_are_label_bounded_and_do_not_include_apex(self) -> None:
        scope = ResearchTargetScope(
            allowed_hosts=(TargetHostRule("example.test", subdomains_only=True),)
        )
        for host in ("api.example.test", "a.b.example.test"):
            scope.require_hostname(host)
        for host in ("example.test", "evil-example.test", "example.test.evil.test"):
            with self.subTest(host=host), self.assertRaises(ResearchError):
                scope.require_hostname(host)

    def test_exclusions_win_over_exact_and_descendant_inclusions(self) -> None:
        scope = ResearchTargetScope(
            allowed_hosts=(
                TargetHostRule("example.test", True),
                TargetHostRule("pay.example.test"),
            ),
            excluded_hosts=(
                TargetHostRule("pay.example.test"),
                TargetHostRule("pay.example.test", True),
            ),
        )
        for host in ("pay.example.test", "api.pay.example.test"):
            with (
                self.subTest(host=host),
                self.assertRaisesRegex(ResearchError, "excluded"),
            ):
                ScopedPublicHttpsUrlValidator(scope, self.resolver).validate(
                    "https://" + host
                )
        self.resolver.assert_not_called()

    def test_invalid_rule_input_is_not_interpreted_as_scope(self) -> None:
        for host in (
            "",
            "*",
            "*.example.test",
            "https://example.test",
            "example.test/path",
            "example.test:443",
            " example.test",
            "example.test..",
            "-a.test",
            "a-.test",
            "a..test",
            "a" * 64 + ".test",
            "example_test.test",
            "127.0.0.1",
            "127.1",
            "2130706433",
            "éxample.test",
            "example.test\n",
        ):
            with self.subTest(host=host), self.assertRaises(ResearchError):
                TargetHostRule(host)

    def test_scope_needs_typed_bounded_rules(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchTargetScope()
        with self.assertRaises(ResearchError):
            TargetHostRule("example.test", 1)  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            ResearchTargetScope(allowed_hosts=[TargetHostRule("example.test")])  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            ResearchTargetScope(allowed_hosts=("example.test",))  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            ResearchTargetScope(
                allowed_hosts=(TargetHostRule("example.test"),) * (MAX_SCOPE_RULES + 1)
            )

    def test_networks_require_strict_explicit_cidr(self) -> None:
        for network in (PUBLIC, "93.184.216.34/24", "::1/64", "nonsense", "1.2.3.4/99"):
            with self.subTest(network=network), self.assertRaises(ResearchError):
                ResearchTargetScope(allowed_networks=(network,))

    def test_ip_literals_require_their_own_network_rule(self) -> None:
        scope = ResearchTargetScope(
            allowed_networks=("93.184.216.0/24", "2606:4700::/32")
        )
        scope.require_hostname(PUBLIC)
        scope.require_hostname("2606:4700:4700::1111")
        for host in ("93.184.217.34", "2607::1", "unlisted.test"):
            with self.subTest(host=host), self.assertRaises(ResearchError):
                scope.require_hostname(host)

    def test_allowed_network_does_not_authorize_a_resolving_hostname(self) -> None:
        scope = ResearchTargetScope(allowed_networks=(PUBLIC + "/32",))
        with self.assertRaises(ResearchError):
            ScopedPublicHttpsUrlValidator(scope, self.resolver).validate(
                "https://unlisted.test"
            )
        self.resolver.assert_not_called()

    def test_resolved_ip_does_not_become_an_allowed_literal(self) -> None:
        self.validator.validate("https://example.test")
        self.resolver.reset_mock()
        with self.assertRaises(ResearchError):
            self.validator.validate("https://" + PUBLIC)
        self.resolver.assert_not_called()

    def test_excluded_network_vetoes_the_whole_dns_set(self) -> None:
        scope = ResearchTargetScope(
            allowed_hosts=self.scope.allowed_hosts,
            excluded_networks=("93.184.216.0/24",),
        )
        for addresses in ((PUBLIC,), ("1.1.1.1", PUBLIC), ("::ffff:" + PUBLIC,)):
            with (
                self.subTest(addresses=addresses),
                self.assertRaisesRegex(ResearchError, "excluded"),
            ):
                ScopedPublicHttpsUrlValidator(
                    scope, Mock(return_value=addresses)
                ).validate("https://example.test")

    def test_network_exclusion_wins_for_literal_as_well(self) -> None:
        scope = ResearchTargetScope(
            allowed_networks=("93.184.216.0/24",), excluded_networks=(PUBLIC + "/32",)
        )
        with self.assertRaisesRegex(ResearchError, "excluded"):
            scope.require_hostname(PUBLIC)

    def test_scoped_literal_fetch_normalizes_ipv6(self) -> None:
        ip = "2606:4700:4700::1111"
        scope = ResearchTargetScope(allowed_networks=(ip + "/128",))
        result = ScopedPublicHttpsUrlValidator(scope, lambda _host: (ip,)).validate(
            "https://[2606:4700:4700:0:0:0:0:1111]/"
        )
        self.assertEqual(result, "https://[2606:4700:4700::1111]/")

    def test_bad_urls_are_denied_before_dns(self) -> None:
        for url in (
            "http://example.test/",
            "https://example.test:8443/",
            "https://u:p@example.test/",
            "https://example.test@evil.test/",
            "https://example.test\\@evil.test/",
            "https://exam\nple.test/",
            " https://example.test/",
            "https://example.test/\x00",
            "https://example.test/%20" + "x" * 8192,
            "https://%65xample.test/",
            "https://example.test../",
            "https://éxample.test/",
            "//example.test/",
            "https://[fe80::1%25eth0]/",
            "https://example.test:bad/",
        ):
            with self.subTest(url=url), self.assertRaises(ResearchError):
                self.validator.validate(url)
        self.resolver.assert_not_called()

    def test_unicode_case_mapping_cannot_turn_into_an_allowed_ascii_host(self) -> None:
        scope = ResearchTargetScope(allowed_hosts=(TargetHostRule("k.test"),))
        with self.assertRaises(ResearchError):
            ScopedPublicHttpsUrlValidator(scope, self.resolver).validate(
                "https://\u212a.test/"
            )
        self.resolver.assert_not_called()

    def test_literal_resolution_cannot_substitute_another_public_address(self) -> None:
        scope = ResearchTargetScope(allowed_networks=(PUBLIC + "/32",))
        with self.assertRaisesRegex(ResearchError, "changed target"):
            ScopedPublicHttpsUrlValidator(scope, lambda _host: ("1.1.1.1",)).validate(
                "https://" + PUBLIC
            )

    def test_invalid_or_oversized_address_sets_are_rejected(self) -> None:
        for addresses in ((), (PUBLIC,) * 65, ("bad",), ("fe80::1%eth0",), (1,)):
            with self.subTest(addresses=addresses), self.assertRaises(ResearchError):
                self.scope.require_addresses(addresses)  # type: ignore[arg-type]

    def test_scoped_connection_factory_receives_the_validated_addresses(self) -> None:
        handler = PinnedHttpsHandler(self.validator.validate_and_resolve)
        with patch.object(handler, "do_open", return_value="offline") as do_open:
            result = handler.https_open(Request("https://example.test/"))
        self.assertEqual(result, "offline")
        factory = do_open.call_args.args[0]
        connection = factory("example.test")
        self.assertEqual(connection.pinned_addresses, (PUBLIC,))
        self.assertEqual(connection.host, "example.test")
        connection.close()

    def test_explicit_scope_does_not_override_public_address_policy(self) -> None:
        for addresses in (("127.0.0.1",), (PUBLIC, "10.0.0.1"), ("::1",)):
            with self.subTest(addresses=addresses), self.assertRaises(ResearchError):
                ScopedPublicHttpsUrlValidator(
                    self.scope, Mock(return_value=addresses)
                ).validate("https://example.test")

    def test_fetch_rejects_outside_scope_before_open(self) -> None:
        opener = FakeOpener(FakeResponse())
        fetcher = HttpResearchSourceFetcher(validator=self.validator, opener=opener)
        with self.assertRaises(ResearchError):
            fetcher.fetch("https://outside.test/")
        self.assertEqual(opener.calls, [])
        self.resolver.assert_not_called()

    def test_valid_fetch_preserves_existing_bounded_read(self) -> None:
        response = FakeResponse(url="https://example.test/article")
        fetcher = HttpResearchSourceFetcher(
            validator=self.validator, opener=FakeOpener(response), maximum_bytes=64
        )
        source = fetcher.fetch("https://example.test/article")
        self.assertEqual(source.content, "Evidence.")
        self.assertEqual(response.read_limits, [65])

    def test_final_out_of_scope_response_body_is_not_read(self) -> None:
        response = FakeResponse(url="https://outside.test/")
        fetcher = HttpResearchSourceFetcher(
            validator=self.validator, opener=FakeOpener(response)
        )
        with self.assertRaises(ResearchError):
            fetcher.fetch("https://example.test/")
        self.assertEqual(response.read_limits, [])

    def test_production_opener_uses_scope_on_redirect_and_connection(self) -> None:
        fetcher = HttpResearchSourceFetcher(validator=self.validator)
        handlers = fetcher._opener.handlers  # type: ignore[attr-defined]
        redirect = next(h for h in handlers if isinstance(h, _ValidatedRedirectHandler))
        pinned = next(h for h in handlers if isinstance(h, PinnedHttpsHandler))
        with self.assertRaises(ResearchError):
            redirect.redirect_request(
                Request("https://example.test/"),
                BytesIO(),
                302,
                "Found",
                HTTPMessage(),
                "https://outside.test/",
            )
        with patch.object(pinned, "do_open") as do_open:
            with self.assertRaises(ResearchError):
                pinned.https_open(Request("https://outside.test/"))
            do_open.assert_not_called()
        self.resolver.assert_not_called()

    def test_dns_is_rechecked_at_connection_not_just_redirect_preview(self) -> None:
        scope = ResearchTargetScope(
            allowed_hosts=self.scope.allowed_hosts, excluded_networks=("1.1.1.1/32",)
        )
        resolver = Mock(side_effect=[(PUBLIC,), ("1.1.1.1",)])
        validator = ScopedPublicHttpsUrlValidator(scope, resolver)
        redirected = _ValidatedRedirectHandler(validator).redirect_request(
            Request("https://example.test/start"),
            BytesIO(),
            302,
            "Found",
            HTTPMessage(),
            "https://example.test/next",
        )
        self.assertIsNotNone(redirected)
        handler = PinnedHttpsHandler(validator.validate_and_resolve)
        with patch.object(handler, "do_open") as do_open:
            with self.assertRaisesRegex(ResearchError, "excluded"):
                handler.https_open(redirected)
            do_open.assert_not_called()
        self.assertEqual(resolver.call_count, 2)


if __name__ == "__main__":
    unittest.main()
