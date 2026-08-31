"""Derive bounded knowledge gaps from what a research run already recorded.

Detection is pure reading. It performs no network call, no model call, and no
mutation, and it never invents a fact: every gap points at a claim, a source, or
the run itself that is already persisted.

The detector deliberately reports absence rather than falsehood. An unassessed
source is not a bad source, and an unresolved claim is not a wrong claim; both
simply mean the record is thinner than it could be.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchKnowledgeGap import MAX_GAP_SUMMARY_LENGTH, ResearchKnowledgeGap
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchRun import ResearchRun
from research.SourceIdentity import identity_of

MAX_GAPS_PER_RUN = 50
RUN_SUBJECT = ""

#: The acquisition stages a run records when a source could not be obtained.
#: Read rather than retried: a failure says something is missing, and what to do
#: about that is a person's decision.
ACQUISITION_FAILURE_STAGES = frozenset(("source_load", "source_discovery"))

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
        hypotheses: Sequence[ResearchHypothesis] = (),
    ) -> tuple[ResearchKnowledgeGap, ...]:
        """Return the highest-severity gaps this run exposes, bounded in count.

        Hypotheses are passed in rather than looked up. They live in their own
        store, and reaching into it from here would make a pure reading of one
        run depend on persistence; composing the two is the application layer's
        job, and this stays a function of its arguments.
        """
        if not isinstance(run, ResearchRun):
            raise ResearchError("Knowledge gap detection requires a research run.")
        gaps = [
            *self._question_gaps(run, detected_at),
            *self._claim_gaps(run, detected_at),
            *self._source_gaps(run, detected_at),
            *self._acquisition_gaps(run, detected_at),
            *self._coverage_gaps(run, detected_at),
            *self._hypothesis_gaps(run, hypotheses, detected_at),
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

    def _hypothesis_gaps(
        self,
        run: ResearchRun,
        hypotheses: Sequence[ResearchHypothesis],
        detected_at: datetime,
    ) -> list[ResearchKnowledgeGap]:
        """Note a hypothesis that names its test and has nothing recorded yet.

        The condition is deliberately narrow, because it is the only one this
        model can state truthfully. A hypothesis carries one discriminating
        test as prose and two lists of evidence identifiers; there is no
        canonical mark saying *this* requirement was met by *that* evidence. So
        the detectable state is the unambiguous one — the test is named and no
        evidence has been entered on either side — and nothing here compares
        the wording of a test against the wording of evidence to guess at
        anything finer.

        Evidence on either side ends the gap, including evidence against. A
        hypothesis someone has argued with is being worked on; what this looks
        for is one nobody has answered at all.

        A withdrawn hypothesis is excluded because withdrawal is the one status
        that settles anything. Support does not, which is why a supported
        hypothesis is not excluded here on status — it simply has evidence, and
        so does not qualify.
        """
        return [
            self._gap(
                run,
                ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
                hypothesis.hypothesis_id,
                "This hypothesis names the observation that would settle it, "
                "and no evidence has been recorded either way.",
                detected_at,
            )
            for hypothesis in sorted(
                (
                    hypothesis
                    for hypothesis in hypotheses
                    if isinstance(hypothesis, ResearchHypothesis)
                    and hypothesis.run_id == run.run_id
                    and not hypothesis.withdrawn
                    and hypothesis.discriminating_test
                    and hypothesis.evidence_count == 0
                ),
                key=lambda hypothesis: hypothesis.hypothesis_id,
            )
        ]

    def _acquisition_gaps(
        self,
        run: ResearchRun,
        detected_at: datetime,
    ) -> list[ResearchKnowledgeGap]:
        """Report what a refused acquisition left missing, never what to retry.

        Grouped by the provider the failure was attributed to, so ten refusals
        from one provider are one gap rather than ten copies of it, and so a
        gap keeps the same identity while the same thing keeps failing.

        Legacy failures carry no provider. They are reported under their stage
        instead of being dropped or guessed at, because a failure whose origin
        was never recorded is still a hole in the record.
        """
        subjects: dict[str, str] = {}
        for failure in run.failures:
            if failure.stage not in ACQUISITION_FAILURE_STAGES:
                continue
            subjects.setdefault(failure.provider or failure.stage, failure.stage)
        return [
            self._gap(
                run,
                ResearchKnowledgeGapKind.FAILED_ACQUISITION,
                subject,
                "An attempt to acquire a source here did not succeed, so "
                "whatever it would have supported is still missing.",
                detected_at,
            )
            for subject in sorted(subjects)
        ]

    def _coverage_gaps(
        self,
        run: ResearchRun,
        detected_at: datetime,
    ) -> list[ResearchKnowledgeGap]:
        """Note a question put to one provider when the run could ask another.

        Only when at least one provider was actually asked. A run that has
        searched nowhere is already an unsupported question, and saying it also
        has a coverage gap would be two names for one emptiness.

        Nothing here prefers the provider that was not asked. Which results are
        better is exactly the judgement the comparison report refuses to make,
        and a gap that implied it would be that judgement wearing a question
        mark.
        """
        asked = {discovery.provider for discovery in run.discoveries}
        if not asked:
            return []
        unasked = sorted(
            provider.value
            for provider in ResearchDiscoveryProviderName
            if provider.value not in asked
        )
        if not unasked:
            return []
        return [
            self._gap(
                run,
                ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP,
                RUN_SUBJECT,
                "This question has been put to some of the available providers "
                f"and not to {', '.join(unasked)}.",
                detected_at,
            )
        ]

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
        """Return each source's least-trusting active authored assessment."""
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
            if current is None or ResearchKnowledgeGapDetector._trust_rank(
                assessment.information_trust
            ) < ResearchKnowledgeGapDetector._trust_rank(current):
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
