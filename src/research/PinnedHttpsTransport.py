"""Connection-level address pinning for validated research HTTPS requests."""

from __future__ import annotations

import socket
import ssl
from collections.abc import Callable
from http.client import HTTPSConnection
from ssl import SSLContext
from typing import Any
from urllib.request import HTTPSHandler, Request

from core.Exceptions import ResearchError
from research.PublicHttpsUrlValidator import ValidatedPublicHttpsDestination

DestinationValidator = Callable[[str], ValidatedPublicHttpsDestination]


class PinnedHttpsConnection(HTTPSConnection):
    """Connect to one validated address while authenticating the URL hostname."""

    def __init__(
        self,
        host: str,
        port: int | None = None,
        *,
        pinned_address: str,
        timeout: float | None = None,
        source_address: tuple[str, int] | None = None,
        context: SSLContext | None = None,
        blocksize: int = 8192,
    ) -> None:
        tls_context = context or ssl.create_default_context()
        super().__init__(
            host,
            port=port,
            timeout=timeout,
            source_address=source_address,
            context=tls_context,
            blocksize=blocksize,
        )
        self._pinned_address = pinned_address
        self._pinned_source_address = source_address
        self._pinned_tls_context = tls_context

    def connect(self) -> None:
        """Open TCP to the pinned address and retain hostname-based TLS checks."""
        if getattr(self, "_tunnel_host", None):
            raise OSError("Pinned research connections do not support tunnels.")
        self.sock = socket.create_connection(
            (self.pinned_address, self.port),
            self.timeout,
            self._pinned_source_address,
        )
        self.sock = self._pinned_tls_context.wrap_socket(
            self.sock,
            server_hostname=self.host,
        )

    @property
    def pinned_address(self) -> str:
        """Return the exact validated address selected for this connection."""
        return self._pinned_address


class PinnedHttpsHandler(HTTPSHandler):
    """Resolve, validate, and pin every HTTPS request independently."""

    def __init__(self, destination_validator: DestinationValidator) -> None:
        tls_context = ssl.create_default_context()
        tls_context.set_alpn_protocols(["http/1.1"])
        super().__init__(context=tls_context)
        self._destination_validator = destination_validator
        self.tls_context = tls_context

    def https_open(self, req: Request) -> Any:
        destination = self._destination_validator(req.full_url)
        if destination.url != req.full_url:
            raise ResearchError("Research request URL was not normalized.")
        pinned_address = destination.addresses[0]

        def connection_factory(
            host: str,
            /,
            *,
            port: int | None = None,
            timeout: float = 10.0,
            source_address: tuple[str, int] | None = None,
            blocksize: int = 8192,
        ) -> HTTPSConnection:
            return PinnedHttpsConnection(
                host,
                port=port,
                pinned_address=pinned_address,
                timeout=timeout,
                source_address=source_address,
                context=self.tls_context,
                blocksize=blocksize,
            )

        return self.do_open(connection_factory, req)
