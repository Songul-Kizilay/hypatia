"""Replaceable boundary for non-persistent contradiction proposals."""

from __future__ import annotations

from typing import Protocol

from research.ResearchClaimContradictionCandidate import (
    ResearchClaimContradictionCandidate,
)
from research.ResearchClaimRecord import ResearchClaimRecord


class ResearchClaimContradictionProposalError(Exception):
    """Raised when a proposal provider cannot return a valid bounded result."""


class ResearchClaimContradictionProposalProvider(Protocol):
    """Suggest review candidates without writing research state."""

    @property
    def provider_name(self) -> str:
        """Return a stable display identity for this proposal boundary."""
        ...

    def propose(
        self,
        question: str,
        claims: tuple[ResearchClaimRecord, ...],
        *,
        limit: int,
    ) -> list[ResearchClaimContradictionCandidate]:
        """Return at most ``limit`` ordered candidates for explicit review."""
        ...
