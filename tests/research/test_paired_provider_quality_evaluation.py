"""Same-question provider quality stays aligned, descriptive, and read-only."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from cognition.PairedProviderQualityApplicationService import (
    PAIRED_PROVIDER_QUALITY_REPORT_INTENT,
    PairedProviderQualityApplicationService,
)
from research.ResearchPairedProviderQualityEvaluator import (
    ResearchPairedProviderQualityEvaluator,
)
from research.ResearchPairedProviderQualityReport import (
    ResearchPairedProviderQualityReport,
)
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceUsefulness import ResearchSourceUsefulness
from response.ResponseComposer import ResponseComposer
from tests.research.test_provider_quality_evaluation import (
    DOI_ONE,
    NVD_ONE,
    assessment,
    discovery,
    evidence,
    run,
    source,
)

REPORT_SOURCE = (
    SRC_DIR / "research" / "ResearchPairedProviderQualityReport.py"
).read_text(encoding="utf-8")
EVALUATOR_SOURCE = (
    SRC_DIR / "research" / "ResearchPairedProviderQualityEvaluator.py"
).read_text(encoding="utf-8")
SERVICE_SOURCE = (
    SRC_DIR / "cognition" / "PairedProviderQualityApplicationService.py"
).read_text(encoding="utf-8")

QUESTION = "CVE-2025-29927 middleware bypass"


def paired_run():
    return run(
        "paired-run",
        question=QUESTION,
        sources=(source(1, DOI_ONE), source(2, NVD_ONE)),
        evidence_records=(evidence(1), evidence(2)),
        discoveries=(
            discovery(1, "crossref", QUESTION, (DOI_ONE,)),
            discovery(2, "nvd", QUESTION, (NVD_ONE,)),
        ),
        assessments=(
            assessment(
                1,
                1,
                usefulness=ResearchSourceUsefulness.PARTIALLY_USEFUL,
                applicability=ResearchSourceApplicability.BACKGROUND_ONLY,
                independence=ResearchSourceIndependence.INDEPENDENT,
                publication=ResearchSourcePublicationStatus.NORMAL,
            ),
            assessment(
                2,
                2,
                usefulness=ResearchSourceUsefulness.USEFUL,
                applicability=ResearchSourceApplicability.DIRECT,
                independence=ResearchSourceIndependence.INDEPENDENT,
                publication=ResearchSourcePublicationStatus.NORMAL,
            ),
        ),
    )


class EvaluationTests(unittest.TestCase):
    def test_only_a_same_question_two_provider_run_is_reported(self) -> None:
        unpaired = run(
            "unpaired",
            question=QUESTION,
            discoveries=(discovery(3, "nvd", QUESTION, (NVD_ONE,)),),
        )

        report = ResearchPairedProviderQualityEvaluator().evaluate(
            [unpaired, paired_run()]
        )

        self.assertEqual(report.eligible_pair_count, 1)
        self.assertEqual([item.run_id for item in report.comparisons], ["paired-run"])

    def test_both_funnels_are_counted_separately_in_a_stable_order(self) -> None:
        [comparison] = (
            ResearchPairedProviderQualityEvaluator()
            .evaluate([paired_run()])
            .comparisons
        )

        self.assertEqual(
            [side.provider for side in comparison.sides], ["crossref", "nvd"]
        )
        self.assertEqual([side.candidate_count for side in comparison.sides], [1, 1])
        self.assertEqual([side.assessed_count for side in comparison.sides], [1, 1])
        self.assertEqual(
            comparison.sides[0].usefulness,
            {ResearchSourceUsefulness.PARTIALLY_USEFUL: 1},
        )
        self.assertEqual(
            comparison.sides[1].usefulness,
            {ResearchSourceUsefulness.USEFUL: 1},
        )

    def test_two_provider_names_with_mismatched_queries_do_not_claim_alignment(
        self,
    ) -> None:
        mismatched = run(
            "mismatched",
            question=QUESTION,
            discoveries=(
                discovery(1, "crossref", QUESTION, (DOI_ONE,)),
                discovery(2, "nvd", "a different question", (NVD_ONE,)),
            ),
        )

        report = ResearchPairedProviderQualityEvaluator().evaluate([mismatched])

        self.assertEqual(report.eligible_pair_count, 0)
        self.assertEqual(report.comparisons, ())

    def test_the_report_carries_denominators_sample_bands_and_caveats(self) -> None:
        report = ResearchPairedProviderQualityEvaluator().evaluate([paired_run()])
        rendered = "\n".join(report.lines())

        self.assertIn("assessment coverage: 1 / 1", rendered)
        self.assertIn("sample: very_small", rendered)
        self.assertIn("question is aligned", rendered)
        self.assertIn("not a controlled provider benchmark", rendered)
        self.assertIn("No provider was judged better", rendered)

    def test_an_empty_history_is_missing_data_not_a_provider_finding(self) -> None:
        report = ResearchPairedProviderQualityEvaluator().evaluate([])

        self.assertEqual(report.counts()["eligible_pair_count"], 0)
        self.assertIn("No comparison is not a finding", "\n".join(report.lines()))

    def test_the_bounded_view_keeps_the_complete_pair_denominator(self) -> None:
        runs = []
        for number in range(41):
            observed = paired_run()
            runs.append(
                run(
                    f"paired-{number:02d}",
                    question=observed.question,
                    sources=observed.sources,
                    evidence_records=observed.evidence,
                    discoveries=observed.discoveries,
                    assessments=observed.assessments,
                )
            )

        report = ResearchPairedProviderQualityEvaluator().evaluate(runs)

        self.assertEqual(report.eligible_pair_count, 41)
        self.assertEqual(len(report.comparisons), 40)
        self.assertIn("omitted from this bounded view: 1", "\n".join(report.lines()))

    def test_evaluation_does_not_mutate_the_run(self) -> None:
        observed = paired_run()
        before = (
            observed.sources,
            observed.evidence,
            observed.assessments,
            observed.discoveries,
            observed.status,
        )

        ResearchPairedProviderQualityEvaluator().evaluate([observed])

        self.assertEqual(
            (
                observed.sources,
                observed.evidence,
                observed.assessments,
                observed.discoveries,
                observed.status,
            ),
            before,
        )


class PolicyBoundaryTests(unittest.TestCase):
    def test_the_report_exposes_no_winner_score_or_routing_field(self) -> None:
        tree = ast.parse(REPORT_SOURCE)
        fields = {
            node.target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        }

        for forbidden in (
            "winner",
            "score",
            "preferred_provider",
            "recommended_provider",
            "route",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, fields)

    def test_the_path_has_no_network_model_execution_or_write_dependency(self) -> None:
        imported = {
            (node.module or "").split(".")[0]
            for text in (EVALUATOR_SOURCE, SERVICE_SOURCE)
            for node in ast.walk(ast.parse(text))
            if isinstance(node, ast.ImportFrom)
        }
        for forbidden in ("urllib", "http", "socket", "requests", "llm", "tools"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, imported)
        for forbidden in (
            "add_discovery",
            "add_source",
            "record_source_assessment",
            "advance",
            "save",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, SERVICE_SOURCE)

    def test_the_report_type_has_no_policy_reader(self) -> None:
        readers = sorted(
            path.name
            for path in SRC_DIR.rglob("*.py")
            if "ResearchPairedProviderQualityReport" in path.read_text(encoding="utf-8")
        )

        self.assertEqual(
            readers,
            [
                "BrainResponse.py",
                "PairedProviderQualityEvents.py",
                "ResearchPairedProviderQualityEvaluator.py",
                "ResearchPairedProviderQualityReport.py",
                "ResponseComposer.py",
            ],
        )


class RecordingRunManager:
    def __init__(self, runs) -> None:
        self.runs = list(runs)
        self.list_calls = 0

    def list(self):
        self.list_calls += 1
        return list(self.runs)


class ApplicationServiceTests(unittest.TestCase):
    def test_the_intent_is_exact_and_the_response_carries_the_report(self) -> None:
        manager = RecordingRunManager([paired_run()])
        service = PairedProviderQualityApplicationService(  # type: ignore[arg-type]
            manager, ResponseComposer()
        )
        request = BrainRequest(
            message="report",
            source="test",
            metadata={"intent": PAIRED_PROVIDER_QUALITY_REPORT_INTENT},
        )

        response = service.process_report(request)

        self.assertTrue(response.success)
        self.assertEqual(response.intent, "paired_provider_quality")
        self.assertIsInstance(
            response.research_paired_provider_quality,
            ResearchPairedProviderQualityReport,
        )
        self.assertEqual(manager.list_calls, 1)
        self.assertTrue(service.is_report_request(request))
        self.assertFalse(
            service.is_report_request(
                BrainRequest(
                    message="report",
                    source="test",
                    metadata={"intent": "provider_quality_report"},
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
