"""Scope identity and restart persistence must preserve every exclusion."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass, replace
from pathlib import Path
from unittest.mock import Mock, patch

from core.Exceptions import ResearchError
from research.JsonFileResearchTargetScopeStore import JsonFileResearchTargetScopeStore
from research.ResearchTargetScope import (
    MAX_SCOPE_RULES,
    ResearchTargetScope,
    TargetHostRule,
)
from research.ResearchTargetScopeCodec import (
    MAX_TARGET_SCOPE_BYTES,
    canonical_target_scope_bytes,
    decode_target_scope,
    encode_target_scope,
    target_scope_digest,
)
from research.ResearchTargetScopeResolution import ResearchTargetScopeResolution
from research.ResearchTargetScopeResolutionStatus import (
    ResearchTargetScopeResolutionStatus,
)
from research.ScopedPublicHttpsUrlValidator import ScopedPublicHttpsUrlValidator


def scope_fixture() -> ResearchTargetScope:
    return ResearchTargetScope(
        allowed_hosts=(
            TargetHostRule("EXAMPLE.TEST"),
            TargetHostRule("example.test", True),
        ),
        excluded_hosts=(
            TargetHostRule("pay.example.test"),
            TargetHostRule("pay.example.test", True),
        ),
        allowed_networks=("93.184.216.0/24", "2606:4700::/32"),
        excluded_networks=("93.184.216.35/32", "2606:4700:4700::1111/128"),
    )


class ScopeCodecTests(unittest.TestCase):
    def test_round_trip_preserves_all_typed_fields(self) -> None:
        scope = scope_fixture()
        loaded = decode_target_scope(encode_target_scope(scope))
        self.assertEqual(loaded, scope)
        self.assertEqual(target_scope_digest(scope), target_scope_digest(loaded))
        self.assertEqual(len(target_scope_digest(scope)), 64)

    def test_canonical_encoding_is_deterministic_and_separate_from_storage_layout(
        self,
    ) -> None:
        scope = scope_fixture()
        document = json.loads(encode_target_scope(scope))
        compact = json.dumps(document, sort_keys=False, separators=(",", ":")).encode()
        self.assertEqual(decode_target_scope(compact), scope)
        self.assertEqual(
            canonical_target_scope_bytes(scope),
            canonical_target_scope_bytes(scope_fixture()),
        )

    def test_every_rule_family_and_subdomain_selection_affects_digest(self) -> None:
        scope = scope_fixture()
        variants = (
            replace(scope, allowed_hosts=(TargetHostRule("other.test"),)),
            replace(scope, excluded_hosts=()),
            replace(scope, allowed_networks=()),
            replace(scope, excluded_networks=()),
            replace(scope, allowed_hosts=(TargetHostRule("example.test", True),)),
            replace(scope, allowed_hosts=tuple(reversed(scope.allowed_hosts))),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(
                    target_scope_digest(scope), target_scope_digest(variant)
                )

    def test_future_model_fields_cannot_silently_escape_identity(self) -> None:
        @dataclass(frozen=True, slots=True)
        class FutureScope(ResearchTargetScope):
            extra_policy: str = "required"

        @dataclass(frozen=True, slots=True)
        class FutureHost(TargetHostRule):
            path_limit: str = "/only"

        for scope in (
            FutureScope(allowed_hosts=(TargetHostRule("example.test"),)),
            ResearchTargetScope(allowed_hosts=(FutureHost("example.test"),)),
        ):
            with (
                self.subTest(scope=scope),
                self.assertRaisesRegex(ResearchError, "schema"),
            ):
                encode_target_scope(scope)

    def test_dropped_exclusions_or_added_permissions_fail_digest_check(self) -> None:
        for field, value in (
            ("excluded_hosts", []),
            ("excluded_networks", []),
            ("allowed_hosts", [{"host": "other.test", "subdomains_only": True}]),
            ("allowed_networks", ["0.0.0.0/0"]),
        ):
            document = json.loads(encode_target_scope(scope_fixture()))
            document["scope"][field] = value
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ResearchError, "digest"),
            ):
                decode_target_scope(json.dumps(document).encode())

    def test_unknown_and_missing_fields_fail_at_every_level(self) -> None:
        for level in ("document", "scope", "host"):
            for missing in (False, True):
                document = json.loads(encode_target_scope(scope_fixture()))
                target = document if level == "document" else document["scope"]
                if level == "host":
                    target = target["allowed_hosts"][0]
                if missing:
                    target.pop(next(iter(target)))
                else:
                    target["path_exclusion"] = "/admin"
                with (
                    self.subTest(level=level, missing=missing),
                    self.assertRaises(ResearchError),
                ):
                    decode_target_scope(json.dumps(document).encode())

    def test_schema_type_is_strict(self) -> None:
        for version in (True, False, 1.0, "1", None, 0, 2, []):
            document = json.loads(encode_target_scope(scope_fixture()))
            document["schema_version"] = version
            with self.subTest(version=version), self.assertRaises(ResearchError):
                decode_target_scope(json.dumps(document).encode())

    def test_duplicate_fields_are_rejected_even_if_values_agree(self) -> None:
        payload = encode_target_scope(scope_fixture())
        for original, duplicated in (
            (b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'),
            (
                b'"subdomains_only": false',
                b'"subdomains_only": false, "subdomains_only": false',
            ),
        ):
            with (
                self.subTest(original=original),
                self.assertRaisesRegex(ResearchError, "duplicate"),
            ):
                decode_target_scope(payload.replace(original, duplicated, 1))

    def test_wrong_types_are_not_coerced_into_rules(self) -> None:
        for field, value in (
            ("allowed_hosts", "example.test"),
            ("excluded_hosts", None),
            ("allowed_networks", [42]),
            ("excluded_networks", ["93.184.216.35/24"]),
            ("allowed_hosts", [{"host": "example.test", "subdomains_only": 1}]),
        ):
            document = json.loads(encode_target_scope(scope_fixture()))
            document["scope"][field] = value
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(ResearchError),
            ):
                decode_target_scope(json.dumps(document).encode())

    def test_corrupt_bytes_and_excessive_nesting_are_controlled_errors(self) -> None:
        for payload in (b"", b"{", b"\xff", b"null", b"[]", b"[" * 2000 + b"]" * 2000):
            with self.subTest(size=len(payload)), self.assertRaises(ResearchError):
                decode_target_scope(payload)

    def test_byte_limit_is_checked_before_json_decoding(self) -> None:
        with patch("research.ResearchTargetScopeCodec.json.loads") as loads:
            with self.assertRaises(ResearchError):
                decode_target_scope(b" " * (MAX_TARGET_SCOPE_BYTES + 1))
            loads.assert_not_called()

    def test_aggregate_rule_count_is_checked_before_rule_construction(self) -> None:
        document = json.loads(encode_target_scope(scope_fixture()))
        document["scope"]["allowed_hosts"] *= MAX_SCOPE_RULES
        with self.assertRaisesRegex(ResearchError, "too many"):
            decode_target_scope(json.dumps(document).encode())


class TargetScopeStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "scope.json"
        self.scope = scope_fixture()
        self.store = JsonFileResearchTargetScopeStore(self.path)

    def test_absence_is_none_not_unrestricted_scope_or_a_write(self) -> None:
        self.assertIsNone(self.store.load())
        self.assertFalse(self.path.exists())

    def test_restart_restores_exact_scope_and_content_identity(self) -> None:
        self.store.save(self.scope)
        before = self.path.read_bytes()
        loaded = JsonFileResearchTargetScopeStore(self.path).load()
        self.assertEqual(loaded, self.scope)
        self.assertEqual(self.path.read_bytes(), before)

    def test_restored_scope_enforces_exclusions_before_dns(self) -> None:
        self.store.save(self.scope)
        loaded = JsonFileResearchTargetScopeStore(self.path).load()
        assert loaded is not None
        resolver = Mock(return_value=("93.184.216.34",))
        validator = ScopedPublicHttpsUrlValidator(loaded, resolver)
        for url in (
            "https://pay.example.test",
            "https://deep.pay.example.test",
            "https://93.184.216.35",
        ):
            with (
                self.subTest(url=url),
                self.assertRaisesRegex(ResearchError, "excluded"),
            ):
                validator.validate(url)
        resolver.assert_not_called()
        self.assertEqual(
            validator.validate("https://api.example.test"), "https://api.example.test/"
        )

    def test_editing_scope_creates_new_identity_without_mutating_old_value(
        self,
    ) -> None:
        before_digest = target_scope_digest(self.scope)
        changed = replace(
            self.scope, excluded_hosts=(TargetHostRule("api.example.test"),)
        )
        self.store.save(changed)
        loaded = self.store.load()
        assert loaded is not None
        self.assertNotEqual(target_scope_digest(loaded), before_digest)
        self.assertEqual(target_scope_digest(self.scope), before_digest)

    def test_replace_failure_preserves_old_snapshot_and_cleans_temporary(self) -> None:
        self.store.save(self.scope)
        before = self.path.read_bytes()
        with patch(
            "research.JsonFileResearchTargetScopeStore.os.replace",
            side_effect=OSError("disk"),
        ):
            with self.assertRaises(ResearchError):
                self.store.save(replace(self.scope, excluded_networks=()))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_fsync_failure_preserves_old_snapshot(self) -> None:
        self.store.save(self.scope)
        before = self.path.read_bytes()
        with patch(
            "research.JsonFileResearchTargetScopeStore.os.fsync",
            side_effect=OSError("disk"),
        ):
            with self.assertRaises(ResearchError):
                self.store.save(replace(self.scope, excluded_networks=()))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_cleanup_failure_does_not_mask_primary_write_error(self) -> None:
        self.store.save(self.scope)
        before = self.path.read_bytes()
        original_error = OSError("disk")
        with (
            patch(
                "research.JsonFileResearchTargetScopeStore.os.replace",
                side_effect=original_error,
            ),
            patch.object(Path, "unlink", side_effect=PermissionError("cleanup")),
            self.assertRaisesRegex(ResearchError, "write") as caught,
        ):
            self.store.save(replace(self.scope, excluded_networks=()))
        self.assertIs(caught.exception.__cause__, original_error)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(list(self.path.parent.glob("*.tmp"))), 1)
        self.assertEqual(self.store.load(), self.scope)

    def test_invalid_save_does_not_replace_or_create_files(self) -> None:
        with self.assertRaises(ResearchError):
            self.store.save(None)  # type: ignore[arg-type]
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_short_write_preserves_old_snapshot_and_removes_temporary(self) -> None:
        self.store.save(self.scope)
        before = self.path.read_bytes()
        temporary = tempfile.NamedTemporaryFile(
            mode="wb", dir=self.path.parent, suffix=".tmp", delete=False
        )
        with (
            patch(
                "research.JsonFileResearchTargetScopeStore.NamedTemporaryFile",
                return_value=temporary,
            ),
            patch.object(temporary, "write", return_value=0),
            self.assertRaises(ResearchError),
        ):
            self.store.save(replace(self.scope, excluded_networks=()))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_encode_overflow_is_rejected_before_touching_disk(self) -> None:
        self.store.save(self.scope)
        before = self.path.read_bytes()
        with (
            patch("research.ResearchTargetScopeCodec.MAX_TARGET_SCOPE_BYTES", 10),
            patch(
                "research.JsonFileResearchTargetScopeStore.NamedTemporaryFile"
            ) as temporary,
        ):
            with self.assertRaises(ResearchError):
                self.store.save(self.scope)
            temporary.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_truncated_valid_prefix_on_load_fails_safely(self) -> None:
        self.store.save(self.scope)
        original_bytes = self.path.read_bytes()

        self.path.write_bytes(original_bytes[: len(original_bytes) // 2])

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_corrupt_existing_snapshot_does_not_fall_back_to_absence(self) -> None:
        self.path.write_bytes(b"{bad json")
        with self.assertRaises(ResearchError):
            self.store.load()
        self.assertEqual(self.path.read_bytes(), b"{bad json")

    def test_oversized_store_is_read_with_a_hard_byte_limit(self) -> None:
        stream = Mock()
        stream.__enter__ = Mock(return_value=stream)
        stream.__exit__ = Mock(return_value=None)
        stream.read.return_value = b" " * (MAX_TARGET_SCOPE_BYTES + 1)
        with patch.object(Path, "open", return_value=stream):
            with self.assertRaises(ResearchError):
                self.store.load()
        stream.read.assert_called_once_with(MAX_TARGET_SCOPE_BYTES + 1)

    def test_unreadable_store_is_not_reported_as_missing(self) -> None:
        with patch.object(Path, "open", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(ResearchError, "read"):
                self.store.load()


class TargetScopeResolutionStatusTests(unittest.TestCase):
    def test_only_the_two_confident_statuses_settle(self) -> None:
        self.assertTrue(ResearchTargetScopeResolutionStatus.IN_SCOPE.settles)
        self.assertTrue(ResearchTargetScopeResolutionStatus.OUT_OF_SCOPE.settles)
        self.assertFalse(ResearchTargetScopeResolutionStatus.UNCERTAIN.settles)

    def test_exactly_three_values_exist(self) -> None:
        self.assertEqual(
            {member.value for member in ResearchTargetScopeResolutionStatus},
            {"in_scope", "out_of_scope", "uncertain"},
        )


class TargetScopeResolutionRecordTests(unittest.TestCase):
    """`matched_rule is None` iff `UNCERTAIN` is a structural invariant."""

    def test_uncertain_requires_no_matched_rule(self) -> None:
        ResearchTargetScopeResolution(
            status=ResearchTargetScopeResolutionStatus.UNCERTAIN,
            target="unknown.test",
            matched_rule=None,
            reason="No rule in this scope addresses this host.",
        )
        with self.assertRaises(ResearchError):
            ResearchTargetScopeResolution(
                status=ResearchTargetScopeResolutionStatus.UNCERTAIN,
                target="unknown.test",
                matched_rule="example.test",
                reason="No rule in this scope addresses this host.",
            )

    def test_settled_statuses_require_a_non_empty_matched_rule(self) -> None:
        for status in (
            ResearchTargetScopeResolutionStatus.IN_SCOPE,
            ResearchTargetScopeResolutionStatus.OUT_OF_SCOPE,
        ):
            with self.subTest(status=status):
                ResearchTargetScopeResolution(
                    status=status,
                    target="example.test",
                    matched_rule="example.test",
                    reason="Target host matches an explicitly allowed scope rule.",
                )
                with self.assertRaises(ResearchError):
                    ResearchTargetScopeResolution(
                        status=status,
                        target="example.test",
                        matched_rule=None,
                        reason="Target host matches an explicitly allowed scope rule.",
                    )
                with self.assertRaises(ResearchError):
                    ResearchTargetScopeResolution(
                        status=status,
                        target="example.test",
                        matched_rule="   ",
                        reason="Target host matches an explicitly allowed scope rule.",
                    )

    def test_empty_or_oversized_target_and_reason_are_rejected(self) -> None:
        for target, reason in (("", "reason"), ("target", ""), ("x" * 501, "reason")):
            with self.subTest(target=target, reason=reason):
                with self.assertRaises(ResearchError):
                    ResearchTargetScopeResolution(
                        status=ResearchTargetScopeResolutionStatus.UNCERTAIN,
                        target=target,
                        matched_rule=None,
                        reason=reason,
                    )


class TargetScopeResolveHostnameTests(unittest.TestCase):
    def test_exact_host_match_is_in_scope_citing_the_exact_rule(self) -> None:
        scope = ResearchTargetScope(allowed_hosts=(TargetHostRule("example.test"),))

        resolution = scope.resolve_hostname("example.test")

        self.assertEqual(
            resolution.status, ResearchTargetScopeResolutionStatus.IN_SCOPE
        )
        self.assertEqual(resolution.target, "example.test")
        self.assertEqual(resolution.matched_rule, "example.test")

    def test_subdomain_only_wildcard_matches_a_subdomain_but_not_the_apex(
        self,
    ) -> None:
        scope = ResearchTargetScope(
            allowed_hosts=(TargetHostRule("example.test", True),)
        )

        subdomain = scope.resolve_hostname("api.example.test")
        apex = scope.resolve_hostname("example.test")

        self.assertEqual(subdomain.status, ResearchTargetScopeResolutionStatus.IN_SCOPE)
        self.assertEqual(subdomain.matched_rule, "*.example.test")
        self.assertEqual(apex.status, ResearchTargetScopeResolutionStatus.UNCERTAIN)
        self.assertIsNone(apex.matched_rule)

    def test_apex_rule_plus_subdomain_rule_together_cover_both(self) -> None:
        scope = ResearchTargetScope(
            allowed_hosts=(
                TargetHostRule("example.test"),
                TargetHostRule("example.test", True),
            )
        )

        self.assertEqual(
            scope.resolve_hostname("example.test").status,
            ResearchTargetScopeResolutionStatus.IN_SCOPE,
        )
        self.assertEqual(
            scope.resolve_hostname("api.example.test").status,
            ResearchTargetScopeResolutionStatus.IN_SCOPE,
        )

    def test_suffix_trick_does_not_match_a_similarly_spelled_domain(self) -> None:
        scope = ResearchTargetScope(allowed_hosts=(TargetHostRule("example.test"),))

        # attackerexample.test ends with "example.test" as a raw string, but
        # is not a subdomain of it and must never be treated as in scope.
        resolution = scope.resolve_hostname("attackerexample.test")

        self.assertEqual(
            resolution.status, ResearchTargetScopeResolutionStatus.UNCERTAIN
        )
        self.assertIsNone(resolution.matched_rule)

    def test_suffix_trick_does_not_match_a_subdomain_wildcard_rule(self) -> None:
        scope = ResearchTargetScope(
            allowed_hosts=(TargetHostRule("example.test", subdomains_only=True),)
        )

        # notexample.test ends with "example.test" as a raw string, but is
        # not a subdomain of it (no "." boundary) and must never be treated
        # as in scope, even though the rule allows any *.example.test host.
        resolution = scope.resolve_hostname("notexample.test")

        self.assertEqual(
            resolution.status, ResearchTargetScopeResolutionStatus.UNCERTAIN
        )
        self.assertIsNone(resolution.matched_rule)

    def test_lookalike_domain_does_not_match(self) -> None:
        scope = ResearchTargetScope(allowed_hosts=(TargetHostRule("example.test"),))

        resolution = scope.resolve_hostname("examp1e.test")

        self.assertEqual(
            resolution.status, ResearchTargetScopeResolutionStatus.UNCERTAIN
        )

    def test_literal_ip_allow_and_exclude_cite_the_exact_network(self) -> None:
        scope = ResearchTargetScope(
            allowed_hosts=(TargetHostRule("example.test"),),
            allowed_networks=("93.184.216.0/24",),
            excluded_networks=("93.184.216.35/32",),
        )

        allowed = scope.resolve_hostname("93.184.216.34")
        excluded = scope.resolve_hostname("93.184.216.35")
        unaddressed = scope.resolve_hostname("8.8.8.8")

        self.assertEqual(allowed.status, ResearchTargetScopeResolutionStatus.IN_SCOPE)
        self.assertEqual(allowed.matched_rule, "93.184.216.0/24")
        self.assertEqual(
            excluded.status, ResearchTargetScopeResolutionStatus.OUT_OF_SCOPE
        )
        self.assertEqual(excluded.matched_rule, "93.184.216.35/32")
        self.assertEqual(
            unaddressed.status, ResearchTargetScopeResolutionStatus.UNCERTAIN
        )
        self.assertIsNone(unaddressed.matched_rule)

    def test_exclusion_wins_over_inclusion_for_hosts(self) -> None:
        scope = scope_fixture()

        for hostname in ("pay.example.test", "deep.pay.example.test"):
            with self.subTest(hostname=hostname):
                resolution = scope.resolve_hostname(hostname)
                self.assertEqual(
                    resolution.status,
                    ResearchTargetScopeResolutionStatus.OUT_OF_SCOPE,
                )

    def test_a_host_addressed_by_no_rule_is_uncertain_never_out_of_scope(
        self,
    ) -> None:
        scope = ResearchTargetScope(allowed_hosts=(TargetHostRule("example.test"),))

        resolution = scope.resolve_hostname("totally-unrelated.test")

        self.assertEqual(
            resolution.status, ResearchTargetScopeResolutionStatus.UNCERTAIN
        )
        self.assertIsNone(resolution.matched_rule)
        self.assertIn("no rule", resolution.reason.lower())

    def test_discovery_by_redirect_cname_cdn_or_ct_log_never_implies_scope(
        self,
    ) -> None:
        """A hostname merely observed, never authored into a rule, is UNCERTAIN.

        Simulates the shapes a redirect target, a CNAME answer, a third-party
        CDN/API host, or a certificate-transparency log entry would take —
        none of them were ever added to this scope's rules, so none of them
        may be read as settled, in either direction.
        """
        scope = ResearchTargetScope(allowed_hosts=(TargetHostRule("example.test"),))
        discovered_hostnames = (
            "redirect-target.example-cdn.net",  # a redirect Location host
            "example.test.edge.cdn-provider.net",  # a CNAME answer
            "api.third-party-vendor.test",  # a third-party API host
            "new-subdomain.example.test",  # a CT-log-discovered subdomain
        )

        for hostname in discovered_hostnames:
            with self.subTest(hostname=hostname):
                resolution = scope.resolve_hostname(hostname)
                self.assertEqual(
                    resolution.status,
                    ResearchTargetScopeResolutionStatus.UNCERTAIN,
                )

    def test_invalid_hostname_input_still_raises_like_require_hostname(self) -> None:
        scope = scope_fixture()
        with self.assertRaises(ResearchError):
            scope.resolve_hostname("host%with%percent")
        with self.assertRaises(ResearchError):
            scope.resolve_hostname(123)  # type: ignore[arg-type]

    def test_restart_reload_produces_identical_resolutions(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "scope.json"
        scope = scope_fixture()
        store = JsonFileResearchTargetScopeStore(path)
        store.save(scope)

        reloaded = JsonFileResearchTargetScopeStore(path).load()
        assert reloaded is not None

        for hostname in (
            "example.test",
            "api.example.test",
            "pay.example.test",
            "unaddressed.test",
        ):
            with self.subTest(hostname=hostname):
                self.assertEqual(
                    scope.resolve_hostname(hostname),
                    reloaded.resolve_hostname(hostname),
                )

    def test_legacy_persisted_scope_resolves_unchanged(self) -> None:
        """A scope decoded from its existing (only) schema resolves identically.

        The resolver adds no field and reads nothing beyond the scope's
        already-persisted shape, so a scope reconstructed purely from its own
        stored document must resolve exactly like the in-memory original.
        """
        scope = scope_fixture()
        decoded = decode_target_scope(encode_target_scope(scope))

        for hostname in ("example.test", "pay.example.test", "unaddressed.test"):
            with self.subTest(hostname=hostname):
                self.assertEqual(
                    scope.resolve_hostname(hostname),
                    decoded.resolve_hostname(hostname),
                )


class TargetScopeResolveAddressesTests(unittest.TestCase):
    def test_mirrors_the_network_only_allow_exclude_and_unaddressed_cases(
        self,
    ) -> None:
        scope = ResearchTargetScope(
            allowed_hosts=(TargetHostRule("example.test"),),
            allowed_networks=("93.184.216.0/24",),
            excluded_networks=("93.184.216.35/32",),
        )

        resolutions = scope.resolve_addresses(
            ("93.184.216.34", "93.184.216.35", "8.8.8.8")
        )

        self.assertEqual(
            [resolution.status for resolution in resolutions],
            [
                ResearchTargetScopeResolutionStatus.IN_SCOPE,
                ResearchTargetScopeResolutionStatus.OUT_OF_SCOPE,
                ResearchTargetScopeResolutionStatus.UNCERTAIN,
            ],
        )
        self.assertEqual(resolutions[0].matched_rule, "93.184.216.0/24")
        self.assertEqual(resolutions[1].matched_rule, "93.184.216.35/32")
        self.assertIsNone(resolutions[2].matched_rule)

    def test_exclusion_wins_over_inclusion_for_an_address_in_both(self) -> None:
        scope = ResearchTargetScope(
            allowed_hosts=(TargetHostRule("example.test"),),
            allowed_networks=("93.184.216.0/24",),
            excluded_networks=("93.184.216.0/28",),
        )

        resolution = scope.resolve_addresses(("93.184.216.5",))[0]

        self.assertEqual(
            resolution.status, ResearchTargetScopeResolutionStatus.OUT_OF_SCOPE
        )
        self.assertEqual(resolution.matched_rule, "93.184.216.0/28")

    def test_invalid_address_set_still_raises_like_require_addresses(self) -> None:
        scope = scope_fixture()
        with self.assertRaises(ResearchError):
            scope.resolve_addresses(())
        with self.assertRaises(ResearchError):
            scope.resolve_addresses(("not-an-address",))

    def test_restart_reload_produces_identical_address_resolutions(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "scope.json"
        scope = scope_fixture()
        JsonFileResearchTargetScopeStore(path).save(scope)
        reloaded = JsonFileResearchTargetScopeStore(path).load()
        assert reloaded is not None

        addresses = ("93.184.216.34", "93.184.216.35", "2606:4700::1")
        self.assertEqual(
            scope.resolve_addresses(addresses),
            reloaded.resolve_addresses(addresses),
        )


if __name__ == "__main__":
    unittest.main()
