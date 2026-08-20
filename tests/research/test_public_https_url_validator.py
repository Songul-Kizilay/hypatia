"""Tests for the explicit public-HTTPS research boundary."""

from __future__ import annotations

import unittest

from core.Exceptions import ResearchError
from research.PublicHttpsUrlValidator import HostResolver, PublicHttpsUrlValidator


def _resolver_for(address: str) -> HostResolver:
    def resolve(_hostname: str) -> tuple[str, ...]:
        return (address,)

    return resolve


class PublicHttpsUrlValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolved_hosts: list[str] = []

        def resolve(hostname: str) -> tuple[str, ...]:
            self.resolved_hosts.append(hostname)
            return ("93.184.216.34",)

        self.validator = PublicHttpsUrlValidator(resolve)

    def test_normalizes_a_public_https_url_and_removes_its_fragment(self) -> None:
        result = self.validator.validate(
            " HTTPS://Example.COM/research?q=hypatia#section "
        )

        self.assertEqual(result, "https://example.com/research?q=hypatia")
        self.assertEqual(self.resolved_hosts, ["example.com"])

    def test_returns_the_exact_normalized_public_addresses_for_pinning(self) -> None:
        validator = PublicHttpsUrlValidator(
            lambda _host: (
                "93.184.216.34",
                "2606:2800:220:1:248:1893:25c8:1946",
                "93.184.216.34",
            )
        )

        destination = validator.validate_and_resolve("https://EXAMPLE.com")

        self.assertEqual(destination.url, "https://example.com/")
        self.assertEqual(destination.hostname, "example.com")
        self.assertEqual(
            destination.addresses,
            (
                "93.184.216.34",
                "2606:2800:220:1:248:1893:25c8:1946",
            ),
        )

    def test_rejects_non_https_credentials_and_nonstandard_ports(self) -> None:
        for url, message in (
            ("http://example.com", "must use HTTPS"),
            ("https://user:secret@example.com", "cannot include credentials"),
            ("https://example.com:8443", "standard HTTPS port"),
        ):
            with self.subTest(url=url), self.assertRaisesRegex(ResearchError, message):
                self.validator.validate(url)

        self.assertEqual(self.resolved_hosts, [])

    def test_rejects_any_private_or_loopback_resolution(self) -> None:
        for address in ("127.0.0.1", "10.0.0.4", "192.168.1.9", "::1"):
            validator = PublicHttpsUrlValidator(_resolver_for(address))
            with (
                self.subTest(address=address),
                self.assertRaisesRegex(
                    ResearchError,
                    "public internet addresses",
                ),
            ):
                validator.validate("https://example.com")

    def test_rejects_mixed_public_and_private_dns_answers(self) -> None:
        validator = PublicHttpsUrlValidator(
            lambda _host: ("93.184.216.34", "127.0.0.1")
        )

        with self.assertRaisesRegex(ResearchError, "public internet addresses"):
            validator.validate("https://example.com")

    def test_formats_a_public_ipv6_literal_as_a_valid_url(self) -> None:
        validator = PublicHttpsUrlValidator(lambda _host: ("2606:4700:4700::1111",))

        result = validator.validate("https://[2606:4700:4700::1111]/dns")

        self.assertEqual(result, "https://[2606:4700:4700::1111]/dns")

    def test_rejects_an_invalid_internationalized_host_as_research_error(self) -> None:
        with self.assertRaisesRegex(ResearchError, "host name is invalid"):
            self.validator.validate("https://\ud800.example/")


if __name__ == "__main__":
    unittest.main()
