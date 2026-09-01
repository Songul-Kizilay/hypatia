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
from research.ResearchClaimCalibrator import ResearchClaimCalibrator
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchHypothesisAppraiser import ResearchHypothesisAppraiser
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchKnowledgeGap import MAX_GAP_SUMMARY_LENGTH, ResearchKnowledgeGap
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchRun import ResearchRun

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
        calibrations = {
            calibration.claim_id: calibration
            for calibration in ResearchClaimCalibrator().calibrate(run)
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
            if claim.epistemic_state not in SETTLED_STATES:
                continue
            calibration = calibrations[claim.claim_id]
            if calibration.profile.source_count == 1:
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
                continue
            if (
                calibration.profile.corroborated
                and not calibration.profile.independence_confirmed
            ):
                gaps.append(
                    self._gap(
                        run,
                        ResearchKnowledgeGapKind.UNCONFIRMED_INDEPENDENCE_CLAIM,
                        claim.claim_id,
                        "This claim has multiple sources, but the record does "
                        "not confirm that every corroborating source is "
                        "independent.",
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
        """Report unanswered tests and only-apparent hypothesis corroboration.

        The discriminating-test gap closes on the authored association and on
        nothing else. Supporting or opposing evidence says that material bears
        on the hypothesis; it does not say somebody examined the question the
        hypothesis was built around.

        Independence is a second, separate gap. More than one canonical source
        can look corroborating while every assessment is silent or one says a
        source repeats another. Reuse the hypothesis appraiser's exact boundary
        rather than inventing another count here. A single supporting source is
        not called corroborated, so it does not produce this specific gap.

        A withdrawn hypothesis is excluded because withdrawal is the one status
        that settles anything. Nothing here compares prose, decides truth, or
        changes the hypothesis.
        """
        gaps: list[ResearchKnowledgeGap] = []
        appraiser = ResearchHypothesisAppraiser()
        run_evidence_ids = {record.evidence_id for record in run.evidence}
        current = sorted(
            (
                hypothesis
                for hypothesis in hypotheses
                if isinstance(hypothesis, ResearchHypothesis)
                and hypothesis.run_id == run.run_id
                and not hypothesis.withdrawn
                and hypothesis.discriminating_test
            ),
            key=lambda hypothesis: hypothesis.hypothesis_id,
        )
        for hypothesis in current:
            # One evidence record cannot represent corroboration. Avoid asking
            # the appraiser to resolve its source until there are at least two
            # authored supporting records; this also preserves legacy
            # hypothesis-gap readings whose old evidence identifiers predate
            # the run-side evidence aggregate.
            if len(hypothesis.supporting_evidence_ids) > 1 and all(
                evidence_id in run_evidence_ids
                for evidence_id in hypothesis.supporting_evidence_ids
            ):
                appraisal = appraiser.appraise(hypothesis, run)
                if (
                    appraisal.corroborated
                    and not appraisal.supporting_sources_independence_confirmed
                ):
                    gaps.append(
                        self._gap(
                            run,
                            ResearchKnowledgeGapKind.UNCONFIRMED_INDEPENDENCE_HYPOTHESIS,
                            hypothesis.hypothesis_id,
                            "This hypothesis has support from multiple sources, but "
                            "the record does not confirm that every supporting "
                            "source is independent.",
                            detected_at,
                        )
                    )
            if not hypothesis.has_discriminating_test_evidence:
                gaps.append(
                    self._gap(
                        run,
                        ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
                        hypothesis.hypothesis_id,
                        "This hypothesis names the observation that would settle "
                        "it, and no evidence has been recorded as addressing it.",
                        detected_at,
                    )
                )
        return gaps

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
