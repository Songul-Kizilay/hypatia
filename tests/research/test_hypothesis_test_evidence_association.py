"""Saying evidence bears on a hypothesis, and saying it answered the question.

Until now a hypothesis could record that evidence supported or opposed it, and
nothing more. That is a weaker statement than it looks: a framework version
number is perfectly good supporting context for "the middleware can be
bypassed" while saying nothing whatever about whether a protected route was
ever reached without authorization. The hypothesis names that observation in its
discriminating test, and nothing recorded which evidence, if any, made it.

So there is now a third collection, authored and never inferred. No code in this
repository decides that evidence addresses a test by reading either of them —
not by substring, token overlap, similarity, or model — because that decision
is a person's and the wrong answer is invisible once stored.

The association is bookkeeping after an observation. The discriminating test is
prose describing something somebody would have to see; nothing here reads it as
an instruction, and recording that it was answered executes nothing at all.
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
    HYPOTHESIS_TEST_EVIDENCE_INTENT,
    HypothesisApplicationService,
)
from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.JsonFileHypothesisStore import JsonFileHypothesisStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchKnowledgeGapDetector import ResearchKnowledgeGapDetector
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer
from tests.SourceVocabulary import working_vocabulary

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
STATEMENT = "Authorization middleware can be bypassed before route handling."
TEST = "Observe whether a protected route is reached without authorization."

MODEL_SOURCE = (SRC_DIR / "research" / "ResearchHypothesis.py").read_text(
    encoding="utf-8"
)
SERVICE_SOURCE = (SRC_DIR / "cognition" / "HypothesisApplicationService.py").read_text(
    encoding="utf-8"
)


def hypothesis(**overrides: object) -> ResearchHypothesis:
    fields: dict[str, object] = {
        "hypothesis_id": "hypothesis-1",
        "run_id": "run-1",
        "statement": STATEMENT,
        "discriminating_test": TEST,
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return ResearchHypothesis(**fields)  # type: ignore[arg-type]


class ModelAssociationTests(unittest.TestCase):
    def test_an_operator_can_state_that_evidence_addresses_the_test(self) -> None:
        updated = hypothesis().addresses_test_by(("evidence-1",), NOW)

        self.assertEqual(updated.discriminating_test_evidence_ids, ("evidence-1",))
        self.assertTrue(updated.has_discriminating_test_evidence)
        self.assertEqual(updated.hypothesis_id, "hypothesis-1")

    def test_the_original_hypothesis_is_left_alone(self) -> None:
        original = hypothesis()

        original.addresses_test_by(("evidence-1",), NOW)

        self.assertEqual(original.discriminating_test_evidence_ids, ())
        self.assertFalse(original.has_discriminating_test_evidence)

    def test_entering_evidence_on_a_side_records_no_association(self) -> None:
        """The whole point: bearing on it is not answering it."""
        supported = hypothesis().supported_by(("evidence-1",), NOW)
        opposed = hypothesis().opposed_by(("evidence-2",), NOW)

        self.assertEqual(supported.discriminating_test_evidence_ids, ())
        self.assertEqual(opposed.discriminating_test_evidence_ids, ())

    def test_an_association_records_no_side(self) -> None:
        """And the reverse: answering it does not say which way it cut."""
        updated = hypothesis().addresses_test_by(("evidence-1",), NOW)

        self.assertEqual(updated.supporting_evidence_ids, ())
        self.assertEqual(updated.opposing_evidence_ids, ())

    def test_evidence_may_address_the_test_and_take_a_side(self) -> None:
        both = (
            hypothesis()
            .supported_by(("evidence-1",), NOW)
            .addresses_test_by(("evidence-1",), NOW)
        )

        self.assertEqual(both.supporting_evidence_ids, ("evidence-1",))
        self.assertEqual(both.discriminating_test_evidence_ids, ("evidence-1",))

    def test_the_same_association_cannot_be_recorded_twice(self) -> None:
        once = hypothesis().addresses_test_by(("evidence-1",), NOW)

        with self.assertRaises(ResearchError):
            once.addresses_test_by(("evidence-1",), NOW)

    def test_an_empty_association_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            hypothesis().addresses_test_by((), NOW)

    def test_a_withdrawn_hypothesis_takes_no_association(self) -> None:
        withdrawn = hypothesis().withdrawn_at(NOW)

        with self.assertRaises(ResearchError):
            withdrawn.addresses_test_by(("evidence-1",), NOW)

    def test_repeated_identifiers_in_one_call_are_refused(self) -> None:
        with self.assertRaises(ResearchError):
            hypothesis(discriminating_test_evidence_ids=("evidence-1", "evidence-1"))

    def test_an_empty_identifier_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            hypothesis(discriminating_test_evidence_ids=("  ",))

    def test_no_module_decides_this_by_reading_text(self) -> None:
        """The invariant the whole design rests on."""
        for name, text in (("model", MODEL_SOURCE), ("service", SERVICE_SOURCE)):
            with self.subTest(module=name):
                vocabulary = working_vocabulary(text)
                for forbidden in (
                    "similarity",
                    "embedding",
                    "overlap",
                    "tokenize",
                    "compile",
                    "findall",
                    "fullmatch",
                ):
                    self.assertNotIn(forbidden, vocabulary)


class ServiceAuthoringTests(unittest.TestCase):
    """The one narrow way an association can come into existence."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.hypothesis_path = self.root / "hypotheses.json"
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.run_id = self.manager.create("Can the middleware be bypassed?").run_id
        self.other_run_id = self.manager.create("An unrelated question").run_id
        self.evidence_id = self._evidence(self.run_id, "chunk-1")
        self.foreign_evidence_id = self._evidence(self.other_run_id, "chunk-2")
        self.service = self._service()
        self.hypothesis_id = self._propose()

    def _evidence(self, run_id: str, chunk_id: str) -> str:
        """Attach a source, then record evidence from it — the canonical chain.

        Evidence only exists downstream of an accepted source, which is the
        provenance this milestone deliberately leaves alone: a hypothesis test
        is associated with evidence, never with a source directly.
        """
        document_id = f"document-{run_id}"
        self.manager.add_source(
            run_id,
            ResearchSource(
                url=f"https://example.test/{run_id}",
                title="An accepted source",
                content="An observation recorded during the run.",
                content_type="text/plain",
                fetched_at=NOW - timedelta(days=1),
            ),
            document_id,
        )
        run = self.manager.add_evidence(
            run_id,
            Chunk(
                document_id=document_id,
                index=0,
                content="An observation recorded during the run.",
                chunk_id=chunk_id,
            ),
            "A note.",
        )
        return run.evidence[-1].evidence_id

    def _service(self) -> HypothesisApplicationService:
        return HypothesisApplicationService(
            self.manager,
            ResponseComposer(),
            hypothesis_store=JsonFileHypothesisStore(self.hypothesis_path),
            clock=lambda: NOW + timedelta(minutes=1),
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

    def _associate(self, **metadata: object):
        return self.service.process_test_evidence(
            BrainRequest(
                message="Associate",
                metadata={
                    "intent": HYPOTHESIS_TEST_EVIDENCE_INTENT,
                    "hypothesis_id": self.hypothesis_id,
                    "evidence_ids": [self.evidence_id],
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

    def test_the_service_records_the_exact_identifiers(self) -> None:
        self._associate()

        current = self._current()
        self.assertEqual(current.discriminating_test_evidence_ids, (self.evidence_id,))
        self.assertEqual(current.run_id, self.run_id)

    def test_another_runs_evidence_is_refused(self) -> None:
        """Cross-run safety, settled by run membership rather than by wording."""
        with self.assertRaises(ResearchError):
            self._associate(evidence_ids=[self.foreign_evidence_id])

        self.assertEqual(self._current().discriminating_test_evidence_ids, ())

    def test_unknown_evidence_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self._associate(evidence_ids=["evidence-missing"])

    def test_an_unknown_hypothesis_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self._associate(hypothesis_id="hypothesis-missing")

    def test_an_empty_request_is_refused(self) -> None:
        for metadata in ({"evidence_ids": []}, {"hypothesis_id": "  "}):
            with self.subTest(metadata=metadata):
                with self.assertRaises(ResearchError):
                    self._associate(**metadata)

    def test_a_duplicate_association_is_refused(self) -> None:
        self._associate()

        with self.assertRaises(ResearchError):
            self._associate()

        self.assertEqual(
            self._current().discriminating_test_evidence_ids, (self.evidence_id,)
        )

    def test_associating_creates_nothing_else_in_the_run(self) -> None:
        before = self.manager.get(self.run_id)

        self._associate()

        after = self.manager.get(self.run_id)
        self.assertEqual(after.sources, before.sources)
        self.assertEqual(after.claims, before.claims)
        self.assertEqual(after.assessments, before.assessments)
        self.assertEqual(after.evidence, before.evidence)
        self.assertEqual(after.failures, before.failures)

    def test_associating_does_not_change_the_evidence_record(self) -> None:
        [before] = [
            record
            for record in self.manager.get(self.run_id).evidence
            if record.evidence_id == self.evidence_id
        ]

        self._associate()

        [after] = [
            record
            for record in self.manager.get(self.run_id).evidence
            if record.evidence_id == self.evidence_id
        ]
        self.assertEqual(after, before)

    def test_the_association_survives_a_restart(self) -> None:
        self._associate()

        reopened = self._service()

        [restored] = [
            entry
            for entry in reopened.hypotheses()
            if entry.hypothesis_id == self.hypothesis_id
        ]
        self.assertEqual(restored.discriminating_test_evidence_ids, (self.evidence_id,))

    def test_the_curiosity_gap_closes_only_after_the_association(self) -> None:
        """The acceptance criterion, end to end through the real service."""
        run = self.manager.get(self.run_id)
        detector = ResearchKnowledgeGapDetector()

        before = detector.detect(run, NOW, self.service.hypotheses())
        self._associate()
        after = detector.detect(run, NOW, self.service.hypotheses())

        self.assertIn(
            ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
            {gap.kind for gap in before},
        )
        self.assertNotIn(
            ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
            {gap.kind for gap in after},
        )

    def test_entering_ordinary_evidence_leaves_the_gap_open(self) -> None:
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

        gaps = ResearchKnowledgeGapDetector().detect(
            self.manager.get(self.run_id), NOW, self.service.hypotheses()
        )

        self.assertIn(
            ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
            {gap.kind for gap in gaps},
        )
        self.assertEqual(self._current().discriminating_test_evidence_ids, ())


class LegacyStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "hypotheses.json"

    def test_a_version_one_record_is_still_readable(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "hypotheses": [
                        {
                            "hypothesis_id": "hypothesis-1",
                            "run_id": "run-1",
                            "statement": STATEMENT,
                            "discriminating_test": TEST,
                            "supporting_evidence_ids": ["evidence-1"],
                            "opposing_evidence_ids": [],
                            "withdrawn": False,
                            "created_at": NOW.isoformat(),
                            "updated_at": NOW.isoformat(),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        [restored] = JsonFileHypothesisStore(self.path).load()

        self.assertEqual(restored.supporting_evidence_ids, ("evidence-1",))
        self.assertEqual(restored.discriminating_test_evidence_ids, ())
        self.assertFalse(restored.has_discriminating_test_evidence)

    def test_saving_writes_the_current_version(self) -> None:
        store = JsonFileHypothesisStore(self.path)

        store.save([hypothesis().addresses_test_by(("evidence-1",), NOW)])

        document = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 3)
        self.assertEqual(
            document["hypotheses"][0]["discriminating_test_evidence_ids"],
            ["evidence-1"],
        )

    def test_an_unsupported_version_is_still_refused(self) -> None:
        self.path.write_text(
            json.dumps({"schema_version": 4, "hypotheses": []}), encoding="utf-8"
        )

        with self.assertRaises(ResearchError):
            JsonFileHypothesisStore(self.path).load()


if __name__ == "__main__":
    unittest.main()
