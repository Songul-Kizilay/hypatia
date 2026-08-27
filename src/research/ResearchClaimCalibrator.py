"""Compare each authored claim against the evidence structure behind it.

The ceilings below are structural rules, and they are stated openly rather than
hidden in a score. One unassessed source cannot carry more than a hypothesis
held with low confidence. Two independent sources, all assessed at medium trust
or better, can carry strong evidence held with high confidence. A contradicted
claim carries nothing until the contradiction is resolved.

These rules say nothing about truth. They describe what our own record can bear
the weight of, and no configuration of sources has ever made a claim correct.
The calibrator therefore reports and never edits: the epistemic state of a claim
belongs to whoever authored it.

Understatement is not reported as a problem. Someone deliberately holding back
is being careful, and calibration has no business talking anyone into more
confidence than they want.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.AssessmentWarningRules import (
    APPLICABILITY_RULES,
    CORROBORATION_RULE,
    INDEPENDENCE_RULES,
    PUBLICATION_RULES,
    USEFULNESS_RULES,
)
from research.CalibrationVerdict import CalibrationVerdict
from research.EvidenceSupportProfile import EvidenceSupportProfile
from research.ResearchAssessmentWarning import ResearchAssessmentWarning
from research.ResearchClaimCalibration import ResearchClaimCalibration
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.SourceIdentity import identity_of

_STATE_RANK: dict[ResearchEpistemicState, int] = {
    ResearchEpistemicState.CONTRADICTED: 0,
    ResearchEpistemicState.UNKNOWN: 1,
    ResearchEpistemicState.SPECULATION: 2,
    ResearchEpistemicState.HYPOTHESIS: 3,
    ResearchEpistemicState.LIKELY: 4,
    ResearchEpistemicState.STRONG_EVIDENCE: 5,
    ResearchEpistemicState.FACT: 6,
}

_CONFIDENCE_RANK: dict[ResearchClaimConfidence, int] = {
    ResearchClaimConfidence.UNASSESSED: 0,
    ResearchClaimConfidence.LOW: 1,
    ResearchClaimConfidence.MEDIUM: 2,
    ResearchClaimConfidence.HIGH: 3,
}

_TRUST_RANK: dict[ResearchInformationTrust, int] = {
    ResearchInformationTrust.UNASSESSED: 0,
    ResearchInformationTrust.LOW: 1,
    ResearchInformationTrust.MEDIUM: 2,
    ResearchInformationTrust.HIGH: 3,
}


class ResearchClaimCalibrator:
    """Report how each authored claim fits the record standing behind it."""

    def calibrate(self, run: ResearchRun) -> tuple[ResearchClaimCalibration, ...]:
        """Return one calibration per active claim, editing nothing."""
        if not isinstance(run, ResearchRun):
            raise ResearchError("Claim calibration requires a research run.")
        contradicted = {
            claim_id
            for record in run.claim_contradictions
            for claim_id in record.claim_ids
        }
        superseded = {
            claim.supersedes_claim_id
            for claim in run.claims
            if claim.supersedes_claim_id
        }
        evidence_sources = {
            record.evidence_id: record.source_document_id for record in run.evidence
        }
        identities = {
            source.document_id: identity_of(source.url) for source in run.sources
        }
        # One pass over the assessments builds both maps, so the per-claim work
        # below is a lookup rather than a rescan of every judgement in the run.
        active = self._active_assessments(run)
        trust = {
            document_id: assessment.information_trust
            for document_id, assessment in active.items()
        }
        return tuple(
            self._calibrate(claim, profile, warnings)
            for claim in run.claims
            if claim.claim_id not in superseded
            for profile in (
                self._profile(
                    claim,
                    evidence_sources,
                    identities,
                    trust,
                    contradicted=claim.claim_id in contradicted,
                ),
            )
            for warnings in (self._warnings(claim, profile, evidence_sources, active),)
        )

    def _calibrate(
        self,
        claim: ResearchClaimRecord,
        profile: EvidenceSupportProfile,
        warnings: tuple[ResearchAssessmentWarning, ...],
    ) -> ResearchClaimCalibration:
        supported_state, supported_confidence = self._ceilings(profile)
        return ResearchClaimCalibration(
            claim_id=claim.claim_id,
            authored_state=claim.epistemic_state,
            authored_confidence=claim.confidence,
            supported_state=supported_state,
            supported_confidence=supported_confidence,
            profile=profile,
            verdict=self._verdict(
                claim, profile, supported_state, supported_confidence
            ),
            warnings=warnings,
        )

    @staticmethod
    def _warnings(
        claim: ResearchClaimRecord,
        profile: EvidenceSupportProfile,
        evidence_sources: dict[str, str],
        active: dict[str, ResearchSourceAssessmentRecord],
    ) -> tuple[ResearchAssessmentWarning, ...]:
        """Report what the recorded judgements say about this claim's sources.

        Nothing here decides anything. Each dimension of each current assessment
        is looked up in a closed table, and a value that is not in the table --
        which is every `unknown`, and every answer a person gave that was not a
        complaint -- produces nothing at all. Silence is not a finding.

        Warnings group by source rather than by evidence record. A claim quoting
        one retracted paper four times has one problem; four copies of the same
        line would bury the claim quoting four different retracted papers, which
        is far worse and would look identical in the list.
        """
        evidence_by_document: dict[str, list[str]] = {}
        for evidence_id in claim.evidence_ids:
            document_id = evidence_sources.get(evidence_id)
            if document_id is not None:
                evidence_by_document.setdefault(document_id, []).append(evidence_id)
        documents = set(evidence_by_document) | set(claim.source_document_ids)

        warnings: list[ResearchAssessmentWarning] = []
        not_independent = 0
        for document_id in sorted(documents):
            assessment = active.get(document_id)
            if assessment is None:
                continue
            if assessment.independence in INDEPENDENCE_RULES:
                not_independent += 1
            rules = (
                PUBLICATION_RULES.get(assessment.publication_status),
                USEFULNESS_RULES.get(assessment.usefulness),
                APPLICABILITY_RULES.get(assessment.applicability),
                INDEPENDENCE_RULES.get(assessment.independence),
            )
            for rule in rules:
                if rule is None:
                    continue
                kind, attention = rule
                warnings.append(
                    ResearchAssessmentWarning(
                        claim_id=claim.claim_id,
                        kind=kind,
                        attention=attention,
                        source_document_id=document_id,
                        assessment_id=assessment.assessment_id,
                        evidence_ids=tuple(evidence_by_document.get(document_id, ())),
                    )
                )
        # Said once, and only when there is corroboration to be weakened. On a
        # single-source claim there is nothing for a repeated witness to inflate,
        # and the per-source warning above has already made the point.
        if profile.corroborated and not_independent:
            kind, attention = CORROBORATION_RULE
            warnings.append(
                ResearchAssessmentWarning(
                    claim_id=claim.claim_id,
                    kind=kind,
                    attention=attention,
                    evidence_ids=tuple(claim.evidence_ids),
                )
            )
        return tuple(
            sorted(
                warnings,
                key=lambda warning: (
                    -warning.attention.rank,
                    warning.kind.order,
                    warning.source_document_id,
                ),
            )
        )

    @staticmethod
    def _ceilings(
        profile: EvidenceSupportProfile,
    ) -> tuple[ResearchEpistemicState, ResearchClaimConfidence]:
        """Return the most the recorded evidence structure can carry."""
        if profile.contradicted:
            return (
                ResearchEpistemicState.CONTRADICTED,
                ResearchClaimConfidence.UNASSESSED,
            )
        lowest = _TRUST_RANK[profile.lowest_trust]
        if not profile.corroborated:
            if not profile.fully_assessed:
                return (
                    ResearchEpistemicState.HYPOTHESIS,
                    ResearchClaimConfidence.LOW,
                )
            if lowest >= _TRUST_RANK[ResearchInformationTrust.HIGH]:
                return (ResearchEpistemicState.LIKELY, ResearchClaimConfidence.MEDIUM)
            return (ResearchEpistemicState.HYPOTHESIS, ResearchClaimConfidence.LOW)
        if not profile.fully_assessed:
            return (ResearchEpistemicState.LIKELY, ResearchClaimConfidence.MEDIUM)
        if lowest >= _TRUST_RANK[ResearchInformationTrust.MEDIUM]:
            return (
                ResearchEpistemicState.STRONG_EVIDENCE,
                ResearchClaimConfidence.HIGH,
            )
        return (ResearchEpistemicState.LIKELY, ResearchClaimConfidence.MEDIUM)

    @staticmethod
    def _verdict(
        claim: ResearchClaimRecord,
        profile: EvidenceSupportProfile,
        supported_state: ResearchEpistemicState,
        supported_confidence: ResearchClaimConfidence,
    ) -> CalibrationVerdict:
        if profile.contradicted:
            return CalibrationVerdict.CONTRADICTED
        state_over = _STATE_RANK[claim.epistemic_state] > _STATE_RANK[supported_state]
        confidence_over = (
            _CONFIDENCE_RANK[claim.confidence] > _CONFIDENCE_RANK[supported_confidence]
        )
        if state_over and confidence_over:
            return CalibrationVerdict.OVERSTATED_BOTH
        if state_over:
            return CalibrationVerdict.OVERSTATED_STATE
        if confidence_over:
            return CalibrationVerdict.OVERSTATED_CONFIDENCE
        if (
            _STATE_RANK[claim.epistemic_state] < _STATE_RANK[supported_state]
            and _CONFIDENCE_RANK[claim.confidence]
            < _CONFIDENCE_RANK[supported_confidence]
        ):
            return CalibrationVerdict.UNDERSTATED
        return CalibrationVerdict.WITHIN_SUPPORT

    @staticmethod
    def _profile(
        claim: ResearchClaimRecord,
        evidence_sources: dict[str, str],
        identities: dict[str, str],
        trust: dict[str, ResearchInformationTrust],
        *,
        contradicted: bool,
    ) -> EvidenceSupportProfile:
        """Count independent resources, not stored records.

        Two records of the same page are not two sources. Counting documents
        would let one page satisfy the corroboration rule on its own, which is
        exactly the inflation the ceilings exist to prevent.
        """
        documents = {
            evidence_sources[evidence_id]
            for evidence_id in claim.evidence_ids
            if evidence_id in evidence_sources
        }
        documents.update(claim.source_document_ids)
        resources = {identities.get(document) or document for document in documents}
        assessed = [trust[document] for document in documents if document in trust]
        return EvidenceSupportProfile(
            source_count=len(resources),
            evidence_count=len(claim.evidence_ids),
            assessed_source_count=min(len(assessed), len(resources)),
            lowest_trust=(
                min(assessed, key=lambda value: _TRUST_RANK[value])
                if assessed
                else ResearchInformationTrust.UNASSESSED
            ),
            highest_trust=(
                max(assessed, key=lambda value: _TRUST_RANK[value])
                if assessed
                else ResearchInformationTrust.UNASSESSED
            ),
            contradicted=contradicted,
            superseded=False,
        )

    @staticmethod
    def _active_assessments(
        run: ResearchRun,
    ) -> dict[str, ResearchSourceAssessmentRecord]:
        """Return each source's current assessment, ignoring superseded ones.

        Only the standing judgement is read. A source once marked retracted and
        later corrected back to normal warns about nothing, because the person
        changed their mind and the record says so; the earlier assessment stays
        in the run and stays inspectable, but it no longer speaks.
        """
        superseded = {
            assessment.supersedes_assessment_id
            for assessment in run.assessments
            if assessment.supersedes_assessment_id
        }
        active: dict[str, ResearchSourceAssessmentRecord] = {}
        for assessment in run.assessments:
            if assessment.assessment_id in superseded:
                continue
            active[assessment.source_document_id] = assessment
        return active
