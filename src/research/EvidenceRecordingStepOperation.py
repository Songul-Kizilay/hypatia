"""Explicit evidence recording for one research-plan step.

Records one evidence entry from content that is already accepted on the bound
run, using the existing `ResearchRunManager.add_evidence` path. No second
evidence domain exists.

Evidence text is never supplied by a caller. The operation resolves a real
`Chunk` from the knowledge engine by exact document ID and chunk index, and the
existing evidence domain computes the excerpt, chunk identity, and hash from
that chunk. A caller may authorize *which* chunk and *what a human noted about
it*, never the excerpt itself, so evidence cannot be fabricated and no language
model is involved.

The run manager independently requires the chunk's document to belong to a
source already accepted on the run. A fetched-but-unaccepted source therefore
cannot produce evidence.

Recording evidence establishes evidence only. It performs no assessment, forms
no claim, elevates no epistemic state, and makes no source trustworthy.
"""

from __future__ import annotations

from hashlib import sha256

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager

_EVIDENCE_BOUNDARY = (
    "Evidence recorded only: not an assessment, not a claim, not a verified "
    "fact, and not a statement that the source is trustworthy."
)


class EvidenceRecordingStepOperation:
    """Record one authorized evidence entry from an accepted source chunk."""

    def __init__(
        self,
        knowledge_engine: KnowledgeEngine,
        research_run_manager: ResearchRunManager,
    ) -> None:
        self._knowledge_engine = knowledge_engine
        self._research_run_manager = research_run_manager

    @property
    def operation_name(self) -> str:
        return "evidence_recording"

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Record the one authorized evidence entry, or fail honestly."""
        authorization = step.evidence_authorization
        if authorization is None:
            raise ResearchError(
                "Evidence recording requires an explicit evidence authorization."
            )
        run_id = context.research_run_id
        if run_id is None:
            raise ResearchError("Evidence recording requires a bound research run.")
        run = self._research_run_manager.get(run_id)
        if run.status.terminal:
            raise ResearchError(
                "Research run is closed and cannot record new evidence."
            )
        self._raise_if_cancelled(context)

        chunk = self._resolve_chunk(
            authorization.document_id,
            authorization.chunk_index,
        )
        if context.source_preview is not None:
            preview = context.source_preview
            if (
                preview.run_id != run_id
                or preview.execution_id != context.execution_id
                or preview.source.to_document().document_id != chunk.document_id
                or chunk.content not in preview.source.content
                or sha256(chunk.content.encode("utf-8")).hexdigest()
                != context.evidence_chunk_sha256
            ):
                raise ResearchError("Evidence candidate changed or is not grounded.")
        self._raise_if_cancelled(context)

        updated = self._research_run_manager.add_evidence(
            run_id,
            chunk,
            authorization.note,
        )
        recorded = updated.evidence[-1]
        truncated = " (excerpt truncated)" if recorded.excerpt_truncated else ""
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=(
                f"Recorded evidence {recorded.evidence_id} for run {run_id} from "
                f"document {recorded.source_document_id} chunk "
                f"{recorded.chunk_index}{truncated}. {_EVIDENCE_BOUNDARY}"
            ),
        )

    def _resolve_chunk(self, document_id: str, chunk_index: int) -> Chunk:
        """Find the one exact indexed chunk, or refuse to guess."""
        for chunk in self._knowledge_engine.chunks():
            if chunk.document_id == document_id and chunk.index == chunk_index:
                return chunk
        raise ResearchError(
            "Authorized evidence chunk was not found in local knowledge."
        )

    @staticmethod
    def _raise_if_cancelled(context: ResearchPlanExecutionContext) -> None:
        if context.cancelled:
            raise ResearchError("Evidence recording was cancelled.")
