"""Derive where a hypothesis stands from the evidence entered on each side.

The rules are stated rather than scored, and they are asymmetric on purpose. Any
opposing evidence at all is enough to move a hypothesis off the supported track,
while positive support has to come from more than one independent source and
each source needs an active authored trust assessment of at least medium. That
asymmetry is not fairness — it is the whole reason a discriminating test is
required, and softening it would make disconfirmation just another input to be
outvoted.

Nothing here decides whether a hypothesis is true. Which side wins is a
judgement someone makes after reading both, and the appraiser exists to make
sure both are still visible when they do.
"""

from __future__ import annotations

from dataclasses import replace

from core.Exceptions import ResearchError
from research.HypothesisAppraisal import HypothesisAppraisal
from research.HypothesisStatus import HypothesisStatus
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.SourceIdentity import identity_of


class ResearchHypothesisAppraiser:
    """Report each hypothesis's standing without ever concluding for anyone."""

    def appraise(
        self,
        hypothesis: ResearchHypothesis,
        run: ResearchRun,
    ) -> HypothesisAppraisal:
        """Return the derived standing, keeping the two sides apart."""
        if not isinstance(hypothesis, ResearchHypothesis):
            raise ResearchError("Appraisal requires a hypothesis.")
        if not isinstance(run, ResearchRun):
            raise ResearchError("Appraisal requires a research run.")
        if hypothesis.run_id != run.run_id:
            raise ResearchError("Hypothesis and research run do not match.")
        identities = {
            source.document_id: identity_of(source.url) for source in run.sources
        }
        evidence_documents = {
            record.evidence_id: record.source_document_id for record in run.evidence
        }
        evidence_ids = (
            *hypothesis.supporting_evidence_ids,
            *hypothesis.opposing_evidence_ids,
        )
        if any(evidence_id not in evidence_documents for evidence_id in evidence_ids):
            raise ResearchError(
                "Hypothesis evidence was not found in its research run."
            )
        trust = self._active_trust(run)
        supporting = self._profile(
            hypothesis.supporting_evidence_ids,
            evidence_documents,
            identities,
            trust,
        )
        opposing = self._profile(
            hypothesis.opposing_evidence_ids,
            evidence_documents,
            identities,
            trust,
        )
        appraisal = HypothesisAppraisal(
            hypothesis=hypothesis,
            status=HypothesisStatus.OPEN,
            supporting_source_count=supporting[0],
            opposing_source_count=opposing[0],
            supporting_assessed_source_count=supporting[1],
            opposing_assessed_source_count=opposing[1],
            lowest_supporting_trust=supporting[2],
            lowest_opposing_trust=opposing[2],
        )
        return replace(appraisal, status=self._status(hypothesis, appraisal))

    @staticmethod
    def _status(
        hypothesis: ResearchHypothesis,
        appraisal: HypothesisAppraisal,
    ) -> HypothesisStatus:
        """Return the bounded standing. No branch here returns "true"."""
        if hypothesis.withdrawn:
            return HypothesisStatus.WITHDRAWN
        if appraisal.opposing_source_count and appraisal.supporting_source_count:
            return HypothesisStatus.WEAKENED
        if appraisal.opposing_source_count:
            return HypothesisStatus.CONTRADICTED
        if appraisal.support_boundary_met:
            return HypothesisStatus.SUPPORTED
        return HypothesisStatus.OPEN

    @staticmethod
    def _profile(
        evidence_ids: tuple[str, ...],
        evidence_documents: dict[str, str],
        identities: dict[str, str],
        trust: dict[str, ResearchInformationTrust],
    ) -> tuple[int, int, ResearchInformationTrust]:
        """Return distinct-source count, trust coverage, and the lowest trust.

        Support requires more than one source; two records of the same page must
        not satisfy that between them. When duplicate records carry different
        active assessments, the resource keeps the least-trusting authored one.
        """
        documents = {
            evidence_documents[evidence_id]
            for evidence_id in evidence_ids
            if evidence_id in evidence_documents
        }
        resource_trust: dict[str, list[ResearchInformationTrust]] = {}
        for document in documents:
            resource = identities.get(document) or document
            resource_trust.setdefault(resource, [])
            if document in trust:
                resource_trust[resource].append(trust[document])
        assessed = [values for values in resource_trust.values() if values]
        lowest = (
            min(
                (value for values in assessed for value in values),
                key=ResearchHypothesisAppraiser._trust_rank,
            )
            if assessed
            else ResearchInformationTrust.UNASSESSED
        )
        return len(resource_trust), len(assessed), lowest

    @staticmethod
    def _active_trust(run: ResearchRun) -> dict[str, ResearchInformationTrust]:
        """Return the least-trusting active judgement for every source record.

        More than one non-superseded assessment can exist for a source. Their
        insertion order is not an epistemic rule, so a later high label must
        not silently erase an earlier active low label. An explicit correction
        still wins because its predecessor is removed by the supersession set.
        """
        superseded = {
            assessment.supersedes_assessment_id
            for assessment in run.assessments
            if assessment.supersedes_assessment_id
        }
        trust: dict[str, ResearchInformationTrust] = {}
        for assessment in run.assessments:
            if assessment.assessment_id in superseded:
                continue
            current = trust.get(assessment.source_document_id)
            if current is None or ResearchHypothesisAppraiser._trust_rank(
                assessment.information_trust
            ) < ResearchHypothesisAppraiser._trust_rank(current):
                trust[assessment.source_document_id] = assessment.information_trust
        return trust

    @staticmethod
    def _trust_rank(value: ResearchInformationTrust) -> int:
        return {
            ResearchInformationTrust.UNASSESSED: 0,
            ResearchInformationTrust.LOW: 1,
            ResearchInformationTrust.MEDIUM: 2,
            ResearchInformationTrust.HIGH: 3,
        }[value]
