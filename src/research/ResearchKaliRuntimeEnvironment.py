"""Reviewed WSL/Kali runtime readiness facts for future operation execution.

This module is a boundary contract only. It does not discover WSL, launch a
process, invoke Kali, perform DNS, or grant execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError
from research.ResearchKaliOperationPreview import ResearchKaliCommandTransport

EXPECTED_KALI_DISTRIBUTION = "kali-linux"
EXPECTED_DIG_EXECUTABLE = "/usr/bin/dig"
EXPECTED_DIG_VERSION_PREFIX = "DiG 9."
EXPECTED_CURL_EXECUTABLE = "/usr/bin/curl"
EXPECTED_CURL_VERSION_PREFIX = "curl "


class ResearchKaliRuntimeReadinessState(StrEnum):
    """Operator-visible Kali runtime readiness states."""

    READY = "ready"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ResearchKaliRuntimeRequirement:
    """Code-owned runtime facts required before real Kali execution can exist."""

    transport: ResearchKaliCommandTransport = ResearchKaliCommandTransport.WSL_KALI
    distribution: str = EXPECTED_KALI_DISTRIBUTION
    executable_path: str = EXPECTED_DIG_EXECUTABLE
    version_prefix: str = EXPECTED_DIG_VERSION_PREFIX
    version_arguments: tuple[str, ...] = ("-v",)

    def __post_init__(self) -> None:
        if not isinstance(self.transport, ResearchKaliCommandTransport):
            raise ResearchError("Kali runtime transport is invalid.")
        for value, label in (
            (self.distribution, "distribution"),
            (self.executable_path, "executable path"),
            (self.version_prefix, "version prefix"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"Kali runtime {label} cannot be empty.")
        if not self.executable_path.startswith("/"):
            raise ResearchError("Kali runtime executable path is invalid.")
        if not isinstance(self.version_arguments, tuple) or not self.version_arguments:
            raise ResearchError("Kali runtime version arguments are invalid.")
        for argument in self.version_arguments:
            if not isinstance(argument, str) or not argument.strip():
                raise ResearchError("Kali runtime version arguments are invalid.")
            if "\x00" in argument or "\r" in argument or "\n" in argument:
                raise ResearchError(
                    "Kali runtime version arguments contain control data."
                )
        if any(
            "\x00" in value or "\r" in value or "\n" in value
            for value in (
                self.distribution,
                self.executable_path,
                self.version_prefix,
            )
        ):
            raise ResearchError("Kali runtime facts contain control data.")


@dataclass(frozen=True, slots=True)
class ResearchKaliRuntimeReadiness:
    """A side-effect-free readiness report for a reviewed Kali runtime."""

    requirement: ResearchKaliRuntimeRequirement
    state: ResearchKaliRuntimeReadinessState
    reason: str
    observed_distribution: str | None = None
    observed_executable_path: str | None = None
    observed_version: str | None = None
    process_created: bool = False
    network_used: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.requirement, ResearchKaliRuntimeRequirement):
            raise ResearchError("Kali runtime requirement is invalid.")
        if not isinstance(self.state, ResearchKaliRuntimeReadinessState):
            raise ResearchError("Kali runtime readiness state is invalid.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError("Kali runtime readiness reason cannot be empty.")
        for value, label in (
            (self.observed_distribution, "observed distribution"),
            (self.observed_executable_path, "observed executable path"),
            (self.observed_version, "observed version"),
        ):
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"Kali runtime {label} cannot be empty.")
            if "\x00" in value:
                raise ResearchError(f"Kali runtime {label} contains control data.")
        if self.process_created is not False or self.network_used is not False:
            raise ResearchError("Kali runtime readiness must not perform real work.")

    @property
    def ready(self) -> bool:
        """Return whether all reviewed runtime prerequisites are reported ready."""
        return self.state is ResearchKaliRuntimeReadinessState.READY


class ResearchKaliRuntimeProbe:
    """Replaceable no-authority probe interface for runtime readiness checks."""

    def readiness(
        self,
        requirement: ResearchKaliRuntimeRequirement,
    ) -> ResearchKaliRuntimeReadiness:
        """Return readiness without granting execution authority."""
        raise NotImplementedError


class UnavailableResearchKaliRuntimeProbe(ResearchKaliRuntimeProbe):
    """Default probe used until an explicit host adapter is installed."""

    def readiness(
        self,
        requirement: ResearchKaliRuntimeRequirement,
    ) -> ResearchKaliRuntimeReadiness:
        """Fail closed without launching WSL, Kali or a child process."""
        return ResearchKaliRuntimeReadiness(
            requirement=requirement,
            state=ResearchKaliRuntimeReadinessState.UNAVAILABLE,
            reason="Kali runtime probe is not configured.",
        )
