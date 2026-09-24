"""`canonical_dns_hostname` must never drift from scope-hostname matching."""

from __future__ import annotations

import unittest

from core.Exceptions import ResearchError
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchTargetScope import (
    ResearchTargetScope,
    TargetHostRule,
    canonical_dns_hostname,
)


class CanonicalDnsHostnameTests(unittest.TestCase):
    def test_case_and_trailing_dot_are_normalized(self) -> None:
        self.assertEqual(canonical_dns_hostname("EXAMPLE.TEST"), "example.test")
        self.assertEqual(canonical_dns_hostname("example.test."), "example.test")
        self.assertEqual(canonical_dns_hostname("Example.Test."), "example.test")

    def test_invalid_hostname_raises_research_error(self) -> None:
        for invalid in ("not a host!!", "", "a" * 300, "1.2.3.4"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ResearchError):
                    canonical_dns_hostname(invalid)

    def test_differential_matches_the_scope_matching_path_exactly(self) -> None:
        """The wrapper's output must be byte-identical to what scope matching uses.

        Construct a scope with a rule authored using a non-canonical form and
        prove the wrapper's canonicalization is exactly what makes
        `TargetHostRule.matches` (fed by the scope's own private `_dns_name`
        normalization) agree.
        """
        raw_forms = ("EXAMPLE.TEST", "example.test.", "Example.Test")
        for raw in raw_forms:
            with self.subTest(raw=raw):
                wrapper_output = canonical_dns_hostname(raw)
                rule = TargetHostRule(raw)
                # `TargetHostRule.__post_init__` stores exactly `_dns_name(raw)`,
                # so its persisted `.host` is the scope's own canonical form.
                self.assertEqual(wrapper_output, rule.host)
                scope = ResearchTargetScope(allowed_hosts=(TargetHostRule(raw),))
                resolution = scope.resolve_hostname(wrapper_output)
                self.assertEqual(resolution.status.value, "in_scope")
                self.assertEqual(resolution.matched_rule, wrapper_output)

    def test_sibling_hosts_never_collapse(self) -> None:
        self.assertNotEqual(
            canonical_dns_hostname("api.example.test"),
            canonical_dns_hostname("www.example.test"),
        )

    def test_suffix_trick_lookalikes_never_collapse(self) -> None:
        self.assertNotEqual(
            canonical_dns_hostname("attackerexample.test"),
            canonical_dns_hostname("example.test"),
        )

    def test_apex_and_subdomain_never_collapse(self) -> None:
        self.assertNotEqual(
            canonical_dns_hostname("example.test"),
            canonical_dns_hostname("sub.example.test"),
        )


class CanonicalizeAssetValueTests(unittest.TestCase):
    def test_hostname_kind_delegates_to_canonical_dns_hostname(self) -> None:
        self.assertEqual(
            canonicalize_asset_value(ResearchAssetKind.HOSTNAME, "EXAMPLE.TEST."),
            "example.test",
        )

    def test_ipv4_is_canonicalized_deterministically(self) -> None:
        self.assertEqual(
            canonicalize_asset_value(ResearchAssetKind.IP_ADDRESS, "93.184.216.34"),
            "93.184.216.34",
        )

    def test_ipv4_leading_zero_octets_are_rejected_not_reinterpreted(self) -> None:
        """A leading-zero octet is ambiguous (decimal vs. octal); refuse it.

        `ipaddress.ip_address` already refuses this form outright rather than
        silently reinterpreting it, so this locks in that fail-closed behavior
        for asset canonicalization rather than assuming it.
        """
        with self.assertRaises(ResearchError):
            canonicalize_asset_value(ResearchAssetKind.IP_ADDRESS, "093.184.216.034")

    def test_ipv6_is_canonicalized_deterministically(self) -> None:
        expanded = "2606:4700:0000:0000:0000:0000:0000:1111"
        compact = "2606:4700::1111"
        self.assertEqual(
            canonicalize_asset_value(ResearchAssetKind.IP_ADDRESS, expanded),
            canonicalize_asset_value(ResearchAssetKind.IP_ADDRESS, compact),
        )
        self.assertEqual(
            canonicalize_asset_value(ResearchAssetKind.IP_ADDRESS, expanded),
            compact,
        )

    def test_invalid_address_raises(self) -> None:
        with self.assertRaises(ResearchError):
            canonicalize_asset_value(ResearchAssetKind.IP_ADDRESS, "not-an-address")

    def test_invalid_kind_raises(self) -> None:
        with self.assertRaises(ResearchError):
            canonicalize_asset_value("not-a-kind", "example.test")  # type: ignore[arg-type]

    def test_empty_value_raises(self) -> None:
        with self.assertRaises(ResearchError):
            canonicalize_asset_value(ResearchAssetKind.HOSTNAME, "   ")

    def test_every_surface_form_matches_the_scope_rules_own_stored_form(self) -> None:
        """Cross the forms: a rule authored one way, an asset the other.

        Identity and scope matching must agree whichever surface form each
        side was typed in, or an asset could read out-of-scope purely because
        the operator typed the rule with different capitalization.
        """
        forms = ("example.test", "EXAMPLE.TEST", "Example.Test.", " example.test ")
        for rule_form in forms:
            for asset_form in forms:
                with self.subTest(rule=rule_form, asset=asset_form):
                    rule = TargetHostRule(rule_form.strip())
                    value = canonicalize_asset_value(
                        ResearchAssetKind.HOSTNAME, asset_form
                    )
                    self.assertEqual(value, rule.host)
                    scope = ResearchTargetScope(allowed_hosts=(rule,))
                    self.assertEqual(
                        scope.resolve_hostname(value).status.value, "in_scope"
                    )


if __name__ == "__main__":
    unittest.main()
