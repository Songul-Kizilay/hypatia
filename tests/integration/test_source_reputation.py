"""Reputation counts our own judgements, and is never allowed to decide.

Reputation is the part of a research system most likely to turn into prejudice:
two bad pages from a host become a rule, the rule quietly filters what gets
read, and nothing after that can disconfirm it. So the tests assert the
absence of power as hard as the presence of memory — no fetch refused, no
evidence discounted, no source pre-assessed, no assessment changed.

They also assert the sample is never hidden. Below three assessments the
standing says "provisional" out loud, because two bad experiences is a
coincidence, not a reputation.

Nothing here touches a network.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from cognition.SourceReputationApplicationService import (
    SourceReputationApplicationService,
)
from cognition.SourceReputationEvents import REPUTATION_REPORTED
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.SourceOrigin import origin_of
from research.SourceReputation import SourceReputation
from research.SourceReputationLedger import SourceReputationLedger
from research.SourceStanding import MIN_ASSESSMENTS_FOR_STANDING, SourceStanding
from response.ResponseComposer import ResponseComposer
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the ring system have a measured age?"
FETCHED = datetime(2026, 8, 1, tzinfo=UTC)


class InMemoryContentStore:
    def __init__(self) -> None:
        self.records: list[object] = []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, records: list[object]) -> None:
        self.records = list(records)


class OriginTests(unittest.TestCase):
    def test_a_host_is_lowercased_and_stripped_of_www(self) -> None:
        self.assertEqual(origin_of("https://WWW.Example.COM/page"), "example.com")

    def test_a_port_is_not_part_of_the_origin(self) -> None:
        self.assertEqual(origin_of("https://example.com:8443/page"), "example.com")

    def test_subdomains_are_kept_separate(self) -> None:
        self.assertNotEqual(
            origin_of("https://docs.example.com/a"),
            origin_of("https://example.com/a"),
        )

    def test_an_unusable_url_has_no_origin(self) -> None:
        for value in ("", "   ", "not a url", None):
            with self.subTest(value=value):
                self.assertEqual(origin_of(value), "")  # type: ignore[arg-type]


class StandingTests(unittest.TestCase):
    @staticmethod
    def reputation(**counts: int) -> SourceReputation:
        return SourceReputation(origin="example.com", **counts)

    def test_no_assessment_means_unknown(self) -> None:
        self.assertIs(
            self.reputation(accepted_count=4).standing,
            SourceStanding.UNKNOWN,
        )

    def test_a_small_sample_is_provisional(self) -> None:
        self.assertIs(
            self.reputation(
                accepted_count=2,
                assessed_count=2,
                low_count=2,
            ).standing,
            SourceStanding.PROVISIONAL,
        )

    def test_consistently_low_needs_the_full_threshold(self) -> None:
        reputation = self.reputation(
            accepted_count=MIN_ASSESSMENTS_FOR_STANDING,
            assessed_count=MIN_ASSESSMENTS_FOR_STANDING,
            low_count=MIN_ASSESSMENTS_FOR_STANDING,
        )

        self.assertIs(reputation.standing, SourceStanding.CONSISTENTLY_LOW)

    def test_consistently_trusted_needs_no_low_assessment(self) -> None:
        reputation = self.reputation(
            accepted_count=3,
            assessed_count=3,
            high_count=2,
            medium_count=1,
        )

        self.assertIs(reputation.standing, SourceStanding.CONSISTENTLY_TRUSTED)

    def test_one_low_among_trusted_makes_it_mixed(self) -> None:
        reputation = self.reputation(
            accepted_count=4,
            assessed_count=4,
            high_count=2,
            medium_count=1,
            low_count=1,
        )

        self.assertIs(reputation.standing, SourceStanding.MIXED)

    def test_only_a_full_sample_counts_as_established(self) -> None:
        self.assertFalse(SourceStanding.UNKNOWN.established)
        self.assertFalse(SourceStanding.PROVISIONAL.established)
        self.assertTrue(SourceStanding.MIXED.established)
        self.assertTrue(SourceStanding.CONSISTENTLY_LOW.established)

    def test_no_standing_decides_anything(self) -> None:
        for standing in SourceStanding:
            with self.subTest(standing=standing):
                self.assertFalse(standing.decides_anything)

    def test_unassessed_sources_are_reported_separately(self) -> None:
        reputation = self.reputation(
            accepted_count=5,
            assessed_count=2,
            high_count=2,
        )

        self.assertEqual(reputation.unassessed_count, 3)

    def test_counts_that_exceed_their_totals_are_refused(self) -> None:
        with self.assertRaises(ResearchError):
            SourceReputation(origin="example.com", assessed_count=1, high_count=2)
        with self.assertRaises(ResearchError):
            SourceReputation(origin="example.com", accepted_count=1, assessed_count=2)

    def test_a_blank_origin_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            SourceReputation(origin="  ")

    def test_a_negative_count_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            SourceReputation(origin="example.com", accepted_count=-1)


class ReputationLedgerFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
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
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.ledger = SourceReputationLedger()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def service(self) -> SourceReputationApplicationService:
        return SourceReputationApplicationService(
            self.manager,
            ResponseComposer(),
            event_bus=self.event_bus,
        )

    def new_run(self) -> str:
        return self.manager.create(QUESTION).run_id

    def accept(self, run_id: str, url: str) -> str:
        result = self.acceptance.accept(
            ResearchSource(
                url=url,
                title="A source",
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

    def assess(
        self,
        run_id: str,
        document_id: str,
        evidence_id: str,
        trust: ResearchInformationTrust,
        supersedes: str | None = None,
    ) -> str:
        run = self.manager.record_source_assessment(
            run_id,
            document_id,
            [evidence_id],
            "Assessed for the reputation test.",
            supersedes_assessment_id=supersedes,
            information_trust=trust,
        )
        return run.assessments[-1].assessment_id

    def graded(
        self,
        run_id: str,
        url: str,
        trust: ResearchInformationTrust,
    ) -> str:
        document_id = self.accept(run_id, url)
        evidence_id = self.add_evidence(run_id, document_id)
        self.assess(run_id, document_id, evidence_id, trust)
        return document_id

    def build(self) -> tuple[SourceReputation, ...]:
        return self.ledger.build(self.manager.list())

    def request(self, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="Reputation",
            metadata={"intent": "source_reputation_report", **metadata},
        )


class ReputationLedgerTests(ReputationLedgerFixture):
    def test_assessments_are_aggregated_by_origin(self) -> None:
        run_id = self.new_run()
        self.graded(run_id, "https://good.test/a", ResearchInformationTrust.HIGH)
        self.graded(run_id, "https://good.test/b", ResearchInformationTrust.MEDIUM)
        self.graded(run_id, "https://weak.test/a", ResearchInformationTrust.LOW)

        reputations = {entry.origin: entry for entry in self.build()}

        self.assertEqual(reputations["good.test"].assessed_count, 2)
        self.assertEqual(reputations["good.test"].high_count, 1)
        self.assertEqual(reputations["weak.test"].low_count, 1)

    def test_acceptance_alone_is_not_a_judgement(self) -> None:
        run_id = self.new_run()
        self.accept(run_id, "https://unjudged.test/a")

        reputation = next(
            entry for entry in self.build() if entry.origin == "unjudged.test"
        )

        self.assertEqual(reputation.accepted_count, 1)
        self.assertEqual(reputation.assessed_count, 0)
        self.assertIs(reputation.standing, SourceStanding.UNKNOWN)

    def test_a_superseded_assessment_no_longer_counts(self) -> None:
        run_id = self.new_run()
        document_id = self.accept(run_id, "https://revised.test/a")
        evidence_id = self.add_evidence(run_id, document_id)
        first = self.assess(
            run_id,
            document_id,
            evidence_id,
            ResearchInformationTrust.LOW,
        )
        self.assess(
            run_id,
            document_id,
            evidence_id,
            ResearchInformationTrust.HIGH,
            supersedes=first,
        )

        reputation = next(
            entry for entry in self.build() if entry.origin == "revised.test"
        )

        self.assertEqual(reputation.low_count, 0)
        self.assertEqual(reputation.high_count, 1)

    def test_parallel_high_trust_does_not_hide_an_active_low_assessment(self) -> None:
        run_id = self.new_run()
        document_id = self.accept(run_id, "https://mixed.test/a")
        evidence_id = self.add_evidence(run_id, document_id)
        self.assess(
            run_id,
            document_id,
            evidence_id,
            ResearchInformationTrust.LOW,
        )
        self.assess(
            run_id,
            document_id,
            evidence_id,
            ResearchInformationTrust.HIGH,
        )

        reputation = next(
            entry for entry in self.build() if entry.origin == "mixed.test"
        )

        self.assertEqual(reputation.assessed_count, 1)
        self.assertEqual(reputation.low_count, 1)
        self.assertEqual(reputation.high_count, 0)

    def test_equivalent_resource_trust_is_cautious_and_order_invariant(self) -> None:
        first_run = self.new_run()
        self.graded(
            first_run,
            "https://www.mixed.test/shared",
            ResearchInformationTrust.HIGH,
        )
        second_run = self.new_run()
        self.graded(
            second_run,
            "https://mixed.test/shared/",
            ResearchInformationTrust.LOW,
        )

        runs = self.manager.list()
        forward = next(
            entry for entry in self.ledger.build(runs) if entry.origin == "mixed.test"
        )
        reverse = next(
            entry
            for entry in self.ledger.build(reversed(runs))
            if entry.origin == "mixed.test"
        )

        self.assertEqual(forward, reverse)
        self.assertEqual(forward.accepted_count, 2)
        self.assertEqual(forward.assessed_count, 1)
        self.assertEqual(forward.low_count, 1)
        self.assertEqual(forward.high_count, 0)

    def test_reputation_accumulates_across_runs(self) -> None:
        for index in range(MIN_ASSESSMENTS_FOR_STANDING):
            run_id = self.new_run()
            self.graded(
                run_id,
                f"https://recurring.test/{index}",
                ResearchInformationTrust.LOW,
            )

        reputation = next(
            entry for entry in self.build() if entry.origin == "recurring.test"
        )

        self.assertEqual(reputation.run_count, MIN_ASSESSMENTS_FOR_STANDING)
        self.assertIs(reputation.standing, SourceStanding.CONSISTENTLY_LOW)

    def test_two_bad_pages_are_only_provisional(self) -> None:
        run_id = self.new_run()
        self.graded(run_id, "https://unlucky.test/a", ResearchInformationTrust.LOW)
        self.graded(run_id, "https://unlucky.test/b", ResearchInformationTrust.LOW)

        reputation = next(
            entry for entry in self.build() if entry.origin == "unlucky.test"
        )

        self.assertIs(reputation.standing, SourceStanding.PROVISIONAL)

    def test_evidence_is_counted_per_origin(self) -> None:
        run_id = self.new_run()
        document_id = self.accept(run_id, "https://cited.test/a")
        self.add_evidence(run_id, document_id)

        reputation = next(
            entry for entry in self.build() if entry.origin == "cited.test"
        )

        self.assertEqual(reputation.evidence_count, 1)

    def test_origins_are_ordered_by_how_much_we_judged_them(self) -> None:
        run_id = self.new_run()
        self.graded(run_id, "https://many.test/a", ResearchInformationTrust.HIGH)
        self.graded(run_id, "https://many.test/b", ResearchInformationTrust.HIGH)
        self.graded(run_id, "https://few.test/a", ResearchInformationTrust.HIGH)

        origins = [entry.origin for entry in self.build()]

        self.assertLess(origins.index("many.test"), origins.index("few.test"))

    def test_no_runs_means_no_reputation(self) -> None:
        self.assertEqual(self.build(), ())

    def test_one_origin_can_be_looked_up_directly(self) -> None:
        run_id = self.new_run()
        self.graded(run_id, "https://looked.test/a", ResearchInformationTrust.HIGH)

        found = self.ledger.for_origin("looked.test", self.manager.list())
        missing = self.ledger.for_origin("absent.test", self.manager.list())

        assert found is not None
        self.assertEqual(found.origin, "looked.test")
        self.assertIsNone(missing)


class ReputationGatesNothingTests(ReputationLedgerFixture):
    def low_standing_origin(self) -> str:
        for index in range(MIN_ASSESSMENTS_FOR_STANDING):
            run_id = self.new_run()
            self.graded(
                run_id,
                f"https://weak.test/{index}",
                ResearchInformationTrust.LOW,
            )
        return "weak.test"

    def test_a_low_standing_does_not_stop_a_later_acceptance(self) -> None:
        origin = self.low_standing_origin()
        run_id = self.new_run()

        document_id = self.accept(run_id, f"https://{origin}/later")

        self.assertTrue(document_id)
        self.assertIn(
            document_id,
            [source.document_id for source in self.manager.get(run_id).sources],
        )

    def test_a_low_standing_does_not_pre_assess_a_new_source(self) -> None:
        origin = self.low_standing_origin()
        run_id = self.new_run()

        self.accept(run_id, f"https://{origin}/later")

        self.assertEqual(self.manager.get(run_id).assessments, ())

    def test_reporting_leaves_the_run_store_byte_identical(self) -> None:
        self.low_standing_origin()
        before = self.run_path.read_bytes()
        service = self.service()

        for _ in range(3):
            service.process_report(self.request())

        self.assertEqual(self.run_path.read_bytes(), before)

    def test_the_report_says_it_gates_nothing(self) -> None:
        self.low_standing_origin()

        response = self.service().process_report(self.request())

        self.assertIn("no standing gates anything", response.message)
        self.assertIn("no fetch was refused", response.message)
        self.assertIn("no assessment", response.message)

    def test_the_report_is_derived_not_stored(self) -> None:
        self.low_standing_origin()

        self.service().process_report(self.request())
        files = sorted(path.name for path in self.root.glob("*.json"))

        self.assertEqual(files, ["runs.json"])

    def test_revising_an_assessment_revises_the_reputation(self) -> None:
        run_id = self.new_run()
        document_id = self.accept(run_id, "https://revised.test/a")
        evidence_id = self.add_evidence(run_id, document_id)
        first = self.assess(
            run_id,
            document_id,
            evidence_id,
            ResearchInformationTrust.LOW,
        )
        service = self.service()
        before = service.process_report(self.request(source_origin="revised.test"))

        self.assess(
            run_id,
            document_id,
            evidence_id,
            ResearchInformationTrust.HIGH,
            supersedes=first,
        )
        after = service.process_report(self.request(source_origin="revised.test"))

        self.assertEqual(before.source_reputations[0].low_count, 1)
        self.assertEqual(after.source_reputations[0].low_count, 0)
        self.assertEqual(after.source_reputations[0].high_count, 1)


class ReputationServiceTests(ReputationLedgerFixture):
    def test_one_origin_can_be_requested(self) -> None:
        run_id = self.new_run()
        self.graded(run_id, "https://wanted.test/a", ResearchInformationTrust.HIGH)
        self.graded(run_id, "https://other.test/a", ResearchInformationTrust.HIGH)

        response = self.service().process_report(
            self.request(source_origin="wanted.test")
        )

        self.assertEqual(len(response.source_reputations), 1)
        self.assertEqual(response.source_reputations[0].origin, "wanted.test")

    def test_a_www_prefix_is_normalised_on_lookup(self) -> None:
        run_id = self.new_run()
        self.graded(run_id, "https://www.wanted.test/a", ResearchInformationTrust.HIGH)

        response = self.service().process_report(
            self.request(source_origin="www.wanted.test")
        )

        self.assertEqual(len(response.source_reputations), 1)

    def test_an_unseen_origin_reports_nothing_rather_than_guessing(self) -> None:
        response = self.service().process_report(
            self.request(source_origin="never-seen.test")
        )

        self.assertEqual(response.source_reputations, ())
        self.assertIn("nothing to report", response.message)

    def test_a_blank_origin_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.service().process_report(self.request(source_origin="  "))


class ReputationEventTests(ReputationLedgerFixture):
    def test_reporting_emits_one_bounded_event(self) -> None:
        run_id = self.new_run()
        self.graded(run_id, "https://good.test/a", ResearchInformationTrust.HIGH)

        self.service().process_report(self.request())

        events = [event for event in self.events if event.name == REPUTATION_REPORTED]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["origin_count"], 1)
        self.assertEqual(events[0].payload["sources_gated"], 0)

    def test_no_event_names_an_origin(self) -> None:
        run_id = self.new_run()
        self.graded(run_id, "https://secret-host.test/a", ResearchInformationTrust.LOW)

        self.service().process_report(self.request())

        payloads = json.dumps(
            [
                event.payload
                for event in self.events
                if event.name.startswith("source_reputation")
            ]
        )
        self.assertTrue(payloads)
        self.assertNotIn("secret-host", payloads)
        self.assertNotIn(QUESTION, payloads)


class ReputationCompositionTests(ReputationLedgerFixture):
    def test_the_engine_routes_reputation_over_the_run_manager(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()
        self.graded(run_id, "https://good.test/a", ResearchInformationTrust.HIGH)

        response = engine.process(self.request())

        service = engine._source_reputation_service
        self.assertIsInstance(service, SourceReputationApplicationService)
        assert service is not None
        self.assertIs(service._run_manager, self.manager)
        self.assertEqual(len(response.source_reputations), 1)

    def test_reputation_is_refused_without_run_persistence(self) -> None:
        engine = self.build_engine(with_runs=False)

        response = engine.process(self.request())

        self.assertIsNone(engine._source_reputation_service)
        self.assertFalse(response.success)
        self.assertIn("unavailable", response.message)

    def test_a_blank_origin_is_refused_without_raising(self) -> None:
        engine = self.build_engine()

        response = engine.process(self.request(source_origin="  "))

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
