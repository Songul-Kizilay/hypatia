"""Pure, network-oblivious length-prefixed framing for the Guest-Agent RPC wire.

FRAME DELIVERY != EXECUTION AUTHORITY. This module answers only "how many
bytes make up the next message on this connection, and where does it end" --
it never parses, interprets, authenticates, or authorizes anything. It opens
no socket itself, starts no process, and performs no TLS handshake; every
function here operates on a caller-supplied socket-like object (see
`GuestAgentRpcFramingSocket` below) that a future transport module is
responsible for actually connecting, accepting, and TLS-wrapping.

Wire shape: exactly one fixed 4-byte big-endian unsigned length prefix
(`struct.Struct(">I")`), followed by exactly that many bytes of canonical
JSON payload (the existing
`research.GuestAgentProtocolSerialization.canonical_guest_agent_request_bytes`/
`canonical_guest_agent_response_bytes` output). No delimiter, no newline
framing, no read-until-EOF, no unbounded buffering, and no
pickle/marshal/eval/YAML anywhere in this module -- the payload bytes
themselves are opaque to framing; decoding them into a typed protocol object
is the authenticated channel's job
(`research.GuestAgentAuthenticatedChannel`), never this module's.

`MAX_GUEST_AGENT_RPC_FRAME_SIZE` is derived honestly from the existing,
already-bounded protocol contract in `research.GuestAgentProtocol`, not an
arbitrary giant number. Computed directly against the real canonical-JSON
encoder (`research.GuestAgentProtocolSerialization`), using the worst-case
*character* content the protocol's own validation still permits --
`ensure_ascii=True` JSON encoding escapes every non-ASCII character as a
`\\uXXXX` sequence, and a Python `str` character above the Basic Multilingual
Plane (for example an emoji) is encoded as a UTF-16 *surrogate pair*, i.e.
TWO `\\uXXXX` escapes (12 ASCII bytes) for what `len()` counts as a single
character -- the worst-case expansion `ensure_ascii=True` can produce, and
the figure this module's ceiling is actually measured against (not the
single-`\\uXXXX`/6-byte estimate a BMP-only character would produce):

    Request worst case (10 logical-input pairs, field names and values each
    filled entirely with such a maximal-expansion character, request_id and
    nonce at their own bounds, a full 64-hex-character operation digest):
    measured at 496,990 bytes (~485.3 KiB) via
    `canonical_guest_agent_request_bytes` against a `GuestAgentRequest` built
    at every field's documented maximum.

    Response worst case (50 output lines at 500 characters each, a 500-
    character detail, all filled with the same maximal-expansion character):
    measured at 308,705 bytes (~301.5 KiB) via
    `canonical_guest_agent_response_bytes`.

512 KiB (`512 * 1024 = 524,288` bytes) is chosen as the one shared ceiling
for both directions: comfortably above the larger (request) worst case with
modest headroom (~27.3 KiB, ~5.5%) -- enough to admit ordinary JSON
formatting variance, never a multi-MB or unbounded allowance, and never
large enough that an attacker-declared length anywhere near this ceiling
could be mistaken for a plausible, honestly-reachable message.
"""

from __future__ import annotations

import struct
from enum import StrEnum
from typing import Protocol

from core.Exceptions import ResearchError

#: 512 KiB -- see the module docstring for the exact worst-case measurement
#: this ceiling is checked against (request: 496,990 bytes; response:
#: 308,705 bytes). Modest, explicit headroom over the larger of the two;
#: never unbounded, never multi-megabyte.
MAX_GUEST_AGENT_RPC_FRAME_SIZE = 512 * 1024

#: Fixed 4-byte big-endian unsigned length prefix. Deterministic byte order
#: on every platform this project runs on, regardless of host endianness.
_LENGTH_PREFIX_STRUCT = struct.Struct(">I")
LENGTH_PREFIX_SIZE = _LENGTH_PREFIX_STRUCT.size


class GuestAgentRpcFramingFailureKind(StrEnum):
    """The smallest closed set of ways one frame can fail to be read or written.

    Never a raw string compare anywhere this module or its callers decide
    what went wrong -- always this enum, carried on
    `GuestAgentRpcFramingError.kind`.
    """

    TRUNCATED_PREFIX = "truncated_prefix"
    TRUNCATED_BODY = "truncated_body"
    ZERO_LENGTH = "zero_length"
    OVERSIZED_LENGTH = "oversized_length"


_FAILURE_MESSAGES: dict[GuestAgentRpcFramingFailureKind, str] = {
    GuestAgentRpcFramingFailureKind.TRUNCATED_PREFIX: (
        "Guest-agent RPC frame length prefix was truncated."
    ),
    GuestAgentRpcFramingFailureKind.TRUNCATED_BODY: (
        "Guest-agent RPC frame body was truncated."
    ),
    GuestAgentRpcFramingFailureKind.ZERO_LENGTH: (
        "Guest-agent RPC frame declared a zero length."
    ),
    GuestAgentRpcFramingFailureKind.OVERSIZED_LENGTH: (
        "Guest-agent RPC frame declared length exceeds the bound."
    ),
}


class GuestAgentRpcFramingError(ResearchError):
    """One framing failure. Carries a closed `kind`, never raw peer bytes.

    The exception message is always one of this module's own fixed, code-
    owned sentences (`_FAILURE_MESSAGES`) -- never built from, or including,
    any attacker-controlled byte, declared length value, or partial payload.
    """

    def __init__(self, kind: GuestAgentRpcFramingFailureKind) -> None:
        super().__init__(_FAILURE_MESSAGES[kind])
        self.kind = kind


class GuestAgentRpcFramingSocket(Protocol):
    """The narrow socket-like surface framing needs -- nothing more.

    Both `socket.socket` and `ssl.SSLSocket` already satisfy this
    structurally; production code never wraps them to conform. A test can
    supply a trivial fake implementing just this surface, with no real
    socket involved at all.
    """

    def recv(self, buffer_size: int, /) -> bytes: ...

    def sendall(self, data: bytes, /) -> None: ...


def _read_exact(
    sock: GuestAgentRpcFramingSocket,
    size: int,
    failure_kind: GuestAgentRpcFramingFailureKind,
) -> bytes:
    """Read exactly `size` bytes, looping over real `recv()` calls only.

    Never trusts one `recv()` call to return everything requested, and never
    polls or sleeps -- it loops strictly on actual data arriving. Raises
    `failure_kind` the moment the peer closes (an empty `recv()` result)
    before `size` bytes have been accumulated.
    """
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise GuestAgentRpcFramingError(failure_kind)
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_guest_agent_rpc_frame(
    sock: GuestAgentRpcFramingSocket,
    *,
    max_frame_size: int = MAX_GUEST_AGENT_RPC_FRAME_SIZE,
) -> bytes:
    """Read exactly one length-prefixed frame's payload bytes.

    Reads the fixed 4-byte prefix via a bounded exact-read loop, rejects a
    declared length of zero, and rejects a declared length greater than
    `max_frame_size` BEFORE performing any body read or allocation -- a
    hostile declared length can never cause this function to attempt a
    body read at all, let alone allocate a buffer sized by it. Only after
    that bound check passes does it read exactly the declared number of
    body bytes, via the same bounded exact-read loop.
    """
    prefix = _read_exact(
        sock,
        LENGTH_PREFIX_SIZE,
        GuestAgentRpcFramingFailureKind.TRUNCATED_PREFIX,
    )
    (declared_length,) = _LENGTH_PREFIX_STRUCT.unpack(prefix)
    if declared_length == 0:
        raise GuestAgentRpcFramingError(GuestAgentRpcFramingFailureKind.ZERO_LENGTH)
    if declared_length > max_frame_size:
        raise GuestAgentRpcFramingError(
            GuestAgentRpcFramingFailureKind.OVERSIZED_LENGTH
        )
    return _read_exact(
        sock,
        declared_length,
        GuestAgentRpcFramingFailureKind.TRUNCATED_BODY,
    )


def write_guest_agent_rpc_frame(
    sock: GuestAgentRpcFramingSocket,
    payload: bytes,
    *,
    max_frame_size: int = MAX_GUEST_AGENT_RPC_FRAME_SIZE,
) -> None:
    """Write exactly one length-prefixed frame in a single `sendall` call.

    Validates `0 < len(payload) <= max_frame_size` before sending anything.
    The 4-byte prefix and the payload are concatenated and handed to the
    underlying socket's own `sendall` exactly once, so CPython's own
    fragmented-send handling is what is exercised here, never a hand-rolled
    retry loop.
    """
    if not isinstance(payload, bytes):
        raise ResearchError("Guest-agent RPC frame payload must be bytes.")
    if len(payload) == 0:
        raise GuestAgentRpcFramingError(GuestAgentRpcFramingFailureKind.ZERO_LENGTH)
    if len(payload) > max_frame_size:
        raise GuestAgentRpcFramingError(
            GuestAgentRpcFramingFailureKind.OVERSIZED_LENGTH
        )
    frame = _LENGTH_PREFIX_STRUCT.pack(len(payload)) + payload
    sock.sendall(frame)
