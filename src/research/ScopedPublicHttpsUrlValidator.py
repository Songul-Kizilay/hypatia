"""Apply an explicit target scope at every existing HTTPS validation boundary."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from core.Exceptions import ResearchError
from research.PublicHttpsUrlValidator import (
    HostResolver,
    PublicHttpsUrlValidator,
    ValidatedPublicHttpsDestination,
    _resolve_host,
)
from research.ResearchTargetScope import ResearchTargetScope


class ScopedPublicHttpsUrlValidator(PublicHttpsUrlValidator):
    """Inject into HttpResearchSourceFetcher for scoped, bounded text GETs.

    The existing fetcher uses this validator before opening, for every redirect,
    at connection pinning, and before reading the final body. No separate HTTP
    stack, scanner, runtime grant, or automatic scope expansion is introduced.
    """

    def __init__(
        self, scope: ResearchTargetScope, resolver: HostResolver = _resolve_host
    ) -> None:
        if not isinstance(scope, ResearchTargetScope):
            raise ResearchError("Target acquisition requires an explicit scope.")
        super().__init__(resolver)
        self._scope = scope

    def validate_and_resolve(self, url: str) -> ValidatedPublicHttpsDestination:
        # urlsplit strips some controls. Refuse ambiguous input before parsing
        # instead of normalizing it into a newly authorized request authority.
        if (
            not isinstance(url, str)
            or not url
            or len(url) > 8192
            or any(
                character.isspace() or ord(character) < 32 or ord(character) == 127
                for character in url
            )
            or "\\" in url
        ):
            raise ResearchError("Scoped target URL is invalid.")
        try:
            parsed = urlsplit(url)
            self._validate_parts(parsed, parsed.port)
        except ValueError as error:
            raise ResearchError("Scoped target URL is invalid.") from error
        if not parsed.netloc.isascii():
            raise ResearchError("Scoped target authority must use ASCII.")
        assert parsed.hostname is not None
        self._scope.require_hostname(parsed.hostname)
        destination = super().validate_and_resolve(url)
        self._scope.require_hostname(destination.hostname)
        self._scope.require_addresses(destination.addresses)
        try:
            literal = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            pass
        else:
            if any(
                ipaddress.ip_address(value) != literal
                for value in destination.addresses
            ):
                raise ResearchError("Scoped literal address resolution changed target.")
        return destination
