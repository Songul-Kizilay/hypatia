"""Connection-level address pinning for validated research HTTPS requests."""

from __future__ import annotations

import socket
import ssl
import time
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
        pinned_addresses: tuple[str, ...],
        timeout: float | None = None,
        source_address: tuple[str, int] | None = None,
        context: SSLContext | None = None,
        blocksize: int = 8192,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not pinned_addresses:
            raise ValueError("Pinned research addresses cannot be empty.")
        if timeout is not None and timeout <= 0:
            raise ValueError("Pinned research timeout must be positive.")
        tls_context = context or ssl.create_default_context()
        super().__init__(
            host,
            port=port,
            timeout=timeout,
            source_address=source_address,
            context=tls_context,
            blocksize=blocksize,
        )
        self._pinned_addresses = pinned_addresses
        self._connected_address: str | None = None
        self._pinned_source_address = source_address
        self._pinned_tls_context = tls_context
        self._clock = clock

    def connect(self) -> None:
        """Open TCP to the pinned address and retain hostname-based TLS checks."""
        if getattr(self, "_tunnel_host", None):
            raise OSError("Pinned research connections do not support tunnels.")
        deadline = None if self.timeout is None else self._clock() + self.timeout
        last_error: OSError | None = None
        for address in self._pinned_addresses:
            remaining = self._remaining_timeout(deadline)
            if remaining is not None and remaining <= 0:
                last_error = TimeoutError("Pinned research timeout expired.")
                break
            raw_socket: socket.socket | None = None
            try:
                raw_socket = socket.create_connection(
                    (address, self.port),
                    remaining,
                    self._pinned_source_address,
                )
                tls_timeout = self._remaining_timeout(deadline)
                if tls_timeout is not None:
                    if tls_timeout <= 0:
                        raise TimeoutError("Pinned research timeout expired.")
                    raw_socket.settimeout(tls_timeout)
                tls_socket = self._pinned_tls_context.wrap_socket(
                    raw_socket,
                    server_hostname=self.host,
                )
                connected_timeout = self._remaining_timeout(deadline)
                if connected_timeout is not None:
                    if connected_timeout <= 0:
                        tls_socket.close()
                        raise TimeoutError("Pinned research timeout expired.")
                    tls_socket.settimeout(connected_timeout)
            except OSError as error:
                if raw_socket is not None:
                    raw_socket.close()
                last_error = error
                continue
            self.sock = tls_socket
            self._connected_address = address
            return
        raise OSError("All validated research addresses failed.") from last_error

    def _remaining_timeout(self, deadline: float | None) -> float | None:
        if deadline is None:
            return None
        return deadline - self._clock()

    @property
    def pinned_address(self) -> str:
        """Return the connected address, or the first candidate before connect."""
        return self._connected_address or self._pinned_addresses[0]

    @property
    def pinned_addresses(self) -> tuple[str, ...]:
        """Return the complete ordered address set from one validation."""
        return self._pinned_addresses


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
        pinned_addresses = destination.addresses

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
                pinned_addresses=pinned_addresses,
                timeout=timeout,
                source_address=source_address,
                context=self.tls_context,
                blocksize=blocksize,
            )

        return self.do_open(connection_factory, req)
