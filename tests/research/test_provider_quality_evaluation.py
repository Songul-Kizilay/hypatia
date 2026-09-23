"""Measuring which provider earned its place, without learning to choose one.

Two providers exist and nothing measured which one was worth asking. Both halves
were already recorded — a discovery names its provider, an assessment names what
a person concluded — and nothing joined them.

The join is the delicate part and most of what follows is about its honesty: a
candidate that was discovered, a source that was accepted, a source that produced
evidence, and a source somebody appraised are four different populations, and
dividing across them would produce a percentage that looks measured and means
nothing. The rest is about what the report must never become — a winner, a
preferred provider, a reputation, a reranking.
"""

from __future__ import annotations

import ast
import sys
import unittest
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.ProviderSampleSize import ProviderSampleSize, sample_size_of
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchProviderQualityEvaluator import ResearchProviderQualityEvaluator
from research.ResearchProviderQualityProfile import ResearchProviderQualityProfile
from research.ResearchProviderQualityReport import ResearchProviderQualityReport
from research.ResearchQueryCategory import ResearchQueryCategory, category_of
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceEvidenceType import ResearchSourceEvidenceType
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceRecord import ResearchSourceRecord
from research.ResearchSourceUsefulness import ResearchSourceUsefulness
from research.SourceReputationLedger import SourceReputationLedger
from tests.SourceVocabulary import mentions, working_vocabulary

EVALUATOR_SOURCE = (
    SRC_DIR / "research" / "ResearchProviderQualityEvaluator.py"
).read_text(encoding="utf-8")
REPORT_SOURCE = (SRC_DIR / "research" / "ResearchProviderQualityReport.py").read_text(
    encoding="utf-8"
)
PROFILE_SOURCE = (SRC_DIR / "research" / "ResearchProviderQualityProfile.py").read_text(
    encoding="utf-8"
)
SERVICE_SOURCE = (
    SRC_DIR / "cognition" / "ProviderQualityApplicationService.py"
).read_text(encoding="utf-8")

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def source(number: int, url: str) -> ResearchSourceRecord:
    return ResearchSourceRecord(
        document_id=f"doc-{number}",
        url=url,
        title=f"Source {number}",
        content_type="text/plain",
        fetched_at=NOW,
        added_at=NOW,
    )


def evidence(number: int) -> ResearchEvidenceRecord:
    return ResearchEvidenceRecord(
        evidence_id=f"ev-{number}",
        source_document_id=f"doc-{number}",
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
    document: int,
    *,
    supersedes: str | None = None,
    usefulness: ResearchSourceUsefulness = ResearchSourceUsefulness.UNKNOWN,
    applicability: ResearchSourceApplicability = ResearchSourceApplicability.UNKNOWN,
    independence: ResearchSourceIndependence = ResearchSourceIndependence.UNKNOWN,
    publication: ResearchSourcePublicationStatus = (
        ResearchSourcePublicationStatus.UNKNOWN
    ),
    evidence_type: ResearchSourceEvidenceType = ResearchSourceEvidenceType.UNKNOWN,
) -> ResearchSourceAssessmentRecord:
    return ResearchSourceAssessmentRecord(
        assessment_id=f"a-{number}",
        source_document_id=f"doc-{document}",
        evidence_ids=(f"ev-{document}",),
        text="I read it.",
        recorded_at=NOW,
        supersedes_assessment_id=supersedes,
        usefulness=usefulness,
        applicability=applicability,
        independence=independence,
        publication_status=publication,
        evidence_type=evidence_type,
    )


def discovery(
    number: int,
    provider: str,
    query: str,
    urls: tuple[str, ...],
) -> ResearchSourceDiscoveryRecord:
    return ResearchSourceDiscoveryRecord(
        f"discovery-{number}",
        query,
        provider,
        tuple(
            ResearchSourceCandidate(url=url, title=f"Candidate {index}", snippet="")
            for index, url in enumerate(urls, start=1)
        ),
        NOW,
    )


def run(
    run_id: str,
    *,
    question: str = "a question",
    sources: tuple[ResearchSourceRecord, ...] = (),
    evidence_records: tuple[ResearchEvidenceRecord, ...] = (),
    discoveries: tuple[ResearchSourceDiscoveryRecord, ...] = (),
    assessments: tuple[ResearchSourceAssessmentRecord, ...] = (),
) -> ResearchRun:
    return ResearchRun(
        run_id=run_id,
        question=question,
        status=ResearchRunStatus.COLLECTING,
        sources=sources,
        failures=(),
        created_at=NOW,
        updated_at=NOW,
        evidence=evidence_records,
        discoveries=discoveries,
        assessments=assessments,
    )


def profile_of(
    report: ResearchProviderQualityReport,
    provider: str,
    category: ResearchQueryCategory,
) -> ResearchProviderQualityProfile | None:
    for profile in report.profiles:
        if profile.provider == provider and profile.category is category:
            return profile
    return None


NVD_ONE = "https://nvd.nist.gov/vuln/detail/CVE-2025-29927"
NVD_TWO = "https://nvd.nist.gov/vuln/detail/CVE-2024-51479"
NVD_THREE = "https://nvd.nist.gov/vuln/detail/CVE-2020-15189"
NVD_FOUR = "https://nvd.nist.gov/vuln/detail/CVE-2009-0793"
NVD_FIVE = "https://nvd.nist.gov/vuln/detail/CVE-2021-44228"
DOI_ONE = "https://doi.org/10.1000/paper-one"
DOI_TWO = "https://doi.org/10.1000/paper-two"
SHARED = "https://doi.org/10.1000/shared"


class EvaluationFixture(unittest.TestCase):
    """Four runs, judged by hand before the code was asked.

    Deliberately messy in the ways real data is messy: a source nobody assessed,
    a source with no evidence, a revised judgement, a resource both providers
    returned, and a source somebody added without any discovery at all.
    """

    def setUp(self) -> None:
        # Run 1 — NVD, exact CVE. Two accepted with evidence; only one assessed.
        exact = run(
            "run-1",
            question="CVE-2025-29927",
            sources=(source(1, NVD_ONE), source(2, NVD_TWO)),
            evidence_records=(evidence(1), evidence(2)),
            discoveries=(discovery(1, "nvd", "CVE-2025-29927", (NVD_ONE, NVD_TWO)),),
            assessments=(
                assessment(
                    1,
                    1,
                    usefulness=ResearchSourceUsefulness.USEFUL,
                    applicability=ResearchSourceApplicability.DIRECT,
                    independence=ResearchSourceIndependence.INDEPENDENT,
                    publication=ResearchSourcePublicationStatus.NORMAL,
                ),
            ),
        )
        # Run 2 — NVD, keyword. Three candidates, one accepted without evidence.
        keyword = run(
            "run-2",
            question="Craft CMS remote code execution",
            sources=(
                source(3, NVD_THREE),
                source(4, NVD_FOUR),
                source(5, NVD_FIVE),
            ),
            evidence_records=(evidence(3), evidence(4)),
            discoveries=(
                discovery(
                    2,
                    "nvd",
                    "Craft CMS remote code execution",
                    (NVD_THREE, NVD_FOUR, NVD_FIVE),
                ),
            ),
            assessments=(
                assessment(
                    2,
                    3,
                    usefulness=ResearchSourceUsefulness.NOT_USEFUL,
                    applicability=ResearchSourceApplicability.UNRELATED,
                    independence=ResearchSourceIndependence.INDEPENDENT,
                    publication=ResearchSourcePublicationStatus.NORMAL,
                ),
                assessment(
                    3,
                    4,
                    usefulness=ResearchSourceUsefulness.PARTIALLY_USEFUL,
                    applicability=ResearchSourceApplicability.BACKGROUND_ONLY,
                    independence=ResearchSourceIndependence.DERIVATIVE,
                    publication=ResearchSourcePublicationStatus.NORMAL,
                ),
            ),
        )
        # Run 3 — Crossref, keyword. One judgement revised; one retracted source.
        scholarly = run(
            "run-3",
            question="request smuggling defences",
            sources=(source(6, DOI_ONE), source(7, DOI_TWO)),
            evidence_records=(evidence(6), evidence(7)),
            discoveries=(
                discovery(
                    3, "crossref", "request smuggling defences", (DOI_ONE, DOI_TWO)
                ),
            ),
            assessments=(
                assessment(4, 6, usefulness=ResearchSourceUsefulness.USEFUL),
                assessment(
                    5,
                    6,
                    supersedes="a-4",
                    usefulness=ResearchSourceUsefulness.NOT_USEFUL,
                    applicability=ResearchSourceApplicability.PARTIAL,
                    independence=ResearchSourceIndependence.INDEPENDENT,
                    publication=ResearchSourcePublicationStatus.NORMAL,
                ),
                assessment(
                    6,
                    7,
                    usefulness=ResearchSourceUsefulness.USEFUL,
                    applicability=ResearchSourceApplicability.DIRECT,
                    independence=ResearchSourceIndependence.LIKELY_DUPLICATE,
                    publication=ResearchSourcePublicationStatus.RETRACTED,
                ),
            ),
        )
        # Run 4 — the same resource returned by both providers, plus one source
        # nobody discovered at all.
        contested = run(
            "run-4",
            question="shared ground",
            sources=(source(8, SHARED), source(9, "https://example.test/manual")),
            evidence_records=(evidence(8), evidence(9)),
            discoveries=(
                discovery(4, "nvd", "shared ground", (SHARED,)),
                discovery(5, "crossref", "shared ground", (SHARED,)),
            ),
            assessments=(
                assessment(7, 8, usefulness=ResearchSourceUsefulness.USEFUL),
                assessment(8, 9, usefulness=ResearchSourceUsefulness.USEFUL),
            ),
        )
        self.runs = [exact, keyword, scholarly, contested]
        self.report = ResearchProviderQualityEvaluator().evaluate(self.runs)


class FunnelTests(EvaluationFixture):
    def test_the_exact_cve_profile_matches_the_hand_count(self) -> None:
        profile = profile_of(self.report, "nvd", ResearchQueryCategory.EXACT_CVE)

        assert profile is not None
        self.assertEqual(profile.discovery_count, 1)
        self.assertEqual(profile.candidate_count, 2)
        self.assertEqual(profile.accepted_count, 2)
        self.assertEqual(profile.evidence_bearing_count, 2)
        self.assertEqual(profile.assessed_count, 1)
        self.assertEqual(profile.coverage(), "1 / 2")

    def test_the_keyword_profile_matches_the_hand_count(self) -> None:
        """Two keyword discoveries, four candidates, and only two appraised.

        The hand count originally said three candidates and was wrong: run 4
        asks NVD a keyword question too, so its candidate joins this profile.
        Which is the point of counting the funnel rather than assuming it — a
        provider accumulates exposure across runs, and the denominator grows
        even when nobody assesses anything new.
        """
        profile = profile_of(self.report, "nvd", ResearchQueryCategory.KEYWORD)

        assert profile is not None
        self.assertEqual(profile.discovery_count, 2)
        self.assertEqual(profile.candidate_count, 4)
        # The contested resource is credited to neither provider, so it never
        # reaches this profile's accepted count.
        self.assertEqual(profile.accepted_count, 3)
        self.assertEqual(profile.evidence_bearing_count, 2)
        self.assertEqual(profile.assessed_count, 2)
        self.assertEqual(profile.coverage(), "2 / 2")

    def test_the_scholarly_profile_matches_the_hand_count(self) -> None:
        profile = profile_of(self.report, "crossref", ResearchQueryCategory.KEYWORD)

        assert profile is not None
        self.assertEqual(profile.discovery_count, 2)
        self.assertEqual(profile.candidate_count, 3)
        self.assertEqual(profile.accepted_count, 2)
        self.assertEqual(profile.evidence_bearing_count, 2)
        self.assertEqual(profile.assessed_count, 2)

    def test_an_unassessed_source_is_never_counted_as_a_bad_one(self) -> None:
        """Silence is missing data, not a negative vote."""
        profile = profile_of(self.report, "nvd", ResearchQueryCategory.EXACT_CVE)

        assert profile is not None
        self.assertEqual(profile.evidence_bearing_count, 2)
        self.assertEqual(sum(profile.usefulness.values()), 1)
        self.assertEqual(
            profile.usefulness.get(ResearchSourceUsefulness.NOT_USEFUL, 0), 0
        )

    def test_discovered_and_assessed_remain_different_numbers(self) -> None:
        profile = profile_of(self.report, "nvd", ResearchQueryCategory.KEYWORD)

        assert profile is not None
        self.assertNotEqual(profile.candidate_count, profile.assessed_count)


class AttributionTests(EvaluationFixture):
    def test_nvd_samples_are_attributed_to_nvd(self) -> None:
        profile = profile_of(self.report, "nvd", ResearchQueryCategory.EXACT_CVE)

        assert profile is not None
        self.assertEqual(profile.sample_document_ids, ("doc-1",))

    def test_crossref_samples_are_attributed_to_crossref(self) -> None:
        profile = profile_of(self.report, "crossref", ResearchQueryCategory.KEYWORD)

        assert profile is not None
        self.assertEqual(profile.sample_document_ids, ("doc-6", "doc-7"))

    def test_a_resource_both_providers_returned_is_credited_to_neither(self) -> None:
        """Picking whichever discovery came first would be inventing provenance."""
        self.assertEqual(self.report.ambiguous_attribution_count, 1)
        for profile in self.report.profiles:
            with self.subTest(provider=profile.provider):
                self.assertNotIn("doc-8", profile.sample_document_ids)

    def test_a_source_no_discovery_proposed_is_counted_apart(self) -> None:
        self.assertEqual(self.report.unattributed_assessed_count, 1)
        for profile in self.report.profiles:
            with self.subTest(provider=profile.provider):
                self.assertNotIn("doc-9", profile.sample_document_ids)

    def test_the_join_uses_canonical_identity_and_never_a_title(self) -> None:
        vocabulary = working_vocabulary(EVALUATOR_SOURCE, "evaluate", "_profile")

        self.assertIn("identity_of", vocabulary)
        for forbidden in ("title", "snippet", "label", "similar", "fuzzy", "domain"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])

    def test_a_trailing_slash_is_the_same_resource(self) -> None:
        """Canonical identity, which is exactly what the panel already uses."""
        report = ResearchProviderQualityEvaluator().evaluate(
            [
                run(
                    "run-1",
                    sources=(source(1, "https://example.test/paper/"),),
                    evidence_records=(evidence(1),),
                    discoveries=(
                        discovery(1, "nvd", "keyword", ("https://example.test/paper",)),
                    ),
                    assessments=(
                        assessment(1, 1, usefulness=ResearchSourceUsefulness.USEFUL),
                    ),
                )
            ]
        )

        profile = profile_of(report, "nvd", ResearchQueryCategory.KEYWORD)
        assert profile is not None
        self.assertEqual(profile.assessed_count, 1)


class SupersessionTests(EvaluationFixture):
    def test_a_revised_judgement_counts_once_and_counts_as_the_new_one(self) -> None:
        profile = profile_of(self.report, "crossref", ResearchQueryCategory.KEYWORD)

        assert profile is not None
        self.assertEqual(profile.assessed_count, 2)
        self.assertEqual(profile.usefulness.get(ResearchSourceUsefulness.NOT_USEFUL), 1)
        self.assertEqual(profile.usefulness.get(ResearchSourceUsefulness.USEFUL), 1)

    def test_changing_your_mind_does_not_produce_a_second_sample(self) -> None:
        profile = profile_of(self.report, "crossref", ResearchQueryCategory.KEYWORD)

        assert profile is not None
        self.assertEqual(len(profile.sample_document_ids), 2)
        self.assertEqual(sum(profile.usefulness.values()), 2)

    def test_the_superseded_judgement_is_left_exactly_where_it_was(self) -> None:
        before = self.runs[2].assessments

        ResearchProviderQualityEvaluator().evaluate(self.runs)

        self.assertEqual(self.runs[2].assessments, before)
        self.assertEqual(len(before), 3)


class DimensionTests(EvaluationFixture):
    def test_usefulness_counts_are_exact(self) -> None:
        profile = profile_of(self.report, "nvd", ResearchQueryCategory.KEYWORD)

        assert profile is not None
        self.assertEqual(profile.usefulness.get(ResearchSourceUsefulness.NOT_USEFUL), 1)
        self.assertEqual(
            profile.usefulness.get(ResearchSourceUsefulness.PARTIALLY_USEFUL), 1
        )
        self.assertIsNone(profile.usefulness.get(ResearchSourceUsefulness.USEFUL))

    def test_applicability_counts_are_exact(self) -> None:
        profile = profile_of(self.report, "nvd", ResearchQueryCategory.KEYWORD)

        assert profile is not None
        self.assertEqual(
            profile.applicability.get(ResearchSourceApplicability.UNRELATED), 1
        )
        self.assertEqual(
            profile.applicability.get(ResearchSourceApplicability.BACKGROUND_ONLY), 1
        )

    def test_independence_counts_are_exact(self) -> None:
        keyword = profile_of(self.report, "nvd", ResearchQueryCategory.KEYWORD)
        scholarly = profile_of(self.report, "crossref", ResearchQueryCategory.KEYWORD)

        assert keyword is not None and scholarly is not None
        self.assertEqual(
            keyword.independence.get(ResearchSourceIndependence.DERIVATIVE), 1
        )
        self.assertEqual(
            scholarly.independence.get(ResearchSourceIndependence.LIKELY_DUPLICATE), 1
        )

    def test_evidence_type_counts_are_exact(self) -> None:
        """Mirrors `test_independence_counts_are_exact`: a fifth, separate count.

        `evidence_type` is a citation, not a corroboration signal, so its own
        count-dict must track each value exactly and never fold into or read
        from the independence counts beside it.
        """
        report = ResearchProviderQualityEvaluator().evaluate(
            [
                run(
                    "run-evidence-type",
                    sources=(source(1, NVD_ONE), source(2, NVD_TWO)),
                    evidence_records=(evidence(1), evidence(2)),
                    discoveries=(discovery(1, "nvd", "keyword", (NVD_ONE, NVD_TWO)),),
                    assessments=(
                        assessment(
                            1, 1, evidence_type=ResearchSourceEvidenceType.PRIMARY
                        ),
                        assessment(
                            2, 2, evidence_type=ResearchSourceEvidenceType.TERTIARY
                        ),
                    ),
                )
            ]
        )
        profile = profile_of(report, "nvd", ResearchQueryCategory.KEYWORD)

        assert profile is not None
        self.assertEqual(
            profile.evidence_type.get(ResearchSourceEvidenceType.PRIMARY), 1
        )
        self.assertEqual(
            profile.evidence_type.get(ResearchSourceEvidenceType.TERTIARY), 1
        )
        self.assertIsNone(
            profile.evidence_type.get(ResearchSourceEvidenceType.SECONDARY)
        )
        self.assertIn("evidence type", "\n".join(profile.lines()))

    def test_a_derivative_source_does_not_become_a_useless_one(self) -> None:
        """Both can be true, and collapsing them would hide one of them."""
        profile = profile_of(self.report, "nvd", ResearchQueryCategory.KEYWORD)

        assert profile is not None
        self.assertEqual(
            profile.independence.get(ResearchSourceIndependence.DERIVATIVE), 1
        )
        self.assertEqual(
            profile.usefulness.get(ResearchSourceUsefulness.PARTIALLY_USEFUL), 1
        )

    def test_a_retracted_source_does_not_become_a_useless_one(self) -> None:
        profile = profile_of(self.report, "crossref", ResearchQueryCategory.KEYWORD)

        assert profile is not None
        self.assertEqual(
            profile.publication.get(ResearchSourcePublicationStatus.RETRACTED), 1
        )
        self.assertEqual(profile.usefulness.get(ResearchSourceUsefulness.USEFUL), 1)

    def test_unknown_is_excluded_from_the_usefulness_rate_and_still_counted(
        self,
    ) -> None:
        profile = profile_of(self.report, "nvd", ResearchQueryCategory.EXACT_CVE)

        assert profile is not None
        self.assertEqual(
            profile.applicability.get(ResearchSourceApplicability.DIRECT), 1
        )
        unanswered = ResearchProviderQualityEvaluator().evaluate(
            [
                run(
                    "run-1",
                    sources=(source(1, NVD_ONE),),
                    evidence_records=(evidence(1),),
                    discoveries=(discovery(1, "nvd", "keyword", (NVD_ONE,)),),
                    assessments=(assessment(1, 1),),
                )
            ]
        )
        only = profile_of(unanswered, "nvd", ResearchQueryCategory.KEYWORD)
        assert only is not None
        self.assertEqual(only.assessed_count, 1)
        self.assertEqual(only.usefulness.get(ResearchSourceUsefulness.UNKNOWN), 1)
        self.assertEqual(only.judged_usefulness_count, 0)


class QueryCategoryTests(unittest.TestCase):
    def test_an_exact_cve_question_is_classified_as_one(self) -> None:
        self.assertIs(category_of("CVE-2025-29927"), ResearchQueryCategory.EXACT_CVE)

    def test_case_does_not_change_the_category(self) -> None:
        self.assertIs(category_of("cve-2025-29927"), ResearchQueryCategory.EXACT_CVE)

    def test_a_malformed_identifier_is_not_an_exact_lookup(self) -> None:
        for query in ("CVE-25-1234", "CVE-2025-", "CVE2025-29927", "CVE-2025-ABC"):
            with self.subTest(query=query):
                self.assertIs(category_of(query), ResearchQueryCategory.KEYWORD)

    def test_two_identifiers_are_not_an_exact_lookup(self) -> None:
        self.assertIs(
            category_of("CVE-2025-29927 and CVE-2024-51479"),
            ResearchQueryCategory.KEYWORD,
        )

    def test_a_general_question_is_a_keyword_search(self) -> None:
        self.assertIs(
            category_of("Craft CMS remote code execution"),
            ResearchQueryCategory.KEYWORD,
        )

    def test_the_category_describes_the_question_and_not_the_provider(self) -> None:
        """Same query, two providers, one category."""
        report = ResearchProviderQualityEvaluator().evaluate(
            [
                run(
                    "run-1",
                    sources=(),
                    discoveries=(
                        discovery(1, "nvd", "CVE-2025-29927", (NVD_ONE,)),
                        discovery(2, "crossref", "CVE-2025-29927", (DOI_ONE,)),
                    ),
                )
            ]
        )

        self.assertEqual(
            {profile.category for profile in report.profiles},
            {ResearchQueryCategory.EXACT_CVE},
        )

    def test_no_model_classifies_a_question(self) -> None:
        category_source = (SRC_DIR / "research" / "ResearchQueryCategory.py").read_text(
            encoding="utf-8"
        )
        vocabulary = working_vocabulary(category_source, "category_of")

        for forbidden in ("llm", "model", "prompt", "classify_with"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])


class SampleSizeTests(unittest.TestCase):
    def test_no_assessed_samples_is_no_data_and_not_zero_quality(self) -> None:
        self.assertIs(sample_size_of(0), ProviderSampleSize.NO_DATA)
        self.assertIn("not the same", ProviderSampleSize.NO_DATA.caution)

    def test_a_tiny_sample_is_marked_as_one(self) -> None:
        for count in (1, 2, 3, 4):
            with self.subTest(count=count):
                self.assertIs(sample_size_of(count), ProviderSampleSize.VERY_SMALL)

    def test_the_bands_climb_without_ever_becoming_sufficient(self) -> None:
        self.assertIs(sample_size_of(5), ProviderSampleSize.LIMITED)
        self.assertIs(sample_size_of(20), ProviderSampleSize.DESCRIPTIVE)
        self.assertIn("descriptive", ProviderSampleSize.DESCRIPTIVE.caution.casefold())

    def test_no_confidence_interval_is_invented(self) -> None:
        size_source = (SRC_DIR / "research" / "ProviderSampleSize.py").read_text(
            encoding="utf-8"
        )

        for forbidden in ("confidence_interval", "p_value", "stddev", "significance"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, size_source)

    def test_a_ratio_never_appears_without_its_denominator(self) -> None:
        report = ResearchProviderQualityEvaluator().evaluate(
            [
                run(
                    "run-1",
                    sources=(source(1, NVD_ONE),),
                    evidence_records=(evidence(1),),
                    discoveries=(discovery(1, "nvd", "keyword", (NVD_ONE,)),),
                    assessments=(
                        assessment(1, 1, usefulness=ResearchSourceUsefulness.USEFUL),
                    ),
                )
            ]
        )

        rendered = "\n".join(report.lines())
        self.assertIn("useful: 1 / 1 (100%)", rendered)
        self.assertIn("very_small", rendered)


class ReportShapeTests(EvaluationFixture):
    def test_profiles_stay_separate_per_provider_and_category(self) -> None:
        keys = {
            (profile.provider, profile.category) for profile in self.report.profiles
        }

        self.assertIn(("nvd", ResearchQueryCategory.EXACT_CVE), keys)
        self.assertIn(("nvd", ResearchQueryCategory.KEYWORD), keys)
        self.assertIn(("crossref", ResearchQueryCategory.KEYWORD), keys)

    def test_nvd_exact_and_keyword_are_never_averaged_together(self) -> None:
        """The only thing this data actually shows would vanish if they were."""
        exact = profile_of(self.report, "nvd", ResearchQueryCategory.EXACT_CVE)
        keyword = profile_of(self.report, "nvd", ResearchQueryCategory.KEYWORD)

        assert exact is not None and keyword is not None
        self.assertEqual(exact.usefulness.get(ResearchSourceUsefulness.USEFUL), 1)
        self.assertIsNone(keyword.usefulness.get(ResearchSourceUsefulness.USEFUL))

    def test_unequal_exposure_is_shown_rather_than_normalised_away(self) -> None:
        rendered = "\n".join(self.report.lines())

        self.assertIn("discovery operations:", rendered)
        self.assertIn("candidates discovered:", rendered)

    def test_the_report_has_no_winner_and_no_preferred_provider(self) -> None:
        """Fields and code, not prose.

        The report's own text has to be able to say `no ranking was altered`,
        so searching the raw source would fail on the sentence that promises
        the very thing being checked. What must be absent is a field or a name
        the code can read.
        """
        tree = ast.parse(REPORT_SOURCE)
        fields = {
            node.target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }

        for forbidden in ("winner", "best", "preferred", "recommended", "ranking"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, fields)
                self.assertNotIn(forbidden, names)

    def test_no_single_provider_score_exists_anywhere(self) -> None:
        for name, text in (
            ("profile", PROFILE_SOURCE),
            ("report", REPORT_SOURCE),
        ):
            fields = {
                node.target.id
                for node in ast.walk(ast.parse(text))
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
            }
            with self.subTest(module=name):
                self.assertNotIn("score", fields)
                self.assertNotIn("quality_score", fields)
                self.assertNotIn("rating", fields)

    def test_the_report_says_the_samples_were_chosen_by_the_operator(self) -> None:
        rendered = "\n".join(self.report.lines())

        self.assertIn("selection-biased", rendered)
        self.assertIn("chose", rendered)
        self.assertIn("not an unbiased measurement", rendered)

    def test_the_report_says_it_changed_no_provider_choice(self) -> None:
        rendered = "\n".join(self.report.lines())

        self.assertIn("No provider was selected", rendered)
        self.assertIn("does not decide", rendered)

    def test_an_empty_history_says_so_instead_of_showing_zero_percent(self) -> None:
        report = ResearchProviderQualityEvaluator().evaluate([])

        rendered = "\n".join(report.lines())
        self.assertFalse(report.has_samples)
        self.assertIn("No assessed provider samples yet.", rendered)
        self.assertNotIn("0%", rendered)

    def test_discoveries_without_assessments_still_show_no_percentages(self) -> None:
        """Searching is not appraising, so a search alone measures nothing."""
        report = ResearchProviderQualityEvaluator().evaluate(
            [
                run(
                    "run-1",
                    discoveries=(discovery(1, "nvd", "keyword", (NVD_ONE,)),),
                )
            ]
        )

        rendered = "\n".join(report.lines())
        self.assertFalse(report.has_samples)
        self.assertIn("No assessed provider samples yet.", rendered)
        self.assertNotIn("%", rendered)
        # The profile was still built, so the funnel is available to anything
        # that asks for it. What is withheld is a rate over nothing.
        profile = profile_of(report, "nvd", ResearchQueryCategory.KEYWORD)
        assert profile is not None
        self.assertEqual(profile.candidate_count, 1)
        self.assertEqual(profile.assessed_count, 0)

    def test_every_aggregate_names_the_samples_behind_it(self) -> None:
        for profile in self.report.profiles:
            with self.subTest(provider=profile.provider):
                self.assertEqual(
                    len(profile.sample_document_ids), profile.assessed_count
                )

    def test_a_profile_whose_dimensions_disagree_is_refused(self) -> None:
        """The audit trail must not disagree with the number it explains."""
        with self.assertRaises(ResearchError):
            ResearchProviderQualityProfile(
                provider="nvd",
                category=ResearchQueryCategory.KEYWORD,
                evidence_bearing_count=2,
                assessed_count=2,
                usefulness={ResearchSourceUsefulness.USEFUL: 1},
                applicability={ResearchSourceApplicability.UNKNOWN: 2},
                independence={ResearchSourceIndependence.UNKNOWN: 2},
                publication={ResearchSourcePublicationStatus.UNKNOWN: 2},
                sample_document_ids=("doc-1", "doc-2"),
            )


class ReadOnlyTests(EvaluationFixture):
    def test_evaluating_changes_nothing_in_any_run(self) -> None:
        before = [
            (
                one.sources,
                one.evidence,
                one.assessments,
                one.claims,
                one.discoveries,
                one.status,
            )
            for one in self.runs
        ]

        ResearchProviderQualityEvaluator().evaluate(self.runs)

        self.assertEqual(
            [
                (
                    one.sources,
                    one.evidence,
                    one.assessments,
                    one.claims,
                    one.discoveries,
                    one.status,
                )
                for one in self.runs
            ],
            before,
        )

    def test_source_reputation_is_untouched_by_the_report(self) -> None:
        ledger = SourceReputationLedger()
        before = ledger.build(self.runs)

        ResearchProviderQualityEvaluator().evaluate(self.runs)

        self.assertEqual(ledger.build(self.runs), before)

    def test_nothing_in_the_path_writes_ranks_reputation_or_selection(self) -> None:
        """Whole names, not substrings: `setdefault` contains `default`."""
        vocabulary = working_vocabulary(EVALUATOR_SOURCE, "evaluate", "_profile")

        for forbidden in (
            "rank",
            "weight",
            "reputation",
            "select",
            "prefer",
            "preferred",
            "default",
            "save",
            "store",
            "persist",
            "write",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, vocabulary)

    def test_nothing_in_the_path_reaches_a_network_or_a_model(self) -> None:
        for name, text in (
            ("evaluator", EVALUATOR_SOURCE),
            ("service", SERVICE_SOURCE),
        ):
            imported = {
                item.name.split(".")[0]
                for node in ast.walk(ast.parse(text))
                if isinstance(node, ast.Import)
                for item in node.names
            } | {
                (node.module or "").split(".")[0]
                for node in ast.walk(ast.parse(text))
                if isinstance(node, ast.ImportFrom)
            }
            for forbidden in ("urllib", "http", "socket", "requests", "llm"):
                with self.subTest(module=name, forbidden=forbidden):
                    self.assertNotIn(forbidden, imported)

    def test_the_service_holds_no_write_path(self) -> None:
        for forbidden in (
            "record_source_assessment",
            "add_evidence",
            "record_claim",
            "add_source",
            "add_discovery",
            "transition_status",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, SERVICE_SOURCE)

    def test_the_report_spends_no_budget_and_advances_nothing(self) -> None:
        vocabulary = working_vocabulary(EVALUATOR_SOURCE, "evaluate")

        for forbidden in ("budget", "allowance", "spend", "advance", "authorization"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])

    def test_no_provider_is_constructed_by_the_report(self) -> None:
        for forbidden in ("Crossref", "Nvd", "discover("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, EVALUATOR_SOURCE)
                self.assertNotIn(forbidden, SERVICE_SOURCE)


class BoundaryTests(unittest.TestCase):
    #: The queue intents left this list in v0.3.278, when the operator got
    #: controls for them. They never belonged to it on their own merits: what
    #: this guards is research running without anybody asking each time, and
    #: creating, listing, pausing, resuming and cancelling a queued task reach
    #: no provider at all. Only two things run research — the autonomy run
    #: below, which stays unreachable, and the worker cycle, which is one press
    #: for one turn.
    AUTONOMY_INTENTS = ("research_autonomy_run",)

    def test_measuring_providers_opened_no_autonomy(self) -> None:
        desktop = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SRC_DIR / "desktop").rglob("*.py")
        )

        for intent in self.AUTONOMY_INTENTS:
            with self.subTest(unreachable=intent):
                self.assertNotIn(intent, desktop)

    def test_no_automatic_provider_routing_was_added(self) -> None:
        """Nothing reads the report to pick a provider, and nothing may."""
        readers = [
            path.name
            for path in SRC_DIR.rglob("*.py")
            if "ResearchProviderQualityReport" in path.read_text(encoding="utf-8")
        ]

        self.assertEqual(
            sorted(readers),
            [
                # Carrying it on a response, emitting counts, building it,
                # defining it, and rendering it. Nothing that chooses anything.
                "BrainResponse.py",
                "ProviderQualityEvents.py",
                "ResearchProviderQualityEvaluator.py",
                "ResearchProviderQualityReport.py",
                "ResponseComposer.py",
            ],
        )
        for name in ("SourceDiscoveryStepOperation.py", "Bootstrap.py"):
            with self.subTest(never_reads=name):
                self.assertNotIn(name, readers)

    def test_the_report_is_derived_and_never_given_a_store(self) -> None:
        stores = [
            path.name
            for path in SRC_DIR.rglob("*.py")
            if "ProviderQuality" in path.read_text(encoding="utf-8")
            and "Store" in path.name
        ]

        self.assertEqual(stores, [])


if __name__ == "__main__":
    unittest.main()
