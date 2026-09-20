"""Drive real desktop requests and confirmation bindings without target traffic."""

from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from cognition.KaliOperationAuthorizationApplicationService import (
    KaliOperationAuthorizationApplicationService,
)
from cognition.KaliOperationPreviewApplicationService import (
    KaliOperationPreviewApplicationService,
)
from cognition.KaliOperationRunApplicationService import (
    KaliOperationRunApplicationService,
)
from desktop.DesktopController import DesktopController
from desktop.KaliOperationPanel import KaliOperationPanel
from research.JsonFileResearchKaliOperationAuthorizationStore import (
    JsonFileResearchKaliOperationAuthorizationStore,
)
from research.PublicHttpsUrlValidator import PublicHttpsUrlValidator
from research.ResearchKaliOperationExecution import ResearchKaliOperationProcessResult
from research.ResearchProgramScopeExecutionPolicy import (
    ResearchProgramScopeExecutionPolicy,
)
from research.WslKaliOperationProcessAdapter import WslKaliOperationProcessAdapter
from response.ResponseComposer import ResponseComposer
from tests.cognition.test_kali_operation_authorization_application_service import (
    ReadyKaliRuntimeProbe,
)
from tests.cognition.test_kali_operation_preview_application_service import (
    FakeProgramScopeRevisionStore,
    revision_fixture,
)
from tests.desktop.test_research_command_bindings import (
    RecordingVariable,
    RecordingWidget,
    build_real_window,
)


class TracedVariable(RecordingVariable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.callbacks = []

    def trace_add(self, mode, callback):
        self.callbacks.append(callback)
        return "trace"

    def set(self, value):
        super().set(value)
        for callback in self.callbacks:
            callback()


class KaliOperationPanelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        now = datetime.now(UTC)
        self.revision = revision_fixture(
            confirmed_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(minutes=30),
        )
        self.scopes = FakeProgramScopeRevisionStore([self.revision])
        self.store = JsonFileResearchKaliOperationAuthorizationStore(
            Path(self.temp.name) / "approvals.json"
        )
        composer = ResponseComposer()
        self.previews = KaliOperationPreviewApplicationService(
            composer,
            self.scopes,
            https_url_validator=PublicHttpsUrlValidator(
                lambda _hostname: ("93.184.216.34",)
            ),
        )
        self.approvals = KaliOperationAuthorizationApplicationService(
            composer, self.previews, authorization_store=self.store
        )
        self.adapter = Mock()
        self.runs = KaliOperationRunApplicationService(
            composer, self.previews, self.store, ReadyKaliRuntimeProbe(), self.adapter
        )
        self.requests = []
        brain = Mock()

        def process(request):
            self.requests.append(request)
            return {
                "kali_operation_preview": self.previews.process_preview,
                "kali_operation_authorization": self.approvals.process_authorization,
                "kali_operation_run": self.runs.process_run,
            }[request.metadata["intent"]](request)

        brain.process.side_effect = process
        self.controller = DesktopController(brain)
        self.pending = []

        def dispatch(action, complete, label):
            self.pending.append((action, complete))

        module = "desktop.KaliOperationPanel"
        RecordingWidget.instances = []
        with ExitStack() as stack:
            for name in ("Frame", "Label", "Entry", "Combobox", "Button"):
                stack.enter_context(patch(f"{module}.ttk.{name}", RecordingWidget))
            stack.enter_context(patch(f"{module}.tk.StringVar", TracedVariable))
            stack.enter_context(
                patch(f"{module}.scrolledtext.ScrolledText", RecordingWidget)
            )
            self.panel = KaliOperationPanel(
                RecordingWidget(),
                self.controller,
                lambda: tuple(self.scopes.load()),
                dispatch,
            )
        self.widgets = list(RecordingWidget.instances)
        self.dialog = patch(f"{module}.messagebox.askyesno", return_value=True).start()
        self.addCleanup(patch.stopall)
        self.panel.refresh()
        self.panel.scope.set(next(iter(self.panel._scope_choices)))
        self.panel.hostname.set("example.test")

    def finish(self):
        action, complete = self.pending.pop(0)
        complete(action())

    def preview_and_approve(self):
        self.panel.preview()
        self.finish()
        self.panel.authorize()
        self.finish()

    def test_real_buttons_preserve_separate_actions(self):
        for label, method in (
            ("1. Önizle", "preview"),
            ("2. Onayla", "authorize"),
            ("3. Çalıştır", "run"),
        ):
            button = next(widget for widget in self.widgets if widget.text == label)
            self.assertEqual(button.command, getattr(self.panel, method))

    def test_preview_and_authorize_use_existing_services_without_running(self):
        self.preview_and_approve()
        preview = self.panel._preview
        self.assertIsNotNone(preview)
        self.assertEqual(len(self.store.load()), 1)
        self.assertEqual(
            self.store.load()[0].operation_digest, preview.operation_digest
        )
        self.assertIsNotNone(self.panel._authorization_id)
        self.adapter.run.assert_not_called()
        self.assertNotIn("operator_opt_in", self.requests[-1].metadata)

    def test_https_selection_uses_curl_and_disables_dns_field(self):
        self.panel.operation.set("HTTPS başlıklarını oku (curl)")
        self.panel.preview()
        self.finish()
        self.assertEqual(self.panel.record_selector.kwargs["state"], "disabled")
        self.assertEqual(self.panel._preview.command_plan.argv[0], "/usr/bin/curl")
        self.assertIsNone(self.panel._preview.dns_record_type)

    def test_change_of_any_selection_invalidates_approval(self):
        for variable, value in (
            (self.panel.hostname, "www.example.test"),
            (self.panel.record_type, "AAAA"),
            (self.panel.operation, "HTTPS başlıklarını oku (curl)"),
            (self.panel.scope, "missing"),
        ):
            self.preview_and_approve()
            variable.set(value)
            self.assertIsNone(self.panel._preview)
            self.assertIsNone(self.panel._authorization_id)
            self.panel.run()
            self.assertEqual(self.pending, [])

    def test_late_authorization_result_cannot_restore_changed_selection(self):
        self.panel.preview()
        self.finish()
        self.panel.authorize()
        self.panel.hostname.set("www.example.test")
        self.finish()
        self.assertIsNone(self.panel._authorization_id)
        self.assertIsNone(self.panel._preview)
        self.panel.run()
        self.assertEqual(self.pending, [])

    def test_declining_confirmation_sends_no_request(self):
        self.panel.preview()
        self.finish()
        self.dialog.return_value = False
        self.panel.authorize()
        self.assertEqual(self.pending, [])
        self.assertEqual(self.store.load(), [])

    def test_run_is_explicit_single_use_and_captures_exact_preview(self):
        self.preview_and_approve()
        preview = self.panel._preview
        approval_id = self.panel._authorization_id
        self.panel.run()
        self.panel.run()
        self.assertEqual(len(self.pending), 1)
        self.assertIsNone(self.panel._authorization_id)
        with patch.object(self.controller, "run_kali_operation") as run:
            self.pending[0][0]()
        run.assert_called_once_with(preview, approval_id, operator_opt_in=True)

    def test_controller_run_without_opt_in_refuses_before_process(self):
        self.preview_and_approve()
        response = self.controller.run_kali_operation(
            self.panel._preview, self.panel._authorization_id
        )
        self.assertFalse(response.success)
        self.adapter.run.assert_not_called()
        self.assertEqual(len(self.store.load()), 1)

    def test_confirmed_run_reaches_adapter_once_for_each_profile(self):
        spent = []
        for operation, executable in (
            ("DNS kayıtlarını sorgula (dig)", "/usr/bin/dig"),
            ("HTTPS başlıklarını oku (curl)", "/usr/bin/curl"),
        ):
            self.adapter.reset_mock()
            self.panel.operation.set(operation)
            self.preview_and_approve()
            preview = self.panel._preview
            current_id = self.panel._authorization_id
            for old_preview, old_id in spent:
                response = self.controller.run_kali_operation(
                    old_preview, old_id, operator_opt_in=True
                )
                self.assertFalse(response.success)
                self.adapter.run.assert_not_called()
            self.adapter.run.return_value = ResearchKaliOperationProcessResult(
                preview.command_plan, 0, ("test output",)
            )
            self.panel.run()
            self.finish()
            self.adapter.run.assert_called_once()
            command = self.adapter.run.call_args.args[0]
            self.assertEqual(command.argv[0], executable)
            self.assertFalse(command.shell)
            self.assertEqual(self.store.load(), [])
            spent.append((preview, current_id))
            self.panel.run()
            self.assertEqual(self.pending, [])

    def test_cancel_run_keeps_approval_without_starting(self):
        self.preview_and_approve()
        authorization_id = self.panel._authorization_id
        self.dialog.return_value = False
        self.panel.run()
        self.assertEqual(self.panel._authorization_id, authorization_id)
        self.assertEqual(self.pending, [])
        self.adapter.run.assert_not_called()

    def test_default_https_scope_runs_with_the_smaller_process_time_limit(self):
        self._check_scope_timeout(60.0, 30.0)

    def test_smaller_scope_timeout_remains_binding(self):
        self._check_scope_timeout(5.0, 5.0)

    def _check_scope_timeout(self, scope_seconds, expected_timeout):
        now = datetime.now(UTC)
        self.revision = revision_fixture(
            confirmed_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(minutes=30),
            execution_policy=ResearchProgramScopeExecutionPolicy(
                max_seconds=scope_seconds
            ),
        )
        self.scopes.save([self.revision])
        self.panel.refresh()
        self.panel.scope.set(next(iter(self.panel._scope_choices)))
        self.panel.operation.set("HTTPS başlıklarını oku (curl)")
        self.preview_and_approve()
        preview = self.panel._preview
        self.assertEqual(preview.max_seconds, scope_seconds)
        self.adapter.run.side_effect = WslKaliOperationProcessAdapter().run
        completed = Mock(returncode=0, stdout="HTTP/2 200", stderr="")
        with patch(
            "research.WslKaliOperationProcessAdapter.subprocess.run",
            return_value=completed,
        ) as process:
            self.panel.run()
            self.finish()
        process.assert_called_once()
        self.assertEqual(process.call_args.kwargs["timeout"], expected_timeout)
        self.assertEqual(self.store.load(), [])

    def test_out_of_scope_host_cannot_be_approved(self):
        self.panel.hostname.set("admin.example.test")
        self.panel.preview()
        self.finish()
        self.assertIsNone(self.panel._preview)
        self.panel.authorize()
        self.assertEqual(self.pending, [])
        self.assertEqual(self.store.load(), [])

    def test_revoked_or_missing_scope_is_rechecked_by_authorization(self):
        self.panel.preview()
        self.finish()
        self.scopes.save([])
        self.panel.authorize()
        self.finish()
        self.assertIsNone(self.panel._authorization_id)
        self.assertEqual(self.store.load(), [])
        self.panel.refresh()
        self.assertEqual(self.panel._scope_choices, {})

    def test_refresh_failure_discards_previous_selection(self):
        self.preview_and_approve()
        self.panel._revisions = Mock(side_effect=OSError("unavailable"))
        self.panel.refresh()
        self.assertEqual(self.panel._scope_choices, {})
        self.assertIsNone(self.panel._authorization_id)

    def test_window_exposes_panel_when_scope_service_is_present(self):
        service = Mock()
        window, widgets = build_real_window(program_scope_enrollment_service=service)
        self.assertIsInstance(window._kali_panel, KaliOperationPanel)
        self.assertIn("1. Önizle", [widget.text for widget in widgets])
        service.revisions.assert_not_called()


if __name__ == "__main__":
    unittest.main()
