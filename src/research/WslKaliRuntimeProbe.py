"""WSL/Kali runtime readiness probe for reviewed operation prerequisites.

This adapter checks only local runtime availability. It must not run a target
operation, perform DNS, spend a research budget or grant execution authority.
"""

from __future__ import annotations

import subprocess
from pathlib import PureWindowsPath

from core.Exceptions import ResearchError
from research.ResearchKaliRuntimeEnvironment import (
    ResearchKaliRuntimeProbe,
    ResearchKaliRuntimeReadiness,
    ResearchKaliRuntimeReadinessState,
    ResearchKaliRuntimeRequirement,
)

MAX_KALI_READINESS_OUTPUT_CHARACTERS = 500
KALI_READINESS_TIMEOUT_SECONDS = 5.0


class WslKaliRuntimeProbe(ResearchKaliRuntimeProbe):
    """Probe a configured WSL/Kali executable using a fixed argv tuple."""

    def __init__(
        self,
        *,
        wsl_executable_path: str = r"C:\Windows\System32\wsl.exe",
        timeout_seconds: float = KALI_READINESS_TIMEOUT_SECONDS,
    ) -> None:
        self._wsl_executable_path = self._windows_executable_path(wsl_executable_path)
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int | float)
            or not 0 < timeout_seconds <= KALI_READINESS_TIMEOUT_SECONDS
        ):
            raise ResearchError("Kali runtime probe timeout is invalid.")
        self._timeout_seconds = float(timeout_seconds)

    def readiness(
        self,
        requirement: ResearchKaliRuntimeRequirement,
    ) -> ResearchKaliRuntimeReadiness:
        """Check the configured WSL/Kali executable version with no target work."""
        argv = (
            self._wsl_executable_path,
            "-d",
            requirement.distribution,
            "--",
            requirement.executable_path,
            *requirement.version_arguments,
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
                timeout=self._timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return ResearchKaliRuntimeReadiness(
                requirement=requirement,
                state=ResearchKaliRuntimeReadinessState.UNAVAILABLE,
                reason=f"Unable to probe WSL/Kali runtime: {type(error).__name__}.",
            )

        output = self._bounded_output(completed.stdout, completed.stderr)
        if completed.returncode != 0:
            return ResearchKaliRuntimeReadiness(
                requirement=requirement,
                state=ResearchKaliRuntimeReadinessState.UNAVAILABLE,
                reason="WSL/Kali runtime probe returned a non-zero exit code.",
                observed_distribution=requirement.distribution,
                observed_executable_path=requirement.executable_path,
                observed_version=output or None,
            )
        if requirement.version_prefix not in output:
            return ResearchKaliRuntimeReadiness(
                requirement=requirement,
                state=ResearchKaliRuntimeReadinessState.UNAVAILABLE,
                reason="WSL/Kali executable version did not match requirements.",
                observed_distribution=requirement.distribution,
                observed_executable_path=requirement.executable_path,
                observed_version=output or None,
            )
        return ResearchKaliRuntimeReadiness(
            requirement=requirement,
            state=ResearchKaliRuntimeReadinessState.READY,
            reason="Reviewed WSL/Kali runtime prerequisites are available.",
            observed_distribution=requirement.distribution,
            observed_executable_path=requirement.executable_path,
            observed_version=output,
        )

    @staticmethod
    def _windows_executable_path(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Kali runtime WSL executable path cannot be empty.")
        stripped = value.strip()
        if "\x00" in stripped or "\r" in stripped or "\n" in stripped:
            raise ResearchError(
                "Kali runtime WSL executable path contains control data."
            )
        path = PureWindowsPath(stripped)
        if not path.is_absolute() or path.name.casefold() != "wsl.exe":
            raise ResearchError("Kali runtime WSL executable path is invalid.")
        return stripped

    @staticmethod
    def _bounded_output(stdout: str, stderr: str) -> str:
        combined = "\n".join(value for value in (stdout, stderr) if value)
        cleaned = "".join(
            (
                character
                if character == "\n" or (character >= " " and character != "\x7f")
                else "\ufffd"
            )
            for character in combined
        ).strip()
        return cleaned[:MAX_KALI_READINESS_OUTPUT_CHARACTERS]
