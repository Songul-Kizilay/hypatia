"""Replaceable persistence boundary for Guest-Agent replay nonce records."""

from __future__ import annotations

from typing import Protocol

from research.GuestAgentReplayNonceRecord import GuestAgentReplayNonceRecord


class GuestAgentReplayNonceStore(Protocol):
    """Load and atomically replace the complete consumed-replay record set."""

    def load(self) -> list[GuestAgentReplayNonceRecord]:
        """Return every persisted replay record, or an empty list when absent."""

    def save(self, records: list[GuestAgentReplayNonceRecord]) -> None:
        """Atomically replace the persisted replay record set."""
