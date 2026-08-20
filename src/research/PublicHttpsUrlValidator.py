"""Network policy for explicit public HTTPS research sources."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from typing import cast
from urllib.parse import SplitResult, urlsplit, urlunsplit

from core.Exceptions import ResearchError

HostResolver = Callable[[str], tuple[str, ...]]


def _resolve_host(hostname: str) -> tuple[str, ...]:
    try:
        records = socket.getaddrinfo(
            hostname,
            443,
            type=socket.SOCK_STREAM,
        )
    except OSError as error:
        raise ResearchError("Research source host could not be resolved.") from error
    return tuple(dict.fromkeys(cast(str, record[4][0]) for record in records))


class PublicHttpsUrlValidator:
    """Allow only credential-free HTTPS URLs resolving to public addresses."""

    def __init__(self, resolver: HostResolver = _resolve_host) -> None:
        self._resolver = resolver

    def validate(self, url: str) -> str:
        """Return a normalized URL after scheme, host, and address validation."""
        if not isinstance(url, str) or not url.strip():
            raise ResearchError("A research source URL is required.")
        try:
            parsed = urlsplit(url.strip())
            port = parsed.port
        except ValueError as error:
            raise ResearchError("Research source URL is invalid.") from error
        self._validate_parts(parsed, port)
        assert parsed.hostname is not None
        try:
            hostname = (
                parsed.hostname.encode("idna").decode("ascii").casefold().rstrip(".")
            )
        except UnicodeError as error:
            raise ResearchError("Research source host name is invalid.") from error
        if not hostname:
            raise ResearchError("Research source URL must include a valid host.")
        addresses = self._resolver(hostname)
        if not addresses:
            raise ResearchError("Research source host did not resolve to an address.")
        try:
            if any(
                not ipaddress.ip_address(address).is_global for address in addresses
            ):
                raise ResearchError(
                    "Research sources must resolve only to public internet addresses."
                )
        except ValueError as error:
            raise ResearchError(
                "Research source host returned an invalid address."
            ) from error
        try:
            literal_address = ipaddress.ip_address(hostname)
        except ValueError:
            literal_address = None
        formatted_host = (
            f"[{literal_address.compressed}]"
            if isinstance(literal_address, ipaddress.IPv6Address)
            else hostname
        )
        netloc = formatted_host if port is None else f"{formatted_host}:{port}"
        path = parsed.path or "/"
        return urlunsplit(("https", netloc, path, parsed.query, ""))

    @staticmethod
    def _validate_parts(parsed: SplitResult, port: int | None) -> None:
        if parsed.scheme.casefold() != "https":
            raise ResearchError("Research sources must use HTTPS.")
        if not parsed.hostname:
            raise ResearchError("Research source URL must include a host.")
        if parsed.username is not None or parsed.password is not None:
            raise ResearchError("Research source URLs cannot include credentials.")
        if port not in {None, 443}:
            raise ResearchError(
                "Research source URLs must use the standard HTTPS port."
            )
