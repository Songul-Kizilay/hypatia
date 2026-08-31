"""When somebody said it, recorded where it is known and absent where it is not.

Three milestones in a row had to work around the same gap: Hypatia knew when a
relationship was withdrawn and never when it was authored. It does now, for
relationships authored from here on.

What it does not do is invent the missing half. A relation carried forward from
an older file has no recorded time, and there is no number anywhere that would
truthfully stand in for one — the hypothesis's update time moves with every
later change, a retraction's time is when a statement ended, and a load time is
when a file was read. So absence is represented as absence, and most of what
follows is about keeping it that way through authoring, retraction, persistence
and restart.

The other half of the milestone is what must NOT happen. A timestamp is
provenance and nothing else: it does not make evidence stronger, does not rank
one relation above another, does not resolve a contradiction, and does not close
a research gap. Those are asserted here as equivalences — the same hypothesis
with and without recorded times must appraise identically and produce identical
curiosity.
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
from cognition.HypothesisApplicationService import HypothesisApplicationService
from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.HypothesisEvidenceAssertion import HypothesisEvidenceAssertion
from research.HypothesisEvidenceRelation import HypothesisEvidenceRelation
from research.HypothesisStatus import HypothesisStatus
from research.JsonFileHypothesisStore import JsonFileHypothesisStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchHypothesisAppraiser import ResearchHypothesisAppraiser
from research.ResearchKnowledgeGapDetector import ResearchKnowledgeGapDetector
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer
from tests.SourceVocabulary import module_vocabulary

PAST = datetime.now(UTC) - timedelta(days=2)
T1 = PAST + timedelta(hours=1)
T2 = PAST + timedelta(hours=2)
T3 = PAST + timedelta(hours=3)
STATEMENT = "Authorization middleware can be bypassed before route handling."
TEST = "Observe whether a protected route is reached without authorization."

MODEL_SOURCE = (SRC_DIR / "research" / "ResearchHypothesis.py").read_text(
    encoding="utf-8"
)
ASSERTION_SOURCE = (SRC_DIR / "research" / "HypothesisEvidenceAssertion.py").read_text(
    encoding="utf-8"
)
APPRAISER_SOURCE = (SRC_DIR / "research" / "ResearchHypothesisAppraiser.py").read_text(
    encoding="utf-8"
)
DETECTOR_SOURCE = (SRC_DIR / "research" / "ResearchKnowledgeGapDetector.py").read_text(
    encoding="utf-8"
)
LESSON_SOURCE = (SRC_DIR / "research" / "HypothesisFailureLessonDeriver.py").read_text(
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


def authored(relation: HypothesisEvidenceRelation, moment: datetime, *ids: str):
    base = hypothesis()
    return {
        SUPPORTS: base.supported_by,
        OPPOSES: base.opposed_by,
        ADDRESSES: base.addresses_test_by,
    }[relation](ids, moment)


class AuthoringTimeTests(unittest.TestCase):
    def test_every_relation_records_the_exact_authoring_moment(self) -> None:
        for relation in HypothesisEvidenceRelation:
            with self.subTest(relation=relation):
                subject = authored(relation, T1, "evidence-1")

                self.assertEqual(subject.authored_at("evidence-1", relation), T1)

    def test_each_relation_is_timed_independently(self) -> None:
        subject = (
            hypothesis()
            .supported_by(("evidence-1",), T1)
            .addresses_test_by(("evidence-1",), T2)
        )

        self.assertEqual(subject.authored_at("evidence-1", SUPPORTS), T1)
        self.assertEqual(subject.authored_at("evidence-1", ADDRESSES), T2)
        self.assertIsNone(subject.authored_at("evidence-1", OPPOSES))

    def test_several_identifiers_authored_together_share_that_moment(self) -> None:
        subject = hypothesis().supported_by(("evidence-1", "evidence-2"), T1)

        for identifier in ("evidence-1", "evidence-2"):
            with self.subTest(evidence=identifier):
                self.assertEqual(subject.authored_at(identifier, SUPPORTS), T1)

    def test_resending_an_existing_identifier_does_not_restamp_it(self) -> None:
        """Re-sending authored nothing, so it moved nothing."""
        subject = hypothesis().supported_by(("evidence-1",), T1)

        again = subject.supported_by(("evidence-1", "evidence-2"), T2)

        self.assertEqual(again.authored_at("evidence-1", SUPPORTS), T1)
        self.assertEqual(again.authored_at("evidence-2", SUPPORTS), T2)

    def test_an_unrecorded_relation_reads_as_unknown(self) -> None:
        """A bare collection is exactly what an older store file restores to."""
        legacy = hypothesis(supporting_evidence_ids=("evidence-1",))

        self.assertIsNone(legacy.authored_at("evidence-1", SUPPORTS))
        self.assertEqual(legacy.assertions, ())
        self.assertEqual(legacy.supporting_evidence_ids, ("evidence-1",))

    def test_a_time_cannot_be_recorded_for_a_relation_that_does_not_stand(
        self,
    ) -> None:
        with self.assertRaises(ResearchError):
            hypothesis(
                assertions=(HypothesisEvidenceAssertion("evidence-1", SUPPORTS, T1),)
            )

    def test_one_relation_cannot_carry_two_times(self) -> None:
        with self.assertRaises(ResearchError):
            hypothesis(
                supporting_evidence_ids=("evidence-1",),
                assertions=(
                    HypothesisEvidenceAssertion("evidence-1", SUPPORTS, T1),
                    HypothesisEvidenceAssertion("evidence-1", SUPPORTS, T2),
                ),
            )

    def test_a_malformed_assertion_is_refused(self) -> None:
        for evidence_id, relation, moment in (
            ("  ", SUPPORTS, T1),
            ("evidence-1", "supports", T1),
            ("evidence-1", SUPPORTS, PAST.replace(tzinfo=None)),
            ("evidence-1", SUPPORTS, datetime.now(UTC) + timedelta(days=1)),
        ):
            with self.subTest(evidence=evidence_id, moment=moment):
                with self.assertRaises(ResearchError):
                    HypothesisEvidenceAssertion(evidence_id, relation, moment)  # type: ignore[arg-type]


class RetractionAndCycleTests(unittest.TestCase):
    def test_retraction_takes_the_time_with_the_statement(self) -> None:
        subject = authored(SUPPORTS, T1, "evidence-1")

        retracted = subject.retracted("evidence-1", SUPPORTS, T2)

        self.assertIsNone(retracted.authored_at("evidence-1", SUPPORTS))
        self.assertEqual(retracted.assertions, ())
        self.assertEqual(retracted.retractions[0].retracted_at, T2)

    def test_retracting_one_relation_leaves_the_others_time_alone(self) -> None:
        subject = (
            hypothesis()
            .supported_by(("evidence-1",), T1)
            .addresses_test_by(("evidence-1",), T2)
        )

        retracted = subject.retracted("evidence-1", SUPPORTS, T3)

        self.assertIsNone(retracted.authored_at("evidence-1", SUPPORTS))
        self.assertEqual(retracted.authored_at("evidence-1", ADDRESSES), T2)

    def test_a_full_cycle_records_all_three_moments(self) -> None:
        """Authored at T1, withdrawn at T2, authored again at T3."""
        cycle = (
            hypothesis()
            .supported_by(("evidence-1",), T1)
            .retracted("evidence-1", SUPPORTS, T2)
            .supported_by(("evidence-1",), T3)
        )

        self.assertEqual(cycle.authored_at("evidence-1", SUPPORTS), T3)
        self.assertEqual(cycle.retractions[0].retracted_at, T2)
        self.assertEqual(cycle.supporting_evidence_ids, ("evidence-1",))

    def test_a_duplicate_current_relation_is_still_refused(self) -> None:
        once = authored(ADDRESSES, T1, "evidence-1")

        with self.assertRaises(ResearchError):
            once.addresses_test_by(("evidence-1",), T2)

        self.assertEqual(once.authored_at("evidence-1", ADDRESSES), T1)


class ProvenanceOnlyTests(unittest.TestCase):
    """A timestamp changes what is known about a record, never what it means."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        self.run_id = self.manager.create("Can it be bypassed?").run_id
        self.first = self._evidence("document-1", "chunk-1")
        self.second = self._evidence("document-2", "chunk-2")

    def _evidence(self, document_id: str, chunk_id: str) -> str:
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

    def _timed(self) -> ResearchHypothesis:
        return (
            hypothesis(run_id=self.run_id)
            .supported_by((self.first,), T1)
            .opposed_by((self.second,), T2)
        )

    def _untimed(self) -> ResearchHypothesis:
        return hypothesis(
            run_id=self.run_id,
            supporting_evidence_ids=(self.first,),
            opposing_evidence_ids=(self.second,),
        )

    def test_appraisal_is_identical_with_and_without_recorded_times(self) -> None:
        run = self.manager.get(self.run_id)
        appraiser = ResearchHypothesisAppraiser()

        timed = appraiser.appraise(self._timed(), run)
        untimed = appraiser.appraise(self._untimed(), run)

        self.assertIs(timed.status, untimed.status)
        self.assertIs(timed.status, HypothesisStatus.WEAKENED)
        self.assertEqual(
            (timed.supporting_source_count, timed.opposing_source_count),
            (untimed.supporting_source_count, untimed.opposing_source_count),
        )

    def test_recency_does_not_decide_which_side_wins(self) -> None:
        """Newer opposition and newer support appraise the same either way."""
        run = self.manager.get(self.run_id)
        appraiser = ResearchHypothesisAppraiser()

        newer_opposition = (
            hypothesis(run_id=self.run_id)
            .supported_by((self.first,), T1)
            .opposed_by((self.second,), T3)
        )
        newer_support = (
            hypothesis(run_id=self.run_id)
            .opposed_by((self.second,), T1)
            .supported_by((self.first,), T3)
        )

        self.assertIs(
            appraiser.appraise(newer_opposition, run).status,
            appraiser.appraise(newer_support, run).status,
        )

    def test_curiosity_is_identical_with_and_without_recorded_times(self) -> None:
        run = ResearchRun(
            run_id="run-1",
            question="Can it be bypassed?",
            status=ResearchRunStatus.COLLECTING,
            sources=(),
            failures=(),
            created_at=PAST,
            updated_at=PAST,
        )
        detector = ResearchKnowledgeGapDetector()
        timed = hypothesis().addresses_test_by(("evidence-1",), T1)
        untimed = hypothesis(discriminating_test_evidence_ids=("evidence-1",))

        for subject, label in ((timed, "timed"), (untimed, "untimed")):
            with self.subTest(subject=label):
                kinds = {gap.kind for gap in detector.detect(run, PAST, (subject,))}
                self.assertNotIn(
                    ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP, kinds
                )

    def test_no_reasoning_module_reads_an_assertion_time(self) -> None:
        """The structural guarantee that recency cannot leak into judgement."""
        for name, text in (
            ("appraiser", APPRAISER_SOURCE),
            ("detector", DETECTOR_SOURCE),
            ("lessons", LESSON_SOURCE),
        ):
            with self.subTest(module=name):
                vocabulary = module_vocabulary(text)
                for forbidden in ("authored_at", "assertions", "recency", "newest"):
                    self.assertNotIn(forbidden, vocabulary)

    def test_no_module_infers_a_time_from_anything(self) -> None:
        for name, text in (("model", MODEL_SOURCE), ("assertion", ASSERTION_SOURCE)):
            with self.subTest(module=name):
                vocabulary = module_vocabulary(text)
                for forbidden in ("similarity", "embedding", "mtime", "getmtime"):
                    self.assertNotIn(forbidden, vocabulary)

    def test_no_other_recorded_time_is_reused_as_an_authoring_time(self) -> None:
        """Every nearby timestamp that a lazy implementation might have grabbed."""
        updated = PAST + timedelta(hours=9)
        legacy = hypothesis(
            created_at=PAST,
            updated_at=updated,
            supporting_evidence_ids=("evidence-1",),
        )
        retracted = (
            hypothesis(supporting_evidence_ids=("evidence-1",))
            .opposed_by(("evidence-2",), T2)
            .retracted("evidence-2", OPPOSES, T3)
        )

        self.assertIsNone(legacy.authored_at("evidence-1", SUPPORTS))
        self.assertIsNone(retracted.authored_at("evidence-1", SUPPORTS))
        self.assertNotIn(updated, [entry.authored_at for entry in legacy.assertions])
        self.assertEqual(retracted.assertions, ())


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "hypotheses.json"

    def _legacy(self, version: int, **extra: object) -> None:
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

    def test_an_authoring_time_survives_a_round_trip_exactly(self) -> None:
        store = JsonFileHypothesisStore(self.path)
        subject = authored(SUPPORTS, T1, "evidence-1")

        store.save([subject])
        [restored] = store.load()

        self.assertEqual(restored.authored_at("evidence-1", SUPPORTS), T1)
        document = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 4)

    def test_a_full_cycle_survives_a_round_trip(self) -> None:
        store = JsonFileHypothesisStore(self.path)
        cycle = (
            hypothesis()
            .supported_by(("evidence-1",), T1)
            .retracted("evidence-1", SUPPORTS, T2)
            .supported_by(("evidence-1",), T3)
        )

        store.save([cycle])
        [restored] = store.load()

        self.assertEqual(restored.authored_at("evidence-1", SUPPORTS), T3)
        self.assertEqual(restored.retractions[0].retracted_at, T2)

    def test_every_legacy_version_loads_with_unknown_times(self) -> None:
        for version, extra in (
            (1, {}),
            (2, {"discriminating_test_evidence_ids": []}),
            (3, {"discriminating_test_evidence_ids": [], "retractions": []}),
        ):
            with self.subTest(version=version):
                self._legacy(version, **extra)

                [restored] = JsonFileHypothesisStore(self.path).load()

                self.assertEqual(restored.supporting_evidence_ids, ("evidence-1",))
                self.assertIsNone(restored.authored_at("evidence-1", SUPPORTS))
                self.assertEqual(restored.assertions, ())

    def test_reading_a_legacy_file_does_not_rewrite_it(self) -> None:
        self._legacy(1)
        before = self.path.read_text(encoding="utf-8")

        JsonFileHypothesisStore(self.path).load()

        self.assertEqual(self.path.read_text(encoding="utf-8"), before)

    def test_a_malformed_assertion_record_is_refused(self) -> None:
        for assertions in (
            [
                {
                    "evidence_id": "evidence-1",
                    "relation": "refutes",
                    "authored_at": T1.isoformat(),
                }
            ],
            [{"evidence_id": "evidence-1", "relation": "supports"}],
            ["not an object"],
            "not a list",
        ):
            with self.subTest(assertions=assertions):
                self._legacy(
                    4,
                    discriminating_test_evidence_ids=[],
                    retractions=[],
                    assertions=assertions,
                )
                with self.assertRaises(ResearchError):
                    JsonFileHypothesisStore(self.path).load()


class ServiceTimingTests(unittest.TestCase):
    """The application layer supplies the moment; nothing reads a hidden clock."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.path = self.root / "hypotheses.json"
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.run_id = self.manager.create("Can it be bypassed?").run_id
        self.evidence_id = self._evidence()
        self.service = self._service(T1)
        self.hypothesis_id = self._propose()

    def _evidence(self) -> str:
        self.manager.add_source(
            self.run_id,
            ResearchSource(
                url="https://example.test/document",
                title="A source",
                content="An observation.",
                content_type="text/plain",
                fetched_at=PAST,
            ),
            "document-1",
        )
        run = self.manager.add_evidence(
            self.run_id,
            Chunk(
                document_id="document-1",
                index=0,
                content="An observation recorded during the run.",
                chunk_id="chunk-1",
            ),
            "A note.",
        )
        return run.evidence[-1].evidence_id

    def _service(self, moment: datetime) -> HypothesisApplicationService:
        return HypothesisApplicationService(
            self.manager,
            ResponseComposer(),
            hypothesis_store=JsonFileHypothesisStore(self.path),
            clock=lambda: moment,
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

    def _current(self, service: HypothesisApplicationService) -> ResearchHypothesis:
        [found] = [
            entry
            for entry in service.hypotheses()
            if entry.hypothesis_id == self.hypothesis_id
        ]
        return found

    def test_the_injected_clock_supplies_the_authoring_time(self) -> None:
        service = self._service(T2)
        service.process_support(
            BrainRequest(
                message="Support",
                metadata={
                    "intent": "research_hypothesis_support",
                    "hypothesis_id": self.hypothesis_id,
                    "evidence_ids": [self.evidence_id],
                },
            )
        )

        self.assertEqual(
            self._current(service).authored_at(self.evidence_id, SUPPORTS), T2
        )

    def test_the_authoring_time_survives_a_restart(self) -> None:
        service = self._service(T2)
        service.process_support(
            BrainRequest(
                message="Support",
                metadata={
                    "intent": "research_hypothesis_support",
                    "hypothesis_id": self.hypothesis_id,
                    "evidence_ids": [self.evidence_id],
                },
            )
        )

        reopened = self._service(T3)

        self.assertEqual(
            self._current(reopened).authored_at(self.evidence_id, SUPPORTS), T2
        )

    def test_a_retraction_after_restart_still_removes_the_time(self) -> None:
        service = self._service(T2)
        service.process_support(
            BrainRequest(
                message="Support",
                metadata={
                    "intent": "research_hypothesis_support",
                    "hypothesis_id": self.hypothesis_id,
                    "evidence_ids": [self.evidence_id],
                },
            )
        )

        reopened = self._service(T3)
        reopened.process_retract_relation(
            BrainRequest(
                message="Retract",
                metadata={
                    "intent": "research_hypothesis_retract_relation",
                    "hypothesis_id": self.hypothesis_id,
                    "evidence_id": self.evidence_id,
                    "relation": SUPPORTS.value,
                },
            )
        )

        restored = self._current(self._service(T3))
        self.assertIsNone(restored.authored_at(self.evidence_id, SUPPORTS))
        self.assertEqual(restored.retractions[0].retracted_at, T3)


if __name__ == "__main__":
    unittest.main()
