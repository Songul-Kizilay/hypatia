"""First real Guest-Agent HTTPS_HEADER_LOOKUP executor adapter (v0.3.472).

EXECUTION ADMISSION != EXECUTION SUCCESS. HTTPS PROCESS STARTED != HTTPS
SUCCESS. HTTP HEADER OUTPUT != EVIDENCE. Every positive test proves the
executor invokes exactly the one reviewed, hardened curl argv with the exact
admitted timeout, derived only from a real `GuestAgentExecutionAdmission`.
Every negative/adversarial test proves a fail-closed outcome -- DNS before
subprocess, a defense-in-depth command-plan mismatch, a forged admission,
hostname/URL-authority injection, or a caller attempting to supply any
target fact separately.

NOTE on command-plan-mismatch and hostname-injection testing: both
`GuestAgentExecutionAdmission` (v0.3.468) and
`research.ResearchKaliOperationPreview.kali_operation_command_plan`
(v0.3.472) already independently re-prove their own exact binding/hostname
safety, so a legitimately unforgeable `GuestAgentExecutionAdmission` can
never wrap a prepared invocation whose command plan is unsafe -- this
executor's own `_validate_reviewed_https_command_plan` defense-in-depth
checks are therefore structurally unreachable through the only public entry
point today (a deliberate security property, not a test gap). Those checks
are proven directly by calling the private validator itself with
handcrafted command plans, mirroring
`tests.research.test_guest_agent_dns_execution_adapter`'s own
`CommandPlanDefenseInDepthTests` pattern exactly.

No real HTTPS request, no real Kali VM, no Internet contact, and no
dependency on `/usr/bin/curl` actually existing on this runner: every
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
from research.GuestAgentExecutionAdmission import (  # noqa: E402
    GuestAgentExecutionAdmission,
    admit_guest_agent_execution,
)
from research.GuestAgentHttpsHeaderExecutionAdapter import (  # noqa: E402
    GuestAgentHttpsHeaderExecutionResult,
    _validate_reviewed_https_command_plan,
    execute_guest_agent_https_header_lookup,
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

MODULE_FILE = SRC_DIR / "research" / "GuestAgentHttpsHeaderExecutionAdapter.py"
TRANSPORT_MODULE_FILE = SRC_DIR / "research" / "GuestAgentSignedDispatchRpcTransport.py"

_VALID_ARGV: tuple[str, ...] = (
    "/usr/bin/curl",
    "-q",
    "--head",
    "--silent",
    "--show-error",
    "--noproxy",
    "*",
    "--max-time",
    "10",
    "--proto",
    "=https",
    "--resolve",
    "example.com:443:93.184.216.34",
    "https://example.com/",
)


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


def _valid_plan(**overrides: object) -> ResearchKaliOperationCommandPlan:
    base: dict[str, object] = dict(
        transport=ResearchKaliCommandTransport.GUEST_AGENT,
        executable_path="/usr/bin/curl",
        argv=_VALID_ARGV,
    )
    base.update(overrides)
    return ResearchKaliOperationCommandPlan(**base)  # type: ignore[arg-type]


class AuthorityPreconditionTests(unittest.TestCase):
    def test_requires_real_execution_admission_type(self) -> None:
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_https_header_lookup(object())  # type: ignore[arg-type]
        run.assert_not_called()

    def test_rejects_guest_agent_request_directly(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_https_header_lookup(
                    admission.verified_dispatch.request  # type: ignore[arg-type]
                )
        run.assert_not_called()

    def test_rejects_verified_dispatch_alone(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_https_header_lookup(
                    admission.verified_dispatch  # type: ignore[arg-type]
                )
        run.assert_not_called()

    def test_rejects_prepared_invocation_alone(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_https_header_lookup(
                    admission.runtime_ready_invocation.prepared_invocation  # type: ignore[arg-type]
                )
        run.assert_not_called()

    def test_rejects_runtime_ready_invocation_alone(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_https_header_lookup(
                    admission.runtime_ready_invocation  # type: ignore[arg-type]
                )
        run.assert_not_called()

    def test_signature_accepts_only_execution_admission(self) -> None:
        import inspect

        parameters = list(
            inspect.signature(execute_guest_agent_https_header_lookup).parameters
        )
        self.assertEqual(parameters, ["execution_admission"])


class HttpsAdmissionAcceptedTests(unittest.TestCase):
    def test_https_admission_is_accepted_and_executes(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            result = execute_guest_agent_https_header_lookup(admission)
        run.assert_called_once()
        self.assertIsInstance(result, GuestAgentHttpsHeaderExecutionResult)
        self.assertTrue(result.process_created)
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.timed_out)

    def test_exact_argv_matches_fixed_reviewed_plan(self) -> None:
        admission = _execution_admission(
            preview=_https_preview(
                hostname="example.com", resolved_address="93.184.216.34"
            )
        )
        command_plan = (
            admission.runtime_ready_invocation.prepared_invocation.command_plan
        )
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        argv = run.call_args[0][0]
        self.assertEqual(
            argv,
            (
                "/usr/bin/curl",
                "-q",
                "--head",
                "--silent",
                "--show-error",
                "--noproxy",
                "*",
                "--max-time",
                "10",
                "--proto",
                "=https",
                "--resolve",
                "example.com:443:93.184.216.34",
                "https://example.com/",
            ),
        )
        self.assertEqual(argv, command_plan.argv)

    def test_ipv6_resolved_address_argv(self) -> None:
        admission = _execution_admission(
            preview=_https_preview(
                hostname="example.com",
                resolved_address="2606:2800:220:1:248:1893:25c8:1946",
            )
        )
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        argv = run.call_args[0][0]
        self.assertIn("example.com:443:[2606:2800:220:1:248:1893:25c8:1946]", argv)

    def test_dns_admission_rejected_before_subprocess(self) -> None:
        admission = _execution_admission(preview=_preview())
        with mock.patch.object(subprocess, "run") as run:
            with self.assertRaises(ResearchError):
                execute_guest_agent_https_header_lookup(admission)
        run.assert_not_called()


class NoSeparateParameterTests(unittest.TestCase):
    def test_hostname_cannot_be_supplied_separately(self) -> None:
        import inspect

        self.assertNotIn(
            "hostname",
            inspect.signature(execute_guest_agent_https_header_lookup).parameters,
        )

    def test_resolved_address_cannot_be_supplied_separately(self) -> None:
        import inspect

        parameters = inspect.signature(
            execute_guest_agent_https_header_lookup
        ).parameters
        self.assertNotIn("resolved_address", parameters)
        self.assertNotIn("address", parameters)

    def test_url_cannot_be_supplied_separately(self) -> None:
        import inspect

        self.assertNotIn(
            "url", inspect.signature(execute_guest_agent_https_header_lookup).parameters
        )

    def test_port_cannot_be_supplied_separately(self) -> None:
        import inspect

        self.assertNotIn(
            "port",
            inspect.signature(execute_guest_agent_https_header_lookup).parameters,
        )

    def test_executable_cannot_be_supplied_separately(self) -> None:
        import inspect

        parameters = inspect.signature(
            execute_guest_agent_https_header_lookup
        ).parameters
        self.assertNotIn("executable", parameters)
        self.assertNotIn("executable_path", parameters)

    def test_argv_cannot_be_supplied_separately(self) -> None:
        import inspect

        self.assertNotIn(
            "argv",
            inspect.signature(execute_guest_agent_https_header_lookup).parameters,
        )

    def test_timeout_cannot_be_supplied_separately(self) -> None:
        import inspect

        parameters = inspect.signature(
            execute_guest_agent_https_header_lookup
        ).parameters
        self.assertNotIn("timeout", parameters)
        self.assertNotIn("timeout_seconds", parameters)

    def test_headers_proxy_tls_cannot_be_supplied_separately(self) -> None:
        import inspect

        parameters = inspect.signature(
            execute_guest_agent_https_header_lookup
        ).parameters
        for forbidden in ("headers", "proxy", "tls", "insecure", "cacert", "cert"):
            self.assertNotIn(forbidden, parameters)


class TimeoutBindingTests(unittest.TestCase):
    def test_timeout_equals_prepared_invocation_timeout_exactly(self) -> None:
        admission = _execution_admission(preview=_https_preview(max_seconds=7.0))
        expected_timeout = (
            admission.runtime_ready_invocation.prepared_invocation.timeout_seconds
        )
        self.assertEqual(expected_timeout, 7.0)
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertEqual(run.call_args.kwargs["timeout"], 7.0)

    def test_different_admission_different_timeout(self) -> None:
        admission = _execution_admission(preview=_https_preview(max_seconds=3.5))
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertEqual(run.call_args.kwargs["timeout"], 3.5)

    def test_caller_cannot_widen_timeout(self) -> None:
        import inspect

        parameters = inspect.signature(
            execute_guest_agent_https_header_lookup
        ).parameters
        self.assertEqual(len(parameters), 1)

    def test_curl_internal_max_time_is_separate_from_outer_timeout(self) -> None:
        """Curl's own fixed `--max-time 10` in the reviewed argv is
        independent of the outer, signed `subprocess.run` timeout -- a
        shorter outer timeout is never widened to match curl's internal
        bound."""
        admission = _execution_admission(preview=_https_preview(max_seconds=2.0))
        argv = admission.runtime_ready_invocation.prepared_invocation.command_plan.argv
        self.assertIn("10", argv)
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertEqual(run.call_args.kwargs["timeout"], 2.0)


class SubprocessInvocationShapeTests(unittest.TestCase):
    def test_shell_is_false(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_stdin_is_devnull(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_capture_output_is_true(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertTrue(run.call_args.kwargs["capture_output"])

    def test_text_is_true(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertTrue(run.call_args.kwargs["text"])

    def test_encoding_is_utf8(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")

    def test_errors_is_replace(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_check_is_false(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertFalse(run.call_args.kwargs["check"])

    def test_exactly_one_subprocess_run_call(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        run.assert_called_once()


class EnvironmentIsolationTests(unittest.TestCase):
    """Proves the executor never passes this process's own environment,
    or any caller-controlled mapping, to `subprocess.run` -- proxy
    environment variables must not reach the curl process this way."""

    def test_env_kwarg_is_always_passed(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertIn("env", run.call_args.kwargs)
        self.assertIsNotNone(run.call_args.kwargs["env"])

    def test_env_kwarg_is_not_os_environ(self) -> None:
        import os

        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        self.assertIsNot(run.call_args.kwargs["env"], os.environ)

    def test_ambient_proxy_environment_variables_are_not_forwarded(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.dict(
            "os.environ",
            {
                "HTTPS_PROXY": "http://attacker.example:8080",
                "https_proxy": "http://attacker.example:8080",
                "ALL_PROXY": "http://attacker.example:8080",
                "http_proxy": "http://attacker.example:8080",
            },
        ):
            with mock.patch.object(
                subprocess,
                "run",
                return_value=_completed(stdout="HTTP/1.1 200 OK\n"),
            ) as run:
                execute_guest_agent_https_header_lookup(admission)
        env = run.call_args.kwargs["env"]
        for forbidden in (
            "HTTPS_PROXY",
            "https_proxy",
            "ALL_PROXY",
            "http_proxy",
            "NO_PROXY",
            "no_proxy",
        ):
            self.assertNotIn(forbidden, env)

    def test_env_kwarg_is_fixed_and_minimal(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        env = run.call_args.kwargs["env"]
        self.assertEqual(env, {"PATH": "/usr/bin:/bin"})


class ReviewedArgvSafetyPropertiesTests(unittest.TestCase):
    """Proves the reviewed argv, as actually produced for execution,
    carries the hardening this milestone's curl audit requires."""

    def _argv(self) -> tuple[str, ...]:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ) as run:
            execute_guest_agent_https_header_lookup(admission)
        return tuple(run.call_args[0][0])

    def test_disable_default_config_is_first_option(self) -> None:
        argv = self._argv()
        self.assertEqual(argv[0], "/usr/bin/curl")
        self.assertEqual(argv[1], "-q")

    def test_noproxy_wildcard_present(self) -> None:
        argv = self._argv()
        index = argv.index("--noproxy")
        self.assertEqual(argv[index + 1], "*")

    def test_proto_restricts_to_https_only(self) -> None:
        argv = self._argv()
        index = argv.index("--proto")
        self.assertEqual(argv[index + 1], "=https")

    def test_no_redirect_following_option(self) -> None:
        argv = self._argv()
        for forbidden in ("-L", "--location", "--location-trusted"):
            self.assertNotIn(forbidden, argv)

    def test_no_insecure_tls_option(self) -> None:
        argv = self._argv()
        for forbidden in ("-k", "--insecure", "--proxy-insecure"):
            self.assertNotIn(forbidden, argv)

    def test_no_arbitrary_headers_or_auth_option(self) -> None:
        argv = self._argv()
        for forbidden in ("-H", "--header", "-u", "--user", "--cacert", "--cert"):
            self.assertNotIn(forbidden, argv)

    def test_fixed_port_443(self) -> None:
        argv = self._argv()
        resolve_value = argv[argv.index("--resolve") + 1]
        self.assertEqual(resolve_value.split(":")[1], "443")

    def test_url_is_exactly_https_scheme(self) -> None:
        argv = self._argv()
        self.assertTrue(argv[-1].startswith("https://"))
        self.assertFalse(argv[-1].startswith("http://"))


class ResultOutcomeTests(unittest.TestCase):
    def test_timeout_produces_bounded_typed_result(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="curl", timeout=10.0),
        ):
            result = execute_guest_agent_https_header_lookup(admission)
        self.assertTrue(result.process_created)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)
        self.assertEqual(result.stdout_lines, ())
        self.assertEqual(result.stderr_lines, ())

    def test_nonzero_exit_is_not_reported_as_success(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(returncode=22, stderr="error")
        ):
            result = execute_guest_agent_https_header_lookup(admission)
        self.assertEqual(result.exit_code, 22)
        self.assertFalse(result.timed_out)
        self.assertFalse(hasattr(result, "success"))

    def test_oserror_fails_closed_without_leaking_exception_text(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess,
            "run",
            side_effect=FileNotFoundError("/some/secret/path/leaked"),
        ):
            with self.assertRaises(ResearchError) as context:
                execute_guest_agent_https_header_lookup(admission)
        message = str(context.exception)
        self.assertNotIn("/some/secret/path/leaked", message)
        self.assertIn("FileNotFoundError", message)

    def test_exit_code_zero_is_never_fabricated_on_oserror(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", side_effect=PermissionError("denied")
        ):
            with self.assertRaises(ResearchError):
                execute_guest_agent_https_header_lookup(admission)


class OutputBoundingTests(unittest.TestCase):
    def test_stdout_bounded_to_line_ceiling(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        huge_stdout = "\n".join(f"header-{i}: value" for i in range(200))
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout=huge_stdout)
        ):
            result = execute_guest_agent_https_header_lookup(admission)
        self.assertLessEqual(len(result.stdout_lines), MAX_KALI_OPERATION_OUTPUT_LINES)

    def test_stdout_bounded_to_character_ceiling(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="x" * 2000)
        ):
            result = execute_guest_agent_https_header_lookup(admission)
        for line in result.stdout_lines:
            self.assertLessEqual(len(line), MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS)

    def test_stderr_bounded(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        huge_stderr = "\n".join(f"err{i}" for i in range(200))
        with mock.patch.object(
            subprocess,
            "run",
            return_value=_completed(returncode=1, stderr=huge_stderr),
        ):
            result = execute_guest_agent_https_header_lookup(admission)
        self.assertLessEqual(len(result.stderr_lines), MAX_KALI_OPERATION_OUTPUT_LINES)

    def test_control_characters_sanitized(self) -> None:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess,
            "run",
            return_value=_completed(stdout="HTTP/1.1 200 OK\x07\x1b[31m"),
        ):
            result = execute_guest_agent_https_header_lookup(admission)
        combined = "".join(result.stdout_lines)
        self.assertNotIn("\x07", combined)
        self.assertNotIn("\x1b", combined)


class UntrustedOutputSemanticsTests(unittest.TestCase):
    def _real_result(self) -> GuestAgentHttpsHeaderExecutionResult:
        admission = _execution_admission(preview=_https_preview())
        with mock.patch.object(
            subprocess, "run", return_value=_completed(stdout="HTTP/1.1 200 OK\n")
        ):
            return execute_guest_agent_https_header_lookup(admission)

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
        with self.assertRaises(ResearchError):
            GuestAgentHttpsHeaderExecutionResult(
                operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                command_plan=_valid_plan(),
                process_created=True,
                exit_code=0,
                timed_out=False,
                stdout_lines=(),
                stderr_lines=(),
                evidence_recorded=True,
            )

    def test_result_rejects_memory_written_true(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentHttpsHeaderExecutionResult(
                operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                command_plan=_valid_plan(),
                process_created=True,
                exit_code=0,
                timed_out=False,
                stdout_lines=(),
                stderr_lines=(),
                memory_written=True,
            )

    def test_result_rejects_exit_code_without_process_created(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentHttpsHeaderExecutionResult(
                operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                command_plan=_valid_plan(),
                process_created=False,
                exit_code=0,
                timed_out=False,
                stdout_lines=(),
                stderr_lines=(),
            )

    def test_result_rejects_exit_code_with_timeout(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentHttpsHeaderExecutionResult(
                operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
                command_plan=_valid_plan(),
                process_created=True,
                exit_code=0,
                timed_out=True,
                stdout_lines=(),
                stderr_lines=(),
            )

    def test_result_rejects_non_https_operation_kind(self) -> None:
        with self.assertRaises(ResearchError):
            GuestAgentHttpsHeaderExecutionResult(
                operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
                command_plan=_valid_plan(),
                process_created=True,
                exit_code=0,
                timed_out=False,
                stdout_lines=(),
                stderr_lines=(),
            )


class CommandPlanDefenseInDepthTests(unittest.TestCase):
    """Direct tests of `_validate_reviewed_https_command_plan` -- the only
    way to exercise these defense-in-depth checks at all, since the real
    `GuestAgentExecutionAdmission` chain structurally cannot produce an
    unsafe command plan (see this file's own module docstring)."""

    def test_valid_plan_passes(self) -> None:
        _validate_reviewed_https_command_plan(_valid_plan())

    def test_valid_ipv6_plan_passes(self) -> None:
        argv = (
            "/usr/bin/curl",
            "-q",
            "--head",
            "--silent",
            "--show-error",
            "--noproxy",
            "*",
            "--max-time",
            "10",
            "--proto",
            "=https",
            "--resolve",
            "example.com:443:[2606:2800:220:1:248:1893:25c8:1946]",
            "https://example.com/",
        )
        _validate_reviewed_https_command_plan(_valid_plan(argv=argv))

    def test_wrong_transport_fails(self) -> None:
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(
                _valid_plan(transport=ResearchKaliCommandTransport.WSL_KALI)
            )

    def test_wrong_executable_fails(self) -> None:
        argv = (
            "/usr/bin/dig",
            "+time=5",
            "+tries=1",
            "+short",
            "example.com",
            "A",
        )
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(
                _valid_plan(executable_path="/usr/bin/dig", argv=argv)
            )

    def test_wrong_argv_length_too_short_fails(self) -> None:
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=_VALID_ARGV[:-1]))

    def test_wrong_argv_length_too_long_fails(self) -> None:
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(
                _valid_plan(argv=_VALID_ARGV + ("extra",))
            )

    def test_wrong_argv_prefix_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[1] = "--silent"  # removes -q from argv[1]
        tampered[2] = "-q"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_missing_disable_config_flag_fails(self) -> None:
        argv = (
            "/usr/bin/curl",
            "--head",
            "--silent",
            "--show-error",
            "--noproxy",
            "*",
            "--max-time",
            "10",
            "--proto",
            "=https",
            "--resolve",
            "example.com:443:93.184.216.34",
            "https://example.com/",
        )
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=argv))

    def test_missing_noproxy_flag_fails(self) -> None:
        argv = (
            "/usr/bin/curl",
            "-q",
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
        )
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=argv))

    def test_redirect_flag_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[2] = "-L"  # replaces --head, keeps length identical
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_insecure_tls_flag_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[2] = "-k"  # replaces --head, keeps length identical
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_resolve_flag_missing_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[11] = "--not-resolve"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_resolve_wrong_port_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[12] = "example.com:8080:93.184.216.34"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_resolve_malformed_address_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[12] = "example.com:443:not-an-ip"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_resolve_malformed_ipv6_brackets_fail(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[12] = "example.com:443:2606:2800:220:1:248:1893:25c8:1946"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_colon_port_injection_in_resolve_hostname_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[12] = "example.com:9999:443:93.184.216.34"
        tampered[13] = "https://example.com/"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_path_injection_hostname_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[12] = "example.com/evil:443:93.184.216.34"
        tampered[13] = "https://example.com/evil/"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_userinfo_injection_in_url_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[13] = "https://attacker.example@example.com/"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_query_fragment_injection_in_url_fails(self) -> None:
        for suffix in ("?x=1", "#frag"):
            with self.subTest(suffix=suffix):
                tampered = list(_VALID_ARGV)
                tampered[13] = f"https://example.com/{suffix}"
                with self.assertRaises(ResearchError):
                    _validate_reviewed_https_command_plan(
                        _valid_plan(argv=tuple(tampered))
                    )

    def test_second_port_in_url_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[13] = "https://example.com:8443/"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_url_hostname_mismatch_with_resolve_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[13] = "https://attacker.example/"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_http_scheme_url_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[13] = "http://example.com/"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_unsafe_hostname_delimiter_fails(self) -> None:
        for bad_hostname in (
            "example.com/evil",
            "example.com\\evil",
            "example.com#evil",
            "example.com?evil",
            "example.com[1]",
            "exa mple.com",
        ):
            with self.subTest(bad_hostname=bad_hostname):
                tampered = list(_VALID_ARGV)
                tampered[12] = f"{bad_hostname}:443:93.184.216.34"
                tampered[13] = f"https://{bad_hostname}/"
                with self.assertRaises(ResearchError):
                    _validate_reviewed_https_command_plan(
                        _valid_plan(argv=tuple(tampered))
                    )

    def test_single_label_hostname_fails(self) -> None:
        tampered = list(_VALID_ARGV)
        tampered[12] = "localhost:443:93.184.216.34"
        tampered[13] = "https://localhost/"
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(_valid_plan(argv=tuple(tampered)))

    def test_shell_mismatch_is_structurally_impossible(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchKaliOperationCommandPlan(
                transport=ResearchKaliCommandTransport.GUEST_AGENT,
                executable_path="/usr/bin/curl",
                argv=_VALID_ARGV,
                shell=True,
            )

    def test_stdin_mismatch_fails(self) -> None:
        plan = _valid_plan()
        tampered = ResearchKaliOperationCommandPlan.__new__(
            ResearchKaliOperationCommandPlan
        )
        object.__setattr__(tampered, "transport", plan.transport)
        object.__setattr__(tampered, "executable_path", plan.executable_path)
        object.__setattr__(tampered, "argv", plan.argv)
        object.__setattr__(tampered, "shell", False)
        object.__setattr__(tampered, "stdin", "open")
        with self.assertRaises(ResearchError):
            _validate_reviewed_https_command_plan(tampered)


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

    def test_urllib_import_is_parse_only(self) -> None:
        """`urllib.parse.urlsplit` is used for URL-authority validation
        only -- never `urllib.request`/`urllib.error` (no HTTP client)."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom) and node.module == "urllib.parse":
                self.assertEqual([alias.name for alias in node.names], ["urlsplit"])
            if isinstance(node, ast.Import):
                self.assertFalse(
                    any(alias.name.startswith("urllib.request") for alias in node.names)
                )

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
            "dig",
            "KaliToolGateway",
            "ProcessAdapter",
            "which",
            "whereis",
            "requests",
            "httpx",
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

        for name in inspect.signature(
            execute_guest_agent_https_header_lookup
        ).parameters:
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

    def test_subprocess_run_passes_a_fixed_env_keyword(self) -> None:
        """Static proof the one `subprocess.run` call site always passes
        an `env=` keyword naming the module's own fixed constant, never
        `os.environ` or a parameter."""
        call_nodes = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ]
        env_keywords = [kw for kw in call_nodes[0].keywords if kw.arg == "env"]
        self.assertEqual(len(env_keywords), 1)
        value = env_keywords[0].value
        self.assertIsInstance(value, ast.Name)
        assert isinstance(value, ast.Name)
        self.assertEqual(value.id, "_SANITIZED_SUBPROCESS_ENVIRONMENT")

    def test_subprocess_run_is_not_nested_inside_any_loop(self) -> None:
        call_def = None
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "execute_guest_agent_https_header_lookup"
            ):
                call_def = node
                break
        self.assertIsNotNone(call_def)
        for node in ast.walk(call_def):  # type: ignore[arg-type]
            self.assertNotIsInstance(node, (ast.For, ast.While))


class RpcIntegrationTests(unittest.TestCase):
    """v0.3.472 note: this milestone deliberately did not wire this
    executor into `GuestAgentSignedDispatchRpcServer`.

    v0.3.473 note: a separately authorized later milestone (v0.3.473)
    deliberately wired this exact executor into
    `GuestAgentSignedDispatchRpcServer`, strictly behind the full
    existing authority chain, as an explicit sibling branch of the
    existing DNS dispatch -- see
    `research.GuestAgentSignedDispatchRpcTransport`'s own module
    docstring and
    `tests.research.test_guest_agent_signed_dispatch_rpc_transport
    .HttpsRpcExecutionTests`/`HttpsRpcStructuralSecurityTests`/
    `HttpsRpcNoHiddenCallerTests` for the full wiring proof. This
    executor implementation remains unmodified by v0.3.473. This test
    module updates the historical no-RPC assertion to permit only the
    reviewed signed-RPC caller; the transport tests prove that wiring."""

    def test_executor_still_has_zero_bootstrap_chat_desktop_callers(self) -> None:
        """The one authorized RPC caller aside, this executor must still
        never be referenced by Bootstrap, CognitiveEngine, chat, or the
        desktop."""
        forbidden = (
            "execute_guest_agent_https_header_lookup",
            "GuestAgentHttpsHeaderExecutionAdapter",
        )
        offending_files = []
        for path in SRC_DIR.rglob("*.py"):
            if path.name in (
                "GuestAgentHttpsHeaderExecutionAdapter.py",
                "GuestAgentSignedDispatchRpcTransport.py",
            ):
                continue
            text = path.read_text(encoding="utf-8")
            if any(name in text for name in forbidden):
                offending_files.append(str(path))
        self.assertEqual(offending_files, [])

    def test_transport_module_now_imports_this_executor(self) -> None:
        """Positive proof of the v0.3.473 wiring: the transport module
        imports and calls this exact function -- never a copy, never a
        re-derivation of the curl argv."""
        text = TRANSPORT_MODULE_FILE.read_text(encoding="utf-8")
        self.assertIn("GuestAgentHttpsHeaderExecutionAdapter", text)
        self.assertIn("execute_guest_agent_https_header_lookup", text)


if __name__ == "__main__":
    unittest.main()
