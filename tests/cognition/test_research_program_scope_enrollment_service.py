from __future__ import annotations

import ast
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from cognition.ResearchProgramScopeEnrollmentService import (
    MAX_PENDING_PROGRAM_SCOPE_PREVIEWS,
    ResearchProgramScopeEnrollmentService,
)
from core.Exceptions import ResearchError
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchProgramScopeEnrollmentPreview import (
    PROGRAM_SCOPE_CREATE_ACTION,
    PROGRAM_SCOPE_REVOKE_ACTION,
)
from research.ResearchProgramScopeExecutionPolicy import (
    ResearchProgramScopeCheckClass,
    ResearchProgramScopeExecutionPolicy,
)
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from research.ResearchTargetScope import ResearchTargetScope, TargetHostRule

_NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)


def scope(host: str = "example.test") -> ResearchTargetScope:
    return ResearchTargetScope(
        allowed_hosts=(TargetHostRule(host),),
        excluded_hosts=(TargetHostRule(f"admin.{host}"),),
    )


def revision(
    revision_id: str = "revision-1",
    program_id: str = "program-a",
    *,
    confirmed_at: datetime = _NOW,
) -> ResearchProgramScopeRevision:
    return ResearchProgramScopeRevision(
        revision_id=revision_id,
        program_id=program_id,
        scope=scope(),
        confirmed_at=confirmed_at,
        expires_at=confirmed_at + timedelta(hours=1),
    )


class MemoryStore:
    def __init__(
        self,
        values: list[ResearchProgramScopeRevision] | None = None,
        *,
        load_error: Exception | None = None,
        save_error: Exception | None = None,
    ) -> None:
        self.values = list(values or [])
        self.load_error = load_error
        self.save_error = save_error
        self.load_calls = 0
        self.save_calls: list[list[ResearchProgramScopeRevision]] = []

    def load(self) -> list[ResearchProgramScopeRevision]:
        self.load_calls += 1
        if self.load_error is not None:
            raise self.load_error
        return list(self.values)

    def save(self, values: list[ResearchProgramScopeRevision]) -> None:
        self.save_calls.append(list(values))
        if self.save_error is not None:
            raise self.save_error
        self.values = list(values)


class ProgramScopeEnrollmentServiceTests(unittest.TestCase):
    def service(
        self,
        store: MemoryStore | None = None,
        *,
        now: datetime = _NOW,
        ids: list[str] | None = None,
    ) -> ResearchProgramScopeEnrollmentService:
        identities = iter(ids or ["revision-new"])
        return ResearchProgramScopeEnrollmentService(
            store or MemoryStore(),
            clock=lambda: now,
            id_factory=lambda: next(identities),
        )

    def test_startup_restores_bounded_history_and_preserves_order(self) -> None:
        first = revision().revoked(_NOW + timedelta(minutes=5))
        second = revision("revision-2", confirmed_at=_NOW + timedelta(minutes=5))
        other = revision("revision-b", "program-b")
        store = MemoryStore([first, second, other])

        service = self.service(store)

        self.assertEqual(service.revisions(), (first, second, other))
        self.assertEqual(store.load_calls, 1)
        self.assertEqual(store.save_calls, [])

    def test_absent_history_is_empty_and_does_not_write(self) -> None:
        store = MemoryStore()
        service = self.service(store)
        self.assertEqual(service.revisions(), ())
        self.assertEqual(store.save_calls, [])

    def test_missing_or_corrupt_load_fails_closed(self) -> None:
        for error in (ResearchError("corrupt"), OSError("missing")):
            with self.subTest(error=error), self.assertRaises(ResearchError):
                self.service(MemoryStore(load_error=error))

    def test_unbounded_or_non_list_load_fails_closed(self) -> None:
        with (
            patch(
                "cognition.ResearchProgramScopeEnrollmentService."
                "MAX_PROGRAM_SCOPE_REVISIONS",
                0,
            ),
            self.assertRaisesRegex(ResearchError, "too large"),
        ):
            self.service(MemoryStore([revision()]))

        class TupleStore(MemoryStore):
            def load(self) -> list[ResearchProgramScopeRevision]:
                return (revision(),)  # type: ignore[return-value]

        with self.assertRaisesRegex(ResearchError, "invalid"):
            self.service(TupleStore())

    def test_create_preview_is_exact_immutable_and_has_no_write(self) -> None:
        store = MemoryStore()
        service = self.service(store, ids=["revision-created"])

        preview = service.preview_create(" program-a ", scope())

        self.assertEqual(preview.action, PROGRAM_SCOPE_CREATE_ACTION)
        self.assertEqual(preview.revision.revision_id, "revision-created")
        self.assertEqual(preview.revision.program_id, "program-a")
        self.assertEqual(preview.revision.confirmed_at, _NOW)
        self.assertEqual(preview.revision.expires_at, _NOW + timedelta(hours=1))
        self.assertTrue(preview.revision.active)
        self.assertEqual(service.revisions(), ())
        self.assertEqual(store.save_calls, [])
        with self.assertRaises(FrozenInstanceError):
            preview.action = "revoke"  # type: ignore[misc]

    def test_create_preview_records_exact_execution_policy_without_running(
        self,
    ) -> None:
        store = MemoryStore()
        service = self.service(store, ids=["revision-created"])
        policy = ResearchProgramScopeExecutionPolicy(
            permitted_check_classes=(
                ResearchProgramScopeCheckClass.PUBLIC_HTTPS_CONTENT,
                ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP,
            ),
            permitted_ports=(443,),
            max_request_count=2,
            max_requests_per_minute=1,
            max_seconds=30.0,
        )

        preview = service.preview_create(
            "program-a",
            scope(),
            execution_policy=policy,
        )

        self.assertEqual(preview.revision.execution_policy, policy)
        self.assertEqual(service.revisions(), ())
        self.assertEqual(store.save_calls, [])

    def test_create_confirmation_persists_previewed_value_then_publishes(self) -> None:
        store = MemoryStore()
        service = self.service(store)
        preview = service.preview_create(
            "program-a", scope(), expires_at=_NOW + timedelta(minutes=20)
        )

        confirmed = service.confirm_create(
            preview.revision.revision_id, preview.revision.revision_digest
        )

        self.assertIs(confirmed, preview.revision)
        self.assertEqual(store.save_calls, [[preview.revision]])
        self.assertEqual(service.revisions(), (preview.revision,))

    def test_create_confirmation_rejects_tamper_unknown_and_replay(self) -> None:
        service = self.service()
        preview = service.preview_create("program-a", scope())
        for identity, digest in (
            ("other", preview.revision.revision_digest),
            (preview.revision.revision_id, "0" * 64),
        ):
            with self.subTest(identity=identity), self.assertRaises(ResearchError):
                service.confirm_create(identity, digest)
        service.confirm_create(
            preview.revision.revision_id, preview.revision.revision_digest
        )
        with self.assertRaises(ResearchError):
            service.confirm_create(
                preview.revision.revision_id, preview.revision.revision_digest
            )

    def test_expired_create_preview_is_stale_and_never_persisted(self) -> None:
        moments = iter((_NOW, _NOW + timedelta(minutes=2)))
        store = MemoryStore()
        service = ResearchProgramScopeEnrollmentService(
            store,
            clock=lambda: next(moments),
            id_factory=lambda: "revision-new",
        )
        preview = service.preview_create(
            "program-a",
            scope(),
            expires_at=_NOW + timedelta(minutes=1),
        )
        with self.assertRaisesRegex(ResearchError, "stale"):
            service.confirm_create(
                preview.revision.revision_id, preview.revision.revision_digest
            )
        self.assertEqual(service.revisions(), ())
        self.assertEqual(store.save_calls, [])
        with self.assertRaises(ResearchError):
            service.confirm_create(
                preview.revision.revision_id, preview.revision.revision_digest
            )

    def test_active_revision_blocks_new_preview_until_revoke_confirmed(self) -> None:
        current = revision()
        service = self.service(MemoryStore([current]), ids=["revision-2"])
        with self.assertRaisesRegex(ResearchError, "revoke it first"):
            service.preview_create("program-a", scope("other.test"))

        revoke = service.preview_revoke(current.revision_id, current.revision_digest)
        with self.assertRaisesRegex(ResearchError, "revoke it first"):
            service.preview_create("program-a", scope("other.test"))

        service.confirm_revoke(
            revoke.revision.revision_id, revoke.revision.revision_digest
        )
        successor = service.preview_create("program-a", scope("other.test"))
        self.assertEqual(successor.revision.revision_id, "revision-2")

    def test_duplicate_pending_create_and_revision_identity_are_rejected(self) -> None:
        service = self.service(ids=["revision-new", "revision-other"])
        service.preview_create("program-a", scope())
        with self.assertRaisesRegex(ResearchError, "awaiting confirmation"):
            service.preview_create("program-a", scope("other.test"))

        current = revision()
        duplicate = self.service(
            MemoryStore([current.revoked(_NOW + timedelta(minutes=1))]),
            now=_NOW + timedelta(minutes=1),
            ids=[current.revision_id],
        )
        with self.assertRaisesRegex(ResearchError, "identity already exists"):
            duplicate.preview_create("program-a", scope("other.test"))

    def test_pending_previews_are_bounded_across_actions(self) -> None:
        current = revision()
        service = self.service(
            MemoryStore([current]),
            ids=[f"new-{index}" for index in range(MAX_PENDING_PROGRAM_SCOPE_PREVIEWS)],
        )
        service.preview_revoke(current.revision_id, current.revision_digest)
        for index in range(MAX_PENDING_PROGRAM_SCOPE_PREVIEWS - 1):
            service.preview_create(f"program-{index}", scope(f"host{index}.test"))
        with self.assertRaisesRegex(ResearchError, "Too many"):
            service.preview_create("overflow", scope("overflow.test"))

    def test_create_store_failure_changes_no_published_state_and_can_retry(
        self,
    ) -> None:
        store = MemoryStore(save_error=OSError("disk"))
        service = self.service(store)
        preview = service.preview_create("program-a", scope())
        with self.assertRaisesRegex(ResearchError, "persist"):
            service.confirm_create(
                preview.revision.revision_id, preview.revision.revision_digest
            )
        self.assertEqual(service.revisions(), ())

        store.save_error = None
        self.assertEqual(
            service.confirm_create(
                preview.revision.revision_id, preview.revision.revision_digest
            ),
            preview.revision,
        )

    def test_revoke_preview_and_confirmation_are_exact_and_human(self) -> None:
        current = revision()
        store = MemoryStore([current])
        service = self.service(store, now=_NOW + timedelta(minutes=10))

        preview = service.preview_revoke(current.revision_id, current.revision_digest)

        self.assertEqual(preview.action, PROGRAM_SCOPE_REVOKE_ACTION)
        self.assertFalse(preview.revision.active)
        self.assertEqual(preview.revision.revoked_at, _NOW + timedelta(minutes=10))
        self.assertIs(preview.revision.revoked_by, ResearchAuthorizer.HUMAN)
        self.assertEqual(service.revisions(), (current,))
        self.assertEqual(store.save_calls, [])

        confirmed = service.confirm_revoke(
            preview.revision.revision_id, preview.revision.revision_digest
        )
        self.assertIs(confirmed, preview.revision)
        self.assertEqual(service.revisions(), (preview.revision,))

    def test_revoke_rejects_wrong_current_digest_tamper_and_replay(self) -> None:
        current = revision()
        service = self.service(MemoryStore([current]))
        with self.assertRaises(ResearchError):
            service.preview_revoke(current.revision_id, "0" * 64)
        preview = service.preview_revoke(current.revision_id, current.revision_digest)
        with self.assertRaises(ResearchError):
            service.confirm_revoke(preview.revision.revision_id, "0" * 64)
        service.confirm_revoke(
            preview.revision.revision_id, preview.revision.revision_digest
        )
        with self.assertRaises(ResearchError):
            service.confirm_revoke(
                preview.revision.revision_id, preview.revision.revision_digest
            )
        self.assertIs(service.revisions()[0].revoked_by, ResearchAuthorizer.HUMAN)

    def test_revoke_store_failure_preserves_active_published_state(self) -> None:
        current = revision()
        store = MemoryStore([current], save_error=ResearchError("disk"))
        service = self.service(store)
        preview = service.preview_revoke(current.revision_id, current.revision_digest)
        with self.assertRaisesRegex(ResearchError, "disk"):
            service.confirm_revoke(
                preview.revision.revision_id, preview.revision.revision_digest
            )
        self.assertEqual(service.revisions(), (current,))
        self.assertTrue(service.revisions()[0].active)

    def test_restart_restores_confirmed_values_but_not_pending_previews(self) -> None:
        store = MemoryStore()
        first = self.service(store)
        pending = first.preview_create("program-a", scope())

        restarted = self.service(store)
        self.assertEqual(restarted.revisions(), ())
        with self.assertRaises(ResearchError):
            restarted.confirm_create(
                pending.revision.revision_id, pending.revision.revision_digest
            )

        first.confirm_create(
            pending.revision.revision_id, pending.revision.revision_digest
        )
        restored = self.service(store)
        self.assertEqual(restored.revisions(), (pending.revision,))

    def test_invalid_clock_and_id_factory_fail_without_write(self) -> None:
        for clock, identity in (
            (lambda: _NOW.replace(tzinfo=None), lambda: "revision-new"),
            (lambda: _NOW, lambda: " "),
        ):
            store = MemoryStore()
            service = ResearchProgramScopeEnrollmentService(
                store, clock=clock, id_factory=identity
            )
            with (
                self.subTest(clock=clock, identity=identity),
                self.assertRaises(ResearchError),
            ):
                service.preview_create("program-a", scope())
            self.assertEqual(store.save_calls, [])

    def test_service_has_no_execution_network_process_or_ui_imports(self) -> None:
        source_path = (
            Path(__file__).parents[2]
            / "src"
            / "cognition"
            / "ResearchProgramScopeEnrollmentService.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(alias.name for alias in node.names)
        forbidden_fragments = (
            "socket",
            "subprocess",
            "urllib",
            "requests",
            "httpx",
            "ResearchPlanExecution",
            "ResearchAutonomy",
            "CognitiveEngine",
            "Desktop",
            "tkinter",
        )
        for fragment in forbidden_fragments:
            with self.subTest(fragment=fragment):
                self.assertFalse(any(fragment in name for name in imported))


if __name__ == "__main__":
    unittest.main()
