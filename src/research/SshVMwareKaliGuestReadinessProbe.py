"""Restricted-SSH VMware guest readiness probe for the one allowed command.

This adapter never authenticates with a password: it pins the SSH host key
(`StrictHostKeyChecking=yes` against a dedicated, code-owned known_hosts
file), disables every interactive/password/keyboard-interactive auth method,
disables agent and port forwarding, and never allocates a pseudo-terminal.
The remote command is always exactly `/usr/bin/dig -v` -- a module-level
constant, never a parameter, so no caller can substitute a different
executable or arguments. It performs no DNS lookup, no HTTP(S) request and
no other target-network operation of any kind.

Why SSH rather than `vmrun runProgramInGuest`: this host's real `vmrun`
authentication flags (`-gu`/`-gp`) require the guest password as a
command-line argument, which would place a plaintext credential in process
argv (visible to any other process on the host that can list command
lines). That is not an acceptable production credential transport under
this project's boundary, so this adapter never uses it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from core.Exceptions import ResearchError
from research.ResearchVMwareKaliGuestReadiness import (
    EXPECTED_GUEST_DIG_EXECUTABLE,
    EXPECTED_GUEST_DIG_VERSION_PREFIX,
    ResearchVMwareKaliGuestReadiness,
    ResearchVMwareKaliGuestReadinessProbe,
    ResearchVMwareKaliGuestReadinessState,
    ResearchVMwareKaliGuestTransportRequirement,
)
from research.ResearchVMwareKaliHostReadiness import ResearchVMwareKaliHostReadiness

MAX_GUEST_PROBE_OUTPUT_CHARACTERS = 500

#: The one allowed remote command. A fixed tuple, never built from a
#: parameter, request metadata or model output -- there is no code path
#: that could substitute a different executable or arguments.
_REMOTE_COMMAND = (EXPECTED_GUEST_DIG_EXECUTABLE, "-v")


class SshVMwareKaliGuestReadinessProbe(ResearchVMwareKaliGuestReadinessProbe):
    """Reach the Kali guest only via pinned, key-based, restricted SSH."""

    def readiness(
        self,
        host_readiness: ResearchVMwareKaliHostReadiness,
        transport: ResearchVMwareKaliGuestTransportRequirement,
    ) -> ResearchVMwareKaliGuestReadiness:
        """Run the one allowed version probe, or fail closed before trying."""
        if not isinstance(host_readiness, ResearchVMwareKaliHostReadiness):
            raise ResearchError("VMware host readiness is invalid.")
        if not isinstance(transport, ResearchVMwareKaliGuestTransportRequirement):
            raise ResearchError("VMware guest transport requirement is invalid.")

        if not host_readiness.host_ready:
            return self._result(
                transport,
                ResearchVMwareKaliGuestReadinessState.HOST_NOT_READY,
                "VMware host is not ready; no guest attempt was made.",
            )

        key_path = Path(transport.private_key_path)
        known_hosts_path = Path(transport.known_hosts_path)
        ssh_path = Path(transport.ssh_executable_path)
        if (
            not ssh_path.is_file()
            or not key_path.is_file()
            or not known_hosts_path.is_file()
        ):
            return self._result(
                transport,
                ResearchVMwareKaliGuestReadinessState.GUEST_TRANSPORT_UNCONFIGURED,
                "SSH executable, private key or pinned known_hosts file was "
                "not found on this host.",
            )

        argv = (
            str(ssh_path),
            "-i",
            str(key_path),
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
            f"UserKnownHostsFile={known_hosts_path}",
            "-o",
            "ForwardAgent=no",
            "-o",
            "ForwardX11=no",
            "-o",
            f"ConnectTimeout={int(transport.connect_timeout_seconds)}",
            "-p",
            str(transport.guest_port),
            f"{transport.guest_user}@{transport.guest_host}",
            *_REMOTE_COMMAND,
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
                timeout=transport.command_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._result(
                transport,
                ResearchVMwareKaliGuestReadinessState.GUEST_UNREACHABLE,
                "SSH connection or command timed out.",
            )
        except (OSError, subprocess.SubprocessError) as error:
            return self._result(
                transport,
                ResearchVMwareKaliGuestReadinessState.GUEST_INSPECTION_FAILED,
                f"Unable to start ssh: {type(error).__name__}.",
            )

        stdout = self._bounded(completed.stdout)
        # Classification only ever inspects this combined text transiently,
        # in this one local variable; neither it nor raw stderr is ever
        # stored in the returned result, logged, or otherwise retained --
        # the one exception is `stdout`, used only as `observed_version`
        # when the dig version line itself matched, which cannot carry a
        # credential (no credential transits stdout under key-based,
        # password-disabled auth in the first place). Both sides are
        # bounded before this concatenation: an unbounded guest response
        # must not cost an unbounded local `casefold()`/concatenation.
        classification_text = (
            stdout + "\n" + self._bounded(completed.stderr)
        ).casefold()

        if completed.returncode == 0:
            if EXPECTED_GUEST_DIG_VERSION_PREFIX in stdout:
                return self._result(
                    transport,
                    ResearchVMwareKaliGuestReadinessState.GUEST_READY,
                    "Guest SSH identity, authentication and the reviewed "
                    "dig version probe were all verified.",
                    observed_version=stdout,
                )
            return self._result(
                transport,
                ResearchVMwareKaliGuestReadinessState.TOOL_VERSION_MISMATCH,
                "Guest dig version did not match the expected prefix.",
                observed_version=stdout or None,
            )

        if "host key verification failed" in classification_text:
            return self._result(
                transport,
                ResearchVMwareKaliGuestReadinessState.GUEST_IDENTITY_UNVERIFIED,
                "SSH host key did not match the pinned known_hosts entry.",
            )
        # Checked by exit code, and before the generic "permission denied"
        # text match below: POSIX shells report both "not found" (127) and
        # "found but not executable" (126) this way, and the latter's own
        # message is commonly "Permission denied" -- a guest tool-permission
        # problem, not an SSH authentication rejection. Classifying by the
        # shell's own exit-code convention first removes that ambiguity
        # instead of guessing from substrings.
        if completed.returncode in (126, 127) or (
            "no such file or directory" in classification_text
            and EXPECTED_GUEST_DIG_EXECUTABLE in classification_text
        ):
            return self._result(
                transport,
                ResearchVMwareKaliGuestReadinessState.TOOL_MISSING,
                "Reviewed dig executable was not found or not executable "
                "on the guest.",
            )
        if "permission denied" in classification_text:
            return self._result(
                transport,
                ResearchVMwareKaliGuestReadinessState.AUTHENTICATION_UNAVAILABLE,
                "SSH public-key authentication was not accepted.",
            )
        if any(
            phrase in classification_text
            for phrase in (
                "connection refused",
                "connection timed out",
                "no route to host",
                "could not resolve hostname",
                "network is unreachable",
            )
        ):
            return self._result(
                transport,
                ResearchVMwareKaliGuestReadinessState.GUEST_UNREACHABLE,
                "Guest endpoint could not be reached.",
            )
        return self._result(
            transport,
            ResearchVMwareKaliGuestReadinessState.GUEST_INSPECTION_FAILED,
            "SSH returned an unexpected, unclassified failure.",
        )

    @staticmethod
    def _result(
        transport: ResearchVMwareKaliGuestTransportRequirement,
        state: ResearchVMwareKaliGuestReadinessState,
        reason: str,
        *,
        observed_version: str | None = None,
    ) -> ResearchVMwareKaliGuestReadiness:
        return ResearchVMwareKaliGuestReadiness(
            transport=transport,
            state=state,
            reason=reason,
            observed_version=observed_version,
        )

    @staticmethod
    def _bounded(value: str) -> str:
        cleaned = "".join(
            (
                character
                if character == "\n" or (character >= " " and character != "\x7f")
                else "�"
            )
            for character in value
        ).strip()
        return cleaned[:MAX_GUEST_PROBE_OUTPUT_CHARACTERS]
