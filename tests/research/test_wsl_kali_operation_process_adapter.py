"""WSL/Kali operation process adapter executes only reviewed argv plans."""

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
)
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
    kali_operation_command_plan,
)
from research.WslKaliOperationProcessAdapter import WslKaliOperationProcessAdapter


def command_plan():
    return kali_operation_command_plan(
        operation_kind=ResearchKaliOperationKind.DNS_RECORD_LOOKUP,
        hostname="www.example.test",
        dns_record_type=ResearchDnsRecordType.A,
    )


def https_header_command_plan(*, resolved_address: str = "93.184.216.34"):
    return kali_operation_command_plan(
        operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
        hostname="www.example.test",
        resolved_address=resolved_address,
    )


class WslKaliOperationProcessAdapterTests(unittest.TestCase):
    def test_adapter_runs_reviewed_argv_through_wsl_without_shell(self) -> None:
        completed = subprocess.CompletedProcess(
            args=(),
            returncode=0,
            stdout="192.0.2.10\n",
            stderr="",
        )
        adapter = WslKaliOperationProcessAdapter(
            wsl_executable_path=r"C:\Windows\System32\wsl.exe"
        )
        plan = command_plan()

        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("subprocess.run", return_value=completed) as run,
            patch("subprocess.Popen") as popen,
        ):
            result = adapter.run(plan, timeout_seconds=30.0)

        self.assertEqual(result.command_plan, plan)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout_lines, ("192.0.2.10",))
        self.assertEqual(result.stderr_lines, ())
        self.assertFalse(result.timed_out)
        run.assert_called_once_with(
            (
                r"C:\Windows\System32\wsl.exe",
                "-d",
                "kali-linux",
                "--",
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
        getaddrinfo.assert_not_called()
        popen.assert_not_called()

    def test_adapter_runs_reviewed_curl_argv_without_shell(self) -> None:
        completed = subprocess.CompletedProcess(
            args=(),
            returncode=0,
            stdout="HTTP/2 200\nserver: example\n",
            stderr="",
        )
        adapter = WslKaliOperationProcessAdapter(
            wsl_executable_path=r"C:\Windows\System32\wsl.exe"
        )
        plan = https_header_command_plan()

        with patch("subprocess.run", return_value=completed) as run:
            result = adapter.run(plan, timeout_seconds=10.0)

        self.assertEqual(result.command_plan, plan)
        self.assertEqual(result.stdout_lines, ("HTTP/2 200", "server: example"))
        run.assert_called_once_with(
            (
                r"C:\Windows\System32\wsl.exe",
                "-d",
                "kali-linux",
                "--",
                "/usr/bin/curl",
                "--head",
                "--silent",
                "--show-error",
                "--max-time",
                "10",
                "--proto",
                "=https",
                "--resolve",
                "www.example.test:443:93.184.216.34",
                "https://www.example.test/",
            ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            shell=False,
            timeout=10.0,
            check=False,
        )

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
        adapter = WslKaliOperationProcessAdapter(
            wsl_executable_path=r"C:\Windows\System32\wsl.exe"
        )

        with patch("subprocess.run", return_value=completed):
            result = adapter.run(command_plan(), timeout_seconds=5.0)

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(len(result.stdout_lines), MAX_KALI_OPERATION_OUTPUT_LINES)
        self.assertLessEqual(
            len(result.stderr_lines[0]),
            MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
        )
        self.assertNotIn("\x00", result.stderr_lines[0])

    def test_adapter_returns_bounded_timeout_result(self) -> None:
        adapter = WslKaliOperationProcessAdapter(
            wsl_executable_path=r"C:\Windows\System32\wsl.exe"
        )
        plan = command_plan()

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(
                cmd=(),
                timeout=5.0,
                output=b"partial\n",
                stderr=b"late\n",
            ),
        ):
            result = adapter.run(plan, timeout_seconds=5.0)

        self.assertEqual(result.command_plan, plan)
        self.assertEqual(result.exit_code, -1)
        self.assertEqual(result.stdout_lines, ("partial",))
        self.assertEqual(result.stderr_lines, ("Kali operation timed out.",))
        self.assertTrue(result.timed_out)

    def test_adapter_rejects_unreviewed_launcher_distribution_or_timeout(
        self,
    ) -> None:
        cases = (
            {"wsl_executable_path": "wsl.exe"},
            {"wsl_executable_path": r"C:\Windows\System32\bash.exe"},
            {"distribution": "kali-linux; whoami"},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ResearchError):
                    WslKaliOperationProcessAdapter(**kwargs)

        adapter = WslKaliOperationProcessAdapter(
            wsl_executable_path=r"C:\Windows\System32\wsl.exe"
        )
        with self.assertRaises(ResearchError):
            adapter.run(command_plan(), timeout_seconds=60.0)

    def test_adapter_reports_start_failure_as_research_error(self) -> None:
        adapter = WslKaliOperationProcessAdapter(
            wsl_executable_path=r"C:\Windows\System32\wsl.exe"
        )

        with patch("subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(ResearchError, "Unable to start"):
                adapter.run(command_plan(), timeout_seconds=5.0)


if __name__ == "__main__":
    unittest.main()
