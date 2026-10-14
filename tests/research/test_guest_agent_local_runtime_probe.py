"""Local Guest-Agent runtime-readiness probe (v0.3.467).

PREPARED INVOCATION != RUNTIME READY. LOCAL READINESS PROCESS != TARGET
OPERATION. Every positive test proves the probe invokes exactly one of the
two fixed version-probe tuples (`/usr/bin/dig -v`, `/usr/bin/curl
--version`), never the prepared invocation's own reviewed target argv.
Every negative/adversarial test proves a fail-closed `UNAVAILABLE` receipt
with zero subprocess attempts whenever a cross-check fails before probing,
or a correctly-classified `UNAVAILABLE` receipt (with
`probe_process_started=True`) whenever the probe itself fails.
"""

from __future__ import annotations

import ast
import math
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import research.GuestAgentInvocationPreparation as preparation_module  # noqa: E402
import research.GuestAgentLocalRuntimeProbe as probe_module  # noqa: E402
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
    UnavailableGuestAgentLocalReadinessProbe,
)
from research.GuestAgentLocalRuntimeProbe import (  # noqa: E402
    GUEST_AGENT_READINESS_TIMEOUT_SECONDS,
    GuestAgentLocalRuntimeProbe,
)
from research.GuestAgentReplayProtector import GuestAgentReplayProtector  # noqa: E402
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchKaliCommandTransport,
    ResearchKaliOperationCommandPlan,
    ResearchKaliOperationKind,
    kali_operation_command_plan,
)
from tests.research.test_guest_agent_host_authorization_handoff import (  # noqa: E402
    NOW,
    FakeAuthorizationStore,
    _authorize,
    _https_preview,
    _preview,
)

MODULE_FILE = SRC_DIR / "research" / "GuestAgentLocalRuntimeProbe.py"


class _MemoryReplayStore:
    def __init__(self) -> None:
        self._records: list = []

    def load(self) -> list:
        return list(self._records)

    def save(self, records: list) -> None:
        self._records = list(records)


def _prepared_invocation(
    *, preview=None, request_id: str = "r1"
) -> GuestAgentPreparedInvocation:
    """Build one real, unforgeable `GuestAgentPreparedInvocation`."""
    preview = preview if preview is not None else _preview()
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


def _tampered_prepared_invocation(
    *,
    operation_kind: ResearchKaliOperationKind,
    command_plan: ResearchKaliOperationCommandPlan,
    timeout_seconds: float = 5.0,
) -> GuestAgentPreparedInvocation:
    """Reach into the module-private capability token to build an internally
    inconsistent prepared invocation -- the only way to exercise the probe's
    defense-in-depth cross-checks, since every real prepared invocation
    already satisfies them by construction."""
    return GuestAgentPreparedInvocation(
        operation_kind=operation_kind,
        command_plan=command_plan,
        timeout_seconds=timeout_seconds,
        _capability_token=preparation_module._PREPARED_INVOCATION_CAPABILITY,
    )


def _completed(
    *, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=(), returncode=returncode, stdout=stdout, stderr=stderr
    )


class ReceiptValidationTests(unittest.TestCase):
    def test_rejects_invalid_operation_kind(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalReadinessReceipt(
                operation_kind="dns_record_lookup",  # type: ignore[arg-type]
                state=GuestAgentLocalReadinessState.READY,
                reason="x",
            )

    def test_rejects_invalid_state(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalReadinessReceipt(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                state="ready",  # type: ignore[arg-type]
                reason="x",
            )

    def test_rejects_empty_reason(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalReadinessReceipt(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                state=GuestAgentLocalReadinessState.UNAVAILABLE,
                reason="   ",
            )

    def test_rejects_relative_executable_path(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalReadinessReceipt(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                state=GuestAgentLocalReadinessState.READY,
                reason="x",
                executable_path="usr/bin/dig",
            )

    def test_rejects_oversized_observed_version(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalReadinessReceipt(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                state=GuestAgentLocalReadinessState.READY,
                reason="x",
                observed_version="a" * 501,
            )

    def test_rejects_true_target_operation_executed(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalReadinessReceipt(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                state=GuestAgentLocalReadinessState.UNAVAILABLE,
                reason="x",
                target_operation_executed=True,
            )

    def test_rejects_true_target_network_used(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalReadinessReceipt(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                state=GuestAgentLocalReadinessState.UNAVAILABLE,
                reason="x",
                target_network_used=True,
            )

    def test_ready_property(self) -> None:
        ready = GuestAgentLocalReadinessReceipt(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            state=GuestAgentLocalReadinessState.READY,
            reason="x",
        )
        unavailable = GuestAgentLocalReadinessReceipt(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            state=GuestAgentLocalReadinessState.UNAVAILABLE,
            reason="x",
        )
        self.assertTrue(ready.ready)
        self.assertFalse(unavailable.ready)


class AbstractContractTests(unittest.TestCase):
    def test_abstract_probe_raises_not_implemented(self) -> None:
        class _Bare(GuestAgentLocalReadinessProbe):
            pass

        with self.assertRaises(NotImplementedError):
            _Bare().check(_prepared_invocation())

    def test_unavailable_default_probe_fails_closed_with_zero_subprocess(self) -> None:
        with mock.patch.object(subprocess, "run") as run:
            receipt = UnavailableGuestAgentLocalReadinessProbe().check(
                _prepared_invocation()
            )
        run.assert_not_called()
        self.assertFalse(receipt.ready)
        self.assertFalse(receipt.probe_process_started)

    def test_unavailable_probe_requires_prepared_invocation(self) -> None:
        with self.assertRaises(ResearchError):
            UnavailableGuestAgentLocalReadinessProbe().check(object())  # type: ignore[arg-type]


class TimeoutConstructorTests(unittest.TestCase):
    def test_default_timeout_is_the_ceiling(self) -> None:
        probe = GuestAgentLocalRuntimeProbe()
        self.assertEqual(probe._timeout_seconds, GUEST_AGENT_READINESS_TIMEOUT_SECONDS)

    def test_rejects_bool(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalRuntimeProbe(timeout_seconds=True)

    def test_rejects_zero(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalRuntimeProbe(timeout_seconds=0)

    def test_rejects_negative(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalRuntimeProbe(timeout_seconds=-1.0)

    def test_rejects_nan(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalRuntimeProbe(timeout_seconds=math.nan)

    def test_rejects_infinity(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalRuntimeProbe(timeout_seconds=math.inf)

    def test_rejects_above_ceiling(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalRuntimeProbe(
                timeout_seconds=GUEST_AGENT_READINESS_TIMEOUT_SECONDS + 0.01
            )

    def test_accepts_exact_ceiling(self) -> None:
        GuestAgentLocalRuntimeProbe(
            timeout_seconds=GUEST_AGENT_READINESS_TIMEOUT_SECONDS
        )


class RequiresPreparedInvocationTests(unittest.TestCase):
    def test_rejects_non_prepared_invocation(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentLocalRuntimeProbe().check(object())  # type: ignore[arg-type]

    def test_rejects_guest_agent_request_directly(self) -> None:
        preview = _preview()
        authorization = _authorize(preview)
        store = FakeAuthorizationStore([authorization])
        grant = consume_authorization_for_guest_agent_dispatch(
            store, authorization.authorization_id, preview, now=NOW
        )
        request = grant.materialize_request(request_id="r", nonce="n")
        with self.assertRaises(ResearchError):
            GuestAgentLocalRuntimeProbe().check(request)  # type: ignore[arg-type]


class DnsReadinessArgvTests(unittest.TestCase):
    def test_dns_probes_exactly_dig_dash_v(self) -> None:
        prepared = _prepared_invocation(preview=_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="DiG 9.18.0\n")
        ) as run:
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0], ("/usr/bin/dig", "-v"))
        self.assertTrue(receipt.ready)

    def test_hostname_never_enters_readiness_argv(self) -> None:
        prepared = _prepared_invocation(preview=_preview(hostname="attacker.example"))
        self.assertIn("attacker.example", prepared.command_plan.argv)
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="DiG 9.18.0\n")
        ) as run:
            GuestAgentLocalRuntimeProbe().check(prepared)
        argv = run.call_args[0][0]
        self.assertNotIn("attacker.example", argv)

    def test_dns_record_type_never_enters_readiness_argv(self) -> None:
        prepared = _prepared_invocation(preview=_preview())
        self.assertIn("A", prepared.command_plan.argv)
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="DiG 9.18.0\n")
        ) as run:
            GuestAgentLocalRuntimeProbe().check(prepared)
        argv = run.call_args[0][0]
        self.assertEqual(argv, ("/usr/bin/dig", "-v"))

    def test_operation_argv_never_used_as_readiness_argv(self) -> None:
        prepared = _prepared_invocation(preview=_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="DiG 9.18.0\n")
        ) as run:
            GuestAgentLocalRuntimeProbe().check(prepared)
        argv = run.call_args[0][0]
        self.assertNotEqual(argv, prepared.command_plan.argv)
        self.assertEqual(argv, ("/usr/bin/dig", "-v"))


class HttpsReadinessArgvTests(unittest.TestCase):
    def test_https_probes_exactly_curl_dash_dash_version(self) -> None:
        prepared = _prepared_invocation(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="curl 7.88.1\n")
        ) as run:
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        run.assert_called_once()
        args, _kwargs = run.call_args
        self.assertEqual(args[0], ("/usr/bin/curl", "--version"))
        self.assertTrue(receipt.ready)

    def test_resolved_address_never_enters_readiness_argv(self) -> None:
        prepared = _prepared_invocation(
            preview=_https_preview(resolved_address="203.0.113.9")
        )
        self.assertTrue(
            any("203.0.113.9" in part for part in prepared.command_plan.argv)
        )
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="curl 7.88.1\n")
        ) as run:
            GuestAgentLocalRuntimeProbe().check(prepared)
        argv = run.call_args[0][0]
        self.assertTrue(all("203.0.113.9" not in part for part in argv))


class SubprocessInvocationShapeTests(unittest.TestCase):
    def test_shell_is_never_true(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="DiG 9.18.0\n")
        ) as run:
            GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_stdin_is_devnull(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="DiG 9.18.0\n")
        ) as run:
            GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_check_is_false(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="DiG 9.18.0\n")
        ) as run:
            GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertFalse(run.call_args.kwargs["check"])

    def test_timeout_is_bounded(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="DiG 9.18.0\n")
        ) as run:
            GuestAgentLocalRuntimeProbe(timeout_seconds=2.0).check(prepared)
        self.assertEqual(run.call_args.kwargs["timeout"], 2.0)


class OutputBoundingTests(unittest.TestCase):
    def test_output_is_truncated_to_500_characters(self) -> None:
        prepared = _prepared_invocation()
        huge = "DiG 9.18.0\n" + ("x" * 1000)
        with mock.patch.object(subprocess, "run", return_value=_completed(stdout=huge)):
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertTrue(receipt.ready)
        self.assertLessEqual(len(receipt.observed_version or ""), 500)

    def test_control_characters_are_sanitized(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.object(
            subprocess,
            "run",
            return_value=_completed(stdout="DiG 9.18.0\x07\x1b[31m"),
        ):
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertTrue(receipt.ready)
        assert receipt.observed_version is not None
        self.assertNotIn("\x07", receipt.observed_version)
        self.assertNotIn("\x1b", receipt.observed_version)


class ReadyAndUnavailableOutcomeTests(unittest.TestCase):
    def test_exit_zero_correct_dig_version_is_ready(self) -> None:
        prepared = _prepared_invocation(preview=_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="DiG 9.18.0\n")
        ):
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertTrue(receipt.ready)
        self.assertTrue(receipt.probe_process_started)
        self.assertEqual(receipt.executable_path, "/usr/bin/dig")

    def test_exit_zero_correct_curl_version_is_ready(self) -> None:
        prepared = _prepared_invocation(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="curl 7.88.1\n")
        ):
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertTrue(receipt.ready)
        self.assertEqual(receipt.executable_path, "/usr/bin/curl")

    def test_exit_zero_wrong_version_is_unavailable(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="BIND 9.x\n")
        ):
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertFalse(receipt.ready)
        self.assertTrue(receipt.probe_process_started)

    def test_empty_output_is_unavailable(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.object(subprocess, "run", return_value=_completed(stdout="")):
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertFalse(receipt.ready)

    def test_nonzero_exit_is_unavailable(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.object(
            subprocess,
            "run",
            return_value=_completed(returncode=1, stdout="DiG 9.18.0"),
        ):
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertFalse(receipt.ready)
        self.assertTrue(receipt.probe_process_started)

    def test_timeout_is_unavailable(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.object(
            subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="dig", timeout=5.0),
        ):
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertFalse(receipt.ready)
        self.assertTrue(receipt.probe_process_started)

    def test_missing_executable_oserror_is_unavailable(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.object(
            subprocess, "run", side_effect=FileNotFoundError("no such file")
        ):
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertFalse(receipt.ready)
        self.assertTrue(receipt.probe_process_started)


class CrossCheckFailClosedTests(unittest.TestCase):
    """Every case here proves zero subprocess attempts: the cross-check
    fails before `check()` ever reaches `subprocess.run`."""

    def test_unsupported_operation_fails_closed(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.dict(probe_module._READINESS_TOOL_SPECS, clear=True):
            with mock.patch.object(subprocess, "run") as run:
                receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        run.assert_not_called()
        self.assertFalse(receipt.ready)
        self.assertFalse(receipt.probe_process_started)

    def test_wrong_transport_fails_closed(self) -> None:
        wsl_plan = kali_operation_command_plan(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            hostname="example.com",
            dns_record_type=_preview().dns_record_type,
            transport=ResearchKaliCommandTransport.WSL_KALI,
        )
        tampered = _tampered_prepared_invocation(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            command_plan=wsl_plan,
        )
        with mock.patch.object(subprocess, "run") as run:
            receipt = GuestAgentLocalRuntimeProbe().check(tampered)
        run.assert_not_called()
        self.assertFalse(receipt.ready)
        self.assertFalse(receipt.probe_process_started)

    def test_executable_path_mismatch_fails_closed(self) -> None:
        mismatched_plan = ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
            executable_path="/usr/bin/curl",
            argv=("/usr/bin/curl", "--head", "https://example.com/"),
        )
        tampered = _tampered_prepared_invocation(
            operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
            command_plan=mismatched_plan,
        )
        with mock.patch.object(subprocess, "run") as run:
            receipt = GuestAgentLocalRuntimeProbe().check(tampered)
        run.assert_not_called()
        self.assertFalse(receipt.ready)
        self.assertFalse(receipt.probe_process_started)


class NoTargetOperationClaimTests(unittest.TestCase):
    def test_ready_receipt_never_claims_target_operation_or_network(self) -> None:
        prepared = _prepared_invocation()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="DiG 9.18.0\n")
        ):
            receipt = GuestAgentLocalRuntimeProbe().check(prepared)
        self.assertFalse(receipt.target_operation_executed)
        self.assertFalse(receipt.target_network_used)


class StructuralSecurityTests(unittest.TestCase):
    """AST-level proof that this module contains no generic process,
    network, or package-installation channel of any kind."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = MODULE_FILE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_no_forbidden_imports(self) -> None:
        forbidden_modules = {
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

    def test_no_os_system_or_popen(self) -> None:
        self.assertNotIn("os.system", self.source)
        self.assertNotIn("Popen", self.source)

    def test_no_forbidden_identifiers(self) -> None:
        forbidden_identifiers = {
            "ssh",
            "vmrun",
            "wsl",
            "bash",
            "sh",
            "cmd",
            "powershell",
            "KaliToolGateway",
            "ProcessAdapter",
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

    def test_readiness_tool_specs_is_a_literal_dict_not_enum_derived(self) -> None:
        """The allowlist must be a `Dict` literal with exactly two entries,
        never built by calling `ResearchKaliOperationKind` iteration/
        comprehension machinery."""
        assignment = None
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "_READINESS_TOOL_SPECS"
            ):
                assignment = node
                break
        self.assertIsNotNone(assignment)
        assert assignment is not None
        self.assertIsInstance(assignment.value, ast.Dict)
        assert isinstance(assignment.value, ast.Dict)
        self.assertEqual(len(assignment.value.keys), 2)
        for key_node in assignment.value.keys:
            self.assertIsInstance(key_node, ast.Attribute)
            assert isinstance(key_node, ast.Attribute)
            self.assertEqual(
                key_node.attr in ("DNS_RECORD_LOOKUP", "HTTPS_HEADER_LOOKUP"), True
            )

    def test_subprocess_run_argv_is_always_the_spec_tuple_not_command_plan_argv(
        self,
    ) -> None:
        """Static proof the one `subprocess.run` call site's first argument
        is the `spec.version_argv` attribute, never
        `prepared_invocation.command_plan.argv` or any name derived from
        caller-controlled text."""
        call_nodes = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ]
        self.assertEqual(len(call_nodes), 1)
        first_arg = call_nodes[0].args[0]
        self.assertIsInstance(first_arg, ast.Attribute)
        assert isinstance(first_arg, ast.Attribute)
        self.assertEqual(first_arg.attr, "version_argv")
        self.assertIsInstance(first_arg.value, ast.Name)
        assert isinstance(first_arg.value, ast.Name)
        self.assertEqual(first_arg.value.id, "spec")


if __name__ == "__main__":
    unittest.main()
