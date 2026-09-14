"""The host a source came from, normalised enough to group by.

Reputation needs a unit, and the host is the honest one: it is what the URL
actually says, requires no lookup, and does not pretend to know who publishes
what. No public-suffix logic is applied, so `docs.example.com` and
`example.com` stay separate. Guessing that they share an owner would be a claim
about the world made from a string.

Normalisation is deliberately minimal — lowercase, drop a leading `www.`, drop
the port. Anything more would start merging origins on a hunch.
"""

from __future__ import annotations

from urllib.parse import urlsplit

MAX_ORIGIN_LENGTH = 253


def origin_of(url: str) -> str:
    """Return the normalised host of a URL, or empty when there is none."""
    if not isinstance(url, str) or not url.strip():
        return ""
    try:
        host = urlsplit(url.strip()).hostname
    except ValueError:
        return ""
    if not host:
        return ""
    normalised = host.casefold()
    if normalised.startswith("www."):
        normalised = normalised[4:]
    return normalised[:MAX_ORIGIN_LENGTH]
