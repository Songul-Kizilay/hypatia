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


if __name__ == "__main__":
    unittest.main()
