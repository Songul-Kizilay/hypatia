"""Readiness gate composition: prepared invocation -> probe -> ready invocation.

RUNTIME READY != EXECUTION AUTHORITY. RUNTIME-READY INVOCATION != EXECUTION
SUCCESS. Every test here proves either unforgeable construction of
`GuestAgentRuntimeReadyInvocation`, or that `check_guest_agent_runtime_readiness`
only ever constructs one after its probe's own `check()` call returned a
`READY` receipt -- never before, never on `UNAVAILABLE`.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import research.GuestAgentRuntimeReadiness as readiness_module  # noqa: E402
from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentHostAuthorizationHandoff import (  # noqa: E402
    consume_authorization_for_guest_agent_dispatch,
)
from research.GuestAgentInvocationPreparation import (  # noqa: E402
    GuestAgentPreparedInvocation,
    prepare_guest_agent_invocation,
)
from research.GuestAgentLocalReadiness import (  # noqa: E402
    GuestAgentLocalReadinessProbe,
    GuestAgentLocalReadinessReceipt,
    GuestAgentLocalReadinessState,
)
from research.GuestAgentReplayProtector import GuestAgentReplayProtector  # noqa: E402
from research.GuestAgentRuntimeReadiness import (  # noqa: E402
    GuestAgentRuntimeReadyInvocation,
    check_guest_agent_runtime_readiness,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchKaliOperationKind,
)
from tests.research.test_guest_agent_host_authorization_handoff import (  # noqa: E402
    NOW,
    FakeAuthorizationStore,
    _authorize,
    _preview,
)


class _MemoryReplayStore:
    def __init__(self) -> None:
        self._records: list = []

    def load(self) -> list:
        return list(self._records)

    def save(self, records: list) -> None:
        self._records = list(records)


def _prepared_invocation(*, request_id: str = "r1") -> GuestAgentPreparedInvocation:
    preview = _preview()
    authorization = _authorize(preview, authorization_id=f"auth-{request_id}")
    store = FakeAuthorizationStore([authorization])
    grant = consume_authorization_for_guest_agent_dispatch(
        store, authorization.authorization_id, preview, now=NOW
    )
    request = grant.materialize_request(
        request_id=request_id, nonce=f"nonce-{request_id}"
    )
    replay_protector = GuestAgentReplayProtector(_MemoryReplayStore())
    _response, prepared = prepare_guest_agent_invocation(request, replay_protector)
    assert prepared is not None
    return prepared


class _FixedReceiptProbe(GuestAgentLocalReadinessProbe):
    """Test double: returns a canned receipt, never touches subprocess."""

    def __init__(self, receipt: GuestAgentLocalReadinessReceipt) -> None:
        self._receipt = receipt
        self.calls: list[GuestAgentPreparedInvocation] = []

    def check(
        self, prepared_invocation: GuestAgentPreparedInvocation
    ) -> GuestAgentLocalReadinessReceipt:
        self.calls.append(prepared_invocation)
        return self._receipt


def _ready_receipt(
    operation_kind: ResearchKaliOperationKind,
) -> GuestAgentLocalReadinessReceipt:
    return GuestAgentLocalReadinessReceipt(
        operation_kind=operation_kind,
        state=GuestAgentLocalReadinessState.READY,
        reason="simulated ready",
        executable_path="/usr/bin/dig",
        observed_version="DiG 9.18.0",
        probe_process_started=True,
    )


def _unavailable_receipt(
    operation_kind: ResearchKaliOperationKind,
) -> GuestAgentLocalReadinessReceipt:
    return GuestAgentLocalReadinessReceipt(
        operation_kind=operation_kind,
        state=GuestAgentLocalReadinessState.UNAVAILABLE,
        reason="simulated unavailable",
    )


class ForgeryResistanceTests(unittest.TestCase):
    def test_cannot_construct_with_foreign_token(self) -> None:
        prepared = _prepared_invocation()
        receipt = _ready_receipt(prepared.operation_kind)
        with self.assertRaises(ResearchError):
            GuestAgentRuntimeReadyInvocation(
                prepared_invocation=prepared,
                readiness_receipt=receipt,
                _capability_token=object(),
            )

    def test_cannot_construct_without_token_kwarg(self) -> None:
        prepared = _prepared_invocation()
        receipt = _ready_receipt(prepared.operation_kind)
        with self.assertRaises(TypeError):
            GuestAgentRuntimeReadyInvocation(  # type: ignore[call-arg]
                prepared_invocation=prepared, readiness_receipt=receipt
            )

    def test_cannot_construct_with_unavailable_receipt_even_with_real_token(
        self,
    ) -> None:
        prepared = _prepared_invocation()
        receipt = _unavailable_receipt(prepared.operation_kind)
        with self.assertRaises(ResearchError):
            GuestAgentRuntimeReadyInvocation(
                prepared_invocation=prepared,
                readiness_receipt=receipt,
                _capability_token=readiness_module._RUNTIME_READY_CAPABILITY,
            )

    def test_cannot_construct_with_mismatched_operation_kind(self) -> None:
        prepared = _prepared_invocation()
        mismatched_kind = (
            ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP
            if prepared.operation_kind is ResearchKaliOperationKind.DNS_RECORD_LOOKUP
            else ResearchKaliOperationKind.DNS_RECORD_LOOKUP
        )
        receipt = _ready_receipt(mismatched_kind)
        with self.assertRaises(ResearchError):
            GuestAgentRuntimeReadyInvocation(
                prepared_invocation=prepared,
                readiness_receipt=receipt,
                _capability_token=readiness_module._RUNTIME_READY_CAPABILITY,
            )

    def test_rejects_non_prepared_invocation(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentRuntimeReadyInvocation(
                prepared_invocation=object(),  # type: ignore[arg-type]
                readiness_receipt=_ready_receipt(
                    ResearchKaliOperationKind.DNS_RECORD_LOOKUP
                ),
                _capability_token=readiness_module._RUNTIME_READY_CAPABILITY,
            )

    def test_rejects_non_receipt(self) -> None:
        prepared = _prepared_invocation()
        with self.assertRaises(ResearchError):
            GuestAgentRuntimeReadyInvocation(
                prepared_invocation=prepared,
                readiness_receipt=object(),  # type: ignore[arg-type]
                _capability_token=readiness_module._RUNTIME_READY_CAPABILITY,
            )

    def test_legitimately_constructed_value_is_consistent(self) -> None:
        prepared = _prepared_invocation()
        receipt = _ready_receipt(prepared.operation_kind)
        ready_invocation = GuestAgentRuntimeReadyInvocation(
            prepared_invocation=prepared,
            readiness_receipt=receipt,
            _capability_token=readiness_module._RUNTIME_READY_CAPABILITY,
        )
        self.assertIs(ready_invocation.prepared_invocation, prepared)
        self.assertIs(ready_invocation.readiness_receipt, receipt)


class CompositionFunctionTests(unittest.TestCase):
    def test_requires_prepared_invocation_type(self) -> None:
        probe = _FixedReceiptProbe(
            _ready_receipt(ResearchKaliOperationKind.DNS_RECORD_LOOKUP)
        )
        with self.assertRaises(ResearchError):
            check_guest_agent_runtime_readiness(object(), probe)  # type: ignore[arg-type]
        self.assertEqual(probe.calls, [])

    def test_requires_bounded_probe_type(self) -> None:
        prepared = _prepared_invocation()
        with self.assertRaises(ResearchError):
            check_guest_agent_runtime_readiness(prepared, object())  # type: ignore[arg-type]

    def test_ready_receipt_produces_ready_invocation(self) -> None:
        prepared = _prepared_invocation()
        probe = _FixedReceiptProbe(_ready_receipt(prepared.operation_kind))
        receipt, ready_invocation = check_guest_agent_runtime_readiness(prepared, probe)
        self.assertTrue(receipt.ready)
        self.assertIsInstance(ready_invocation, GuestAgentRuntimeReadyInvocation)
        assert ready_invocation is not None
        self.assertIs(ready_invocation.prepared_invocation, prepared)
        self.assertEqual(probe.calls, [prepared])

    def test_unavailable_receipt_produces_no_ready_invocation(self) -> None:
        prepared = _prepared_invocation()
        probe = _FixedReceiptProbe(_unavailable_receipt(prepared.operation_kind))
        receipt, ready_invocation = check_guest_agent_runtime_readiness(prepared, probe)
        self.assertFalse(receipt.ready)
        self.assertIsNone(ready_invocation)

    def test_probe_receives_the_exact_prepared_invocation_object(self) -> None:
        prepared = _prepared_invocation()
        probe = _FixedReceiptProbe(_ready_receipt(prepared.operation_kind))
        check_guest_agent_runtime_readiness(prepared, probe)
        self.assertEqual(len(probe.calls), 1)
        self.assertIs(probe.calls[0], prepared)

    def test_function_never_touches_command_plan_argv(self) -> None:
        """The composition function itself has no code path that reads
        `prepared_invocation.command_plan` at all -- it only forwards the
        whole prepared invocation to the probe and inspects the probe's
        returned receipt. Checked structurally (AST attribute access), not
        by substring, so the module's own docstring prose is never a false
        positive."""
        import ast
        import inspect
        import textwrap

        source = textwrap.dedent(inspect.getsource(check_guest_agent_runtime_readiness))
        tree = ast.parse(source)
        attribute_names = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        self.assertNotIn("command_plan", attribute_names)
        self.assertNotIn("argv", attribute_names)

    def test_readiness_does_not_mutate_prepared_invocation(self) -> None:
        prepared = _prepared_invocation()
        original_timeout = prepared.timeout_seconds
        original_plan = prepared.command_plan
        probe = _FixedReceiptProbe(_ready_receipt(prepared.operation_kind))
        check_guest_agent_runtime_readiness(prepared, probe)
        self.assertEqual(prepared.timeout_seconds, original_timeout)
        self.assertIs(prepared.command_plan, original_plan)


if __name__ == "__main__":
    unittest.main()
