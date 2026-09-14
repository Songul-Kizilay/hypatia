"""A hypothesis that named its test, and that nobody has answered yet.

The hypothesis engine already records the one thing that would settle each
hypothesis, and curiosity could not see it: hypotheses live in their own store,
so a pure reading of one run never met them. They are now handed to the
detector rather than fetched by it, which keeps detection a function of its
arguments and leaves composing the two aggregates to the layer that knows a
store exists.

What this cannot do is decide that a particular piece of evidence answered a
particular requirement. A hypothesis carries one discriminating test as prose
and two lists of evidence identifiers; nothing canonical links the two. So the
only honest condition is the unambiguous one — the test is named, and no
evidence has been entered on either side — and no test here compares the
wording of a requirement against the wording of evidence, because that
comparison would be a guess wearing the costume of a rule.

Nothing below runs a test, builds a payload, or reaches anything. A curiosity
question asks what would need to be known; making the observation is a person's
decision and a different system's job.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from brain.BrainRequest import BrainRequest
from cognition.CuriosityApplicationService import CuriosityApplicationService
from core.Exceptions import ResearchError
from research.HypothesisStatus import HypothesisStatus
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchCuriosityQuestionGenerator import (
    ResearchCuriosityQuestionGenerator,
)
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchKnowledgeGapDetector import ResearchKnowledgeGapDetector
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from response.ResponseComposer import ResponseComposer
from tests.SourceVocabulary import module_vocabulary

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
RUN_ID = "run-1"
QUESTION = "Can the middleware authorization check be bypassed?"
STATEMENT = "Authorization middleware can be bypassed before route handling."
TEST = "A request reaches a protected route without middleware authorization."

DETECTOR_SOURCE = (SRC_DIR / "research" / "ResearchKnowledgeGapDetector.py").read_text(
    encoding="utf-8"
)
GENERATOR_SOURCE = (
    SRC_DIR / "research" / "ResearchCuriosityQuestionGenerator.py"
).read_text(encoding="utf-8")


def hypothesis(**overrides: object) -> ResearchHypothesis:
    fields: dict[str, object] = {
        "hypothesis_id": "hypothesis-1",
        "run_id": RUN_ID,
        "statement": STATEMENT,
        "discriminating_test": TEST,
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return ResearchHypothesis(**fields)  # type: ignore[arg-type]


def run(run_id: str = RUN_ID) -> ResearchRun:
    return ResearchRun(
        run_id=run_id,
        question=QUESTION,
        status=ResearchRunStatus.COLLECTING,
        sources=(),
        failures=(),
        created_at=NOW,
        updated_at=NOW,
    )


def hypothesis_gaps(*hypotheses: ResearchHypothesis, research_run=None):
    return [
        gap
        for gap in ResearchKnowledgeGapDetector().detect(
            research_run or run(), NOW, hypotheses
        )
        if gap.kind is ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP
    ]


class BlockedHypothesisDetectionTests(unittest.TestCase):
    def test_an_unanswered_hypothesis_becomes_a_gap(self) -> None:
        [gap] = hypothesis_gaps(hypothesis())

        self.assertEqual(gap.subject_id, "hypothesis-1")
        self.assertEqual(gap.run_id, RUN_ID)
        self.assertIn("no evidence has been recorded", gap.summary)

    def test_ordinary_evidence_on_either_side_leaves_the_gap_open(self) -> None:
        """Bearing on a hypothesis is not the same as answering its question.

        This is the distinction the association exists for. A framework version
        number attached as supporting context tells us nothing about whether a
        protected route can be reached unauthenticated, and until v0.3.230 it
        closed the gap anyway.
        """
        for field in ("supporting_evidence_ids", "opposing_evidence_ids"):
            with self.subTest(side=field):
                [gap] = hypothesis_gaps(hypothesis(**{field: ("evidence-1",)}))
                self.assertEqual(gap.subject_id, "hypothesis-1")

    def test_only_the_authored_association_ends_the_gap(self) -> None:
        answered = hypothesis(discriminating_test_evidence_ids=("evidence-2",))

        self.assertEqual(hypothesis_gaps(answered), [])

    def test_test_evidence_closes_the_gap_whichever_side_it_took(self) -> None:
        """Addressing the test is one statement; which way it cuts is another."""
        for field in ("supporting_evidence_ids", "opposing_evidence_ids"):
            with self.subTest(side=field):
                answered = hypothesis(
                    discriminating_test_evidence_ids=("evidence-2",),
                    **{field: ("evidence-2",)},
                )
                self.assertEqual(hypothesis_gaps(answered), [])

    def test_a_withdrawn_hypothesis_produces_no_gap(self) -> None:
        """Withdrawal is the one status this vocabulary says settles anything."""
        self.assertEqual(hypothesis_gaps(hypothesis(withdrawn=True)), [])
        self.assertTrue(HypothesisStatus.WITHDRAWN.settled)

    def test_every_hypothesis_names_its_test_by_construction(self) -> None:
        """The requirement this gap is about cannot be missing in the first place.

        The model refuses a hypothesis with no discriminating test outright —
        "without one it is a belief, not a hypothesis" — so there is no such
        thing as a hypothesis whose requirement was never stated. The detector
        still checks, because a guard that states the rule locally costs
        nothing, but the invariant lives here.
        """
        with self.assertRaises(ResearchError):
            hypothesis(discriminating_test="")
        with self.assertRaises(ResearchError):
            hypothesis(discriminating_test="   ")

    def test_a_hypothesis_from_another_run_is_never_borrowed(self) -> None:
        self.assertEqual(hypothesis_gaps(hypothesis(run_id="run-2")), [])

    def test_two_hypotheses_produce_two_distinct_gaps(self) -> None:
        found = hypothesis_gaps(hypothesis(), hypothesis(hypothesis_id="hypothesis-2"))

        self.assertEqual(
            [gap.subject_id for gap in found], ["hypothesis-1", "hypothesis-2"]
        )
        self.assertEqual(len({gap.gap_id for gap in found}), 2)

    def test_a_weakened_hypothesis_still_needs_its_test_addressed(self) -> None:
        """Argument on both sides is not proof anyone ran the discriminating test.

        Its provenance is preserved exactly: the two sides keep meaning what
        they meant, and nothing reclassifies them. What is reported is only
        that nobody has yet said which evidence answers the question.
        """
        weakened = hypothesis(
            supporting_evidence_ids=("evidence-1",),
            opposing_evidence_ids=("evidence-2",),
        )

        [gap] = hypothesis_gaps(weakened)
        self.assertEqual(gap.subject_id, "hypothesis-1")
        self.assertEqual(weakened.supporting_evidence_ids, ("evidence-1",))
        self.assertEqual(weakened.opposing_evidence_ids, ("evidence-2",))
        self.assertTrue(HypothesisStatus.WEAKENED.has_opposing_evidence)

    def test_passing_no_hypotheses_leaves_the_run_gaps_unchanged(self) -> None:
        with_none = ResearchKnowledgeGapDetector().detect(run(), NOW)
        with_empty = ResearchKnowledgeGapDetector().detect(run(), NOW, ())

        self.assertEqual(with_none, with_empty)
        self.assertNotIn(
            ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
            {gap.kind for gap in with_none},
        )


class DeterminismAndProvenanceTests(unittest.TestCase):
    def test_unchanged_state_detects_identically(self) -> None:
        subject = hypothesis()

        first = ResearchKnowledgeGapDetector().detect(run(), NOW, (subject,))
        second = ResearchKnowledgeGapDetector().detect(run(), NOW, (subject,))

        self.assertEqual(first, second)

    def test_the_gap_identity_names_its_hypothesis(self) -> None:
        [first] = hypothesis_gaps(hypothesis())
        [other] = hypothesis_gaps(hypothesis(hypothesis_id="hypothesis-2"))

        self.assertIn("hypothesis-1", first.gap_id)
        self.assertNotEqual(first.gap_id, other.gap_id)

    def test_authoring_the_association_removes_that_hypothesis_gap(self) -> None:
        before = hypothesis()
        after = before.addresses_test_by(("evidence-1",), NOW)

        self.assertEqual(len(hypothesis_gaps(before)), 1)
        self.assertEqual(hypothesis_gaps(after), [])

    def test_a_legacy_hypothesis_reads_as_having_no_test_evidence(self) -> None:
        """Silence is not consent: old evidence is never promoted after upgrade.

        A hypothesis written before the association existed says nothing about
        which evidence addressed its test, and the truthful reading of that is
        that nobody said. Such a hypothesis surfacing the gap after upgrade is
        the correct outcome, not a regression.
        """
        legacy = hypothesis(supporting_evidence_ids=("evidence-1", "evidence-2"))

        self.assertEqual(legacy.discriminating_test_evidence_ids, ())
        self.assertFalse(legacy.has_discriminating_test_evidence)
        self.assertEqual(len(hypothesis_gaps(legacy)), 1)

    def test_detection_changes_neither_the_run_nor_the_hypothesis(self) -> None:
        subject = hypothesis()
        research_run = run()
        run_before = replace(research_run)
        hypothesis_before = replace(subject)

        ResearchKnowledgeGapDetector().detect(research_run, NOW, (subject,))

        self.assertEqual(research_run, run_before)
        self.assertEqual(subject, hypothesis_before)
        self.assertEqual(subject.supporting_evidence_ids, ())
        self.assertFalse(subject.withdrawn)

    def test_it_ranks_below_claim_gaps_and_above_run_breadth_gaps(self) -> None:
        blocked = ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP

        for claim_kind in (
            ResearchKnowledgeGapKind.CONTRADICTED_CLAIM,
            ResearchKnowledgeGapKind.UNRESOLVED_CLAIM,
            ResearchKnowledgeGapKind.SINGLE_SOURCE_CLAIM,
        ):
            with self.subTest(above=claim_kind):
                self.assertLess(blocked.severity, claim_kind.severity)
        for breadth_kind in (
            ResearchKnowledgeGapKind.UNSUPPORTED_QUESTION,
            ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP,
            ResearchKnowledgeGapKind.UNASSESSED_SOURCE,
        ):
            with self.subTest(below=breadth_kind):
                self.assertGreater(blocked.severity, breadth_kind.severity)


class QuestionTests(unittest.TestCase):
    def _question(self, subject: ResearchHypothesis):
        research_run = run()
        gaps = ResearchKnowledgeGapDetector().detect(research_run, NOW, (subject,))
        [question] = [
            question
            for question in ResearchCuriosityQuestionGenerator().generate(
                research_run, gaps, (subject,)
            )
            if question.kind is ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP
        ]
        return question

    def test_the_question_names_the_hypothesis_in_its_own_words(self) -> None:
        question = self._question(hypothesis())

        self.assertEqual(
            question.text,
            "What evidence would settle this hypothesis, which so far has "
            f"none: {STATEMENT}?",
        )
        self.assertEqual(question.subject_id, "hypothesis-1")

    def test_the_question_never_quotes_the_discriminating_test(self) -> None:
        """The test describes an observation; quoting it makes an instruction."""
        question = self._question(hypothesis())

        self.assertNotIn(TEST, question.text)
        self.assertNotIn("request reaches", question.text.casefold())

    def test_the_question_carries_no_executable_language(self) -> None:
        question = self._question(hypothesis())

        for verb in (
            "run ",
            "send",
            "exploit",
            "execute",
            "scan",
            "curl",
            "payload",
            "nmap",
            "try ",
        ):
            with self.subTest(verb=verb):
                self.assertNotIn(verb, question.text.casefold())

    def test_missing_evidence_asserts_nothing_about_the_hypothesis(self) -> None:
        """An unanswered question is not a false one, nor a true one."""
        question = self._question(hypothesis())

        for verdict in ("false", "true", "disproven", "confirmed", "likely"):
            with self.subTest(word=verdict):
                self.assertNotIn(verdict, question.text.casefold())
        self.assertFalse(HypothesisStatus.OPEN.means_true)

    def test_a_question_is_still_produced_without_the_hypothesis_text(self) -> None:
        """Losing the readable subject must not lose the gap."""
        research_run = run()
        subject = hypothesis()
        gaps = ResearchKnowledgeGapDetector().detect(research_run, NOW, (subject,))

        questions = ResearchCuriosityQuestionGenerator().generate(research_run, gaps)

        [question] = [
            question
            for question in questions
            if question.kind is ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP
        ]
        self.assertIn("hypothesis-1", question.text)

    def test_neither_module_can_match_prose_or_reach_anything(self) -> None:
        for name, text in (
            ("detector", DETECTOR_SOURCE),
            ("generator", GENERATOR_SOURCE),
        ):
            with self.subTest(module=name):
                vocabulary = module_vocabulary(text)
                for forbidden in (
                    "search",
                    "match",
                    "similarity",
                    "embed",
                    "fetch",
                    "execute",
                    "retry",
                ):
                    self.assertNotIn(forbidden, vocabulary)

    def test_the_output_cap_still_binds_with_many_hypotheses(self) -> None:
        research_run = run()
        many = tuple(
            hypothesis(hypothesis_id=f"hypothesis-{index}") for index in range(30)
        )
        gaps = ResearchKnowledgeGapDetector().detect(research_run, NOW, many)

        questions = ResearchCuriosityQuestionGenerator(max_questions=5).generate(
            research_run, gaps, many
        )

        self.assertEqual(len(questions), 5)


class RecordingHypothesisStore:
    """A store that answers reads and remembers whether anyone wrote."""

    def __init__(self, hypotheses: list[ResearchHypothesis]) -> None:
        self._hypotheses = hypotheses
        self.loads = 0
        self.saves: list[list[ResearchHypothesis]] = []

    def load(self) -> list[ResearchHypothesis]:
        self.loads += 1
        return list(self._hypotheses)

    def save(self, hypotheses: list[ResearchHypothesis]) -> None:
        self.saves.append(list(hypotheses))


class FailingHypothesisStore:
    def load(self) -> list[ResearchHypothesis]:
        raise ResearchError("Hypothesis store is unreadable.")

    def save(self, hypotheses: list[ResearchHypothesis]) -> None:
        raise ResearchError("Hypothesis store is unreadable.")


class ServiceCompositionTests(unittest.TestCase):
    """The layer that knows a store exists is the one that composes the two."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.manager = ResearchRunManager(JsonFileResearchRunStore(root / "runs.json"))
        self.run_id = self.manager.create(QUESTION).run_id

    def _service(self, store: object | None) -> CuriosityApplicationService:
        return CuriosityApplicationService(
            self.manager,
            ResponseComposer(),
            hypothesis_store=store,  # type: ignore[arg-type]
            clock=lambda: NOW,
        )

    def _request(self, intent: str, **metadata: str) -> BrainRequest:
        return BrainRequest(
            message="Curiosity",
            metadata={"intent": intent, "research_run_id": self.run_id, **metadata},
        )

    def _preview(self, service: CuriosityApplicationService):
        return service.process_question_preview(
            self._request("curiosity_question_preview")
        )

    def test_the_service_reaches_this_runs_hypotheses(self) -> None:
        store = RecordingHypothesisStore([hypothesis(run_id=self.run_id)])

        response = self._preview(self._service(store))

        preview = response.research_curiosity
        self.assertEqual(store.loads, 1)
        self.assertIn(
            ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
            {gap.kind for gap in preview.gaps},
        )

    def test_another_runs_hypothesis_is_not_borrowed(self) -> None:
        store = RecordingHypothesisStore([hypothesis(run_id="some-other-run")])

        preview = self._preview(self._service(store)).research_curiosity

        self.assertNotIn(
            ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
            {gap.kind for gap in preview.gaps},
        )

    def test_curiosity_still_works_with_no_hypothesis_store(self) -> None:
        preview = self._preview(self._service(None)).research_curiosity

        self.assertTrue(preview.gaps)
        self.assertNotIn(
            ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
            {gap.kind for gap in preview.gaps},
        )

    def test_an_unreadable_store_does_not_fail_the_read_only_report(self) -> None:
        """What the run itself exposes is still true, and still reported."""
        preview = self._preview(
            self._service(FailingHypothesisStore())
        ).research_curiosity

        self.assertTrue(preview.gaps)
        self.assertNotIn(
            ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
            {gap.kind for gap in preview.gaps},
        )

    def test_previewing_never_writes_a_hypothesis(self) -> None:
        store = RecordingHypothesisStore([hypothesis(run_id=self.run_id)])
        service = self._service(store)

        self._preview(service)
        self._preview(service)

        self.assertEqual(store.saves, [])

    def test_accepting_a_question_decides_nothing_about_the_hypothesis(self) -> None:
        """Accepting means the question is worth asking, and nothing else."""
        subject = hypothesis(run_id=self.run_id)
        store = RecordingHypothesisStore([subject])
        service = self._service(store)
        preview = self._preview(service).research_curiosity
        [question] = [
            question
            for question in preview.questions
            if question.kind is ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP
        ]
        service.process_question_store(self._request("curiosity_question_store"))

        service.process_question_accept(
            self._request(
                "curiosity_question_accept", curiosity_question_id=question.question_id
            )
        )

        self.assertEqual(store.saves, [])
        self.assertEqual(subject.supporting_evidence_ids, ())
        self.assertEqual(subject.opposing_evidence_ids, ())
        self.assertFalse(subject.withdrawn)
        run_now = self.manager.get(self.run_id)
        self.assertEqual((run_now.evidence, run_now.claims), ((), ()))


if __name__ == "__main__":
    unittest.main()
