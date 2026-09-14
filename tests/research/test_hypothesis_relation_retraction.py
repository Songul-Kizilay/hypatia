"""Taking back something you said, without pretending you never said it.

All three evidence relationships were append-only. An operator who filed
evidence on the wrong side, or named the wrong evidence as answering the
discriminating test, had no way back: deleting the evidence would be wrong,
deleting the hypothesis would be wrong, and quietly dropping the identifier
would leave a record that looks as though the statement had never been made.

So the collections stay as the current projection — an identifier sits in one
exactly while that relation stands — and a retraction record keeps the fact that
it once did. Every consumer already reads the collections, so appraisal,
curiosity, events and failure lessons see current state without knowing this
feature exists.

Retraction says one thing: this statement no longer stands. Not that the
evidence was wrong, not that it belongs on the other side, not that the
hypothesis is settled. Correcting a mistake is two authored events, and the
tests below insist on seeing both.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from cognition.HypothesisApplicationService import (
    HYPOTHESIS_RETRACT_RELATION_INTENT,
    HypothesisApplicationService,
)
from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.HypothesisEvidenceRelation import (
    HypothesisEvidenceRelation,
    relation_of,
)
from research.HypothesisStatus import HypothesisStatus
from research.JsonFileHypothesisStore import JsonFileHypothesisStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchHypothesisAppraiser import ResearchHypothesisAppraiser
from research.ResearchKnowledgeGapDetector import ResearchKnowledgeGapDetector
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer
from tests.SourceVocabulary import module_vocabulary

PAST = datetime.now(UTC) - timedelta(days=1)
STATEMENT = "Authorization middleware can be bypassed before route handling."
TEST = "Observe whether a protected route is reached without authorization."

MODEL_SOURCE = (SRC_DIR / "research" / "ResearchHypothesis.py").read_text(
    encoding="utf-8"
)
RETRACTION_SOURCE = (
    SRC_DIR / "research" / "HypothesisEvidenceRetraction.py"
).read_text(encoding="utf-8")
SERVICE_SOURCE = (SRC_DIR / "cognition" / "HypothesisApplicationService.py").read_text(
    encoding="utf-8"
)

SUPPORTS = HypothesisEvidenceRelation.SUPPORTS
OPPOSES = HypothesisEvidenceRelation.OPPOSES
ADDRESSES = HypothesisEvidenceRelation.ADDRESSES_DISCRIMINATING_TEST


def hypothesis(**overrides: object) -> ResearchHypothesis:
    fields: dict[str, object] = {
        "hypothesis_id": "hypothesis-1",
        "run_id": "run-1",
        "statement": STATEMENT,
        "discriminating_test": TEST,
        "created_at": PAST,
        "updated_at": PAST,
    }
    fields.update(overrides)
    return ResearchHypothesis(**fields)  # type: ignore[arg-type]


def authored(relation: HypothesisEvidenceRelation, *ids: str) -> ResearchHypothesis:
    base = hypothesis()
    if relation is SUPPORTS:
        return base.supported_by(ids, PAST)
    if relation is OPPOSES:
        return base.opposed_by(ids, PAST)
    return base.addresses_test_by(ids, PAST)


class RelationVocabularyTests(unittest.TestCase):
    def test_the_vocabulary_is_exactly_the_three_statements(self) -> None:
        self.assertEqual(
            [relation.value for relation in HypothesisEvidenceRelation],
            ["supports", "opposes", "addresses_discriminating_test"],
        )

    def test_each_relation_names_its_own_current_collection(self) -> None:
        names = {relation.collection_name for relation in HypothesisEvidenceRelation}

        self.assertEqual(len(names), 3)
        for relation in HypothesisEvidenceRelation:
            with self.subTest(relation=relation):
                self.assertTrue(hasattr(hypothesis(), relation.collection_name))

    def test_an_unknown_relation_is_refused(self) -> None:
        for value in ("refutes", "", None, 7, "supports_maybe"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    relation_of(value)


class ModelRetractionTests(unittest.TestCase):
    def test_each_relation_can_be_taken_back(self) -> None:
        for relation in HypothesisEvidenceRelation:
            with self.subTest(relation=relation):
                subject = authored(relation, "evidence-1")

                retracted = subject.retracted("evidence-1", relation, PAST)

                self.assertEqual(retracted.active_evidence_ids(relation), ())
                self.assertTrue(retracted.was_retracted("evidence-1", relation))

    def test_the_history_survives_the_retraction(self) -> None:
        retracted = authored(SUPPORTS, "evidence-1").retracted(
            "evidence-1", SUPPORTS, PAST
        )

        [record] = retracted.retractions
        self.assertEqual(record.evidence_id, "evidence-1")
        self.assertIs(record.relation, SUPPORTS)
        self.assertEqual(record.retracted_at, PAST)

    def test_retracting_one_leaves_the_others_standing(self) -> None:
        subject = authored(SUPPORTS, "evidence-1", "evidence-2")

        retracted = subject.retracted("evidence-1", SUPPORTS, PAST)

        self.assertEqual(retracted.supporting_evidence_ids, ("evidence-2",))

    def test_retracting_never_moves_evidence_to_another_relation(self) -> None:
        """A correction is two authored events, never one hidden flip."""
        for relation in HypothesisEvidenceRelation:
            with self.subTest(relation=relation):
                retracted = authored(relation, "evidence-1").retracted(
                    "evidence-1", relation, PAST
                )

                for other in HypothesisEvidenceRelation:
                    self.assertEqual(retracted.active_evidence_ids(other), ())

    def test_retracting_one_relation_leaves_a_different_one_alone(self) -> None:
        both = (
            hypothesis()
            .supported_by(("evidence-1",), PAST)
            .addresses_test_by(("evidence-1",), PAST)
        )

        retracted = both.retracted("evidence-1", SUPPORTS, PAST)

        self.assertEqual(retracted.supporting_evidence_ids, ())
        self.assertEqual(retracted.discriminating_test_evidence_ids, ("evidence-1",))

    def test_the_original_hypothesis_is_untouched(self) -> None:
        subject = authored(SUPPORTS, "evidence-1")

        subject.retracted("evidence-1", SUPPORTS, PAST)

        self.assertEqual(subject.supporting_evidence_ids, ("evidence-1",))
        self.assertEqual(subject.retractions, ())

    def test_retracting_what_does_not_stand_is_refused(self) -> None:
        subject = authored(SUPPORTS, "evidence-1")

        for evidence_id, relation in (
            ("evidence-missing", SUPPORTS),
            ("evidence-1", OPPOSES),
            ("evidence-1", ADDRESSES),
        ):
            with self.subTest(evidence=evidence_id, relation=relation):
                with self.assertRaises(ResearchError):
                    subject.retracted(evidence_id, relation, PAST)

    def test_retracting_twice_in_a_row_is_refused(self) -> None:
        """Which is what keeps one correction from becoming two records."""
        once = authored(SUPPORTS, "evidence-1").retracted("evidence-1", SUPPORTS, PAST)

        with self.assertRaises(ResearchError):
            once.retracted("evidence-1", SUPPORTS, PAST)

        self.assertEqual(len(once.retractions), 1)

    def test_an_empty_or_unknown_argument_is_refused(self) -> None:
        subject = authored(SUPPORTS, "evidence-1")

        for evidence_id, relation in (("  ", SUPPORTS), ("evidence-1", "supports")):
            with self.subTest(evidence=evidence_id, relation=relation):
                with self.assertRaises(ResearchError):
                    subject.retracted(evidence_id, relation, PAST)  # type: ignore[arg-type]

    def test_a_statement_can_be_authored_again_after_retraction(self) -> None:
        """Three events, and the history shows all three."""
        again = (
            authored(SUPPORTS, "evidence-1")
            .retracted("evidence-1", SUPPORTS, PAST)
            .supported_by(("evidence-1",), PAST)
        )

        self.assertEqual(again.supporting_evidence_ids, ("evidence-1",))
        self.assertEqual(len(again.retractions), 1)
        self.assertTrue(again.was_retracted("evidence-1", SUPPORTS))

    def test_a_second_cycle_records_a_second_retraction(self) -> None:
        twice = (
            authored(SUPPORTS, "evidence-1")
            .retracted("evidence-1", SUPPORTS, PAST)
            .supported_by(("evidence-1",), PAST)
            .retracted("evidence-1", SUPPORTS, PAST)
        )

        self.assertEqual(twice.supporting_evidence_ids, ())
        self.assertEqual(len(twice.retractions), 2)

    def test_the_correction_flow_is_two_visible_events(self) -> None:
        corrected = (
            authored(SUPPORTS, "evidence-1")
            .retracted("evidence-1", SUPPORTS, PAST)
            .opposed_by(("evidence-1",), PAST)
        )

        self.assertEqual(corrected.supporting_evidence_ids, ())
        self.assertEqual(corrected.opposing_evidence_ids, ("evidence-1",))
        self.assertTrue(corrected.was_retracted("evidence-1", SUPPORTS))

    def test_no_module_decides_a_retraction_by_reading_text(self) -> None:
        for name, text in (
            ("model", MODEL_SOURCE),
            ("record", RETRACTION_SOURCE),
            ("service", SERVICE_SOURCE),
        ):
            with self.subTest(module=name):
                vocabulary = module_vocabulary(text)
                for forbidden in (
                    "similarity",
                    "embedding",
                    "overlap",
                    "tokenize",
                    "findall",
                    "fullmatch",
                ):
                    self.assertNotIn(forbidden, vocabulary)


class AppraisalTests(unittest.TestCase):
    """Appraisal reads the current collections, so retraction reaches it free."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        self.run_id = self.manager.create("Can it be bypassed?").run_id
        self.first = self._evidence("chunk-1", "document-1")
        self.second = self._evidence("chunk-2", "document-2")

    def _evidence(self, chunk_id: str, document_id: str) -> str:
        self.manager.add_source(
            self.run_id,
            ResearchSource(
                url=f"https://example.test/{document_id}",
                title="A source",
                content="An observation.",
                content_type="text/plain",
                fetched_at=PAST,
            ),
            document_id,
        )
        run = self.manager.add_evidence(
            self.run_id,
            Chunk(
                document_id=document_id,
                index=0,
                content="An observation recorded during the run.",
                chunk_id=chunk_id,
            ),
            "A note.",
        )
        return run.evidence[-1].evidence_id

    def _appraise(self, subject: ResearchHypothesis):
        return ResearchHypothesisAppraiser().appraise(
            subject, self.manager.get(self.run_id)
        )

    def _hypothesis(self) -> ResearchHypothesis:
        return hypothesis(run_id=self.run_id)

    def test_retracted_opposition_no_longer_counts_against(self) -> None:
        weakened = (
            self._hypothesis()
            .supported_by((self.first,), PAST)
            .opposed_by((self.second,), PAST)
        )
        self.assertIs(self._appraise(weakened).status, HypothesisStatus.WEAKENED)

        corrected = weakened.retracted(self.second, OPPOSES, PAST)

        self.assertEqual(self._appraise(corrected).opposing_source_count, 0)
        self.assertIsNot(self._appraise(corrected).status, HypothesisStatus.WEAKENED)

    def test_retracted_support_no_longer_counts_for(self) -> None:
        supported = self._hypothesis().supported_by((self.first,), PAST)

        corrected = supported.retracted(self.first, SUPPORTS, PAST)

        self.assertEqual(self._appraise(corrected).supporting_source_count, 0)

    def test_the_history_of_a_weakened_hypothesis_stays_visible(self) -> None:
        """Current standing changes; the fact that it was argued does not."""
        corrected = (
            self._hypothesis()
            .supported_by((self.first,), PAST)
            .opposed_by((self.second,), PAST)
            .retracted(self.second, OPPOSES, PAST)
        )

        self.assertTrue(corrected.was_retracted(self.second, OPPOSES))
        self.assertEqual(len(corrected.retractions), 1)

    def test_retracting_a_test_association_does_not_move_the_status(self) -> None:
        """Addressing the test was never a status input, and still is not."""
        subject = self._hypothesis().addresses_test_by((self.first,), PAST)
        before = self._appraise(subject).status

        after = self._appraise(subject.retracted(self.first, ADDRESSES, PAST)).status

        self.assertIs(before, after)


class CuriosityTests(unittest.TestCase):
    def _run(self):
        from research.ResearchRun import ResearchRun
        from research.ResearchRunStatus import ResearchRunStatus

        return ResearchRun(
            run_id="run-1",
            question="Can it be bypassed?",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=PAST,
            updated_at=PAST,
        )

    def _gap_present(self, subject: ResearchHypothesis) -> bool:
        gaps = ResearchKnowledgeGapDetector().detect(self._run(), PAST, (subject,))
        return ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP in {
            gap.kind for gap in gaps
        }

    def test_the_gap_follows_the_current_association_only(self) -> None:
        none = hypothesis()
        one = none.addresses_test_by(("evidence-1",), PAST)
        two = one.addresses_test_by(("evidence-2",), PAST)
        one_retracted = two.retracted("evidence-1", ADDRESSES, PAST)
        both_retracted = one_retracted.retracted("evidence-2", ADDRESSES, PAST)

        self.assertTrue(self._gap_present(none))
        self.assertFalse(self._gap_present(one))
        self.assertFalse(self._gap_present(two))
        self.assertFalse(self._gap_present(one_retracted))
        self.assertTrue(self._gap_present(both_retracted))

    def test_the_gap_counts_current_associations_not_historical_ones(self) -> None:
        """Two retractions in the history do not stand in for an association."""
        emptied = (
            hypothesis()
            .addresses_test_by(("evidence-1",), PAST)
            .retracted("evidence-1", ADDRESSES, PAST)
            .addresses_test_by(("evidence-2",), PAST)
            .retracted("evidence-2", ADDRESSES, PAST)
        )

        self.assertEqual(len(emptied.retractions), 2)
        self.assertTrue(self._gap_present(emptied))

    def test_support_and_opposition_still_cannot_close_the_gap(self) -> None:
        subject = (
            hypothesis()
            .supported_by(("evidence-1",), PAST)
            .opposed_by(("evidence-2",), PAST)
        )

        self.assertTrue(self._gap_present(subject))

    def test_retracting_support_does_not_open_or_close_the_test_gap(self) -> None:
        answered = (
            hypothesis()
            .supported_by(("evidence-1",), PAST)
            .addresses_test_by(("evidence-2",), PAST)
        )

        corrected = answered.retracted("evidence-1", SUPPORTS, PAST)

        self.assertFalse(self._gap_present(corrected))


class ServiceRetractionTests(unittest.TestCase):
    """The one narrow way a retraction happens, and what it leaves alone."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.hypothesis_path = self.root / "hypotheses.json"
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.run_id = self.manager.create("Can it be bypassed?").run_id
        self.other_run_id = self.manager.create("Another question").run_id
        self.evidence_id = self._evidence(self.run_id)
        self.foreign_evidence_id = self._evidence(self.other_run_id)
        self.service = self._service()
        self.hypothesis_id = self._propose()
        self._support()

    def _evidence(self, run_id: str) -> str:
        document_id = f"document-{run_id}"
        self.manager.add_source(
            run_id,
            ResearchSource(
                url=f"https://example.test/{run_id}",
                title="A source",
                content="An observation.",
                content_type="text/plain",
                fetched_at=PAST,
            ),
            document_id,
        )
        run = self.manager.add_evidence(
            run_id,
            Chunk(
                document_id=document_id,
                index=0,
                content="An observation recorded during the run.",
                chunk_id=f"chunk-{run_id}",
            ),
            "A note.",
        )
        return run.evidence[-1].evidence_id

    def _service(self) -> HypothesisApplicationService:
        return HypothesisApplicationService(
            self.manager,
            ResponseComposer(),
            hypothesis_store=JsonFileHypothesisStore(self.hypothesis_path),
            clock=lambda: PAST + timedelta(minutes=5),
        )

    def _propose(self) -> str:
        response = self.service.process_propose(
            BrainRequest(
                message="Propose",
                metadata={
                    "intent": "research_hypothesis_propose",
                    "research_run_id": self.run_id,
                    "hypothesis_statement": STATEMENT,
                    "hypothesis_discriminating_test": TEST,
                },
            )
        )
        return response.hypothesis_appraisal.hypothesis.hypothesis_id

    def _support(self) -> None:
        self.service.process_support(
            BrainRequest(
                message="Support",
                metadata={
                    "intent": "research_hypothesis_support",
                    "hypothesis_id": self.hypothesis_id,
                    "evidence_ids": [self.evidence_id],
                },
            )
        )

    def _retract(self, **metadata: object):
        return self.service.process_retract_relation(
            BrainRequest(
                message="Retract",
                metadata={
                    "intent": HYPOTHESIS_RETRACT_RELATION_INTENT,
                    "hypothesis_id": self.hypothesis_id,
                    "evidence_id": self.evidence_id,
                    "relation": SUPPORTS.value,
                    **metadata,
                },
            )
        )

    def _current(self) -> ResearchHypothesis:
        [found] = [
            entry
            for entry in self.service.hypotheses()
            if entry.hypothesis_id == self.hypothesis_id
        ]
        return found

    def test_the_service_retracts_exactly_that_statement(self) -> None:
        self._retract()

        current = self._current()
        self.assertEqual(current.supporting_evidence_ids, ())
        self.assertTrue(current.was_retracted(self.evidence_id, SUPPORTS))

    def test_another_runs_evidence_cannot_be_retracted_here(self) -> None:
        with self.assertRaises(ResearchError):
            self._retract(evidence_id=self.foreign_evidence_id)

        self.assertEqual(self._current().supporting_evidence_ids, (self.evidence_id,))

    def test_an_unknown_hypothesis_or_relation_is_refused(self) -> None:
        for metadata in (
            {"hypothesis_id": "hypothesis-missing"},
            {"relation": "refutes"},
            {"relation": ""},
            {"evidence_id": "  "},
        ):
            with self.subTest(metadata=metadata):
                with self.assertRaises(ResearchError):
                    self._retract(**metadata)

    def test_a_repeated_retraction_is_refused(self) -> None:
        self._retract()

        with self.assertRaises(ResearchError):
            self._retract()

        self.assertEqual(len(self._current().retractions), 1)

    def test_retraction_leaves_every_other_record_alone(self) -> None:
        before = self.manager.get(self.run_id)

        self._retract()

        after = self.manager.get(self.run_id)
        self.assertEqual(after.evidence, before.evidence)
        self.assertEqual(after.sources, before.sources)
        self.assertEqual(after.claims, before.claims)
        self.assertEqual(after.assessments, before.assessments)
        self.assertEqual(after.failures, before.failures)

    def test_the_retraction_survives_a_restart(self) -> None:
        self._retract()

        reopened = self._service()

        [restored] = [
            entry
            for entry in reopened.hypotheses()
            if entry.hypothesis_id == self.hypothesis_id
        ]
        self.assertEqual(restored.supporting_evidence_ids, ())
        self.assertTrue(restored.was_retracted(self.evidence_id, SUPPORTS))
        self.assertEqual(len(restored.retractions), 1)

    def test_correction_through_the_service_is_two_events(self) -> None:
        self._retract()

        self.service.process_oppose(
            BrainRequest(
                message="Oppose",
                metadata={
                    "intent": "research_hypothesis_oppose",
                    "hypothesis_id": self.hypothesis_id,
                    "evidence_ids": [self.evidence_id],
                },
            )
        )

        current = self._current()
        self.assertEqual(current.supporting_evidence_ids, ())
        self.assertEqual(current.opposing_evidence_ids, (self.evidence_id,))
        self.assertTrue(current.was_retracted(self.evidence_id, SUPPORTS))


class LegacyStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "hypotheses.json"

    def _write(self, version: int, **extra: object) -> None:
        entry: dict[str, object] = {
            "hypothesis_id": "hypothesis-1",
            "run_id": "run-1",
            "statement": STATEMENT,
            "discriminating_test": TEST,
            "supporting_evidence_ids": ["evidence-1"],
            "opposing_evidence_ids": [],
            "withdrawn": False,
            "created_at": PAST.isoformat(),
            "updated_at": PAST.isoformat(),
        }
        entry.update(extra)
        self.path.write_text(
            json.dumps({"schema_version": version, "hypotheses": [entry]}),
            encoding="utf-8",
        )

    def test_legacy_relations_stay_active_with_no_invented_history(self) -> None:
        """Silence about retraction means none happened, not that any did."""
        self._write(1)

        [restored] = JsonFileHypothesisStore(self.path).load()

        self.assertEqual(restored.supporting_evidence_ids, ("evidence-1",))
        self.assertEqual(restored.retractions, ())

    def test_a_version_two_record_is_still_readable(self) -> None:
        self._write(2, discriminating_test_evidence_ids=["evidence-2"])

        [restored] = JsonFileHypothesisStore(self.path).load()

        self.assertEqual(restored.discriminating_test_evidence_ids, ("evidence-2",))
        self.assertEqual(restored.retractions, ())

    def test_a_malformed_retraction_is_refused(self) -> None:
        for retractions in (
            [
                {
                    "evidence_id": "evidence-1",
                    "relation": "refutes",
                    "retracted_at": PAST.isoformat(),
                }
            ],
            [{"evidence_id": "evidence-1", "relation": "supports"}],
            ["not an object"],
            "not a list",
        ):
            with self.subTest(retractions=retractions):
                self._write(
                    3,
                    discriminating_test_evidence_ids=[],
                    retractions=retractions,
                )
                with self.assertRaises(ResearchError):
                    JsonFileHypothesisStore(self.path).load()

    def test_a_round_trip_preserves_the_history(self) -> None:
        store = JsonFileHypothesisStore(self.path)
        subject = authored(SUPPORTS, "evidence-1").retracted(
            "evidence-1", SUPPORTS, PAST
        )

        store.save([subject])
        [restored] = store.load()

        document = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 4)
        self.assertEqual(restored.retractions, subject.retractions)


if __name__ == "__main__":
    unittest.main()
