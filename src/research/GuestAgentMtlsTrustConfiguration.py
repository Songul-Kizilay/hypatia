"""Who the two Guest-Agent mTLS peers are, and what trusted material proves it.

AUTHENTICATED PEER != EXECUTION AUTHORITY. TRUSTED CERTIFICATE != EXECUTION
AUTHORITY. Everything in this module is trusted, code-owned configuration or
a code-owned identity constant -- never anything a chat message, model
output, request metadata, a `GuestAgentRequest`'s `logical_inputs`, a
`GuestAgentResponse`, or Kali process output could redefine. This module
starts no process, opens no socket, and performs no TLS handshake; it only
describes who is allowed to be on each end of a future channel and which
trusted files a future transport would present or verify against.

The channel has exactly two roles, deliberately closed:

    HOST  -- Windows Hypatia, the side that will eventually dispatch a
             reviewed capability to the guest.
    GUEST -- the future Hypatia Kali Guest Agent, the side that will
             eventually execute one allowlisted capability.

Peer identity is certificate-bound, never IP-address-bound: a VMware
Host-Only IP can change at any time and must never itself stand in for who
the other side is. The identity string each role's certificate is expected
to carry is a fixed, code-owned URI Subject Alternative Name following this
repository's own existing `"hypatia:<concept>:v<n>"` / `"hypatia-<concept>/<n>"`
naming convention (see `research.GuestAgentProtocol.GuestAgentProtocolVersion.V1
== "hypatia-kali-guest-agent/1"`), not an invented new scheme: it is not a
DNS name (these are not resolvable hosts and treating them as one would
invite exactly the hostname-based confusion this design avoids), and it is
exact-match only -- there is no wildcard, prefix, or substring form anywhere
in this module.

"Certificate chains to a trusted CA" is not, by itself, enough to know which
*application* is on the other end: this module models that distinction on
purpose. `GuestAgentMtlsTrustConfiguration` carries both facts side by side
-- which CA this installation trusts, and which exact peer identity a
chain-valid certificate must *also* carry -- so a certificate that is valid
under the trusted CA but names the wrong role (or no recognized role at all)
is still not the correct peer. A future transport that validates chain
trust and stops there would not be enforcing this distinction; nothing in
this module lets it skip the second check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PureWindowsPath

from core.Exceptions import ResearchError

MAX_PEER_IDENTITY_URI_LENGTH = 200
MAX_TRUST_PATH_LENGTH = 400

#: Exact, code-owned URI SAN identities -- one per role, versioned like this
#: repository's other schema strings. Never configurable, never derived from
#: request or chat content: a role's expected identity is a fact about this
#: project's own naming convention, not a deployment setting.
_HOST_PEER_IDENTITY_URI = "hypatia-kali-guest-agent/host/1"
_GUEST_PEER_IDENTITY_URI = "hypatia-kali-guest-agent/guest/1"

#: `scheme:opaque-or-path` only, matching the project's own existing
#: `"hypatia-kali-guest-agent/1"`-shaped strings exactly -- no wildcard
#: (`*`), no path traversal segment, no whitespace, no scheme other than
#: this project's own `hypatia-kali-guest-agent` identity space.
_PEER_IDENTITY_URI_PATTERN = re.compile(
    r"^hypatia-kali-guest-agent/(host|guest)/[1-9][0-9]*$"
)


class GuestAgentPeerRole(StrEnum):
    """Name one of exactly two Guest-Agent mTLS channel endpoints.

    Nothing outside this module (and the future transport/guest-agent
    milestones that consume it) may construct or select a value here from
    untrusted input: a `GuestAgentRequest` has no `peer_role` field, and
    never will -- peer identity comes only from an authenticated TLS layer,
    never from protocol data the peer itself supplies.
    """

    HOST = "host"
    GUEST = "guest"

    @property
    def other(self) -> GuestAgentPeerRole:
        """Return the one role this channel's other end must be."""
        return (
            GuestAgentPeerRole.GUEST
            if self is GuestAgentPeerRole.HOST
            else (GuestAgentPeerRole.HOST)
        )


@dataclass(frozen=True, slots=True)
class GuestAgentPeerIdentity:
    """Bind one role to the exact URI SAN its certificate must carry.

    `uri` is validated against this project's own fixed naming convention
    and must agree with `role` -- there is no way to construct a
    `GuestAgentPeerIdentity` naming the host role while carrying the
    guest's URI, or vice versa, so a caller cannot accidentally (or
    adversarially) mint a mismatched pair.
    """

    role: GuestAgentPeerRole
    uri: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, GuestAgentPeerRole):
            raise ResearchError("Guest-agent peer identity role is invalid.")
        if not isinstance(self.uri, str) or not self.uri.strip():
            raise ResearchError("Guest-agent peer identity URI cannot be empty.")
        if "\x00" in self.uri or "\r" in self.uri or "\n" in self.uri:
            raise ResearchError("Guest-agent peer identity URI contains control data.")
        if len(self.uri) > MAX_PEER_IDENTITY_URI_LENGTH:
            raise ResearchError("Guest-agent peer identity URI is too long.")
        match = _PEER_IDENTITY_URI_PATTERN.fullmatch(self.uri)
        if match is None:
            raise ResearchError("Guest-agent peer identity URI is not recognized.")
        if match.group(1) != self.role.value:
            raise ResearchError(
                "Guest-agent peer identity URI does not name its own role."
            )

    @classmethod
    def for_role(cls, role: GuestAgentPeerRole) -> GuestAgentPeerIdentity:
        """Return the one fixed, code-owned identity for `role`."""
        if not isinstance(role, GuestAgentPeerRole):
            raise ResearchError("Guest-agent peer identity role is invalid.")
        uri = (
            _HOST_PEER_IDENTITY_URI
            if role is GuestAgentPeerRole.HOST
            else _GUEST_PEER_IDENTITY_URI
        )
        return cls(role=role, uri=uri)


@dataclass(frozen=True, slots=True)
class GuestAgentMtlsTrustConfiguration:
    """Trusted, code-owned paths and identity expectations for one role.

    This type never holds key *material* -- only paths a future transport
    would pass to `ssl.SSLContext.load_cert_chain`/`load_verify_locations`.
    Nothing here reads a file or touches the filesystem; path strings are
    validated as strings only (non-empty, absolute, free of control data),
    exactly as `ResearchVMwareKaliGuestTransportRequirement` in
    `research.ResearchVMwareKaliGuestReadiness` already validates its own
    trusted SSH paths without checking existence at construction time.

    `own_role` names which side of the channel this configuration is for.
    `expected_peer_identity` is never a separate, independently-settable
    field: it is always derived from `own_role.other`, so a configuration
    cannot be constructed claiming to be the host while expecting another
    host, or any other self-contradictory pairing.

    `expected_peer_fingerprint_sha256` is optional, additional defense, not
    a required trust mechanism: a dedicated, project-owned CA together with
    exact role-bound SAN matching already identifies the correct peer
    application; pinning one more fact on top is a caller's choice, not a
    requirement this type imposes. Left `None` by default.
    """

    own_role: GuestAgentPeerRole
    trusted_ca_certificate_path: str
    own_certificate_path: str
    own_private_key_path: str
    expected_peer_fingerprint_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.own_role, GuestAgentPeerRole):
            raise ResearchError("Guest-agent mTLS trust configuration role is invalid.")
        for value, label in (
            (self.trusted_ca_certificate_path, "trusted CA certificate path"),
            (self.own_certificate_path, "own certificate path"),
            (self.own_private_key_path, "own private key path"),
        ):
            self._require_trusted_path(value, label)
        if self.expected_peer_fingerprint_sha256 is not None:
            self._require_fingerprint(self.expected_peer_fingerprint_sha256)

    @property
    def expected_peer_role(self) -> GuestAgentPeerRole:
        """Return the one role the other end of this channel must be."""
        return self.own_role.other

    @property
    def expected_peer_identity(self) -> GuestAgentPeerIdentity:
        """Return the fixed identity the authenticated peer must present."""
        return GuestAgentPeerIdentity.for_role(self.expected_peer_role)

    @staticmethod
    def _require_trusted_path(value: object, label: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"Guest-agent mTLS {label} cannot be empty.")
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ResearchError(f"Guest-agent mTLS {label} contains control data.")
        if len(value) > MAX_TRUST_PATH_LENGTH:
            raise ResearchError(f"Guest-agent mTLS {label} is too long.")
        if not GuestAgentMtlsTrustConfiguration._is_absolute_on_any_platform(value):
            raise ResearchError(f"Guest-agent mTLS {label} must be an absolute path.")

    @staticmethod
    def _is_absolute_on_any_platform(value: str) -> bool:
        """Return whether `value` is absolute under POSIX or Windows rules.

        Mirrors `ResearchVMwareKaliGuestReadiness`'s own cross-platform
        absolute-path check exactly, for the same reason: trusted
        configuration must be validated the same way regardless of which
        OS actually runs this installation.
        """
        return value.startswith("/") or PureWindowsPath(value).is_absolute()

    @staticmethod
    def _require_fingerprint(value: object) -> None:
        if not isinstance(value, str):
            raise ResearchError(
                "Guest-agent mTLS expected peer fingerprint must be text."
            )
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ResearchError(
                "Guest-agent mTLS expected peer fingerprint must be exactly 64 "
                "lowercase hexadecimal characters."
            )
