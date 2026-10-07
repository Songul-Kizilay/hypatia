"""VMware/Kali operation process adapter runs only the reviewed dig lookup.

Locks in: the restricted-SSH argv shape (pinned host key, key-only auth, no
shell, no pseudo-terminal, no forwarding, closed stdin, bounded timeout);
that only a VMWARE_KALI, dig-only, exact-argv DNS_RECORD_LOOKUP plan is ever
dispatched; that every adversarial hostname/record-type/executable/argv
substitution is refused before any subprocess starts; that failures never
retry; and that no credential ever appears in argv, output or error text.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.ResearchKaliOperationExecution import (
    MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
    MAX_KALI_OPERATION_OUTPUT_LINES,
    MAX_KALI_OPERATION_TIMEOUT_SECONDS,
)
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliCommandTransport,
    ResearchKaliOperationCommandPlan,
    ResearchKaliOperationKind,
    kali_operation_command_plan,
)
from research.ResearchVMwareKaliGuestReadiness import (
    ResearchVMwareKaliGuestTransportRequirement,
)
from research.VmwareKaliOperationProcessAdapter import (
    VmwareKaliOperationProcessAdapter,
)

GUEST_USER = "hypatia-probe"
GUEST_HOST = "192.168.206.128"


def _guest_transport() -> ResearchVMwareKaliGuestTransportRequirement:
    return ResearchVMwareKaliGuestTransportRequirement(
        ssh_executable_path=r"C:\Windows\System32\OpenSSH\ssh.exe",
        private_key_path=r"C:\Users\hypatia\.ssh\hypatia_guest_ed25519",
        known_hosts_path=r"C:\Users\hypatia\.ssh\hypatia_known_hosts",
        guest_user=GUEST_USER,
        guest_host=GUEST_HOST,
    )


def _plan(
    *,
    hostname: str = "www.example.test",
    dns_record_type: ResearchDnsRecordType = ResearchDnsRecordType.A,
) -> ResearchKaliOperationCommandPlan:
    return kali_operation_command_plan(
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        hostname=hostname,
        dns_record_type=dns_record_type,
        transport=ResearchKaliCommandTransport.VMWARE_KALI,
    )


def _wsl_plan() -> ResearchKaliOperationCommandPlan:
    return kali_operation_command_plan(
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        hostname="www.example.test",
        dns_record_type=ResearchDnsRecordType.A,
    )


def _https_plan() -> ResearchKaliOperationCommandPlan:
    return kali_operation_command_plan(
        operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
        hostname="www.example.test",
        resolved_address="93.184.216.34",
        transport=ResearchKaliCommandTransport.VMWARE_KALI,
    )


def _forged_plan(
    argv: tuple[str, ...], *, executable_path: str = "/usr/bin/dig"
) -> object:
    """Build a plan-shaped object bypassing `kali_operation_command_plan`.

    `ResearchKaliOperationCommandPlan` itself only rejects empty/control-
    character argv entries and an argv[0]/executable_path mismatch, not
    argument shape or content -- so an adversarial plan with a tampered
    argv must be constructed directly to exercise the adapter's own
    structural re-validation, exactly as a future caller mistake (never a
    model or chat path, since nothing wires one to this type) would look.
    """
    return ResearchKaliOperationCommandPlan(
        transport=ResearchKaliCommandTransport.VMWARE_KALI,
        executable_path=executable_path,
        argv=argv,
    )


class VmwareKaliOperationProcessAdapterTests(unittest.TestCase):
    def test_adapter_runs_reviewed_argv_through_restricted_ssh(self) -> None:
        completed = subprocess.CompletedProcess(
            args=(), returncode=0, stdout="192.0.2.10\n", stderr=""
        )
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())
        plan = _plan()

        with patch("subprocess.run", return_value=completed) as run:
            result = adapter.run(plan, timeout_seconds=30.0)

        self.assertEqual(result.command_plan, plan)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout_lines, ("192.0.2.10",))
        self.assertFalse(result.timed_out)
        run.assert_called_once_with(
            (
                r"C:\Windows\System32\OpenSSH\ssh.exe",
                "-i",
                r"C:\Users\hypatia\.ssh\hypatia_guest_ed25519",
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "BatchMode=yes",
                "-o",
                "PasswordAuthentication=no",
                "-o",
                "KbdInteractiveAuthentication=no",
                "-o",
                "ChallengeResponseAuthentication=no",
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                r"UserKnownHostsFile=C:\Users\hypatia\.ssh\hypatia_known_hosts",
                "-o",
                "ForwardAgent=no",
                "-o",
                "ForwardX11=no",
                "-o",
                "ConnectTimeout=5",
                "-p",
                "22",
                f"{GUEST_USER}@{GUEST_HOST}",
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "www.example.test",
                "A",
            ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            shell=False,
            timeout=30.0,
            check=False,
        )
        # No pseudo-terminal (-t/-tt) and no port forwarding (-L/-R/-D) flag
        # is ever present in the dispatched argv.
        dispatched_argv = run.call_args.args[0]
        for forbidden in ("-t", "-tt", "-L", "-R", "-D"):
            self.assertNotIn(forbidden, dispatched_argv)

    def test_adapter_rejects_wsl_kali_plans(self) -> None:
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())
        with patch("subprocess.run") as run:
            with self.assertRaises(ResearchError):
                adapter.run(_wsl_plan(), timeout_seconds=30.0)
        run.assert_not_called()

    def test_adapter_rejects_https_header_lookup_and_curl(self) -> None:
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())
        with patch("subprocess.run") as run:
            with self.assertRaises(ResearchError):
                adapter.run(_https_plan(), timeout_seconds=30.0)
        run.assert_not_called()

    def test_adapter_rejects_an_arbitrary_executable(self) -> None:
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())
        plan = _forged_plan(
            (
                "/bin/sh",
                "+time=5",
                "+tries=1",
                "+short",
                "www.example.test",
                "A",
            ),
            executable_path="/bin/sh",
        )
        with patch("subprocess.run") as run:
            with self.assertRaises(ResearchError):
                adapter.run(plan, timeout_seconds=30.0)  # type: ignore[arg-type]
        run.assert_not_called()

    def test_adapter_rejects_argv_injection_and_mutation(self) -> None:
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())
        cases = (
            # Extra argument appended.
            (
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "www.example.test",
                "A",
                "extra",
            ),
            # Reordered fixed arguments.
            (
                "/usr/bin/dig",
                "+short",
                "+time=5",
                "+tries=1",
                "www.example.test",
                "A",
            ),
            # Custom resolver injected.
            (
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "@8.8.8.8",
                "A",
            ),
            # +trace mode substituted for a fixed option.
            (
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+trace",
                "www.example.test",
                "A",
            ),
            # ANY/AXFR/IXFR record types.
            (
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "www.example.test",
                "ANY",
            ),
            (
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "www.example.test",
                "AXFR",
            ),
            (
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "www.example.test",
                "IXFR",
            ),
            # -x reverse-lookup flag substituted for the hostname.
            (
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "-x",
                "A",
            ),
            # Missing an argument.
            ("/usr/bin/dig", "+time=5", "+tries=1", "+short", "www.example.test"),
            # All-numeric final label (IP-literal-shaped "hostname").
            (
                "/usr/bin/dig",
                "+time=5",
                "+tries=1",
                "+short",
                "203.0.113.5",
                "A",
            ),
        )
        for argv in cases:
            with self.subTest(argv=argv):
                with patch("subprocess.run") as run:
                    with self.assertRaises(ResearchError):
                        adapter.run(
                            _forged_plan(argv),  # type: ignore[arg-type]
                            timeout_seconds=30.0,
                        )
                run.assert_not_called()

    def test_adapter_rejects_hostile_hostnames_without_dispatch(self) -> None:
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())
        hostile_hostnames = (
            "@8.8.8.8",
            "+trace",
            "-x",
            "foo;id",
            "foo&&id",
            "foo|id",
            "$(id)",
            "`id`",
            "foo bar",
            "foo\nbar",
            "-leading-option",
        )
        for hostname in hostile_hostnames:
            with self.subTest(hostname=hostname):
                # A hostile hostname may already be refused when the plan
                # itself is built (e.g. control characters, which
                # `ResearchKaliOperationCommandPlan` itself rejects) or only
                # once the adapter re-validates it; either point proves the
                # same property -- it can never reach a dispatched
                # subprocess -- so both are accepted inside one assertion.
                with patch("subprocess.run") as run:
                    with self.assertRaises(ResearchError):
                        plan = _forged_plan(
                            (
                                "/usr/bin/dig",
                                "+time=5",
                                "+tries=1",
                                "+short",
                                hostname,
                                "A",
                            )
                        )
                        adapter.run(plan, timeout_seconds=30.0)  # type: ignore[arg-type]
                    run.assert_not_called()

    def test_valid_ordinary_hostname_is_preserved(self) -> None:
        completed = subprocess.CompletedProcess(
            args=(), returncode=0, stdout="192.0.2.10\n", stderr=""
        )
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())
        plan = _plan(hostname="sub.example.test")

        with patch("subprocess.run", return_value=completed) as run:
            result = adapter.run(plan, timeout_seconds=30.0)

        self.assertEqual(result.exit_code, 0)
        dispatched_argv = run.call_args.args[0]
        self.assertIn("sub.example.test", dispatched_argv)

    def test_adapter_bounds_stdout_and_stderr_lines(self) -> None:
        long_line = "x" * (MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS + 20)
        output_lines = "\n".join(
            f"line-{index}" for index in range(MAX_KALI_OPERATION_OUTPUT_LINES + 5)
        )
        completed = subprocess.CompletedProcess(
            args=(),
            returncode=1,
            stdout=f"{output_lines}\n",
            stderr=f"{long_line}\x00\n",
        )
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())

        with patch("subprocess.run", return_value=completed):
            result = adapter.run(_plan(), timeout_seconds=5.0)

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(len(result.stdout_lines), MAX_KALI_OPERATION_OUTPUT_LINES)
        self.assertLessEqual(
            len(result.stderr_lines[0]), MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS
        )
        self.assertNotIn("\x00", result.stderr_lines[0])

    def test_adapter_returns_bounded_timeout_result_without_retry(self) -> None:
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())
        plan = _plan()

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(
                cmd=(), timeout=5.0, output=b"partial\n", stderr=b"late\n"
            ),
        ) as run:
            result = adapter.run(plan, timeout_seconds=5.0)

        self.assertEqual(result.exit_code, -1)
        self.assertEqual(result.stdout_lines, ("partial",))
        self.assertTrue(result.timed_out)
        self.assertEqual(run.call_count, 1)

    def test_adapter_rejects_timeout_above_the_global_cap(self) -> None:
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())
        with self.assertRaises(ResearchError):
            adapter.run(
                _plan(), timeout_seconds=MAX_KALI_OPERATION_TIMEOUT_SECONDS + 1.0
            )

    def test_adapter_reports_start_failure_as_research_error_without_retry(
        self,
    ) -> None:
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())
        with patch("subprocess.run", side_effect=FileNotFoundError) as run:
            with self.assertRaisesRegex(ResearchError, "Unable to start"):
                adapter.run(_plan(), timeout_seconds=5.0)
        self.assertEqual(run.call_count, 1)

    def test_no_credential_appears_in_dispatched_argv_or_bounded_output(self) -> None:
        completed = subprocess.CompletedProcess(
            args=(),
            returncode=255,
            stdout="",
            stderr=(f"{GUEST_USER}@{GUEST_HOST}: Permission denied " "(publickey)."),
        )
        adapter = VmwareKaliOperationProcessAdapter(guest_transport=_guest_transport())

        with patch("subprocess.run", return_value=completed) as run:
            result = adapter.run(_plan(), timeout_seconds=5.0)

        dispatched_argv = run.call_args.args[0]
        # Only the fixed, code-owned "disable password auth" option string
        # may mention "password"; no literal credential value ever does.
        self.assertIn("PasswordAuthentication=no", dispatched_argv)
        self.assertNotIn("-gu", dispatched_argv)
        self.assertNotIn("-gp", dispatched_argv)
        for argument in dispatched_argv:
            self.assertNotIn("PasswordAuthentication=yes", argument)
        for line in (*result.stdout_lines, *result.stderr_lines):
            self.assertNotIn("password", line.lower())

    def test_constructor_rejects_an_invalid_guest_transport(self) -> None:
        with self.assertRaises(ResearchError):
            VmwareKaliOperationProcessAdapter(guest_transport="not-a-requirement")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
