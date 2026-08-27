"""A hypothesis must name its own defeater, and can never be confirmed.

Two invariants are enforced here. The first is that a conjecture without a
discriminating test is refused: something that names nothing capable of counting
against it is a belief with better manners, and it will survive any amount of
evidence because nothing was ever allowed to threaten it.

The second is that no vocabulary exists for settling one. There is no confirm
intent and no status meaning true — SUPPORTED goes as far as this system goes,
and it requires corroboration plus active authored source trust of at least
medium on every supporting source. That is still where most abandoned theories
stood right up until the observation that undid them.

Supporting and opposing evidence are never netted. Three-for and two-against is
a situation someone has to read; any single number describing it has thrown away
the part that mattered.

Time and identifiers are injected, and no test touches a network.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.CognitiveEngine import CognitiveEngine
from cognition.HypothesisApplicationService import HypothesisApplicationService
from cognition.HypothesisEvents import (
    HYPOTHESIS_EVIDENCE_ENTERED,
    HYPOTHESIS_PROPOSED,
    HYPOTHESIS_WITHDRAWN,
)
from cognition.ResearchSourceAcceptanceService import ResearchSourceAcceptanceService
from core.Bootstrap import Bootstrap
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from knowledge.KnowledgeEngine import KnowledgeEngine
from memory.MemoryManager import MemoryManager
from planner.Planner import Planner
from research.HypothesisAppraisal import HypothesisAppraisal
from research.HypothesisStatus import HypothesisStatus
from research.JsonFileHypothesisStore import (
    MAX_HYPOTHESIS_STORE_ENTRIES,
    JsonFileHypothesisStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchHypothesisAppraiser import ResearchHypothesisAppraiser
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import (
    MAX_LISTED_HYPOTHESIS_STATEMENT_LENGTH,
    ResponseComposer,
)
from session.SessionManager import SessionManager
from session.SessionRenameTransactionService import SessionRenameTransactionService

QUESTION = "Does the ring system have a measured age?"
START = datetime(2026, 8, 23, tzinfo=UTC)
FETCHED = datetime(2026, 8, 1, tzinfo=UTC)
STATEMENT = "The rings formed within the last hundred million years."
TEST = "A dated ring particle older than one billion years would counter this."


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


class HypothesisFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.run_path = self.root / "runs.json"
        self.hypothesis_path = self.root / "hypotheses.json"
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
        self.identifiers = count(1)
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.appraiser = ResearchHypothesisAppraiser()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def service(self, persist: bool = True) -> HypothesisApplicationService:
        return HypothesisApplicationService(
            self.manager,
            ResponseComposer(),
            hypothesis_store=(
                JsonFileHypothesisStore(self.hypothesis_path) if persist else None
            ),
            event_bus=self.event_bus,
            clock=self.clock,
            id_factory=lambda: f"hypothesis-{next(self.identifiers)}",
        )

    def new_run(self) -> str:
        return self.manager.create(QUESTION).run_id

    def evidence(self, run_id: str, slug: str) -> str:
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
        chunk = next(
            candidate
            for candidate in self.knowledge_engine.chunks()
            if candidate.document_id == result.document_id and candidate.index == 0
        )
        updated = self.manager.add_evidence(run_id, chunk, "Directly relevant.")
        return updated.evidence[-1].evidence_id

    def assess(
        self,
        run_id: str,
        evidence_id: str,
        trust: ResearchInformationTrust,
        *,
        supersedes_assessment_id: str | None = None,
    ) -> str:
        run = self.manager.get(run_id)
        record = next(
            entry for entry in run.evidence if entry.evidence_id == evidence_id
        )
        updated = self.manager.record_source_assessment(
            run_id,
            record.source_document_id,
            [evidence_id],
            "Assessed for the hypothesis test.",
            supersedes_assessment_id=supersedes_assessment_id,
            information_trust=trust,
        )
        return updated.assessments[-1].assessment_id

    def request(self, intent: str, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="Hypothesis",
            metadata={"intent": intent, **metadata},
        )

    def propose(
        self,
        service: HypothesisApplicationService,
        run_id: str,
        test: str = TEST,
    ) -> str:
        response = service.process_propose(
            self.request(
                "research_hypothesis_propose",
                research_run_id=run_id,
                hypothesis_statement=STATEMENT,
                hypothesis_discriminating_test=test,
            )
        )
        assert response.hypothesis_appraisal is not None
        return response.hypothesis_appraisal.hypothesis.hypothesis_id

    def enter(
        self,
        service: HypothesisApplicationService,
        hypothesis_id: str,
        evidence_ids: list[str],
        supporting: bool,
    ) -> HypothesisStatus:
        intent = (
            "research_hypothesis_support"
            if supporting
            else "research_hypothesis_oppose"
        )
        response = (service.process_support if supporting else service.process_oppose)(
            self.request(
                intent,
                hypothesis_id=hypothesis_id,
                evidence_ids=evidence_ids,
            )
        )
        assert response.hypothesis_appraisal is not None
        return response.hypothesis_appraisal.status

    def named(self, name: str) -> list[Event]:
        return [event for event in self.events if event.name == name]


class DiscriminatingTestTests(unittest.TestCase):
    @staticmethod
    def hypothesis(**overrides: object) -> ResearchHypothesis:
        fields: dict[str, object] = {
            "hypothesis_id": "hypothesis-1",
            "run_id": "run-1",
            "statement": STATEMENT,
            "discriminating_test": TEST,
            "created_at": START,
            "updated_at": START,
        }
        fields.update(overrides)
        return ResearchHypothesis(**fields)  # type: ignore[arg-type]

    def test_a_hypothesis_without_a_defeater_is_refused(self) -> None:
        for value in ("", "   "):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError) as raised:
                    self.hypothesis(discriminating_test=value)
                self.assertIn("would count against it", str(raised.exception))
                self.assertIn("a belief, not a hypothesis", str(raised.exception))

    def test_a_hypothesis_with_a_defeater_is_accepted(self) -> None:
        self.assertEqual(self.hypothesis().discriminating_test, TEST)

    def test_the_same_evidence_cannot_sit_on_both_sides(self) -> None:
        with self.assertRaises(ResearchError) as raised:
            self.hypothesis(
                supporting_evidence_ids=("evidence-1",),
                opposing_evidence_ids=("evidence-1",),
            )

        self.assertIn("both support and oppose", str(raised.exception))

    def test_repeated_evidence_on_one_side_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.hypothesis(supporting_evidence_ids=("evidence-1", "evidence-1"))

    def test_an_update_before_creation_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.hypothesis(updated_at=START - timedelta(seconds=1))

    def test_a_withdrawn_hypothesis_takes_no_more_evidence(self) -> None:
        withdrawn = self.hypothesis().withdrawn_at(START)

        with self.assertRaises(ResearchError):
            withdrawn.supported_by(("evidence-1",), START)

    def test_withdrawing_twice_is_refused(self) -> None:
        withdrawn = self.hypothesis().withdrawn_at(START)

        with self.assertRaises(ResearchError):
            withdrawn.withdrawn_at(START)

    def test_no_status_means_true(self) -> None:
        for status in HypothesisStatus:
            with self.subTest(status=status):
                self.assertFalse(status.means_true)

    def test_only_withdrawal_settles_a_hypothesis(self) -> None:
        self.assertFalse(HypothesisStatus.SUPPORTED.settled)
        self.assertFalse(HypothesisStatus.OPEN.settled)
        self.assertTrue(HypothesisStatus.WITHDRAWN.settled)

    def test_the_status_vocabulary_offers_no_confirmation(self) -> None:
        values = {status.value for status in HypothesisStatus}

        self.assertNotIn("confirmed", values)
        self.assertNotIn("proven", values)
        self.assertNotIn("true", values)
        self.assertNotIn("false", values)


class AppraisalTests(HypothesisFixture):
    def test_an_appraisal_rejects_trust_without_an_assessed_source(self) -> None:
        hypothesis = ResearchHypothesis(
            hypothesis_id="hypothesis-1",
            run_id="run-1",
            statement=STATEMENT,
            discriminating_test=TEST,
            created_at=START,
            updated_at=START,
        )

        with self.assertRaisesRegex(ResearchError, "requires an assessed source"):
            HypothesisAppraisal(
                hypothesis=hypothesis,
                status=HypothesisStatus.OPEN,
                supporting_source_count=1,
                opposing_source_count=0,
                lowest_supporting_trust=ResearchInformationTrust.HIGH,
            )

    def test_a_new_hypothesis_is_open(self) -> None:
        service = self.service()
        run_id = self.new_run()

        self.propose(service, run_id)

        appraisal = self.appraiser.appraise(
            service.hypotheses()[0],
            self.manager.get(run_id),
        )
        self.assertIs(appraisal.status, HypothesisStatus.OPEN)

    def test_one_supporting_source_is_not_yet_support(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        evidence_id = self.evidence(run_id, "a")

        status = self.enter(service, hypothesis_id, [evidence_id], True)

        self.assertIs(status, HypothesisStatus.OPEN)

    def test_two_medium_trust_supporting_sources_make_it_supported(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        first = self.evidence(run_id, "a")
        second = self.evidence(run_id, "b")
        self.assess(run_id, first, ResearchInformationTrust.MEDIUM)
        self.assess(run_id, second, ResearchInformationTrust.MEDIUM)

        status = self.enter(service, hypothesis_id, [first, second], True)

        self.assertIs(status, HypothesisStatus.SUPPORTED)

    def test_two_unassessed_supporting_sources_stay_open(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        first = self.evidence(run_id, "a")
        second = self.evidence(run_id, "b")

        status = self.enter(service, hypothesis_id, [first, second], True)

        self.assertIs(status, HypothesisStatus.OPEN)

    def test_one_low_trust_supporting_source_keeps_corroboration_open(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        first = self.evidence(run_id, "a")
        second = self.evidence(run_id, "b")
        self.assess(run_id, first, ResearchInformationTrust.MEDIUM)
        self.assess(run_id, second, ResearchInformationTrust.LOW)

        status = self.enter(service, hypothesis_id, [first, second], True)

        self.assertIs(status, HypothesisStatus.OPEN)

    def test_the_newest_active_trust_assessment_controls_support(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        first = self.evidence(run_id, "a")
        second = self.evidence(run_id, "b")
        earlier = self.assess(run_id, first, ResearchInformationTrust.LOW)
        self.assess(
            run_id,
            first,
            ResearchInformationTrust.HIGH,
            supersedes_assessment_id=earlier,
        )
        self.assess(run_id, second, ResearchInformationTrust.MEDIUM)

        status = self.enter(service, hypothesis_id, [first, second], True)

        self.assertIs(status, HypothesisStatus.SUPPORTED)

    def test_multiple_active_assessments_keep_the_least_trusting_label(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        first = self.evidence(run_id, "a")
        second = self.evidence(run_id, "b")
        self.assess(run_id, first, ResearchInformationTrust.LOW)
        self.assess(run_id, first, ResearchInformationTrust.HIGH)
        self.assess(run_id, second, ResearchInformationTrust.MEDIUM)

        status = self.enter(service, hypothesis_id, [first, second], True)

        self.assertIs(status, HypothesisStatus.OPEN)
        appraisal = self.appraiser.appraise(
            service.hypotheses()[0],
            self.manager.get(run_id),
        )
        self.assertIs(
            appraisal.lowest_supporting_trust,
            ResearchInformationTrust.LOW,
        )

    def test_appraisal_reports_authored_trust_coverage(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        first = self.evidence(run_id, "a")
        second = self.evidence(run_id, "b")
        self.assess(run_id, first, ResearchInformationTrust.HIGH)

        response = service.process_support(
            self.request(
                "research_hypothesis_support",
                hypothesis_id=hypothesis_id,
                evidence_ids=[first, second],
            )
        )

        assert response.hypothesis_appraisal is not None
        appraisal = response.hypothesis_appraisal
        self.assertEqual(appraisal.supporting_source_count, 2)
        self.assertEqual(appraisal.supporting_assessed_source_count, 1)
        self.assertIs(
            appraisal.lowest_supporting_trust,
            ResearchInformationTrust.HIGH,
        )
        self.assertIn("Supporting trust: 1/2", response.message)
        self.assertIn("lowest high", response.message)

    def test_any_opposing_evidence_alone_contradicts(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        evidence_id = self.evidence(run_id, "a")

        status = self.enter(service, hypothesis_id, [evidence_id], False)

        self.assertIs(status, HypothesisStatus.CONTRADICTED)

    def test_one_opposing_source_weakens_two_supporting_ones(self) -> None:
        """Disconfirmation is not just another vote to be outnumbered."""
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        first = self.evidence(run_id, "a")
        second = self.evidence(run_id, "b")
        against = self.evidence(run_id, "c")
        self.enter(service, hypothesis_id, [first, second], True)

        status = self.enter(service, hypothesis_id, [against], False)

        self.assertIs(status, HypothesisStatus.WEAKENED)

    def test_the_two_sides_are_counted_separately(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        first = self.evidence(run_id, "a")
        second = self.evidence(run_id, "b")
        against = self.evidence(run_id, "c")
        self.enter(service, hypothesis_id, [first, second], True)
        self.enter(service, hypothesis_id, [against], False)

        appraisal = self.appraiser.appraise(
            service.hypotheses()[0],
            self.manager.get(run_id),
        )

        self.assertEqual(appraisal.supporting_source_count, 2)
        self.assertEqual(appraisal.opposing_source_count, 1)
        self.assertTrue(appraisal.corroborated)

    def test_withdrawal_overrides_any_accumulated_support(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        first = self.evidence(run_id, "a")
        second = self.evidence(run_id, "b")
        self.enter(service, hypothesis_id, [first, second], True)

        response = service.process_withdraw(
            self.request("research_hypothesis_withdraw", hypothesis_id=hypothesis_id)
        )

        assert response.hypothesis_appraisal is not None
        self.assertIs(response.hypothesis_appraisal.status, HypothesisStatus.WITHDRAWN)

    def test_appraisal_requires_a_hypothesis_and_a_run(self) -> None:
        run_id = self.new_run()
        run = self.manager.get(run_id)
        hypothesis = ResearchHypothesis(
            hypothesis_id="hypothesis-1",
            run_id=run_id,
            statement=STATEMENT,
            discriminating_test=TEST,
            created_at=START,
            updated_at=START,
        )

        with self.assertRaises(ResearchError):
            self.appraiser.appraise("hypothesis-1", run)  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            self.appraiser.appraise(hypothesis, "run-1")  # type: ignore[arg-type]


class HypothesisServiceTests(HypothesisFixture):
    def test_there_is_no_confirm_intent(self) -> None:
        """The absence is the design, so it is asserted rather than assumed."""
        service = HypothesisApplicationService

        self.assertFalse(hasattr(service, "process_confirm"))
        self.assertFalse(hasattr(service, "is_confirm_request"))

    def test_a_proposal_without_a_defeater_is_refused(self) -> None:
        service = self.service()
        run_id = self.new_run()

        with self.assertRaises(ResearchError):
            service.process_propose(
                self.request(
                    "research_hypothesis_propose",
                    research_run_id=run_id,
                    hypothesis_statement=STATEMENT,
                    hypothesis_discriminating_test="   ",
                )
            )

        self.assertEqual(service.hypotheses(), ())

    def test_evidence_must_already_be_recorded_in_the_run(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)

        with self.assertRaises(ResearchError) as raised:
            service.process_support(
                self.request(
                    "research_hypothesis_support",
                    hypothesis_id=hypothesis_id,
                    evidence_ids=["evidence-never-recorded"],
                )
            )

        self.assertIn("already be recorded in this run", str(raised.exception))

    def test_evidence_is_required(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)

        for value in ([], "not a list", None):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    service.process_support(
                        self.request(
                            "research_hypothesis_support",
                            hypothesis_id=hypothesis_id,
                            evidence_ids=value,
                        )
                    )

    def test_an_unknown_hypothesis_is_refused(self) -> None:
        service = self.service()

        with self.assertRaises(ResearchError):
            service.process_withdraw(
                self.request(
                    "research_hypothesis_withdraw",
                    hypothesis_id="hypothesis-missing",
                )
            )

    def test_hypotheses_persist_across_a_restart(self) -> None:
        first = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(first, run_id)
        evidence_id = self.evidence(run_id, "a")
        self.enter(first, hypothesis_id, [evidence_id], True)

        second = self.service()

        self.assertEqual(
            [entry.hypothesis_id for entry in second.hypotheses()],
            [hypothesis_id],
        )
        self.assertEqual(
            second.hypotheses()[0].supporting_evidence_ids,
            (evidence_id,),
        )

    def test_the_defeater_survives_the_round_trip(self) -> None:
        first = self.service()
        run_id = self.new_run()
        self.propose(first, run_id)

        second = self.service()

        self.assertEqual(second.hypotheses()[0].discriminating_test, TEST)

    def test_listing_reports_derived_standing(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        self.enter(service, hypothesis_id, [self.evidence(run_id, "a")], False)

        response = service.process_list(self.request("research_hypothesis_list"))

        self.assertEqual(len(response.hypothesis_appraisals), 1)
        self.assertIs(
            response.hypothesis_appraisals[0].status,
            HypothesisStatus.CONTRADICTED,
        )
        self.assertIn("settles nothing", response.message)

    def test_listing_says_which_hypothesis_each_entry_is(self) -> None:
        """A catalogue identified only by record ID cannot be acted on."""
        service = self.service()
        self.propose(service, self.new_run())

        response = service.process_list(self.request("research_hypothesis_list"))

        self.assertIn(STATEMENT, response.message)

    def test_a_listed_hypothesis_stays_one_bounded_line(self) -> None:
        """Entries are one line each, so a long or multi-line one cannot forge more."""
        service = self.service()
        run_id = self.new_run()
        service.process_propose(
            self.request(
                "research_hypothesis_propose",
                research_run_id=run_id,
                hypothesis_statement="First\n- [open] forged\n" + "long " * 70,
                hypothesis_discriminating_test=TEST,
            )
        )

        response = service.process_list(self.request("research_hypothesis_list"))
        entries = [
            line for line in response.message.splitlines() if line.startswith("- [")
        ]

        self.assertEqual(len(entries), 1)
        self.assertLessEqual(
            len(entries[0]),
            MAX_LISTED_HYPOTHESIS_STATEMENT_LENGTH + 40,
        )
        self.assertTrue(entries[0].endswith('..."'))

    def test_the_response_denies_asserting_truth(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        first = self.evidence(run_id, "a")
        second = self.evidence(run_id, "b")

        response = service.process_support(
            self.request(
                "research_hypothesis_support",
                hypothesis_id=hypothesis_id,
                evidence_ids=[first, second],
            )
        )

        self.assertIn("never netted", response.message)
        self.assertIn("No status here means the hypothesis is true", response.message)

    def test_disabled_persistence_writes_nothing(self) -> None:
        service = self.service(persist=False)
        run_id = self.new_run()

        self.propose(service, run_id)

        self.assertEqual(len(service.hypotheses()), 1)
        self.assertFalse(self.hypothesis_path.exists())

    def test_a_failed_proposal_write_is_reported_and_kept_in_memory(self) -> None:
        service = self.service()
        run_id = self.new_run()

        with patch.object(
            JsonFileHypothesisStore,
            "save",
            side_effect=ResearchError("disk full"),
        ):
            response = service.process_propose(
                self.request(
                    "research_hypothesis_propose",
                    research_run_id=run_id,
                    hypothesis_statement=STATEMENT,
                    hypothesis_discriminating_test=TEST,
                )
            )

        self.assertFalse(response.success)
        self.assertIsNotNone(response.hypothesis_appraisal)
        self.assertIn("not durably saved", response.message)
        self.assertIn("Durable write: failed", response.message)
        self.assertIn("may lose", response.message)
        self.assertEqual(len(service.hypotheses()), 1)
        self.assertEqual(self.service().hypotheses(), ())

    def test_a_failed_evidence_write_reports_the_unpersisted_delta(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        evidence_id = self.evidence(run_id, "a")

        with patch.object(
            JsonFileHypothesisStore,
            "save",
            side_effect=ResearchError("disk full"),
        ):
            response = service.process_support(
                self.request(
                    "research_hypothesis_support",
                    hypothesis_id=hypothesis_id,
                    evidence_ids=[evidence_id],
                )
            )

        self.assertFalse(response.success)
        self.assertEqual(
            service.hypotheses()[0].supporting_evidence_ids,
            (evidence_id,),
        )
        self.assertEqual(self.service().hypotheses()[0].supporting_evidence_ids, ())

    def test_a_failed_withdraw_write_reports_the_unpersisted_delta(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)

        with patch.object(
            JsonFileHypothesisStore,
            "save",
            side_effect=ResearchError("disk full"),
        ):
            response = service.process_withdraw(
                self.request(
                    "research_hypothesis_withdraw",
                    hypothesis_id=hypothesis_id,
                )
            )

        self.assertFalse(response.success)
        self.assertTrue(service.hypotheses()[0].withdrawn)
        self.assertFalse(self.service().hypotheses()[0].withdrawn)

    def test_hypotheses_never_change_the_run(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        evidence_id = self.evidence(run_id, "a")
        before = self.run_path.read_bytes()

        self.enter(service, hypothesis_id, [evidence_id], True)
        self.enter(service, hypothesis_id, [self.evidence(run_id, "b")], False)

        run = self.manager.get(run_id)
        self.assertEqual(run.claims, ())
        self.assertNotEqual(before, b"")

    def test_a_hypothesis_creates_no_claim(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        first = self.evidence(run_id, "a")
        second = self.evidence(run_id, "b")

        self.enter(service, hypothesis_id, [first, second], True)

        self.assertEqual(self.manager.get(run_id).claims, ())


class HypothesisEventTests(HypothesisFixture):
    def test_the_lifecycle_emits_bounded_events(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        self.enter(service, hypothesis_id, [self.evidence(run_id, "a")], True)
        service.process_withdraw(
            self.request("research_hypothesis_withdraw", hypothesis_id=hypothesis_id)
        )

        for name in (
            HYPOTHESIS_PROPOSED,
            HYPOTHESIS_EVIDENCE_ENTERED,
            HYPOTHESIS_WITHDRAWN,
        ):
            self.assertTrue(self.named(name), name)

    def test_every_event_declares_it_asserts_no_truth(self) -> None:
        service = self.service()
        run_id = self.new_run()
        self.propose(service, run_id)

        for event in self.named(HYPOTHESIS_PROPOSED):
            self.assertIs(event.payload["asserts_truth"], False)

    def test_no_event_carries_the_statement_or_its_defeater(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        self.enter(service, hypothesis_id, [self.evidence(run_id, "a")], True)

        payloads = json.dumps(
            [
                event.payload
                for event in self.events
                if event.name.startswith("hypothesis")
            ]
        )

        self.assertTrue(payloads)
        self.assertNotIn("hundred million years", payloads)
        self.assertNotIn("dated ring particle", payloads)
        self.assertNotIn(QUESTION, payloads)
        self.assertNotIn("example.test", payloads)

    def test_the_side_of_entered_evidence_is_recorded(self) -> None:
        service = self.service()
        run_id = self.new_run()
        hypothesis_id = self.propose(service, run_id)
        self.enter(service, hypothesis_id, [self.evidence(run_id, "a")], False)

        events = self.named(HYPOTHESIS_EVIDENCE_ENTERED)

        self.assertEqual(events[-1].payload["side"], "opposing")


class HypothesisStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "hypotheses.json"
        self.store = JsonFileHypothesisStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def hypothesis(index: int = 1) -> ResearchHypothesis:
        return ResearchHypothesis(
            hypothesis_id=f"hypothesis-{index}",
            run_id="run-1",
            statement=STATEMENT,
            discriminating_test=TEST,
            created_at=START,
            updated_at=START,
            supporting_evidence_ids=("evidence-1",),
        )

    def test_an_absent_store_loads_empty(self) -> None:
        self.assertEqual(self.store.load(), [])

    def test_a_saved_hypothesis_round_trips(self) -> None:
        original = self.hypothesis()

        self.store.save([original])

        self.assertEqual(self.store.load(), [original])

    def test_a_stored_hypothesis_stripped_of_its_defeater_is_refused(self) -> None:
        self.store.save([self.hypothesis()])
        document = json.loads(self.path.read_text(encoding="utf-8"))
        document["hypotheses"][0]["discriminating_test"] = ""
        self.path.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_a_malformed_document_is_refused(self) -> None:
        self.path.write_text("{ not json", encoding="utf-8")

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_an_unsupported_schema_version_is_refused(self) -> None:
        self.path.write_text(
            json.dumps({"schema_version": 99, "hypotheses": []}),
            encoding="utf-8",
        )

        with self.assertRaises(ResearchError):
            self.store.load()

    def test_a_status_field_is_not_persisted(self) -> None:
        self.store.save([self.hypothesis()])

        document = json.loads(self.path.read_text(encoding="utf-8"))

        self.assertNotIn("status", document["hypotheses"][0])

    def test_duplicate_identifiers_are_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.store.save([self.hypothesis(), self.hypothesis()])

    def test_too_many_hypotheses_are_refused(self) -> None:
        entries = [
            replace(self.hypothesis(), hypothesis_id=f"hypothesis-{index}")
            for index in range(MAX_HYPOTHESIS_STORE_ENTRIES + 1)
        ]

        with self.assertRaises(ResearchError):
            self.store.save(entries)

    def test_a_failed_write_leaves_the_previous_document_intact(self) -> None:
        self.store.save([self.hypothesis()])
        before = self.path.read_bytes()

        with (
            patch("research.JsonFileHypothesisStore.os.replace") as replace_call,
            self.assertRaises(ResearchError),
        ):
            replace_call.side_effect = OSError("no space")
            self.store.save([self.hypothesis(1), self.hypothesis(2)])

        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])


class HypothesisCompositionTests(HypothesisFixture):
    def test_hypotheses_are_disabled_without_the_flag(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            bootstrap = Bootstrap(
                memory_path=self.root / "memory.json",
                session_path=self.root / "sessions.json",
            )

            self.assertIsNone(bootstrap._hypothesis_store())

    def test_the_flag_enables_a_store_beside_the_run_store(self) -> None:
        with patch.dict(
            os.environ,
            {"HYPATIA_HYPOTHESIS_ENABLED": "true"},
            clear=True,
        ):
            bootstrap = Bootstrap(
                memory_path=self.root / "memory.json",
                session_path=self.root / "sessions.json",
                research_run_path=self.root / "runs.json",
            )

            store = bootstrap._hypothesis_store()

            self.assertIsNotNone(store)
            assert store is not None
            self.assertEqual(
                store._path,
                self.root / "research_hypotheses.json",
            )

    def test_the_engine_routes_hypotheses_over_the_run_manager(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        response = engine.process(
            self.request(
                "research_hypothesis_propose",
                research_run_id=run_id,
                hypothesis_statement=STATEMENT,
                hypothesis_discriminating_test=TEST,
            )
        )

        service = engine._hypothesis_service
        self.assertIsInstance(service, HypothesisApplicationService)
        assert service is not None
        self.assertIs(service._run_manager, self.manager)
        self.assertIsNone(service._hypothesis_store)
        assert response.hypothesis_appraisal is not None
        self.assertIs(response.hypothesis_appraisal.status, HypothesisStatus.OPEN)

    def test_hypotheses_are_refused_without_run_persistence(self) -> None:
        engine = self.build_engine(with_runs=False)

        response = engine.process(self.request("research_hypothesis_list"))

        self.assertIsNone(engine._hypothesis_service)
        self.assertFalse(response.success)
        self.assertIn("unavailable", response.message)

    def test_a_missing_defeater_is_refused_without_raising(self) -> None:
        engine = self.build_engine()
        run_id = self.new_run()

        response = engine.process(
            self.request(
                "research_hypothesis_propose",
                research_run_id=run_id,
                hypothesis_statement=STATEMENT,
                hypothesis_discriminating_test="  ",
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
