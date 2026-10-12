"""Close the gap between "chain-valid certificate" and "expected application peer."

AUTHENTICATED PEER != EXECUTION AUTHORITY. AUTHENTICATED CHANNEL != EXECUTION
AUTHORITY. AUTHENTICATED CHANNEL != OPERATION AUTHORIZATION. TLS CONTEXT
CONFIGURED != PEER AUTHENTICATED. TLS HANDSHAKE SUCCESS != APPLICATION
IDENTITY MATCH. CERTIFICATE CHAIN VALID != CORRECT APPLICATION PEER. PEER
IDENTITY MATCH != EXECUTION AUTHORITY.

This module cannot itself perform or prove that a real TLS handshake and
chain verification happened -- that remains entirely a future transport's
job, using the strict `ssl.SSLContext` builders already established in
`research.GuestAgentMtlsContext`. Nothing here opens a socket, performs a
handshake, touches a network, or accepts a caller-supplied boolean (such as
`verified=True`, `chain_valid=True`, or `trusted=True`) that could
manufacture authentication without an actual matching
`GuestAgentPeerCertificateIdentityObservation`. The conceptual order a
future transport must follow is: TLS chain verification succeeds -> obtain
the real peer certificate -> parse a bounded peer certificate observation
(`research.GuestAgentPeerCertificateIdentity.parse_peer_certificate_identity`)
-> call `authenticate_peer` here -> only then may protocol bytes cross the
application channel boundary via `research.GuestAgentAuthenticatedChannel`.
Even then, an authenticated channel still never means "this operation may
execute" -- that remains `KaliToolGateway`'s authority alone, and this
module is never wired into it.

`authenticate_peer` reuses `research.GuestAgentPeerCertificateIdentity
.peer_identity_matches` for the actual URI SAN / validity / fingerprint
comparison; it never duplicates that logic. `observation` is intentionally
typed as `object` at this boundary (rather than
`GuestAgentPeerCertificateIdentityObservation`): a caller that has not
actually produced a real observation (for example because parsing upstream
failed, or a caller mistakenly passed `None` or raw cert data) gets back a
bounded `INVALID_CERTIFICATE_OBSERVATION` status, never an unhandled
exception and never a silent pass.

`GuestAgentAuthenticatedPeer` is deliberately not publicly constructible.
Python dataclasses have no true private constructor, so this module uses a
module-private capability-token pattern instead: the dataclass requires a
keyword-only `_authentication_token` field, and `__post_init__` rejects any
value other than this module's own private sentinel object, which is never
exported and is used in exactly one place -- inside `authenticate_peer`,
after an exact identity match already succeeded. A caller that does not
import this module's private sentinel (which nothing public ever hands
out) cannot construct a `GuestAgentAuthenticatedPeer` that claims
authentication did not actually happen. This is a structural property,
tested directly -- not a claim resting on a docstring alone.

The authenticated peer value itself carries only a role and a matched
identity: no capability, no scope, no credential, no private key material,
and no permission of any kind. It cannot grant anything by existing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from core.Exceptions import ResearchError
from research.GuestAgentMtlsTrustConfiguration import (
    GuestAgentMtlsTrustConfiguration,
    GuestAgentPeerIdentity,
    GuestAgentPeerRole,
)
from research.GuestAgentPeerCertificateIdentity import (
    GuestAgentPeerCertificateIdentityObservation,
    peer_identity_matches,
)

#: Module-private capability token. Never exported, never re-derivable from
#: public data: the only code path that can supply this exact object to
#: `GuestAgentAuthenticatedPeer.__init__` is `authenticate_peer`, below,
#: after an exact role/identity match already succeeded.
_AUTHENTICATION_CAPABILITY = object()

_REASON_AUTHENTICATED = "The peer certificate matched the expected role identity."
_REASON_IDENTITY_MISMATCH = (
    "The peer certificate did not match the expected role identity."
)
_REASON_INVALID_OBSERVATION = (
    "The supplied peer certificate observation is not a valid observation."
)


class GuestAgentChannelAuthenticationStatus(StrEnum):
    """The smallest honest, closed set of channel authentication outcomes.

    There is no `CONNECTED`, `READY_TO_EXECUTE`, or `AUTHORIZED` status, and
    there never will be one named or meaning "authorized to execute": this
    enum only ever describes whether the supplied certificate evidence
    names the expected application peer, never whether any operation may
    run.
    """

    AUTHENTICATED = "authenticated"
    IDENTITY_MISMATCH = "identity_mismatch"
    INVALID_CERTIFICATE_OBSERVATION = "invalid_certificate_observation"


@dataclass(frozen=True, slots=True, kw_only=True)
class GuestAgentAuthenticatedPeer:
    """An exact-identity-matched peer. Not execution authority; see module docstring.

    `peer_role` is always derived from `own_role.other`, exactly like
    `GuestAgentMtlsTrustConfiguration.expected_peer_role` -- it is never an
    independently settable field, so this value can never claim a
    self-contradictory role pairing.
    """

    own_role: GuestAgentPeerRole
    peer_identity: GuestAgentPeerIdentity
    _authentication_token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._authentication_token is not _AUTHENTICATION_CAPABILITY:
            raise ResearchError(
                "Guest-agent authenticated peer may only be constructed by "
                "research.GuestAgentPeerAuthenticator.authenticate_peer."
            )
        if not isinstance(self.own_role, GuestAgentPeerRole):
            raise ResearchError("Guest-agent authenticated peer own role is invalid.")
        if not isinstance(self.peer_identity, GuestAgentPeerIdentity):
            raise ResearchError("Guest-agent authenticated peer identity is invalid.")
        if self.peer_identity.role is not self.own_role.other:
            raise ResearchError(
                "Guest-agent authenticated peer identity does not match the "
                "expected peer role."
            )

    @property
    def peer_role(self) -> GuestAgentPeerRole:
        """Return the one role the authenticated peer was matched against."""
        return self.own_role.other


@dataclass(frozen=True, slots=True, kw_only=True)
class GuestAgentChannelAuthenticationResult:
    """The outcome of one `authenticate_peer` call. Not execution authority.

    `authenticated_peer` is present if, and only if, `status` is
    `AUTHENTICATED` -- `__post_init__` enforces that pairing so the two
    fields can never disagree.
    """

    status: GuestAgentChannelAuthenticationStatus
    reason: str
    authenticated_peer: GuestAgentAuthenticatedPeer | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, GuestAgentChannelAuthenticationStatus):
            raise ResearchError("Guest-agent channel authentication status is invalid.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ResearchError(
                "Guest-agent channel authentication reason cannot be empty."
            )
        if "\x00" in self.reason or "\r" in self.reason or "\n" in self.reason:
            raise ResearchError(
                "Guest-agent channel authentication reason contains control data."
            )
        is_authenticated = (
            self.status is GuestAgentChannelAuthenticationStatus.AUTHENTICATED
        )
        if is_authenticated and not isinstance(
            self.authenticated_peer, GuestAgentAuthenticatedPeer
        ):
            raise ResearchError(
                "An authenticated channel result must carry an authenticated peer."
            )
        if not is_authenticated and self.authenticated_peer is not None:
            raise ResearchError(
                "An unauthenticated channel result must not carry an "
                "authenticated peer."
            )

    @property
    def authenticated(self) -> bool:
        """Return whether this result reached `AUTHENTICATED`."""
        return self.status is GuestAgentChannelAuthenticationStatus.AUTHENTICATED


def authenticate_peer(
    observation: object,
    trust_configuration: GuestAgentMtlsTrustConfiguration,
) -> GuestAgentChannelAuthenticationResult:
    """Decide whether `observation` honestly is the expected application peer.

    Reuses `peer_identity_matches` for the actual comparison; this function
    never duplicates URI SAN, validity, or fingerprint logic. `observation`
    is accepted as `object` so a caller that did not actually produce a
    real `GuestAgentPeerCertificateIdentityObservation` gets a bounded
    `INVALID_CERTIFICATE_OBSERVATION` result rather than an exception.
    `trust_configuration` is trusted, code-owned configuration the calling
    transport constructs -- not wire data -- so an invalid one raises
    rather than returning a status.

    This function cannot, by itself, prove that a real TLS handshake or
    chain verification occurred: see the module docstring. It enforces
    application identity over certificate facts a future strict transport
    must already have obtained that way.
    """
    if not isinstance(trust_configuration, GuestAgentMtlsTrustConfiguration):
        raise ResearchError(
            "Guest-agent peer authentication requires a bounded trust " "configuration."
        )
    if not isinstance(observation, GuestAgentPeerCertificateIdentityObservation):
        return GuestAgentChannelAuthenticationResult(
            status=GuestAgentChannelAuthenticationStatus.INVALID_CERTIFICATE_OBSERVATION,
            reason=_REASON_INVALID_OBSERVATION,
            authenticated_peer=None,
        )
    expected_identity = trust_configuration.expected_peer_identity
    if not peer_identity_matches(observation, expected_identity, trust_configuration):
        return GuestAgentChannelAuthenticationResult(
            status=GuestAgentChannelAuthenticationStatus.IDENTITY_MISMATCH,
            reason=_REASON_IDENTITY_MISMATCH,
            authenticated_peer=None,
        )
    peer = GuestAgentAuthenticatedPeer(
        own_role=trust_configuration.own_role,
        peer_identity=expected_identity,
        _authentication_token=_AUTHENTICATION_CAPABILITY,
    )
    return GuestAgentChannelAuthenticationResult(
        status=GuestAgentChannelAuthenticationStatus.AUTHENTICATED,
        reason=_REASON_AUTHENTICATED,
        authenticated_peer=peer,
    )
