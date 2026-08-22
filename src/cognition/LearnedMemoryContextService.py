"""Bounded learned-memory context selection for the conversation path."""

from __future__ import annotations

from collections.abc import Callable

from core.Exceptions import MemoryError
from memory.HybridSemanticMemoryRanker import HybridSemanticMemoryRanker
from memory.LearnedMemory import LearnedMemory, LearnedMemoryKind
from memory.LearnedMemoryCodec import decode_learned_memory
from memory.LearnedMemoryContext import (
    build_learned_memory_context,
    load_bounded_learned_memory_context,
    load_current_selected_bounded_learned_memory_context,
    load_current_selected_learned_memory_context,
    load_learned_memory_context,
)
from memory.LearnedMemoryRetrieval import select_latest_learned_memories
from memory.LearnedMemorySelector import LearnedMemorySelector
from memory.LearnedMemoryStore import load_learned_memories
from memory.MemoryManager import MemoryManager
from memory.MemoryRecord import MemoryRecord
from memory.SemanticMemoryIndexRuntime import SemanticMemoryIndexRuntime
from memory.SemanticMemoryMatch import SemanticMemoryMatch

DEFAULT_CHAT_SEMANTIC_CONTEXT_LIMIT = 8
DEFAULT_CHAT_SEMANTIC_QUERY_LIMIT = 16


class LearnedMemoryContextService:
    """Compose one bounded learned-memory context for a single user turn.

    With semantic chat retrieval disabled the service delegates to the existing
    deterministic loaders unchanged. With it enabled the service performs at most
    one semantic query per turn, fuses those candidates with the deterministic
    selection, and falls back to the deterministic result whenever the semantic
    runtime is unavailable or fails.
    """

    def __init__(
        self,
        *,
        selector: LearnedMemorySelector | None = None,
        context_limit: int | None = None,
        semantic_runtime: SemanticMemoryIndexRuntime | None = None,
        semantic_query_limit: int = DEFAULT_CHAT_SEMANTIC_QUERY_LIMIT,
        hybrid_ranker: HybridSemanticMemoryRanker | None = None,
        on_semantic_failure: Callable[[str], None] | None = None,
    ) -> None:
        if (
            isinstance(semantic_query_limit, bool)
            or not isinstance(semantic_query_limit, int)
            or semantic_query_limit < 1
        ):
            raise ValueError("Chat semantic query limit must be a positive integer.")
        self._selector = selector
        self._context_limit = context_limit
        self._semantic_runtime = semantic_runtime
        self._semantic_query_limit = semantic_query_limit
        self._hybrid_ranker = hybrid_ranker or HybridSemanticMemoryRanker()
        self._on_semantic_failure = on_semantic_failure

    @property
    def semantic_enabled(self) -> bool:
        """Report whether this turn may issue one semantic query."""
        return self._semantic_runtime is not None

    def build(self, memory_manager: MemoryManager, source_text: str) -> str:
        """Return the bounded learned-memory context for one user message."""
        if self._semantic_runtime is None:
            return self._build_deterministic(memory_manager, source_text)
        return self._build_semantic_hybrid(memory_manager, source_text)

    def _build_deterministic(
        self,
        memory_manager: MemoryManager,
        source_text: str,
    ) -> str:
        """Preserve the exact pre-existing selection behavior."""
        if self._selector is not None:
            if self._context_limit is None:
                return load_current_selected_learned_memory_context(
                    memory_manager=memory_manager,
                    source_text=source_text,
                    selector=self._selector,
                )
            return load_current_selected_bounded_learned_memory_context(
                memory_manager=memory_manager,
                source_text=source_text,
                selector=self._selector,
                limit=self._context_limit,
            )
        if self._context_limit is None:
            return load_learned_memory_context(memory_manager)
        return load_bounded_learned_memory_context(
            memory_manager,
            self._context_limit,
        )

    def _build_semantic_hybrid(
        self,
        memory_manager: MemoryManager,
        source_text: str,
    ) -> str:
        """Fuse one bounded semantic query with the deterministic selection."""
        semantic_matches = self._semantic_matches(source_text)
        if not semantic_matches:
            return self._build_deterministic(memory_manager, source_text)

        memories = load_learned_memories(memory_manager)
        latest_memories = select_latest_learned_memories(memories)
        current_by_identity: dict[tuple[LearnedMemoryKind, str], LearnedMemory] = {
            (memory.kind, memory.key): memory for memory in latest_memories
        }
        selected_memories = (
            self._selector.select(
                source_text=source_text,
                memories=latest_memories,
            )
            if self._selector is not None
            else latest_memories
        )
        lexical_records = self._current_records_for(
            memory_manager,
            selected_memories,
            current_by_identity,
        )
        ranked_matches = self._hybrid_ranker.rank(
            semantic_matches,
            lexical_records,
        )

        fused: list[LearnedMemory] = []
        seen: set[tuple[LearnedMemoryKind, str]] = set()
        for match in ranked_matches:
            memory = self._current_learned_memory(
                memory_manager,
                match.memory_id,
                current_by_identity,
            )
            if memory is None:
                continue
            identity = (memory.kind, memory.key)
            if identity in seen:
                continue
            seen.add(identity)
            fused.append(memory)

        return build_learned_memory_context(tuple(fused[: self._resolved_limit()]))

    def _semantic_matches(
        self,
        source_text: str,
    ) -> tuple[SemanticMemoryMatch, ...]:
        """Issue at most one semantic query and never fail the conversation."""
        runtime = self._semantic_runtime
        if runtime is None:
            return ()
        try:
            return runtime.search(source_text, limit=self._semantic_query_limit)
        except (MemoryError, OSError, ValueError) as error:
            if self._on_semantic_failure is not None:
                self._on_semantic_failure(type(error).__name__)
            return ()

    @staticmethod
    def _current_records_for(
        memory_manager: MemoryManager,
        memories: tuple[LearnedMemory, ...],
        current_by_identity: dict[tuple[LearnedMemoryKind, str], LearnedMemory],
    ) -> tuple[MemoryRecord, ...]:
        """Resolve selected learned memories back to their current records."""
        wanted = {(memory.kind, memory.key) for memory in memories}
        records: list[MemoryRecord] = []
        for record in memory_manager.all():
            decoded = decode_learned_memory(record)
            if decoded is None:
                continue
            identity = (decoded.kind, decoded.key)
            if identity not in wanted:
                continue
            if current_by_identity.get(identity) != decoded:
                continue
            records.append(record)
        return tuple(records)

    @staticmethod
    def _current_learned_memory(
        memory_manager: MemoryManager,
        memory_id: str,
        current_by_identity: dict[tuple[LearnedMemoryKind, str], LearnedMemory],
    ) -> LearnedMemory | None:
        """Reject superseded records so corrections are never resurrected."""
        record = memory_manager.get(memory_id)
        if record is None:
            return None
        decoded = decode_learned_memory(record)
        if decoded is None:
            return None
        if current_by_identity.get((decoded.kind, decoded.key)) != decoded:
            return None
        return decoded

    def _resolved_limit(self) -> int:
        if self._context_limit is None:
            return DEFAULT_CHAT_SEMANTIC_CONTEXT_LIMIT
        return self._context_limit
