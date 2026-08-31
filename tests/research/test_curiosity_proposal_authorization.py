"""Approving one exact proposal, bound to the digest a person actually read.

The previous milestone produced a proposal and stopped. This crosses the
authorization boundary — once, deliberately, with the digest in hand — and stops
again before anything runs.

The digest comparison is the whole safeguard, and most of what follows is about
it. An operator supplies which question and which digest they were shown;
neither is trusted as content. The proposal is derived again from current
canonical state by the same code that produced the preview, and the digest they
name has to equal the one that derivation produces. Every way the plan could
have moved underneath them is caught by that one check: a gap that closed, a
hypothesis that gained evidence, a provider since asked, a question since
dismissed.

What an approval is not is a start. It records that a person agreed to exactly
this plan; nothing is consumed, no step exists, and beginning the work remains a
separate action that this milestone does not provide.
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
    CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
    CURIOSITY_PREPARE_PROPOSAL_INTENT,
    CuriosityApplicationService,
)
from cognition.ResearchPlanAuthorizationApplicationService import (
    ResearchPlanAuthorizationApplicationService,
)
from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.CuriosityQuestionStatus import CuriosityQuestionStatus
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchPlanAuthorizationVerdict import (
    ResearchPlanAuthorizationVerdict,
)
from research.ResearchPlanAuthorizationVerifier import verify_plan_authorization
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSource import ResearchSource
from response.ResponseComposer import ResponseComposer
from tests.SourceVocabulary import module_vocabulary

PAST = datetime.now(UTC) - timedelta(days=1)
NOW = PAST + timedelta(hours=1)
QUESTION = "Can the middleware authorization check be bypassed?"
STATEMENT = "Authorization middleware can be bypassed before route handling."
TEST = "Observe whether a protected route is reached without authorization."

CURIOSITY_SERVICE_SOURCE = (
    SRC_DIR / "cognition" / "CuriosityApplicationService.py"
).read_text(encoding="utf-8")

HYPOTHESIS_GAP = ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP


class StubHypothesisStore:
    def __init__(self, hypotheses: list[ResearchHypothesis]) -> None:
        self.hypotheses = hypotheses

    def load(self) -> list[ResearchHypothesis]:
        return list(self.hypotheses)

    def save(self, hypotheses: list[ResearchHypothesis]) -> None:
        raise AssertionError("Approving must never write a hypothesis.")


class AuthorizationFixture(unittest.TestCase):
    """Real curiosity service over the real authorization service and store."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.authorization_path = self.root / "authorizations.json"
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
        self.hypothesis_store = StubHypothesisStore([self.hypothesis])
        self.authorization_service = self._authorization_service()
        self.service = self._service()
        self.question = self._question(HYPOTHESIS_GAP)

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

    def _authorization_service(self) -> ResearchPlanAuthorizationApplicationService:
        return ResearchPlanAuthorizationApplicationService(
            self.manager,
            ResponseComposer(),
            authorization_store=JsonFileResearchPlanAuthorizationStore(
                self.authorization_path
            ),
            clock=lambda: NOW,
        )

    def _service(self) -> CuriosityApplicationService:
        return CuriosityApplicationService(
            self.manager,
            ResponseComposer(),
            hypothesis_store=self.hypothesis_store,
            authorization_service=self.authorization_service,
            draft_service=ResearchPlanDraftService(
                id_factory=lambda: "plan-1", clock=lambda: NOW
            ),
            clock=lambda: NOW,
        )

    def _request(self, intent: str, **metadata: str) -> BrainRequest:
        return BrainRequest(
            message="Curiosity", metadata={"intent": intent, **metadata}
        )

    def _question(self, kind: ResearchKnowledgeGapKind):
        self.service.process_question_store(
            self._request("curiosity_question_store", research_run_id=self.run_id)
        )
        [question] = [entry for entry in self.service.questions() if entry.kind is kind]
        return question

    def _accept(self) -> None:
        self.service.process_question_accept(
            self._request(
                "curiosity_question_accept",
                curiosity_question_id=self.question.question_id,
            )
        )

    def _preview(self):
        return self.service.process_prepare_proposal(
            self._request(
                CURIOSITY_PREPARE_PROPOSAL_INTENT,
                curiosity_question_id=self.question.question_id,
            )
        )

    def _authorize(self, digest: str, question_id: str | None = None):
        return self.service.process_authorize_proposal(
            self._request(
                CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
                curiosity_question_id=question_id or self.question.question_id,
                expected_plan_digest=digest,
            )
        )

    def _accepted_digest(self) -> str:
        self._accept()
        return self._preview().curiosity_proposal.digest

    def _stored(self):
        return JsonFileResearchPlanAuthorizationStore(self.authorization_path).load()


class EligibilityTests(AuthorizationFixture):
    def test_previewing_alone_records_no_approval(self) -> None:
        """The decision this milestone must not have merged into the preview."""
        self._accept()

        response = self._preview()

        self.assertIsNotNone(response.curiosity_proposal)
        self.assertIsNone(response.research_plan_authorization)
        self.assertEqual(self._stored(), [])

    def test_an_accepted_question_with_its_digest_is_authorized(self) -> None:
        digest = self._accepted_digest()

        response = self._authorize(digest)

        authorization = response.research_plan_authorization
        self.assertIsNotNone(authorization)
        self.assertEqual(authorization.plan_digest, digest)
        self.assertEqual(authorization.research_run_id, self.run_id)

    def test_a_proposed_question_cannot_be_authorized(self) -> None:
        response = self._authorize("a" * 64)

        self.assertIsNone(response.research_plan_authorization)
        self.assertEqual(self._stored(), [])

    def test_a_dismissed_question_cannot_be_authorized(self) -> None:
        """A question somebody threw away stays thrown away.

        Dismissing happens while a question is undecided — the model refuses to
        re-decide one — so this dismisses first and then attempts approval,
        which is the only order in which a dismissed question can reach here.
        """
        self.service.process_question_dismiss(
            self._request(
                "curiosity_question_dismiss",
                curiosity_question_id=self.question.question_id,
            )
        )

        response = self._authorize("a" * 64)

        self.assertIsNone(response.research_plan_authorization)
        self.assertIn("dismissed", response.message)
        self.assertEqual(self._stored(), [])

    def test_an_accepted_question_cannot_be_dismissed_out_from_under_it(
        self,
    ) -> None:
        """Existing semantics: a decided question is not re-decided."""
        digest = self._accepted_digest()

        self.service.process_question_dismiss(
            self._request(
                "curiosity_question_dismiss",
                curiosity_question_id=self.question.question_id,
            )
        )

        [stored] = [
            entry
            for entry in self.service.questions()
            if entry.question_id == self.question.question_id
        ]
        self.assertIs(stored.status, CuriosityQuestionStatus.ACCEPTED)
        self.assertIsNotNone(self._authorize(digest).research_plan_authorization)

    def test_an_unknown_question_is_refused(self) -> None:
        digest = self._accepted_digest()

        response = self._authorize(digest, question_id="question-missing")

        self.assertIsNone(response.research_plan_authorization)
        self.assertEqual(self._stored(), [])

    def test_the_request_must_name_a_digest_at_all(self) -> None:
        """A missing field raises here and is rendered as a refusal upstream,
        which is how every other required field on this service behaves."""
        self._accept()

        with self.assertRaises(ResearchError):
            self.service.process_authorize_proposal(
                self._request(
                    CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
                    curiosity_question_id=self.question.question_id,
                )
            )

        self.assertEqual(self._stored(), [])


class DigestBindingTests(AuthorizationFixture):
    def test_a_wrong_digest_is_refused_and_nothing_is_searched_for(self) -> None:
        self._accepted_digest()

        response = self._authorize("b" * 64)

        self.assertIsNone(response.research_plan_authorization)
        self.assertIn("changed since preview", response.message)
        self.assertEqual(self._stored(), [])

    def test_a_malformed_digest_is_refused(self) -> None:
        self._accepted_digest()

        for malformed in ("not-a-digest", "abc", "Z" * 64, "0" * 63):
            with self.subTest(digest=malformed):
                response = self._authorize(malformed)
                self.assertIsNone(response.research_plan_authorization)
        with self.assertRaises(ResearchError):
            self._authorize("   ")
        self.assertEqual(self._stored(), [])

    def test_a_digest_from_another_question_is_refused(self) -> None:
        """No cross-question approval: the other question is re-derived."""
        other = self._question(ResearchKnowledgeGapKind.UNASSESSED_SOURCE)
        self._accept()
        self.service.process_question_accept(
            self._request(
                "curiosity_question_accept",
                curiosity_question_id=other.question_id,
            )
        )
        other_digest = self.service.process_prepare_proposal(
            self._request(
                CURIOSITY_PREPARE_PROPOSAL_INTENT,
                curiosity_question_id=other.question_id,
            )
        ).curiosity_proposal.digest

        response = self._authorize(other_digest)

        self.assertIsNone(response.research_plan_authorization)
        self.assertEqual(self._stored(), [])

    def test_the_plan_is_re_derived_and_never_taken_from_the_request(self) -> None:
        """A request carrying plan content cannot widen what is approved."""
        digest = self._accepted_digest()

        response = self.service.process_authorize_proposal(
            BrainRequest(
                message="Curiosity",
                metadata={
                    "intent": CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
                    "curiosity_question_id": self.question.question_id,
                    "expected_plan_digest": digest,
                    "plan": {"steps": [{"capability": "source_fetch"}]},
                    "capabilities": ["source_fetch", "source_accept"],
                },
            )
        )

        authorization = response.research_plan_authorization
        self.assertIsNotNone(authorization)
        self.assertEqual(
            {capability.value for capability in authorization.capabilities},
            {"source_discovery"},
        )

    def test_no_fuzzy_or_latest_proposal_lookup_exists(self) -> None:
        vocabulary = module_vocabulary(CURIOSITY_SERVICE_SOURCE)

        for forbidden in ("similarity", "embedding", "latest", "most_recent"):
            with self.subTest(term=forbidden):
                self.assertNotIn(forbidden, vocabulary)


class StalenessTests(AuthorizationFixture):
    def test_a_gap_that_closed_after_preview_refuses_approval(self) -> None:
        """The sequence this check exists for."""
        digest = self._accepted_digest()
        self.hypothesis_store.hypotheses = [
            self.hypothesis.addresses_test_by((self.evidence_id,), NOW)
        ]

        response = self._authorize(digest)

        self.assertIsNone(response.research_plan_authorization)
        self.assertIn("no longer current", response.message)
        self.assertEqual(self._stored(), [])

    def test_a_coverage_proposal_answered_after_preview_is_refused(self) -> None:
        """The plan named one provider; asking it makes that plan obsolete."""
        self.manager.add_discovery(self.run_id, QUESTION, "crossref", [])
        coverage = self._question(ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP)
        self.service.process_question_accept(
            self._request(
                "curiosity_question_accept",
                curiosity_question_id=coverage.question_id,
            )
        )
        stale_digest = self.service.process_prepare_proposal(
            self._request(
                CURIOSITY_PREPARE_PROPOSAL_INTENT,
                curiosity_question_id=coverage.question_id,
            )
        ).curiosity_proposal.digest

        self.manager.add_discovery(self.run_id, QUESTION, "nvd", [])
        response = self.service.process_authorize_proposal(
            self._request(
                CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
                curiosity_question_id=coverage.question_id,
                expected_plan_digest=stale_digest,
            )
        )

        self.assertIsNone(response.research_plan_authorization)
        self.assertEqual(self._stored(), [])

    def test_an_unchanged_proposal_still_authorizes_after_a_restart(self) -> None:
        """Proposals are transient; approval re-derives rather than remembering."""
        digest = self._accepted_digest()

        reopened = self._service()
        reopened.process_question_store(
            self._request("curiosity_question_store", research_run_id=self.run_id)
        )
        reopened.process_question_accept(
            self._request(
                "curiosity_question_accept",
                curiosity_question_id=self.question.question_id,
            )
        )
        response = reopened.process_authorize_proposal(
            self._request(
                CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
                curiosity_question_id=self.question.question_id,
                expected_plan_digest=digest,
            )
        )

        self.assertIsNotNone(response.research_plan_authorization)
        self.assertEqual(response.research_plan_authorization.plan_digest, digest)


class AuthorizationRecordTests(AuthorizationFixture):
    def test_the_approval_is_human_and_carries_the_exact_digest(self) -> None:
        digest = self._accepted_digest()

        authorization = self._authorize(digest).research_plan_authorization

        self.assertIs(authorization.authorized_by, ResearchAuthorizer.HUMAN)
        self.assertEqual(authorization.plan_digest, digest)
        self.assertEqual(authorization.authorized_at, NOW)
        self.assertGreater(authorization.expires_at, authorization.authorized_at)

    def test_the_approval_survives_a_restart_of_the_store(self) -> None:
        digest = self._accepted_digest()
        self._authorize(digest)

        [restored] = self._stored()

        self.assertEqual(restored.plan_digest, digest)
        self.assertIs(restored.authorized_by, ResearchAuthorizer.HUMAN)
        self.assertEqual(restored.research_run_id, self.run_id)

    def test_the_approval_is_valid_and_unconsumed(self) -> None:
        """Creating permission is not using it."""
        digest = self._accepted_digest()
        proposal = self._preview().curiosity_proposal

        authorization = self._authorize(digest).research_plan_authorization

        self.assertIsNone(authorization.consumption)
        self.assertIs(
            verify_plan_authorization(authorization, proposal.plan, self.run_id, NOW),
            ResearchPlanAuthorizationVerdict.VALID,
        )

    def test_authorizing_twice_records_two_distinct_approvals(self) -> None:
        """Existing policy: identity is per approval, so each is its own record.

        The service refuses only a repeated *identity*, and every approval gets
        a fresh one, so a second deliberate approval of the same plan is
        recorded rather than merged. Nothing is overwritten and no approval is
        silently reused.
        """
        digest = self._accepted_digest()

        first = self._authorize(digest).research_plan_authorization
        second = self._authorize(digest).research_plan_authorization

        self.assertNotEqual(first.authorization_id, second.authorization_id)
        self.assertEqual(first.plan_digest, second.plan_digest)
        self.assertEqual(len(self._stored()), 2)

    def test_the_wording_says_approved_and_not_running(self) -> None:
        digest = self._accepted_digest()

        message = self._authorize(digest).message

        self.assertIn("AUTHORIZED", message)
        self.assertIn("not running", message)
        self.assertIn("Nothing has started", message)
        for forbidden in ("starting", "executing", "advancing"):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, message.casefold())

    def test_the_preview_still_says_not_authorized(self) -> None:
        self._accept()

        message = self._preview().message

        self.assertIn("not authorized", message)


class IsolationTests(AuthorizationFixture):
    def test_approving_touches_nothing_in_the_run(self) -> None:
        digest = self._accepted_digest()
        before = self.manager.get(self.run_id)

        self._authorize(digest)

        after = self.manager.get(self.run_id)
        self.assertEqual(after.discoveries, before.discoveries)
        self.assertEqual(after.sources, before.sources)
        self.assertEqual(after.evidence, before.evidence)
        self.assertEqual(after.claims, before.claims)
        self.assertEqual(after.assessments, before.assessments)
        self.assertEqual(after.failures, before.failures)

    def test_approving_never_writes_a_hypothesis(self) -> None:
        """The stub raises if anything tries, so passing is the proof."""
        digest = self._accepted_digest()

        self._authorize(digest)

        self.assertEqual(len(self.hypothesis_store.hypotheses), 1)

    def test_the_curiosity_service_cannot_execute_anything(self) -> None:
        vocabulary = module_vocabulary(CURIOSITY_SERVICE_SOURCE)

        for forbidden in (
            "urlopen",
            "urllib",
            "socket",
            "requests",
            "subprocess",
            "ollama",
            "process_advance",
            "advance",
            "execution",
        ):
            with self.subTest(term=forbidden):
                self.assertNotIn(forbidden, vocabulary)

    def test_the_service_holds_no_execution_or_provider_port(self) -> None:
        for attribute in (
            "_execution_service",
            "_research_source_fetcher",
            "_research_source_discovery_provider",
            "_llm_provider",
            "_tool_runtime",
        ):
            with self.subTest(attribute=attribute):
                self.assertFalse(hasattr(self.service, attribute))

    def test_approving_without_an_authorization_service_is_refused(self) -> None:
        service = CuriosityApplicationService(
            self.manager,
            ResponseComposer(),
            hypothesis_store=self.hypothesis_store,
            clock=lambda: NOW,
        )
        service.process_question_store(
            self._request("curiosity_question_store", research_run_id=self.run_id)
        )
        service.process_question_accept(
            self._request(
                "curiosity_question_accept",
                curiosity_question_id=self.question.question_id,
            )
        )

        response = service.process_authorize_proposal(
            self._request(
                CURIOSITY_AUTHORIZE_PROPOSAL_INTENT,
                curiosity_question_id=self.question.question_id,
                expected_plan_digest="a" * 64,
            )
        )

        self.assertIsNone(response.research_plan_authorization)
        self.assertEqual(self._stored(), [])

    def test_the_question_is_unchanged_by_approving(self) -> None:
        digest = self._accepted_digest()

        self._authorize(digest)

        [stored] = [
            entry
            for entry in self.service.questions()
            if entry.question_id == self.question.question_id
        ]
        self.assertIs(stored.status, CuriosityQuestionStatus.ACCEPTED)


if __name__ == "__main__":
    unittest.main()
