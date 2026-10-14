"""Local Guest-Agent runtime-readiness probe for the two reviewed capabilities.

This adapter checks only local executable availability for an already-
prepared, unforgeable `GuestAgentPreparedInvocation`. It never runs the
invocation's own reviewed target argv, performs DNS, makes an HTTPS request,
spends a research budget, or grants execution authority. LOCAL READINESS
PROCESS != TARGET OPERATION.

The only two production subprocess argv this module may ever invoke are the
exact fixed tuples `("/usr/bin/dig", "-v")` and `("/usr/bin/curl",
"--version")` -- a private, literal mapping keyed only by
`ResearchKaliOperationKind.DNS_RECORD_LOOKUP`/`HTTPS_HEADER_LOOKUP`, never
built by iterating that enum (a future third member fails closed by `dict
.get` returning `None`), and never derived from
`prepared_invocation.command_plan.argv`. Before ever invoking
`subprocess.run`, `check()` cross-checks that the prepared invocation's own
`command_plan.transport` is `ResearchKaliCommandTransport.GUEST_AGENT` and
that its `executable_path` matches the one this mapping expects for the
invocation's `operation_kind` -- a mismatch fails closed with zero
subprocess attempt, as defense in depth against a hypothetical future bug
upstream of this probe (every real `GuestAgentPreparedInvocation` already
satisfies both checks by construction; see
`research.GuestAgentInvocationPreparation._build_prepared_invocation`).
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from core.Exceptions import ResearchError
from research.GuestAgentInvocationPreparation import GuestAgentPreparedInvocation
from research.GuestAgentLocalReadiness import (
    MAX_GUEST_AGENT_READINESS_OUTPUT_CHARACTERS,
    GuestAgentLocalReadinessProbe,
    GuestAgentLocalReadinessReceipt,
    GuestAgentLocalReadinessState,
)
from research.ResearchKaliOperationPreview import (
    ResearchKaliCommandTransport,
    ResearchKaliOperationKind,
)
from research.ResearchKaliRuntimeEnvironment import (
    EXPECTED_CURL_EXECUTABLE,
    EXPECTED_CURL_VERSION_PREFIX,
    EXPECTED_DIG_EXECUTABLE,
    EXPECTED_DIG_VERSION_PREFIX,
)

#: Mirrors `research.WslKaliRuntimeProbe.KALI_READINESS_TIMEOUT_SECONDS`'s
#: existing 5-second ceiling -- the same bound this repository already
#: treats as the hard local-readiness-probe limit -- declared independently
#: here rather than imported, so this Guest-Agent module never depends on a
#: concrete WSL-specific adapter module. This is the LOCAL VERSION PROBE
#: timeout only; it is never the signed operation `max_seconds` carried by
#: `GuestAgentPreparedInvocation.timeout_seconds`, and the two must never be
#: conflated.
GUEST_AGENT_READINESS_TIMEOUT_SECONDS: Final[float] = 5.0


@dataclass(frozen=True, slots=True)
class _GuestAgentReadinessToolSpec:
    """Code-owned, fixed local version-probe facts for one operation kind."""

    executable_path: str
    version_argv: tuple[str, str]
    version_prefix: str


#: The one fixed literal allowlist. Not built by iterating
#: `ResearchKaliOperationKind` -- a future enum member simply has no entry
#: here, so `_READINESS_TOOL_SPECS.get(...)` returns `None` and `check()`
#: fails closed before any subprocess attempt. See
#: `tests/research/test_guest_agent_local_runtime_probe.py`'s structural
#: (AST) proof that this mapping is a literal dict, not enum-derived.
_READINESS_TOOL_SPECS: Final[
    Mapping[ResearchKaliOperationKind, _GuestAgentReadinessToolSpec]
] = {
    ResearchKaliOperationKind.DNS_RECORD_LOOKUP: _GuestAgentReadinessToolSpec(
        executable_path=EXPECTED_DIG_EXECUTABLE,
        version_argv=(EXPECTED_DIG_EXECUTABLE, "-v"),
        version_prefix=EXPECTED_DIG_VERSION_PREFIX,
    ),
    ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP: _GuestAgentReadinessToolSpec(
        executable_path=EXPECTED_CURL_EXECUTABLE,
        version_argv=(EXPECTED_CURL_EXECUTABLE, "--version"),
        version_prefix=EXPECTED_CURL_VERSION_PREFIX,
    ),
}

_REASON_UNSUPPORTED_OPERATION = (
    "This operation kind has no reviewed local readiness probe."
)
_REASON_WRONG_TRANSPORT = (
    "Prepared invocation transport does not match the Guest-Agent route."
)
_REASON_EXECUTABLE_MISMATCH = (
    "Prepared invocation executable path does not match the reviewed tool."
)
_REASON_PROCESS_START_FAILED = "Unable to start the local version-probe process."
_REASON_TIMED_OUT = "The local version-probe process timed out."
_REASON_NONZERO_EXIT = "The local version-probe process returned a non-zero exit code."
_REASON_VERSION_MISMATCH = "The local tool version did not match the expected identity."
_REASON_READY = (
    "The exact reviewed local executable and version identity are available."
)


class GuestAgentLocalRuntimeProbe(GuestAgentLocalReadinessProbe):
    """Probe the one fixed local version-probe tuple for a prepared invocation."""

    def __init__(
        self,
        *,
        timeout_seconds: float = GUEST_AGENT_READINESS_TIMEOUT_SECONDS,
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int | float)
            or not 0 < timeout_seconds <= GUEST_AGENT_READINESS_TIMEOUT_SECONDS
        ):
            raise ResearchError("Guest-agent local readiness probe timeout is invalid.")
        self._timeout_seconds = float(timeout_seconds)

    def check(
        self, prepared_invocation: GuestAgentPreparedInvocation
    ) -> GuestAgentLocalReadinessReceipt:
        """Cross-check, then run only the one fixed local version probe."""
        if not isinstance(prepared_invocation, GuestAgentPreparedInvocation):
            raise ResearchError(
                "Guest-agent local readiness probe requires a prepared invocation."
            )
        operation_kind = prepared_invocation.operation_kind
        spec = _READINESS_TOOL_SPECS.get(operation_kind)
        if spec is None:
            return self._unavailable(operation_kind, _REASON_UNSUPPORTED_OPERATION)

        command_plan = prepared_invocation.command_plan
        if command_plan.transport is not ResearchKaliCommandTransport.GUEST_AGENT:
            return self._unavailable(operation_kind, _REASON_WRONG_TRANSPORT)
        if command_plan.executable_path != spec.executable_path:
            return self._unavailable(operation_kind, _REASON_EXECUTABLE_MISMATCH)

        try:
            completed = subprocess.run(
                spec.version_argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                shell=False,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._unavailable(
                operation_kind,
                _REASON_TIMED_OUT,
                executable_path=spec.executable_path,
                probe_process_started=True,
            )
        # PEP 758 (Python 3.14, this project's pinned minimum): an
        # unparenthesized exception list here is not Python-2-era syntax --
        # it is equivalent to `except (OSError, subprocess.SubprocessError):`.
        except OSError, subprocess.SubprocessError:
            return self._unavailable(
                operation_kind,
                _REASON_PROCESS_START_FAILED,
                executable_path=spec.executable_path,
                probe_process_started=True,
            )

        output = self._bounded_output(completed.stdout, completed.stderr)
        if completed.returncode != 0:
            return self._unavailable(
                operation_kind,
                _REASON_NONZERO_EXIT,
                executable_path=spec.executable_path,
                observed_version=output or None,
                probe_process_started=True,
            )
        if spec.version_prefix not in output:
            return self._unavailable(
                operation_kind,
                _REASON_VERSION_MISMATCH,
                executable_path=spec.executable_path,
                observed_version=output or None,
                probe_process_started=True,
            )
        return GuestAgentLocalReadinessReceipt(
            operation_kind=operation_kind,
            state=GuestAgentLocalReadinessState.READY,
            reason=_REASON_READY,
            executable_path=spec.executable_path,
            observed_version=output,
            probe_process_started=True,
        )

    @staticmethod
    def _unavailable(
        operation_kind: ResearchKaliOperationKind,
        reason: str,
        *,
        executable_path: str | None = None,
        observed_version: str | None = None,
        probe_process_started: bool = False,
    ) -> GuestAgentLocalReadinessReceipt:
        return GuestAgentLocalReadinessReceipt(
            operation_kind=operation_kind,
            state=GuestAgentLocalReadinessState.UNAVAILABLE,
            reason=reason,
            executable_path=executable_path,
            observed_version=observed_version,
            probe_process_started=probe_process_started,
        )

    @staticmethod
    def _bounded_output(stdout: str, stderr: str) -> str:
        combined = "\n".join(value for value in (stdout, stderr) if value)
        cleaned = "".join(
            (
                character
                if character == "\n" or (character >= " " and character != "\x7f")
                else "�"
            )
            for character in combined
        ).strip()
        return cleaned[:MAX_GUEST_AGENT_READINESS_OUTPUT_CHARACTERS]
