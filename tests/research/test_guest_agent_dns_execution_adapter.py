"""First real Guest-Agent DNS_RECORD_LOOKUP executor adapter (v0.3.469).

EXECUTION ADMISSION != EXECUTION SUCCESS. DNS PROCESS STARTED != DNS
SUCCESS. DNS OUTPUT != TRUSTED EVIDENCE. Every positive test proves the
executor invokes exactly `("/usr/bin/dig", "+time=5", "+tries=1",
"+short", <hostname>, <record type>)` with the exact admitted timeout,
derived only from a real `GuestAgentExecutionAdmission`. Every negative/
adversarial test proves a fail-closed outcome -- HTTPS before subprocess,
a defense-in-depth command-plan mismatch, a forged admission, or a
caller attempting to supply any target fact separately.

NOTE on command-plan-mismatch testing: `GuestAgentExecutionAdmission`
(v0.3.468) independently re-proves its own exact binding even when
constructed with its real private capability token, so a legitimately
unforgeable `GuestAgentExecutionAdmission` can never wrap a prepared
invocation whose command plan does not match its verified dispatch's own
reconstructed plan -- this executor's own `_validate_reviewed_dns_command
_plan` defense-in-depth checks are therefore structurally unreachable
through the only public entry point today (a deliberate security
property, not a test gap). Those checks are proven directly by calling
the private validator itself with handcrafted command plans -- the only
way to exercise that code at all, mirroring how v0.3.467 tested
`GuestAgentLocalRuntimeProbe`'s own cross-checks the same way.

No real DNS query, no real Kali VM, no Internet contact, and no
dependency on `/usr/bin/dig` actually existing on this runner: every
`subprocess.run` call in this file is mocked/patched deterministically.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentDnsExecutionAdapter import (  # noqa: E402
    GuestAgentDnsExecutionResult,
    _validate_reviewed_dns_command_plan,
    execute_guest_agent_dns_record_lookup,
)
from research.GuestAgentExecutionAdmission import (  # noqa: E402
    GuestAgentExecutionAdmission,
    admit_guest_agent_execution,
)
from research.ResearchKaliOperationExecution import (  # noqa: E402
    MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
    MAX_KALI_OPERATION_OUTPUT_LINES,
)
from research.ResearchKaliOperationPreview import (  # noqa: E402
    ResearchKaliCommandTransport,
    ResearchKaliOperationCommandPlan,
    ResearchKaliOperationKind,
)
from tests.research.test_guest_agent_execution_admission import (  # noqa: E402
    _full_chain,
    _signing_key,
)
from tests.research.test_guest_agent_host_authorization_handoff import (  # noqa: E402
    _https_preview,
    _preview,
)

MODULE_FILE = SRC_DIR / "research" / "GuestAgentDnsExecutionAdapter.py"
TRANSPORT_MODULE_FILE = SRC_DIR / "research" / "GuestAgentSignedDispatchRpcTransport.py"


def _execution_admission(
    *, preview=None, request_id: str = "r1"
) -> GuestAgentExecutionAdmission:
    signing_key = _signing_key()
    verified, ready = _full_chain(signing_key, preview=preview, request_id=request_id)
    receipt = admit_guest_agent_execution(verified, ready)
    assert receipt is not None
    return receipt.execution_admission


def _completed(
    *, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=(), returncode=returncode, stdout=stdout, stderr=stderr
    )


class AuthorityPreconditionTests(unittest.TestCase):
    def test_requires_real_execution_admission_type(self) -> None:
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_dns_record_lookup(object())  # type: ignore[arg-type]
        run.assert_not_called()

    def test_rejects_guest_agent_request_directly(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_dns_record_lookup(
                    admission.verified_dispatch.request  # type: ignore[arg-type]
                )
        run.assert_not_called()

    def test_rejects_verified_dispatch_alone(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_dns_record_lookup(
                    admission.verified_dispatch  # type: ignore[arg-type]
                )
        run.assert_not_called()

    def test_rejects_prepared_invocation_alone(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_dns_record_lookup(
                    admission.runtime_ready_invocation.prepared_invocation  # type: ignore[arg-type]
                )
        run.assert_not_called()

    def test_rejects_runtime_ready_invocation_alone(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_dns_record_lookup(
                    admission.runtime_ready_invocation  # type: ignore[arg-type]
                )
        run.assert_not_called()

    def test_signature_accepts_only_execution_admission(self) -> None:
        import inspect

        parameters = list(
            inspect.signature(execute_guest_agent_dns_record_lookup).parameters
        )
        self.assertEqual(parameters, ["execution_admission"])


class DnsAdmissionAcceptedTests(unittest.TestCase):
    def test_dns_admission_is_accepted_and_executes(self) -> None:
        admission = _execution_admission(preview=_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="93.184.216.34\n")
        ) as run:
            result = execute_guest_agent_dns_record_lookup(admission)
        run.assert_called_once()
        self.assertIsInstance(result, GuestAgentDnsExecutionResult)
        self.assertTrue(result.process_created)
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.timed_out)

    def test_exact_argv_matches_fixed_prefix_plus_real_hostname_and_type(
        self,
    ) -> None:
        admission = _execution_admission(preview=_preview(hostname="example.com"))
        command_plan = (
            admission.runtime_ready_invocation.prepared_invocation.command_plan
        )
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            execute_guest_agent_dns_record_lookup(admission)
        argv = run.call_args[0][0]
        self.assertEqual(
            argv, ("/usr/bin/dig", "+time=5", "+tries=1", "+short", "example.com", "A")
        )
        self.assertEqual(argv, command_plan.argv)

    def test_https_admission_rejected_before_subprocess(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_dns_record_lookup(admission)
        run.assert_not_called()


class NoSeparateParameterTests(unittest.TestCase):
    def test_hostname_cannot_be_supplied_separately(self) -> None:
        import inspect

        self.assertNotIn(
            "hostname",
            inspect.signature(execute_guest_agent_dns_record_lookup).parameters,
        )

    def test_record_type_cannot_be_supplied_separately(self) -> None:
        import inspect

        self.assertNotIn(
            "record_type",
            inspect.signature(execute_guest_agent_dns_record_lookup).parameters,
        )

    def test_executable_cannot_be_supplied_separately(self) -> None:
        import inspect

        parameters = inspect.signature(execute_guest_agent_dns_record_lookup).parameters
        self.assertNotIn("executable", parameters)
        self.assertNotIn("executable_path", parameters)

    def test_argv_cannot_be_supplied_separately(self) -> None:
        import inspect

        self.assertNotIn(
            "argv", inspect.signature(execute_guest_agent_dns_record_lookup).parameters
        )

    def test_timeout_cannot_be_supplied_separately(self) -> None:
        import inspect

        parameters = inspect.signature(execute_guest_agent_dns_record_lookup).parameters
        self.assertNotIn("timeout", parameters)
        self.assertNotIn("timeout_seconds", parameters)


class TimeoutBindingTests(unittest.TestCase):
    def test_timeout_equals_prepared_invocation_timeout_exactly(self) -> None:
        admission = _execution_admission(preview=_preview(max_seconds=7.0))
        expected_timeout = (
            admission.runtime_ready_invocation.prepared_invocation.timeout_seconds
        )
        self.assertEqual(expected_timeout, 7.0)
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            execute_guest_agent_dns_record_lookup(admission)
        self.assertEqual(run.call_args.kwargs["timeout"], 7.0)

    def test_different_admission_different_timeout(self) -> None:
        admission = _execution_admission(preview=_preview(max_seconds=3.5))
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            execute_guest_agent_dns_record_lookup(admission)
        self.assertEqual(run.call_args.kwargs["timeout"], 3.5)

    def test_caller_cannot_widen_timeout(self) -> None:
        """There is no parameter through which a caller could request a
        larger timeout than the one bound into the admission."""
        import inspect

        parameters = inspect.signature(execute_guest_agent_dns_record_lookup).parameters
        self.assertEqual(len(parameters), 1)


class SubprocessInvocationShapeTests(unittest.TestCase):
    def test_shell_is_false(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            execute_guest_agent_dns_record_lookup(admission)
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_stdin_is_devnull(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            execute_guest_agent_dns_record_lookup(admission)
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_capture_output_is_true(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            execute_guest_agent_dns_record_lookup(admission)
        self.assertTrue(run.call_args.kwargs["capture_output"])

    def test_text_is_true(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            execute_guest_agent_dns_record_lookup(admission)
        self.assertTrue(run.call_args.kwargs["text"])

    def test_encoding_is_utf8(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            execute_guest_agent_dns_record_lookup(admission)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")

    def test_errors_is_replace(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            execute_guest_agent_dns_record_lookup(admission)
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_check_is_false(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            execute_guest_agent_dns_record_lookup(admission)
        self.assertFalse(run.call_args.kwargs["check"])

    def test_exactly_one_subprocess_run_call(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ) as run:
            execute_guest_agent_dns_record_lookup(admission)
        run.assert_called_once()


class ResultOutcomeTests(unittest.TestCase):
    def test_timeout_produces_bounded_typed_result(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="dig", timeout=5.0),
        ):
            result = execute_guest_agent_dns_record_lookup(admission)
        self.assertTrue(result.process_created)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)
        self.assertEqual(result.stdout_lines, ())
        self.assertEqual(result.stderr_lines, ())

    def test_nonzero_exit_is_not_reported_as_success(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(returncode=1, stderr="error")
        ):
            result = execute_guest_agent_dns_record_lookup(admission)
        self.assertEqual(result.exit_code, 1)
        self.assertFalse(result.timed_out)
        # No "success" field exists anywhere on this type to set.
        self.assertFalse(hasattr(result, "success"))

    def test_oserror_fails_closed_without_leaking_exception_text(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess,
            "run",
            side_effect=FileNotFoundError("/some/secret/path/leaked"),
        ):
            with self.assertRaises(ResearchError) as context:
                execute_guest_agent_dns_record_lookup(admission)
        message = str(context.exception)
        self.assertNotIn("/some/secret/path/leaked", message)
        self.assertIn("FileNotFoundError", message)

    def test_exit_code_zero_is_never_fabricated_on_oserror(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", side_effect=PermissionError("denied")
        ):
            with self.assertRaises(ResearchError):
                execute_guest_agent_dns_record_lookup(admission)
        # No result object is even returned on OSError -- confirmed by
        # the raise above; there is no code path that could fabricate
        # exit_code=0 here.


class OutputBoundingTests(unittest.TestCase):
    def test_stdout_bounded_to_line_ceiling(self) -> None:
        admission = _execution_admission()
        huge_stdout = "\n".join(f"line{i}" for i in range(200))
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout=huge_stdout)
        ):
            result = execute_guest_agent_dns_record_lookup(admission)
        self.assertLessEqual(len(result.stdout_lines), MAX_KALI_OPERATION_OUTPUT_LINES)

    def test_stdout_bounded_to_character_ceiling(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="x" * 2000)
        ):
            result = execute_guest_agent_dns_record_lookup(admission)
        for line in result.stdout_lines:
            self.assertLessEqual(len(line), MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS)

    def test_stderr_bounded(self) -> None:
        admission = _execution_admission()
        huge_stderr = "\n".join(f"err{i}" for i in range(200))
        with mock.patch.object(
            subprocess,
            "run",
            return_value=_completed(returncode=1, stderr=huge_stderr),
        ):
            result = execute_guest_agent_dns_record_lookup(admission)
        self.assertLessEqual(len(result.stderr_lines), MAX_KALI_OPERATION_OUTPUT_LINES)

    def test_control_characters_sanitized(self) -> None:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\x07\x1b[31m")
        ):
            result = execute_guest_agent_dns_record_lookup(admission)
        combined = "".join(result.stdout_lines)
        self.assertNotIn("\x07", combined)
        self.assertNotIn("\x1b", combined)


class UntrustedOutputSemanticsTests(unittest.TestCase):
    def _real_result(self) -> GuestAgentDnsExecutionResult:
        admission = _execution_admission()
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="1.2.3.4\n")
        ):
            return execute_guest_agent_dns_record_lookup(admission)

    def test_output_trust_label_is_untrusted(self) -> None:
        result = self._real_result()
        self.assertEqual(result.output_trust, "untrusted_process_output")

    def test_evidence_recorded_is_false(self) -> None:
        self.assertFalse(self._real_result().evidence_recorded)

    def test_claim_created_is_false(self) -> None:
        self.assertFalse(self._real_result().claim_created)

    def test_source_accepted_is_false(self) -> None:
        self.assertFalse(self._real_result().source_accepted)

    def test_memory_written_is_false(self) -> None:
        self.assertFalse(self._real_result().memory_written)

    def test_result_rejects_evidence_recorded_true(self) -> None:
        admission = _execution_admission()
        with self.assertRaises(ResearchError):
            GuestAgentDnsExecutionResult(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                command_plan=admission.runtime_ready_invocation.prepared_invocation.command_plan,
                process_created=True,
                exit_code=0,
                timed_out=False,
                stdout_lines=(),
                stderr_lines=(),
                evidence_recorded=True,
            )

    def test_result_rejects_memory_written_true(self) -> None:
        admission = _execution_admission()
        with self.assertRaises(ResearchError):
            GuestAgentDnsExecutionResult(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                command_plan=admission.runtime_ready_invocation.prepared_invocation.command_plan,
                process_created=True,
                exit_code=0,
                timed_out=False,
                stdout_lines=(),
                stderr_lines=(),
                memory_written=True,
            )

    def test_result_rejects_exit_code_without_process_created(self) -> None:
        admission = _execution_admission()
        with self.assertRaises(ResearchError):
            GuestAgentDnsExecutionResult(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                command_plan=admission.runtime_ready_invocation.prepared_invocation.command_plan,
                process_created=False,
                exit_code=0,
                timed_out=False,
                stdout_lines=(),
                stderr_lines=(),
            )

    def test_result_rejects_exit_code_with_timeout(self) -> None:
        admission = _execution_admission()
        with self.assertRaises(ResearchError):
            GuestAgentDnsExecutionResult(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                command_plan=admission.runtime_ready_invocation.prepared_invocation.command_plan,
                process_created=True,
                exit_code=0,
                timed_out=True,
                stdout_lines=(),
                stderr_lines=(),
            )

    def test_result_rejects_non_dns_operation_kind(self) -> None:
        admission = _execution_admission()
        with self.assertRaises(ResearchError):
            GuestAgentDnsExecutionResult(
                operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                command_plan=admission.runtime_ready_invocation.prepared_invocation.command_plan,
                process_created=True,
                exit_code=0,
                timed_out=False,
                stdout_lines=(),
                stderr_lines=(),
            )


class CommandPlanDefenseInDepthTests(unittest.TestCase):
    """Direct tests of `_validate_reviewed_dns_command_plan` -- the only
    way to exercise these defense-in-depth checks at all, since the real
    `GuestAgentExecutionAdmission` chain structurally cannot produce a
    mismatched command plan (see this file's own module docstring)."""

    @staticmethod
    def _valid_plan() -> ResearchKaliOperationCommandPlan:
        return ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
            executable_path="/usr/bin/dig",
            argv=("/usr/bin/dig", "+time=5", "+tries=1", "+short", "example.com", "A"),
        )

    def test_valid_plan_passes(self) -> None:
        _validate_reviewed_dns_command_plan(self._valid_plan())

    def test_wrong_transport_fails(self) -> None:
        plan = ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.WSL_KALI,
            executable_path="/usr/bin/dig",
            argv=("/usr/bin/dig", "+time=5", "+tries=1", "+short", "example.com", "A"),
        )
        with self.assertRaises(ResearchError):
            _validate_reviewed_dns_command_plan(plan)

    def test_wrong_executable_fails(self) -> None:
        plan = ResearchKaliOperationCommandPlan(
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
                "example.com:443:1.2.3.4",
                "https://example.com/",
            ),
        )
        with self.assertRaises(ResearchError):
            _validate_reviewed_dns_command_plan(plan)

    def test_wrong_argv_length_too_short_fails(self) -> None:
        plan = ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
            executable_path="/usr/bin/dig",
            argv=("/usr/bin/dig", "+time=5", "+tries=1", "+short", "example.com"),
        )
        with self.assertRaises(ResearchError):
            _validate_reviewed_dns_command_plan(plan)

    def test_wrong_argv_length_too_long_fails(self) -> None:
        plan = ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
            executable_path="/usr/bin/dig",
            argv=(
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "example.com",
                "A",
                "extra",
            ),
        )
        with self.assertRaises(ResearchError):
            _validate_reviewed_dns_command_plan(plan)

    def test_wrong_argv_prefix_fails(self) -> None:
        plan = ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
            executable_path="/usr/bin/dig",
            argv=("/usr/bin/dig", "+time=10", "+tries=1", "+short", "example.com", "A"),
        )
        with self.assertRaises(ResearchError):
            _validate_reviewed_dns_command_plan(plan)

    def test_hostname_too_long_fails(self) -> None:
        plan = ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
            executable_path="/usr/bin/dig",
            argv=(
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "a" * 300,
                "A",
            ),
        )
        with self.assertRaises(ResearchError):
            _validate_reviewed_dns_command_plan(plan)

    def test_whitespace_only_hostname_fails(self) -> None:
        """An empty-string hostname is already structurally impossible --
        `ResearchKaliOperationCommandPlan.__post_init__` itself rejects
        any empty argv element unconditionally. A whitespace-only
        hostname passes that lower-layer check (the string is non-empty)
        but must still fail this executor's own `.strip()` shape check."""
        plan = ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
            executable_path="/usr/bin/dig",
            argv=("/usr/bin/dig", "+time=5", "+tries=1", "+short", "   ", "A"),
        )
        with self.assertRaises(ResearchError):
            _validate_reviewed_dns_command_plan(plan)

    def test_empty_hostname_is_structurally_impossible(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchKaliOperationCommandPlan(
                transport=ResearchKaliCommandTransport.GUEST_AGENT,
                executable_path="/usr/bin/dig",
                argv=("/usr/bin/dig", "+time=5", "+tries=1", "+short", "", "A"),
            )

    def test_unsupported_record_type_fails(self) -> None:
        plan = ResearchKaliOperationCommandPlan(
            transport=ResearchKaliCommandTransport.GUEST_AGENT,
            executable_path="/usr/bin/dig",
            argv=("/usr/bin/dig", "+time=5", "+tries=1", "+short", "example.com", "MX"),
        )
        with self.assertRaises(ResearchError):
            _validate_reviewed_dns_command_plan(plan)

    def test_aaaa_and_cname_are_accepted(self) -> None:
        for record_type in ("AAAA", "CNAME"):
            plan = ResearchKaliOperationCommandPlan(
                transport=ResearchKaliCommandTransport.GUEST_AGENT,
                executable_path="/usr/bin/dig",
                argv=(
                    "/usr/bin/dig",
                    "+time=5",
                    "+tries=1",
                    "+short",
                    "example.com",
                    record_type,
                ),
            )
            _validate_reviewed_dns_command_plan(plan)

    def test_shell_mismatch_is_structurally_impossible(self) -> None:
        """`ResearchKaliOperationCommandPlan.__post_init__` forces
        `shell is False` unconditionally -- there is no way to construct
        a plan with `shell=True` at all, so a shell-mismatch bypass of
        this executor cannot even be attempted."""
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


class StructuralSecurityTests(unittest.TestCase):
    """AST-level proof that this module contains no generic process,
    network, SSH/VMware/WSL, or package-installation channel of any
    kind -- exactly one reviewed subprocess invocation site."""

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

    def test_no_os_system_popen_eval_exec(self) -> None:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr in (
                    "system",
                    "Popen",
                ):
                    self.fail(f"forbidden call found: {node.func.attr}")
                if isinstance(node.func, ast.Name) and node.func.id in (
                    "eval",
                    "exec",
                ):
                    self.fail(f"forbidden call found: {node.func.id}")

    def test_no_forbidden_identifiers(self) -> None:
        forbidden_identifiers = {
            "ssh",
            "vmrun",
            "wsl",
            "bash",
            "cmd",
            "powershell",
            "curl",
            "KaliToolGateway",
            "ProcessAdapter",
            "which",
            "whereis",
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

    def test_no_generic_callback_parameter(self) -> None:
        import inspect

        for name in inspect.signature(execute_guest_agent_dns_record_lookup).parameters:
            self.assertNotIn("callback", name)
            self.assertNotIn("handler", name)

    def test_exactly_one_subprocess_run_call_site(self) -> None:
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

    def test_subprocess_run_consumes_command_plan_argv_attribute(self) -> None:
        """Static proof the one `subprocess.run` call site's first
        argument is `command_plan.argv` -- the already-reviewed plan
        read from the admission chain -- never a name built from
        separately-supplied caller parameters."""
        call_nodes = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ]
        first_arg = call_nodes[0].args[0]
        self.assertIsInstance(first_arg, ast.Attribute)
        assert isinstance(first_arg, ast.Attribute)
        self.assertEqual(first_arg.attr, "argv")
        self.assertIsInstance(first_arg.value, ast.Name)
        assert isinstance(first_arg.value, ast.Name)
        self.assertEqual(first_arg.value.id, "command_plan")

    def test_subprocess_run_is_not_nested_inside_any_loop(self) -> None:
        """Proves no retry: the one `subprocess.run` call site is not
        nested inside an `ast.For`/`ast.While` anywhere in the function
        that contains it (a benign `for line in lines:` output-validation
        loop exists elsewhere in this module, in the result type's own
        `__post_init__` -- that loop never reaches `subprocess.run`)."""
        call_def = None
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "execute_guest_agent_dns_record_lookup"
            ):
                call_def = node
                break
        self.assertIsNotNone(call_def)
        for node in ast.walk(call_def):  # type: ignore[arg-type]
            self.assertNotIsInstance(node, (ast.For, ast.While))


class RpcIntegrationAbsenceTests(unittest.TestCase):
    """Proves the RPC transport is completely untouched by this milestone:
    zero references to the new module or its public names anywhere in
    `GuestAgentSignedDispatchRpcTransport.py`."""

    def test_rpc_transport_never_references_the_dns_executor(self) -> None:
        source = TRANSPORT_MODULE_FILE.read_text(encoding="utf-8")
        forbidden = (
            "GuestAgentDnsExecutionAdapter",
            "execute_guest_agent_dns_record_lookup",
            "GuestAgentDnsExecutionResult",
        )
        for name in forbidden:
            self.assertNotIn(name, source)


if __name__ == "__main__":
    unittest.main()
