"""Admit -> replay-consume -> prepare: the post-replay prepared-invocation
foundation (`research.GuestAgentInvocationPreparation`).

PREPARED INVOCATION != PROCESS CREATED, != RUNTIME READY, != EXECUTION
SUCCESS, != TRUSTED OUTPUT, != EVIDENCE. Every test below proves either the
exact admit -> replay -> prepare ordering (including every way a prepared
invocation must NOT be constructed), unforgeable construction, exact code-
owned command-plan reconstruction (never wire-carried), or a bounded,
never-widened process timeout.
"""

from __future__ import annotations

import ast
import hashlib
import sys
import unittest
from pathlib import Path
from unittest import mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import research.GuestAgentCore as guest_agent_core_module  # noqa: E402
import research.GuestAgentInvocationPreparation as preparation_module  # noqa: E402
from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentCore import admit_guest_agent_request  # noqa: E402
from research.GuestAgentHostAuthorizationHandoff import (  # noqa: E402
    consume_authorization_for_guest_agent_dispatch,
)
from research.GuestAgentInvocationPreparation import (  # noqa: E402
    GuestAgentPreparedInvocation,
    prepare_guest_agent_invocation,
)
from research.GuestAgentProtocol import (  # noqa: E402
    GuestAgentProtocolVersion,
    GuestAgentRequest,
    GuestAgentResponseStatus,
)
from research.GuestAgentReplayProtector import (  # noqa: E402
    GuestAgentReplayProtector,
)
from research.ResearchKaliOperationExecution import (  # noqa: E402
    MAX_KALI_OPERATION_TIMEOUT_SECONDS,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchKaliCommandTransport,
    ResearchKaliOperationKind,
)
from tests.research.test_guest_agent_host_authorization_handoff import (  # noqa: E402
    NOW,
    FakeAuthorizationStore,
    _authorize,
    _https_preview,
    _preview,
)

MODULE_FILE = SRC_DIR / "research" / "GuestAgentInvocationPreparation.py"

VALID_DIGEST = hashlib.sha256(b"example-preview").hexdigest()


class _MemoryReplayStore:
    """Minimal in-memory replay store with error injection."""

    def __init__(self, *, save_error: Exception | None = None) -> None:
        self._records: list = []
        self._save_error = save_error
        self.save_calls = 0

    def load(self) -> list:
        return list(self._records)

    def save(self, records: list) -> None:
        self.save_calls += 1
        if self._save_error is not None:
            raise self._save_error
        self._records = list(records)


def _real_v2_request(*, preview=None, request_id: str = "r1") -> GuestAgentRequest:
    preview = preview or _preview()
    authorization = _authorize(preview, authorization_id=f"auth-{request_id}")
    store = FakeAuthorizationStore([authorization])
    grant = consume_authorization_for_guest_agent_dispatch(
        store, authorization.authorization_id, preview, now=NOW
    )
    return grant.materialize_request(request_id=request_id, nonce=f"nonce-{request_id}")


def _v1_request(**overrides: object) -> GuestAgentRequest:
    base: dict[str, object] = dict(
        protocol_version=GuestAgentProtocolVersion.V1,
        request_id="r1",
        nonce="n1",
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        operation_digest=VALID_DIGEST,
        logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
    )
    base.update(overrides)
    return GuestAgentRequest(**base)  # type: ignore[arg-type]


class V1BehaviorTests(unittest.TestCase):
    """V1 RPC BEHAVIOR: admission/replay may succeed; no prepared invocation."""

    def test_v1_declined_admission_still_consumes_replay(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _v1_request()
        response, prepared = prepare_guest_agent_invocation(request, protector)
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        self.assertIsNone(prepared)
        self.assertEqual(store.save_calls, 1)

    def test_v1_replay_produces_replay_rejected_no_prepared_invocation(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _v1_request()
        prepare_guest_agent_invocation(request, protector)
        response, prepared = prepare_guest_agent_invocation(request, protector)
        self.assertEqual(response.status, GuestAgentResponseStatus.REPLAY_REJECTED)
        self.assertIsNone(prepared)


class OrderingTests(unittest.TestCase):
    """Admission -> replay-consume -> prepare, structurally enforced."""

    def test_unsupported_capability_skips_replay_and_preparation(self) -> None:
        # There is no third `ResearchKaliOperationKind` member to send
        # today (mirroring tests.research.test_guest_agent_core's own
        # established technique), so the `UNSUPPORTED_CAPABILITY` branch
        # is exercised by temporarily emptying the allowlist dict.
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _v1_request()
        with mock.patch.dict(
            guest_agent_core_module._OPERATION_REQUIRED_LOGICAL_INPUT_FIELDS,
            {},
            clear=True,
        ):
            response, prepared = prepare_guest_agent_invocation(request, protector)
        self.assertEqual(
            response.status, GuestAgentResponseStatus.UNSUPPORTED_CAPABILITY
        )
        self.assertIsNone(prepared)
        self.assertEqual(store.save_calls, 0)

    def test_invalid_request_skips_replay_and_preparation(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _v1_request(logical_inputs=(("hostname", "example.com"),))
        response, prepared = prepare_guest_agent_invocation(request, protector)
        self.assertEqual(response.status, GuestAgentResponseStatus.INVALID_REQUEST)
        self.assertIsNone(prepared)
        self.assertEqual(store.save_calls, 0)

    def test_replay_already_consumed_prevents_prepared_invocation(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _real_v2_request(request_id="r-replay")
        prepare_guest_agent_invocation(request, protector)
        response, prepared = prepare_guest_agent_invocation(request, protector)
        self.assertEqual(response.status, GuestAgentResponseStatus.REPLAY_REJECTED)
        self.assertIsNone(prepared)

    def test_replay_persistence_failure_prevents_prepared_invocation(self) -> None:
        store = _MemoryReplayStore(save_error=ResearchError("forced failure"))
        protector = GuestAgentReplayProtector(store)
        request = _real_v2_request(request_id="r-fail")
        with self.assertRaises(ResearchError):
            prepare_guest_agent_invocation(request, protector)

    def test_admission_runs_before_replay_consumption(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _v1_request(logical_inputs=())  # UNSUPPORTED_CAPABILITY path
        with mock.patch.object(
            preparation_module, "admit_guest_agent_request"
        ) as mock_admit:
            mock_admit.return_value = admit_guest_agent_request(
                _v1_request(
                    operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                    logical_inputs=(),
                )
            )
            prepare_guest_agent_invocation(request, protector)
        mock_admit.assert_called_once()
        self.assertEqual(store.save_calls, 0)

    def test_declined_admission_consumes_replay_exactly_once(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _real_v2_request(request_id="r-once")
        prepare_guest_agent_invocation(request, protector)
        self.assertEqual(store.save_calls, 1)

    def test_prepared_invocation_is_built_strictly_after_replay_consumption(
        self,
    ) -> None:
        """Building (and discarding) a `GuestAgentPreparedInvocation` has no
        side effect of its own, so a naive return-value check cannot catch
        a regression that reorders construction before replay consumption
        -- caught only by a mutation test during implementation. This test
        closes that gap by recording call order directly."""
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _real_v2_request(request_id="r-order")

        call_order: list[str] = []
        real_consume_once = protector.consume_once
        real_build = preparation_module._build_prepared_invocation

        def _recording_consume_once(req):
            call_order.append("consume_once")
            return real_consume_once(req)

        def _recording_build(req):
            call_order.append("_build_prepared_invocation")
            return real_build(req)

        with (
            mock.patch.object(
                protector, "consume_once", side_effect=_recording_consume_once
            ),
            mock.patch.object(
                preparation_module,
                "_build_prepared_invocation",
                side_effect=_recording_build,
            ),
        ):
            _response, prepared = prepare_guest_agent_invocation(request, protector)

        self.assertIsNotNone(prepared)
        self.assertEqual(call_order, ["consume_once", "_build_prepared_invocation"])


class V2RealRoundTripTests(unittest.TestCase):
    """Requirements 19-21: valid V2 verification/admission for DNS and HTTPS."""

    def test_v2_dns_first_seen_declined_then_prepared(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _real_v2_request(request_id="r-dns")
        response, prepared = prepare_guest_agent_invocation(request, protector)
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        self.assertIsInstance(prepared, GuestAgentPreparedInvocation)
        self.assertIs(
            prepared.operation_kind, ResearchKaliOperationKind.DNS_RECORD_LOOKUP
        )

    def test_v2_https_first_seen_declined_then_prepared(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _real_v2_request(preview=_https_preview(), request_id="r-https")
        response, prepared = prepare_guest_agent_invocation(request, protector)
        self.assertEqual(response.status, GuestAgentResponseStatus.DECLINED)
        self.assertIsInstance(prepared, GuestAgentPreparedInvocation)
        self.assertIs(
            prepared.operation_kind, ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP
        )

    def test_wire_response_output_lines_remain_empty(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _real_v2_request(request_id="r-output")
        response, _prepared = prepare_guest_agent_invocation(request, protector)
        self.assertEqual(response.output_lines, ())

    def test_success_is_unreachable(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _real_v2_request(request_id="r-success")
        response, _prepared = prepare_guest_agent_invocation(request, protector)
        self.assertNotEqual(response.status, GuestAgentResponseStatus.SUCCESS)


class CommandPlanTests(unittest.TestCase):
    """Requirements 29-31, 'COMMAND-PLAN TESTS': code-owned reconstruction."""

    def test_dns_command_plan_matches_the_existing_reviewed_builder(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _real_v2_request(request_id="r-dns-plan")
        _response, prepared = prepare_guest_agent_invocation(request, protector)
        plan = prepared.command_plan
        self.assertIs(plan.transport, ResearchKaliCommandTransport.GUEST_AGENT)
        self.assertEqual(plan.executable_path, "/usr/bin/dig")
        self.assertFalse(plan.shell)
        self.assertEqual(plan.stdin, "closed")
        self.assertEqual(
            plan.argv,
            (
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "example.com",
                "A",
            ),
        )

    def test_https_command_plan_matches_the_existing_reviewed_builder(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        request = _real_v2_request(preview=_https_preview(), request_id="r-https-plan")
        _response, prepared = prepare_guest_agent_invocation(request, protector)
        plan = prepared.command_plan
        self.assertIs(plan.transport, ResearchKaliCommandTransport.GUEST_AGENT)
        self.assertEqual(plan.executable_path, "/usr/bin/curl")
        self.assertFalse(plan.shell)
        self.assertEqual(plan.stdin, "closed")
        self.assertEqual(
            plan.argv,
            (
                "/usr/bin/curl",
                "--head",
                "--silent",
                "--show-error",
                "--max-time",
                "10",
                "--proto",
                "=https",
                "--resolve",
                "example.com:443:93.184.216.34",
                "https://example.com/",
            ),
        )

    def test_no_caller_override_of_command_plan_is_possible(self) -> None:
        """`prepare_guest_agent_invocation` takes no command-plan parameter
        at all -- structurally proven by its own signature."""
        import inspect

        parameters = set(inspect.signature(prepare_guest_agent_invocation).parameters)
        self.assertEqual(parameters, {"request", "replay_protector"})


class TimeoutBoundTests(unittest.TestCase):
    """Requirements 32-33: prepared timeout never exceeds the signed limit
    or the global hard cap."""

    def test_timeout_matches_signed_limit_when_under_the_cap(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        preview = _preview(max_seconds=5.0)
        request = _real_v2_request(preview=preview, request_id="r-timeout-low")
        _response, prepared = prepare_guest_agent_invocation(request, protector)
        self.assertEqual(prepared.timeout_seconds, 5.0)
        self.assertLessEqual(
            prepared.timeout_seconds, request.execution_limits.max_seconds
        )

    def test_timeout_is_capped_at_the_global_hard_ceiling(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        preview = _preview(max_seconds=3600.0)
        request = _real_v2_request(preview=preview, request_id="r-timeout-high")
        _response, prepared = prepare_guest_agent_invocation(request, protector)
        self.assertEqual(prepared.timeout_seconds, MAX_KALI_OPERATION_TIMEOUT_SECONDS)
        self.assertLessEqual(
            prepared.timeout_seconds, MAX_KALI_OPERATION_TIMEOUT_SECONDS
        )

    def test_timeout_exactly_at_the_hard_ceiling_is_not_widened(self) -> None:
        store = _MemoryReplayStore()
        protector = GuestAgentReplayProtector(store)
        preview = _preview(max_seconds=MAX_KALI_OPERATION_TIMEOUT_SECONDS)
        request = _real_v2_request(preview=preview, request_id="r-timeout-exact")
        _response, prepared = prepare_guest_agent_invocation(request, protector)
        self.assertEqual(prepared.timeout_seconds, MAX_KALI_OPERATION_TIMEOUT_SECONDS)


class PreparedInvocationForgeryResistanceTests(unittest.TestCase):
    """Requirement 27: the prepared invocation is unforgeable."""

    def test_direct_construction_without_token_raises(self) -> None:
        from research.ResearchKaliOperationPreview import (
            ResearchDnsRecordType,
            kali_operation_command_plan,
        )

        plan = kali_operation_command_plan(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            hostname="example.com",
            dns_record_type=ResearchDnsRecordType.A,
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
        )
        with self.assertRaises(TypeError):
            GuestAgentPreparedInvocation(  # type: ignore[call-arg]
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                command_plan=plan,
                timeout_seconds=5.0,
            )

    def test_direct_construction_with_wrong_token_raises(self) -> None:
        from research.ResearchKaliOperationPreview import (
            ResearchDnsRecordType,
            kali_operation_command_plan,
        )

        plan = kali_operation_command_plan(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            hostname="example.com",
            dns_record_type=ResearchDnsRecordType.A,
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
        )
        with self.assertRaises(ResearchError):
            GuestAgentPreparedInvocation(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                command_plan=plan,
                timeout_seconds=5.0,
                _capability_token=object(),  # type: ignore[call-arg]
            )

    def test_timeout_exceeding_global_cap_rejected_at_construction(self) -> None:
        from research.ResearchKaliOperationPreview import (
            ResearchDnsRecordType,
            kali_operation_command_plan,
        )

        plan = kali_operation_command_plan(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            hostname="example.com",
            dns_record_type=ResearchDnsRecordType.A,
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
        )
        with self.assertRaises(ResearchError):
            GuestAgentPreparedInvocation(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                command_plan=plan,
                timeout_seconds=MAX_KALI_OPERATION_TIMEOUT_SECONDS + 1,
                _capability_token=preparation_module._PREPARED_INVOCATION_CAPABILITY,
            )


class StructuralSecurityTests(unittest.TestCase):
    """AST-based proof: no process, no subprocess, no execution authority."""

    def setUp(self) -> None:
        self.tree = ast.parse(
            MODULE_FILE.read_text(encoding="utf-8"), filename=str(MODULE_FILE)
        )

    @staticmethod
    def _referenced_names(tree: ast.AST) -> set[str]:
        referenced: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                referenced.add(node.id)
            elif isinstance(node, ast.Attribute):
                referenced.add(node.attr)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                referenced.update(alias.name for alias in node.names)
        return referenced

    def test_no_process_or_network_reference(self) -> None:
        forbidden = {
            "subprocess",
            "Popen",
            "socket",
            "ssl",
            "os_system",
        }
        referenced = self._referenced_names(self.tree)
        self.assertEqual(referenced & forbidden, set())
        self.assertNotIn("system", referenced)

    def test_no_kali_execution_authority_reference(self) -> None:
        forbidden = {
            "KaliToolGateway",
            "ToolExecutionService",
            "ResearchKaliOperationProcessAdapter",
            "WslKaliOperationProcessAdapter",
            "VmwareKaliOperationProcessAdapter",
        }
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())

    def test_no_dig_curl_nmap_literal_reference(self) -> None:
        forbidden = {"dig", "curl", "nmap"}
        self.assertEqual(self._referenced_names(self.tree) & forbidden, set())

    def test_no_wire_carried_command_vocabulary(self) -> None:
        forbidden = {"argv", "executable", "shell", "command", "script"}
        field_names: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(
                        item.target, ast.Name
                    ):
                        field_names.add(item.target.id)
        self.assertEqual(field_names & forbidden, set())


if __name__ == "__main__":
    unittest.main()
