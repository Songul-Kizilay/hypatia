"""Review can say a claim rests on a source somebody distrusted, and change nothing.

The warnings are the easy half. The half these tests are mostly about is what a
warning is forbidden to become: a lowered confidence, a withdrawn claim, a
deleted piece of evidence, a demoted source, a rewritten rank. A system that
quietly acted on its own warnings would be correcting a person's judgement while
calling it bookkeeping, and the person would never see it happen.

The other half is restraint about silence. `unknown` warns about nothing, an
unassessed source warns about nothing, and an old record that predates these
dimensions warns about nothing. Absence of a judgement is not a judgement.
"""

from __future__ import annotations

import ast
import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.AssessmentWarningAttention import AssessmentWarningAttention
from research.AssessmentWarningKind import AssessmentWarningKind
from research.ResearchAssessmentWarning import ResearchAssessmentWarning
from research.ResearchCalibrationReport import ResearchCalibrationReport
from research.ResearchClaimCalibrator import ResearchClaimCalibrator
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceRecord import ResearchSourceRecord
from research.ResearchSourceRelevanceRanker import ResearchSourceRelevanceRanker
from research.ResearchSourceUsefulness import ResearchSourceUsefulness
from research.SourceReputationLedger import SourceReputationLedger
from tests.SourceVocabulary import mentions, working_vocabulary

CALIBRATOR_SOURCE = (SRC_DIR / "research" / "ResearchClaimCalibrator.py").read_text(
    encoding="utf-8"
)
RULES_SOURCE = (SRC_DIR / "research" / "AssessmentWarningRules.py").read_text(
    encoding="utf-8"
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def source(number: int) -> ResearchSourceRecord:
    return ResearchSourceRecord(
        document_id=f"document-{number}",
        url=f"https://doi.org/10.1000/{number}",
        title=f"Paper {number}",
        content_type="text/plain",
        fetched_at=NOW,
        added_at=NOW,
    )


def evidence(number: int, document: int | None = None) -> ResearchEvidenceRecord:
    return ResearchEvidenceRecord(
        evidence_id=f"evidence-{number}",
        source_document_id=f"document-{document or number}",
        chunk_id=f"chunk-{number}",
        chunk_index=0,
        excerpt="Body text.",
        excerpt_truncated=False,
        chunk_sha256=sha256(b"Body text.").hexdigest(),
        note="A note.",
        recorded_at=NOW,
    )


def assessment(
    number: int,
    document: int | None = None,
    *,
    text: str = "I read it.",
    supersedes: str | None = None,
    usefulness: ResearchSourceUsefulness = ResearchSourceUsefulness.UNKNOWN,
    applicability: ResearchSourceApplicability = ResearchSourceApplicability.UNKNOWN,
    independence: ResearchSourceIndependence = ResearchSourceIndependence.UNKNOWN,
    publication_status: ResearchSourcePublicationStatus = (
        ResearchSourcePublicationStatus.UNKNOWN
    ),
    trust: ResearchInformationTrust = ResearchInformationTrust.UNASSESSED,
) -> ResearchSourceAssessmentRecord:
    document = document or number
    return ResearchSourceAssessmentRecord(
        assessment_id=f"assessment-{number}",
        source_document_id=f"document-{document}",
        evidence_ids=(f"evidence-{document}",),
        text=text,
        recorded_at=NOW,
        supersedes_assessment_id=supersedes,
        information_trust=trust,
        usefulness=usefulness,
        applicability=applicability,
        independence=independence,
        publication_status=publication_status,
    )


def claim(
    documents: tuple[int, ...] = (1,),
    evidence_numbers: tuple[int, ...] = (1,),
    *,
    state: ResearchEpistemicState = ResearchEpistemicState.STRONG_EVIDENCE,
    confidence: ResearchClaimConfidence = ResearchClaimConfidence.HIGH,
) -> ResearchClaimRecord:
    return ResearchClaimRecord(
        claim_id="claim-1",
        text="Request smuggling is possible here.",
        epistemic_state=state,
        confidence=confidence,
        source_document_ids=tuple(f"document-{number}" for number in documents),
        evidence_ids=tuple(f"evidence-{number}" for number in evidence_numbers),
        recorded_at=NOW,
    )


def build_run(
    *,
    sources: tuple[int, ...] = (1,),
    evidence_records: tuple[ResearchEvidenceRecord, ...] | None = None,
    assessments: tuple[ResearchSourceAssessmentRecord, ...] = (),
    claims: tuple[ResearchClaimRecord, ...] | None = None,
) -> ResearchRun:
    return ResearchRun(
        run_id="run-1",
        question="HTTP request smuggling in Next.js middleware",
        status=ResearchRunStatus.COLLECTING,
        sources=tuple(source(number) for number in sources),
        failures=(),
        created_at=NOW,
        updated_at=NOW,
        evidence=(
            tuple(evidence(number) for number in sources)
            if evidence_records is None
            else evidence_records
        ),
        assessments=assessments,
        claims=(claim(),) if claims is None else claims,
    )


def kinds(calibration) -> list[str]:
    return [warning.kind.value for warning in calibration.warnings]


class WarningTestCase(unittest.TestCase):
    def calibrate(self, run: ResearchRun):
        [calibration] = ResearchClaimCalibrator().calibrate(run)
        return calibration

    def only(self, **judgement) -> object:
        """Calibrate one claim resting on one source judged exactly this way."""
        return self.calibrate(build_run(assessments=(assessment(1, **judgement),)))


class PublicationStatusTests(WarningTestCase):
    def test_a_retracted_source_raises_the_highest_attention(self) -> None:
        calibration = self.only(
            publication_status=ResearchSourcePublicationStatus.RETRACTED
        )

        self.assertIn(AssessmentWarningKind.SOURCE_RETRACTED.value, kinds(calibration))
        self.assertEqual(
            calibration.highest_attention, AssessmentWarningAttention.HIGH_ATTENTION
        )

    def test_a_withdrawn_source_raises_the_highest_attention(self) -> None:
        calibration = self.only(
            publication_status=ResearchSourcePublicationStatus.WITHDRAWN
        )

        self.assertIn(AssessmentWarningKind.SOURCE_WITHDRAWN.value, kinds(calibration))
        self.assertEqual(
            calibration.highest_attention, AssessmentWarningAttention.HIGH_ATTENTION
        )

    def test_a_corrected_source_is_reported_without_being_alarming(self) -> None:
        """The paper still stands; some part of it changed."""
        calibration = self.only(
            publication_status=ResearchSourcePublicationStatus.CORRECTED
        )

        self.assertEqual(kinds(calibration), ["source_corrected"])
        self.assertEqual(calibration.highest_attention, AssessmentWarningAttention.INFO)

    def test_a_normal_publication_says_nothing(self) -> None:
        calibration = self.only(
            publication_status=ResearchSourcePublicationStatus.NORMAL
        )

        self.assertEqual(calibration.warnings, ())

    def test_an_unknown_publication_status_is_never_a_complaint(self) -> None:
        calibration = self.only(
            publication_status=ResearchSourcePublicationStatus.UNKNOWN
        )

        self.assertEqual(calibration.warnings, ())


class UsefulnessTests(WarningTestCase):
    def test_a_source_judged_useless_is_reported(self) -> None:
        calibration = self.only(usefulness=ResearchSourceUsefulness.NOT_USEFUL)

        self.assertEqual(kinds(calibration), ["source_not_useful"])
        self.assertEqual(
            calibration.highest_attention, AssessmentWarningAttention.REVIEW
        )

    def test_a_useful_source_says_nothing(self) -> None:
        self.assertEqual(
            self.only(usefulness=ResearchSourceUsefulness.USEFUL).warnings, ()
        )

    def test_an_unknown_usefulness_says_nothing(self) -> None:
        self.assertEqual(
            self.only(usefulness=ResearchSourceUsefulness.UNKNOWN).warnings, ()
        )

    def test_partly_useful_says_nothing_by_design(self) -> None:
        """Warning about it would make the honest middle answer the costly one."""
        self.assertEqual(
            self.only(usefulness=ResearchSourceUsefulness.PARTIALLY_USEFUL).warnings,
            (),
        )


class ApplicabilityTests(WarningTestCase):
    def test_an_unrelated_source_still_supporting_a_claim_is_reported(self) -> None:
        calibration = self.only(applicability=ResearchSourceApplicability.UNRELATED)

        self.assertEqual(kinds(calibration), ["source_unrelated"])
        self.assertEqual(
            calibration.highest_attention, AssessmentWarningAttention.REVIEW
        )

    def test_background_only_is_reported_as_information(self) -> None:
        """The domain cannot tell direct support from context, so it does not try."""
        calibration = self.only(
            applicability=ResearchSourceApplicability.BACKGROUND_ONLY
        )

        self.assertEqual(kinds(calibration), ["source_background_only"])
        self.assertEqual(calibration.highest_attention, AssessmentWarningAttention.INFO)

    def test_direct_applicability_says_nothing(self) -> None:
        self.assertEqual(
            self.only(applicability=ResearchSourceApplicability.DIRECT).warnings, ()
        )

    def test_unknown_applicability_says_nothing(self) -> None:
        self.assertEqual(
            self.only(applicability=ResearchSourceApplicability.UNKNOWN).warnings, ()
        )

    def test_partial_applicability_says_nothing(self) -> None:
        self.assertEqual(
            self.only(applicability=ResearchSourceApplicability.PARTIAL).warnings, ()
        )


class IndependenceTests(WarningTestCase):
    def _two_source_run(
        self,
        first: ResearchSourceIndependence,
        second: ResearchSourceIndependence,
    ) -> ResearchRun:
        return build_run(
            sources=(1, 2),
            assessments=(
                assessment(1, independence=first),
                assessment(2, independence=second),
            ),
            claims=(claim(documents=(1, 2), evidence_numbers=(1, 2)),),
        )

    def test_a_derivative_source_is_reported(self) -> None:
        calibration = self.only(independence=ResearchSourceIndependence.DERIVATIVE)

        self.assertEqual(kinds(calibration), ["source_not_independent"])

    def test_a_likely_duplicate_is_reported(self) -> None:
        calibration = self.only(
            independence=ResearchSourceIndependence.LIKELY_DUPLICATE
        )

        self.assertEqual(kinds(calibration), ["source_not_independent"])

    def test_an_independent_source_says_nothing(self) -> None:
        self.assertEqual(
            self.only(independence=ResearchSourceIndependence.INDEPENDENT).warnings,
            (),
        )

    def test_case_b_two_derivative_sources_question_the_corroboration(self) -> None:
        """Two witnesses and one witness twice look identical from outside."""
        run = self._two_source_run(
            ResearchSourceIndependence.DERIVATIVE,
            ResearchSourceIndependence.DERIVATIVE,
        )

        calibration = self.calibrate(run)

        self.assertIn(
            AssessmentWarningKind.CORROBORATION_MAY_NOT_BE_INDEPENDENT.value,
            kinds(calibration),
        )
        self.assertEqual(
            kinds(calibration).count(
                AssessmentWarningKind.CORROBORATION_MAY_NOT_BE_INDEPENDENT.value
            ),
            1,
        )

    def test_the_corroboration_warning_deletes_and_merges_nothing(self) -> None:
        run = self._two_source_run(
            ResearchSourceIndependence.DERIVATIVE,
            ResearchSourceIndependence.LIKELY_DUPLICATE,
        )
        before = (run.sources, run.evidence, run.claims)

        calibration = self.calibrate(run)

        self.assertEqual((run.sources, run.evidence, run.claims), before)
        self.assertEqual(calibration.profile.source_count, 2)
        self.assertTrue(calibration.profile.corroborated)

    def test_a_single_source_claim_raises_no_corroboration_warning(self) -> None:
        """There is no corroboration to weaken when there is one witness."""
        calibration = self.only(independence=ResearchSourceIndependence.DERIVATIVE)

        self.assertNotIn(
            AssessmentWarningKind.CORROBORATION_MAY_NOT_BE_INDEPENDENT.value,
            kinds(calibration),
        )

    def test_independent_sources_raise_no_corroboration_warning(self) -> None:
        run = self._two_source_run(
            ResearchSourceIndependence.INDEPENDENT,
            ResearchSourceIndependence.INDEPENDENT,
        )

        self.assertEqual(self.calibrate(run).warnings, ())


class GroupingTests(WarningTestCase):
    def test_one_retracted_source_quoted_four_times_warns_once(self) -> None:
        """Four copies would bury the claim quoting four different retractions."""
        run = build_run(
            sources=(1,),
            evidence_records=tuple(evidence(number, 1) for number in (1, 2, 3, 4)),
            assessments=(
                assessment(
                    1,
                    publication_status=ResearchSourcePublicationStatus.RETRACTED,
                ),
            ),
            claims=(claim(documents=(1,), evidence_numbers=(1, 2, 3, 4)),),
        )

        calibration = self.calibrate(run)

        self.assertEqual(kinds(calibration), ["source_retracted"])
        self.assertEqual(len(calibration.warnings[0].evidence_ids), 4)

    def test_a_warning_names_the_source_and_the_assessment_behind_it(self) -> None:
        calibration = self.only(
            publication_status=ResearchSourcePublicationStatus.RETRACTED
        )

        warning = calibration.warnings[0]
        self.assertEqual(warning.source_document_id, "document-1")
        self.assertEqual(warning.assessment_id, "assessment-1")

    def test_one_retraction_among_four_sources_names_only_that_one(self) -> None:
        run = build_run(
            sources=(1, 2, 3, 4),
            assessments=(
                assessment(
                    3,
                    publication_status=ResearchSourcePublicationStatus.RETRACTED,
                ),
            ),
            claims=(claim(documents=(1, 2, 3, 4), evidence_numbers=(1, 2, 3, 4)),),
        )

        calibration = self.calibrate(run)

        self.assertEqual(len(calibration.warnings), 1)
        self.assertEqual(calibration.warnings[0].source_document_id, "document-3")

    def test_identity_is_derived_so_recomputing_produces_equal_warnings(self) -> None:
        run = build_run(
            assessments=(
                assessment(
                    1,
                    publication_status=ResearchSourcePublicationStatus.RETRACTED,
                ),
            )
        )

        first = self.calibrate(run).warnings
        second = self.calibrate(run).warnings

        self.assertEqual(first, second)
        self.assertEqual(
            first[0].identity, ("claim-1", "document-1", "source_retracted")
        )

    def test_a_calibration_refuses_a_repeated_warning(self) -> None:
        warning = ResearchAssessmentWarning(
            claim_id="claim-1",
            kind=AssessmentWarningKind.SOURCE_RETRACTED,
            attention=AssessmentWarningAttention.HIGH_ATTENTION,
            source_document_id="document-1",
        )
        calibration = self.only(
            publication_status=ResearchSourcePublicationStatus.RETRACTED
        )

        with self.assertRaises(ResearchError):
            replace(calibration, warnings=(warning, warning))

    def test_a_warning_cannot_be_attached_to_another_claim(self) -> None:
        calibration = self.only(
            publication_status=ResearchSourcePublicationStatus.RETRACTED
        )
        foreign = ResearchAssessmentWarning(
            claim_id="claim-9",
            kind=AssessmentWarningKind.SOURCE_RETRACTED,
            attention=AssessmentWarningAttention.HIGH_ATTENTION,
            source_document_id="document-1",
        )

        with self.assertRaises(ResearchError):
            replace(calibration, warnings=(foreign,))

    def test_a_source_specific_warning_must_name_its_source(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchAssessmentWarning(
                claim_id="claim-1",
                kind=AssessmentWarningKind.SOURCE_RETRACTED,
                attention=AssessmentWarningAttention.HIGH_ATTENTION,
            )


class SupersessionTests(WarningTestCase):
    def test_the_current_assessment_is_the_one_that_speaks(self) -> None:
        run = build_run(
            assessments=(
                assessment(
                    1,
                    publication_status=ResearchSourcePublicationStatus.RETRACTED,
                ),
                assessment(
                    2,
                    document=1,
                    supersedes="assessment-1",
                    publication_status=ResearchSourcePublicationStatus.NORMAL,
                ),
            )
        )

        calibration = self.calibrate(run)

        self.assertEqual(calibration.warnings, ())

    def test_a_revision_that_finds_a_retraction_raises_the_warning(self) -> None:
        run = build_run(
            assessments=(
                assessment(
                    1,
                    publication_status=ResearchSourcePublicationStatus.NORMAL,
                ),
                assessment(
                    2,
                    document=1,
                    supersedes="assessment-1",
                    publication_status=ResearchSourcePublicationStatus.RETRACTED,
                ),
            )
        )

        calibration = self.calibrate(run)

        self.assertEqual(kinds(calibration), ["source_retracted"])
        self.assertEqual(calibration.warnings[0].assessment_id, "assessment-2")

    def test_the_superseded_judgement_is_left_exactly_where_it_was(self) -> None:
        run = build_run(
            assessments=(
                assessment(
                    1,
                    publication_status=ResearchSourcePublicationStatus.RETRACTED,
                ),
                assessment(
                    2,
                    document=1,
                    supersedes="assessment-1",
                    publication_status=ResearchSourcePublicationStatus.NORMAL,
                ),
            )
        )
        before = run.assessments

        self.calibrate(run)

        self.assertEqual(run.assessments, before)
        self.assertEqual(
            run.assessments[0].publication_status,
            ResearchSourcePublicationStatus.RETRACTED,
        )

    def test_a_superseded_judgement_never_warns_alongside_the_current_one(
        self,
    ) -> None:
        run = build_run(
            assessments=(
                assessment(1, usefulness=ResearchSourceUsefulness.NOT_USEFUL),
                assessment(
                    2,
                    document=1,
                    supersedes="assessment-1",
                    applicability=ResearchSourceApplicability.UNRELATED,
                ),
            )
        )

        calibration = self.calibrate(run)

        self.assertEqual(kinds(calibration), ["source_unrelated"])
        self.assertNotIn("source_not_useful", kinds(calibration))


class ParallelAssessmentTests(WarningTestCase):
    def test_a_parallel_normal_assessment_does_not_hide_a_retraction(self) -> None:
        run = build_run(
            assessments=(
                assessment(
                    1,
                    publication_status=ResearchSourcePublicationStatus.RETRACTED,
                ),
                assessment(
                    2,
                    document=1,
                    publication_status=ResearchSourcePublicationStatus.NORMAL,
                ),
            )
        )

        calibration = self.calibrate(run)

        self.assertEqual(kinds(calibration), ["source_retracted"])
        self.assertEqual(calibration.warnings[0].assessment_id, "assessment-1")

    def test_same_parallel_concern_is_grouped_once_per_source(self) -> None:
        run = build_run(
            assessments=(
                assessment(
                    1,
                    publication_status=ResearchSourcePublicationStatus.RETRACTED,
                ),
                assessment(
                    2,
                    document=1,
                    publication_status=ResearchSourcePublicationStatus.RETRACTED,
                ),
            )
        )

        calibration = self.calibrate(run)

        self.assertEqual(kinds(calibration), ["source_retracted"])
        self.assertEqual(calibration.warnings[0].assessment_id, "assessment-2")


class ReadOnlyTests(WarningTestCase):
    def _rich_run(self) -> ResearchRun:
        return build_run(
            sources=(1, 2),
            assessments=(
                assessment(
                    1,
                    publication_status=ResearchSourcePublicationStatus.RETRACTED,
                    independence=ResearchSourceIndependence.DERIVATIVE,
                    trust=ResearchInformationTrust.LOW,
                ),
                assessment(2, usefulness=ResearchSourceUsefulness.NOT_USEFUL),
            ),
            claims=(claim(documents=(1, 2), evidence_numbers=(1, 2)),),
        )

    def test_case_a_a_retracted_source_leaves_a_high_confidence_claim_alone(
        self,
    ) -> None:
        run = self._rich_run()
        before = run.claims

        calibration = self.calibrate(run)

        self.assertEqual(run.claims, before)
        self.assertEqual(calibration.authored_confidence, ResearchClaimConfidence.HIGH)
        self.assertEqual(
            calibration.authored_state, ResearchEpistemicState.STRONG_EVIDENCE
        )
        self.assertIn("source_retracted", kinds(calibration))

    def test_nothing_canonical_moves_when_warnings_are_computed(self) -> None:
        run = self._rich_run()
        before = (
            run.claims,
            run.evidence,
            run.sources,
            run.assessments,
            run.discoveries,
            run.status,
        )

        ResearchClaimCalibrator().calibrate(run)

        self.assertEqual(
            (
                run.claims,
                run.evidence,
                run.sources,
                run.assessments,
                run.discoveries,
                run.status,
            ),
            before,
        )

    def test_case_d_source_reputation_is_untouched_by_a_warning(self) -> None:
        run = self._rich_run()
        ledger = SourceReputationLedger()
        before = ledger.build([run])

        ResearchClaimCalibrator().calibrate(run)

        self.assertEqual(ledger.build([run]), before)

    def test_case_c_relevance_ranking_is_untouched_by_a_warning(self) -> None:
        candidates = [
            ResearchSourceCandidate(
                url="https://doi.org/10.1000/1",
                title="Request smuggling in Next.js middleware",
                snippet="",
            ),
            ResearchSourceCandidate(
                url="https://doi.org/10.1000/2",
                title="A general survey",
                snippet="",
            ),
        ]
        query = "request smuggling in Next.js middleware"
        before = [
            (entry.candidate.url, entry.relevance.score, entry.relevance_rank)
            for entry in ResearchSourceRelevanceRanker().rank(query, candidates)
        ]

        calibration = self.calibrate(self._rich_run())

        after = [
            (entry.candidate.url, entry.relevance.score, entry.relevance_rank)
            for entry in ResearchSourceRelevanceRanker().rank(query, candidates)
        ]
        self.assertEqual(after, before)
        self.assertTrue(calibration.warnings)

    def test_the_warning_path_reaches_no_network_and_no_model(self) -> None:
        for name, source_text in (
            ("calibrator", CALIBRATOR_SOURCE),
            ("rules", RULES_SOURCE),
        ):
            imported = _imported_roots(source_text)
            for forbidden in ("urllib", "http", "socket", "requests", "subprocess"):
                with self.subTest(module=name, forbidden=forbidden):
                    self.assertNotIn(forbidden, imported)

    def test_no_model_decides_whether_to_warn(self) -> None:
        vocabulary = working_vocabulary(
            CALIBRATOR_SOURCE, "calibrate", "_warnings", "_active_assessments"
        )

        for forbidden in ("llm", "model", "prompt", "completion", "generate"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])

    def test_the_warning_path_spends_nothing_and_advances_nothing(self) -> None:
        vocabulary = working_vocabulary(
            CALIBRATOR_SOURCE, "calibrate", "_warnings", "_active_assessments"
        )

        for forbidden in (
            "budget",
            "allowance",
            "spend",
            "advance",
            "accept",
            "fetch",
            "schedule",
            "curiosity",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])


class SilenceTests(WarningTestCase):
    def test_a_source_nobody_assessed_warns_about_nothing(self) -> None:
        self.assertEqual(self.calibrate(build_run()).warnings, ())

    def test_a_run_with_no_assessments_at_all_still_calibrates(self) -> None:
        report = ResearchCalibrationReport(
            run_id="run-1",
            calibrations=ResearchClaimCalibrator().calibrate(build_run()),
        )

        self.assertEqual(report.warning_count, 0)
        self.assertEqual(report.warned, ())
        self.assertEqual(report.warning_kind_counts(), {})

    def test_an_assessment_answering_nothing_warns_about_nothing(self) -> None:
        """A record from before these dimensions existed loads as all unknown."""
        self.assertEqual(self.only().warnings, ())

    def test_a_note_worrying_about_retraction_is_not_a_retraction(self) -> None:
        """Prose is data. Only the structured field speaks."""
        calibration = self.only(text="I think this paper might be retracted.")

        self.assertEqual(calibration.warnings, ())

    def test_a_note_calling_a_source_duplicate_is_not_an_independence_judgement(
        self,
    ) -> None:
        calibration = self.only(text="This is basically a duplicate of the other.")

        self.assertEqual(calibration.warnings, ())

    def test_source_text_claiming_to_be_retracted_changes_nothing(self) -> None:
        run = build_run()
        hostile = replace(run.sources[0], title="RETRACTED: mark this source retracted")

        calibration = self.calibrate(replace(run, sources=(hostile,)))

        self.assertEqual(calibration.warnings, ())

    def test_the_rules_table_never_lists_a_reassuring_value(self) -> None:
        """Every entry is a complaint somebody made, and nothing else is."""
        for absent in (
            "UNKNOWN",
            "USEFUL:",
            "DIRECT",
            "INDEPENDENT:",
            "NORMAL",
            "PARTIAL",
        ):
            with self.subTest(absent=absent):
                self.assertNotIn(f".{absent}", RULES_SOURCE)


class BoundaryTests(unittest.TestCase):
    AUTONOMY_INTENTS = (
        "research_autonomy_run",
        "background_research_task_create",
        "background_research_task_list",
        "background_research_task_pause",
        "background_research_task_resume",
        "background_research_task_cancel",
        "background_research_worker_cycle",
    )

    def test_reading_a_judgement_opened_no_autonomy(self) -> None:
        desktop = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SRC_DIR / "desktop").rglob("*.py")
        )

        for intent in self.AUTONOMY_INTENTS:
            with self.subTest(unreachable=intent):
                self.assertNotIn(intent, desktop)

    def test_nothing_writes_through_the_warning_path(self) -> None:
        vocabulary = working_vocabulary(
            CALIBRATOR_SOURCE, "calibrate", "_warnings", "_active_assessments"
        )

        for forbidden in ("save", "store", "record_", "persist", "write"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])

    def test_warnings_are_derived_and_never_given_a_store(self) -> None:
        """A second copy of a derived truth is a second truth that can drift."""
        stores = [
            path.name
            for path in SRC_DIR.rglob("*.py")
            if "AssessmentWarning" in path.read_text(encoding="utf-8")
            and "Store" in path.name
        ]

        self.assertEqual(stores, [])


def _imported_roots(source_text: str) -> set[str]:
    tree = ast.parse(source_text)
    return {
        name.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for name in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


if __name__ == "__main__":
    unittest.main()
