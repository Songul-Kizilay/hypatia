"""Derive where a hypothesis stands from the evidence entered on each side.

The rules are stated rather than scored, and they are asymmetric on purpose. Any
opposing evidence at all is enough to move a hypothesis off the supported track,
while support has to come from more than one source before it counts as
anything. That asymmetry is not fairness — it is the whole reason a
discriminating test is required, and softening it would make disconfirmation
just another input to be outvoted.

Nothing here decides whether a hypothesis is true. Which side wins is a
judgement someone makes after reading both, and the appraiser exists to make
sure both are still visible when they do.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.HypothesisAppraisal import HypothesisAppraisal
from research.HypothesisStatus import HypothesisStatus
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchRun import ResearchRun
from research.SourceIdentity import identity_of

MIN_SOURCES_FOR_SUPPORT = 2


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
        identities = {
            source.document_id: identity_of(source.url) for source in run.sources
        }
        sources = {
            record.evidence_id: identities.get(record.source_document_id)
            or record.source_document_id
            for record in run.evidence
        }
        supporting = self._sources(hypothesis.supporting_evidence_ids, sources)
        opposing = self._sources(hypothesis.opposing_evidence_ids, sources)
        return HypothesisAppraisal(
            hypothesis=hypothesis,
            status=self._status(hypothesis, len(supporting), len(opposing)),
            supporting_source_count=len(supporting),
            opposing_source_count=len(opposing),
        )

    @staticmethod
    def _status(
        hypothesis: ResearchHypothesis,
        supporting: int,
        opposing: int,
    ) -> HypothesisStatus:
        """Return the bounded standing. No branch here returns "true"."""
        if hypothesis.withdrawn:
            return HypothesisStatus.WITHDRAWN
        if opposing and supporting:
            return HypothesisStatus.WEAKENED
        if opposing:
            return HypothesisStatus.CONTRADICTED
        if supporting >= MIN_SOURCES_FOR_SUPPORT:
            return HypothesisStatus.SUPPORTED
        return HypothesisStatus.OPEN

    @staticmethod
    def _sources(
        evidence_ids: tuple[str, ...],
        sources: dict[str, str],
    ) -> set[str]:
        """Return the distinct resources behind this evidence, not the records.

        Support requires more than one source; two records of the same page must
        not satisfy that between them.
        """
        return {
            sources[evidence_id]
            for evidence_id in evidence_ids
            if evidence_id in sources
        }
