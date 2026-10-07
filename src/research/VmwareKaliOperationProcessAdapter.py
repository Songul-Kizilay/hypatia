"""VMware/Kali process adapter for exactly one reviewed DNS lookup command.

This adapter never authenticates with a password: it pins the SSH host key
(`StrictHostKeyChecking=yes` against a dedicated, code-owned known_hosts
file), disables every interactive/password/keyboard-interactive auth method,
disables agent and port forwarding, allocates no pseudo-terminal and closes
stdin -- mirroring `SshVMwareKaliGuestReadinessProbe`'s restricted argv
exactly, for the same reason documented there: this host's `vmrun`
`-gu`/`-gp` authentication flags would place a plaintext guest password in
process argv, which is not an acceptable production credential transport
under this project's boundary.

Unlike the guest-readiness probe, which only ever runs one fixed, parameter-
less command (`/usr/bin/dig -v`), this adapter runs the one reviewed
DNS_RECORD_LOOKUP command plan `research.ResearchKaliOperationPreview`
builds, so it must itself re-validate that plan's exact shape before it ever
reaches a real SSH remote command: the hostname and record-type arguments
inside that plan are reviewed, scope-bound values (see
`ResearchTargetScope.require_hostname`, which already enforces a strict
label grammar -- ASCII, lowercase, `[a-z0-9-]` labels only -- before any
preview naming that hostname can exist), but OpenSSH joins remote command
arguments into one line the guest's login shell parses unquoted. The
structural check below is therefore defense in depth at the exact point that
unquoted remote-shell semantics becomes real, not a replacement for the
scope-level grammar check, which remains the authoritative boundary: nothing
here loosens or re-implements what that check already proves safe.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from core.Exceptions import ResearchError
from research.ResearchKaliOperationExecution import (
    MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
    MAX_KALI_OPERATION_OUTPUT_LINES,
    MAX_KALI_OPERATION_TIMEOUT_SECONDS,
    ResearchKaliOperationProcessAdapter,
    ResearchKaliOperationProcessResult,
)
from research.ResearchKaliOperationPreview import (
    ResearchKaliCommandTransport,
    ResearchKaliOperationCommandPlan,
)
from research.ResearchVMwareKaliGuestReadiness import (
    ResearchVMwareKaliGuestTransportRequirement,
)

#: The one reviewed executable this adapter will ever invoke remotely.
_EXPECTED_EXECUTABLE = "/usr/bin/dig"
#: The reviewed DNS_RECORD_LOOKUP argv's fixed leading options, in this
#: exact order -- never reordered, extended or substituted.
_EXPECTED_ARGV_PREFIX = ("/usr/bin/dig", "+time=5", "+tries=1", "+short")
#: The only DNS record types the reviewed lookup profile allows.
_ALLOWED_RECORD_TYPES = ("A", "AAAA", "CNAME")
#: Mirrors `research.ResearchTargetScope`'s own private `_LABEL` grammar
#: exactly (ASCII, lowercase-or-digit start/end, interior hyphens only). A
#: defense-in-depth re-check at the point a hostname is about to join an
#: unquoted remote command line, never a relaxation of that authoritative
#: scope-level grammar.
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_MAX_HOSTNAME_CHARACTERS = 253


class VmwareKaliOperationProcessAdapter(ResearchKaliOperationProcessAdapter):
    """Run exactly the reviewed VMware/Kali DNS_RECORD_LOOKUP command plan.

    This adapter is not a generic SSH terminal or remote process runner: it
    accepts only a `ResearchKaliOperationCommandPlan` whose transport is
    `VMWARE_KALI`, whose executable is `/usr/bin/dig`, and whose argv is
    exactly the reviewed four fixed options followed by one validated
    hostname and one allowed record type -- anything else is refused before
    any subprocess is started.
    """

    def __init__(
        self,
        *,
        guest_transport: ResearchVMwareKaliGuestTransportRequirement,
    ) -> None:
        if not isinstance(guest_transport, ResearchVMwareKaliGuestTransportRequirement):
            raise ResearchError("VMware Kali operation guest transport is invalid.")
        self._guest_transport = guest_transport

    def run(
        self,
        command_plan: ResearchKaliOperationCommandPlan,
        *,
        timeout_seconds: float,
    ) -> ResearchKaliOperationProcessResult:
        """Run exactly the supplied reviewed command plan over restricted SSH."""
        self._validate_command_plan(command_plan)
        timeout = self._timeout(timeout_seconds)
        transport = self._guest_transport
        argv = (
            str(Path(transport.ssh_executable_path)),
            "-i",
            str(Path(transport.private_key_path)),
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
            f"UserKnownHostsFile={Path(transport.known_hosts_path)}",
            "-o",
            "ForwardAgent=no",
            "-o",
            "ForwardX11=no",
            "-o",
            f"ConnectTimeout={int(transport.connect_timeout_seconds)}",
            "-p",
            str(transport.guest_port),
            f"{transport.guest_user}@{transport.guest_host}",
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
                f"Unable to start VMware/Kali SSH operation: {type(error).__name__}."
            ) from error

        return ResearchKaliOperationProcessResult(
            command_plan=command_plan,
            exit_code=completed.returncode,
            stdout_lines=self._bounded_lines(completed.stdout),
            stderr_lines=self._bounded_lines(completed.stderr),
        )

    @staticmethod
    def _validate_command_plan(
        command_plan: ResearchKaliOperationCommandPlan,
    ) -> None:
        if not isinstance(command_plan, ResearchKaliOperationCommandPlan):
            raise ResearchError("Kali operation command plan is invalid.")
        if command_plan.transport is not ResearchKaliCommandTransport.VMWARE_KALI:
            raise ResearchError("Kali operation transport is not supported.")
        if command_plan.shell is not False:
            raise ResearchError("Kali operation command plan must not use a shell.")
        if command_plan.stdin != "closed":
            raise ResearchError("Kali operation command plan stdin must be closed.")
        if command_plan.executable_path != _EXPECTED_EXECUTABLE:
            raise ResearchError("Kali operation executable is not supported.")
        argv = command_plan.argv
        if len(argv) != len(_EXPECTED_ARGV_PREFIX) + 2:
            raise ResearchError("Kali operation argv shape is not supported.")
        if tuple(argv[: len(_EXPECTED_ARGV_PREFIX)]) != _EXPECTED_ARGV_PREFIX:
            raise ResearchError("Kali operation argv is not the reviewed dig lookup.")
        hostname, record_type = argv[-2], argv[-1]
        if record_type not in _ALLOWED_RECORD_TYPES:
            raise ResearchError("Kali operation DNS record type is not supported.")
        if not VmwareKaliOperationProcessAdapter._is_safe_hostname(hostname):
            raise ResearchError("Kali operation hostname is not supported.")

    @staticmethod
    def _is_safe_hostname(value: object) -> bool:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > (_MAX_HOSTNAME_CHARACTERS)
        ):
            return False
        labels = value.split(".")
        return (
            len(labels) >= 2
            and not labels[-1].isdigit()
            and all(_LABEL.fullmatch(label) is not None for label in labels)
        )

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
                else "�"
            )
            for character in text
        )
        lines = tuple(
            line[:MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS]
            for line in cleaned.splitlines()
            if line
        )
        return lines[:MAX_KALI_OPERATION_OUTPUT_LINES]
