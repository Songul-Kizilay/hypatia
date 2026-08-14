"""Pure reciprocal-rank fusion for evaluating semantic and lexical recall."""

from __future__ import annotations

from collections.abc import Iterable

from memory.HybridSemanticMemoryMatch import HybridSemanticMemoryMatch
from memory.MemoryRecord import MemoryRecord
from memory.SemanticMemoryMatch import SemanticMemoryMatch


class HybridSemanticMemoryRanker:
    """Fuse ordered semantic and lexical candidates without runtime side effects."""

    def __init__(self, rank_constant: int = 60) -> None:
        if (
            isinstance(rank_constant, bool)
            or not isinstance(rank_constant, int)
            or rank_constant < 1
        ):
            raise ValueError("Hybrid rank constant must be a positive integer.")
        self._rank_constant = rank_constant

    def rank(
        self,
        semantic_matches: tuple[SemanticMemoryMatch, ...],
        lexical_records: tuple[MemoryRecord, ...],
        *,
        limit: int | None = None,
    ) -> tuple[HybridSemanticMemoryMatch, ...]:
        """Return deterministic reciprocal-rank fusion without duplicate IDs."""
        self._validate_limit(limit)
        if limit == 0:
            return ()

        scores: dict[str, float] = {}
        self._add_ranked_scores(
            scores,
            (match.memory_id for match in semantic_matches),
        )
        self._add_ranked_scores(
            scores,
            (record.memory_id for record in lexical_records),
        )
        ranked = tuple(
            HybridSemanticMemoryMatch(memory_id=memory_id, score=score)
            for memory_id, score in sorted(
                scores.items(),
                key=lambda item: (-item[1], item[0]),
            )
        )
        return ranked if limit is None else ranked[:limit]

    def _add_ranked_scores(
        self,
        scores: dict[str, float],
        memory_ids: Iterable[str],
    ) -> None:
        for position, memory_id in enumerate(memory_ids, start=1):
            scores[memory_id] = scores.get(memory_id, 0.0) + 1.0 / (
                self._rank_constant + position
            )

    @staticmethod
    def _validate_limit(limit: int | None) -> None:
        if limit is None:
            return
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError(
                "Hybrid memory ranking limit must be a non-negative integer."
            )
