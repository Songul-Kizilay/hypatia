"""Which sources are the same resource, for the purpose of counting support.

Storing a page twice is a history question and storing it twice is fine. Counting
it twice is an epistemic question and counting it twice is not: two records of
one page read as two independent sources to anything that counts them, so a claim
resting on a single page can appear corroborated, and a hypothesis can look
supported by two sources it does not have.

So the two ideas are separated. Records stay as they are, and nothing is merged
or deleted. What changes is that support is counted over resource identities
rather than over stored records.

Normalisation is deliberately conservative, because a wrong merge is worse than a
missed one — a missed merge overcounts support, which the security audit already
flags, while a wrong merge silently discards a genuinely independent source. So
only equivalences that are essentially always true are applied: the scheme and
host are lowercased, a default port is dropped, a `www.` prefix is dropped, and
one trailing slash is dropped from the path.

Nothing else. The query string is kept, because two query strings usually mean
two resources. Case in the path is kept, because paths are case-sensitive on
most servers. Titles are never compared, because similar text is not identity.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

MAX_IDENTITY_LENGTH = 2048

_DEFAULT_PORTS = {"http": "80", "https": "443"}


def identity_of(url: str) -> str:
    """Return the canonical resource identity of a URL.

    Falls back to the stripped original when the URL cannot be parsed, so an
    unparseable value stays distinct from everything else rather than collapsing
    into one bucket with every other unparseable value.
    """
    if not isinstance(url, str) or not url.strip():
        return ""
    stripped = url.strip()
    try:
        parts = urlsplit(stripped)
    except ValueError:
        return stripped[:MAX_IDENTITY_LENGTH]
    if not parts.scheme or not parts.hostname:
        return stripped[:MAX_IDENTITY_LENGTH]
    host = parts.hostname.casefold()
    if host.startswith("www."):
        host = host[4:]
    scheme = parts.scheme.casefold()
    port = parts.port
    if port is not None and str(port) != _DEFAULT_PORTS.get(scheme):
        host = f"{host}:{port}"
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    identity = urlunsplit((scheme, host, path, parts.query, ""))
    return identity[:MAX_IDENTITY_LENGTH]


def same_resource(first: str, second: str) -> bool:
    """Return whether two URLs name the same resource for counting purposes."""
    left = identity_of(first)
    return bool(left) and left == identity_of(second)


def independent_identities(urls: tuple[str, ...]) -> frozenset[str]:
    """Return the distinct resource identities among these URLs."""
    return frozenset(
        identity for identity in (identity_of(url) for url in urls) if identity
    )
