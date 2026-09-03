"""Offline proof: confirmed target scope survives execution and restart."""

from __future__ import annotations

import socket
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from http.client import HTTPMessage
from io import BytesIO
from itertools import count
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.request import Request

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.ResearchPlanAuthorizationApplicationService import (
    ResearchPlanAuthorizationApplicationService,
)
from cognition.ResearchPlanExecutionApplicationService import (
    ResearchPlanExecutionApplicationService,
)
from cognition.ResearchPlanPreviewApplicationService import (
    ResearchPlanPreviewApplicationService,
)
from core.Exceptions import ResearchError
from research.HttpResearchSourceFetcher import _ValidatedRedirectHandler
from research.JsonFileResearchExecutionStore import JsonFileResearchExecutionStore
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.PinnedHttpsTransport import PinnedHttpsHandler
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanOperationRegistry import ResearchPlanOperationRegistry
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.ResearchPlanTargetBinding import ResearchPlanTargetBinding
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourceAcceptanceResult import ResearchSourceAcceptanceResult
from research.ResearchTargetScope import ResearchTargetScope, TargetHostRule
from research.SourceAcceptStepOperation import SourceAcceptStepOperation
from research.SourceFetchStepOperation import SourceFetchStepOperation
from research.StartsResearchPlanExecution import ResearchPlanExecutionStartRefusal
from response.ResponseComposer import ResponseComposer
from tests.research.test_http_research_source_fetcher import FakeOpener, FakeResponse

NOW = datetime(2026, 9, 3, tzinfo=UTC)
URL = "https://example.test/authorized"
STEPS = (("Read the authorized page", (), "source_fetch", URL),)


class TargetBoundPlanFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.scope = ResearchTargetScope(
            allowed_hosts=(
                TargetHostRule("example.test", True),
                TargetHostRule("example.test"),
            ),
            excluded_hosts=(TargetHostRule("pay.example.test"),),
            excluded_networks=("93.184.216.35/32",),
        )
        self.binding = ResearchPlanTargetBinding("program-a", self.scope)
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.run_id = self.manager.create(
            "Inspect permitted public documentation"
        ).run_id
        ids = count(1)
        self.drafter = ResearchPlanDraftService(
            clock=lambda: NOW, id_factory=lambda: f"plan-{next(ids)}"
        )
        self.auth_store = JsonFileResearchPlanAuthorizationStore(
            self.root / "auth.json"
        )
        self.authorizations = ResearchPlanAuthorizationApplicationService(
            self.manager,
            ResponseComposer(),
            authorization_store=self.auth_store,
            clock=lambda: NOW,
        )
        self.store = JsonFileResearchExecutionStore(self.root / "executions.json")
        self.reference = Mock()
        self.registry = ResearchPlanOperationRegistry(
            {
                ResearchPlanStepCapability.SOURCE_FETCH: SourceFetchStepOperation(
                    self.reference, self.manager
                ),
            }
        )
        self.response = FakeResponse(url=URL)
        self.opener = FakeOpener(self.response)
        self.build_opener = patch(
            "research.HttpResearchSourceFetcher.build_opener", return_value=self.opener
        ).start()
        self.addCleanup(patch.stopall)
        self.dns = patch(
            "socket.getaddrinfo",
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
            ],
        ).start()
        patch(
            "socket.create_connection", side_effect=AssertionError("Live socket")
        ).start()
        self.execution = self.new_execution()

    def new_execution(self):
        return ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            self.drafter,
            operation_registry=self.registry,
            execution_store=self.store,
            authorization_consumer=self.authorizations,
            clock=lambda: NOW,
        )

    def request(self, **extra):
        return BrainRequest(
            message="Explicit operator action",
            metadata={
                "research_plan_question": "Inspect permitted public documentation",
                "research_plan_steps": STEPS,
                "research_run_id": self.run_id,
                "research_plan_target_binding": self.binding,
                **extra,
            },
        )

    def approve(self):
        preview = self.authorizations.process_preview(self.request())
        self.assertTrue(preview.success, preview.message)
        authorization = preview.research_plan_authorization
        assert authorization is not None
        confirmed = self.authorizations.process_confirm(
            self.request(authorization_id=authorization.authorization_id)
        )
        self.assertTrue(confirmed.success, confirmed.message)
        return authorization.authorization_id

    def start(self):
        response = self.execution.process_start(
            self.request(authorization_id=self.approve())
        )
        self.assertTrue(response.success, response.message)
        state = response.research_plan_execution
        assert state is not None
        return state.plan_id

    def advance(self, service, execution_id, **extra):
        return service.process_advance(
            BrainRequest(
                message="Advance", metadata={"research_plan_id": execution_id, **extra}
            )
        )

    def test_draft_and_approval_disclose_exact_program_inclusions_and_exclusions(self):
        draft = ResearchPlanPreviewApplicationService(ResponseComposer(), self.drafter)
        for response in (
            draft.process_draft_preview(self.request()),
            self.authorizations.process_preview(self.request()),
        ):
            self.assertTrue(response.success)
            self.assertIn("Target program: program-a", response.message)
            self.assertIn(
                "Allowed host: example.test (descendants only, not apex)",
                response.message,
            )
            self.assertIn("Excluded host: pay.example.test (exact)", response.message)
            self.assertIn("Excluded IP network: 93.184.216.35/32", response.message)
        self.assertFalse(self.auth_store.load())
        self.dns.assert_not_called()
        self.assertEqual(self.opener.calls, [])

    def test_changed_program_scope_or_removed_binding_cannot_confirm(self):
        for binding in (
            replace(self.binding, program_id="program-b"),
            replace(self.binding, scope=replace(self.scope, excluded_hosts=())),
            None,
        ):
            preview = self.authorizations.process_preview(self.request())
            auth = preview.research_plan_authorization
            assert auth is not None
            response = self.authorizations.process_confirm(
                self.request(
                    authorization_id=auth.authorization_id,
                    research_plan_target_binding=binding,
                )
            )
            self.assertFalse(response.success)
        self.assertFalse(self.auth_store.load())
        self.dns.assert_not_called()

    def test_changed_binding_cannot_start_or_consume_approval(self):
        auth_id = self.approve()
        response = self.execution.process_start(
            self.request(
                authorization_id=auth_id,
                research_plan_target_binding=replace(
                    self.binding, program_id="program-b"
                ),
            )
        )
        self.assertFalse(response.success)
        self.assertFalse(self.auth_store.load()[0].is_consumed)
        self.assertEqual(self.store.load(), [])
        self.dns.assert_not_called()

    def test_target_start_requires_authorization_even_in_legacy_composition(self):
        service = ResearchPlanExecutionApplicationService(
            ResponseComposer(), self.drafter
        )
        response = service.process_start(self.request())
        self.assertFalse(response.success)
        self.assertIn("human approval", response.message)
        self.dns.assert_not_called()

    def test_preview_confirm_start_are_zero_network_then_advance_uses_scoped_transport(
        self,
    ):
        execution_id = self.start()
        self.dns.assert_not_called()
        self.assertEqual(self.opener.calls, [])
        allowance = self.execution.allowance(execution_id)
        assert allowance is not None
        self.assertEqual(allowance.spend.network_operations, 0)
        # Per-advance caller metadata cannot replace the approved context.
        result = self.advance(
            self.execution, execution_id, research_plan_target_binding=None
        )
        state = result.research_plan_execution
        assert state is not None
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.COMPLETED)
        self.reference.fetch.assert_not_called()
        self.assertEqual(len(self.opener.calls), 1)
        self.assertEqual(self.opener.calls[0][0].full_url, URL)
        self.assertEqual(self.response.read_limits, [1_000_001])
        allowance = self.execution.allowance(execution_id)
        assert allowance is not None
        self.assertEqual(allowance.spend.network_operations, 1)

    def test_bound_operation_refuses_excluded_host_without_reference_fallback(self):
        context = ResearchPlanExecutionContext(
            research_run_id=self.run_id, target_binding=self.binding
        )
        for cls in (SourceFetchStepOperation, SourceAcceptStepOperation):
            acceptance = Mock()
            operation = (
                cls(self.reference, self.manager)
                if cls is SourceFetchStepOperation
                else cls(self.reference, acceptance, self.manager)
            )
            step = ResearchPlanStep(
                "s",
                "Fetch",
                capability=ResearchPlanStepCapability.SOURCE_FETCH,
                authorized_source_url="https://pay.example.test/",
            )
            with self.assertRaisesRegex(ResearchError, "excluded"):
                operation.run(step, context)
            acceptance.accept.assert_not_called()
        self.reference.fetch.assert_not_called()
        self.dns.assert_not_called()
        self.assertEqual(self.opener.calls, [])

    def test_dispatch_redirect_and_connection_handlers_keep_approved_scope(self):
        self.advance(self.execution, self.start())
        handlers = self.build_opener.call_args.args
        redirect = next(h for h in handlers if isinstance(h, _ValidatedRedirectHandler))
        pinned = next(h for h in handlers if isinstance(h, PinnedHttpsHandler))
        self.dns.reset_mock()
        with self.assertRaises(ResearchError):
            redirect.redirect_request(
                Request(URL),
                BytesIO(),
                302,
                "Found",
                HTTPMessage(),
                "https://pay.example.test/",
            )
        with patch.object(pinned, "do_open") as do_open:
            with self.assertRaises(ResearchError):
                pinned.https_open(Request("https://pay.example.test/"))
            do_open.assert_not_called()
        self.dns.assert_not_called()
        # A later DNS answer pointing at an excluded address is refused too.
        self.dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.35", 443))
        ]
        with patch.object(pinned, "do_open") as do_open:
            with self.assertRaisesRegex(ResearchError, "excluded"):
                pinned.https_open(Request(URL))
            do_open.assert_not_called()
        self.reference.fetch.assert_not_called()

    def test_accept_operation_uses_scoped_transport_before_canonical_acceptance(self):
        acceptance = Mock()
        acceptance.accept.return_value = ResearchSourceAcceptanceResult(
            accepted=False, transaction_attempted=True, failure_reason="Test rejection"
        )
        operation = SourceAcceptStepOperation(self.reference, acceptance, self.manager)
        result = operation.run(
            ResearchPlanStep(
                "s",
                "Accept",
                capability=ResearchPlanStepCapability.SOURCE_ACCEPT,
                authorized_source_url=URL,
            ),
            ResearchPlanExecutionContext(
                research_run_id=self.run_id, target_binding=self.binding
            ),
        )
        self.assertTrue(result.performed)
        self.assertFalse(result.succeeded)
        self.reference.fetch.assert_not_called()
        self.assertEqual(acceptance.accept.call_args.args[0].url, URL)
        self.assertEqual(acceptance.accept.call_args.args[1], self.run_id)

    def test_final_out_of_scope_body_is_not_read_and_never_falls_back(self):
        self.opener._response = FakeResponse(url="https://other.test/")
        result = self.advance(self.execution, self.start())
        state = result.research_plan_execution
        assert state is not None
        self.assertIs(state.steps[0].status, ResearchPlanStepStatus.FAILED)
        self.assertEqual(self.opener._response.read_limits, [])
        self.reference.fetch.assert_not_called()

    def test_restart_checks_exact_digest_run_and_retains_scope_at_dispatch(self):
        execution_id = self.start()
        plan = self.execution.live_plan(execution_id)
        assert plan is not None
        snapshot = self.store.load()[0]
        self.assertEqual(snapshot.target_plan_digest, plan_digest(plan))
        restored = self.new_execution()
        for candidate, run_id in (
            (replace(plan, target_binding=None), self.run_id),
            (
                replace(plan, target_binding=replace(self.binding, program_id="b")),
                self.run_id,
            ),
            (
                replace(
                    plan,
                    target_binding=replace(
                        self.binding, scope=replace(self.scope, excluded_hosts=())
                    ),
                ),
                self.run_id,
            ),
            (
                replace(
                    plan,
                    steps=(
                        replace(plan.steps[0], authorized_source_url=URL + "changed"),
                    ),
                ),
                self.run_id,
            ),
            (plan, "wrong-run"),
        ):
            self.assertIsInstance(
                restored.rebind_restored(candidate, run_id, execution_id),
                ResearchPlanExecutionStartRefusal,
            )
        self.dns.assert_not_called()
        state = restored.rebind_restored(plan, self.run_id, execution_id)
        self.assertNotIsInstance(state, ResearchPlanExecutionStartRefusal)
        response = self.advance(restored, execution_id)
        self.assertIs(
            response.research_plan_execution.steps[0].status,
            ResearchPlanStepStatus.COMPLETED,
        )
        self.reference.fetch.assert_not_called()

    def test_legacy_snapshot_cannot_be_rebound_to_target_plan(self):
        execution_id = self.start()
        plan = self.execution.live_plan(execution_id)
        assert plan is not None
        snapshot = self.store.load()[0]
        self.store.save([replace(snapshot, target_plan_digest=None)])
        response = self.new_execution().rebind_restored(plan, self.run_id, execution_id)
        self.assertIsInstance(response, ResearchPlanExecutionStartRefusal)
        self.dns.assert_not_called()

    def test_malformed_binding_cannot_be_silently_dropped_by_draft_or_start(self):
        for value in ({}, "example.test", False):
            request = self.request(research_plan_target_binding=value)
            self.assertFalse(self.authorizations.process_preview(request).success)
            self.assertFalse(self.execution.process_start(request).success)
        self.dns.assert_not_called()


if __name__ == "__main__":
    unittest.main()
