"""Program-scope revisions remain exact, bounded, human and immutable."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.Exceptions import ResearchError
from research.JsonFileResearchProgramScopeRevisionStore import (
    JsonFileResearchProgramScopeRevisionStore,
)
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchProgramScopeRevision import (
    MAX_PROGRAM_SCOPE_PROGRAM_ID_CHARACTERS,
    MAX_PROGRAM_SCOPE_REVISION_ID_CHARACTERS,
    MAX_PROGRAM_SCOPE_REVISION_VALIDITY_SECONDS,
    PROGRAM_SCOPE_CAPABILITIES,
    PROGRAM_SCOPE_TRANSPORT,
    ResearchProgramScopeRevision,
)
from research.ResearchProgramScopeRevisionCodec import (
    decode_program_scope_revisions,
    encode_program_scope_revisions,
)
from research.ResearchTargetScope import ResearchTargetScope, TargetHostRule
from research.ResearchTargetScopeCodec import target_scope_digest

_CONFIRMED = datetime(2026, 9, 5, 10, tzinfo=UTC)


def scope_fixture(host: str = "example.test") -> ResearchTargetScope:
    return ResearchTargetScope(
        allowed_hosts=(TargetHostRule(host), TargetHostRule(host, True)),
        excluded_hosts=(TargetHostRule(f"admin.{host}"),),
        allowed_networks=("93.184.216.0/24",),
        excluded_networks=("93.184.216.35/32",),
    )


def revision_fixture(
    revision_id: str = "revision-1",
    program_id: str = "program-a",
    *,
    scope: ResearchTargetScope | None = None,
    confirmed_at: datetime = _CONFIRMED,
    expires_at: datetime | None = None,
) -> ResearchProgramScopeRevision:
    return ResearchProgramScopeRevision(
        revision_id=revision_id,
        program_id=program_id,
        scope=scope or scope_fixture(),
        confirmed_at=confirmed_at,
        expires_at=expires_at or confirmed_at + timedelta(hours=1),
    )


class ProgramScopeRevisionTests(unittest.TestCase):
    def test_confirmation_derives_identity_and_fixed_audit_facts(self) -> None:
        revision = revision_fixture("  revision-1  ", "  program-a  ")
        self.assertEqual(revision.revision_id, "revision-1")
        self.assertEqual(revision.program_id, "program-a")
        self.assertEqual(revision.scope_digest, target_scope_digest(revision.scope))
        self.assertEqual(len(revision.revision_digest), 64)
        self.assertEqual(
            revision.capabilities,
            frozenset(
                {
                    ResearchPlanStepCapability.SOURCE_FETCH,
                    ResearchPlanStepCapability.SOURCE_ACCEPT,
                }
            ),
        )
        self.assertEqual(revision.capabilities, PROGRAM_SCOPE_CAPABILITIES)
        self.assertEqual(revision.transport, PROGRAM_SCOPE_TRANSPORT)
        self.assertIs(revision.confirmed_by, ResearchAuthorizer.HUMAN)

    def test_derived_and_fixed_facts_are_not_caller_parameters(self) -> None:
        values = {
            "revision_id": "revision-1",
            "program_id": "program-a",
            "scope": scope_fixture(),
            "confirmed_at": _CONFIRMED,
            "expires_at": _CONFIRMED + timedelta(hours=1),
        }
        for field, value in (
            ("scope_digest", "0" * 64),
            ("revision_digest", "0" * 64),
            ("capabilities", frozenset()),
            ("transport", "http:80"),
            ("confirmed_by", ResearchAuthorizer.HUMAN),
        ):
            with self.subTest(field=field), self.assertRaises(TypeError):
                ResearchProgramScopeRevision(**values, **{field: value})  # type: ignore[arg-type]

    def test_revision_is_frozen(self) -> None:
        revision = revision_fixture()
        with self.assertRaises(FrozenInstanceError):
            revision.program_id = "changed"  # type: ignore[misc]

    def test_ids_are_nonempty_and_bounded(self) -> None:
        for field, value in (
            ("revision_id", " "),
            ("program_id", ""),
            (
                "revision_id",
                "r" * (MAX_PROGRAM_SCOPE_REVISION_ID_CHARACTERS + 1),
            ),
            (
                "program_id",
                "p" * (MAX_PROGRAM_SCOPE_PROGRAM_ID_CHARACTERS + 1),
            ),
        ):
            values = {
                "revision_id": "revision-1",
                "program_id": "program-a",
                "scope": scope_fixture(),
                "confirmed_at": _CONFIRMED,
                "expires_at": _CONFIRMED + timedelta(hours=1),
            }
            values[field] = value
            with self.subTest(field=field), self.assertRaises(ResearchError):
                ResearchProgramScopeRevision(**values)  # type: ignore[arg-type]

    def test_confirmation_window_is_aware_positive_and_at_most_one_hour(self) -> None:
        self.assertEqual(MAX_PROGRAM_SCOPE_REVISION_VALIDITY_SECONDS, 3600.0)
        self.assertEqual(
            revision_fixture().expires_at, _CONFIRMED + timedelta(seconds=3600)
        )
        invalid = (
            (_CONFIRMED.replace(tzinfo=None), _CONFIRMED + timedelta(minutes=1)),
            (_CONFIRMED, (_CONFIRMED + timedelta(minutes=1)).replace(tzinfo=None)),
            (_CONFIRMED, _CONFIRMED),
            (_CONFIRMED, _CONFIRMED + timedelta(seconds=3600, microseconds=1)),
        )
        for confirmed_at, expires_at in invalid:
            with (
                self.subTest(confirmed_at=confirmed_at, expires_at=expires_at),
                self.assertRaises(ResearchError),
            ):
                revision_fixture(confirmed_at=confirmed_at, expires_at=expires_at)

    def test_validity_ceiling_uses_elapsed_time_across_offset_changes(self) -> None:
        before_fallback = datetime(
            2026, 10, 25, 2, 30, tzinfo=timezone(timedelta(hours=2))
        )
        after_fallback = datetime(
            2026, 10, 25, 2, 31, tzinfo=timezone(timedelta(hours=1))
        )
        with self.assertRaisesRegex(ResearchError, "ceiling"):
            revision_fixture(
                confirmed_at=before_fallback,
                expires_at=after_fallback,
            )

    def test_active_is_revocation_state_and_valid_at_also_checks_expiry(self) -> None:
        revision = revision_fixture()
        self.assertTrue(revision.active)
        self.assertFalse(revision.valid_at(_CONFIRMED - timedelta(microseconds=1)))
        self.assertTrue(revision.valid_at(_CONFIRMED))
        self.assertTrue(
            revision.valid_at(revision.expires_at - timedelta(microseconds=1))
        )
        self.assertFalse(revision.valid_at(revision.expires_at))
        with self.assertRaises(ResearchError):
            revision.valid_at(_CONFIRMED.replace(tzinfo=None))

    def test_human_revocation_returns_a_new_digest_bound_value(self) -> None:
        revision = revision_fixture()
        at = _CONFIRMED + timedelta(minutes=10)
        revoked = revision.revoked(at)
        self.assertTrue(revision.active)
        self.assertFalse(revoked.active)
        self.assertEqual(revoked.state, "revoked")
        self.assertEqual(revoked.scope_digest, revision.scope_digest)
        self.assertNotEqual(revoked.revision_digest, revision.revision_digest)
        self.assertEqual(revoked.revoked_at, at)
        self.assertIs(revoked.revoked_by, ResearchAuthorizer.HUMAN)
        self.assertFalse(revoked.valid_at(_CONFIRMED + timedelta(minutes=1)))
        with self.assertRaises(ResearchError):
            revoked.revoked(at + timedelta(minutes=1))

    def test_direct_revocation_requires_complete_human_provenance(self) -> None:
        values = {
            "revision_id": "revision-1",
            "program_id": "program-a",
            "scope": scope_fixture(),
            "confirmed_at": _CONFIRMED,
            "expires_at": _CONFIRMED + timedelta(hours=1),
        }
        for additions in (
            {"revoked_at": _CONFIRMED + timedelta(minutes=1)},
            {"revoked_by": ResearchAuthorizer.HUMAN},
            {
                "revoked_at": _CONFIRMED - timedelta(microseconds=1),
                "revoked_by": ResearchAuthorizer.HUMAN,
            },
        ):
            with self.subTest(additions=additions), self.assertRaises(ResearchError):
                ResearchProgramScopeRevision(**values, **additions)  # type: ignore[arg-type]

    def test_revision_digest_covers_scope_expiry_identity_and_revocation(self) -> None:
        baseline = revision_fixture()
        variants = (
            revision_fixture("revision-2"),
            revision_fixture(program_id="program-b"),
            revision_fixture(scope=scope_fixture("other.test")),
            revision_fixture(expires_at=_CONFIRMED + timedelta(minutes=59)),
            baseline.revoked(_CONFIRMED + timedelta(minutes=5)),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(baseline.revision_digest, variant.revision_digest)


class ProgramScopeRevisionCodecTests(unittest.TestCase):
    def history(self) -> list[ResearchProgramScopeRevision]:
        first = revision_fixture().revoked(_CONFIRMED + timedelta(minutes=10))
        replacement = revision_fixture(
            "revision-2",
            confirmed_at=_CONFIRMED + timedelta(minutes=10),
            expires_at=_CONFIRMED + timedelta(minutes=50),
        )
        other = revision_fixture("revision-b", "program-b")
        return [first, replacement, other]

    def test_round_trip_preserves_multi_program_revision_history(self) -> None:
        revisions = self.history()
        loaded = decode_program_scope_revisions(
            encode_program_scope_revisions(revisions)
        )
        self.assertEqual(loaded, revisions)
        document = json.loads(encode_program_scope_revisions(revisions))
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(
            document["revisions"][0]["capabilities"],
            ["source_accept", "source_fetch"],
        )
        self.assertEqual(document["revisions"][0]["transport"], PROGRAM_SCOPE_TRANSPORT)
        self.assertEqual(document["revisions"][0]["confirmed_by"], "human")

    def test_fixed_audit_facts_and_derived_state_are_strict_on_decode(self) -> None:
        for field, value in (
            ("capabilities", ["source_fetch"]),
            ("capabilities", ["source_fetch", "source_accept"]),
            ("transport", "https:8443"),
            ("confirmed_by", "model"),
            ("state", "active"),
            ("scope_digest", "0" * 64),
            ("revision_digest", "0" * 64),
        ):
            document = json.loads(encode_program_scope_revisions(self.history()))
            document["revisions"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ResearchError):
                decode_program_scope_revisions(json.dumps(document).encode())

    def test_authority_field_changes_fail_without_a_matching_revision_digest(
        self,
    ) -> None:
        document = json.loads(encode_program_scope_revisions([revision_fixture()]))
        document["revisions"][0]["expires_at"] = (
            _CONFIRMED + timedelta(minutes=59)
        ).isoformat()
        with self.assertRaisesRegex(ResearchError, "digest"):
            decode_program_scope_revisions(json.dumps(document).encode())

    def test_scope_changes_fail_at_the_nested_scope_digest(self) -> None:
        document = json.loads(encode_program_scope_revisions([revision_fixture()]))
        document["revisions"][0]["scope"]["scope"]["excluded_hosts"] = []
        with self.assertRaisesRegex(ResearchError, "digest"):
            decode_program_scope_revisions(json.dumps(document).encode())

    def test_unknown_and_missing_fields_fail_closed_at_each_level(self) -> None:
        for level in ("root", "entry", "scope"):
            for missing in (False, True):
                document = json.loads(
                    encode_program_scope_revisions([revision_fixture()])
                )
                target = document
                if level == "entry":
                    target = document["revisions"][0]
                elif level == "scope":
                    target = document["revisions"][0]["scope"]["scope"]
                if missing:
                    target.pop(next(iter(target)))
                else:
                    target["unsupported_permission"] = True
                with (
                    self.subTest(level=level, missing=missing),
                    self.assertRaises(ResearchError),
                ):
                    decode_program_scope_revisions(json.dumps(document).encode())

    def test_duplicate_fields_are_rejected_at_root_entry_and_scope_levels(self) -> None:
        payload = encode_program_scope_revisions([revision_fixture()])
        replacements = (
            (
                b'"schema_version": 1',
                b'"schema_version": 1, "schema_version": 1',
            ),
            (
                b'"program_id": "program-a"',
                b'"program_id": "program-a", "program_id": "program-a"',
            ),
            (
                b'"allowed_networks": [',
                b'"allowed_networks": [], "allowed_networks": [',
            ),
        )
        for original, duplicate in replacements:
            with (
                self.subTest(original=original),
                self.assertRaisesRegex(ResearchError, "duplicate"),
            ):
                decode_program_scope_revisions(payload.replace(original, duplicate, 1))

    def test_schema_type_and_corrupt_bytes_are_rejected(self) -> None:
        for version in (True, 1.0, "1", None, 0, 2):
            document = json.loads(encode_program_scope_revisions([revision_fixture()]))
            document["schema_version"] = version
            with self.subTest(version=version), self.assertRaises(ResearchError):
                decode_program_scope_revisions(json.dumps(document).encode())
        for payload in (b"", b"{", b"\xff", b"null", b"[]", b"[" * 2000):
            with self.subTest(payload=payload[:10]), self.assertRaises(ResearchError):
                decode_program_scope_revisions(payload)

    def test_byte_and_entry_limits_are_checked_before_unbounded_work(self) -> None:
        with (
            patch(
                "research.ResearchProgramScopeRevisionCodec."
                "MAX_PROGRAM_SCOPE_REVISION_STORE_BYTES",
                10,
            ),
            patch("research.ResearchProgramScopeRevisionCodec.json.loads") as loads,
            self.assertRaises(ResearchError),
        ):
            decode_program_scope_revisions(b" " * 11)
        loads.assert_not_called()

        with (
            patch(
                "research.ResearchProgramScopeRevisionCodec."
                "MAX_PROGRAM_SCOPE_REVISIONS",
                0,
            ),
            self.assertRaisesRegex(ResearchError, "too many"),
        ):
            encode_program_scope_revisions([revision_fixture()])

    def test_duplicate_ids_and_unrevoked_replacement_are_rejected(self) -> None:
        for revisions in (
            [revision_fixture(), revision_fixture(program_id="program-b")],
            [revision_fixture(), revision_fixture("revision-2")],
        ):
            with self.subTest(revisions=revisions), self.assertRaises(ResearchError):
                encode_program_scope_revisions(revisions)

    def test_replacement_must_follow_explicit_prior_revocation(self) -> None:
        revoked_at = _CONFIRMED + timedelta(minutes=10)
        first = revision_fixture().revoked(revoked_at)
        before = revision_fixture(
            "revision-2",
            confirmed_at=revoked_at - timedelta(microseconds=1),
            expires_at=revoked_at + timedelta(minutes=20),
        )
        with self.assertRaisesRegex(ResearchError, "predates"):
            encode_program_scope_revisions([first, before])

    def test_future_revision_fields_require_a_new_schema(self) -> None:
        @dataclass(frozen=True, slots=True)
        class FutureRevision(ResearchProgramScopeRevision):
            request_budget: int = 1

        revision = FutureRevision(
            revision_id="revision-1",
            program_id="program-a",
            scope=scope_fixture(),
            confirmed_at=_CONFIRMED,
            expires_at=_CONFIRMED + timedelta(hours=1),
        )
        with self.assertRaisesRegex(ResearchError, "schema"):
            encode_program_scope_revisions([revision])


class ProgramScopeRevisionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "nested" / "scope-revisions.json"
        self.store = JsonFileResearchProgramScopeRevisionStore(self.path)

    def test_absence_is_empty_history_and_performs_no_write(self) -> None:
        self.assertEqual(self.store.load(), [])
        self.assertFalse(self.path.exists())

    def test_restart_restores_revocation_history_and_current_revision(self) -> None:
        revoked_at = _CONFIRMED + timedelta(minutes=10)
        first = revision_fixture()
        replacement = revision_fixture(
            "revision-2",
            confirmed_at=revoked_at,
            expires_at=revoked_at + timedelta(minutes=40),
        )
        self.store.save([first])
        self.store.save([first.revoked(revoked_at), replacement])
        loaded = JsonFileResearchProgramScopeRevisionStore(self.path).load()
        self.assertEqual(loaded, [first.revoked(revoked_at), replacement])
        self.assertFalse(loaded[0].active)
        self.assertTrue(loaded[1].active)

    def test_replacement_requires_the_persisted_revision_to_be_revoked(self) -> None:
        first = revision_fixture()
        self.store.save([first])
        replacement = revision_fixture(
            "revision-2",
            confirmed_at=_CONFIRMED + timedelta(minutes=10),
            expires_at=_CONFIRMED + timedelta(minutes=50),
        )
        before = self.path.read_bytes()
        with self.assertRaises(ResearchError):
            self.store.save([first, replacement])
        self.assertEqual(self.path.read_bytes(), before)

    def test_existing_entries_cannot_be_removed_mutated_or_unrevoked(self) -> None:
        at = _CONFIRMED + timedelta(minutes=10)
        first = revision_fixture()
        revoked = first.revoked(at)
        self.store.save([revoked])
        attempts: tuple[list[ResearchProgramScopeRevision], ...] = (
            [],
            [first],
            [first.revoked(at + timedelta(minutes=1))],
            [replace(revoked, expires_at=revoked.expires_at - timedelta(minutes=1))],
        )
        before = self.path.read_bytes()
        for attempt in attempts:
            with self.subTest(attempt=attempt), self.assertRaises(ResearchError):
                self.store.save(attempt)
            self.assertEqual(self.path.read_bytes(), before)

    def test_replace_failure_preserves_old_history_and_cleans_temporary(self) -> None:
        first = revision_fixture()
        self.store.save([first])
        before = self.path.read_bytes()
        revoked = first.revoked(_CONFIRMED + timedelta(minutes=10))
        with patch(
            "research.JsonFileResearchProgramScopeRevisionStore.os.replace",
            side_effect=OSError("disk"),
        ):
            with self.assertRaisesRegex(ResearchError, "write"):
                self.store.save([revoked])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_corrupt_existing_history_blocks_overwrite(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"{bad json")
        with self.assertRaises(ResearchError):
            self.store.save([revision_fixture()])
        self.assertEqual(self.path.read_bytes(), b"{bad json")


if __name__ == "__main__":
    unittest.main()
