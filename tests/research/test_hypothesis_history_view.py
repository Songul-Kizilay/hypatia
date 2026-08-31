"""Reading what happened to a hypothesis, without inventing any of it.

Retraction gave the model a history; nothing showed it. An operator could see
what currently stands and could not see that a relationship had been corrected
without opening the store file, which is exactly the kind of thing an audit
trail exists to make unnecessary.

So this projects the two halves side by side, and most of what follows guards
the seam between them. A retracted relationship must never read as active. A
relationship retracted and then authored again must read as active, because
showing it as withdrawn on the strength of an older cycle would be a worse
story than showing none at all.

The view is also tested for what it refuses to say. When each relationship was
authored is recorded nowhere, so it is reported as unknown rather than filled in
from the hypothesis's update time, the retraction's own time, or a file's. No
reason for a withdrawal is stored, so none is shown. An audit view that
estimates is worse than one that admits a gap.
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
    HYPOTHESIS_HISTORY_INTENT,
    HypothesisApplicationService,
)
from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.HypothesisEvidenceRelation import HypothesisEvidenceRelation
from research.HypothesisHistoryBuilder import HypothesisHistoryBuilder
from research.HypothesisHistoryView import (
    ASSERTION_TIME_NOTICE,
    MAX_HISTORY_RETRACTIONS,
    HypothesisHistoryView,
)
from research.HypothesisStatus import HypothesisStatus
from research.JsonFileHypothesisStore import JsonFileHypothesisStore
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer
from tests.SourceVocabulary import working_vocabulary

PAST = datetime.now(UTC) - timedelta(days=1)
STATEMENT = "Authorization middleware can be bypassed before route handling."
TEST = "Observe whether a protected route is reached without authorization."

VIEW_SOURCE = (SRC_DIR / "research" / "HypothesisHistoryView.py").read_text(
    encoding="utf-8"
)
BUILDER_SOURCE = (SRC_DIR / "research" / "HypothesisHistoryBuilder.py").read_text(
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


def evidence_record(evidence_id: str, note: str) -> ResearchEvidenceRecord:
    return ResearchEvidenceRecord(
        evidence_id=evidence_id,
        source_document_id="document-1",
        chunk_id=f"chunk-{evidence_id}",
        chunk_index=0,
        excerpt="An observation recorded during the run.",
        excerpt_truncated=False,
        chunk_sha256="a" * 64,
        note=note,
        recorded_at=PAST,
    )


def view_of(subject: ResearchHypothesis, **kwargs: object) -> HypothesisHistoryView:
    return HypothesisHistoryBuilder().build(subject, **kwargs)  # type: ignore[arg-type]


class CurrentStandingTests(unittest.TestCase):
    def test_each_relation_appears_under_its_own_meaning(self) -> None:
        subject = (
            hypothesis()
            .supported_by(("evidence-1",), PAST)
            .opposed_by(("evidence-2",), PAST)
            .addresses_test_by(("evidence-3",), PAST)
        )

        view = view_of(subject)

        self.assertEqual(view.current_evidence_ids(SUPPORTS), ("evidence-1",))
        self.assertEqual(view.current_evidence_ids(OPPOSES), ("evidence-2",))
        self.assertEqual(view.current_evidence_ids(ADDRESSES), ("evidence-3",))

    def test_the_three_meanings_are_never_merged(self) -> None:
        rendered = "\n".join(view_of(hypothesis()).lines()).casefold()

        for relation in HypothesisEvidenceRelation:
            with self.subTest(relation=relation):
                self.assertIn(relation.label.casefold(), rendered)
        self.assertNotIn("linked evidence", rendered)

    def test_identity_survives_the_projection_exactly(self) -> None:
        subject = hypothesis().supported_by(("evidence-1",), PAST)

        view = view_of(subject)

        self.assertEqual(view.hypothesis_id, "hypothesis-1")
        self.assertEqual(view.run_id, "run-1")
        self.assertEqual(view.supporting_evidence_ids, ("evidence-1",))

    def test_a_withdrawn_hypothesis_says_so(self) -> None:
        view = view_of(hypothesis().withdrawn_at(PAST))

        self.assertTrue(view.withdrawn)
        self.assertIn("withdrawn", "\n".join(view.lines()))


class RetractionHistoryTests(unittest.TestCase):
    def test_a_retracted_relation_leaves_current_and_enters_history(self) -> None:
        for relation in HypothesisEvidenceRelation:
            with self.subTest(relation=relation):
                base = hypothesis()
                authored = {
                    SUPPORTS: base.supported_by,
                    OPPOSES: base.opposed_by,
                    ADDRESSES: base.addresses_test_by,
                }[relation](("evidence-1",), PAST)

                view = view_of(authored.retracted("evidence-1", relation, PAST))

                self.assertEqual(view.current_evidence_ids(relation), ())
                self.assertFalse(view.is_current("evidence-1", relation))
                [record] = view.retractions
                self.assertEqual(record.evidence_id, "evidence-1")
                self.assertIs(record.relation, relation)

    def test_the_retraction_time_survives_exactly(self) -> None:
        moment = PAST + timedelta(hours=3)
        subject = hypothesis().supported_by(("evidence-1",), PAST)

        view = view_of(subject.retracted("evidence-1", SUPPORTS, moment))

        self.assertEqual(view.retractions[0].retracted_at, moment)
        self.assertIn(moment.isoformat(), "\n".join(view.lines()))

    def test_a_hypothesis_with_no_corrections_says_none_recorded(self) -> None:
        view = view_of(hypothesis().supported_by(("evidence-1",), PAST))

        self.assertEqual(view.retractions, ())
        self.assertEqual(view.total_retraction_count, 0)
        self.assertIn("- none recorded", view.lines())

    def test_a_reauthored_relation_reads_as_standing_again(self) -> None:
        """The case that would otherwise be told backwards."""
        subject = (
            hypothesis()
            .supported_by(("evidence-1",), PAST)
            .retracted("evidence-1", SUPPORTS, PAST)
            .supported_by(("evidence-1",), PAST)
        )

        view = view_of(subject)

        self.assertEqual(view.current_evidence_ids(SUPPORTS), ("evidence-1",))
        self.assertTrue(view.is_current("evidence-1", SUPPORTS))
        self.assertEqual(len(view.retractions), 1)
        self.assertIn("stands in that relation again", "\n".join(view.lines()))

    def test_retracting_one_relation_leaves_another_standing(self) -> None:
        subject = (
            hypothesis()
            .supported_by(("evidence-1",), PAST)
            .addresses_test_by(("evidence-1",), PAST)
            .retracted("evidence-1", SUPPORTS, PAST)
        )

        view = view_of(subject)

        self.assertEqual(view.current_evidence_ids(SUPPORTS), ())
        self.assertEqual(view.current_evidence_ids(ADDRESSES), ("evidence-1",))
        self.assertFalse(view.is_current("evidence-1", SUPPORTS))
        self.assertTrue(view.is_current("evidence-1", ADDRESSES))

    def test_withdrawals_are_ordered_oldest_first_and_deterministically(self) -> None:
        first = PAST
        second = PAST + timedelta(hours=1)
        subject = (
            hypothesis()
            .supported_by(("evidence-2", "evidence-1"), PAST)
            .retracted("evidence-2", SUPPORTS, second)
            .retracted("evidence-1", SUPPORTS, first)
        )

        view = view_of(subject)

        self.assertEqual(
            [record.evidence_id for record in view.retractions],
            ["evidence-1", "evidence-2"],
        )

    def test_withdrawals_recorded_at_one_instant_still_order_stably(self) -> None:
        subject = (
            hypothesis()
            .supported_by(("evidence-2", "evidence-1"), PAST)
            .retracted("evidence-2", SUPPORTS, PAST)
            .retracted("evidence-1", SUPPORTS, PAST)
        )

        first = view_of(subject).retractions
        second = view_of(subject).retractions

        self.assertEqual(first, second)
        self.assertEqual(
            [record.evidence_id for record in first], ["evidence-1", "evidence-2"]
        )


class BoundednessTests(unittest.TestCase):
    def _many(self, count: int) -> ResearchHypothesis:
        subject = hypothesis()
        for index in range(count):
            identifier = f"evidence-{index:02d}"
            subject = subject.supported_by((identifier,), PAST).retracted(
                identifier, SUPPORTS, PAST + timedelta(minutes=index)
            )
        return subject

    def test_a_long_history_is_capped_and_says_so(self) -> None:
        view = view_of(self._many(MAX_HISTORY_RETRACTIONS + 5))

        self.assertEqual(len(view.retractions), MAX_HISTORY_RETRACTIONS)
        self.assertEqual(view.total_retraction_count, MAX_HISTORY_RETRACTIONS + 5)
        self.assertTrue(view.retractions_truncated)
        self.assertIn(
            f"showing {MAX_HISTORY_RETRACTIONS} of {MAX_HISTORY_RETRACTIONS + 5}",
            "\n".join(view.lines()),
        )

    def test_the_newest_withdrawals_are_the_ones_kept(self) -> None:
        view = HypothesisHistoryBuilder().build(self._many(6), limit=2)

        self.assertEqual(
            [record.evidence_id for record in view.retractions],
            ["evidence-04", "evidence-05"],
        )

    def test_a_short_history_is_not_reported_as_truncated(self) -> None:
        view = view_of(self._many(2))

        self.assertFalse(view.retractions_truncated)
        self.assertNotIn("showing", "\n".join(view.lines()))

    def test_an_out_of_range_limit_is_refused(self) -> None:
        for limit in (0, -1, MAX_HISTORY_RETRACTIONS + 1, True):
            with self.subTest(limit=limit):
                with self.assertRaises(ResearchError):
                    HypothesisHistoryBuilder().build(hypothesis(), limit=limit)


class NoFabricationTests(unittest.TestCase):
    def test_no_assertion_time_is_stated_or_invented(self) -> None:
        """The limitation the previous milestone found, surfaced rather than filled."""
        moment = PAST + timedelta(hours=2)
        subject = hypothesis().supported_by(("evidence-1",), PAST)

        rendered = "\n".join(
            view_of(subject.retracted("evidence-1", SUPPORTS, moment)).lines()
        )

        self.assertIn("is not recorded anywhere", rendered)
        for invented in ("authored at", "asserted at", "added at", "created at"):
            with self.subTest(phrase=invented):
                self.assertNotIn(invented, rendered.casefold())

    def test_the_hypothesis_update_time_is_never_shown_as_an_assertion_time(
        self,
    ) -> None:
        updated = PAST + timedelta(hours=5)
        subject = hypothesis(updated_at=updated).supported_by(("evidence-1",), PAST)

        rendered = "\n".join(view_of(subject).lines())

        self.assertNotIn(updated.isoformat(), rendered)

    def test_no_reason_for_a_withdrawal_is_shown(self) -> None:
        subject = hypothesis().supported_by(("evidence-1",), PAST)

        rendered = "\n".join(
            view_of(subject.retracted("evidence-1", SUPPORTS, PAST)).lines()
        )

        for invented in ("because", "reason:", "mistake", "in error"):
            with self.subTest(phrase=invented):
                self.assertNotIn(invented, rendered.casefold())

    def test_the_view_draws_no_conclusion_about_the_hypothesis(self) -> None:
        """Checked over the reported lines, not over the notice denying them.

        The closing notice says the view claims nothing about truth, so it
        necessarily contains the words a naive search would flag. Searching the
        whole render would match the disclaimer that states the rule.
        """
        lines = view_of(hypothesis()).lines()
        reported = "\n".join(lines[: lines.index(ASSERTION_TIME_NOTICE)]).casefold()

        self.assertIn("not the world", "\n".join(lines).casefold())
        for verdict in ("is true", "is false", "confirmed", "disproven"):
            with self.subTest(word=verdict):
                self.assertNotIn(verdict, reported)

    def test_neither_module_infers_anything_from_text(self) -> None:
        for name, text in (("view", VIEW_SOURCE), ("builder", BUILDER_SOURCE)):
            with self.subTest(module=name):
                vocabulary = working_vocabulary(text)
                for forbidden in (
                    "similarity",
                    "embedding",
                    "overlap",
                    "findall",
                    "fullmatch",
                    "fetch",
                    "execute",
                    "now",
                ):
                    self.assertNotIn(forbidden, vocabulary)


class DerivedStateTests(unittest.TestCase):
    def test_the_current_standing_is_shown_when_supplied(self) -> None:
        view = view_of(hypothesis(), status=HypothesisStatus.WEAKENED)

        self.assertIs(view.status, HypothesisStatus.WEAKENED)
        self.assertIn("Current standing: weakened", view.lines())

    def test_an_underived_standing_says_so_rather_than_guessing(self) -> None:
        view = view_of(hypothesis())

        self.assertIsNone(view.status)
        self.assertIn("Current standing: not derived for this view", view.lines())

    def test_the_current_research_gap_is_reported_both_ways(self) -> None:
        for gap_open, expected in (
            (True, "no evidence recorded against it"),
            (False, "none open"),
        ):
            with self.subTest(gap_open=gap_open):
                view = view_of(hypothesis(), evidence_gap_open=gap_open)

                self.assertIs(view.evidence_gap_open, gap_open)
                self.assertIn(expected, "\n".join(view.lines()))

    def test_an_underived_gap_stays_unknown(self) -> None:
        view = view_of(hypothesis())

        self.assertIsNone(view.evidence_gap_open)
        self.assertIn("Current research gap: not derived for this view", view.lines())

    def test_evidence_is_labelled_by_its_own_note_where_one_exists(self) -> None:
        subject = hypothesis().supported_by(("evidence-1",), PAST)

        view = view_of(
            subject,
            evidence=(evidence_record("evidence-1", "The version string."),),
        )

        self.assertIn("evidence-1 (The version string.)", "\n".join(view.lines()))

    def test_unmentioned_evidence_is_not_pulled_in(self) -> None:
        subject = hypothesis().supported_by(("evidence-1",), PAST)

        view = view_of(
            subject,
            evidence=(
                evidence_record("evidence-1", "Mentioned."),
                evidence_record("evidence-9", "Not mentioned."),
            ),
        )

        self.assertEqual(set(view.evidence_notes), {"evidence-1"})
        self.assertNotIn("evidence-9", "\n".join(view.lines()))

    def test_retracted_evidence_keeps_its_label(self) -> None:
        subject = hypothesis().supported_by(("evidence-1",), PAST)

        view = view_of(
            subject.retracted("evidence-1", SUPPORTS, PAST),
            evidence=(evidence_record("evidence-1", "The version string."),),
        )

        self.assertIn("evidence-1 (The version string.)", "\n".join(view.lines()))

    def test_source_content_is_not_reprinted_beside_a_withdrawal(self) -> None:
        subject = hypothesis().supported_by(("evidence-1",), PAST)

        rendered = "\n".join(
            view_of(
                subject.retracted("evidence-1", SUPPORTS, PAST),
                evidence=(evidence_record("evidence-1", "A note."),),
            ).lines()
        )

        self.assertNotIn("An observation recorded during the run.", rendered)


class ReadOnlyTests(unittest.TestCase):
    def test_building_a_history_changes_nothing_about_the_hypothesis(self) -> None:
        subject = (
            hypothesis()
            .supported_by(("evidence-1",), PAST)
            .retracted("evidence-1", SUPPORTS, PAST)
        )
        before = ResearchHypothesis(
            hypothesis_id=subject.hypothesis_id,
            run_id=subject.run_id,
            statement=subject.statement,
            discriminating_test=subject.discriminating_test,
            created_at=subject.created_at,
            updated_at=subject.updated_at,
            supporting_evidence_ids=subject.supporting_evidence_ids,
            opposing_evidence_ids=subject.opposing_evidence_ids,
            discriminating_test_evidence_ids=(subject.discriminating_test_evidence_ids),
            retractions=subject.retractions,
            withdrawn=subject.withdrawn,
        )

        view_of(subject)
        view_of(subject)

        self.assertEqual(subject, before)

    def test_two_reads_of_unchanged_state_are_identical(self) -> None:
        subject = hypothesis().supported_by(("evidence-1",), PAST)

        self.assertEqual(view_of(subject), view_of(subject))

    def test_a_correction_is_visible_on_the_next_read(self) -> None:
        """Rebuilt each time, so nothing shows a stale snapshot."""
        subject = hypothesis().supported_by(("evidence-1",), PAST)
        before = view_of(subject)

        after = view_of(subject.retracted("evidence-1", SUPPORTS, PAST))

        self.assertEqual(before.current_evidence_ids(SUPPORTS), ("evidence-1",))
        self.assertEqual(after.current_evidence_ids(SUPPORTS), ())


class ServiceHistoryTests(unittest.TestCase):
    """The read boundary, over real stores, deriving what only it can reach."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.hypothesis_path = self.root / "hypotheses.json"
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.run_id = self.manager.create("Can it be bypassed?").run_id
        self.evidence_id = self._evidence()
        self.service = self._service()
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
            "The version string.",
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

    def _act(self, intent: str, **metadata: object) -> None:
        request = BrainRequest(
            message=intent,
            metadata={
                "intent": intent,
                "hypothesis_id": self.hypothesis_id,
                **metadata,
            },
        )
        if intent == "research_hypothesis_retract_relation":
            self.service.process_retract_relation(request)
        elif intent == "research_hypothesis_test_evidence":
            self.service.process_test_evidence(request)
        else:
            self.service.process_support(request)

    def _history(self, service: object | None = None) -> HypothesisHistoryView:
        target = service or self.service
        response = target.process_history(  # type: ignore[attr-defined]
            BrainRequest(
                message="History",
                metadata={
                    "intent": HYPOTHESIS_HISTORY_INTENT,
                    "hypothesis_id": self.hypothesis_id,
                },
            )
        )
        return response.hypothesis_history

    def test_the_service_derives_standing_and_the_current_gap(self) -> None:
        view = self._history()

        self.assertIs(view.status, HypothesisStatus.OPEN)
        self.assertTrue(view.evidence_gap_open)
        self.assertEqual(view.hypothesis_id, self.hypothesis_id)

    def test_the_gap_closes_in_the_view_once_the_test_is_addressed(self) -> None:
        self._act("research_hypothesis_test_evidence", evidence_ids=[self.evidence_id])

        self.assertFalse(self._history().evidence_gap_open)

    def test_a_correction_is_visible_on_the_next_read(self) -> None:
        """No construction-time snapshot: each read asks the store again."""
        self._act("research_hypothesis_support", evidence_ids=[self.evidence_id])
        before = self._history()

        self._act(
            "research_hypothesis_retract_relation",
            evidence_id=self.evidence_id,
            relation=SUPPORTS.value,
        )
        after = self._history()

        self.assertEqual(before.current_evidence_ids(SUPPORTS), (self.evidence_id,))
        self.assertEqual(before.retractions, ())
        self.assertEqual(after.current_evidence_ids(SUPPORTS), ())
        self.assertEqual(len(after.retractions), 1)

    def test_evidence_is_labelled_by_the_operators_own_note(self) -> None:
        self._act("research_hypothesis_support", evidence_ids=[self.evidence_id])

        self.assertEqual(
            self._history().evidence_notes[self.evidence_id], "The version string."
        )

    def test_reading_history_changes_nothing_at_all(self) -> None:
        self._act("research_hypothesis_support", evidence_ids=[self.evidence_id])
        run_before = self.manager.get(self.run_id)
        [hypothesis_before] = self.service.hypotheses()

        self._history()
        self._history()

        run_after = self.manager.get(self.run_id)
        [hypothesis_after] = self.service.hypotheses()
        self.assertEqual(hypothesis_after, hypothesis_before)
        self.assertEqual(run_after.evidence, run_before.evidence)
        self.assertEqual(run_after.sources, run_before.sources)
        self.assertEqual(run_after.claims, run_before.claims)
        self.assertEqual(run_after.assessments, run_before.assessments)
        self.assertEqual(run_after.failures, run_before.failures)

    def test_an_unknown_hypothesis_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.service.process_history(
                BrainRequest(
                    message="History",
                    metadata={
                        "intent": HYPOTHESIS_HISTORY_INTENT,
                        "hypothesis_id": "hypothesis-missing",
                    },
                )
            )

    def test_the_history_survives_a_restart(self) -> None:
        self._act("research_hypothesis_support", evidence_ids=[self.evidence_id])
        self._act(
            "research_hypothesis_retract_relation",
            evidence_id=self.evidence_id,
            relation=SUPPORTS.value,
        )

        reopened = self._service()
        view = self._history(reopened)

        self.assertEqual(view.current_evidence_ids(SUPPORTS), ())
        self.assertEqual(len(view.retractions), 1)
        self.assertEqual(view.retractions[0].evidence_id, self.evidence_id)
        self.assertIs(view.retractions[0].relation, SUPPORTS)

    def test_a_legacy_hypothesis_shows_no_invented_withdrawals(self) -> None:
        """Silence about corrections means none happened."""
        self.hypothesis_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "hypotheses": [
                        {
                            "hypothesis_id": self.hypothesis_id,
                            "run_id": self.run_id,
                            "statement": STATEMENT,
                            "discriminating_test": TEST,
                            "supporting_evidence_ids": [self.evidence_id],
                            "opposing_evidence_ids": [],
                            "withdrawn": False,
                            "created_at": PAST.isoformat(),
                            "updated_at": PAST.isoformat(),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        view = self._history(self._service())

        self.assertEqual(view.current_evidence_ids(SUPPORTS), (self.evidence_id,))
        self.assertEqual(view.retractions, ())
        self.assertEqual(view.total_retraction_count, 0)


if __name__ == "__main__":
    unittest.main()
