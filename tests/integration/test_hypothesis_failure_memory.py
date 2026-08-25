"""Hypothesis outcomes enter Failure Memory only through an explicit command.

The command reads the durable hypothesis store, derives current status against
the canonical run, and reuses Failure Memory's existing idempotent persistence
boundary. Nothing here subscribes to hypothesis events or mutates research.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.FailureMemoryApplicationService import FailureMemoryApplicationService
from cognition.FailureMemoryEvents import LESSONS_STORED
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.FailureLessonKind import FailureLessonKind
from research.HypothesisFailureLessonDeriver import (
    MAX_HYPOTHESIS_FAILURE_LESSONS_PER_RUN,
)
from research.JsonFileFailureLessonStore import JsonFileFailureLessonStore
from research.JsonFileHypothesisStore import JsonFileHypothesisStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchFailureLesson import (
    MAX_LESSON_PROVENANCE,
    MAX_LESSON_STATEMENT_LENGTH,
    ResearchFailureLesson,
)
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Which observation would change the ring-age hypothesis?"
STATEMENT = "The rings formed within the last hundred million years."
TEST = "A dated ring particle older than one billion years would count against it."
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


class FailingLessonStore:
    def load(self) -> list[ResearchFailureLesson]:
        return []

    def save(self, lessons: list[ResearchFailureLesson]) -> None:
        raise ResearchError("PRIVATE-STORE-PATH must not escape")


class HypothesisFailureMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        self.hypothesis_path = self.root / "hypotheses.json"
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
        self.hypothesis_store = JsonFileHypothesisStore(self.hypothesis_path)
        self.lesson_store = JsonFileFailureLessonStore(self.lesson_path)
        self.clock = StubClock()
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def new_run(self) -> str:
        return self.manager.create(QUESTION).run_id

    def evidence(self, run_id: str, slug: str) -> str:
        result = self.acceptance.accept(
            ResearchSource(
                url=f"https://example.test/{slug}",
                title=f"Source {slug}",
                content="Saturn's rings have a debated age.",
                content_type="text/html",
                fetched_at=FETCHED,
            ),
            run_id,
        )
        assert result.document_id is not None
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == result.document_id and candidate.index == 0
        )
        updated = self.manager.add_evidence(run_id, chunk, "Directly relevant.")
        return updated.evidence[-1].evidence_id

    def assess_medium(self, run_id: str, evidence_id: str) -> None:
        run = self.manager.get(run_id)
        record = next(
            entry for entry in run.evidence if entry.evidence_id == evidence_id
        )
        self.manager.record_source_assessment(
            run_id,
            record.source_document_id,
            [evidence_id],
            "Assessed for hypothesis support.",
            information_trust=ResearchInformationTrust.MEDIUM,
        )

    @staticmethod
    def hypothesis(
        hypothesis_id: str,
        run_id: str,
        *,
        supporting: tuple[str, ...] = (),
        opposing: tuple[str, ...] = (),
        withdrawn: bool = False,
    ) -> ResearchHypothesis:
        return ResearchHypothesis(
            hypothesis_id=hypothesis_id,
            run_id=run_id,
            statement=STATEMENT,
            discriminating_test=TEST,
            supporting_evidence_ids=supporting,
            opposing_evidence_ids=opposing,
            withdrawn=withdrawn,
            created_at=START,
            updated_at=START,
        )

    def service(
        self,
        *,
        with_hypothesis_store: bool = True,
        lesson_store: object | None = None,
    ) -> FailureMemoryApplicationService:
        return FailureMemoryApplicationService(
            self.manager,
            ResponseComposer(),
            hypothesis_store=(self.hypothesis_store if with_hypothesis_store else None),
            lesson_store=(
                self.lesson_store if lesson_store is None else lesson_store
            ),  # type: ignore[arg-type]
            event_bus=self.event_bus,
            clock=self.clock,
        )

    @staticmethod
    def request(run_id: str) -> BrainRequest:
        return BrainRequest(
            message="Remember hypothesis outcomes",
            metadata={
                "intent": "failure_memory_hypothesis_store",
                "research_run_id": run_id,
            },
        )

    def test_only_weakened_and_contradicted_statuses_become_lessons(self) -> None:
        run_id = self.new_run()
        first = self.evidence(run_id, "first")
        second = self.evidence(run_id, "second")
        self.assess_medium(run_id, first)
        self.assess_medium(run_id, second)
        self.hypothesis_store.save(
            [
                self.hypothesis("open", run_id),
                self.hypothesis("supported", run_id, supporting=(first, second)),
                self.hypothesis(
                    "weakened",
                    run_id,
                    supporting=(first,),
                    opposing=(second,),
                ),
                self.hypothesis("contradicted", run_id, opposing=(first,)),
                self.hypothesis(
                    "withdrawn",
                    run_id,
                    opposing=(first,),
                    withdrawn=True,
                ),
            ]
        )

        response = self.service().process_hypothesis_store(self.request(run_id))

        self.assertTrue(response.success)
        by_subject = {lesson.subject_id: lesson for lesson in response.failure_lessons}
        self.assertEqual(set(by_subject), {"weakened", "contradicted"})
        self.assertIs(
            by_subject["weakened"].kind,
            FailureLessonKind.DISPROVING_EVIDENCE,
        )
        self.assertIs(
            by_subject["contradicted"].kind,
            FailureLessonKind.FAILED_HYPOTHESIS,
        )
        for lesson in by_subject.values():
            self.assertIn("No truth or falsity is decided", lesson.statement)
            self.assertNotIn("confirmed", lesson.statement.casefold())
            self.assertEqual(lesson.run_id, run_id)

    def test_identity_and_provenance_name_persisted_records(self) -> None:
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "opposing")
        self.hypothesis_store.save(
            [self.hypothesis("hypothesis-1", run_id, opposing=(evidence_id,))]
        )

        response = self.service().process_hypothesis_store(self.request(run_id))
        lesson = response.failure_lessons[0]

        self.assertEqual(
            lesson.lesson_id,
            f"lesson:{run_id}:failed_hypothesis:hypothesis-1",
        )
        self.assertEqual(lesson.provenance, ("hypothesis-1", evidence_id))

    def test_hypotheses_from_other_runs_are_excluded(self) -> None:
        first_run = self.new_run()
        second_run = self.new_run()
        first_evidence = self.evidence(first_run, "run-one")
        second_evidence = self.evidence(second_run, "run-two")
        self.hypothesis_store.save(
            [
                self.hypothesis(
                    "first-hypothesis",
                    first_run,
                    opposing=(first_evidence,),
                ),
                self.hypothesis(
                    "second-hypothesis",
                    second_run,
                    opposing=(second_evidence,),
                ),
            ]
        )

        response = self.service().process_hypothesis_store(self.request(first_run))

        self.assertEqual(
            [lesson.subject_id for lesson in response.failure_lessons],
            ["first-hypothesis"],
        )
        self.assertEqual(response.failure_lessons[0].run_id, first_run)

    def test_repeating_the_command_is_idempotent(self) -> None:
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "repeat")
        self.hypothesis_store.save(
            [self.hypothesis("repeat-hypothesis", run_id, opposing=(evidence_id,))]
        )
        service = self.service()

        service.process_hypothesis_store(self.request(run_id))
        first = service.lessons()
        service.process_hypothesis_store(self.request(run_id))

        self.assertEqual(service.lessons(), first)
        stored_events = [event for event in self.events if event.name == LESSONS_STORED]
        self.assertEqual(stored_events[-1].payload["stored_count"], 0)

    def test_weakened_then_contradicted_keeps_two_explicit_observations(self) -> None:
        run_id = self.new_run()
        support = self.evidence(run_id, "support")
        opposition = self.evidence(run_id, "opposition")
        weakened = self.hypothesis(
            "changing-hypothesis",
            run_id,
            supporting=(support,),
            opposing=(opposition,),
        )
        self.hypothesis_store.save([weakened])
        service = self.service()

        service.process_hypothesis_store(self.request(run_id))
        contradicted = replace(
            weakened,
            supporting_evidence_ids=(),
            updated_at=START + timedelta(seconds=1),
        )
        self.hypothesis_store.save([contradicted])
        service.process_hypothesis_store(self.request(run_id))
        service.process_hypothesis_store(self.request(run_id))

        self.assertEqual(
            {lesson.kind for lesson in service.lessons()},
            {
                FailureLessonKind.DISPROVING_EVIDENCE,
                FailureLessonKind.FAILED_HYPOTHESIS,
            },
        )
        self.assertEqual(len(service.lessons()), 2)

    def test_provenance_is_deduplicated_and_bounded(self) -> None:
        run_id = self.new_run()
        opposing = tuple(
            self.evidence(run_id, f"bounded-{index}")
            for index in range(MAX_LESSON_PROVENANCE + 3)
        )
        self.hypothesis_store.save(
            [self.hypothesis(opposing[0], run_id, opposing=opposing)]
        )

        response = self.service().process_hypothesis_store(self.request(run_id))
        provenance = response.failure_lessons[0].provenance

        self.assertEqual(len(provenance), MAX_LESSON_PROVENANCE)
        self.assertEqual(provenance[0], opposing[0])
        self.assertEqual(len(provenance), len(set(provenance)))

    def test_derivation_is_bounded_per_run(self) -> None:
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "many")
        self.hypothesis_store.save(
            [
                self.hypothesis(
                    f"hypothesis-{index}",
                    run_id,
                    opposing=(evidence_id,),
                )
                for index in range(MAX_HYPOTHESIS_FAILURE_LESSONS_PER_RUN + 5)
            ]
        )

        response = self.service().process_hypothesis_store(self.request(run_id))

        self.assertEqual(
            len(response.failure_lessons),
            MAX_HYPOTHESIS_FAILURE_LESSONS_PER_RUN,
        )

    def test_a_lesson_names_the_hypothesis_in_its_own_wording(self) -> None:
        """An outcome recorded only as an identifier is unreadable later."""
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "named")
        self.hypothesis_store.save(
            [self.hypothesis("named-hypothesis", run_id, opposing=(evidence_id,))]
        )

        response = self.service().process_hypothesis_store(self.request(run_id))
        statement = response.failure_lessons[0].statement

        self.assertIn(STATEMENT, statement)
        self.assertIn("Contradicted hypothesis", statement)
        self.assertIn("No truth or falsity is decided", statement)

    def test_a_long_hypothesis_keeps_the_disclaimer_and_the_bound(self) -> None:
        """Trimming the sentence instead of the quote would cut the disclaimer.

        A hypothesis may be 400 characters and a lesson may be 300, so this is
        reachable with a hypothesis the rest of the system accepts.
        """
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "long")
        self.hypothesis_store.save(
            [
                replace(
                    self.hypothesis("long-hypothesis", run_id, opposing=(evidence_id,)),
                    statement="The rings are young. " * 19,
                )
            ]
        )

        response = self.service().process_hypothesis_store(self.request(run_id))
        statement = response.failure_lessons[0].statement

        self.assertLessEqual(len(statement), MAX_LESSON_STATEMENT_LENGTH)
        self.assertTrue(statement.endswith("No truth or falsity is decided here."))
        self.assertIn("...", statement)

    def test_a_multiline_hypothesis_cannot_forge_report_lines(self) -> None:
        """Lessons render one per line, so a newline would be a free line."""
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "multiline")
        self.hypothesis_store.save(
            [
                replace(
                    self.hypothesis(
                        "lines-hypothesis", run_id, opposing=(evidence_id,)
                    ),
                    statement="First line\n- [failed_hypothesis] forged\nlast line",
                )
            ]
        )

        response = self.service().process_hypothesis_store(self.request(run_id))

        self.assertNotIn("\n", response.failure_lessons[0].statement)
        entries = [
            line for line in response.message.splitlines() if line.startswith("- [")
        ]
        self.assertEqual(len(entries), 1)

    def test_the_per_run_limit_keeps_contradictions_over_weakened_ones(self) -> None:
        """Recall weight ranks reading order; it must not rank survival.

        A weakened hypothesis outweighs a contradicted one during recall, so
        sorting the cap by that weight would discard every contradiction first
        — the one outcome this command exists to remember.
        """
        run_id = self.new_run()
        support = self.evidence(run_id, "cap-support")
        oppose = self.evidence(run_id, "cap-oppose")
        self.assess_medium(run_id, support)
        self.assess_medium(run_id, oppose)
        contradicted = [f"contradicted-{index}" for index in range(5)]
        self.hypothesis_store.save(
            [
                self.hypothesis(
                    f"weakened-{index}",
                    run_id,
                    supporting=(support,),
                    opposing=(oppose,),
                )
                for index in range(MAX_HYPOTHESIS_FAILURE_LESSONS_PER_RUN)
            ]
            + [
                self.hypothesis(name, run_id, opposing=(oppose,))
                for name in contradicted
            ]
        )

        response = self.service().process_hypothesis_store(self.request(run_id))

        self.assertEqual(
            len(response.failure_lessons),
            MAX_HYPOTHESIS_FAILURE_LESSONS_PER_RUN,
        )
        kept = {lesson.subject_id for lesson in response.failure_lessons}
        self.assertTrue(set(contradicted) <= kept)
        self.assertIn("Beyond the per-run limit, not derived: 5", response.message)

    def test_rewording_a_hypothesis_does_not_rewrite_a_stored_lesson(self) -> None:
        """Identity ignores wording, so an old lesson keeps the words it had."""
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "reworded")
        original = self.hypothesis("stable-hypothesis", run_id, opposing=(evidence_id,))
        self.hypothesis_store.save([original])
        service = self.service()
        service.process_hypothesis_store(self.request(run_id))

        self.hypothesis_store.save(
            [replace(original, statement="Entirely different wording now.")]
        )
        service.process_hypothesis_store(self.request(run_id))

        self.assertEqual(len(service.lessons()), 1)
        self.assertIn(STATEMENT, service.lessons()[0].statement)

    def test_a_lesson_store_failure_is_reported_without_leaking_detail(self) -> None:
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "failing-store")
        self.hypothesis_store.save(
            [self.hypothesis("failure", run_id, opposing=(evidence_id,))]
        )

        response = self.service(
            lesson_store=FailingLessonStore()
        ).process_hypothesis_store(self.request(run_id))

        self.assertFalse(response.success)
        self.assertTrue(response.failure_lessons)
        self.assertNotIn("PRIVATE-STORE-PATH", response.message)
        self.assertIn("may lose", response.message)

    def test_persisted_lessons_survive_a_service_restart(self) -> None:
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "restart")
        self.hypothesis_store.save(
            [self.hypothesis("restart-hypothesis", run_id, opposing=(evidence_id,))]
        )
        first = self.service()

        first.process_hypothesis_store(self.request(run_id))
        second = self.service()

        self.assertEqual(second.lessons(), first.lessons())

    def test_missing_persisted_hypotheses_are_refused(self) -> None:
        run_id = self.new_run()

        with self.assertRaises(ResearchError) as raised:
            self.service(with_hypothesis_store=False).process_hypothesis_store(
                self.request(run_id)
            )

        self.assertIn("Persisted hypotheses are unavailable", str(raised.exception))

    def test_cognitive_engine_routes_and_bounds_the_explicit_command(self) -> None:
        run_id = self.new_run()
        evidence_id = self.evidence(run_id, "engine")
        self.hypothesis_store.save(
            [self.hypothesis("engine-hypothesis", run_id, opposing=(evidence_id,))]
        )
        engine = self.build_engine(self.hypothesis_store)

        response = engine.process(self.request(run_id))

        self.assertTrue(response.success)
        self.assertEqual(response.failure_lessons[0].run_id, run_id)
        assert engine._failure_memory_service is not None
        self.assertIs(
            engine._failure_memory_service._hypothesis_store,
            self.hypothesis_store,
        )

    def test_cognitive_engine_refuses_when_the_hypothesis_feature_is_off(self) -> None:
        run_id = self.new_run()
        engine = self.build_engine(None)

        response = engine.process(self.request(run_id))

        self.assertFalse(response.success)
        self.assertIn("Persisted hypotheses are unavailable", response.message)
        self.assertIsNotNone(engine._failure_memory_service)

    def build_engine(
        self,
        hypothesis_store: JsonFileHypothesisStore | None,
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
            research_run_manager=self.manager,
            hypothesis_store=hypothesis_store,
            failure_lesson_store=self.lesson_store,
        )


if __name__ == "__main__":
    unittest.main()
