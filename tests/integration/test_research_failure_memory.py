"""A lesson must be checkable, and it must never become a rule.

Two properties are policed here. The first is provenance: every remembered
lesson names the persisted records it came from, and a lesson without any is
refused at construction — otherwise an opinion outlives the reasoning behind it
and quietly hardens into a belief nobody can audit.

The second is that recall stays advice. Nothing here blocks a plan, refuses a
capability, downgrades a claim, or edits a run. A system that stops trying
things because something similar failed once has swapped research for
superstition, so the tests assert the absence of enforcement as hard as the
presence of memory.

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
from cognition.FailureMemoryApplicationService import FailureMemoryApplicationService
from cognition.FailureMemoryEvents import (
    LESSONS_DERIVED,
    LESSONS_RECALLED,
    LESSONS_STORED,
)
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Bootstrap import Bootstrap
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.CanonicalResearchSummary import CanonicalResearchSummary
from research.FailureLessonKind import FailureLessonKind, weight_for
from research.FailureMemoryAdvisor import (
    MAX_RECALL_LIMIT,
    MIN_SHARED_TOKENS,
    FailureMemoryAdvisor,
)
from research.JsonFileFailureLessonStore import (
    MAX_FAILURE_STORE_LESSONS,
    JsonFileFailureLessonStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchFailureLesson import (
    MAX_LESSON_PROVENANCE,
    ResearchFailureLesson,
)
from research.ResearchFailureLessonDeriver import (
    MAX_LESSONS_PER_RUN,
    ResearchFailureLessonDeriver,
)
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the Saturn ring system have a measured age?"
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


class FailureMemoryFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        self.lesson_path = self.root / "lessons.json"
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
        self.deriver = ResearchFailureLessonDeriver()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def service(self, persist: bool = True) -> FailureMemoryApplicationService:
        return FailureMemoryApplicationService(
            self.manager,
            ResponseComposer(),
            lesson_store=(
                JsonFileFailureLessonStore(self.lesson_path) if persist else None
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
        run_id = self.new_run()
        document_id = self.accept_source(run_id, slug)
        return run_id, document_id, self.add_evidence(run_id, document_id)

    def derive(self, run_id: str) -> tuple[ResearchFailureLesson, ...]:
        return self.deriver.derive(self.manager.get(run_id), START)

    def kinds(self, run_id: str) -> list[FailureLessonKind]:
        return [lesson.kind for lesson in self.derive(run_id)]

    def of_kind(
        self,
        run_id: str,
        kind: FailureLessonKind,
    ) -> tuple[ResearchFailureLesson, ...]:
        return tuple(lesson for lesson in self.derive(run_id) if lesson.kind is kind)

    def request(self, intent: str, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="Failure memory",
            metadata={"intent": intent, **metadata},
        )

    def named(self, name: str) -> list[Event]:
        return [event for event in self.events if event.name == name]


class ProvenanceTests(unittest.TestCase):
    @staticmethod
    def lesson(**overrides: object) -> ResearchFailureLesson:
        fields: dict[str, object] = {
            "lesson_id": "lesson:run-1:operation_failure:fetch",
            "kind": FailureLessonKind.OPERATION_FAILURE,
            "run_id": "run-1",
            "subject_id": "fetch",
            "statement": "The fetch stage failed here.",
            "provenance": ("failure:fetch:2026-08-23T00:00:00+00:00",),
            "context": QUESTION,
            "recorded_at": START,
        }
        fields.update(overrides)
        return ResearchFailureLesson(**fields)  # type: ignore[arg-type]

    def test_a_lesson_without_provenance_is_refused(self) -> None:
        with self.assertRaises(ResearchError) as raised:
            self.lesson(provenance=())

        self.assertIn("is an opinion, not a lesson", str(raised.exception))

    def test_repeated_provenance_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.lesson(provenance=("a", "a"))

    def test_empty_provenance_entries_are_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.lesson(provenance=("a", "  "))

    def test_overlong_provenance_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.lesson(
                provenance=tuple(
                    f"record-{index}" for index in range(MAX_LESSON_PROVENANCE + 1)
                )
            )

    def test_a_valid_lesson_keeps_its_provenance(self) -> None:
        lesson = self.lesson(provenance=("claim-1", "claim-2"))

        self.assertEqual(lesson.provenance, ("claim-1", "claim-2"))

    def test_every_lesson_kind_declares_a_weight(self) -> None:
        for kind in FailureLessonKind:
            self.assertIsInstance(weight_for(kind), int)

    def test_an_unclassified_lesson_kind_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            weight_for("invented_kind")  # type: ignore[arg-type]

    def test_only_belief_kinds_concern_belief(self) -> None:
        self.assertTrue(FailureLessonKind.FAILED_HYPOTHESIS.concerns_belief)
        self.assertTrue(FailureLessonKind.REVISED_CLAIM.concerns_belief)
        self.assertTrue(FailureLessonKind.DISPROVING_EVIDENCE.concerns_belief)
        self.assertFalse(FailureLessonKind.INEFFECTIVE_STRATEGY.concerns_belief)
        self.assertFalse(FailureLessonKind.OPERATION_FAILURE.concerns_belief)
        self.assertEqual(
            FailureLessonKind.REVISED_CLAIM.weight,
            FailureLessonKind.FAILED_HYPOTHESIS.weight,
        )


class LessonDerivationTests(FailureMemoryFixture):
    def test_a_recorded_failure_becomes_an_operation_lesson(self) -> None:
        run_id = self.new_run()
        self.manager.record_failure(run_id, "source_fetch", "Refused before request.")

        lessons = self.of_kind(run_id, FailureLessonKind.OPERATION_FAILURE)

        self.assertEqual(len(lessons), 1)
        self.assertIn("source_fetch", lessons[0].statement)
        self.assertTrue(lessons[0].provenance)

    def test_a_superseded_claim_is_abandoned_not_disproved(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        run = self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        earlier_id = run.claims[-1].claim_id
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings are young.",
            ResearchEpistemicState.LIKELY,
            supersedes_claim_id=earlier_id,
        )

        lessons = self.of_kind(run_id, FailureLessonKind.FAILED_HYPOTHESIS)

        self.assertEqual(len(lessons), 1)
        self.assertIn("abandoned, not disproved", lessons[0].statement)
        self.assertIn(earlier_id, lessons[0].provenance)

    def test_superseded_claim_kind_matches_the_authored_epistemic_state(self) -> None:
        for state in ResearchEpistemicState:
            with self.subTest(state=state.value):
                run_id, _, evidence_id = self.sourced_run(f"state-{state.value}")
                run = self.manager.record_claim(
                    run_id,
                    [evidence_id],
                    f"Earlier {state.value} claim.",
                    state,
                )
                earlier_id = run.claims[-1].claim_id
                self.manager.record_claim(
                    run_id,
                    [evidence_id],
                    "A later authored claim.",
                    ResearchEpistemicState.LIKELY,
                    supersedes_claim_id=earlier_id,
                )

                revision = next(
                    lesson
                    for lesson in self.derive(run_id)
                    if lesson.subject_id == earlier_id
                    and lesson.kind
                    in (
                        FailureLessonKind.FAILED_HYPOTHESIS,
                        FailureLessonKind.REVISED_CLAIM,
                    )
                )
                expected = (
                    FailureLessonKind.FAILED_HYPOTHESIS
                    if state is ResearchEpistemicState.HYPOTHESIS
                    else FailureLessonKind.REVISED_CLAIM
                )

                self.assertIs(revision.kind, expected)
                self.assertIn(state.value, revision.statement)
                self.assertIn("not disproved", revision.statement)
                self.assertEqual(
                    revision.lesson_id,
                    f"lesson:{run_id}:{expected.value}:{earlier_id}",
                )

    def test_a_confidence_move_is_remembered_separately(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        run = self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.HIGH,
        )
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings may be young after all.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
            supersedes_claim_id=run.claims[-1].claim_id,
        )

        lessons = self.of_kind(run_id, FailureLessonKind.CONFIDENCE_CHANGE)

        self.assertEqual(len(lessons), 1)
        self.assertIn("from high to low", lessons[0].statement)

    def test_an_unchanged_confidence_produces_no_lesson(self) -> None:
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
            "The rings may be young after all.",
            ResearchEpistemicState.HYPOTHESIS,
            ResearchClaimConfidence.LOW,
            supersedes_claim_id=run.claims[-1].claim_id,
        )

        self.assertEqual(self.of_kind(run_id, FailureLessonKind.CONFIDENCE_CHANGE), ())

    def test_a_contradiction_becomes_a_disproving_evidence_lesson(self) -> None:
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

        lessons = self.of_kind(run_id, FailureLessonKind.DISPROVING_EVIDENCE)

        self.assertEqual(len(lessons), 2)
        for lesson in lessons:
            self.assertIn("Which one survives is not settled here", lesson.statement)

    def test_a_revised_assessment_becomes_an_invalid_assumption(self) -> None:
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

        lessons = self.of_kind(run_id, FailureLessonKind.INVALID_ASSUMPTION)

        self.assertEqual(len(lessons), 1)
        self.assertIn("The first judgement did not hold", lessons[0].statement)

    def test_a_low_trust_acceptance_becomes_a_false_positive(self) -> None:
        run_id, document_id, evidence_id = self.sourced_run()
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Self-published and unreviewed.",
            information_trust=ResearchInformationTrust.LOW,
        )

        lessons = self.of_kind(run_id, FailureLessonKind.FALSE_POSITIVE)

        self.assertEqual(len(lessons), 1)
        self.assertIn("Acceptance is not a judgement of quality", lessons[0].statement)

    def test_a_barren_discovery_becomes_an_ineffective_strategy(self) -> None:
        run_id = self.new_run()
        self.manager.add_discovery(
            run_id,
            QUESTION,
            "crossref",
            [
                ResearchSourceCandidate(
                    url="https://example.test/never-accepted",
                    title="Unaccepted",
                    snippet="",
                )
            ],
        )

        lessons = self.of_kind(run_id, FailureLessonKind.INEFFECTIVE_STRATEGY)

        self.assertEqual(len(lessons), 1)
        self.assertIn("not about the provider", lessons[0].statement)

    def test_a_discovery_that_led_to_acceptance_produces_no_lesson(self) -> None:
        run_id = self.new_run()
        document_id = self.accept_source(run_id, "used")
        self.assertTrue(document_id)
        self.manager.add_discovery(
            run_id,
            QUESTION,
            "crossref",
            [
                ResearchSourceCandidate(
                    url="https://example.test/used",
                    title="Used",
                    snippet="",
                )
            ],
        )

        self.assertEqual(
            self.of_kind(run_id, FailureLessonKind.INEFFECTIVE_STRATEGY),
            (),
        )

    def test_a_clean_run_leaves_no_lessons(self) -> None:
        run_id, _, _ = self.sourced_run()

        self.assertEqual(self.derive(run_id), ())

    def test_lessons_are_ordered_by_declared_weight(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_failure(run_id, "source_fetch", "Refused.")
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

        weights = [lesson.weight for lesson in self.derive(run_id)]

        self.assertEqual(weights, sorted(weights, reverse=True))

    def test_lesson_identities_are_stable_across_repeated_derivation(self) -> None:
        run_id = self.new_run()
        self.manager.record_failure(run_id, "source_fetch", "Refused.")

        first = self.derive(run_id)
        second = self.derive(run_id)

        self.assertEqual(
            [lesson.lesson_id for lesson in first],
            [lesson.lesson_id for lesson in second],
        )

    def test_a_discovery_failure_lesson_names_its_recorded_provider(self) -> None:
        run_id = self.new_run()
        self.manager.record_failure(
            run_id,
            "source_discovery",
            "Research source discovery failed.",
            provider="nvd",
        )

        [lesson] = self.of_kind(run_id, FailureLessonKind.OPERATION_FAILURE)

        self.assertIn("source_discovery stage for nvd failed", lesson.statement)
        self.assertIn(":nvd", lesson.subject_id)
        self.assertIn(":nvd", lesson.provenance[0])

    def test_the_lesson_count_is_bounded(self) -> None:
        run_id = self.new_run()
        for index in range(5):
            self.manager.record_failure(run_id, f"stage_{index}", "Refused.")
        deriver = ResearchFailureLessonDeriver(max_lessons=3)

        lessons = deriver.derive(self.manager.get(run_id), START)

        self.assertEqual(len(lessons), 3)

    def test_an_out_of_range_lesson_limit_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            ResearchFailureLessonDeriver(max_lessons=MAX_LESSONS_PER_RUN + 1)
        with self.assertRaises(ValueError):
            ResearchFailureLessonDeriver(max_lessons=0)

    def test_derivation_requires_an_actual_run(self) -> None:
        with self.assertRaises(ResearchError):
            self.deriver.derive("run-1", START)  # type: ignore[arg-type]

    def test_every_derived_lesson_carries_provenance(self) -> None:
        run_id, document_id, evidence_id = self.sourced_run()
        self.manager.record_failure(run_id, "source_fetch", "Refused.")
        self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Self-published.",
            information_trust=ResearchInformationTrust.LOW,
        )

        lessons = self.derive(run_id)

        self.assertTrue(lessons)
        for lesson in lessons:
            self.assertTrue(lesson.provenance, lesson.lesson_id)


class OneLessonIsOneLineTests(FailureMemoryFixture):
    """Authored text must not be able to invent a lesson nobody derived.

    Lessons are rendered one per line. A failure reason is free text a person
    or a stage supplies, so a line break inside one used to arrive in the
    report as a second entry, complete with a kind label of its own choosing.
    """

    FORGERY = "Plain HTTP\n- [failed_hypothesis] FORGED\n  from: nothing"

    def forged_run(self) -> str:
        run_id = self.new_run()
        self.manager.record_failure(run_id, "source_fetch", self.FORGERY)
        return run_id

    @staticmethod
    def entries(message: str) -> list[str]:
        """Return the lines that read as one listed record each."""
        return [line for line in message.splitlines() if line.startswith("- [")]

    def rendered(self, name: str, *arguments: object) -> str:
        composer = getattr(ResponseComposer(), name)
        return composer(self.request(f"failure_memory_{name}"), *arguments).message

    def test_a_line_break_in_a_reason_cannot_forge_a_lesson(self) -> None:
        lessons = self.derive(self.forged_run())

        for name, arguments in (
            ("failure_lessons", (lessons, True)),
            ("failure_lesson_recall", (lessons,)),
            ("failure_lesson_list", (lessons,)),
        ):
            with self.subTest(rendering=name):
                self.assertEqual(
                    len(self.entries(self.rendered(name, *arguments))),
                    len(lessons),
                )

    def test_the_forged_label_never_becomes_its_own_entry(self) -> None:
        """The text survives inside the lesson; it just stops being a line."""
        lessons = self.derive(self.forged_run())

        message = self.rendered("failure_lessons", lessons, True)
        carrying = [line for line in message.splitlines() if "FORGED" in line]

        self.assertIn("FORGED", message)
        self.assertEqual(len(self.entries(message)), 1)
        self.assertEqual(carrying, self.entries(message))

    def test_the_guarantee_is_held_by_the_record_not_the_renderer(self) -> None:
        """Every producer inherits it, including ones written later."""
        lesson = ResearchFailureLesson(
            lesson_id="lesson:run-1:operation_failure:stage",
            kind=FailureLessonKind.OPERATION_FAILURE,
            run_id="run-1",
            subject_id="stage",
            statement="First\nsecond\r\nthird",
            provenance=("failure:stage",),
            context="A question\nsplit across lines",
            recorded_at=START,
        )

        self.assertEqual(lesson.statement, "First second third")
        self.assertEqual(lesson.context, "A question split across lines")

    def test_listing_says_which_lesson_each_entry_is(self) -> None:
        """A catalogue identified only by record ID cannot be acted on."""
        lessons = self.derive(self.forged_run())

        message = self.rendered("failure_lesson_list", lessons)

        self.assertIn(lessons[0].statement, message)


class RecallIsAdvisoryTests(FailureMemoryFixture):
    def failing_run(self) -> str:
        run_id = self.new_run()
        self.manager.record_failure(
            run_id,
            "source_fetch",
            "Publisher redirect was plain HTTP.",
        )
        return run_id

    def test_recall_surfaces_a_lesson_sharing_the_question_wording(self) -> None:
        run_id = self.failing_run()
        service = self.service()
        service.process_store(
            self.request("failure_memory_store", research_run_id=run_id)
        )

        response = service.process_recall(
            self.request(
                "failure_memory_recall",
                research_question="What is the Saturn ring system made of?",
            )
        )

        self.assertTrue(response.failure_lessons)
        self.assertIn("Possibly relevant prior lessons", response.message)

    def test_recall_says_plainly_that_it_blocks_nothing(self) -> None:
        run_id = self.failing_run()
        service = self.service()
        service.process_store(
            self.request("failure_memory_store", research_run_id=run_id)
        )

        response = service.process_recall(
            self.request("failure_memory_recall", research_question=QUESTION)
        )

        self.assertIn("advisory", response.message)
        self.assertIn("Nothing was blocked", response.message)
        self.assertIn("not a reason not to try it", response.message)

    def test_recall_changes_no_research_state(self) -> None:
        run_id = self.failing_run()
        service = self.service()
        service.process_store(
            self.request("failure_memory_store", research_run_id=run_id)
        )
        before = self.run_path.read_bytes()
        summary_before = CanonicalResearchSummary.from_runs(self.manager.list())

        service.process_recall(
            self.request("failure_memory_recall", research_question=QUESTION)
        )

        self.assertEqual(self.run_path.read_bytes(), before)
        self.assertEqual(
            CanonicalResearchSummary.from_runs(self.manager.list()),
            summary_before,
        )

    def test_an_unrelated_question_recalls_nothing(self) -> None:
        run_id = self.failing_run()
        service = self.service()
        service.process_store(
            self.request("failure_memory_store", research_run_id=run_id)
        )

        response = service.process_recall(
            self.request(
                "failure_memory_recall",
                research_question="Which grammar rules govern Basque ergativity?",
            )
        )

        self.assertEqual(response.failure_lessons, ())
        self.assertIn("Nothing remembered overlaps this question", response.message)

    def test_recall_is_bounded(self) -> None:
        lessons = [
            ResearchFailureLesson(
                lesson_id=f"lesson:{index}",
                kind=FailureLessonKind.OPERATION_FAILURE,
                run_id="run-1",
                subject_id=f"stage-{index}",
                statement="Saturn ring research failed at this stage.",
                provenance=(f"failure:{index}",),
                context=QUESTION,
                recorded_at=START,
            )
            for index in range(10)
        ]

        relevant = FailureMemoryAdvisor(limit=3).relevant(QUESTION, lessons)

        self.assertEqual(len(relevant), 3)

    def test_a_heavier_lesson_outranks_a_lighter_one_on_equal_overlap(self) -> None:
        def lesson(kind: FailureLessonKind, name: str) -> ResearchFailureLesson:
            return ResearchFailureLesson(
                lesson_id=name,
                kind=kind,
                run_id="run-1",
                subject_id=name,
                statement="Saturn rings measured age evidence.",
                provenance=(name,),
                context="",
                recorded_at=START,
            )

        relevant = FailureMemoryAdvisor().relevant(
            "Saturn rings measured age evidence",
            [
                lesson(FailureLessonKind.OPERATION_FAILURE, "light"),
                lesson(FailureLessonKind.DISPROVING_EVIDENCE, "heavy"),
            ],
        )

        self.assertEqual(relevant[0].lesson_id, "heavy")

    def test_a_newer_lesson_breaks_an_exact_relevance_tie(self) -> None:
        def lesson(name: str, recorded_at: datetime) -> ResearchFailureLesson:
            return ResearchFailureLesson(
                lesson_id=name,
                kind=FailureLessonKind.OPERATION_FAILURE,
                run_id=f"run-{name}",
                subject_id=name,
                statement="Saturn rings research failed.",
                provenance=(f"failure:{name}",),
                context="",
                recorded_at=recorded_at,
            )

        relevant = FailureMemoryAdvisor().relevant(
            "Saturn rings research",
            [
                lesson("older", START),
                lesson("newer", START + timedelta(days=1)),
            ],
        )

        self.assertEqual([entry.lesson_id for entry in relevant], ["newer", "older"])

    def test_a_single_shared_word_is_not_enough_to_recall(self) -> None:
        """Lessons share vocabulary just by being lessons.

        Both questions below overlap this lesson. Only the second overlaps it
        on anything that identifies the subject; the first shares "evidence",
        which every disproving lesson ever written will also contain. Recall
        that fires on one such word is recall nobody reads.
        """
        lesson = ResearchFailureLesson(
            lesson_id="lesson:run-1:disproving_evidence:h1",
            kind=FailureLessonKind.DISPROVING_EVIDENCE,
            run_id="run-1",
            subject_id="h1",
            statement="Opposing evidence was recorded against the ring-age reading.",
            provenance=("h1",),
            context="Which observation would change the ring-age hypothesis?",
            recorded_at=START,
        )
        advisor = FailureMemoryAdvisor()

        self.assertEqual(MIN_SHARED_TOKENS, 2)
        self.assertEqual(
            advisor.relevant(
                "Does quantum error correction reduce evidence loss?",
                [lesson],
            ),
            (),
        )
        self.assertEqual(
            advisor.relevant(
                "Which observation settles the ring-age question?",
                [lesson],
            ),
            (lesson,),
        )

    def test_recall_normalizes_edge_punctuation_on_both_sides(self) -> None:
        """A question mark in stored context may not hide a relevant lesson."""
        lesson = ResearchFailureLesson(
            lesson_id="lesson:run-1:operation_failure:ring-search",
            kind=FailureLessonKind.OPERATION_FAILURE,
            run_id="run-1",
            subject_id="ring-search",
            statement="Rings failed.",
            provenance=("failure:ring-search",),
            context="Which Saturn?",
            recorded_at=START,
        )

        self.assertEqual(
            FailureMemoryAdvisor().relevant("Saturn rings?", [lesson]),
            (lesson,),
        )

    def test_recall_discards_punctuation_only_fragments(self) -> None:
        lesson = ResearchFailureLesson(
            lesson_id="lesson:run-1:operation_failure:punctuation",
            kind=FailureLessonKind.OPERATION_FAILURE,
            run_id="run-1",
            subject_id="punctuation",
            statement="**** .... !!!!",
            provenance=("failure:punctuation",),
            context="",
            recorded_at=START,
        )

        self.assertEqual(lesson.tokens(), frozenset())
        self.assertEqual(FailureMemoryAdvisor().relevant("**** ....", [lesson]), ())

    def test_an_empty_question_recalls_nothing(self) -> None:
        self.assertEqual(FailureMemoryAdvisor().relevant("", []), ())
        self.assertEqual(FailureMemoryAdvisor().relevant("a bc", []), ())

    def test_an_out_of_range_recall_limit_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            FailureMemoryAdvisor(limit=MAX_RECALL_LIMIT + 1)
        with self.assertRaises(ValueError):
            FailureMemoryAdvisor(limit=0)

    def test_recall_requires_a_question(self) -> None:
        service = self.service()

        with self.assertRaises(ResearchError):
            service.process_recall(self.request("failure_memory_recall"))


class FailureMemoryServiceTests(FailureMemoryFixture):
    def failing_run(self) -> str:
        run_id = self.new_run()
        self.manager.record_failure(run_id, "source_fetch", "Refused.")
        return run_id

    def test_preview_derives_without_remembering(self) -> None:
        run_id = self.failing_run()
        service = self.service()

        response = service.process_preview(
            self.request("failure_memory_preview", research_run_id=run_id)
        )

        self.assertIn("Not remembered.", response.message)
        self.assertEqual(service.lessons(), ())
        self.assertFalse(self.lesson_path.exists())

    def test_the_response_says_a_lesson_is_not_a_universal_rule(self) -> None:
        run_id = self.failing_run()
        service = self.service()

        response = service.process_preview(
            self.request("failure_memory_preview", research_run_id=run_id)
        )

        self.assertIn("did not work here, not that it cannot work", response.message)

    def test_storing_persists_and_survives_a_restart(self) -> None:
        run_id = self.failing_run()
        first = self.service()

        first.process_store(
            self.request("failure_memory_store", research_run_id=run_id)
        )

        second = self.service()
        self.assertEqual(
            [lesson.lesson_id for lesson in second.lessons()],
            [lesson.lesson_id for lesson in first.lessons()],
        )

    def test_storing_twice_remembers_nothing_new(self) -> None:
        run_id = self.failing_run()
        service = self.service()
        request = self.request("failure_memory_store", research_run_id=run_id)

        service.process_store(request)
        first = service.lessons()
        service.process_store(request)

        self.assertEqual(service.lessons(), first)

    def test_deriving_and_storing_leave_the_run_byte_identical(self) -> None:
        run_id = self.failing_run()
        before = self.run_path.read_bytes()
        service = self.service()

        service.process_preview(
            self.request("failure_memory_preview", research_run_id=run_id)
        )
        service.process_store(
            self.request("failure_memory_store", research_run_id=run_id)
        )

        self.assertEqual(self.run_path.read_bytes(), before)

    def test_listing_derives_nothing_new(self) -> None:
        run_id = self.failing_run()
        service = self.service()
        service.process_store(
            self.request("failure_memory_store", research_run_id=run_id)
        )

        response = service.process_list(self.request("failure_memory_list"))

        self.assertIn("performs no research", response.message)
        self.assertEqual(len(service.lessons()), 1)

    def test_a_missing_run_identifier_is_refused(self) -> None:
        service = self.service()

        with self.assertRaises(ResearchError):
            service.process_preview(self.request("failure_memory_preview"))

    def test_disabled_persistence_writes_nothing(self) -> None:
        run_id = self.failing_run()
        service = self.service(persist=False)

        service.process_store(
            self.request("failure_memory_store", research_run_id=run_id)
        )

        self.assertEqual(len(service.lessons()), 1)
        self.assertFalse(self.lesson_path.exists())

    def test_a_failed_write_is_reported_and_keeps_the_lesson_in_memory(self) -> None:
        run_id = self.failing_run()
        service = self.service()
        request = self.request("failure_memory_store", research_run_id=run_id)

        with patch.object(
            JsonFileFailureLessonStore,
            "save",
            side_effect=ResearchError("disk full"),
        ):
            response = service.process_store(request)

        self.assertFalse(response.success)
        self.assertEqual(len(response.failure_lessons), 1)
        self.assertIn("not durably remembered", response.message)
        self.assertIn("Durable write: failed", response.message)
        self.assertIn("may lose", response.message)
        self.assertEqual(len(service.lessons()), 1)
        self.assertEqual(self.service().lessons(), ())
        self.assertEqual(self.named(LESSONS_STORED), [])

    def test_an_explicit_second_store_retries_a_pending_write(self) -> None:
        run_id = self.failing_run()
        service = self.service()
        request = self.request("failure_memory_store", research_run_id=run_id)

        with patch.object(
            JsonFileFailureLessonStore,
            "save",
            side_effect=ResearchError("disk full"),
        ):
            first = service.process_store(request)

        second = service.process_store(request)

        self.assertFalse(first.success)
        self.assertTrue(second.success)
        self.assertEqual(len(self.service().lessons()), 1)


class FailureMemoryEventTests(FailureMemoryFixture):
    def test_the_pipeline_emits_bounded_events(self) -> None:
        run_id = self.new_run()
        self.manager.record_failure(run_id, "source_fetch", "Refused.")
        service = self.service()

        service.process_store(
            self.request("failure_memory_store", research_run_id=run_id)
        )
        service.process_recall(
            self.request("failure_memory_recall", research_question=QUESTION)
        )

        for name in (LESSONS_DERIVED, LESSONS_STORED, LESSONS_RECALLED):
            self.assertTrue(self.named(name), name)

    def test_no_event_carries_a_statement_question_or_provenance_list(self) -> None:
        run_id, _, evidence_id = self.sourced_run()
        self.manager.record_failure(
            run_id,
            "source_fetch",
            "Publisher redirect was plain HTTP.",
        )
        run = self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings are demonstrably young.",
            ResearchEpistemicState.HYPOTHESIS,
        )
        self.manager.record_claim(
            run_id,
            [evidence_id],
            "The rings are ancient after all.",
            ResearchEpistemicState.LIKELY,
            supersedes_claim_id=run.claims[-1].claim_id,
        )
        service = self.service()
        service.process_store(
            self.request("failure_memory_store", research_run_id=run_id)
        )

        payloads = json.dumps(
            [
                event.payload
                for event in self.events
                if event.name.startswith("failure_memory")
            ]
        )

        self.assertTrue(payloads)
        self.assertNotIn("demonstrably young", payloads)
        self.assertNotIn("plain HTTP", payloads)
        self.assertNotIn(QUESTION, payloads)
        self.assertNotIn("example.test", payloads)

    def test_recall_events_declare_themselves_advisory(self) -> None:
        service = self.service()

        service.process_recall(
            self.request("failure_memory_recall", research_question=QUESTION)
        )

        for event in self.named(LESSONS_RECALLED):
            self.assertIs(event.payload["advisory"], True)
            self.assertIs(event.payload["executed"], False)


class FailureLessonStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "lessons.json"
        self.store = JsonFileFailureLessonStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def lesson(index: int = 1) -> ResearchFailureLesson:
        return ResearchFailureLesson(
            lesson_id=f"lesson:run-1:operation_failure:stage-{index}",
            kind=FailureLessonKind.OPERATION_FAILURE,
            run_id="run-1",
            subject_id=f"stage-{index}",
            statement="The fetch stage failed here.",
            provenance=(f"failure:stage-{index}",),
            context=QUESTION,
            recorded_at=START,
        )

    def test_an_absent_store_loads_empty(self) -> None:
        self.assertEqual(self.store.load(), [])

    def test_a_saved_lesson_round_trips_with_its_provenance(self) -> None:
        original = self.lesson()

        self.store.save([original])
        reloaded = self.store.load()

        self.assertEqual(reloaded, [original])
        self.assertEqual(reloaded[0].provenance, original.provenance)

    def test_a_legacy_failed_hypothesis_lesson_still_loads(self) -> None:
        original = replace(
            self.lesson(),
            lesson_id="lesson:run-1:failed_hypothesis:claim-1",
            kind=FailureLessonKind.FAILED_HYPOTHESIS,
            subject_id="claim-1",
        )

        self.store.save([original])

        self.assertEqual(self.store.load(), [original])

    def test_a_malformed_document_is_refused(self) -> None:
        self.path.write_text("{ not json", encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_an_unsupported_schema_version_is_refused(self) -> None:
        self.path.write_text(
            json.dumps({"schema_version": 99, "lessons": []}),
            encoding="utf-8",
        )

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_a_stored_lesson_stripped_of_provenance_is_refused(self) -> None:
        self.store.save([self.lesson()])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["lessons"][0]["provenance"] = []
        self.path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_an_unknown_lesson_kind_is_refused(self) -> None:
        self.store.save([self.lesson()])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["lessons"][0]["kind"] = "invented"
        self.path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_duplicate_lesson_identifiers_are_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.store.save([self.lesson(), self.lesson()])

    def test_too_many_lessons_are_refused(self) -> None:
        lessons = [
            replace(self.lesson(), lesson_id=f"lesson:{index}")
            for index in range(MAX_FAILURE_STORE_LESSONS + 1)
        ]

        with self.assertRaises(ResearchError):
            self.store.save(lessons)

    def test_a_failed_write_leaves_the_previous_document_intact(self) -> None:
        self.store.save([self.lesson()])
        before = self.path.read_bytes()

        with (
            patch("research.JsonFileFailureLessonStore.os.replace") as replace_call,
            self.assertRaises(ResearchError),
        ):
            replace_call.side_effect = OSError("no space")
            self.store.save([self.lesson(1), self.lesson(2)])

        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])


class FailureMemoryCompositionTests(FailureMemoryFixture):
    def test_failure_memory_is_disabled_without_the_flag(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            bootstrap = Bootstrap(
                memory_path=self.root / "memory.json",
                session_path=self.root / "sessions.json",
            )

            self.assertIsNone(bootstrap._failure_lesson_store())

    def test_the_flag_enables_a_store_beside_the_run_store(self) -> None:
        with patch.dict(
            os.environ,
            {"HYPATIA_FAILURE_MEMORY_ENABLED": "true"},
            clear=True,
        ):
            bootstrap = Bootstrap(
                memory_path=self.root / "memory.json",
                session_path=self.root / "sessions.json",
                research_run_path=self.root / "runs.json",
            )

            store = bootstrap._failure_lesson_store()

            self.assertIsNotNone(store)
            assert store is not None
            self.assertEqual(
                store._path,
                self.root / "research_failure_lessons.json",
            )

    def test_the_engine_routes_failure_memory_over_the_run_manager(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()
        self.manager.record_failure(run_id, "source_fetch", "Refused.")

        response = engine.process(
            BrainRequest(
                message="Lessons",
                metadata={
                    "intent": "failure_memory_preview",
                    "research_run_id": run_id,
                },
            )
        )

        service = engine._failure_memory_service
        self.assertIsInstance(service, FailureMemoryApplicationService)
        assert service is not None
        self.assertIs(service._run_manager, self.manager)
        self.assertIsNone(service._lesson_store)
        self.assertTrue(response.failure_lessons)

    def test_failure_memory_is_refused_without_run_persistence(self) -> None:
        engine = self.build_engine(with_runs=False)

        response = engine.process(
            BrainRequest(
                message="Lessons",
                metadata={
                    "intent": "failure_memory_preview",
                    "research_run_id": "run-1",
                },
            )
        )

        self.assertIsNone(engine._failure_memory_service)
        self.assertFalse(response.success)
        self.assertIn("unavailable", response.message)

    def test_an_unknown_run_is_refused_without_raising(self) -> None:
        engine = self.build_engine()

        response = engine.process(
            BrainRequest(
                message="Lessons",
                metadata={
                    "intent": "failure_memory_preview",
                    "research_run_id": "run-missing",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("rejected", response.message)

    def build_engine(self, with_runs: bool = True) -> CognitiveEngine:
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
        )


if __name__ == "__main__":
    unittest.main()
