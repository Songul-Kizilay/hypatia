"""WSL/Kali process adapter for one reviewed operation command plan.

This adapter executes only the code-owned argv plan produced by the Kali
operation preview layer. It does not accept command strings, shell syntax or
operator-supplied executable paths.
"""

from __future__ import annotations

import subprocess
from pathlib import PureWindowsPath

from core.Exceptions import ResearchError
from research.ResearchKaliOperationExecution import (
    MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
    MAX_KALI_OPERATION_OUTPUT_LINES,
    ResearchKaliOperationProcessAdapter,
    ResearchKaliOperationProcessResult,
)
from research.ResearchKaliOperationPreview import (
    ResearchKaliCommandTransport,
    ResearchKaliOperationCommandPlan,
)

MAX_KALI_OPERATION_TIMEOUT_SECONDS = 30.0


class WslKaliOperationProcessAdapter(ResearchKaliOperationProcessAdapter):
    """Run one reviewed WSL/Kali command plan with bounded output."""

    def __init__(
        self,
        *,
        wsl_executable_path: str = r"C:\Windows\System32\wsl.exe",
        distribution: str = "kali-linux",
    ) -> None:
        self._wsl_executable_path = self._windows_executable_path(wsl_executable_path)
        self._distribution = self._distribution_name(distribution)

    def run(
        self,
        command_plan: ResearchKaliOperationCommandPlan,
        *,
        timeout_seconds: float,
    ) -> ResearchKaliOperationProcessResult:
        """Run exactly the supplied reviewed command plan inside WSL/Kali."""
        self._validate_command_plan(command_plan)
        timeout = self._timeout(timeout_seconds)
        argv = (
            self._wsl_executable_path,
            "-d",
            self._distribution,
            "--",
            *command_plan.argv,
        )
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                shell=False,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            return ResearchKaliOperationProcessResult(
                command_plan=command_plan,
                exit_code=-1,
                stdout_lines=self._bounded_lines(error.stdout),
                stderr_lines=("Kali operation timed out.",),
                timed_out=True,
            )
        except OSError as error:
            raise ResearchError(
                f"Unable to start WSL/Kali operation: {type(error).__name__}."
            ) from error

        return ResearchKaliOperationProcessResult(
            command_plan=command_plan,
            exit_code=completed.returncode,
            stdout_lines=self._bounded_lines(completed.stdout),
            stderr_lines=self._bounded_lines(completed.stderr),
        )

    @staticmethod
    def _validate_command_plan(command_plan: ResearchKaliOperationCommandPlan) -> None:
        if not isinstance(command_plan, ResearchKaliOperationCommandPlan):
            raise ResearchError("Kali operation command plan is invalid.")
        if command_plan.transport is not ResearchKaliCommandTransport.WSL_KALI:
            raise ResearchError("Kali operation transport is not supported.")
        if command_plan.shell is not False:
            raise ResearchError("Kali operation command plan must not use a shell.")
        if command_plan.stdin != "closed":
            raise ResearchError("Kali operation command plan stdin must be closed.")
        if command_plan.argv[0] != command_plan.executable_path:
            raise ResearchError("Kali operation argv does not match executable.")

    @staticmethod
    def _windows_executable_path(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Kali operation WSL executable path cannot be empty.")
        stripped = value.strip()
        if "\x00" in stripped or "\r" in stripped or "\n" in stripped:
            raise ResearchError(
                "Kali operation WSL executable path contains control data."
            )
        path = PureWindowsPath(stripped)
        if not path.is_absolute() or path.name.casefold() != "wsl.exe":
            raise ResearchError("Kali operation WSL executable path is invalid.")
        return stripped

    @staticmethod
    def _distribution_name(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Kali operation WSL distribution cannot be empty.")
        stripped = value.strip()
        if any(character.isspace() for character in stripped):
            raise ResearchError("Kali operation WSL distribution is invalid.")
        if "\x00" in stripped or "\r" in stripped or "\n" in stripped:
            raise ResearchError(
                "Kali operation WSL distribution contains control data."
            )
        return stripped

    @staticmethod
    def _timeout(value: float) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not 0 < value <= MAX_KALI_OPERATION_TIMEOUT_SECONDS
        ):
            raise ResearchError("Kali operation timeout is invalid.")
        return float(value)

    @staticmethod
    def _bounded_lines(value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, bytes):
            text = value.decode("utf-8", errors="replace")
        elif isinstance(value, str):
            text = value
        else:
            text = str(value)
        cleaned = "".join(
            (
                character
                if character == "\n" or (character >= " " and character != "\x7f")
                else "\ufffd"
            )
            for character in text
        )
        lines = tuple(
            line[:MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS]
            for line in cleaned.splitlines()
            if line
        )
        return lines[:MAX_KALI_OPERATION_OUTPUT_LINES]
