"""Strict mutual-TLS `SSLContext` construction for the future Guest-Agent channel.

TLS HANDSHAKE SUCCESS != EXECUTION AUTHORITY. mTLS CONNECTED != PERMISSION TO
EXECUTE. This module builds `ssl.SSLContext` objects and nothing else: it
opens no socket, performs no handshake, and contacts no network or process.
A future transport milestone wraps a real socket with the context this
module returns; that wrapping, and everything downstream of it, is out of
scope here.

Every context built here starts from a raw `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT
| ssl.PROTOCOL_TLS_SERVER)` -- never `ssl.create_default_context()`, because
that convenience constructor also calls `load_default_certs()` and would
pull in the operating system's global trusted root CA bundle. For a private
channel between two project-controlled peers, that would be exactly the
"accidentally trust system/global CAs" mistake this module exists to avoid:
the *only* certificate authority either context ever trusts is the one
explicit, project-owned CA file named in
`research.GuestAgentMtlsTrustConfiguration.GuestAgentMtlsTrustConfiguration.trusted_ca_certificate_path`.

Both the host-as-client and the guest-as-server context are hardened
identically and explicitly, never by relying on a constructor default to
happen to already be strict:

- TLS 1.3 only (`minimum_version == maximum_version == ssl.TLSVersion.TLSv1_3`)
  -- not merely "at least 1.2" -- because both peers are this project's own
  code and there is no legacy-interoperability requirement to honor.
- `verify_mode = ssl.CERT_REQUIRED`, explicitly, on *both* sides. A raw
  `ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)` defaults to `CERT_NONE` --
  anonymous clients accepted -- which is exactly the one-sided-TLS trap
  that is not mutual TLS at all; this module never leaves that default in
  place.
- Compression explicitly disabled (`ssl.OP_NO_COMPRESSION`).
- `keylog_filename` explicitly set to `None` -- never read from
  `SSLKEYLOGFILE` or any other environment variable, so a build cannot be
  made to leak session secrets to a log file by an environment change.

There is no "development mode," no parameter that disables verification,
and no helper named anything like `_create_unverified_context`: every
construction path here ends in the same strict configuration, and the
tests prove there is no other branch to reach.

Application identity (does the certificate name the *expected role*, not
merely some certificate this CA happened to sign) is deliberately checked
the same way on *both* sides, after the handshake, never by this module's
own `ssl.SSLContext.check_hostname` mechanism. That mechanism exists for
`dNSName` Subject Alternative Names (and, as a legacy fallback, the
Subject Common Name) -- it has no defined meaning for a `URI` SAN, and
this project's peer identities are URIs on purpose (see
`research.GuestAgentMtlsTrustConfiguration`'s own docstring for why a DNS
name is the wrong shape here). Setting `check_hostname = True` and
passing a URI string as `server_hostname` would not perform the check its
name suggests; `check_hostname` is therefore explicitly `False` on the
client context too, and a future transport must call
`research.GuestAgentPeerCertificateIdentity.parse_peer_certificate_identity`/
`peer_identity_matches` against the real, already-chain-verified peer
certificate on *both* ends after the handshake completes -- exactly the
one mechanism this repository can actually prove correct for a URI SAN,
used symmetrically rather than relying on a built-in check that silently
does not apply.
"""

from __future__ import annotations

import ssl

from core.Exceptions import ResearchError
from research.GuestAgentMtlsTrustConfiguration import (
    GuestAgentMtlsTrustConfiguration,
    GuestAgentPeerRole,
)


def build_host_client_tls_context(
    config: GuestAgentMtlsTrustConfiguration,
) -> ssl.SSLContext:
    """Return a strict mTLS client context for the host dialing the guest.

    Requires `config.own_role is GuestAgentPeerRole.HOST`. The returned
    context authenticates the guest's certificate chain against the
    project CA (`verify_mode = ssl.CERT_REQUIRED`). `check_hostname` is
    explicitly `False`, not `True`: this project's peer identities are
    `URI` SANs, which the real `ssl`/OpenSSL hostname-checking machinery
    never matches against (it only ever considers `dNSName` SANs and the
    legacy Subject CN) -- so setting `check_hostname=True` here would not
    perform any real identity check at all, it would only look like one.
    A future transport must instead check
    `research.GuestAgentPeerCertificateIdentity.parse_peer_certificate_identity`/
    `peer_identity_matches` against `config.expected_peer_identity` using
    the real, already-chain-verified peer certificate obtained after the
    handshake -- the same mechanism the guest-server side already uses.
    This function also presents the host's own certificate, so the guest
    can authenticate it in turn: a client that sends no certificate is
    not mutual TLS.
    """
    _require_role(config, GuestAgentPeerRole.HOST)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    _harden(context)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = False
    _load_trust_and_identity(context, config)
    return context


def build_guest_server_tls_context(
    config: GuestAgentMtlsTrustConfiguration,
) -> ssl.SSLContext:
    """Return a strict mTLS server context for the guest accepting the host.

    Requires `config.own_role is GuestAgentPeerRole.GUEST`. Explicitly sets
    `verify_mode = ssl.CERT_REQUIRED` -- a raw `PROTOCOL_TLS_SERVER` context
    defaults to `CERT_NONE`, which would accept any client with no
    certificate at all. The host's application identity is not checked by
    this context object itself (`check_hostname` has no meaning for an
    incoming client certificate); a future transport must inspect the
    already-verified peer certificate after `accept()` via
    `research.GuestAgentPeerCertificateIdentity.parse_peer_certificate_identity`/
    `peer_identity_matches`, exactly as this module's own docstring
    describes for that module.
    """
    _require_role(config, GuestAgentPeerRole.GUEST)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    _harden(context)
    context.verify_mode = ssl.CERT_REQUIRED
    _load_trust_and_identity(context, config)
    return context


def _require_role(
    config: GuestAgentMtlsTrustConfiguration, role: GuestAgentPeerRole
) -> None:
    if not isinstance(config, GuestAgentMtlsTrustConfiguration):
        raise ResearchError(
            "Guest-agent mTLS context construction requires a bounded trust "
            "configuration."
        )
    if config.own_role is not role:
        raise ResearchError(
            "Guest-agent mTLS context construction requires a configuration "
            "for the matching role."
        )


def _harden(context: ssl.SSLContext) -> None:
    """Apply the one strict policy both roles share, explicitly."""
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.options |= ssl.OP_NO_COMPRESSION
    # `keylog_filename` is typed as `str` by the stub, but the runtime
    # genuinely accepts and honors `None` ("disabled") -- confirmed
    # directly against this project's own Python/OpenSSL build, not
    # merely assumed. Never read from `SSLKEYLOGFILE` or any other
    # environment variable.
    context.keylog_filename = None  # type: ignore[assignment]


def _load_trust_and_identity(
    context: ssl.SSLContext, config: GuestAgentMtlsTrustConfiguration
) -> None:
    """Load the one trusted CA and this side's own presented certificate.

    Both calls touch the filesystem at the exact paths the trusted
    configuration names -- never a path derived from protocol data, chat
    text, or model output, because `GuestAgentMtlsTrustConfiguration` is
    the only type that can ever supply them.
    """
    context.load_verify_locations(cafile=config.trusted_ca_certificate_path)
    context.load_cert_chain(
        certfile=config.own_certificate_path,
        keyfile=config.own_private_key_path,
    )
