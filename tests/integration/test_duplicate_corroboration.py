"""One page stored twice is one source, however many records it has.

The security audit surfaced this as a real gap: the same resource could exist
under two document IDs, and everything that counted support counted records. Two
records of one page therefore read as two independent sources, so a claim resting
on a single page could satisfy the corroboration ceiling and a hypothesis could
look supported by sources it did not have.

The fix separates two questions that were being answered by one number. How many
records exist is a storage question, and the records are left alone — nothing is
merged, nothing is deleted, and history is preserved. How many independent
sources support something is an epistemic question, and that is now counted over
resource identities.

Normalisation stays conservative on purpose. A missed merge overcounts support,
which the audit already flags; a wrong merge silently discards a genuinely
independent source, which nothing would flag. So only near-certain equivalences
apply, and titles are never compared.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from knowledge.KnowledgeEngine import KnowledgeEngine
from research.CalibrationVerdict import CalibrationVerdict
from research.HypothesisStatus import HypothesisStatus
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchClaimCalibrator import ResearchClaimCalibrator
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchHypothesisAppraiser import ResearchHypothesisAppraiser
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchKnowledgeGapDetector import ResearchKnowledgeGapDetector
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceRecord import ResearchSourceRecord
from research.SourceIdentity import identity_of, independent_identities, same_resource
from research.SourceReputationLedger import SourceReputationLedger
from research.SourceStanding import MIN_ASSESSMENTS_FOR_STANDING, SourceStanding
from security.SecurityFindingKind import SecurityFindingKind
from security.SecurityPostureAuditor import SecurityPostureAuditor

QUESTION = "Does web cache deception have a documented mitigation?"
START = datetime(2026, 8, 1, tzinfo=UTC)


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


class SourceIdentityTests(unittest.TestCase):
    """Level A: only near-certain equivalences collapse."""

    SAME = (
        ("https://example.test/a", "https://example.test/a/"),
        ("https://example.test/a", "https://www.example.test/a"),
        ("https://Example.Test/a", "https://example.test/a"),
        ("https://example.test:443/a", "https://example.test/a"),
        ("http://example.test:80/a", "http://example.test/a"),
    )
    DIFFERENT = (
        ("https://example.test/a", "https://example.test/b"),
        ("https://example.test/a", "https://other.test/a"),
        ("https://example.test/a", "https://docs.example.test/a"),
        ("https://example.test/a?x=1", "https://example.test/a?x=2"),
        ("https://example.test/a", "https://example.test/A"),
        ("https://example.test/a", "http://example.test/a"),
    )

    def test_equivalent_urls_share_an_identity(self) -> None:
        for first, second in self.SAME:
            with self.subTest(first=first, second=second):
                self.assertTrue(same_resource(first, second))

    def test_distinct_resources_keep_distinct_identities(self) -> None:
        for first, second in self.DIFFERENT:
            with self.subTest(first=first, second=second):
                self.assertFalse(same_resource(first, second))

    def test_a_query_string_is_kept(self) -> None:
        self.assertIn("x=1", identity_of("https://example.test/a?x=1"))

    def test_an_unparseable_value_stays_distinct(self) -> None:
        first = identity_of("not a url")
        second = identity_of("also not a url")

        self.assertTrue(first)
        self.assertNotEqual(first, second)

    def test_an_empty_value_has_no_identity(self) -> None:
        for value in ("", "   ", None):
            with self.subTest(value=value):
                self.assertEqual(identity_of(value), "")  # type: ignore[arg-type]

    def test_independent_identities_collapse_duplicates(self) -> None:
        identities = independent_identities(
            (
                "https://example.test/a",
                "https://www.example.test/a/",
                "https://example.test/b",
            )
        )

        self.assertEqual(len(identities), 2)


class DuplicateCorroborationFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.manager.load()
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            InMemoryContentStore(),  # type: ignore[arg-type]
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def accept(self, run_id: str, url: str, body: str) -> str:
        result = self.acceptance.accept(
            ResearchSource(
                url=url,
                title="A source",
                content=body,
                content_type="text/html",
                fetched_at=START,
            ),
            run_id,
        )
        assert result.document_id is not None
        return result.document_id

    def add_evidence(self, run_id: str, document_id: str) -> str:
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == document_id and candidate.index == 0
        )
        updated = self.manager.add_evidence(run_id, chunk, "Directly relevant.")
        return updated.evidence[-1].evidence_id

    def duplicated_run(self) -> tuple[str, list[str]]:
        """Return a run holding the same resource twice, plus its evidence.

        The two records differ only in a trailing slash, which is how a genuine
        duplicate arrives: the same page reached by two equivalent URLs.
        """
        run_id = self.manager.create(QUESTION).run_id
        first = self.accept(
            run_id,
            "https://example.test/page",
            "Web cache deception stores a personalised response.",
        )
        second = self.accept(
            run_id,
            "https://example.test/page/",
            "Web cache deception stores a personalised response in a shared cache.",
        )
        return run_id, [
            self.add_evidence(run_id, first),
            self.add_evidence(run_id, second),
        ]

    def distinct_run(self) -> tuple[str, list[str]]:
        """Return a run holding two genuinely different pages on one host."""
        run_id = self.manager.create(QUESTION).run_id
        first = self.accept(
            run_id,
            "https://example.test/first",
            "Web cache deception stores a personalised response.",
        )
        second = self.accept(
            run_id,
            "https://example.test/second",
            "A cache key that ignores the path suffix causes the confusion.",
        )
        return run_id, [
            self.add_evidence(run_id, first),
            self.add_evidence(run_id, second),
        ]

    def assess_all(
        self,
        run_id: str,
        evidence_ids: list[str],
        trust: ResearchInformationTrust,
    ) -> None:
        run = self.manager.get(run_id)
        for source, evidence_id in zip(run.sources, evidence_ids, strict=True):
            self.manager.record_source_assessment(
                run_id,
                source.document_id,
                [evidence_id],
                "Assessed for the duplicate test.",
                information_trust=trust,
            )


class CalibrationCorroborationTests(DuplicateCorroborationFixture):
    def calibrate(self, run_id: str) -> CalibrationVerdict:
        calibrations = ResearchClaimCalibrator().calibrate(self.manager.get(run_id))
        self.assertEqual(len(calibrations), 1)
        return calibrations[0].verdict

    def test_one_page_twice_does_not_corroborate_a_claim(self) -> None:
        run_id, evidence_ids = self.duplicated_run()
        self.assess_all(run_id, evidence_ids, ResearchInformationTrust.MEDIUM)
        self.manager.record_claim(
            run_id,
            evidence_ids,
            "The mitigation is documented.",
            ResearchEpistemicState.STRONG_EVIDENCE,
            ResearchClaimConfidence.HIGH,
        )

        self.assertIs(self.calibrate(run_id), CalibrationVerdict.OVERSTATED_BOTH)

    def test_two_different_pages_still_corroborate(self) -> None:
        run_id, evidence_ids = self.distinct_run()
        self.assess_all(run_id, evidence_ids, ResearchInformationTrust.MEDIUM)
        self.manager.record_claim(
            run_id,
            evidence_ids,
            "The mitigation is documented.",
            ResearchEpistemicState.STRONG_EVIDENCE,
            ResearchClaimConfidence.HIGH,
        )

        self.assertIs(self.calibrate(run_id), CalibrationVerdict.WITHIN_SUPPORT)

    def test_the_profile_reports_one_source_for_a_duplicate(self) -> None:
        run_id, evidence_ids = self.duplicated_run()
        self.manager.record_claim(
            run_id,
            evidence_ids,
            "The mitigation is documented.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
        )

        calibration = ResearchClaimCalibrator().calibrate(self.manager.get(run_id))[0]

        self.assertEqual(calibration.profile.source_count, 1)
        self.assertFalse(calibration.profile.corroborated)


class HypothesisCorroborationTests(DuplicateCorroborationFixture):
    def appraise(self, run_id: str, evidence_ids: list[str]) -> HypothesisStatus:
        hypothesis = ResearchHypothesis(
            hypothesis_id="hypothesis-1",
            run_id=run_id,
            statement="The mitigation is documented.",
            discriminating_test="A contradicting vendor advisory would counter it.",
            created_at=START,
            updated_at=START,
            supporting_evidence_ids=tuple(evidence_ids),
        )
        return (
            ResearchHypothesisAppraiser()
            .appraise(hypothesis, self.manager.get(run_id))
            .status
        )

    def test_one_page_twice_does_not_support_a_hypothesis(self) -> None:
        run_id, evidence_ids = self.duplicated_run()

        self.assertIs(self.appraise(run_id, evidence_ids), HypothesisStatus.OPEN)

    def test_two_different_pages_do_support_a_hypothesis(self) -> None:
        run_id, evidence_ids = self.distinct_run()
        self.assess_all(run_id, evidence_ids, ResearchInformationTrust.MEDIUM)

        self.assertIs(self.appraise(run_id, evidence_ids), HypothesisStatus.SUPPORTED)

    def test_the_supporting_source_count_collapses_a_duplicate(self) -> None:
        run_id, evidence_ids = self.duplicated_run()
        hypothesis = ResearchHypothesis(
            hypothesis_id="hypothesis-1",
            run_id=run_id,
            statement="The mitigation is documented.",
            discriminating_test="A contradicting vendor advisory would counter it.",
            created_at=START,
            updated_at=START,
            supporting_evidence_ids=tuple(evidence_ids),
        )

        appraisal = ResearchHypothesisAppraiser().appraise(
            hypothesis,
            self.manager.get(run_id),
        )

        self.assertEqual(appraisal.supporting_source_count, 1)
        self.assertFalse(appraisal.corroborated)


class ThinClaimDetectionTests(DuplicateCorroborationFixture):
    def test_a_claim_on_one_duplicated_page_is_still_thin(self) -> None:
        run_id, evidence_ids = self.duplicated_run()
        self.manager.record_claim(
            run_id,
            evidence_ids,
            "The mitigation is documented.",
            ResearchEpistemicState.LIKELY,
        )

        gaps = ResearchKnowledgeGapDetector().detect(self.manager.get(run_id), START)

        self.assertIn(
            ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM,
            [gap.kind for gap in gaps],
        )

    def test_a_claim_on_two_pages_is_not_thin(self) -> None:
        run_id, evidence_ids = self.distinct_run()
        self.manager.record_claim(
            run_id,
            evidence_ids,
            "The mitigation is documented.",
            ResearchEpistemicState.LIKELY,
        )

        gaps = ResearchKnowledgeGapDetector().detect(self.manager.get(run_id), START)

        self.assertNotIn(
            ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM,
            [gap.kind for gap in gaps],
        )


class ReputationSampleTests(DuplicateCorroborationFixture):
    def test_the_same_page_assessed_twice_counts_once(self) -> None:
        run_id, evidence_ids = self.duplicated_run()
        self.assess_all(run_id, evidence_ids, ResearchInformationTrust.LOW)

        reputation = SourceReputationLedger().build(self.manager.list())[0]

        self.assertEqual(reputation.assessed_count, 1)
        self.assertEqual(reputation.low_count, 1)
        self.assertEqual(reputation.accepted_count, 2)

    def test_a_duplicate_cannot_reach_a_standing_on_its_own(self) -> None:
        run_id, evidence_ids = self.duplicated_run()
        self.assess_all(run_id, evidence_ids, ResearchInformationTrust.LOW)

        reputation = SourceReputationLedger().build(self.manager.list())[0]

        self.assertIs(reputation.standing, SourceStanding.PROVISIONAL)

    def test_distinct_pages_still_accumulate_a_sample(self) -> None:
        for index in range(MIN_ASSESSMENTS_FOR_STANDING):
            run_id = self.manager.create(QUESTION).run_id
            document_id = self.accept(
                run_id,
                f"https://example.test/p{index}",
                f"Distinct body number {index} about cache keys and suffixes.",
            )
            evidence_id = self.add_evidence(run_id, document_id)
            self.manager.record_source_assessment(
                run_id,
                document_id,
                [evidence_id],
                "Assessed for the duplicate test.",
                information_trust=ResearchInformationTrust.LOW,
            )

        reputation = SourceReputationLedger().build(self.manager.list())[0]

        self.assertEqual(reputation.assessed_count, MIN_ASSESSMENTS_FOR_STANDING)
        self.assertIs(reputation.standing, SourceStanding.CONSISTENTLY_LOW)


class DuplicateStaysVisibleTests(DuplicateCorroborationFixture):
    def test_the_audit_still_reports_the_duplicate(self) -> None:
        """A currently-redundant check is what notices a regression."""
        run_id, _ = self.duplicated_run()

        report = SecurityPostureAuditor().audit(self.manager.list())

        self.assertEqual(
            len(report.of_kind(SecurityFindingKind.DUPLICATE_SOURCE_URL)),
            2,
        )
        self.assertEqual(len(self.manager.get(run_id).sources), 2)

    def test_the_audit_detects_an_equivalent_url_not_only_an_identical_one(
        self,
    ) -> None:
        run_id = self.manager.create(QUESTION).run_id
        first = self.accept(
            run_id,
            "https://example.test/page",
            "One body about cache deception and shared caches.",
        )
        run = self.manager.get(run_id)
        original = run.sources[0]
        self.assertEqual(original.document_id, first)
        twin = ResearchSourceRecord(
            document_id="second-document",
            url="https://www.example.test/page/",
            title=original.title,
            content_type=original.content_type,
            fetched_at=original.fetched_at,
            added_at=original.added_at,
        )

        report = SecurityPostureAuditor().audit(
            (replace(run, sources=(original, twin), evidence=()),)
        )

        self.assertEqual(
            len(report.of_kind(SecurityFindingKind.DUPLICATE_SOURCE_URL)),
            2,
        )

    def test_distinct_pages_produce_no_duplicate_finding(self) -> None:
        self.distinct_run()

        report = SecurityPostureAuditor().audit(self.manager.list())

        self.assertEqual(report.of_kind(SecurityFindingKind.DUPLICATE_SOURCE_URL), ())

    def test_no_record_is_merged_or_removed(self) -> None:
        """Storage stays history-preserving; only counting changed."""
        run_id, _ = self.duplicated_run()

        run = self.manager.get(run_id)

        self.assertEqual(len(run.sources), 2)
        self.assertEqual(len(run.evidence), 2)
        self.assertEqual(
            len({source.document_id for source in run.sources}),
            2,
        )


if __name__ == "__main__":
    unittest.main()
