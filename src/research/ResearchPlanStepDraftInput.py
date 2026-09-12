"""Named immutable input describing one authored research-plan step.

Capability authorization used to arrive as a widening positional tuple, where
the fifth element's meaning was only knowable by counting. This structure names
each field instead, so adding a capability adds a named optional field rather
than another positional slot.

Legacy positional tuples remain accepted and are normalized into this structure,
so existing callers and the persisted plan domain are unaffected.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAssessmentAuthorization import ResearchAssessmentAuthorization
from research.ResearchClaimAuthorization import ResearchClaimAuthorization
from research.ResearchComparisonAuthorization import (
    ResearchComparisonAuthorization,
)
from research.ResearchCompletionAuthorization import (
    ResearchCompletionAuthorization,
)
from research.ResearchContradictionAuthorization import (
    ResearchContradictionAuthorization,
)
from research.ResearchEvidenceAuthorization import ResearchEvidenceAuthorization
from research.SemanticComparisonStepBinding import SemanticComparisonStepBinding
from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding

MAX_LEGACY_DRAFT_TUPLE_LENGTH = 6


@dataclass(frozen=True, slots=True)
class ResearchPlanStepDraftInput:
    """One authored step and its explicit capability authorizations."""

    instruction: str
    selected_source_document_ids: tuple[str, ...] = ()
    capability: str | None = None
    authorized_source_url: str = ""
    discovery_provider: str | None = None
    evidence_authorization: ResearchEvidenceAuthorization | None = None
    assessment_authorization: ResearchAssessmentAuthorization | None = None
    claim_authorization: ResearchClaimAuthorization | None = None
    contradiction_authorization: ResearchContradictionAuthorization | None = None
    comparison_authorization: ResearchComparisonAuthorization | None = None
    completion_authorization: ResearchCompletionAuthorization | None = None
    semantic_evidence_binding: SemanticEvidenceStepBinding | None = None
    semantic_comparison_binding: SemanticComparisonStepBinding | None = None

    @classmethod
    def from_value(cls, value: object) -> ResearchPlanStepDraftInput:
        """Accept this structure or a legacy positional tuple unchanged."""
        if isinstance(value, cls):
            return value
        if not isinstance(value, tuple) or not 2 <= len(value) <= (
            MAX_LEGACY_DRAFT_TUPLE_LENGTH
        ):
            raise ResearchError("Research plan draft step is invalid.")
        return cls(
            instruction=value[0],
            selected_source_document_ids=value[1],
            capability=value[2] if len(value) >= 3 else None,
            authorized_source_url=value[3] if len(value) >= 4 else "",
            evidence_authorization=cls._evidence(value[4] if len(value) >= 5 else None),
            assessment_authorization=cls._assessment(
                value[5] if len(value) >= 6 else None
            ),
        )

    @staticmethod
    def _evidence(value: object) -> ResearchEvidenceAuthorization | None:
        if value is None or isinstance(value, ResearchEvidenceAuthorization):
            return value
        if not isinstance(value, tuple) or len(value) != 3:
            raise ResearchError("Research plan evidence authorization is invalid.")
        document_id, chunk_index, note = value
        return ResearchEvidenceAuthorization(
            document_id=document_id,
            chunk_index=chunk_index,
            note=note,
        )

    @staticmethod
    def _assessment(value: object) -> ResearchAssessmentAuthorization | None:
        if value is None or isinstance(value, ResearchAssessmentAuthorization):
            return value
        if not isinstance(value, tuple) or len(value) != 4:
            raise ResearchError("Research plan assessment authorization is invalid.")
        document_id, evidence_ids, text, information_trust = value
        return ResearchAssessmentAuthorization(
            document_id=document_id,
            evidence_ids=evidence_ids,
            text=text,
            information_trust=information_trust,
        )
