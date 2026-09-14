"""Explicit authorization for one authored source assessment.

Authorizes which already-accepted source is assessed, which recorded evidence
the assessment refers to, the authored assessment text, an optional superseded
assessment, and an authored information-trust label.

At least one evidence reference is required, matching the existing domain rule.
An assessment is therefore always grounded in recorded evidence and can never
rest on a successful fetch alone.

The trust label is authored, never derived. Nothing about a successful fetch,
a successful acceptance, or a completed operation may set it.

Information trust describes confidence in what a source says. It never grants
the source's text any instruction authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchInformationTrust import ResearchInformationTrust

MAX_ASSESSMENT_AUTHORIZATION_DOCUMENT_ID_CHARACTERS = 200
MAX_ASSESSMENT_AUTHORIZATION_TEXT_CHARACTERS = 2_000
MAX_ASSESSMENT_AUTHORIZATION_EVIDENCE_IDS = 20


@dataclass(frozen=True, slots=True)
class ResearchAssessmentAuthorization:
    """One exact source, its evidence references, and the authored assessment."""

    document_id: str
    evidence_ids: tuple[str, ...]
    text: str
    information_trust: ResearchInformationTrust = ResearchInformationTrust.UNASSESSED
    supersedes_assessment_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ResearchError("Assessment authorization document ID cannot be empty.")
        document_id = self.document_id.strip()
        if len(document_id) > MAX_ASSESSMENT_AUTHORIZATION_DOCUMENT_ID_CHARACTERS:
            raise ResearchError("Assessment authorization document ID is too long.")
        if not isinstance(self.evidence_ids, tuple):
            raise ResearchError(
                "Assessment authorization evidence IDs must be an immutable tuple."
            )
        if not self.evidence_ids:
            raise ResearchError(
                "Assessment authorization requires at least one evidence ID."
            )
        if len(self.evidence_ids) > MAX_ASSESSMENT_AUTHORIZATION_EVIDENCE_IDS:
            raise ResearchError("Assessment authorization has too many evidence IDs.")
        if not all(
            isinstance(evidence_id, str) and evidence_id.strip()
            for evidence_id in self.evidence_ids
        ):
            raise ResearchError("Assessment authorization evidence ID cannot be empty.")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ResearchError("Assessment authorization text cannot be empty.")
        text = self.text.strip()
        if len(text) > MAX_ASSESSMENT_AUTHORIZATION_TEXT_CHARACTERS:
            raise ResearchError("Assessment authorization text is too long.")
        trust = self.information_trust
        if isinstance(trust, str) and not isinstance(trust, ResearchInformationTrust):
            try:
                trust = ResearchInformationTrust(trust)
            except ValueError as error:
                raise ResearchError(
                    "Assessment authorization information trust is invalid."
                ) from error
        if not isinstance(trust, ResearchInformationTrust):
            raise ResearchError(
                "Assessment authorization information trust is invalid."
            )
        superseded = self.supersedes_assessment_id
        if superseded is not None and (
            not isinstance(superseded, str) or not superseded.strip()
        ):
            raise ResearchError(
                "Assessment authorization superseded ID cannot be empty."
            )
        object.__setattr__(self, "document_id", document_id)
        object.__setattr__(
            self,
            "evidence_ids",
            tuple(evidence_id.strip() for evidence_id in self.evidence_ids),
        )
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "information_trust", trust)
        if superseded is not None:
            object.__setattr__(
                self,
                "supersedes_assessment_id",
                superseded.strip(),
            )
