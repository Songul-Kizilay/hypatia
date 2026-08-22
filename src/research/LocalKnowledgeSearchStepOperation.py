"""Real local-knowledge research operation for one authored plan step.

Stage 3 of research-plan execution connects exactly one existing research
capability: the deterministic local knowledge search. It reads the already
loaded local knowledge base and performs no network request, no LLM call, no
source fetch, and no persistence write.

The reported detail states only what the search actually found, including a
zero-result search, so a step never implies evidence that was not located.
"""

from __future__ import annotations

from knowledge.KnowledgeEngine import KnowledgeEngine
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult

MAX_REPORTED_KNOWLEDGE_DOCUMENTS = 3


class LocalKnowledgeSearchStepOperation:
    """Search the local knowledge base for one authored step instruction."""

    def __init__(self, knowledge_engine: KnowledgeEngine) -> None:
        self._knowledge_engine = knowledge_engine

    @property
    def operation_name(self) -> str:
        return "local_knowledge_search"

    def run(self, step: ResearchPlanStep) -> ResearchPlanStepOperationResult:
        """Run one bounded local search and report its exact outcome."""
        chunks = self._knowledge_engine.search(step.instruction)
        document_ids = tuple(dict.fromkeys(chunk.document_id for chunk in chunks))
        reported = document_ids[:MAX_REPORTED_KNOWLEDGE_DOCUMENTS]
        summary = (
            f"Local knowledge search matched {len(chunks)} chunk(s) "
            f"across {len(document_ids)} document(s)."
        )
        if reported:
            listed = ", ".join(reported)
            remaining = len(document_ids) - len(reported)
            suffix = f" (+{remaining} more)" if remaining > 0 else ""
            summary = f"{summary} Documents: {listed}{suffix}."
        else:
            summary = f"{summary} No local knowledge matched this instruction."
        return ResearchPlanStepOperationResult(performed=True, detail=summary)
