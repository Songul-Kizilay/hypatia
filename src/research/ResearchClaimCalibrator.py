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
from research.CalibrationVerdict import CalibrationVerdict
from research.EvidenceSupportProfile import EvidenceSupportProfile
from research.ResearchClaimCalibration import ResearchClaimCalibration
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
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
        trust = self._active_trust(run)
        return tuple(
            self._calibrate(claim, profile)
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
        )

    def _calibrate(
        self,
        claim: ResearchClaimRecord,
        profile: EvidenceSupportProfile,
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
