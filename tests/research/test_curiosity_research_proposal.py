"""The first bridge from noticing a gap to describing what would close it.

Curiosity could propose a question and an operator could keep it, and there it
stopped. This adds the next step and stops again: an accepted question can be
turned into an ordinary research plan that a person can read. The plan is the
same model an approved plan uses, carries the same content digest, and has
exactly the same amount of permission as it did before it existed, which is
none.

Two operator decisions stay separate, and most of what follows guards the gap
between them. Accepting a question must remain inert — a system that quietly
drafted research on acceptance would have moved the decision without telling
anyone. Preparing a proposal must remain inert in a different way: it describes
provider work without doing any, and produces the digest a later authorization
would name without creating, requesting, or implying that authorization.

The other half is staleness. An accepted question outlives the situation that
produced it, so the gap is re-derived from current state at preview time rather
than trusted from the stored question. Somebody may have recorded the very
evidence the gap was about in between, and drafting research for a gap that has
since closed would propose work nobody needs.
"""

from __future__ import annotations

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
from cognition.CuriosityApplicationService import (
    CURIOSITY_PREPARE_PROPOSAL_INTENT,
    CuriosityApplicationService,
)
from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.CuriosityQuestionStatus import CuriosityQuestionStatus
from research.CuriosityResearchProposal import NOT_AUTHORIZED_NOTICE
from research.HypothesisEvidenceRelation import HypothesisEvidenceRelation
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchPlanDigest import plan_digest
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from research.ResearchSourceCandidate import ResearchSourceCandidate
from response.ResponseComposer import ResponseComposer
from tests.SourceVocabulary import module_vocabulary

PAST = datetime.now(UTC) - timedelta(days=1)
NOW = PAST + timedelta(hours=1)
QUESTION = "Can the middleware authorization check be bypassed?"
STATEMENT = "Authorization middleware can be bypassed before route handling."
TEST = "Observe whether a protected route is reached without authorization."

BUILDER_SOURCE = (SRC_DIR / "research" / "CuriosityProposalBuilder.py").read_text(
    encoding="utf-8"
)
PROPOSAL_SOURCE = (SRC_DIR / "research" / "CuriosityResearchProposal.py").read_text(
    encoding="utf-8"
)

ADDRESSES = HypothesisEvidenceRelation.ADDRESSES_DISCRIMINATING_TEST


class RecordingHypothesisStore:
    def __init__(self, hypotheses: list[ResearchHypothesis]) -> None:
        self.hypotheses = hypotheses
        self.saves = 0

    def load(self) -> list[ResearchHypothesis]:
        return list(self.hypotheses)

    def save(self, hypotheses: list[ResearchHypothesis]) -> None:
        self.saves += 1


class ProposalFixture(unittest.TestCase):
    """A real service over real stores, with no provider or model anywhere."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.run_id = self.manager.create(QUESTION).run_id
        self.evidence_id = self._evidence()
        self.hypothesis = ResearchHypothesis(
            hypothesis_id="hypothesis-1",
            run_id=self.run_id,
            statement=STATEMENT,
            discriminating_test=TEST,
            created_at=PAST,
            updated_at=PAST,
        )
        self.hypothesis_store = RecordingHypothesisStore([self.hypothesis])
        self.service = self._service()

    def _evidence(self) -> str:
        self.manager.add_source(
            self.run_id,
            ResearchSource(
                url="https://example.test/document",
                title="A source",
                content="An observation recorded during the run.",
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

    def _service(self) -> CuriosityApplicationService:
        return CuriosityApplicationService(
            self.manager,
            ResponseComposer(),
            hypothesis_store=self.hypothesis_store,
            draft_service=ResearchPlanDraftService(
                id_factory=lambda: "plan-1", clock=lambda: NOW
            ),
            clock=lambda: NOW,
        )

    def _request(self, intent: str, **metadata: str) -> BrainRequest:
        return BrainRequest(
            message="Curiosity", metadata={"intent": intent, **metadata}
        )

    def _stored_questions(self):
        self.service.process_question_store(
            self._request("curiosity_question_store", research_run_id=self.run_id)
        )
        return self.service.questions()

    def _question_of(self, kind: ResearchKnowledgeGapKind):
        [question] = [
            question for question in self._stored_questions() if question.kind is kind
        ]
        return question

    def _accept(self, question_id: str) -> None:
        self.service.process_question_accept(
            self._request(
                "curiosity_question_accept", curiosity_question_id=question_id
            )
        )

    def _prepare(self, question_id: str):
        return self.service.process_prepare_proposal(
            self._request(
                CURIOSITY_PREPARE_PROPOSAL_INTENT,
                curiosity_question_id=question_id,
            )
        )


class EligibilityTests(ProposalFixture):
    def test_a_proposed_question_cannot_prepare_a_proposal(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)

        response = self._prepare(question.question_id)

        self.assertIsNone(response.curiosity_proposal)
        self.assertIn("proposed", response.message)

    def test_a_dismissed_question_cannot_prepare_a_proposal(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self.service.process_question_dismiss(
            self._request(
                "curiosity_question_dismiss",
                curiosity_question_id=question.question_id,
            )
        )

        response = self._prepare(question.question_id)

        self.assertIsNone(response.curiosity_proposal)
        self.assertIn("dismissed", response.message)

    def test_an_accepted_current_question_prepares_a_proposal(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)

        proposal = self._prepare(question.question_id).curiosity_proposal

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.curiosity_question_id, question.question_id)

    def test_an_unknown_question_is_refused(self) -> None:
        response = self._prepare("question-missing")

        self.assertIsNone(response.curiosity_proposal)

    def test_the_exact_question_asked_for_is_the_one_used(self) -> None:
        """No 'latest accepted' shortcut: two accepted questions stay distinct."""
        questions = [
            question
            for question in self._stored_questions()
            if question.kind
            in (
                ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
                ResearchKnowledgeGapKind.UNASSESSED_SOURCE,
            )
        ]
        self.assertEqual(len(questions), 2)
        for question in questions:
            self._accept(question.question_id)

        for question in questions:
            with self.subTest(kind=question.kind):
                proposal = self._prepare(question.question_id).curiosity_proposal
                self.assertEqual(proposal.curiosity_question_id, question.question_id)
                self.assertIs(proposal.gap_kind, question.kind)


class AcceptanceRemainsInertTests(ProposalFixture):
    def test_accepting_prepares_no_proposal(self) -> None:
        """The decision this milestone must not have quietly merged."""
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)

        response = self.service.process_question_accept(
            self._request(
                "curiosity_question_accept",
                curiosity_question_id=question.question_id,
            )
        )

        self.assertIsNone(response.curiosity_proposal)
        self.assertNotIn("RESEARCH PROPOSAL", response.message)

    def test_accepting_changes_nothing_in_the_run(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        before = self.manager.get(self.run_id)

        self._accept(question.question_id)

        after = self.manager.get(self.run_id)
        self.assertEqual(after.sources, before.sources)
        self.assertEqual(after.discoveries, before.discoveries)
        self.assertEqual(after.evidence, before.evidence)
        self.assertEqual(after.claims, before.claims)
        self.assertEqual(after.failures, before.failures)

    def test_acceptance_alone_is_not_enough_to_get_a_plan(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)

        [stored] = [
            entry
            for entry in self.service.questions()
            if entry.question_id == question.question_id
        ]

        self.assertIs(stored.status, CuriosityQuestionStatus.ACCEPTED)
        self.assertFalse(hasattr(stored, "plan"))


class ProvenanceTests(ProposalFixture):
    def _hypothesis_proposal(self):
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)
        return question, self._prepare(question.question_id).curiosity_proposal

    def test_the_proposal_carries_its_curiosity_and_gap_identity(self) -> None:
        question, proposal = self._hypothesis_proposal()

        self.assertEqual(proposal.curiosity_question_id, question.question_id)
        self.assertEqual(proposal.knowledge_gap_id, question.gap_id)
        self.assertEqual(proposal.run_id, self.run_id)
        self.assertIs(proposal.gap_kind, question.kind)
        self.assertEqual(proposal.question, question.text)

    def test_a_hypothesis_gap_carries_its_hypothesis_and_test(self) -> None:
        _question, proposal = self._hypothesis_proposal()

        self.assertEqual(proposal.hypothesis_id, "hypothesis-1")
        self.assertEqual(proposal.discriminating_test, TEST)

    def test_a_non_hypothesis_gap_names_no_hypothesis(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.UNASSESSED_SOURCE)
        self._accept(question.question_id)

        proposal = self._prepare(question.question_id).curiosity_proposal

        self.assertEqual(proposal.hypothesis_id, "")
        self.assertEqual(proposal.discriminating_test, "")

    def test_the_proposal_claims_nothing_about_the_hypothesis(self) -> None:
        """An evidence gap is a statement about our record, not about the world.

        Checked over the reported lines rather than the whole render: the
        closing notice says a proposal never states what is true, so searching
        everything would match the sentence that states the rule.
        """
        _question, proposal = self._hypothesis_proposal()

        lines = proposal.lines()
        reported = "\n".join(lines[: lines.index(NOT_AUTHORIZED_NOTICE)]).casefold()
        for verdict in (
            "is true",
            "is false",
            "confirmed",
            "vulnerable",
            "exploitable",
            "proven",
        ):
            with self.subTest(word=verdict):
                self.assertNotIn(verdict, reported)

    def test_no_module_reconstructs_provenance_from_prose(self) -> None:
        for name, text in (
            ("builder", BUILDER_SOURCE),
            ("proposal", PROPOSAL_SOURCE),
        ):
            with self.subTest(module=name):
                vocabulary = module_vocabulary(text)
                for forbidden in (
                    "similarity",
                    "embedding",
                    "findall",
                    "fullmatch",
                    "search",
                ):
                    self.assertNotIn(forbidden, vocabulary)


class StalenessTests(ProposalFixture):
    def test_a_gap_that_has_since_closed_refuses_the_proposal(self) -> None:
        """The exact sequence the milestone exists to get right."""
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)
        self.assertIsNotNone(self._prepare(question.question_id).curiosity_proposal)

        self.hypothesis_store.hypotheses = [
            self.hypothesis.addresses_test_by((self.evidence_id,), NOW)
        ]
        response = self._prepare(question.question_id)

        self.assertIsNone(response.curiosity_proposal)
        self.assertIn("no longer current", response.message)

    def test_freshness_is_re_evaluated_on_every_request(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)

        self.hypothesis_store.hypotheses = [
            self.hypothesis.addresses_test_by((self.evidence_id,), NOW)
        ]
        refused = self._prepare(question.question_id)
        self.hypothesis_store.hypotheses = [self.hypothesis]
        allowed = self._prepare(question.question_id)

        self.assertIsNone(refused.curiosity_proposal)
        self.assertIsNotNone(allowed.curiosity_proposal)

    def test_a_stale_refusal_does_not_change_the_question(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)
        self.hypothesis_store.hypotheses = [
            self.hypothesis.addresses_test_by((self.evidence_id,), NOW)
        ]

        self._prepare(question.question_id)

        [stored] = [
            entry
            for entry in self.service.questions()
            if entry.question_id == question.question_id
        ]
        self.assertIs(stored.status, CuriosityQuestionStatus.ACCEPTED)

    def test_the_staleness_check_never_writes_a_hypothesis(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)

        self._prepare(question.question_id)

        self.assertEqual(self.hypothesis_store.saves, 0)


class PlanTests(ProposalFixture):
    def _proposal(self, kind=ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP):
        question = self._question_of(kind)
        self._accept(question.question_id)
        return self._prepare(question.question_id).curiosity_proposal

    def test_the_plan_looks_locally_then_discovers_and_nothing_further(self) -> None:
        proposal = self._proposal()

        self.assertGreaterEqual(proposal.step_count, 2)
        local, *outward = proposal.plan.steps
        self.assertIs(
            local.capability,
            ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
        )
        self.assertIn(proposal.question, local.instruction)
        for step in outward:
            with self.subTest(step=step.step_id):
                self.assertIs(
                    step.capability, ResearchPlanStepCapability.SOURCE_DISCOVERY
                )

    def test_the_proposal_is_not_authorized_and_not_running(self) -> None:
        proposal = self._proposal()

        self.assertFalse(proposal.authorized)
        self.assertFalse(proposal.started)
        rendered = "\n".join(proposal.lines())
        self.assertIn("preview only, not authorized, not running", rendered)
        self.assertIn("separate explicit authorization", rendered)

    def test_the_preview_never_says_anything_is_starting(self) -> None:
        rendered = "\n".join(self._proposal().lines()).casefold()

        for forbidden in ("starting research", "running...", "executing"):
            with self.subTest(phrase=forbidden):
                self.assertNotIn(forbidden, rendered)

    def test_the_same_state_previews_the_same_plan_and_digest(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)

        first = self._prepare(question.question_id).curiosity_proposal
        second = self._prepare(question.question_id).curiosity_proposal

        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.plan.steps, second.plan.steps)
        self.assertEqual(first.digest, plan_digest(first.plan))

    def test_a_different_gap_proposes_a_different_plan(self) -> None:
        hypothesis_proposal = self._proposal()
        other = self._proposal(ResearchKnowledgeGapKind.UNASSESSED_SOURCE)

        self.assertNotEqual(hypothesis_proposal.digest, other.digest)

    def test_a_failed_acquisition_proposal_does_not_propose_a_retry(self) -> None:
        self.manager.record_failure(
            self.run_id, "source_load", "Research source acquisition failed."
        )

        proposal = self._proposal(ResearchKnowledgeGapKind.FAILED_ACQUISITION)

        rendered = "\n".join(proposal.lines()).casefold()
        self.assertIn("without repeating the failed attempt", rendered)
        for forbidden in ("retry", "try again", "re-run"):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, rendered)

    def test_a_coverage_proposal_names_the_unasked_provider_only(self) -> None:
        self.manager.add_discovery(
            self.run_id,
            QUESTION,
            "crossref",
            [
                ResearchSourceCandidate(
                    url="https://doi.org/10.1/a", title="A paper", snippet=""
                )
            ],
        )

        proposal = self._proposal(ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP)

        rendered = "\n".join(proposal.lines())
        self.assertIn("nvd", rendered)
        self.assertIn("Neither provider is preferred", rendered)


class IsolationTests(ProposalFixture):
    """What preparing a proposal must not touch, reach, or create."""

    def test_preparing_reaches_no_provider_and_loads_no_source(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)
        before = self.manager.get(self.run_id)

        self._prepare(question.question_id)

        after = self.manager.get(self.run_id)
        self.assertEqual(after.discoveries, before.discoveries)
        self.assertEqual(after.sources, before.sources)
        self.assertEqual(after.evidence, before.evidence)
        self.assertEqual(after.claims, before.claims)
        self.assertEqual(after.assessments, before.assessments)
        self.assertEqual(after.failures, before.failures)

    def test_the_service_holds_no_provider_fetcher_or_model(self) -> None:
        """Isolation by construction: it has nothing to reach with."""
        for attribute in (
            "_research_source_fetcher",
            "_research_source_discovery_provider",
            "_llm_provider",
            "_tool_runtime",
        ):
            with self.subTest(attribute=attribute):
                self.assertFalse(hasattr(self.service, attribute))

    def test_no_proposal_module_can_reach_or_execute_anything(self) -> None:
        for name, text in (
            ("builder", BUILDER_SOURCE),
            ("proposal", PROPOSAL_SOURCE),
        ):
            with self.subTest(module=name):
                vocabulary = module_vocabulary(text)
                for forbidden in (
                    "urlopen",
                    "urllib",
                    "socket",
                    "requests",
                    "subprocess",
                    "ollama",
                    "authorize",
                    "authorization",
                    "advance",
                    "execute",
                ):
                    self.assertNotIn(forbidden, vocabulary)

    def test_the_proposal_creates_no_authorization_object(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)

        proposal = self._prepare(question.question_id).curiosity_proposal

        self.assertFalse(proposal.authorized)
        for attribute in ("authorization", "approval", "authorized_at"):
            with self.subTest(attribute=attribute):
                self.assertFalse(hasattr(proposal, attribute))

    def test_an_accepted_question_is_not_an_authorization(self) -> None:
        """Status and permission are different kinds of thing."""
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)

        [stored] = [
            entry
            for entry in self.service.questions()
            if entry.question_id == question.question_id
        ]

        self.assertIs(stored.status, CuriosityQuestionStatus.ACCEPTED)
        self.assertNotIsInstance(stored.status, bool)
        for attribute in ("digest", "plan", "authorization"):
            with self.subTest(attribute=attribute):
                self.assertFalse(hasattr(stored, attribute))

    def test_the_plan_is_drafted_but_never_advanced(self) -> None:
        question = self._question_of(ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP)
        self._accept(question.question_id)

        proposal = self._prepare(question.question_id).curiosity_proposal

        for attribute in ("started_at", "attempts", "step_states", "budget_spent"):
            with self.subTest(attribute=attribute):
                self.assertFalse(hasattr(proposal.plan, attribute))
        self.assertFalse(proposal.started)


class BuilderValidationTests(unittest.TestCase):
    def test_the_builder_refuses_anything_that_is_not_a_question(self) -> None:
        from research.CuriosityProposalBuilder import CuriosityProposalBuilder

        with self.assertRaises(ResearchError):
            CuriosityProposalBuilder().build(
                "not a question",  # type: ignore[arg-type]
                None,  # type: ignore[arg-type]
                ResearchPlanDraftService(),
            )


if __name__ == "__main__":
    unittest.main()
