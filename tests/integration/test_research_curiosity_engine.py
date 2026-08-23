"""Bounded curiosity over what a research run actually established.

Curiosity is allowed to notice and to propose. It is not allowed to act, so
these tests assert the negative as hard as the positive: after every intent the
run is byte-for-byte unchanged, no plan exists, no background task exists, and
no network or model call was possible in the first place.

Time and identifiers are injected, and no test sleeps or touches a network.
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
from cognition.CuriosityApplicationService import CuriosityApplicationService
from cognition.CuriosityEvents import (
    GAPS_DETECTED,
    QUESTION_ACCEPTED,
    QUESTION_DISMISSED,
    QUESTIONS_GENERATED,
    QUESTIONS_STORED,
)
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Bootstrap import Bootstrap
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.CuriosityQuestionStatus import CuriosityQuestionStatus
from research.JsonFileCuriosityQuestionStore import (
    MAX_CURIOSITY_STORE_QUESTIONS,
    JsonFileCuriosityQuestionStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchCuriosityQuestion import ResearchCuriosityQuestion
from research.ResearchCuriosityQuestionGenerator import (
    MAX_QUESTIONS_CEILING,
    ResearchCuriosityQuestionGenerator,
)
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchKnowledgeGapDetector import (
    MAX_GAPS_PER_RUN,
    ResearchKnowledgeGapDetector,
)
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind, severity_for
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the ring system have a measured age?"
START = datetime(2026, 8, 23, tzinfo=UTC)
FETCHED = datetime(2026, 8, 1, tzinfo=UTC)


class StubClock:
    """Advance one second per read so ordering is deterministic."""

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


class CuriosityFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.question_path = self.root / "questions.json"
        self.clock = StubClock()
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.knowledge_engine = KnowledgeEngine()
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.acceptance = ResearchSourceAcceptanceService(
            self.knowledge_engine,
            self.manager,
            InMemoryContentStore(),  # type: ignore[arg-type]
        )
        self.detector = ResearchKnowledgeGapDetector()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def service(self, persist: bool = True) -> CuriosityApplicationService:
        return CuriosityApplicationService(
            self.manager,
            ResponseComposer(),
            question_store=(
                JsonFileCuriosityQuestionStore(self.question_path) if persist else None
            ),
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
        """Return a run with one accepted source and one evidence record."""
        run_id = self.new_run()
        document_id = self.accept_source(run_id, slug)
        evidence_id = self.add_evidence(run_id, document_id)
        return run_id, document_id, evidence_id

    def kinds(self, run_id: str) -> list[ResearchKnowledgeGapKind]:
        run = self.manager.get(run_id)
        return [gap.kind for gap in self.detector.detect(run, START)]

    def request(self, intent: str, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="Curiosity",
            metadata={"intent": intent, **metadata},
        )

    def named(self, name: str) -> list[Event]:
        return [event for event in self.events if event.name == name]


class KnowledgeGapDetectionTests(CuriosityFixture):
    def test_a_run_without_sources_reports_only_an_unsupported_question(self) -> None:
        run_id = self.new_run()

        self.assertEqual(
            self.kinds(run_id),
            [ResearchKnowledgeGapKind.UNSUPPORTED_QUESTION],
        )

    def test_an_accepted_source_is_never_reported_as_unsupported(self) -> None:
        run_id, _, _ = self.sourced_run()

        self.assertNotIn(
            ResearchKnowledgeGapKind.UNSUPPORTED_QUESTION,
            self.kinds(run_id),
        )

    def test_a_source_without_evidence_is_unassessed_and_unused(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")

        self.assertEqual(
            sorted(kind.value for kind in self.kinds(run_id)),
            ["unassessed_source", "unused_source"],
        )

    def test_a_cited_source_is_not_reported_as_unused(self) -> None:
        run_id, _, _ = self.sourced_run()

        self.assertNotIn(ResearchKnowledgeGapKind.UNUSED_SOURCE, self.kinds(run_id))

    def test_a_low_trust_assessment_replaces_the_unassessed_gap(self) -> None:
        run_id, document_id, evidence_id = self.sourced_run()
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Self-published and unreviewed.",
            information_trust=ResearchInformationTrust.LOW,
        )

        kinds = self.kinds(run_id)

        self.assertIn(ResearchKnowledgeGapKind.LOW_TRUST_SOURCE, kinds)
        self.assertNotIn(ResearchKnowledgeGapKind.UNASSESSED_SOURCE, kinds)

    def test_a_high_trust_assessment_reports_no_source_gap(self) -> None:
        run_id, document_id, evidence_id = self.sourced_run()
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Peer reviewed and corroborated.",
            information_trust=ResearchInformationTrust.HIGH,
        )

        self.assertEqual(self.kinds(run_id), [])

    def test_a_superseded_assessment_does_not_decide_trust(self) -> None:
        run_id, document_id, evidence_id = self.sourced_run()
        run = self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Self-published and unreviewed.",
            information_trust=ResearchInformationTrust.LOW,
        )
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Later found to be peer reviewed.",
            supersedes_assessment_id=run.assessments[-1].assessment_id,
            information_trust=ResearchInformationTrust.HIGH,
        )

        self.assertNotIn(
            ResearchKnowledgeGapKind.LOW_TRUST_SOURCE,
            self.kinds(run_id),
        )

    def test_a_hypothesis_claim_is_reported_as_unresolved(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
        )

        self.assertIn(ResearchKnowledgeGapKind.UNRESOLVED_CLAIM, self.kinds(run_id))

    def test_a_settled_single_source_claim_is_reported_as_thin(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings exist.",
            ResearchEpistemicState.FACT,
        )

        self.assertIn(
            ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM,
            self.kinds(run_id),
        )

    def test_a_corroborated_claim_is_not_reported_as_thin(self) -> None:
        run_id, first_document, first_evidence = self.sourced_run("a")
        second_document = self.accept_source(run_id, "b")
        second_evidence = self.add_evidence(run_id, second_document)
        self.assertNotEqual(first_document, second_document)
        self.manager.record_claim(
            run_id,
            [first_evidence, second_evidence],
            "The rings exist.",
            ResearchEpistemicState.FACT,
        )

        self.assertNotIn(
            ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM,
            self.kinds(run_id),
        )

    def test_a_contradicted_claim_outranks_an_unresolved_one(self) -> None:
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

        kinds = self.kinds(run_id)

        self.assertEqual(
            kinds[:2],
            [
                ResearchKnowledgeGapKind.CONTRADICTED_CLAIM,
                ResearchKnowledgeGapKind.CONTRADICTED_CLAIM,
            ],
        )
        self.assertNotIn(ResearchKnowledgeGapKind.UNRESOLVED_CLAIM, kinds)

    def test_a_superseded_claim_is_not_reported(self) -> None:
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
            "The rings are young.",
            ResearchEpistemicState.LIKELY,
            supersedes_claim_id=run.claims[-1].claim_id,
        )

        self.assertNotIn(ResearchKnowledgeGapKind.UNRESOLVED_CLAIM, self.kinds(run_id))

    def test_gaps_are_ordered_by_declared_severity(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
        )

        gaps = self.detector.detect(self.manager.get(run_id), START)
        severities = [gap.severity for gap in gaps]

        self.assertEqual(severities, sorted(severities, reverse=True))

    def test_gap_identities_are_stable_across_repeated_detection(self) -> None:
        run_id, _, _ = self.sourced_run()
        run = self.manager.get(run_id)

        first = self.detector.detect(run, START)
        second = self.detector.detect(run, START + timedelta(hours=1))

        self.assertEqual(
            [gap.gap_id for gap in first],
            [gap.gap_id for gap in second],
        )

    def test_the_gap_count_is_bounded(self) -> None:
        run_id = self.new_run()
        for index in range(4):
            self.accept_source(run_id, f"s{index}")
        detector = ResearchKnowledgeGapDetector(max_gaps=3)

        gaps = detector.detect(self.manager.get(run_id), START)

        self.assertEqual(len(gaps), 3)

    def test_an_out_of_range_gap_limit_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            ResearchKnowledgeGapDetector(max_gaps=MAX_GAPS_PER_RUN + 1)
        with self.assertRaises(ValueError):
            ResearchKnowledgeGapDetector(max_gaps=0)

    def test_detection_requires_an_actual_run(self) -> None:
        with self.assertRaises(ResearchError):
            self.detector.detect("run-1", START)  # type: ignore[arg-type]

    def test_every_gap_kind_declares_a_severity(self) -> None:
        for kind in ResearchKnowledgeGapKind:
            self.assertIsInstance(severity_for(kind), int)

    def test_an_unclassified_gap_kind_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            severity_for("invented_kind")  # type: ignore[arg-type]

    def test_detection_leaves_the_run_untouched(self) -> None:
        run_id, _, _ = self.sourced_run()
        before = self.manager.get(run_id)

        self.detector.detect(before, START)

        self.assertEqual(self.manager.get(run_id), before)


class CuriosityQuestionGenerationTests(CuriosityFixture):
    def test_every_gap_yields_exactly_one_question(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        run = self.manager.get(run_id)
        gaps = self.detector.detect(run, START)

        questions = ResearchCuriosityQuestionGenerator().generate(run, gaps)

        self.assertEqual(len(questions), len(gaps))
        self.assertEqual(
            {question.gap_id for question in questions},
            {gap.gap_id for gap in gaps},
        )

    def test_every_generated_string_is_a_question(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        run = self.manager.get(run_id)

        questions = ResearchCuriosityQuestionGenerator().generate(
            run,
            self.detector.detect(run, START),
        )

        self.assertTrue(questions)
        for question in questions:
            self.assertTrue(question.text.endswith("?"), question.text)

    def test_questions_are_ranked_by_gap_severity(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        run = self.manager.get(run_id)

        questions = ResearchCuriosityQuestionGenerator().generate(
            run,
            self.detector.detect(run, START),
        )
        ranks = [question.rank_score for question in questions]

        self.assertEqual(ranks, sorted(ranks, reverse=True))
        self.assertIs(questions[0].kind, ResearchKnowledgeGapKind.UNRESOLVED_CLAIM)

    def test_lower_recorded_confidence_ranks_higher_within_a_kind(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be ancient.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.HIGH,
        )
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
        )
        run = self.manager.get(run_id)

        questions = ResearchCuriosityQuestionGenerator().generate(
            run,
            self.detector.detect(run, START),
        )
        unresolved = [
            question
            for question in questions
            if question.kind is ResearchKnowledgeGapKind.UNRESOLVED_CLAIM
        ]

        self.assertEqual(len(unresolved), 2)
        self.assertGreater(unresolved[0].rank_score, unresolved[1].rank_score)
        self.assertIn("young", unresolved[0].text)

    def test_question_identities_are_stable_across_repeated_generation(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        run = self.manager.get(run_id)
        generator = ResearchCuriosityQuestionGenerator()

        first = generator.generate(run, self.detector.detect(run, START))
        second = generator.generate(run, self.detector.detect(run, START))

        self.assertEqual(
            [question.question_id for question in first],
            [question.question_id for question in second],
        )

    def test_the_question_count_is_bounded(self) -> None:
        run_id = self.new_run()
        for index in range(4):
            self.accept_source(run_id, f"s{index}")
        run = self.manager.get(run_id)

        questions = ResearchCuriosityQuestionGenerator(max_questions=2).generate(
            run,
            self.detector.detect(run, START),
        )

        self.assertEqual(len(questions), 2)

    def test_an_out_of_range_question_limit_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            ResearchCuriosityQuestionGenerator(max_questions=MAX_QUESTIONS_CEILING + 1)
        with self.assertRaises(ValueError):
            ResearchCuriosityQuestionGenerator(max_questions=0)

    def test_a_long_claim_is_trimmed_rather_than_rejected(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The ring system " + ("is very old " * 40),
            ResearchEpistemicState.HYPOTHESIS,
        )
        run = self.manager.get(run_id)

        questions = ResearchCuriosityQuestionGenerator().generate(
            run,
            self.detector.detect(run, START),
        )

        self.assertTrue(questions)
        for question in questions:
            self.assertLessEqual(len(question.text), 300)


class CuriosityServiceTests(CuriosityFixture):
    def test_preview_proposes_without_storing(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        service = self.service()

        response = service.process_question_preview(
            self.request("curiosity_question_preview", research_run_id=run_id)
        )

        assert response.research_curiosity is not None
        self.assertGreater(response.research_curiosity.question_count, 0)
        self.assertFalse(response.research_curiosity.stored)
        self.assertEqual(service.questions(), ())
        self.assertFalse(self.question_path.exists())
        self.assertIn("Nothing was stored", response.message)

    def test_gap_detection_proposes_nothing(self) -> None:
        run_id = self.new_run()
        service = self.service()

        response = service.process_gap_detect(
            self.request("curiosity_gap_detect", research_run_id=run_id)
        )

        assert response.research_curiosity is not None
        self.assertEqual(response.research_curiosity.question_count, 0)
        self.assertEqual(response.research_curiosity.gap_count, 1)

    def test_storing_persists_proposals_and_survives_a_restart(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        first = self.service()

        first.process_question_store(
            self.request("curiosity_question_store", research_run_id=run_id)
        )
        stored = first.questions()

        second = self.service()

        self.assertTrue(stored)
        self.assertEqual(
            [question.question_id for question in second.questions()],
            [question.question_id for question in stored],
        )

    def test_storing_twice_adds_nothing_new(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        service = self.service()
        request = self.request("curiosity_question_store", research_run_id=run_id)

        service.process_question_store(request)
        first = service.questions()
        service.process_question_store(request)

        self.assertEqual(service.questions(), first)

    def test_storing_never_reopens_a_decided_question(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        service = self.service()
        store_request = self.request(
            "curiosity_question_store",
            research_run_id=run_id,
        )
        service.process_question_store(store_request)
        question_id = service.questions()[0].question_id
        service.process_question_dismiss(
            self.request(
                "curiosity_question_dismiss",
                curiosity_question_id=question_id,
            )
        )

        service.process_question_store(store_request)

        decided = next(
            question
            for question in service.questions()
            if question.question_id == question_id
        )
        self.assertIs(decided.status, CuriosityQuestionStatus.DISMISSED)

    def test_accepting_records_intent_without_starting_research(self) -> None:
        run_id, _, _ = self.sourced_run()
        before = self.manager.get(run_id)
        service = self.service()
        service.process_question_store(
            self.request("curiosity_question_store", research_run_id=run_id)
        )
        question_id = service.questions()[0].question_id

        response = service.process_question_accept(
            self.request(
                "curiosity_question_accept",
                curiosity_question_id=question_id,
            )
        )

        assert response.curiosity_question is not None
        self.assertIs(
            response.curiosity_question.status,
            CuriosityQuestionStatus.ACCEPTED,
        )
        self.assertIn("starts no research", response.message)
        self.assertEqual(self.manager.get(run_id), before)

    def test_a_decided_question_cannot_be_decided_again(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        service = self.service()
        service.process_question_store(
            self.request("curiosity_question_store", research_run_id=run_id)
        )
        question_id = service.questions()[0].question_id
        accept = self.request(
            "curiosity_question_accept",
            curiosity_question_id=question_id,
        )
        service.process_question_accept(accept)

        response = service.process_question_accept(accept)

        self.assertFalse(response.success)
        self.assertIn("cannot be decided again", response.message)

    def test_an_unknown_question_is_reported_not_invented(self) -> None:
        service = self.service()

        response = service.process_question_accept(
            self.request(
                "curiosity_question_accept",
                curiosity_question_id="question:missing",
            )
        )

        self.assertFalse(response.success)
        self.assertIn("not found", response.message)
        self.assertEqual(service.questions(), ())

    def test_an_empty_run_identifier_is_refused(self) -> None:
        service = self.service()

        with self.assertRaises(ResearchError):
            service.process_gap_detect(
                self.request("curiosity_gap_detect", research_run_id="  ")
            )

    def test_an_unknown_run_is_refused(self) -> None:
        service = self.service()

        with self.assertRaises(ResearchError):
            service.process_gap_detect(
                self.request("curiosity_gap_detect", research_run_id="run-missing")
            )

    def test_listing_performs_no_research(self) -> None:
        run_id, _, _ = self.sourced_run()
        before = self.manager.get(run_id)
        service = self.service()

        response = service.process_question_list(
            self.request("curiosity_question_list")
        )

        self.assertIn("performs no research", response.message)
        self.assertEqual(self.manager.get(run_id), before)

    def test_disabled_persistence_writes_nothing(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        service = self.service(persist=False)

        service.process_question_store(
            self.request("curiosity_question_store", research_run_id=run_id)
        )

        self.assertTrue(service.questions())
        self.assertFalse(self.question_path.exists())

    def test_a_failed_write_leaves_proposals_in_memory(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        service = self.service()

        with patch.object(
            JsonFileCuriosityQuestionStore,
            "save",
            side_effect=ResearchError("disk full"),
        ):
            service.process_question_store(
                self.request("curiosity_question_store", research_run_id=run_id)
            )

        self.assertTrue(service.questions())


class CuriosityEventTests(CuriosityFixture):
    def test_the_full_pipeline_emits_bounded_events(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        service = self.service()

        service.process_question_store(
            self.request("curiosity_question_store", research_run_id=run_id)
        )
        question_id = service.questions()[0].question_id
        service.process_question_accept(
            self.request(
                "curiosity_question_accept",
                curiosity_question_id=question_id,
            )
        )
        service.process_question_dismiss(
            self.request(
                "curiosity_question_dismiss",
                curiosity_question_id=service.questions()[-1].question_id,
            )
        )

        for name in (
            GAPS_DETECTED,
            QUESTIONS_GENERATED,
            QUESTIONS_STORED,
            QUESTION_ACCEPTED,
            QUESTION_DISMISSED,
        ):
            self.assertTrue(self.named(name), name)

    def test_no_event_carries_research_or_question_text(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings are demonstrably young.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        service = self.service()
        service.process_question_store(
            self.request("curiosity_question_store", research_run_id=run_id)
        )
        service.process_question_accept(
            self.request(
                "curiosity_question_accept",
                curiosity_question_id=service.questions()[0].question_id,
            )
        )

        payloads = json.dumps(
            [
                event.payload
                for event in self.events
                if event.name.startswith("curiosity")
            ]
        )

        self.assertTrue(payloads)
        self.assertNotIn("demonstrably young", payloads)
        self.assertNotIn(QUESTION, payloads)
        self.assertNotIn("example.test", payloads)
        self.assertNotIn("corroborate", payloads)

    def test_every_curiosity_event_states_that_nothing_ran(self) -> None:
        run_id = self.new_run()
        self.accept_source(run_id, "lonely")
        service = self.service()
        service.process_question_store(
            self.request("curiosity_question_store", research_run_id=run_id)
        )

        generated = self.named(QUESTIONS_GENERATED)

        self.assertTrue(generated)
        for event in generated:
            self.assertIs(event.payload["executed"], False)


class CuriosityQuestionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "questions.json"
        self.store = JsonFileCuriosityQuestionStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def question(index: int = 1) -> ResearchCuriosityQuestion:
        return ResearchCuriosityQuestion(
            question_id=f"question:gap:run-1:unused_source:doc-{index}",
            gap_id=f"gap:run-1:unused_source:doc-{index}",
            run_id="run-1",
            kind=ResearchKnowledgeGapKind.UNUSED_SOURCE,
            subject_id=f"doc-{index}",
            text="What evidence, if any, does this so-far unused source support?",
            rank_score=100,
            generated_at=START,
        )

    def test_an_absent_store_loads_empty(self) -> None:
        self.assertEqual(self.store.load(), [])

    def test_a_saved_question_round_trips(self) -> None:
        original = self.question().accepted(START + timedelta(minutes=1))

        self.store.save([original])

        self.assertEqual(self.store.load(), [original])

    def test_a_malformed_document_is_refused(self) -> None:
        self.path.write_text("{ not json", encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_an_unsupported_schema_version_is_refused(self) -> None:
        self.path.write_text(
            json.dumps({"schema_version": 99, "questions": []}),
            encoding="utf-8",
        )

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_an_unknown_gap_kind_is_refused(self) -> None:
        self.store.save([self.question()])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["questions"][0]["kind"] = "invented_kind"
        self.path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_duplicate_question_identifiers_are_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.store.save([self.question(), self.question()])

    def test_too_many_questions_are_refused(self) -> None:
        questions = [
            replace(self.question(), question_id=f"question:{index}")
            for index in range(MAX_CURIOSITY_STORE_QUESTIONS + 1)
        ]

        with self.assertRaises(ResearchError):
            self.store.save(questions)

    def test_a_failed_write_leaves_the_previous_document_intact(self) -> None:
        self.store.save([self.question()])
        before = self.path.read_bytes()

        with (
            patch("research.JsonFileCuriosityQuestionStore.os.replace") as replace_call,
            self.assertRaises(ResearchError),
        ):
            replace_call.side_effect = OSError("no space")
            self.store.save([self.question(1), self.question(2)])

        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(
            list(self.path.parent.glob(f".{self.path.name}.*.tmp")),
            [],
        )


class CuriosityCompositionTests(unittest.TestCase):
    def test_curiosity_is_disabled_without_the_flag(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {}, clear=True),
        ):
            path = Path(directory)
            bootstrap = Bootstrap(
                memory_path=path / "memory.json",
                session_path=path / "sessions.json",
            )

            self.assertIsNone(bootstrap._curiosity_question_store())

    def test_the_flag_enables_a_store_beside_the_run_store(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"HYPATIA_CURIOSITY_ENABLED": "true"},
                clear=True,
            ),
        ):
            path = Path(directory)
            bootstrap = Bootstrap(
                memory_path=path / "memory.json",
                session_path=path / "sessions.json",
                research_run_path=path / "runs.json",
            )

            store = bootstrap._curiosity_question_store()

            self.assertIsNotNone(store)
            assert store is not None
            self.assertEqual(
                store._path,
                path / "research_curiosity_questions.json",
            )

    def test_the_engine_routes_curiosity_over_the_run_manager(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            engine, manager = self.build_engine(path)
            run_id = manager.create(QUESTION).run_id

            response = engine.process(
                BrainRequest(
                    message="Detect gaps",
                    metadata={
                        "intent": "curiosity_gap_detect",
                        "research_run_id": run_id,
                    },
                )
            )

            service = engine._curiosity_service
            self.assertIsInstance(service, CuriosityApplicationService)
            assert service is not None
            self.assertIs(service._run_manager, manager)
            self.assertIsNone(service._question_store)
            assert response.research_curiosity is not None
            self.assertEqual(response.research_curiosity.run_id, run_id)

    def test_curiosity_is_refused_without_run_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            engine, _ = self.build_engine(Path(directory), with_runs=False)

            response = engine.process(
                BrainRequest(
                    message="Detect gaps",
                    metadata={
                        "intent": "curiosity_gap_detect",
                        "research_run_id": "run-1",
                    },
                )
            )

            self.assertIsNone(engine._curiosity_service)
            self.assertFalse(response.success)
            self.assertIn("unavailable", response.message)

    def test_an_unknown_run_is_refused_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            engine, _ = self.build_engine(Path(directory))

            response = engine.process(
                BrainRequest(
                    message="Detect gaps",
                    metadata={
                        "intent": "curiosity_gap_detect",
                        "research_run_id": "run-missing",
                    },
                )
            )

            self.assertFalse(response.success)
            self.assertIn("rejected", response.message)

    @staticmethod
    def build_engine(
        path: Path,
        with_runs: bool = True,
    ) -> tuple[CognitiveEngine, ResearchRunManager]:
        document = path / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        knowledge_engine = KnowledgeEngine()
        knowledge_engine.load(document)
        session_manager = SessionManager(event_bus)
        manager = ResearchRunManager(JsonFileResearchRunStore(path / "runs.json"))
        manager.load()
        engine = CognitiveEngine(
            knowledge_engine,
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
            research_run_manager=manager if with_runs else None,
        )
        return engine, manager


if __name__ == "__main__":
    unittest.main()
