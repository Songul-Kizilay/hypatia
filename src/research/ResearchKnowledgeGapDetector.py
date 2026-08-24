"""Derive bounded knowledge gaps from what a research run already recorded.

Detection is pure reading. It performs no network call, no model call, and no
mutation, and it never invents a fact: every gap points at a claim, a source, or
the run itself that is already persisted.

The detector deliberately reports absence rather than falsehood. An unassessed
source is not a bad source, and an unresolved claim is not a wrong claim; both
simply mean the record is thinner than it could be.
"""

from __future__ import annotations

from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchKnowledgeGap import MAX_GAP_SUMMARY_LENGTH, ResearchKnowledgeGap
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchRun import ResearchRun
from research.SourceIdentity import identity_of

MAX_GAPS_PER_RUN = 50
RUN_SUBJECT = ""

UNRESOLVED_STATES = frozenset(
    (
        ResearchEpistemicState.HYPOTHESIS,
        ResearchEpistemicState.SPECULATION,
        ResearchEpistemicState.UNKNOWN,
    )
)
SETTLED_STATES = frozenset(
    (
        ResearchEpistemicState.FACT,
        ResearchEpistemicState.STRONG_EVIDENCE,
        ResearchEpistemicState.LIKELY,
    )
)


class ResearchKnowledgeGapDetector:
    """Read one research run and report where its own record is incomplete."""

    def __init__(self, max_gaps: int = MAX_GAPS_PER_RUN) -> None:
        if isinstance(max_gaps, bool) or not isinstance(max_gaps, int):
            raise ValueError("Knowledge gap limit must be a whole number.")
        if max_gaps < 1 or max_gaps > MAX_GAPS_PER_RUN:
            raise ValueError("Knowledge gap limit is out of range.")
        self._max_gaps = max_gaps

    def detect(
        self,
        run: ResearchRun,
        detected_at: datetime,
    ) -> tuple[ResearchKnowledgeGap, ...]:
        """Return the highest-severity gaps this run exposes, bounded in count."""
        if not isinstance(run, ResearchRun):
            raise ResearchError("Knowledge gap detection requires a research run.")
        gaps = [
            *self._question_gaps(run, detected_at),
            *self._claim_gaps(run, detected_at),
            *self._source_gaps(run, detected_at),
        ]
        gaps.sort(key=lambda gap: (-gap.severity, gap.kind.value, gap.subject_id))
        return tuple(gaps[: self._max_gaps])

    def _question_gaps(
        self,
        run: ResearchRun,
        detected_at: datetime,
    ) -> list[ResearchKnowledgeGap]:
        if run.sources:
            return []
        return [
            self._gap(
                run,
                ResearchKnowledgeGapKind.UNSUPPORTED_QUESTION,
                RUN_SUBJECT,
                "This run accepted no sources, so nothing supports its question.",
                detected_at,
            )
        ]

    def _claim_gaps(
        self,
        run: ResearchRun,
        detected_at: datetime,
    ) -> list[ResearchKnowledgeGap]:
        contradicted = {
            claim_id
            for record in run.claim_contradictions
            for claim_id in record.claim_ids
        }
        identities = {
            source.document_id: identity_of(source.url) for source in run.sources
        }
        evidence_sources = {
            record.evidence_id: identities.get(record.source_document_id)
            or record.source_document_id
            for record in run.evidence
        }
        gaps: list[ResearchKnowledgeGap] = []
        for claim in self._active_claims(run):
            if self._is_contradicted(claim, contradicted):
                gaps.append(
                    self._gap(
                        run,
                        ResearchKnowledgeGapKind.CONTRADICTED_CLAIM,
                        claim.claim_id,
                        "This claim is contradicted, so the record holds "
                        "incompatible beliefs.",
                        detected_at,
                    )
                )
                continue
            if claim.epistemic_state in UNRESOLVED_STATES:
                gaps.append(
                    self._gap(
                        run,
                        ResearchKnowledgeGapKind.UNRESOLVED_CLAIM,
                        claim.claim_id,
                        f"This claim is still {claim.epistemic_state.value} "
                        "and unresolved.",
                        detected_at,
                    )
                )
                continue
            if (
                claim.epistemic_state in SETTLED_STATES
                and self._distinct_source_count(claim, evidence_sources, identities)
                == 1
            ):
                gaps.append(
                    self._gap(
                        run,
                        ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM,
                        claim.claim_id,
                        "This claim rests on a single source, so nothing "
                        "corroborates it.",
                        detected_at,
                    )
                )
        return gaps

    def _source_gaps(
        self,
        run: ResearchRun,
        detected_at: datetime,
    ) -> list[ResearchKnowledgeGap]:
        trust = self._active_trust(run)
        cited = {record.source_document_id for record in run.evidence}
        gaps: list[ResearchKnowledgeGap] = []
        for source in run.sources:
            document_id = source.document_id
            if document_id not in trust:
                gaps.append(
                    self._gap(
                        run,
                        ResearchKnowledgeGapKind.UNASSESSED_SOURCE,
                        document_id,
                        "This accepted source carries no assessment of its trust.",
                        detected_at,
                    )
                )
            elif trust[document_id] is ResearchInformationTrust.LOW:
                gaps.append(
                    self._gap(
                        run,
                        ResearchKnowledgeGapKind.LOW_TRUST_SOURCE,
                        document_id,
                        "This source was assessed as low trust, so what rests "
                        "on it is weak.",
                        detected_at,
                    )
                )
            if document_id not in cited:
                gaps.append(
                    self._gap(
                        run,
                        ResearchKnowledgeGapKind.UNUSED_SOURCE,
                        document_id,
                        "This accepted source supports no recorded evidence.",
                        detected_at,
                    )
                )
        return gaps

    @staticmethod
    def _is_contradicted(
        claim: ResearchClaimRecord,
        contradicted: set[str],
    ) -> bool:
        return (
            claim.claim_id in contradicted
            or claim.epistemic_state is ResearchEpistemicState.CONTRADICTED
        )

    @staticmethod
    def _active_claims(run: ResearchRun) -> tuple[ResearchClaimRecord, ...]:
        """Return claims no later claim has replaced."""
        superseded = {
            claim.supersedes_claim_id
            for claim in run.claims
            if claim.supersedes_claim_id
        }
        return tuple(claim for claim in run.claims if claim.claim_id not in superseded)

    @staticmethod
    def _active_trust(run: ResearchRun) -> dict[str, ResearchInformationTrust]:
        """Return the trust label of each source's newest active assessment."""
        superseded = {
            assessment.supersedes_assessment_id
            for assessment in run.assessments
            if assessment.supersedes_assessment_id
        }
        trust: dict[str, ResearchInformationTrust] = {}
        for assessment in run.assessments:
            if assessment.assessment_id in superseded:
                continue
            trust[assessment.source_document_id] = assessment.information_trust
        return trust

    @staticmethod
    def _distinct_source_count(
        claim: ResearchClaimRecord,
        evidence_sources: dict[str, str],
        identities: dict[str, str],
    ) -> int:
        """Count independent resources, so one page cannot look like two.

        The claim's own document IDs are mapped through the identity table too.
        Leaving them raw would add the duplicate records back after the evidence
        side had already collapsed them.
        """
        resources = {
            evidence_sources[evidence_id]
            for evidence_id in claim.evidence_ids
            if evidence_id in evidence_sources
        }
        resources.update(
            identities.get(document) or document
            for document in claim.source_document_ids
        )
        return len(resources)

    @staticmethod
    def _gap(
        run: ResearchRun,
        kind: ResearchKnowledgeGapKind,
        subject_id: str,
        summary: str,
        detected_at: datetime,
    ) -> ResearchKnowledgeGap:
        return ResearchKnowledgeGap(
            gap_id=gap_identity(run.run_id, kind, subject_id),
            run_id=run.run_id,
            kind=kind,
            subject_id=subject_id,
            summary=summary[:MAX_GAP_SUMMARY_LENGTH],
            detected_at=detected_at,
        )


def gap_identity(
    run_id: str,
    kind: ResearchKnowledgeGapKind,
    subject_id: str,
) -> str:
    """Return a stable identity so re-detecting a gap yields the same ID."""
    return f"gap:{run_id}:{kind.value}:{subject_id or 'run'}"
