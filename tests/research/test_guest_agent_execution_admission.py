"""Exact-request execution-admission boundary (v0.3.468).

VERIFIED DISPATCH != EXECUTION AUTHORITY BY ITSELF. RUNTIME READY !=
EXECUTION AUTHORITY BY ITSELF. EXECUTION ADMISSION IS BOUND TO ONE EXACT
VERIFIED REQUEST. Every positive test proves admission succeeds only when
a runtime-ready invocation corresponds exactly to the verified dispatch's
own request; every negative/adversarial test proves a confused-deputy
pairing (or any individually-insufficient input) is rejected, even when
both inputs are individually valid and unforgeable.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

import research.GuestAgentExecutionAdmission as admission_module  # noqa: E402
import research.GuestAgentInvocationPreparation as preparation_module  # noqa: E402
from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentDispatchSigning import (  # noqa: E402
    create_signed_dispatch_envelope,
)
from research.GuestAgentDispatchVerification import (  # noqa: E402
    GuestAgentVerifiedDispatch,
    verify_signed_dispatch_envelope,
)
from research.GuestAgentExecutionAdmission import (  # noqa: E402
    GuestAgentExecutionAdmission,
    GuestAgentExecutionBoundaryReceipt,
    GuestAgentExecutionBoundaryStatus,
    admit_guest_agent_execution,
)
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
    ResearchDnsRecordType,
    ResearchKaliCommandTransport,
    ResearchKaliOperationCommandPlan,
    ResearchKaliOperationKind,
)
from tests.research.test_guest_agent_host_authorization_handoff import (  # noqa: E402
    NOW,
    FakeAuthorizationStore,
    _authorize,
    _https_preview,
    _preview,
)
from tests.research.test_guest_agent_signed_dispatch_rpc_transport import (  # noqa: E402
    _sign_arbitrary_request_for_test,
)

MODULE_FILE = SRC_DIR / "research" / "GuestAgentExecutionAdmission.py"


class _MemoryReplayStore:
    def __init__(self) -> None:
        self._records: list = []

    def load(self) -> list:
        return list(self._records)

    def save(self, records: list) -> None:
        self._records = list(records)


class _AlwaysReadyProbe(GuestAgentLocalReadinessProbe):
    """Test double: reports READY for whatever it is handed, no subprocess."""

    def check(
        self, prepared_invocation: GuestAgentPreparedInvocation
    ) -> GuestAgentLocalReadinessReceipt:
        return GuestAgentLocalReadinessReceipt(
            operation_kind=prepared_invocation.operation_kind,
            state=GuestAgentLocalReadinessState.READY,
            reason="simulated ready for execution-admission tests",
            executable_path=prepared_invocation.command_plan.executable_path,
            observed_version="simulated version",
            probe_process_started=True,
        )


def _signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def _verified_v2_dispatch(
    signing_key: Ed25519PrivateKey,
    *,
    preview=None,
    request_id: str = "r1",
) -> GuestAgentVerifiedDispatch:
    preview = preview if preview is not None else _preview()
    authorization = _authorize(preview, authorization_id=f"auth-{request_id}")
    store = FakeAuthorizationStore([authorization])
    grant = consume_authorization_for_guest_agent_dispatch(
        store, authorization.authorization_id, preview, now=NOW
    )
    envelope = create_signed_dispatch_envelope(
        grant,
        request_id=request_id,
        nonce=f"nonce-{request_id}",
        signing_key=signing_key,
        now=NOW,
    )
    return verify_signed_dispatch_envelope(
        envelope, verification_key=signing_key.public_key(), now=NOW
    )


def _ready_invocation_for(
    verified: GuestAgentVerifiedDispatch,
    *,
    probe: GuestAgentLocalReadinessProbe | None = None,
) -> GuestAgentRuntimeReadyInvocation:
    replay_protector = GuestAgentReplayProtector(_MemoryReplayStore())
    _response, prepared = prepare_guest_agent_invocation(
        verified.request, replay_protector
    )
    assert prepared is not None
    _receipt, ready = check_guest_agent_runtime_readiness(
        prepared, probe or _AlwaysReadyProbe()
    )
    assert ready is not None
    return ready


def _full_chain(
    signing_key: Ed25519PrivateKey, *, preview=None, request_id: str = "r1"
) -> tuple[GuestAgentVerifiedDispatch, GuestAgentRuntimeReadyInvocation]:
    verified = _verified_v2_dispatch(
        signing_key, preview=preview, request_id=request_id
    )
    ready = _ready_invocation_for(verified)
    return verified, ready


def _tampered_ready_invocation(
    *,
    operation_kind: ResearchKaliOperationKind,
    command_plan: ResearchKaliOperationCommandPlan,
    timeout_seconds: float = 5.0,
) -> GuestAgentRuntimeReadyInvocation:
    """Reach into the module-private capability token to build an internally
    tampered prepared invocation, then wrap it as READY -- the only way to
    exercise exact-binding mismatches a legitimate chain could never
    produce."""
    tampered = GuestAgentPreparedInvocation(
        operation_kind=operation_kind,
        command_plan=command_plan,
        timeout_seconds=timeout_seconds,
        _capability_token=preparation_module._PREPARED_INVOCATION_CAPABILITY,
    )
    _receipt, ready = check_guest_agent_runtime_readiness(tampered, _AlwaysReadyProbe())
    assert ready is not None
    return ready


class ForgeryResistanceTests(unittest.TestCase):
    def test_cannot_construct_with_foreign_token(self) -> None:
        signing_key = _signing_key()
        verified, ready = _full_chain(signing_key)
        with self.assertRaises(ResearchError):
            GuestAgentExecutionAdmission(
                verified_dispatch=verified,
                runtime_ready_invocation=ready,
                _capability_token=object(),
            )

    def test_cannot_construct_without_token_kwarg(self) -> None:
        signing_key = _signing_key()
        verified, ready = _full_chain(signing_key)
        with self.assertRaises(TypeError):
            GuestAgentExecutionAdmission(  # type: ignore[call-arg]
                verified_dispatch=verified, runtime_ready_invocation=ready
            )

    def test_rejects_non_verified_dispatch(self) -> None:
        signing_key = _signing_key()
        _verified, ready = _full_chain(signing_key)
        with self.assertRaises(ResearchError):
            GuestAgentExecutionAdmission(
                verified_dispatch=object(),  # type: ignore[arg-type]
                runtime_ready_invocation=ready,
                _capability_token=admission_module._EXECUTION_ADMISSION_CAPABILITY,
            )

    def test_rejects_non_runtime_ready_invocation(self) -> None:
        signing_key = _signing_key()
        verified, _ready = _full_chain(signing_key)
        with self.assertRaises(ResearchError):
            GuestAgentExecutionAdmission(
                verified_dispatch=verified,
                runtime_ready_invocation=object(),  # type: ignore[arg-type]
                _capability_token=admission_module._EXECUTION_ADMISSION_CAPABILITY,
            )

    def test_verified_dispatch_alone_cannot_grant_admission(self) -> None:
        """A verified dispatch with no runtime-ready invocation at all
        cannot produce admission -- there is no code path that accepts
        only one argument."""
        import inspect

        parameters = list(inspect.signature(admit_guest_agent_execution).parameters)
        self.assertEqual(parameters, ["verified_dispatch", "runtime_ready_invocation"])

    def test_runtime_ready_invocation_alone_cannot_grant_admission(self) -> None:
        signing_key = _signing_key()
        _verified, ready = _full_chain(signing_key)
        with self.assertRaises(TypeError):
            GuestAgentExecutionAdmission(  # type: ignore[call-arg]
                runtime_ready_invocation=ready,
                _capability_token=admission_module._EXECUTION_ADMISSION_CAPABILITY,
            )


class ExactBindingSuccessTests(unittest.TestCase):
    def test_exact_dns_request_binds_and_admits(self) -> None:
        signing_key = _signing_key()
        verified, ready = _full_chain(signing_key, preview=_preview())
        receipt = admit_guest_agent_execution(verified, ready)
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertEqual(receipt.execution_admission.verified_dispatch, verified)
        self.assertIs(receipt.execution_admission.runtime_ready_invocation, ready)

    def test_exact_https_request_binds_and_admits(self) -> None:
        signing_key = _signing_key()
        verified, ready = _full_chain(signing_key, preview=_https_preview())
        receipt = admit_guest_agent_execution(verified, ready)
        self.assertIsNotNone(receipt)

    def test_admission_requires_bounded_probe_types(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionAdmission(
                verified_dispatch=object(),  # type: ignore[arg-type]
                runtime_ready_invocation=object(),  # type: ignore[arg-type]
                _capability_token=admission_module._EXECUTION_ADMISSION_CAPABILITY,
            )


class ExactBindingMismatchTests(unittest.TestCase):
    """Every case: individually-valid, unforgeable inputs; rejected anyway
    because the exact binding does not hold."""

    def test_different_hostname_fails(self) -> None:
        signing_key = _signing_key()
        verified, _ = _full_chain(
            signing_key, preview=_preview(hostname="example.com"), request_id="a"
        )
        _other_verified, other_ready = _full_chain(
            signing_key,
            preview=_preview(hostname="attacker.example"),
            request_id="b",
        )
        self.assertIsNone(admit_guest_agent_execution(verified, other_ready))

    def test_different_dns_record_type_fails(self) -> None:
        signing_key = _signing_key()
        verified, _ = _full_chain(
            signing_key,
            preview=_preview(dns_record_type=ResearchDnsRecordType.A),
            request_id="a",
        )
        _other_verified, other_ready = _full_chain(
            signing_key,
            preview=_preview(dns_record_type=ResearchDnsRecordType.AAAA),
            request_id="b",
        )
        self.assertIsNone(admit_guest_agent_execution(verified, other_ready))

    def test_different_resolved_address_fails(self) -> None:
        signing_key = _signing_key()
        verified, _ = _full_chain(
            signing_key,
            preview=_https_preview(resolved_address="93.184.216.34"),
            request_id="a",
        )
        _other_verified, other_ready = _full_chain(
            signing_key,
            preview=_https_preview(resolved_address="203.0.113.9"),
            request_id="b",
        )
        self.assertIsNone(admit_guest_agent_execution(verified, other_ready))

    def test_different_max_seconds_fails(self) -> None:
        signing_key = _signing_key()
        verified, _ = _full_chain(
            signing_key, preview=_preview(max_seconds=5.0), request_id="a"
        )
        _other_verified, other_ready = _full_chain(
            signing_key, preview=_preview(max_seconds=10.0), request_id="b"
        )
        self.assertIsNone(admit_guest_agent_execution(verified, other_ready))

    def test_different_operation_kind_fails(self) -> None:
        signing_key = _signing_key()
        verified, _ = _full_chain(signing_key, preview=_preview(), request_id="a")
        _other_verified, other_ready = _full_chain(
            signing_key, preview=_https_preview(), request_id="b"
        )
        self.assertIsNone(admit_guest_agent_execution(verified, other_ready))

    def test_different_executable_fails(self) -> None:
        signing_key = _signing_key()
        verified, _ = _full_chain(signing_key, preview=_preview())
        mismatched_plan = ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
            executable_path="/usr/bin/curl",
            argv=(
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
        tampered_ready = _tampered_ready_invocation(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            command_plan=mismatched_plan,
        )
        self.assertIsNone(admit_guest_agent_execution(verified, tampered_ready))

    def test_different_argv_fails(self) -> None:
        signing_key = _signing_key()
        verified, _ = _full_chain(signing_key, preview=_preview())
        mutated_argv_plan = ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
            executable_path="/usr/bin/dig",
            argv=(
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "example.com",
                "AAAA",
            ),
        )
        tampered_ready = _tampered_ready_invocation(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            command_plan=mutated_argv_plan,
        )
        self.assertIsNone(admit_guest_agent_execution(verified, tampered_ready))

    def test_different_transport_fails(self) -> None:
        signing_key = _signing_key()
        verified, _ = _full_chain(signing_key, preview=_preview())
        wsl_plan = ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.WSL_KALI,
            executable_path="/usr/bin/dig",
            argv=("/usr/bin/dig", "+time=5", "+tries=1", "+short", "example.com", "A"),
        )
        tampered_ready = _tampered_ready_invocation(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            command_plan=wsl_plan,
        )
        self.assertIsNone(admit_guest_agent_execution(verified, tampered_ready))

    def test_shell_mismatch_is_structurally_impossible(self) -> None:
        """There is no way to construct a `ResearchKaliOperationCommandPlan`
        with `shell=True` at all -- its own `__post_init__` forces
        `shell is False` unconditionally -- so a "shell mismatch" admission
        bypass cannot even be attempted, let alone succeed."""
        with self.assertRaises(ResearchError):
            ResearchKaliOperationCommandPlan(
                transport=ResearchKaliCommandTransport.GUEST_AGENT,
                executable_path="/usr/bin/dig",
                argv=(
                    "/usr/bin/dig",
                    "+time=5",
                    "+tries=1",
                    "+short",
                    "example.com",
                    "A",
                ),
                shell=True,
            )


class CrossRequestPairingTests(unittest.TestCase):
    """The confused-deputy case this milestone exists to close: both
    objects individually valid and unforgeable, produced for two different
    legitimate requests -- admission must still fail."""

    def test_valid_a_paired_with_valid_b_is_rejected(self) -> None:
        signing_key = _signing_key()
        verified_a, _ready_a = _full_chain(
            signing_key, preview=_preview(hostname="a.example"), request_id="a"
        )
        _verified_b, ready_b = _full_chain(
            signing_key, preview=_preview(hostname="b.example"), request_id="b"
        )
        self.assertIsNone(admit_guest_agent_execution(verified_a, ready_b))
        # The reverse pairing is rejected too.
        verified_b_again, ready_a_for_direct_check = _full_chain(
            signing_key, preview=_preview(hostname="b.example"), request_id="c"
        )
        self.assertIsNone(
            admit_guest_agent_execution(verified_a, ready_a_for_direct_check)
        )

    def test_both_individually_valid_but_mismatched_direct_construction_raises(
        self,
    ) -> None:
        signing_key = _signing_key()
        verified_a, _ready_a = _full_chain(
            signing_key, preview=_preview(hostname="a.example"), request_id="a"
        )
        _verified_b, ready_b = _full_chain(
            signing_key, preview=_preview(hostname="b.example"), request_id="b"
        )
        with self.assertRaises(ResearchError):
            GuestAgentExecutionAdmission(
                verified_dispatch=verified_a,
                runtime_ready_invocation=ready_b,
                _capability_token=admission_module._EXECUTION_ADMISSION_CAPABILITY,
            )


class V1Tests(unittest.TestCase):
    def test_v1_verified_dispatch_cannot_produce_admission(self) -> None:
        from research.GuestAgentProtocol import (
            GuestAgentProtocolVersion,
            GuestAgentRequest,
        )

        signing_key = _signing_key()
        v1_request = GuestAgentRequest(
            protocol_version=GuestAgentProtocolVersion.V1,
            request_id="v1-admission",
            nonce="v1-admission-nonce",
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            operation_digest="a" * 64,
            logical_inputs=(("hostname", "example.com"), ("dns_record_type", "A")),
        )
        envelope = _sign_arbitrary_request_for_test(
            v1_request, signing_key=signing_key, now=NOW
        )
        verified_v1 = verify_signed_dispatch_envelope(
            envelope, verification_key=signing_key.public_key(), now=NOW
        )
        self.assertIsNone(verified_v1.request.execution_limits)

        # A real, legitimate V2 ready invocation for an unrelated request.
        _other_verified, ready = _full_chain(signing_key, request_id="v2-other")

        self.assertIsNone(admit_guest_agent_execution(verified_v1, ready))
        with self.assertRaises(ResearchError):
            GuestAgentExecutionAdmission(
                verified_dispatch=verified_v1,
                runtime_ready_invocation=ready,
                _capability_token=admission_module._EXECUTION_ADMISSION_CAPABILITY,
            )


class ReceiptSemanticsTests(unittest.TestCase):
    def _admission(self) -> GuestAgentExecutionAdmission:
        signing_key = _signing_key()
        verified, ready = _full_chain(signing_key)
        return GuestAgentExecutionAdmission(
            verified_dispatch=verified,
            runtime_ready_invocation=ready,
            _capability_token=admission_module._EXECUTION_ADMISSION_CAPABILITY,
        )

    def test_default_receipt_reports_not_executed(self) -> None:
        receipt = GuestAgentExecutionBoundaryReceipt(
            execution_admission=self._admission()
        )
        self.assertEqual(receipt.status, GuestAgentExecutionBoundaryStatus.NOT_EXECUTED)
        self.assertFalse(receipt.process_created)
        self.assertFalse(receipt.target_operation_executed)
        self.assertFalse(receipt.target_network_used)
        self.assertEqual(receipt.output_lines, ())
        self.assertIsNone(receipt.exit_code)
        self.assertFalse(receipt.timed_out)
        self.assertFalse(receipt.evidence_recorded)
        self.assertFalse(receipt.claim_created)
        self.assertFalse(receipt.memory_written)

    def test_rejects_non_admission(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionBoundaryReceipt(execution_admission=object())  # type: ignore[arg-type]

    def test_rejects_process_created_true(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionBoundaryReceipt(
                execution_admission=self._admission(), process_created=True
            )

    def test_rejects_target_operation_executed_true(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionBoundaryReceipt(
                execution_admission=self._admission(), target_operation_executed=True
            )

    def test_rejects_target_network_used_true(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionBoundaryReceipt(
                execution_admission=self._admission(), target_network_used=True
            )

    def test_rejects_output_lines(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionBoundaryReceipt(
                execution_admission=self._admission(), output_lines=("fake stdout",)
            )

    def test_rejects_exit_code(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionBoundaryReceipt(
                execution_admission=self._admission(), exit_code=0
            )

    def test_rejects_timed_out_true(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionBoundaryReceipt(
                execution_admission=self._admission(), timed_out=True
            )

    def test_rejects_evidence_recorded_true(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionBoundaryReceipt(
                execution_admission=self._admission(), evidence_recorded=True
            )

    def test_rejects_claim_created_true(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionBoundaryReceipt(
                execution_admission=self._admission(), claim_created=True
            )

    def test_rejects_memory_written_true(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionBoundaryReceipt(
                execution_admission=self._admission(), memory_written=True
            )

    def test_rejects_invalid_status(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentExecutionBoundaryReceipt(
                execution_admission=self._admission(), status="success"  # type: ignore[arg-type]
            )


class CompositionFunctionTests(unittest.TestCase):
    def test_ready_pair_admits_exactly_once(self) -> None:
        signing_key = _signing_key()
        verified, ready = _full_chain(signing_key)
        receipt = admit_guest_agent_execution(verified, ready)
        self.assertIsInstance(receipt, GuestAgentExecutionBoundaryReceipt)

    def test_mismatched_pair_returns_none_never_raises(self) -> None:
        signing_key = _signing_key()
        verified_a, _ = _full_chain(
            signing_key, preview=_preview(hostname="a.example"), request_id="a"
        )
        _verified_b, ready_b = _full_chain(
            signing_key, preview=_preview(hostname="b.example"), request_id="b"
        )
        # Must not raise -- admit_guest_agent_execution is the fail-closed
        # boundary that converts every ResearchError into "no admission".
        result = admit_guest_agent_execution(verified_a, ready_b)
        self.assertIsNone(result)

    def test_admission_does_not_mutate_inputs(self) -> None:
        signing_key = _signing_key()
        verified, ready = _full_chain(signing_key)
        original_timeout = ready.prepared_invocation.timeout_seconds
        original_plan = ready.prepared_invocation.command_plan
        admit_guest_agent_execution(verified, ready)
        self.assertEqual(ready.prepared_invocation.timeout_seconds, original_timeout)
        self.assertIs(ready.prepared_invocation.command_plan, original_plan)


class StructuralSecurityTests(unittest.TestCase):
    """AST-level proof that this module contains no process, network, or
    package-installation channel of any kind -- pure in-process validation
    and composition only."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = MODULE_FILE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_no_forbidden_imports(self) -> None:
        forbidden_modules = {
            "subprocess",
            "socket",
            "requests",
            "urllib",
            "httpx",
            "dns",
            "paramiko",
            "ssl",
        }
        imported: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported & forbidden_modules, imported & forbidden_modules)

    def test_no_shell_true_anywhere(self) -> None:
        self.assertNotIn("shell=True", self.source)
        self.assertNotIn("shell = True", self.source)

    def test_no_os_system_or_popen_or_command_plan_argv_execution(self) -> None:
        """AST-level, not substring-level: the module's own docstring
        prose *names* `os.system`/`subprocess.Popen`/`command_plan.argv`
        as things it does NOT do, so a substring check would false-positive
        on the docstring itself. Checked structurally instead: no call
        node targets `os.system`/`subprocess.Popen`, and no attribute
        access reads `.argv` off a `.command_plan` attribute chain."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "system" and (
                    isinstance(node.func.value, ast.Name) and node.func.value.id == "os"
                ):
                    self.fail("os.system call found")
                if node.func.attr == "Popen":
                    self.fail("subprocess.Popen call found")
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "argv"
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "command_plan"
            ):
                self.fail("command_plan.argv attribute access found")

    def test_no_forbidden_identifiers(self) -> None:
        forbidden_identifiers = {
            "ssh",
            "vmrun",
            "wsl",
            "bash",
            "cmd",
            "powershell",
            "KaliToolGateway",
            "ProcessAdapter",
            "GuestAgentCapabilityExecutor",
            "GuestAgentProcessAdapter",
            "GuestAgentDnsExecutor",
            "GuestAgentHttpsExecutor",
            "GuestAgentOperationRunner",
        }
        names = {
            node.id for node in ast.walk(self.tree) if isinstance(node, ast.Name)
        } | {
            node.attr for node in ast.walk(self.tree) if isinstance(node, ast.Attribute)
        }
        self.assertFalse(names & forbidden_identifiers, names & forbidden_identifiers)

    def test_no_package_install_strings(self) -> None:
        lowered = self.source.lower()
        for token in ("apt-get", "apt ", "pip install", "sudo"):
            self.assertNotIn(token, lowered)

    def test_no_generic_execute_or_run_callback(self) -> None:
        forbidden_function_names = {"execute", "run", "run_command", "exec"}
        function_names = {
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef)
        }
        self.assertEqual(function_names & forbidden_function_names, set())


if __name__ == "__main__":
    unittest.main()
