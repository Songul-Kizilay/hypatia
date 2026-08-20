"""Read-only reconciliation of persisted evidence and restored paragraphs."""

from __future__ import annotations

import hashlib
import hmac

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.ResearchEvidenceIntegrityStatus import ResearchEvidenceIntegrityStatus
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchRun import ResearchRun

MAX_AUDITED_RESEARCH_EVIDENCE = 20_000
MAX_AUDITED_RESEARCH_CHUNKS = 20_000
MAX_AUDITED_RESEARCH_RUNS = 20_000


class ResearchEvidenceIntegrityAuditor:
    """Classify evidence against the current in-memory knowledge snapshot."""

    def __init__(self, knowledge_engine: KnowledgeEngine) -> None:
        if not isinstance(knowledge_engine, KnowledgeEngine):
            raise ResearchError(
                "Research evidence integrity requires a knowledge engine."
            )
        self._knowledge_engine = knowledge_engine

    def audit(self, runs: list[ResearchRun]) -> ResearchEvidenceIntegrityStatus:
        """Return bounded aggregate counts without persistence or mutation."""
        if not isinstance(runs, list):
            raise ResearchError("Research evidence integrity requires research runs.")
        if len(runs) > MAX_AUDITED_RESEARCH_RUNS:
            return ResearchEvidenceIntegrityStatus.unavailable()
        if not all(isinstance(run, ResearchRun) for run in runs):
            raise ResearchError("Research evidence integrity requires research runs.")
        evidence: list[ResearchEvidenceRecord] = []
        for run in runs:
            for record in run.evidence:
                if len(evidence) == MAX_AUDITED_RESEARCH_EVIDENCE:
                    return ResearchEvidenceIntegrityStatus.unavailable()
                evidence.append(record)
        locators = {
            (record.source_document_id, record.chunk_index) for record in evidence
        }
        if self._knowledge_engine.chunk_count() > MAX_AUDITED_RESEARCH_CHUNKS:
            return ResearchEvidenceIntegrityStatus.unavailable()
        chunks_by_locator: dict[tuple[str, int], Chunk] = {}
        for chunk in self._knowledge_engine.chunks():
            locator = (chunk.document_id, chunk.index)
            if locator not in locators:
                continue
            if locator in chunks_by_locator:
                return ResearchEvidenceIntegrityStatus.unavailable()
            chunks_by_locator[locator] = chunk

        matched = 0
        missing = 0
        changed = 0
        for record in evidence:
            classification = self._classify(record, chunks_by_locator)
            if classification == "matched":
                matched += 1
            elif classification == "missing":
                missing += 1
            else:
                changed += 1
        return ResearchEvidenceIntegrityStatus(
            available=True,
            recorded_evidence_count=len(evidence),
            matched_evidence_count=matched,
            missing_evidence_count=missing,
            changed_evidence_count=changed,
        )

    @staticmethod
    def _classify(
        record: ResearchEvidenceRecord,
        chunks_by_locator: dict[tuple[str, int], Chunk],
    ) -> str:
        chunk = chunks_by_locator.get((record.source_document_id, record.chunk_index))
        if chunk is None:
            return "missing"
        observed_sha256 = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
        if chunk.chunk_id == record.chunk_id and hmac.compare_digest(
            observed_sha256,
            record.chunk_sha256,
        ):
            return "matched"
        return "changed"
