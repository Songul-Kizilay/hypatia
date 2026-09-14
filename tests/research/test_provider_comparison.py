"""Asking both providers the same question, without teaching anything to choose.

The interesting result of this milestone is how little it needed. A comparison
turned out to be two ordinary discovery steps in one plan: the question already
belongs to the run rather than to a step, so both sides ask the same thing by
construction; the provider is already digest-bound; discovery already costs one
network operation each; and one advance has always attempted exactly one step.
No comparison execution engine exists because none was required.

So most of what follows guards the things that would quietly turn a comparison
into a policy — a merged ranking, a winner, a second request under one charge, a
button that skips the preview — and the honest reporting of a comparison that is
only half finished.
"""

from __future__ import annotations

import ast
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.ProviderComparisonRequest import ProviderComparisonRequest
from research.ResearchCapabilityCost import cost_for
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchPlanDigest import canonical_plan_bytes, plan_digest
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchProviderComparisonBuilder import (
    ResearchProviderComparisonBuilder,
)
from research.ResearchProviderComparisonReport import (
    ResearchProviderComparisonReport,
)
from research.ResearchProviderComparisonSide import ResearchProviderComparisonSide
from research.ResearchQueryCategory import ResearchQueryCategory
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from tests.SourceVocabulary import mentions, working_vocabulary

REQUEST_SOURCE = (SRC_DIR / "research" / "ProviderComparisonRequest.py").read_text(
    encoding="utf-8"
)
BUILDER_SOURCE = (
    SRC_DIR / "research" / "ResearchProviderComparisonBuilder.py"
).read_text(encoding="utf-8")
REPORT_SOURCE = (
    SRC_DIR / "research" / "ResearchProviderComparisonReport.py"
).read_text(encoding="utf-8")
SERVICE_SOURCE = (
    SRC_DIR / "cognition" / "ProviderComparisonApplicationService.py"
).read_text(encoding="utf-8")
WINDOW_SOURCE = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
    encoding="utf-8"
)
CONTROLLER_SOURCE = (SRC_DIR / "desktop" / "DesktopController.py").read_text(
    encoding="utf-8"
)

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
KEYWORD_QUESTION = "Craft CMS remote code execution"
CVE_QUESTION = "CVE-2025-29927"


def draft_service() -> ResearchPlanDraftService:
    return ResearchPlanDraftService(id_factory=lambda: "plan-1", clock=lambda: NOW)


def comparison_plan(question: str = KEYWORD_QUESTION, **kwargs: object) -> object:
    preview = draft_service().preview(
        question, ProviderComparisonRequest(**kwargs).step_drafts()
    )
    assert preview.allowed, preview.reason
    return preview.plan


def candidate(url: str, title: str) -> ResearchSourceCandidate:
    return ResearchSourceCandidate(url=url, title=title, snippet="")


def discovery(
    number: int,
    provider: str,
    question: str,
    *candidates: ResearchSourceCandidate,
) -> ResearchSourceDiscoveryRecord:
    return ResearchSourceDiscoveryRecord(
        f"discovery-{number}", question, provider, tuple(candidates), NOW
    )


def run(
    *discoveries: ResearchSourceDiscoveryRecord,
    question: str = KEYWORD_QUESTION,
    failures: tuple[ResearchFailureRecord, ...] = (),
) -> ResearchRun:
    return ResearchRun(
        run_id="run-1",
        question=question,
        status=ResearchRunStatus.COLLECTING,
        sources=(),
        failures=failures,
        created_at=NOW,
        updated_at=NOW,
        discoveries=tuple(discoveries),
    )


def side_of(
    report: ResearchProviderComparisonReport, provider: str
) -> ResearchProviderComparisonSide:
    [side] = [entry for entry in report.sides if entry.provider == provider]
    return side


class PlanningTests(unittest.TestCase):
    def test_a_comparison_is_two_ordinary_discovery_steps(self) -> None:
        plan = comparison_plan()

        self.assertEqual(len(plan.steps), 2)
        for step in plan.steps:
            with self.subTest(step=step.step_id):
                self.assertIs(
                    step.capability, ResearchPlanStepCapability.SOURCE_DISCOVERY
                )

    def test_one_step_names_each_provider_and_no_third_exists(self) -> None:
        plan = comparison_plan()

        self.assertEqual(
            [step.discovery_provider for step in plan.steps],
            [
                ResearchDiscoveryProviderName.CROSSREF,
                ResearchDiscoveryProviderName.NVD,
            ],
        )

    def test_both_sides_ask_the_same_question_by_construction(self) -> None:
        """The question belongs to the run, not to a step, so it cannot diverge."""
        step_source = (
            SRC_DIR / "research" / "SourceDiscoveryStepOperation.py"
        ).read_text(encoding="utf-8")
        vocabulary = working_vocabulary(step_source, "run")

        self.assertIn("question", vocabulary)
        for step in comparison_plan().steps:
            with self.subTest(step=step.step_id):
                self.assertFalse(hasattr(step, "question"))

    def test_a_comparison_is_between_exactly_two_providers(self) -> None:
        for providers in (
            (ResearchDiscoveryProviderName.NVD,),
            (
                ResearchDiscoveryProviderName.NVD,
                ResearchDiscoveryProviderName.CROSSREF,
                ResearchDiscoveryProviderName.NVD,
            ),
            (),
        ):
            with self.subTest(providers=providers):
                with self.assertRaises(ResearchError):
                    ProviderComparisonRequest(providers=providers)

    def test_a_comparison_needs_two_different_providers(self) -> None:
        with self.assertRaises(ResearchError):
            ProviderComparisonRequest(
                providers=(
                    ResearchDiscoveryProviderName.NVD,
                    ResearchDiscoveryProviderName.NVD,
                )
            )

    def test_building_the_request_reaches_no_provider(self) -> None:
        """Calls and imports, not words.

        The step instruction a person reads legitimately contains `Discover`,
        so searching the text would fail on the very sentence describing what
        the approved step will later do. What must be absent is a call.
        """
        tree = ast.parse(REQUEST_SOURCE)
        # Both call shapes, and the bare names themselves. Collecting only
        # attribute calls let `open` reach this module as a plain reference
        # without the guard noticing, which is the difference between checking
        # that nothing is reached and checking that nothing is reached *through
        # an attribute*.
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        } | {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        imported = {
            item.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for item in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }

        for forbidden in ("discover", "open", "urlopen", "fetch", "process"):
            with self.subTest(never_called=forbidden):
                self.assertNotIn(forbidden, called)
        for forbidden in ("urllib", "http", "socket", "requests", "llm"):
            with self.subTest(never_imported=forbidden):
                self.assertNotIn(forbidden, imported)

    def test_no_comparison_execution_engine_was_built(self) -> None:
        """Two ordinary steps were enough; a second engine would be a second path."""
        for name in ("ComparisonExecutor", "ComparisonEngine", "ComparisonRunner"):
            with self.subTest(absent=name):
                self.assertEqual(list(SRC_DIR.rglob(f"*{name}*.py")), [])


class AuthorizationTests(unittest.TestCase):
    def test_the_digest_covers_both_provider_steps(self) -> None:
        canonical = canonical_plan_bytes(comparison_plan())

        self.assertIn(b"crossref", canonical)
        self.assertIn(b"nvd", canonical)
        self.assertIn(b"discovery_provider", canonical)

    def test_swapping_the_providers_changes_the_digest(self) -> None:
        forward = plan_digest(comparison_plan())
        reversed_pair = plan_digest(
            comparison_plan(
                providers=(
                    ResearchDiscoveryProviderName.NVD,
                    ResearchDiscoveryProviderName.CROSSREF,
                )
            )
        )

        self.assertNotEqual(forward, reversed_pair)

    def test_changing_the_question_changes_the_digest(self) -> None:
        self.assertNotEqual(
            plan_digest(comparison_plan(KEYWORD_QUESTION)),
            plan_digest(comparison_plan(CVE_QUESTION)),
        )

    def test_dropping_one_side_changes_the_digest(self) -> None:
        """An approval for two providers must not authorize only one."""
        both = comparison_plan()
        single = draft_service().preview(
            KEYWORD_QUESTION,
            (ProviderComparisonRequest().step_drafts()[0],),
        )

        assert single.plan is not None
        self.assertNotEqual(plan_digest(both), plan_digest(single.plan))

    def test_replacing_a_provider_changes_the_digest(self) -> None:
        both = plan_digest(comparison_plan())
        doubled_nvd = draft_service().preview(
            KEYWORD_QUESTION,
            tuple(
                ProviderComparisonRequest(
                    providers=(
                        ResearchDiscoveryProviderName.NVD,
                        ResearchDiscoveryProviderName.CROSSREF,
                    )
                ).step_drafts()
            ),
        )

        assert doubled_nvd.plan is not None
        self.assertNotEqual(both, plan_digest(doubled_nvd.plan))

    def test_the_preview_names_both_providers_and_the_question(self) -> None:
        from brain.BrainRequest import BrainRequest
        from cognition.ResearchPlanPreviewApplicationService import (
            ResearchPlanPreviewApplicationService,
        )
        from response.ResponseComposer import ResponseComposer

        service = ResearchPlanPreviewApplicationService(ResponseComposer())
        response = service.process_draft_preview(
            BrainRequest(
                message="Preview provider comparison plan",
                metadata={
                    "intent": "research_plan_draft_preview",
                    "research_plan_question": KEYWORD_QUESTION,
                    "research_plan_steps": ProviderComparisonRequest().step_drafts(),
                },
            )
        )

        self.assertIn(KEYWORD_QUESTION, response.message)
        self.assertIn("Crossref", response.message)
        self.assertIn("NVD", response.message)
        self.assertIn("Steps: 2", response.message)
        self.assertIn("Execution: not started", response.message)


class BudgetTests(unittest.TestCase):
    def test_each_discovery_step_costs_its_own_network_operation(self) -> None:
        """Two providers mean two operations. Never one charge for two requests."""
        cost = cost_for(ResearchPlanStepCapability.SOURCE_DISCOVERY)

        self.assertEqual(cost.network_operations, 1)
        self.assertEqual(len(comparison_plan().steps), 2)

    def test_the_pair_costs_two_network_operations_in_total(self) -> None:
        total = sum(
            cost_for(step.capability).network_operations
            for step in comparison_plan().steps
        )

        self.assertEqual(total, 2)

    def test_nothing_in_the_comparison_path_widens_a_budget(self) -> None:
        for name, text in (
            ("request", REQUEST_SOURCE),
            ("builder", BUILDER_SOURCE),
            ("service", SERVICE_SOURCE),
        ):
            for forbidden in (
                "budget",
                "allowance",
                "max_network",
                "ResearchAutonomyBudget",
            ):
                with self.subTest(module=name, forbidden=forbidden):
                    self.assertNotIn(forbidden, text)


class SideBySideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ResearchProviderComparisonBuilder()

    def test_both_sides_render_separately_with_their_own_ranks(self) -> None:
        report = self.builder.build(
            run(
                discovery(
                    1,
                    "crossref",
                    KEYWORD_QUESTION,
                    candidate("https://doi.org/10.1/a", "An unrelated survey"),
                    candidate(
                        "https://doi.org/10.1/b", "Craft CMS remote code execution"
                    ),
                ),
                discovery(
                    2,
                    "nvd",
                    KEYWORD_QUESTION,
                    candidate(
                        "https://nvd.nist.gov/vuln/detail/CVE-2020-15189",
                        "CVE-2020-15189: SOY CMS remote code execution",
                    ),
                ),
            )
        )

        crossref = side_of(report, "crossref")
        nvd = side_of(report, "nvd")
        self.assertEqual(crossref.candidate_count, 2)
        self.assertEqual(nvd.candidate_count, 1)
        self.assertTrue(report.complete)

    def test_each_side_is_ranked_within_itself_and_never_across(self) -> None:
        """A rank across providers would be a verdict wearing a sort order."""
        report = self.builder.build(
            run(
                discovery(
                    1,
                    "crossref",
                    KEYWORD_QUESTION,
                    candidate("https://doi.org/10.1/a", "An unrelated survey"),
                ),
                discovery(
                    2,
                    "nvd",
                    KEYWORD_QUESTION,
                    candidate(
                        "https://nvd.nist.gov/vuln/detail/CVE-1",
                        "Craft CMS remote code execution",
                    ),
                ),
            )
        )

        for side in report.sides:
            with self.subTest(provider=side.provider):
                self.assertEqual(
                    [entry.relevance_rank for entry in side.ranked],
                    list(range(1, side.candidate_count + 1)),
                )

    def test_provider_rank_survives_alongside_relevance_rank(self) -> None:
        report = self.builder.build(
            run(
                discovery(
                    1,
                    "crossref",
                    KEYWORD_QUESTION,
                    candidate("https://doi.org/10.1/a", "An unrelated survey"),
                    candidate(
                        "https://doi.org/10.1/b", "Craft CMS remote code execution"
                    ),
                ),
            )
        )

        crossref = side_of(report, "crossref")
        self.assertEqual(crossref.ranked[0].provider_rank, 2)
        self.assertEqual(crossref.ranked[0].relevance_rank, 1)

    def test_the_question_category_is_shown_and_shared(self) -> None:
        report = self.builder.build(
            run(
                discovery(1, "crossref", CVE_QUESTION),
                discovery(2, "nvd", CVE_QUESTION),
                question=CVE_QUESTION,
            )
        )

        self.assertIs(report.category, ResearchQueryCategory.EXACT_CVE)
        self.assertIn("Exact CVE lookup", "\n".join(report.lines()))

    def test_vulnerability_metadata_stays_on_the_side_that_has_it(self) -> None:
        """No fake symmetry: an empty CVE column beside a paper reads as missing."""
        from research.ResearchVulnerabilityRecord import ResearchVulnerabilityRecord

        report = self.builder.build(
            run(
                discovery(
                    1,
                    "crossref",
                    KEYWORD_QUESTION,
                    candidate("https://doi.org/10.1/a", "A paper"),
                ),
                discovery(
                    2,
                    "nvd",
                    KEYWORD_QUESTION,
                    ResearchSourceCandidate(
                        url="https://nvd.nist.gov/vuln/detail/CVE-2020-15189",
                        title="CVE-2020-15189: remote code execution",
                        snippet="",
                        vulnerability=ResearchVulnerabilityRecord(
                            cve_id="CVE-2020-15189", status="Modified"
                        ),
                    ),
                ),
            )
        )

        self.assertIsNone(side_of(report, "crossref").ranked[0].candidate.vulnerability)
        self.assertIn("CVE: CVE-2020-15189", "\n".join(report.lines()))


class PartialStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ResearchProviderComparisonBuilder()

    def test_only_crossref_complete_reads_as_partial(self) -> None:
        report = self.builder.build(run(discovery(1, "crossref", KEYWORD_QUESTION)))

        self.assertTrue(report.partial)
        self.assertFalse(report.complete)
        self.assertTrue(side_of(report, "crossref").completed)
        self.assertFalse(side_of(report, "nvd").completed)

    def test_only_nvd_complete_reads_as_partial(self) -> None:
        report = self.builder.build(run(discovery(1, "nvd", KEYWORD_QUESTION)))

        self.assertTrue(report.partial)
        self.assertFalse(side_of(report, "crossref").completed)

    def test_a_pending_side_is_never_rendered_as_an_empty_result(self) -> None:
        report = self.builder.build(run(discovery(1, "crossref", KEYWORD_QUESTION)))

        rendered = "\n".join(report.lines())
        self.assertIn("nvd: pending", rendered)
        self.assertIn("not the same as returning nothing", rendered)

    def test_a_provider_that_returned_nothing_says_so_rather_than_pending(
        self,
    ) -> None:
        """Asked and answered nothing is a result. Not asked is not."""
        report = self.builder.build(
            run(
                discovery(1, "crossref", KEYWORD_QUESTION),
                discovery(2, "nvd", KEYWORD_QUESTION),
            )
        )

        self.assertTrue(report.complete)
        self.assertIn("returned no candidates", "\n".join(report.lines()))

    def test_a_failed_side_never_erases_the_successful_one(self) -> None:
        report = self.builder.build(
            run(
                discovery(
                    1,
                    "crossref",
                    KEYWORD_QUESTION,
                    candidate("https://doi.org/10.1/a", "Craft CMS RCE"),
                ),
                failures=(
                    ResearchFailureRecord(
                        stage="source_discovery",
                        reason="Research source discovery failed.",
                        occurred_at=NOW,
                    ),
                ),
            )
        )

        self.assertEqual(side_of(report, "crossref").candidate_count, 1)
        self.assertEqual(report.failed_discovery_count, 1)

    def test_a_failure_is_not_attributed_to_a_provider_it_cannot_name(self) -> None:
        """The audit record says a discovery failed, never which one."""
        report = self.builder.build(
            run(
                discovery(1, "crossref", KEYWORD_QUESTION),
                failures=(
                    ResearchFailureRecord(
                        stage="source_discovery",
                        reason="Research source discovery failed.",
                        occurred_at=NOW,
                    ),
                ),
            )
        )

        rendered = "\n".join(report.lines())
        self.assertIn("provider is unavailable in legacy audit records", rendered)
        self.assertIn("nvd: pending", rendered)

    def test_a_provider_attributed_failure_marks_only_that_side_failed(self) -> None:
        report = self.builder.build(
            run(
                discovery(1, "crossref", KEYWORD_QUESTION),
                failures=(
                    ResearchFailureRecord(
                        stage="source_discovery",
                        reason="Research source discovery failed.",
                        occurred_at=NOW,
                        provider="nvd",
                    ),
                ),
            )
        )

        self.assertTrue(side_of(report, "nvd").failed)
        self.assertFalse(side_of(report, "crossref").failed)
        self.assertIn("nvd: failed", "\n".join(report.lines()))
        self.assertEqual(report.unattributed_failed_discovery_count, 0)

    def test_neither_side_run_reads_as_not_started(self) -> None:
        report = self.builder.build(run())

        self.assertFalse(report.complete)
        self.assertFalse(report.partial)
        self.assertIn("not started", "\n".join(report.lines()))

    def test_re_asking_a_provider_replaces_its_side_rather_than_adding_one(
        self,
    ) -> None:
        report = self.builder.build(
            run(
                discovery(
                    1,
                    "crossref",
                    KEYWORD_QUESTION,
                    candidate("https://doi.org/10.1/a", "Older"),
                ),
                discovery(
                    2,
                    "crossref",
                    KEYWORD_QUESTION,
                    candidate("https://doi.org/10.1/b", "Newer"),
                ),
            )
        )

        crossref = side_of(report, "crossref")
        self.assertEqual(len(report.sides), 2)
        self.assertEqual(crossref.discovery_id, "discovery-2")


class ProviderProvenanceNameTests(unittest.TestCase):
    """A discovery must be found under the name the plan authorized.

    The provider name written into a discovery record and the name the closed
    vocabulary uses are the same identity, and they were briefly two different
    strings: Crossref recorded `crossref-rest-v1` while the comparison and
    paired-quality reports looked for `crossref`. A Crossref search that had
    genuinely run was therefore reported as never having happened, which would
    have quietly emptied the measurement this whole evaluation depends on.
    """

    def test_each_provider_records_itself_under_its_authorized_name(self) -> None:
        from research.CrossrefResearchSourceDiscoveryProvider import (
            CROSSREF_PROVIDER_NAME,
        )
        from research.NvdResearchSourceDiscoveryProvider import NVD_PROVIDER_NAME

        self.assertEqual(
            CROSSREF_PROVIDER_NAME, ResearchDiscoveryProviderName.CROSSREF.value
        )
        self.assertEqual(NVD_PROVIDER_NAME, ResearchDiscoveryProviderName.NVD.value)

    def test_a_real_crossref_discovery_is_found_by_the_comparison(self) -> None:
        from research.CrossrefResearchSourceDiscoveryProvider import (
            CROSSREF_PROVIDER_NAME,
        )
        from research.NvdResearchSourceDiscoveryProvider import NVD_PROVIDER_NAME

        report = ResearchProviderComparisonBuilder().build(
            run(
                discovery(
                    1,
                    CROSSREF_PROVIDER_NAME,
                    KEYWORD_QUESTION,
                    candidate("https://doi.org/10.1/a", "A paper"),
                ),
                discovery(
                    2,
                    NVD_PROVIDER_NAME,
                    KEYWORD_QUESTION,
                    candidate(
                        "https://nvd.nist.gov/vuln/detail/CVE-1", "A vulnerability"
                    ),
                ),
            )
        )

        self.assertTrue(report.complete)
        for provider in ("crossref", "nvd"):
            with self.subTest(provider=provider):
                self.assertTrue(side_of(report, provider).completed)
                self.assertEqual(side_of(report, provider).candidate_count, 1)

    def test_a_real_paired_run_is_eligible_for_paired_quality(self) -> None:
        from research.CrossrefResearchSourceDiscoveryProvider import (
            CROSSREF_PROVIDER_NAME,
        )
        from research.NvdResearchSourceDiscoveryProvider import NVD_PROVIDER_NAME
        from research.ResearchPairedProviderQualityEvaluator import (
            ResearchPairedProviderQualityEvaluator,
        )

        report = ResearchPairedProviderQualityEvaluator().evaluate(
            [
                run(
                    discovery(
                        1,
                        CROSSREF_PROVIDER_NAME,
                        KEYWORD_QUESTION,
                        candidate("https://doi.org/10.1/a", "A paper"),
                    ),
                    discovery(
                        2,
                        NVD_PROVIDER_NAME,
                        KEYWORD_QUESTION,
                        candidate(
                            "https://nvd.nist.gov/vuln/detail/CVE-1",
                            "A vulnerability",
                        ),
                    ),
                )
            ]
        )

        self.assertEqual(report.eligible_pair_count, 1)


class NoWinnerTests(unittest.TestCase):
    def test_no_winner_field_exists_in_the_report_or_the_side(self) -> None:
        for name, text in (
            ("report", REPORT_SOURCE),
            (
                "side",
                (SRC_DIR / "research" / "ResearchProviderComparisonSide.py").read_text(
                    encoding="utf-8"
                ),
            ),
        ):
            tree = ast.parse(text)
            fields = {
                node.target.id
                for node in ast.walk(tree)
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
            }
            names = {
                node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
            } | {
                node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
            }
            for forbidden in ("winner", "best", "preferred", "recommended"):
                with self.subTest(module=name, forbidden=forbidden):
                    self.assertNotIn(forbidden, fields)
                    self.assertNotIn(forbidden, names)
            # A candidate's own relevance score is read and shown; what must
            # not exist is a score belonging to a provider.
            for forbidden in ("score", "provider_score", "quality_score", "rating"):
                with self.subTest(module=name, absent_field=forbidden):
                    self.assertNotIn(forbidden, fields)

    def test_the_report_says_neither_provider_was_judged_better(self) -> None:
        report = ResearchProviderComparisonBuilder().build(
            run(
                discovery(1, "crossref", KEYWORD_QUESTION),
                discovery(2, "nvd", KEYWORD_QUESTION),
            )
        )

        rendered = "\n".join(report.lines())
        self.assertIn("No provider was judged better", rendered)
        self.assertIn("never merged into one order", rendered)
        self.assertIn("no default was changed", rendered)

    def test_the_two_lists_are_never_merged(self) -> None:
        vocabulary = working_vocabulary(BUILDER_SOURCE, "build", "_side")

        for forbidden in ("merge", "combine", "interleave", "winner", "prefer"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])


class ReadOnlyTests(unittest.TestCase):
    def test_viewing_a_comparison_changes_nothing_in_the_run(self) -> None:
        one = run(
            discovery(1, "crossref", KEYWORD_QUESTION),
            discovery(2, "nvd", KEYWORD_QUESTION),
        )
        before = (one.discoveries, one.sources, one.assessments, one.status)

        ResearchProviderComparisonBuilder().build(one)

        self.assertEqual(
            (one.discoveries, one.sources, one.assessments, one.status), before
        )

    def test_the_comparison_path_reaches_no_network_and_no_model(self) -> None:
        for name, text in (
            ("builder", BUILDER_SOURCE),
            ("service", SERVICE_SOURCE),
            ("request", REQUEST_SOURCE),
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

    def test_the_service_holds_no_provider_and_no_write_path(self) -> None:
        for forbidden in (
            "Crossref",
            "Nvd",
            "discover(",
            "record_source_assessment",
            "add_discovery",
            "add_evidence",
            "record_claim",
            "process_advance",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, SERVICE_SOURCE)

    def test_the_comparison_creates_no_assessment_of_providers(self) -> None:
        for forbidden in ("usefulness", "applicability", "independence", "trust"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, BUILDER_SOURCE)
                self.assertNotIn(forbidden, REPORT_SOURCE)


class SurfaceTests(unittest.TestCase):
    def test_the_compare_button_reaches_a_preview_and_not_a_provider(self) -> None:
        """The invariant: Compare must not bypass preview and approval."""
        vocabulary = working_vocabulary(
            WINDOW_SOURCE, "_preview_provider_comparison_plan"
        )

        self.assertIn("preview_provider_comparison_plan", vocabulary)
        # The docstring explains that two advances follow, so the guard reads
        # what the function does rather than what it says about itself.
        for forbidden in (
            "discover_research_sources",
            "advance",
            "process_advance",
            "start_execution",
            "confirm",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, vocabulary)

    def test_the_controller_compare_call_only_previews(self) -> None:
        start = CONTROLLER_SOURCE.index("def preview_provider_comparison_plan")
        end = CONTROLLER_SOURCE.index("def report_provider_comparison")
        method = CONTROLLER_SOURCE[start:end]

        self.assertIn("research_plan_draft_preview", method)
        for forbidden in ("research_source_discover", "execution_advance"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, method)

    def test_the_panel_promises_two_presses_and_no_winner(self) -> None:
        self.assertIn("two separate presses of Advance", WINDOW_SOURCE)
        self.assertIn("names no winner", WINDOW_SOURCE)
        self.assertIn("merges", WINDOW_SOURCE)
        self.assertIn("contacts nobody", WINDOW_SOURCE)


class BoundaryTests(unittest.TestCase):
    #: The queue intents left this list in v0.3.278, when the operator got
    #: controls for them. They never belonged to it on their own merits: what
    #: this guards is research running without anybody asking each time, and
    #: creating, listing, pausing, resuming and cancelling a queued task reach
    #: no provider at all. Only two things run research — the autonomy run
    #: below, which stays unreachable, and the worker cycle, which is one press
    #: for one turn.
    AUTONOMY_INTENTS = ("research_autonomy_run",)

    def test_comparing_providers_opened_no_autonomy(self) -> None:
        desktop = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SRC_DIR / "desktop").rglob("*.py")
        )

        for intent in self.AUTONOMY_INTENTS:
            with self.subTest(unreachable=intent):
                self.assertNotIn(intent, desktop)

    def test_only_the_operator_path_builds_a_comparison_request(self) -> None:
        """Curiosity, reflection, calibration and the quality report cannot."""
        builders = sorted(
            path.name
            for path in SRC_DIR.rglob("*.py")
            if "ProviderComparisonRequest" in path.read_text(encoding="utf-8")
        )

        self.assertEqual(
            builders, ["DesktopController.py", "ProviderComparisonRequest.py"]
        )

    def test_the_comparison_report_is_derived_and_has_no_store(self) -> None:
        stores = [
            path.name
            for path in SRC_DIR.rglob("*.py")
            if "ProviderComparison" in path.read_text(encoding="utf-8")
            and "Store" in path.name
        ]

        self.assertEqual(stores, [])


if __name__ == "__main__":
    unittest.main()
