"""Reflection reports how a run went, never what its subject turned out to be.

The distinction these tests police is the one that matters: a reflection finding
is an observation about our own process — a recorded failure, a contradiction, a
revised belief, a thin claim — and never a conclusion about the world. A
reflection that could say "and therefore the claim is true" would be a research
engine wearing a different name.

They also police the second rule: there is no recursive reflection. Only a
research run can be reflected on, a stored report is not a run, and no intent
accepts one.

Time is injected and no test sleeps or touches a network.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ReflectionApplicationService import ReflectionApplicationService
from cognition.ReflectionEvents import REFLECTION_PRODUCED, REFLECTION_STORED
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Bootstrap import Bootstrap
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.JsonFileReflectionReportStore import (
    MAX_REFLECTION_STORE_REPORTS,
    JsonFileReflectionReportStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ReflectionFindingKind import ReflectionFindingKind, order_for
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchReflectionFinding import ResearchReflectionFinding
from research.ResearchReflectionGenerator import ResearchReflectionGenerator
from research.ResearchReflectionReport import (
    MAX_REFLECTION_FINDINGS,
    ResearchReflectionReport,
)
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceUsefulness import ResearchSourceUsefulness
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the ring system have a measured age?"
START = datetime(2026, 8, 23, tzinfo=UTC)
FETCHED = datetime(2026, 8, 1, tzinfo=UTC)


class StubClock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        value = self.now
        self.now += timedelta(seconds=1)
        return value


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


class InMemoryHypothesisStore:
    def __init__(self, records: list[ResearchHypothesis] | None = None) -> None:
        self.records = list(records or [])
        self.save_calls = 0

    def load(self) -> list[ResearchHypothesis]:
        return list(self.records)

    def save(self, records: list[ResearchHypothesis]) -> None:
        self.save_calls += 1
        self.records = list(records)


class UnreadableHypothesisStore(InMemoryHypothesisStore):
    def load(self) -> list[ResearchHypothesis]:
        raise ResearchError("PRIVATE-HYPOTHESIS-PATH is unreadable.")


class ReflectionFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        self.report_path = self.root / "reflections.json"
        document = self.root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        self.knowledge_engine = KnowledgeEngine()
        self.knowledge_engine.load(document)
        self.manager = ResearchRunManager(JsonFileResearchRunStore(self.run_path))
        self.manager.load()
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            InMemoryContentStore(),  # type: ignore[arg-type]
        )
        self.clock = StubClock()
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.generator = ResearchReflectionGenerator()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def service(
        self,
        persist: bool = True,
        hypothesis_store: InMemoryHypothesisStore | None = None,
    ) -> ReflectionApplicationService:
        return ReflectionApplicationService(
            self.manager,
            ResponseComposer(),
            report_store=(
                JsonFileReflectionReportStore(self.report_path) if persist else None
            ),
            hypothesis_store=hypothesis_store,
            event_bus=self.event_bus,
            clock=self.clock,
        )

    def new_run(self) -> str:
        return self.manager.create(QUESTION).run_id

    def accept_source(self, run_id: str, slug: str) -> str:
        result = self.acceptance.accept(
            ResearchSource(
                url=f"https://example.test/{slug}",
                title=f"Source {slug}",
                content="Saturn has a prominent ring system with a debated age.",
                content_type="text/html",
                fetched_at=FETCHED,
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

    def sourced_run(self, slug: str = "a") -> tuple[str, str, str]:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, slug)
        return run_id, document_id, self.add_evidence(run_id, document_id)

    @staticmethod
    def hypothesis(
        run_id: str,
        supporting_evidence_ids: tuple[str, ...],
        *,
        test_evidence_ids: tuple[str, ...] = (),
        hypothesis_id: str = "hypothesis-rings-age",
    ) -> ResearchHypothesis:
        return ResearchHypothesis(
            hypothesis_id=hypothesis_id,
            run_id=run_id,
            statement="The ring system formed recently.",
            discriminating_test="Older dust would count against a recent origin.",
            supporting_evidence_ids=supporting_evidence_ids,
            discriminating_test_evidence_ids=test_evidence_ids,
            created_at=START,
            updated_at=START,
        )

    def reflect(self, run_id: str) -> ResearchReflectionReport:
        return self.generator.reflect(self.manager.get(run_id), START)

    def kinds(self, run_id: str) -> list[ReflectionFindingKind]:
        return [finding.kind for finding in self.reflect(run_id).findings]

    def request(self, intent: str, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="Reflection",
            metadata={"intent": intent, **metadata},
        )

    def named(self, name: str) -> list[Event]:
        return [event for event in self.events if event.name == name]


class ReflectionDerivationTests(ReflectionFixture):
    def test_a_recorded_failure_is_reported_as_a_failure(self) -> None:
        run_id = self.new_run()
        self.manager.record_failure(run_id, "source_fetch", "Refused before request.")

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.FAILED)

        self.assertEqual(len(findings), 1)
        self.assertIn("source_fetch", findings[0].detail)
        self.assertIn("Refused before request.", findings[0].detail)

    def test_a_claim_revision_names_each_changed_dimension(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        run = self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
        )
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings are young.",
            ResearchEpistemicState.LIKELY,
            ResearchClaimConfidence.HIGH,
            supersedes_claim_id=run.claims[-1].claim_id,
        )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.REVISED_BELIEF)

        self.assertEqual(len(findings), 1)
        self.assertIn(
            "epistemic state from hypothesis to likely",
            findings[0].detail,
        )
        self.assertIn(
            "authored confidence from low to high",
            findings[0].detail,
        )
        self.assertIn("authored wording", findings[0].detail)

    def test_a_confidence_only_claim_revision_does_not_invent_other_changes(
        self,
    ) -> None:
        run_id, _, evidence_id = self.sourced_run()
        run = self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
        )
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.HIGH,
            supersedes_claim_id=run.claims[-1].claim_id,
        )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.REVISED_BELIEF)

        self.assertEqual(len(findings), 1)
        self.assertIn("authored confidence from low to high", findings[0].detail)
        self.assertNotIn("epistemic state", findings[0].detail)
        self.assertNotIn("authored wording", findings[0].detail)

    def test_a_provenance_only_claim_revision_names_sources_and_evidence(self) -> None:
        run_id, _, first_evidence = self.sourced_run("claim-first")
        second_document = self.accept_source(run_id, "claim-second")
        second_evidence = self.add_evidence(run_id, second_document)
        run = self.manager.record_claim(
            run_id,
            [first_evidence],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        self.manager.record_claim(
            run_id,
            [second_evidence],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
            supersedes_claim_id=run.claims[-1].claim_id,
        )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.REVISED_BELIEF)

        self.assertEqual(len(findings), 1)
        self.assertIn("linked sources and linked evidence", findings[0].detail)
        self.assertNotIn("epistemic state", findings[0].detail)
        self.assertNotIn("confidence", findings[0].detail)

    def test_a_wording_only_claim_revision_does_not_invent_a_belief_change(
        self,
    ) -> None:
        run_id, _, evidence_id = self.sourced_run()
        run = self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings could be young.",
            ResearchEpistemicState.HYPOTHESIS,
            supersedes_claim_id=run.claims[-1].claim_id,
        )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.REVISED_BELIEF)

        self.assertEqual(len(findings), 1)
        self.assertIn("authored wording", findings[0].detail)
        self.assertIn(
            "no structured claim judgement or provenance changed",
            findings[0].detail,
        )
        self.assertNotIn("what was believed", findings[0].detail)

    def test_an_identical_claim_replacement_is_not_called_a_belief_change(
        self,
    ) -> None:
        run_id, _, evidence_id = self.sourced_run()
        run = self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
            supersedes_claim_id=run.claims[-1].claim_id,
        )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.REVISED_BELIEF)

        self.assertEqual(len(findings), 1)
        self.assertIn("replaced this claim record", findings[0].detail)
        self.assertIn("no authored wording", findings[0].detail)
        self.assertNotIn("what was believed", findings[0].detail)

    def test_a_superseded_assessment_is_reported_as_a_revised_belief(self) -> None:
        run_id, document_id, evidence_id = self.sourced_run()
        run = self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Self-published.",
            information_trust=ResearchInformationTrust.LOW,
        )
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Actually peer reviewed.",
            supersedes_assessment_id=run.assessments[-1].assessment_id,
            information_trust=ResearchInformationTrust.HIGH,
        )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.REVISED_BELIEF)

        self.assertEqual(len(findings), 1)
        self.assertIn("information trust from low to high", findings[0].detail)

    def test_an_independence_revision_does_not_claim_trust_changed(self) -> None:
        run_id, document_id, evidence_id = self.sourced_run()
        run = self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Independent analysis.",
            information_trust=ResearchInformationTrust.HIGH,
            independence=ResearchSourceIndependence.INDEPENDENT,
        )
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Derived analysis.",
            supersedes_assessment_id=run.assessments[-1].assessment_id,
            information_trust=ResearchInformationTrust.HIGH,
            independence=ResearchSourceIndependence.DERIVATIVE,
        )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.REVISED_BELIEF)

        self.assertEqual(len(findings), 1)
        self.assertIn(
            "independence from independent to derivative",
            findings[0].detail,
        )
        self.assertNotIn("information trust", findings[0].detail)

    def test_combined_assessment_revision_names_each_changed_dimension(self) -> None:
        run_id, document_id, evidence_id = self.sourced_run()
        run = self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Initial review.",
            information_trust=ResearchInformationTrust.LOW,
            independence=ResearchSourceIndependence.INDEPENDENT,
        )
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Corrected review.",
            supersedes_assessment_id=run.assessments[-1].assessment_id,
            information_trust=ResearchInformationTrust.HIGH,
            independence=ResearchSourceIndependence.DERIVATIVE,
        )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.REVISED_BELIEF)

        self.assertEqual(len(findings), 1)
        self.assertIn("information trust from low to high", findings[0].detail)
        self.assertIn(
            "independence from independent to derivative",
            findings[0].detail,
        )

    def test_reflection_names_every_structured_assessment_dimension_that_changed(
        self,
    ) -> None:
        run_id, document_id, evidence_id = self.sourced_run()
        run = self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Initial structured review.",
            information_trust=ResearchInformationTrust.LOW,
            usefulness=ResearchSourceUsefulness.NOT_USEFUL,
            applicability=ResearchSourceApplicability.UNRELATED,
            independence=ResearchSourceIndependence.INDEPENDENT,
            publication_status=ResearchSourcePublicationStatus.NORMAL,
        )
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Corrected structured review.",
            supersedes_assessment_id=run.assessments[-1].assessment_id,
            information_trust=ResearchInformationTrust.HIGH,
            usefulness=ResearchSourceUsefulness.USEFUL,
            applicability=ResearchSourceApplicability.DIRECT,
            independence=ResearchSourceIndependence.DERIVATIVE,
            publication_status=ResearchSourcePublicationStatus.CORRECTED,
        )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.REVISED_BELIEF)

        self.assertEqual(len(findings), 1)
        for expected in (
            "information trust from low to high",
            "usefulness from not_useful to useful",
            "applicability from unrelated to direct",
            "independence from independent to derivative",
            "publication status from normal to corrected",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, findings[0].detail)

    def test_wording_only_revision_does_not_invent_a_structured_change(self) -> None:
        run_id, document_id, evidence_id = self.sourced_run()
        run = self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Initial wording.",
            information_trust=ResearchInformationTrust.HIGH,
            independence=ResearchSourceIndependence.INDEPENDENT,
        )
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Clearer wording.",
            supersedes_assessment_id=run.assessments[-1].assessment_id,
            information_trust=ResearchInformationTrust.HIGH,
            independence=ResearchSourceIndependence.INDEPENDENT,
        )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.REVISED_BELIEF)

        self.assertEqual(len(findings), 1)
        self.assertIn("authored wording", findings[0].detail)
        self.assertIn("no structured source judgement changed", findings[0].detail)
        self.assertNotIn("trust from", findings[0].detail)

    def test_parallel_assessments_are_not_reported_as_revisions(self) -> None:
        run_id, document_id, evidence_id = self.sourced_run()
        for trust in (
            ResearchInformationTrust.LOW,
            ResearchInformationTrust.HIGH,
        ):
            self.manager.record_source_assessment(
                run_id,
                document_id,
                [evidence_id],
                "Parallel authored view.",
                information_trust=trust,
            )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.REVISED_BELIEF)

        self.assertEqual(findings, ())

    def test_a_contradiction_is_reported_as_a_contradiction(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings are young.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        run = self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings are ancient.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        self.manager.record_claim_contradiction(
            run_id,
            [run.claims[0].claim_id, run.claims[1].claim_id],
            "These two cannot both hold.",
        )

        self.assertIn(ReflectionFindingKind.CONTRADICTION, self.kinds(run_id))

    def test_a_thin_claim_is_reported_as_weak_evidence(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings exist.",
            ResearchEpistemicState.FACT,
        )

        self.assertIn(ReflectionFindingKind.WEAK_EVIDENCE, self.kinds(run_id))

    def test_unconfirmed_independence_is_reported_as_weak_evidence(self) -> None:
        run_id, _, first_evidence = self.sourced_run("a")
        second_document = self.accept_source(run_id, "b")
        second_evidence = self.add_evidence(run_id, second_document)
        self.manager.record_claim(
            run_id,
            [first_evidence, second_evidence],
            "The rings exist.",
            ResearchEpistemicState.FACT,
        )

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.WEAK_EVIDENCE)

        self.assertTrue(
            any("independent" in finding.detail for finding in findings),
            findings,
        )

    def test_hypothesis_independence_gap_is_reflected_from_the_same_detector(
        self,
    ) -> None:
        run_id, _, first_evidence = self.sourced_run("a")
        second_document = self.accept_source(run_id, "b")
        second_evidence = self.add_evidence(run_id, second_document)
        hypothesis = self.hypothesis(
            run_id,
            (first_evidence, second_evidence),
            test_evidence_ids=(first_evidence,),
        )

        report = self.generator.reflect(
            self.manager.get(run_id),
            START,
            (hypothesis,),
        )
        weak = report.of_kind(ReflectionFindingKind.WEAK_EVIDENCE)
        questions = report.of_kind(ReflectionFindingKind.NEXT_QUESTION)

        self.assertTrue(
            any(
                finding.subject_id == hypothesis.hypothesis_id
                and "does not confirm" in finding.detail
                for finding in weak
            ),
            weak,
        )
        self.assertTrue(
            any(
                "independent source" in finding.detail
                and "ring system formed recently" in finding.detail
                for finding in questions
            ),
            questions,
        )

    def test_confirmed_hypothesis_independence_closes_the_reflection_gap(self) -> None:
        run_id, first_document, first_evidence = self.sourced_run("a")
        second_document = self.accept_source(run_id, "b")
        second_evidence = self.add_evidence(run_id, second_document)
        for document_id, evidence_id in (
            (first_document, first_evidence),
            (second_document, second_evidence),
        ):
            self.manager.record_source_assessment(
                run_id,
                document_id,
                [evidence_id],
                "This source is an independent account.",
                information_trust=ResearchInformationTrust.MEDIUM,
                independence=ResearchSourceIndependence.INDEPENDENT,
            )
        hypothesis = self.hypothesis(
            run_id,
            (first_evidence, second_evidence),
            test_evidence_ids=(first_evidence,),
        )

        report = self.generator.reflect(
            self.manager.get(run_id),
            START,
            (hypothesis,),
        )

        self.assertNotIn(
            hypothesis.hypothesis_id,
            {
                finding.subject_id
                for finding in report.of_kind(ReflectionFindingKind.WEAK_EVIDENCE)
            },
        )
        self.assertFalse(
            any(
                "independent source" in finding.detail
                for finding in report.of_kind(ReflectionFindingKind.NEXT_QUESTION)
            )
        )

    def test_unanswered_hypothesis_test_is_reflected_as_weak_evidence(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        hypothesis = self.hypothesis(run_id, (evidence_id,))

        report = self.generator.reflect(
            self.manager.get(run_id),
            START,
            (hypothesis,),
        )

        weak = report.of_kind(ReflectionFindingKind.WEAK_EVIDENCE)
        self.assertTrue(
            any(
                finding.subject_id == hypothesis.hypothesis_id
                and "addressing it" in finding.detail
                for finding in weak
            ),
            weak,
        )

    def test_an_open_claim_is_reported_as_uncertain(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
        )

        self.assertIn(ReflectionFindingKind.UNCERTAIN, self.kinds(run_id))

    def test_what_landed_is_reported_with_each_stage_kept_separate(self) -> None:
        run_id, _, _ = self.sourced_run()

        details = [
            finding.detail
            for finding in self.reflect(run_id).of_kind(ReflectionFindingKind.WORKED)
        ]

        self.assertIn("1 source accepted.", details)
        self.assertIn("1 evidence record recorded.", details)
        self.assertNotIn("1 claim authored.", details)

    def test_an_empty_run_reports_no_success_at_all(self) -> None:
        run_id = self.new_run()

        self.assertEqual(
            self.reflect(run_id).of_kind(ReflectionFindingKind.WORKED),
            (),
        )

    def test_findings_are_ordered_with_problems_before_successes(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_failure(run_id, "source_fetch", "Refused.")
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
        )

        orders = [finding.order for finding in self.reflect(run_id).findings]

        self.assertEqual(orders, sorted(orders))
        self.assertIs(
            self.reflect(run_id).findings[0].kind, ReflectionFindingKind.FAILED
        )

    def test_next_questions_come_from_curiosity_and_are_questions(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")

        findings = self.reflect(run_id).of_kind(ReflectionFindingKind.NEXT_QUESTION)

        self.assertTrue(findings)
        for finding in findings:
            self.assertTrue(finding.detail.endswith("?"), finding.detail)

    def test_successes_and_questions_are_not_counted_as_lessons(self) -> None:
        run_id, _, _ = self.sourced_run()

        report = self.reflect(run_id)

        for finding in report.lessons:
            self.assertNotIn(
                finding.kind,
                (ReflectionFindingKind.WORKED, ReflectionFindingKind.NEXT_QUESTION),
            )
        self.assertTrue(finding.is_lesson for finding in report.lessons)

    def test_the_finding_count_is_bounded(self) -> None:
        run_id = self.new_run()
        for index in range(6):
            self.accept_source(run_id, f"s{index}")
        generator = ResearchReflectionGenerator(max_findings=4)

        report = generator.reflect(self.manager.get(run_id), START)

        self.assertEqual(len(report.findings), 4)

    def test_an_out_of_range_finding_limit_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            ResearchReflectionGenerator(max_findings=MAX_REFLECTION_FINDINGS + 1)
        with self.assertRaises(ValueError):
            ResearchReflectionGenerator(max_findings=0)

    def test_reflection_carries_canonical_counts_for_that_run(self) -> None:
        run_id, _, _ = self.sourced_run()

        report = self.reflect(run_id)

        self.assertEqual(report.summary.source_count, 1)
        self.assertEqual(report.summary.evidence_count, 1)
        self.assertEqual(report.summary.claim_count, 0)

    def test_every_finding_kind_declares_a_report_order(self) -> None:
        for kind in ReflectionFindingKind:
            self.assertIsInstance(order_for(kind), int)

    def test_an_unclassified_finding_kind_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            order_for("invented_kind")  # type: ignore[arg-type]


class ReflectionIsInertTests(ReflectionFixture):
    def test_reflecting_leaves_the_run_byte_identical(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        before = self.run_path.read_bytes()
        summary_before = CanonicalResearchSummary.from_runs(self.manager.list())

        for _ in range(3):
            self.reflect(run_id)

        self.assertEqual(self.run_path.read_bytes(), before)
        self.assertEqual(
            CanonicalResearchSummary.from_runs(self.manager.list()),
            summary_before,
        )

    def test_reflection_never_promotes_an_uncertain_claim(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
        )

        self.reflect(run_id)

        claim = self.manager.get(run_id).claims[-1]
        self.assertIs(claim.epistemic_state, ResearchEpistemicState.HYPOTHESIS)

    def test_reflection_requires_an_actual_run(self) -> None:
        with self.assertRaises(ResearchError):
            self.generator.reflect("run-1", START)  # type: ignore[arg-type]

    def test_a_stored_report_cannot_itself_be_reflected_on(self) -> None:
        """The recursion guard: only a run is an acceptable subject."""
        run_id, _, _ = self.sourced_run()
        report = self.reflect(run_id)

        with self.assertRaises(ResearchError):
            self.generator.reflect(report, START)  # type: ignore[arg-type]

    def test_reflecting_on_a_report_id_is_refused_as_an_unknown_run(self) -> None:
        run_id, _, _ = self.sourced_run()
        service = self.service()
        stored = service.process_store(
            self.request("research_reflection_store", research_run_id=run_id)
        )
        assert stored.research_reflection is not None

        with self.assertRaises(ResearchError):
            service.process_preview(
                self.request(
                    "research_reflection_preview",
                    research_run_id=stored.research_reflection.report_id,
                )
            )


class ReflectionServiceTests(ReflectionFixture):
    def test_preview_reports_without_storing(self) -> None:
        run_id, _, _ = self.sourced_run()
        service = self.service()

        response = service.process_preview(
            self.request("research_reflection_preview", research_run_id=run_id)
        )

        self.assertIn("Not stored.", response.message)
        self.assertEqual(service.reports(), ())
        self.assertFalse(self.report_path.exists())

    def test_preview_reads_this_runs_persisted_hypotheses(self) -> None:
        run_id, _, first_evidence = self.sourced_run("a")
        second_document = self.accept_source(run_id, "b")
        second_evidence = self.add_evidence(run_id, second_document)
        hypothesis = self.hypothesis(
            run_id,
            (first_evidence, second_evidence),
            test_evidence_ids=(first_evidence,),
        )
        store = InMemoryHypothesisStore(
            [
                hypothesis,
                self.hypothesis(
                    "run-other",
                    (),
                    hypothesis_id="hypothesis-other-run",
                ),
            ]
        )

        response = self.service(hypothesis_store=store).process_preview(
            self.request("research_reflection_preview", research_run_id=run_id)
        )
        assert response.research_reflection is not None
        subject_ids = {
            finding.subject_id for finding in response.research_reflection.findings
        }

        self.assertIn(hypothesis.hypothesis_id, subject_ids)
        self.assertNotIn("hypothesis-other-run", subject_ids)
        self.assertEqual(store.save_calls, 0)
        self.assertEqual(store.records[0], hypothesis)

    def test_unreadable_hypothesis_store_preserves_run_side_reflection(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings exist.",
            ResearchEpistemicState.FACT,
        )

        response = self.service(
            hypothesis_store=UnreadableHypothesisStore()
        ).process_preview(
            self.request("research_reflection_preview", research_run_id=run_id)
        )
        assert response.research_reflection is not None

        self.assertTrue(response.success)
        self.assertIn(
            ReflectionFindingKind.WEAK_EVIDENCE,
            [finding.kind for finding in response.research_reflection.findings],
        )
        self.assertNotIn("PRIVATE-HYPOTHESIS-PATH", response.message)

    def test_the_response_says_it_describes_process_not_truth(self) -> None:
        run_id, _, _ = self.sourced_run()
        service = self.service()

        response = service.process_preview(
            self.request("research_reflection_preview", research_run_id=run_id)
        )

        self.assertIn("not whether its conclusions are true", response.message)
        self.assertIn("promoted nothing", response.message)

    def test_storing_persists_and_survives_a_restart(self) -> None:
        run_id, _, _ = self.sourced_run()
        first = self.service()

        first.process_store(
            self.request("research_reflection_store", research_run_id=run_id)
        )

        second = self.service()
        self.assertEqual(
            [report.report_id for report in second.reports()],
            [report.report_id for report in first.reports()],
        )

    def test_reflecting_twice_keeps_both_accounts(self) -> None:
        run_id, _, _ = self.sourced_run()
        service = self.service()
        request = self.request("research_reflection_store", research_run_id=run_id)

        service.process_store(request)
        service.process_store(request)

        self.assertEqual(len(service.reports()), 2)

    def test_reports_are_listed_oldest_first(self) -> None:
        run_id, _, _ = self.sourced_run()
        service = self.service()
        request = self.request("research_reflection_store", research_run_id=run_id)
        service.process_store(request)
        service.process_store(request)

        moments = [report.reflected_at for report in service.reports()]

        self.assertEqual(moments, sorted(moments))

    def test_listing_produces_no_new_reflection(self) -> None:
        run_id, _, _ = self.sourced_run()
        service = self.service()
        service.process_store(
            self.request("research_reflection_store", research_run_id=run_id)
        )

        response = service.process_list(self.request("research_reflection_list"))

        self.assertIn("performs no research", response.message)
        self.assertEqual(len(service.reports()), 1)

    def test_a_missing_run_identifier_is_refused(self) -> None:
        service = self.service()

        with self.assertRaises(ResearchError):
            service.process_preview(self.request("research_reflection_preview"))

    def test_disabled_persistence_writes_nothing(self) -> None:
        run_id, _, _ = self.sourced_run()
        service = self.service(persist=False)

        service.process_store(
            self.request("research_reflection_store", research_run_id=run_id)
        )

        self.assertEqual(len(service.reports()), 1)
        self.assertFalse(self.report_path.exists())

    def test_a_failed_write_keeps_the_report_in_memory(self) -> None:
        run_id, _, _ = self.sourced_run()
        service = self.service()

        with patch.object(
            JsonFileReflectionReportStore,
            "save",
            side_effect=ResearchError("disk full"),
        ):
            service.process_store(
                self.request("research_reflection_store", research_run_id=run_id)
            )

        self.assertEqual(len(service.reports()), 1)


class FailingReportStore:
    """A store that refuses to write, so honesty about that can be tested."""

    @staticmethod
    def load() -> list[object]:
        return []

    @staticmethod
    def save(reports: list[object]) -> None:
        raise ResearchError("PRIVATE-REFLECTION-PATH is unwritable.")


class ReflectionPersistenceHonestyTests(ReflectionFixture):
    """A kept reflection that was not written is not a kept reflection."""

    def failing_service(self) -> ReflectionApplicationService:
        return ReflectionApplicationService(
            self.manager,
            ResponseComposer(),
            report_store=FailingReportStore(),  # type: ignore[arg-type]
            event_bus=self.event_bus,
            clock=self.clock,
        )

    def test_a_failed_write_is_not_reported_as_stored(self) -> None:
        run_id = self.new_run()

        response = self.failing_service().process_store(
            self.request("research_reflection_store", research_run_id=run_id)
        )

        self.assertFalse(response.success)
        self.assertIn("was not durably written", response.message)
        self.assertIn("Restarting Hypatia may lose", response.message)

    def test_a_failed_write_leaks_neither_path_nor_native_error(self) -> None:
        run_id = self.new_run()

        response = self.failing_service().process_store(
            self.request("research_reflection_store", research_run_id=run_id)
        )

        self.assertNotIn("PRIVATE-REFLECTION-PATH", response.message)

    def test_a_failed_write_keeps_the_report_for_this_session(self) -> None:
        run_id = self.new_run()
        service = self.failing_service()

        service.process_store(
            self.request("research_reflection_store", research_run_id=run_id)
        )

        self.assertEqual(len(service.reports()), 1)

    def test_previewing_never_reports_a_write_problem(self) -> None:
        """Preview stores nothing, so it has nothing to be dishonest about."""
        run_id = self.new_run()

        response = self.failing_service().process_preview(
            self.request("research_reflection_preview", research_run_id=run_id)
        )

        self.assertTrue(response.success)


class ReflectionEventTests(ReflectionFixture):
    def test_producing_and_storing_both_emit_bounded_events(self) -> None:
        run_id, _, _ = self.sourced_run()
        service = self.service()

        service.process_store(
            self.request("research_reflection_store", research_run_id=run_id)
        )

        self.assertTrue(self.named(REFLECTION_PRODUCED))
        self.assertTrue(self.named(REFLECTION_STORED))

    def test_no_event_carries_research_or_finding_text(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings are demonstrably young.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        service = self.service()
        service.process_store(
            self.request("research_reflection_store", research_run_id=run_id)
        )

        payloads = json.dumps(
            [
                event.payload
                for event in self.events
                if event.name.startswith("reflection")
            ]
        )

        self.assertTrue(payloads)
        self.assertNotIn("demonstrably young", payloads)
        self.assertNotIn(QUESTION, payloads)
        self.assertNotIn("example.test", payloads)
        self.assertNotIn("corroborate", payloads)

    def test_every_reflection_event_states_that_nothing_ran(self) -> None:
        run_id, _, _ = self.sourced_run()
        service = self.service()
        service.process_preview(
            self.request("research_reflection_preview", research_run_id=run_id)
        )

        for event in self.named(REFLECTION_PRODUCED):
            self.assertIs(event.payload["executed"], False)


class ReflectionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "reflections.json"
        self.store = JsonFileReflectionReportStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def report(index: int = 1) -> ResearchReflectionReport:
        return ResearchReflectionReport(
            report_id=f"reflection:run-1:{index}",
            run_id="run-1",
            question=QUESTION,
            findings=(
                ResearchReflectionFinding(
                    kind=ReflectionFindingKind.WORKED,
                    subject_id="sources",
                    detail="1 source accepted.",
                ),
            ),
            summary=CanonicalResearchSummary(run_count=1, source_count=1),
            reflected_at=START,
        )

    def test_an_absent_store_loads_empty(self) -> None:
        self.assertEqual(self.store.load(), [])

    def test_a_saved_report_round_trips(self) -> None:
        original = self.report()

        self.store.save([original])

        self.assertEqual(self.store.load(), [original])

    def test_a_malformed_document_is_refused(self) -> None:
        self.path.write_text("{ not json", encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_an_unsupported_schema_version_is_refused(self) -> None:
        self.path.write_text(
            json.dumps({"schema_version": 99, "reports": []}),
            encoding="utf-8",
        )

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_an_unknown_finding_kind_is_refused(self) -> None:
        self.store.save([self.report()])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["reports"][0]["findings"][0]["kind"] = "invented"
        self.path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_duplicate_report_identifiers_are_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.store.save([self.report(), self.report()])

    def test_too_many_reports_are_refused(self) -> None:
        reports = [
            replace(self.report(), report_id=f"reflection:{index}")
            for index in range(MAX_REFLECTION_STORE_REPORTS + 1)
        ]

        with self.assertRaises(ResearchError):
            self.store.save(reports)

    def test_a_failed_write_leaves_the_previous_document_intact(self) -> None:
        self.store.save([self.report()])
        before = self.path.read_bytes()

        with (
            patch("research.JsonFileReflectionReportStore.os.replace") as replace_call,
            self.assertRaises(ResearchError),
        ):
            replace_call.side_effect = OSError("no space")
            self.store.save([self.report(1), self.report(2)])

        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])


class ReflectionCompositionTests(ReflectionFixture):
    def test_reflection_is_disabled_without_the_flag(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            bootstrap = Bootstrap(
                memory_path=self.root / "memory.json",
                session_path=self.root / "sessions.json",
            )

            self.assertIsNone(bootstrap._reflection_report_store())

    def test_the_flag_enables_a_store_beside_the_run_store(self) -> None:
        with patch.dict(
            os.environ,
            {"HYPATIA_REFLECTION_ENABLED": "true"},
            clear=True,
        ):
            bootstrap = Bootstrap(
                memory_path=self.root / "memory.json",
                session_path=self.root / "sessions.json",
                research_run_path=self.root / "runs.json",
            )

            store = bootstrap._reflection_report_store()

            self.assertIsNotNone(store)
            assert store is not None
            self.assertEqual(
                store._path,
                self.root / "research_reflections.json",
            )

    def test_the_engine_routes_reflection_over_the_run_manager(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        response = engine.process(
            BrainRequest(
                message="Reflect",
                metadata={
                    "intent": "research_reflection_preview",
                    "research_run_id": run_id,
                },
            )
        )

        service = engine._reflection_service
        self.assertIsInstance(service, ReflectionApplicationService)
        assert service is not None
        self.assertIs(service._run_manager, self.manager)
        self.assertIsNone(service._report_store)
        assert response.research_reflection is not None
        self.assertEqual(response.research_reflection.run_id, run_id)

    def test_the_engine_routes_the_hypothesis_store_into_reflection(self) -> None:
        store = InMemoryHypothesisStore()

        engine = self.build_engine(hypothesis_store=store)

        service = engine._reflection_service
        self.assertIsInstance(service, ReflectionApplicationService)
        assert service is not None
        self.assertIs(service._hypothesis_store, store)

    def test_reflection_is_refused_without_run_persistence(self) -> None:
        engine = self.build_engine(with_runs=False)

        response = engine.process(
            BrainRequest(
                message="Reflect",
                metadata={
                    "intent": "research_reflection_preview",
                    "research_run_id": "run-1",
                },
            )
        )

        self.assertIsNone(engine._reflection_service)
        self.assertFalse(response.success)
        self.assertIn("unavailable", response.message)

    def test_an_unknown_run_is_refused_without_raising(self) -> None:
        engine = self.build_engine()

        response = engine.process(
            BrainRequest(
                message="Reflect",
                metadata={
                    "intent": "research_reflection_preview",
                    "research_run_id": "run-missing",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("rejected", response.message)

    def build_engine(
        self,
        with_runs: bool = True,
        hypothesis_store: InMemoryHypothesisStore | None = None,
    ) -> CognitiveEngine:
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        session_manager = SessionManager(event_bus)
        return CognitiveEngine(
            self.knowledge_engine,
            memory_manager,
            Planner(),
            event_bus,
            ResponseComposer(),
            session_manager,
            SessionRenameTransactionService(
                session_manager=session_manager,
                memory_manager=memory_manager,
                event_bus=event_bus,
            ),
            research_run_manager=self.manager if with_runs else None,
            hypothesis_store=hypothesis_store,
        )


if __name__ == "__main__":
    unittest.main()
