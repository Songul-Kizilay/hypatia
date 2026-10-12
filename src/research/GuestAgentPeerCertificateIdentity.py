"""Facts a future TLS transport observes about an already-verified peer.

TRUSTED CERTIFICATE != EXECUTION AUTHORITY. PEER IDENTITY MATCH != EXECUTION
AUTHORITY. This module never performs a TLS handshake and never decides
whether a certificate chains to a trusted CA -- that cryptographic
verification belongs entirely to `ssl.SSLContext` (in `CERT_REQUIRED` mode)
in a future transport milestone, which raises `ssl.SSLCertVerificationError`
and never returns peer certificate data at all when verification fails.
`parse_peer_certificate_identity` only ever extracts plain facts from the
same dict shape Python's own `ssl.SSLSocket.getpeercert()` already returns
-- it never consults a network, a process, or a socket, and it never
accepts a caller-supplied `chain_verified` flag or anything like one:
there is no field here a caller could set to manufacture trust, because the
only way real code can produce the input shape this function accepts is to
have already survived real chain verification.

`peer_identity_matches` is the one application-level decision this module
makes, and it is narrow on purpose: given an observation already produced
by (in real use) a successful handshake, does it name the exact expected
role's identity, is it currently within its validity window, and -- only if
the trust configuration opted into the additional check -- does its
fingerprint match? Matching is always exact equality against the full URI
string; there is no substring, prefix, or wildcard comparison anywhere in
this module, so a certificate naming `"hypatia-kali-guest-agent/guest/1evil"`
or a crafted superstring can never be mistaken for the real guest identity.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from core.Exceptions import ResearchError
from research.GuestAgentMtlsTrustConfiguration import (
    MAX_PEER_IDENTITY_URI_LENGTH,
    GuestAgentMtlsTrustConfiguration,
    GuestAgentPeerIdentity,
)

MAX_SAN_ENTRIES = 20
MAX_SAN_VALUE_LENGTH = MAX_PEER_IDENTITY_URI_LENGTH

_SHA256_FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")

#: Python's own `ssl` module date format for `notBefore`/`notAfter`, as
#: `ssl.SSLSocket.getpeercert()` already documents it: e.g.
#: `"Jan  1 00:00:00 2026 GMT"`. Reused verbatim -- this is not a format
#: this module invents, it is the one the standard library already commits
#: to for this exact dict shape.
_CERT_TIME_FORMAT = "%b %d %H:%M:%S %Y %Z"


@dataclass(frozen=True, slots=True)
class GuestAgentPeerCertificateIdentityObservation:
    """Bounded facts extracted from one already-handshake-verified peer cert.

    Every field here is a plain, bounded fact -- never a decision, and
    never a boolean a caller could flip to assert verification happened.
    `fingerprint_sha256` is `None` when the DER bytes needed to compute it
    were not supplied to `parse_peer_certificate_identity`; it is never a
    caller-asserted string independent of those bytes.
    """

    dns_names: tuple[str, ...]
    uri_names: tuple[str, ...]
    not_before: datetime
    not_after: datetime
    fingerprint_sha256: str | None

    def __post_init__(self) -> None:
        self._validate_names(self.dns_names, "DNS SAN entry")
        self._validate_names(self.uri_names, "URI SAN entry")
        for value, label in (
            (self.not_before, "validity start"),
            (self.not_after, "validity end"),
        ):
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise ResearchError(
                    f"Guest-agent peer certificate {label} must be timezone-aware."
                )
        if self.not_after <= self.not_before:
            raise ResearchError(
                "Guest-agent peer certificate validity end must follow its start."
            )
        if (
            self.fingerprint_sha256 is not None
            and not _SHA256_FINGERPRINT_PATTERN.fullmatch(self.fingerprint_sha256)
        ):
            raise ResearchError(
                "Guest-agent peer certificate fingerprint must be exactly 64 "
                "lowercase hexadecimal characters."
            )

    @property
    def currently_valid(self) -> bool:
        """Return whether this observation's validity window covers now."""
        now = datetime.now(UTC)
        return self.not_before <= now <= self.not_after

    @staticmethod
    def _validate_names(values: tuple[str, ...], label: str) -> None:
        if not isinstance(values, tuple):
            raise ResearchError(
                f"Guest-agent peer certificate {label}s must be an immutable sequence."
            )
        if len(values) > MAX_SAN_ENTRIES:
            raise ResearchError(f"Guest-agent peer certificate has too many {label}s.")
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"Guest-agent peer certificate {label} is invalid.")
            if "\x00" in value or "\r" in value or "\n" in value:
                raise ResearchError(
                    f"Guest-agent peer certificate {label} contains control data."
                )
            if len(value) > MAX_SAN_VALUE_LENGTH:
                raise ResearchError(
                    f"Guest-agent peer certificate {label} is too long."
                )


def parse_peer_certificate_identity(
    cert_dict: Mapping[str, object],
    *,
    der_bytes: bytes | None = None,
) -> GuestAgentPeerCertificateIdentityObservation:
    """Extract bounded identity facts from a `getpeercert()`-shaped dict.

    Fails closed on anything that is not exactly this shape: a missing
    `subjectAltName`, an unparseable validity date, or a malformed entry
    all raise `core.Exceptions.ResearchError` rather than guessing. This
    function never opens a socket, a file, or a process -- its only input
    is already-decoded data.
    """
    if not isinstance(cert_dict, Mapping):
        raise ResearchError("Guest-agent peer certificate data must be a mapping.")
    dns_names: list[str] = []
    uri_names: list[str] = []
    san_entries = cert_dict.get("subjectAltName", ())
    if not isinstance(san_entries, tuple):
        raise ResearchError(
            "Guest-agent peer certificate subject alternative names are invalid."
        )
    for entry in san_entries:
        if (
            not isinstance(entry, tuple)
            or len(entry) != 2
            or not isinstance(entry[0], str)
            or not isinstance(entry[1], str)
        ):
            raise ResearchError(
                "Guest-agent peer certificate subject alternative name entry "
                "is invalid."
            )
        kind, value = entry
        if kind == "DNS":
            dns_names.append(value)
        elif kind == "URI":
            uri_names.append(value)
        # Any other SAN kind (IP address, email, etc.) is deliberately
        # ignored here: this module only ever matches on DNS/URI identity,
        # never on an address.
    not_before = _parse_cert_time(cert_dict.get("notBefore"), "validity start")
    not_after = _parse_cert_time(cert_dict.get("notAfter"), "validity end")
    fingerprint = (
        hashlib.sha256(der_bytes).hexdigest() if der_bytes is not None else None
    )
    return GuestAgentPeerCertificateIdentityObservation(
        dns_names=tuple(dns_names),
        uri_names=tuple(uri_names),
        not_before=not_before,
        not_after=not_after,
        fingerprint_sha256=fingerprint,
    )


def _parse_cert_time(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ResearchError(f"Guest-agent peer certificate {label} is invalid.")
    try:
        parsed = datetime.strptime(value, _CERT_TIME_FORMAT)
    except ValueError as error:
        raise ResearchError(
            f"Guest-agent peer certificate {label} is invalid."
        ) from error
    return parsed.replace(tzinfo=UTC)


def peer_identity_matches(
    observation: GuestAgentPeerCertificateIdentityObservation,
    expected: GuestAgentPeerIdentity,
    trust_configuration: GuestAgentMtlsTrustConfiguration | None = None,
) -> bool:
    """Return whether `observation` honestly is the expected application peer.

    Exact URI match only -- `expected.uri in observation.uri_names` is a
    tuple-membership equality check, never a substring or prefix test.
    Also requires the observation's own validity window to currently cover
    now (defense in depth: real handshake-time chain verification already
    enforces this, but nothing here assumes that happened). When
    `trust_configuration` carries an optional pinned fingerprint, that must
    match exactly too; a configuration with no pinned fingerprint makes no
    fingerprint claim at all, and this function makes none on its behalf.

    When both `expected` and `trust_configuration` are supplied, they must
    agree: `expected` must equal `trust_configuration.expected_peer_identity`.
    This closes an avoidable footgun rather than silently trusting whichever
    of the two a caller passed -- a caller that somehow supplied a
    `trust_configuration` for one role alongside an `expected` identity for
    a different one gets a loud, immediate `ResearchError`, never a quiet
    comparison against the wrong value.
    """
    if not isinstance(observation, GuestAgentPeerCertificateIdentityObservation):
        raise ResearchError("Guest-agent peer identity check requires an observation.")
    if not isinstance(expected, GuestAgentPeerIdentity):
        raise ResearchError(
            "Guest-agent peer identity check requires an expected identity."
        )
    if trust_configuration is not None and not isinstance(
        trust_configuration, GuestAgentMtlsTrustConfiguration
    ):
        raise ResearchError(
            "Guest-agent peer identity check requires a bounded trust configuration."
        )
    if (
        trust_configuration is not None
        and expected != trust_configuration.expected_peer_identity
    ):
        raise ResearchError(
            "Guest-agent peer identity check requires the expected identity "
            "to match the trust configuration's own expected peer identity."
        )
    if expected.uri not in observation.uri_names:
        return False
    if not observation.currently_valid:
        return False
    expected_fingerprint = (
        trust_configuration.expected_peer_fingerprint_sha256
        if trust_configuration is not None
        else None
    )
    if expected_fingerprint is not None:
        if observation.fingerprint_sha256 != expected_fingerprint:
            return False
    return True
