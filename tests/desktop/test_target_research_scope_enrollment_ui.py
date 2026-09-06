from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cognition.ResearchProgramScopeEnrollmentService import (
    ResearchProgramScopeEnrollmentService,
)
from desktop.TargetResearchDraftDialog import TargetResearchDraftDialog
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision

_NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)


class _Variable:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class _Text:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self, *_args: object) -> str:
        return self.value


class _MemoryStore:
    def __init__(self) -> None:
        self.values: list[ResearchProgramScopeRevision] = []
        self.save_calls: list[list[ResearchProgramScopeRevision]] = []

    def load(self) -> list[ResearchProgramScopeRevision]:
        return list(self.values)

    def save(self, values: list[ResearchProgramScopeRevision]) -> None:
        self.save_calls.append(list(values))
        self.values = list(values)


def _service(
    store: _MemoryStore,
    *,
    identities: list[str] | None = None,
) -> ResearchProgramScopeEnrollmentService:
    ids = iter(identities or ["revision-1", "revision-2"])
    return ResearchProgramScopeEnrollmentService(
        store,
        clock=lambda: _NOW,
        id_factory=lambda: next(ids),
    )


def _dialog(
    service: ResearchProgramScopeEnrollmentService,
) -> TargetResearchDraftDialog:
    dialog = object.__new__(TargetResearchDraftDialog)
    dialog._scope_enrollment_service = service
    dialog._pending_scope_preview = None
    dialog._active_scope_revisions = ()
    dialog.program = _Variable("program-a")
    dialog.status = _Variable()
    dialog.fields = {
        "allowed_hosts": _Text("example.test\n*.example.test"),
        "excluded_hosts": _Text("admin.example.test"),
        "allowed_networks": _Text(""),
        "excluded_networks": _Text(""),
        "source_urls": _Text("https://example.test/"),
    }
    dialog.action = _Variable("Read page only")
    dialog._on_apply = Mock()
    dialog.window = Mock()
    return dialog


class TargetResearchScopeEnrollmentUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dns = patch(
            "socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")
        ).start()
        self.process = patch(
            "subprocess.Popen", side_effect=AssertionError("process forbidden")
        ).start()
        self.addCleanup(patch.stopall)

    def tearDown(self) -> None:
        self.dns.assert_not_called()
        self.process.assert_not_called()

    def test_scope_preview_is_no_write_until_exact_confirm(self) -> None:
        store = _MemoryStore()
        dialog = _dialog(_service(store))

        dialog._preview_scope_enrollment()

        self.assertEqual(store.save_calls, [])
        self.assertIn("not saved", dialog.status.get())

        dialog._confirm_scope_enrollment()

        self.assertEqual(len(store.save_calls), 1)
        self.assertEqual(store.values[0].program_id, "program-a")
        self.assertIn("plan still needs approval", dialog.status.get())

    def test_edit_after_preview_invalidates_save_confirmation(self) -> None:
        store = _MemoryStore()
        dialog = _dialog(_service(store))
        dialog._preview_scope_enrollment()

        dialog.fields["allowed_hosts"] = _Text("other.test")
        dialog._confirm_scope_enrollment()

        self.assertEqual(store.save_calls, [])
        self.assertIsNone(dialog._pending_scope_preview)
        self.assertIn("preview changed", dialog.status.get())

    def test_revoke_requires_preview_and_exact_confirmation(self) -> None:
        store = _MemoryStore()
        service = _service(store)
        dialog = _dialog(service)
        dialog._preview_scope_enrollment()
        dialog._confirm_scope_enrollment()
        dialog._refresh_scope_revisions()

        dialog._preview_scope_revocation()

        self.assertTrue(store.values[0].active)
        self.assertIn("not revoked", dialog.status.get())

        dialog._confirm_scope_revocation()

        self.assertFalse(store.values[0].active)
        self.assertIn("Scope revoked", dialog.status.get())

    def test_use_in_plan_binds_selected_active_scope_revision(self) -> None:
        store = _MemoryStore()
        service = _service(store)
        dialog = _dialog(service)
        dialog._preview_scope_enrollment()
        dialog._confirm_scope_enrollment()
        revision = store.values[0]

        dialog.apply()

        draft = dialog._on_apply.call_args.args[0]
        self.assertEqual(draft.binding.scope_revision_id, revision.revision_id)
        self.assertEqual(draft.binding.scope_revision_digest, revision.revision_digest)
        dialog.window.destroy.assert_called_once_with()

    def test_missing_enrollment_service_is_inert(self) -> None:
        dialog = object.__new__(TargetResearchDraftDialog)
        dialog._scope_enrollment_service = None
        dialog._pending_scope_preview = object()
        dialog.status = _Variable()

        dialog._preview_scope_enrollment()
        dialog._confirm_scope_enrollment()
        dialog._preview_scope_revocation()
        dialog._confirm_scope_revocation()

        self.assertIn("not available", dialog.status.get())


if __name__ == "__main__":
    unittest.main()
