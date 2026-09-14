"""Explicit authorization for one authored research claim.

Authorizes the exact evidence a claim rests on, the authored claim text, its
explicit epistemic state, its explicit categorical confidence, and an optional
superseded claim.

Epistemic state and confidence are authored, never inferred. No completed
operation, successful fetch, accepted source, or recorded assessment may set or
raise them. A claim reaching `fact` is always something a human declared, and
the categorical confidence never becomes a fabricated number.

The existing domain requires at least one evidence reference for every claim,
including a hypothesis or speculation. That exact rule is preserved here rather
than replaced with a looser one, so no claim can exist without evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState

MAX_CLAIM_AUTHORIZATION_TEXT_CHARACTERS = 2_000
MAX_CLAIM_AUTHORIZATION_EVIDENCE_IDS = 50


@dataclass(frozen=True, slots=True)
class ResearchClaimAuthorization:
    """One authored claim, its exact evidence, and its explicit epistemics."""

    evidence_ids: tuple[str, ...]
    text: str
    epistemic_state: ResearchEpistemicState
    confidence: ResearchClaimConfidence = ResearchClaimConfidence.UNASSESSED
    supersedes_claim_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_ids, tuple):
            raise ResearchError(
                "Claim authorization evidence IDs must be an immutable tuple."
            )
        if not self.evidence_ids:
            raise ResearchError(
                "Claim authorization requires at least one evidence ID."
            )
        if len(self.evidence_ids) > MAX_CLAIM_AUTHORIZATION_EVIDENCE_IDS:
            raise ResearchError("Claim authorization has too many evidence IDs.")
        if not all(
            isinstance(evidence_id, str) and evidence_id.strip()
            for evidence_id in self.evidence_ids
        ):
            raise ResearchError("Claim authorization evidence ID cannot be empty.")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ResearchError("Claim authorization text cannot be empty.")
        text = self.text.strip()
        if len(text) > MAX_CLAIM_AUTHORIZATION_TEXT_CHARACTERS:
            raise ResearchError("Claim authorization text is too long.")
        state = self._coerce(
            self.epistemic_state,
            ResearchEpistemicState,
            "Claim authorization epistemic state is invalid.",
        )
        confidence = self._coerce(
            self.confidence,
            ResearchClaimConfidence,
            "Claim authorization confidence is invalid.",
        )
        superseded = self.supersedes_claim_id
        if superseded is not None and (
            not isinstance(superseded, str) or not superseded.strip()
        ):
            raise ResearchError("Claim authorization superseded ID cannot be empty.")
        object.__setattr__(
            self,
            "evidence_ids",
            tuple(evidence_id.strip() for evidence_id in self.evidence_ids),
        )
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "epistemic_state", state)
        object.__setattr__(self, "confidence", confidence)
        if superseded is not None:
            object.__setattr__(self, "supersedes_claim_id", superseded.strip())

    @staticmethod
    def _coerce(value: object, enum_type: type, message: str) -> object:
        """Accept the exact enum or its exact declared value, nothing else."""
        if isinstance(value, enum_type):
            return value
        if isinstance(value, str):
            try:
                return enum_type(value)
            except ValueError as error:
                raise ResearchError(message) from error
        raise ResearchError(message)
