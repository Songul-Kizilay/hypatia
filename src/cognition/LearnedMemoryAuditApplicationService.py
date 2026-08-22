"""Explicit Brain-facing boundary for the read-only learned-memory audit."""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from memory.LearnedMemoryAuditor import audit_learned_memory_records
from memory.MemoryManager import MemoryManager
from response.ResponseComposer import ResponseComposer

LEARNED_MEMORY_AUDIT_INTENT = "learned_memory_audit"


class LearnedMemoryAuditApplicationService:
    """Compose one bounded audit without mutating, deleting, or merging."""

    def __init__(
        self,
        memory_manager: MemoryManager,
        response_composer: ResponseComposer,
    ) -> None:
        self._memory_manager = memory_manager
        self._response_composer = response_composer

    @staticmethod
    def is_audit_request(request: BrainRequest) -> bool:
        """Recognize only the explicit structured audit intent."""
        return request.metadata.get("intent") == LEARNED_MEMORY_AUDIT_INTENT

    def process_audit(self, request: BrainRequest) -> BrainResponse:
        """Read current records once and render the bounded report."""
        report = audit_learned_memory_records(tuple(self._memory_manager.all()))
        return self._response_composer.learned_memory_audit(request, report)
