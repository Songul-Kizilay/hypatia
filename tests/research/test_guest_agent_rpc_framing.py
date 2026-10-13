"""Pure, no-real-socket tests for the Guest-Agent RPC length-prefixed framing.

FRAME DELIVERY != EXECUTION AUTHORITY. Every test here exercises
`research.GuestAgentRpcFraming` against a trivial fake object implementing
only the narrow `recv`/`sendall` surface `GuestAgentRpcFramingSocket`
describes -- no real socket, no TLS, no network, anywhere in this file.
"""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError  # noqa: E402
from research.GuestAgentRpcFraming import (  # noqa: E402
    LENGTH_PREFIX_SIZE,
    MAX_GUEST_AGENT_RPC_FRAME_SIZE,
    GuestAgentRpcFramingError,
    GuestAgentRpcFramingFailureKind,
    read_guest_agent_rpc_frame,
    write_guest_agent_rpc_frame,
)


class _ScriptedSocket:
    """A fake `recv`/`sendall` surface backed by a plain byte buffer.

    `recv(n)` returns up to `n` bytes from the front of the buffer (or up
    to `max_chunk_size`, when set, to simulate fragmentation one call at a
    time) -- never more than a real socket would ever return. When the
    buffer is exhausted, `recv` returns `b""` (simulating an orderly peer
    close) unless `raise_if_exhausted` is set, in which case a further call
    raises `AssertionError` -- used to prove a code path never issues that
    call at all (e.g. the body must never be read after an oversized
    declared length is rejected).
    """

    def __init__(
        self,
        data: bytes = b"",
        *,
        max_chunk_size: int | None = None,
        raise_if_exhausted: bool = False,
    ) -> None:
        self._buffer = data
        self._max_chunk_size = max_chunk_size
        self._raise_if_exhausted = raise_if_exhausted
        self.recv_calls: list[int] = []
        self.sendall_calls: list[bytes] = []

    def recv(self, n: int) -> bytes:
        self.recv_calls.append(n)
        if not self._buffer:
            if self._raise_if_exhausted:
                raise AssertionError("recv() must not be called again")
            return b""
        take = n if self._max_chunk_size is None else min(n, self._max_chunk_size)
        chunk = self._buffer[:take]
        self._buffer = self._buffer[take:]
        return chunk

    def sendall(self, data: bytes) -> None:
        self.sendall_calls.append(data)

    @property
    def remaining_buffer(self) -> bytes:
        return self._buffer


def _prefix(length: int) -> bytes:
    return struct.pack(">I", length)


class RoundTripTests(unittest.TestCase):
    def test_write_then_read_round_trips_exact_payload(self) -> None:
        sock = _ScriptedSocket()
        payload = b"hello guest agent rpc frame"
        write_guest_agent_rpc_frame(sock, payload)
        self.assertEqual(len(sock.sendall_calls), 1)
        reader = _ScriptedSocket(sock.sendall_calls[0])
        result = read_guest_agent_rpc_frame(reader)
        self.assertEqual(result, payload)

    def test_length_prefix_uses_fixed_four_byte_big_endian_order(self) -> None:
        """Deterministic byte order: `struct.pack`/`unpack` symmetry."""
        sock = _ScriptedSocket()
        payload = b"x" * 10
        write_guest_agent_rpc_frame(sock, payload)
        frame = sock.sendall_calls[0]
        self.assertEqual(len(frame), LENGTH_PREFIX_SIZE + len(payload))
        (declared_length,) = struct.unpack(">I", frame[:LENGTH_PREFIX_SIZE])
        self.assertEqual(declared_length, len(payload))
        self.assertEqual(frame[:LENGTH_PREFIX_SIZE], struct.pack(">I", len(payload)))

    def test_write_uses_exactly_one_sendall_call(self) -> None:
        sock = _ScriptedSocket()
        write_guest_agent_rpc_frame(sock, b"payload bytes")
        self.assertEqual(len(sock.sendall_calls), 1)

    def test_two_sequential_frames_each_read_correctly(self) -> None:
        """Framing itself supports reading more than one frame in sequence
        when a caller chooses to call it twice -- the one-shot session
        constraint belongs to the transport server, not to framing."""
        sock = _ScriptedSocket()
        write_guest_agent_rpc_frame(sock, b"first")
        write_guest_agent_rpc_frame(sock, b"second")
        combined = b"".join(sock.sendall_calls)
        reader = _ScriptedSocket(combined)
        self.assertEqual(read_guest_agent_rpc_frame(reader), b"first")
        self.assertEqual(read_guest_agent_rpc_frame(reader), b"second")


class WriteValidationTests(unittest.TestCase):
    def test_zero_length_payload_is_rejected(self) -> None:
        sock = _ScriptedSocket()
        with self.assertRaises(GuestAgentRpcFramingError) as ctx:
            write_guest_agent_rpc_frame(sock, b"")
        self.assertEqual(
            ctx.exception.kind, GuestAgentRpcFramingFailureKind.ZERO_LENGTH
        )
        self.assertEqual(sock.sendall_calls, [])

    def test_oversized_payload_is_rejected_before_any_send(self) -> None:
        sock = _ScriptedSocket()
        oversized = b"a" * (MAX_GUEST_AGENT_RPC_FRAME_SIZE + 1)
        with self.assertRaises(GuestAgentRpcFramingError) as ctx:
            write_guest_agent_rpc_frame(sock, oversized)
        self.assertEqual(
            ctx.exception.kind, GuestAgentRpcFramingFailureKind.OVERSIZED_LENGTH
        )
        self.assertEqual(sock.sendall_calls, [])

    def test_non_bytes_payload_is_rejected(self) -> None:
        sock = _ScriptedSocket()
        with self.assertRaises(ResearchError):
            write_guest_agent_rpc_frame(sock, "not bytes")  # type: ignore[arg-type]
        self.assertEqual(sock.sendall_calls, [])


class ReadAdversarialTests(unittest.TestCase):
    def test_declared_zero_length_is_rejected(self) -> None:
        sock = _ScriptedSocket(_prefix(0), raise_if_exhausted=True)
        with self.assertRaises(GuestAgentRpcFramingError) as ctx:
            read_guest_agent_rpc_frame(sock)
        self.assertEqual(
            ctx.exception.kind, GuestAgentRpcFramingFailureKind.ZERO_LENGTH
        )

    def test_declared_length_exceeding_max_is_rejected_before_body_read(self) -> None:
        """The body must never be read when the declared length exceeds the
        bound -- `raise_if_exhausted=True` turns any further `recv()` call
        into an immediate test failure, proving the body read never
        happens."""
        sock = _ScriptedSocket(
            _prefix(MAX_GUEST_AGENT_RPC_FRAME_SIZE + 1), raise_if_exhausted=True
        )
        with self.assertRaises(GuestAgentRpcFramingError) as ctx:
            read_guest_agent_rpc_frame(sock)
        self.assertEqual(
            ctx.exception.kind, GuestAgentRpcFramingFailureKind.OVERSIZED_LENGTH
        )
        self.assertEqual(len(sock.recv_calls), 1)

    def test_declared_length_0xffffffff_is_rejected_before_body_read(self) -> None:
        sock = _ScriptedSocket(_prefix(0xFFFFFFFF), raise_if_exhausted=True)
        with self.assertRaises(GuestAgentRpcFramingError) as ctx:
            read_guest_agent_rpc_frame(sock)
        self.assertEqual(
            ctx.exception.kind, GuestAgentRpcFramingFailureKind.OVERSIZED_LENGTH
        )
        self.assertEqual(len(sock.recv_calls), 1)

    def test_truncated_length_prefix_is_rejected(self) -> None:
        sock = _ScriptedSocket(b"\x00\x01")
        with self.assertRaises(GuestAgentRpcFramingError) as ctx:
            read_guest_agent_rpc_frame(sock)
        self.assertEqual(
            ctx.exception.kind, GuestAgentRpcFramingFailureKind.TRUNCATED_PREFIX
        )

    def test_empty_stream_is_a_truncated_prefix(self) -> None:
        sock = _ScriptedSocket(b"")
        with self.assertRaises(GuestAgentRpcFramingError) as ctx:
            read_guest_agent_rpc_frame(sock)
        self.assertEqual(
            ctx.exception.kind, GuestAgentRpcFramingFailureKind.TRUNCATED_PREFIX
        )

    def test_truncated_frame_body_is_rejected(self) -> None:
        sock = _ScriptedSocket(_prefix(10) + b"abc")
        with self.assertRaises(GuestAgentRpcFramingError) as ctx:
            read_guest_agent_rpc_frame(sock)
        self.assertEqual(
            ctx.exception.kind, GuestAgentRpcFramingFailureKind.TRUNCATED_BODY
        )

    def test_early_eof_with_no_body_bytes_at_all_is_truncated_body(self) -> None:
        sock = _ScriptedSocket(_prefix(5))
        with self.assertRaises(GuestAgentRpcFramingError) as ctx:
            read_guest_agent_rpc_frame(sock)
        self.assertEqual(
            ctx.exception.kind, GuestAgentRpcFramingFailureKind.TRUNCATED_BODY
        )

    def test_one_byte_at_a_time_fragmented_prefix_is_reassembled(self) -> None:
        payload = b"abcde"
        sock = _ScriptedSocket(_prefix(len(payload)) + payload, max_chunk_size=1)
        result = read_guest_agent_rpc_frame(sock)
        self.assertEqual(result, payload)
        # Every recv() call returned at most one byte -- proves the loop
        # genuinely accumulated across many small reads rather than relying
        # on one call returning everything.
        self.assertTrue(all(call >= 1 for call in sock.recv_calls))
        self.assertGreaterEqual(len(sock.recv_calls), len(payload) + LENGTH_PREFIX_SIZE)

    def test_one_byte_at_a_time_fragmented_payload_is_reassembled(self) -> None:
        payload = b"0123456789"
        sock = _ScriptedSocket(_prefix(len(payload)) + payload, max_chunk_size=1)
        result = read_guest_agent_rpc_frame(sock)
        self.assertEqual(result, payload)

    def test_valid_frame_followed_by_junk_is_never_folded_into_the_message(
        self,
    ) -> None:
        payload = b"the real message"
        junk = b"JUNK-BYTES-NOT-PART-OF-ANY-FRAME"
        sock = _ScriptedSocket(_prefix(len(payload)) + payload + junk)
        result = read_guest_agent_rpc_frame(sock)
        self.assertEqual(result, payload)
        self.assertEqual(sock.remaining_buffer, junk)

    def test_two_concatenated_frames_only_first_consumed_by_one_read(self) -> None:
        first = b"first-frame"
        second = b"second-frame"
        combined = _prefix(len(first)) + first + _prefix(len(second)) + second
        sock = _ScriptedSocket(combined)
        result = read_guest_agent_rpc_frame(sock)
        self.assertEqual(result, first)
        self.assertEqual(sock.remaining_buffer, _prefix(len(second)) + second)

    def test_oversized_frame_size_override_is_honored(self) -> None:
        """A caller-supplied `max_frame_size` is the bound actually enforced,
        not the module default, proving the parameter is load-bearing."""
        sock = _ScriptedSocket(_prefix(100), raise_if_exhausted=True)
        with self.assertRaises(GuestAgentRpcFramingError) as ctx:
            read_guest_agent_rpc_frame(sock, max_frame_size=50)
        self.assertEqual(
            ctx.exception.kind, GuestAgentRpcFramingFailureKind.OVERSIZED_LENGTH
        )

    def test_frame_exactly_at_the_maximum_size_is_accepted(self) -> None:
        payload = b"z" * 20
        sock = _ScriptedSocket(_prefix(len(payload)) + payload)
        result = read_guest_agent_rpc_frame(sock, max_frame_size=len(payload))
        self.assertEqual(result, payload)


class ErrorHygieneTests(unittest.TestCase):
    def test_framing_error_messages_are_fixed_and_never_embed_payload_bytes(
        self,
    ) -> None:
        hostile_marker = "HOSTILE-MARKER-STRING-SHOULD-NEVER-APPEAR"
        sock = _ScriptedSocket(_prefix(10) + hostile_marker.encode("ascii")[:3])
        with self.assertRaises(GuestAgentRpcFramingError) as ctx:
            read_guest_agent_rpc_frame(sock)
        message = str(ctx.exception)
        self.assertNotIn(hostile_marker, message)
        self.assertLessEqual(len(message), 200)


class MaxFrameSizeDerivationTests(unittest.TestCase):
    def test_max_frame_size_is_in_the_few_hundred_kib_range(self) -> None:
        self.assertEqual(MAX_GUEST_AGENT_RPC_FRAME_SIZE, 512 * 1024)
        self.assertGreater(MAX_GUEST_AGENT_RPC_FRAME_SIZE, 300_000)
        self.assertLess(MAX_GUEST_AGENT_RPC_FRAME_SIZE, 2_000_000)

    def test_max_frame_size_exceeds_the_real_worst_case_request_bytes(
        self,
    ) -> None:
        """Builds the real worst-case `GuestAgentRequest` the existing
        protocol bounds allow and confirms the real canonical encoder's
        output fits comfortably under the ceiling -- not a guessed number."""
        from research.GuestAgentProtocol import (
            MAX_LOGICAL_INPUT_FIELD_NAME_LENGTH,
            MAX_LOGICAL_INPUT_FIELDS,
            MAX_LOGICAL_INPUT_VALUE_LENGTH,
            MAX_NONCE_LENGTH,
            MAX_REQUEST_ID_LENGTH,
            GuestAgentProtocolVersion,
            GuestAgentRequest,
        )
        from research.GuestAgentProtocolSerialization import (
            canonical_guest_agent_request_bytes,
        )
        from research.ResearchKaliOperationPreview import ResearchKaliOperationKind

        astral = "\U0001f600"
        logical_inputs = []
        for index in range(MAX_LOGICAL_INPUT_FIELDS):
            name = str(index)[-1] + astral * (MAX_LOGICAL_INPUT_FIELD_NAME_LENGTH - 1)
            value = astral * MAX_LOGICAL_INPUT_VALUE_LENGTH
            logical_inputs.append((name, value))
        request = GuestAgentRequest(
            protocol_version=GuestAgentProtocolVersion.V1,
            request_id=astral * MAX_REQUEST_ID_LENGTH,
            nonce=astral * MAX_NONCE_LENGTH,
            operation_kind=ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP,
            operation_digest="a" * 64,
            logical_inputs=tuple(logical_inputs),
        )
        worst_case_bytes = canonical_guest_agent_request_bytes(request)
        self.assertLess(len(worst_case_bytes), MAX_GUEST_AGENT_RPC_FRAME_SIZE)
        # Document the measured figure stays in the range the module
        # docstring claims, so a future protocol bound change that silently
        # busts this ceiling is caught here, not merely asserted in prose.
        self.assertGreater(len(worst_case_bytes), 400_000)


if __name__ == "__main__":
    unittest.main()
