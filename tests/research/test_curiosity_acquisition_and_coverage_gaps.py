"""Two things a run already recorded and curiosity was not reading.

The engine was already complete for what a run *holds* — claims, sources,
evidence, assessments. It was blind to two things a run *attempted*: an
acquisition that failed, and a question put to one provider when another was
available. Both are recorded on the run, both are plainly gaps in the record,
and neither needed a new aggregate to see.

What they must not become is advice. A failed acquisition is a hole with a known
cause, not a reason to try the same thing again, so its question asks what is
still missing rather than what to re-run. A single-provider run is narrow, not
wrong, and its question asks what other coverage would add rather than which
provider answers better — that judgement belongs to the person reading the
comparison, and a gap implying it would be that judgement wearing a question
mark.

Nothing here reaches a network, a model, or a store. Detection reads one run.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from research.CuriosityProposalBuilder import CuriosityProposalBuilder
from research.ResearchCuriosityQuestionGenerator import (
    ResearchCuriosityQuestionGenerator,
)
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchKnowledgeGapDetector import (
    ACQUISITION_FAILURE_STAGES,
    ResearchKnowledgeGapDetector,
)
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRecord import ResearchSourceRecord
from tests.SourceVocabulary import module_vocabulary

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
QUESTION = "CVE-2025-29927"
DETECTOR_SOURCE = (SRC_DIR / "research" / "ResearchKnowledgeGapDetector.py").read_text(
    encoding="utf-8"
)
GENERATOR_SOURCE = (
    SRC_DIR / "research" / "ResearchCuriosityQuestionGenerator.py"
).read_text(encoding="utf-8")


def failure(stage: str = "source_load", provider: str | None = None):
    return ResearchFailureRecord(
        stage=stage,
        reason="Research source acquisition failed.",
        occurred_at=NOW,
        provider=provider,
    )


def discovery(number: int, provider: str) -> ResearchSourceDiscoveryRecord:
    return ResearchSourceDiscoveryRecord(
        f"discovery-{number}",
        QUESTION,
        provider,
        (
            ResearchSourceCandidate(
                url=f"https://example.test/{number}", title="A result", snippet=""
            ),
        ),
        NOW,
    )


def source(document_id: str = "document-1") -> ResearchSourceRecord:
    return ResearchSourceRecord(
        document_id=document_id,
        url=f"https://example.test/{document_id}",
        title="An accepted source",
        content_type="text/plain",
        fetched_at=NOW,
        added_at=NOW,
    )


def run(**overrides) -> ResearchRun:
    fields = {
        "run_id": "run-1",
        "question": QUESTION,
        "status": ResearchRunStatus.COLLECTING,
        "sources": (),
        "failures": (),
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return ResearchRun(**fields)


def gaps_of(research_run: ResearchRun, kind: ResearchKnowledgeGapKind):
    return [
        gap
        for gap in ResearchKnowledgeGapDetector().detect(research_run, NOW)
        if gap.kind is kind
    ]


class FailedAcquisitionGapTests(unittest.TestCase):
    def test_a_refused_acquisition_is_reported_as_a_gap(self) -> None:
        [gap] = gaps_of(
            run(failures=(failure(provider="nvd"),)),
            ResearchKnowledgeGapKind.FAILED_ACQUISITION,
        )

        self.assertEqual(gap.subject_id, "nvd")
        self.assertEqual(gap.run_id, "run-1")
        self.assertIn("still missing", gap.summary)

    def test_repeated_failures_from_one_provider_are_one_gap(self) -> None:
        """Ten refusals are one hole, and keep one identity while they repeat."""
        first = gaps_of(
            run(failures=(failure(provider="nvd"),)),
            ResearchKnowledgeGapKind.FAILED_ACQUISITION,
        )
        again = gaps_of(
            run(failures=tuple(failure(provider="nvd") for _ in range(10))),
            ResearchKnowledgeGapKind.FAILED_ACQUISITION,
        )

        self.assertEqual(len(again), 1)
        self.assertEqual(first[0].gap_id, again[0].gap_id)

    def test_two_providers_failing_are_two_separate_gaps(self) -> None:
        found = gaps_of(
            run(failures=(failure(provider="nvd"), failure(provider="crossref"))),
            ResearchKnowledgeGapKind.FAILED_ACQUISITION,
        )

        self.assertEqual(sorted(gap.subject_id for gap in found), ["crossref", "nvd"])

    def test_a_legacy_failure_without_a_provider_is_still_reported(self) -> None:
        """A failure whose origin was never recorded is still a hole."""
        [gap] = gaps_of(
            run(failures=(failure(provider=None),)),
            ResearchKnowledgeGapKind.FAILED_ACQUISITION,
        )

        self.assertEqual(gap.subject_id, "source_load")

    def test_a_failure_from_another_stage_is_not_an_acquisition_gap(self) -> None:
        self.assertEqual(
            gaps_of(
                run(failures=(failure(stage="evidence_integrity"),)),
                ResearchKnowledgeGapKind.FAILED_ACQUISITION,
            ),
            [],
        )
        self.assertNotIn("evidence_integrity", ACQUISITION_FAILURE_STAGES)

    def test_the_question_asks_what_is_missing_and_never_to_retry(self) -> None:
        """The one thing this gap must not become is advice to try again."""
        research_run = run(failures=(failure(provider="nvd"),))
        [question] = [
            question
            for question in ResearchCuriosityQuestionGenerator().generate(
                research_run,
                ResearchKnowledgeGapDetector().detect(research_run, NOW),
            )
            if question.kind is ResearchKnowledgeGapKind.FAILED_ACQUISITION
        ]

        self.assertEqual(
            question.text,
            "What information is still missing because a source could not be "
            "acquired from nvd?",
        )
        for advice in ("retry", "try again", "re-run", "attempt again"):
            with self.subTest(advice=advice):
                self.assertNotIn(advice, question.text.casefold())

    def test_no_retry_machinery_exists_in_either_module(self) -> None:
        for name, text in (
            ("detector", DETECTOR_SOURCE),
            ("generator", GENERATOR_SOURCE),
        ):
            with self.subTest(module=name):
                vocabulary = module_vocabulary(text)
                for forbidden in ("retry", "reattempt", "sleep", "fetch", "execute"):
                    self.assertNotIn(forbidden, vocabulary)


class ProviderCoverageGapTests(unittest.TestCase):
    def test_a_single_provider_run_reports_a_coverage_gap(self) -> None:
        [gap] = gaps_of(
            run(discoveries=(discovery(1, "nvd"),)),
            ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP,
        )

        self.assertEqual(gap.subject_id, "")
        self.assertIn("crossref", gap.summary)

    def test_a_run_asking_both_providers_reports_no_coverage_gap(self) -> None:
        self.assertEqual(
            gaps_of(
                run(discoveries=(discovery(1, "nvd"), discovery(2, "crossref"))),
                ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP,
            ),
            [],
        )

    def test_a_run_that_searched_nowhere_is_not_a_coverage_gap(self) -> None:
        """Emptiness already has a name, and does not need a second one."""
        detected = ResearchKnowledgeGapDetector().detect(run(), NOW)

        kinds = {gap.kind for gap in detected}
        self.assertNotIn(ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP, kinds)
        self.assertIn(ResearchKnowledgeGapKind.UNSUPPORTED_QUESTION, kinds)

    def test_the_coverage_question_prefers_no_provider(self) -> None:
        research_run = run(discoveries=(discovery(1, "nvd"),))
        [question] = [
            question
            for question in ResearchCuriosityQuestionGenerator().generate(
                research_run,
                ResearchKnowledgeGapDetector().detect(research_run, NOW),
            )
            if question.kind is ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP
        ]

        self.assertEqual(
            question.text,
            "What would the providers not yet asked add to this run's coverage?",
        )
        for verdict in ("better", "worse", "prefer", "instead of", "should use"):
            with self.subTest(word=verdict):
                self.assertNotIn(verdict, question.text.casefold())

    def test_which_provider_was_asked_does_not_change_the_ranking(self) -> None:
        """Provider identity is not a reason to care more or less about a gap."""
        ranks = {}
        for provider in ("nvd", "crossref"):
            research_run = run(discoveries=(discovery(1, provider),))
            [question] = [
                question
                for question in ResearchCuriosityQuestionGenerator().generate(
                    research_run,
                    ResearchKnowledgeGapDetector().detect(research_run, NOW),
                )
                if question.kind is ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP
            ]
            ranks[provider] = question.rank_score

        self.assertEqual(ranks["nvd"], ranks["crossref"])


class ResolutionAndDeterminismTests(unittest.TestCase):
    def test_an_authoritative_provider_does_not_suppress_other_gaps(self) -> None:
        """NVD answering is not a reason to stop noticing an unassessed source."""
        research_run = run(
            sources=(source(),),
            discoveries=(discovery(1, "nvd"), discovery(2, "crossref")),
        )

        kinds = {
            gap.kind for gap in ResearchKnowledgeGapDetector().detect(research_run, NOW)
        }

        self.assertIn(ResearchKnowledgeGapKind.UNASSESSED_SOURCE, kinds)
        self.assertIn(ResearchKnowledgeGapKind.UNUSED_SOURCE, kinds)

    def test_a_coverage_gap_disappears_once_the_other_provider_is_asked(
        self,
    ) -> None:
        before = run(discoveries=(discovery(1, "nvd"),))
        after = replace(
            before, discoveries=(*before.discoveries, discovery(2, "crossref"))
        )

        self.assertEqual(
            len(gaps_of(before, ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP)), 1
        )
        self.assertEqual(
            gaps_of(after, ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP), []
        )

    def test_unchanged_state_detects_identically_every_time(self) -> None:
        research_run = run(
            failures=(failure(provider="nvd"),),
            discoveries=(discovery(1, "nvd"),),
            sources=(source(),),
        )

        first = ResearchKnowledgeGapDetector().detect(research_run, NOW)
        second = ResearchKnowledgeGapDetector().detect(research_run, NOW)

        self.assertEqual(first, second)
        self.assertEqual([gap.gap_id for gap in first], [gap.gap_id for gap in second])

    def test_detection_reads_the_run_without_changing_it(self) -> None:
        research_run = run(
            failures=(failure(provider="nvd"),),
            discoveries=(discovery(1, "nvd"),),
            sources=(source(),),
        )
        before = replace(research_run)

        ResearchKnowledgeGapDetector().detect(research_run, NOW)

        self.assertEqual(research_run, before)
        self.assertEqual(research_run.sources, before.sources)
        self.assertEqual(research_run.evidence, ())
        self.assertEqual(research_run.claims, ())
        self.assertEqual(research_run.assessments, ())

    def test_the_new_gaps_rank_below_every_claim_gap(self) -> None:
        """An attempt that failed still matters less than a belief in trouble."""
        for attempted in (
            ResearchKnowledgeGapKind.FAILED_ACQUISITION,
            ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP,
        ):
            for claim_kind in (
                ResearchKnowledgeGapKind.CONTRADICTED_CLAIM,
                ResearchKnowledgeGapKind.UNRESOLVED_CLAIM,
                ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM,
            ):
                with self.subTest(attempted=attempted, claim=claim_kind):
                    self.assertLess(attempted.severity, claim_kind.severity)

    def test_the_generated_output_stays_capped(self) -> None:
        research_run = run(
            failures=tuple(
                failure(provider=f"provider-{index}") for index in range(30)
            ),
            discoveries=(discovery(1, "nvd"),),
        )

        questions = ResearchCuriosityQuestionGenerator(max_questions=5).generate(
            research_run, ResearchKnowledgeGapDetector().detect(research_run, NOW)
        )

        self.assertEqual(len(questions), 5)


class CoverageProposalStepTests(unittest.TestCase):
    """One discovery step per provider that has not been asked, named exactly.

    The plan is where a coverage gap stops being an observation and becomes
    work, so this checks the work is addressed to somebody in particular. A
    step that named no provider would leave the choice to whatever the runtime
    felt like reaching for, which is the one thing a coverage gap must not do.
    """

    def _proposal(self, asked: tuple[str, ...]):
        """Return the proposal for a run that has asked exactly these providers."""
        return self._proposal_from(
            tuple(
                discovery(index, provider)
                for index, provider in enumerate(asked, start=1)
            )
        )

    def _proposal_from(self, discoveries: tuple):
        """Return the proposal for a run holding exactly these discoveries."""
        research_run = run(discoveries=discoveries)
        [question] = [
            candidate
            for candidate in ResearchCuriosityQuestionGenerator().generate(
                research_run,
                ResearchKnowledgeGapDetector().detect(research_run, NOW),
            )
            if candidate.kind is ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP
        ]
        return CuriosityProposalBuilder().build(
            question.accepted(NOW),
            research_run,
            ResearchPlanDraftService(id_factory=lambda: "plan-1", clock=lambda: NOW),
        )

    def test_the_plan_looks_locally_before_asking_anyone(self) -> None:
        proposal = self._proposal(("nvd",))

        first = proposal.plan.steps[0]

        self.assertIs(
            first.capability,
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
        )
        self.assertIsNone(first.discovery_provider)

    def test_each_unasked_provider_gets_its_own_named_step(self) -> None:
        proposal = self._proposal(("nvd",))

        discoveries = [
            step
            for step in proposal.plan.steps
            if step.capability is ResearchPlanStepCapability.SOURCE_DISCOVERY
        ]

        self.assertEqual(
            [step.discovery_provider.value for step in discoveries],
            [
                provider.value
                for provider in ResearchDiscoveryProviderName
                if provider.value != "nvd"
            ],
        )

    def test_a_provider_already_asked_gets_no_step(self) -> None:
        proposal = self._proposal(("nvd",))

        providers = {
            step.discovery_provider.value
            for step in proposal.plan.steps
            if step.discovery_provider is not None
        }

        self.assertNotIn("nvd", providers)

    def test_the_recorded_order_of_discoveries_does_not_change_the_plan(self) -> None:
        """Same provider asked twice, recorded either way round, plans the same.

        Storage order is not a planning rule. Only two providers exist, so both
        runs here still leave the same one unasked; what differs is the order
        the record happens to hold, and the plan must not notice.
        """
        forward = self._proposal_from(
            (discovery(1, "nvd"), discovery(2, "nvd")),
        )
        backward = self._proposal_from(
            (discovery(2, "nvd"), discovery(1, "nvd")),
        )

        self.assertEqual(forward.digest, backward.digest)

    def test_the_same_state_plans_the_same_way_twice(self) -> None:
        self.assertEqual(
            self._proposal(("nvd",)).digest, self._proposal(("nvd",)).digest
        )

    def test_no_step_needs_a_result_that_does_not_exist_yet(self) -> None:
        """Nothing authored here binds to a source, document or chunk."""
        proposal = self._proposal(("nvd",))

        for step in proposal.plan.steps:
            with self.subTest(step=step.step_id):
                self.assertEqual(step.selected_source_document_ids, ())
                self.assertEqual(step.authorized_source_url, "")


if __name__ == "__main__":
    unittest.main()
