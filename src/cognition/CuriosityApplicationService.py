"""Bounded curiosity: notice, propose, and cross only explicit human gates.

The pipeline is deliberately short of acting. Detection reads a run, generation
drafts questions from templates, ranking orders them, and preview reports them.
Storing a question records a proposal; accepting one records that a human thinks
it is worth pursuing. Preparing, authorizing, and starting remain three separate
operator acts. Even the last act is zero-step: it spends one approval and creates
foreground execution state, but contacts no provider and performs no operation.

That separation is the point. A system that automatically chased everything it
noticed would convert idle curiosity into unbounded work, and would quietly
decide for itself what deserves investigation.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.CuriosityEvents import CuriosityEvents
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.CuriosityProposalBuilder import CuriosityProposalBuilder
from research.CuriosityQuestionStatus import CuriosityQuestionStatus
from research.CuriosityQuestionStore import CuriosityQuestionStore
from research.CuriosityResearchProposal import CuriosityResearchProposal
from research.HypothesisStore import HypothesisStore
from research.JsonFileCuriosityQuestionStore import MAX_CURIOSITY_STORE_QUESTIONS
from research.RecordsResearchPlanAuthorization import (
    RecordsResearchPlanAuthorization,
)
from research.ResearchAuthorizationBudgetChoice import budget_from
from research.ResearchCuriosityPreview import ResearchCuriosityPreview
from research.ResearchCuriosityQuestion import ResearchCuriosityQuestion
from research.ResearchCuriosityQuestionGenerator import (
    ResearchCuriosityQuestionGenerator,
)
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchKnowledgeGapDetector import ResearchKnowledgeGapDetector
from research.ResearchPlanDigest import is_plan_digest
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.StartsResearchPlanExecution import (
    ResearchPlanExecutionStartRefusal,
    StartsResearchPlanExecution,
)
from response.ResponseComposer import ResponseComposer

CURIOSITY_GAP_DETECT_INTENT = "curiosity_gap_detect"
CURIOSITY_QUESTION_PREVIEW_INTENT = "curiosity_question_preview"
CURIOSITY_QUESTION_STORE_INTENT = "curiosity_question_store"
CURIOSITY_QUESTION_LIST_INTENT = "curiosity_question_list"
CURIOSITY_QUESTION_ACCEPT_INTENT = "curiosity_question_accept"
CURIOSITY_QUESTION_DISMISS_INTENT = "curiosity_question_dismiss"
CURIOSITY_PREPARE_PROPOSAL_INTENT = "curiosity_prepare_proposal"
CURIOSITY_AUTHORIZE_PROPOSAL_INTENT = "curiosity_authorize_proposal"
CURIOSITY_START_AUTHORIZED_PROPOSAL_INTENT = "curiosity_start_authorized_proposal"
CURIOSITY_RESUME_EXECUTION_INTENT = "curiosity_resume_execution"


class CuriosityApplicationService:
    """Detect gaps, propose questions, and honor only explicit human gates."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        detector: ResearchKnowledgeGapDetector | None = None,
        generator: ResearchCuriosityQuestionGenerator | None = None,
        question_store: CuriosityQuestionStore | None = None,
        hypothesis_store: HypothesisStore | None = None,
        draft_service: ResearchPlanDraftService | None = None,
        authorization_service: RecordsResearchPlanAuthorization | None = None,
        execution_starter: StartsResearchPlanExecution | None = None,
        event_bus: EventBus | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._detector = detector or ResearchKnowledgeGapDetector()
        self._generator = generator or ResearchCuriosityQuestionGenerator()
        self._question_store = question_store
        self._hypothesis_store = hypothesis_store
        # Injected so a preview's plan identity and time are deterministic in
        # tests. The digest ignores both, so a default service still previews
        # the same plan content twice.
        self._draft_service = draft_service or ResearchPlanDraftService()
        # The one place approvals are written. Curiosity does not build an
        # approval itself, so there is no second kind of approval to reason
        # about, and where the service is absent no proposal can be approved.
        self._authorization_service = authorization_service
        # A deliberately narrower boundary than the ordinary execution
        # application service. Curiosity can ask to start only the exact plan
        # it just re-derived; it cannot advance a step or reach an operation.
        self._execution_starter = execution_starter
        self._events = CuriosityEvents(event_bus)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._questions: dict[str, ResearchCuriosityQuestion] = {}
        self._restore()

    @staticmethod
    def is_gap_detect_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_GAP_DETECT_INTENT

    @staticmethod
    def is_question_preview_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_QUESTION_PREVIEW_INTENT

    @staticmethod
    def is_question_store_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_QUESTION_STORE_INTENT

    @staticmethod
    def is_question_list_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_QUESTION_LIST_INTENT

    @staticmethod
    def is_question_accept_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_QUESTION_ACCEPT_INTENT

    @staticmethod
    def is_authorize_proposal_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_AUTHORIZE_PROPOSAL_INTENT

    @staticmethod
    def is_start_authorized_proposal_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent") == CURIOSITY_START_AUTHORIZED_PROPOSAL_INTENT
        )

    @staticmethod
    def is_resume_execution_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_RESUME_EXECUTION_INTENT

    @staticmethod
    def is_prepare_proposal_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_PREPARE_PROPOSAL_INTENT

    @staticmethod
    def is_question_dismiss_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CURIOSITY_QUESTION_DISMISS_INTENT

    def questions(self) -> tuple[ResearchCuriosityQuestion, ...]:
        """Return every known proposal, highest rank first."""
        return tuple(
            sorted(
                self._questions.values(),
                key=lambda question: (-question.rank_score, question.question_id),
            )
        )

    def process_gap_detect(self, request: BrainRequest) -> BrainResponse:
        """Report where one run's own record is thin, proposing nothing."""
        preview = self._detect(request, generate=False)
        self._events.gaps_detected(preview)
        return self._response_composer.curiosity_gaps(request, preview)

    def process_question_preview(self, request: BrainRequest) -> BrainResponse:
        """Draft and rank questions for one run without storing any of them."""
        preview = self._detect(request, generate=True)
        self._events.gaps_detected(preview)
        self._events.questions_generated(preview)
        return self._response_composer.curiosity_preview(request, preview)

    def process_question_store(self, request: BrainRequest) -> BrainResponse:
        """Persist the ranked proposals for one run, deciding nothing."""
        preview = self._detect(request, generate=True)
        self._events.gaps_detected(preview)
        self._events.questions_generated(preview)
        stored, durable = self._store(preview.questions)
        if not durable:
            return self._response_composer.curiosity_persistence_failed(
                request,
                f"{stored} proposal(s)",
            )
        persisted = ResearchCuriosityPreview(
            run_id=preview.run_id,
            gaps=preview.gaps,
            questions=preview.questions,
            stored=True,
        )
        self._events.questions_stored(persisted, stored, len(self._questions))
        return self._response_composer.curiosity_preview(request, persisted)

    def process_question_list(self, request: BrainRequest) -> BrainResponse:
        """Report every stored proposal without running anything."""
        return self._response_composer.curiosity_question_list(
            request,
            self.questions(),
        )

    def process_authorize_proposal(self, request: BrainRequest) -> BrainResponse:
        """Record a human approval of one exact previewed proposal.

        The operator supplies two things: which question, and the digest they
        were shown. Neither is trusted as content. The proposal is derived again
        from current canonical state by the same path that produced the preview,
        and the digest they name has to equal the one that derivation produces.

        That comparison is the whole safeguard. A digest is what the approval
        will be bound to, so approving anything other than the plan the person
        actually read would make the record a lie about what they agreed to —
        and every way the plan could have moved underneath them is caught by the
        same check: a gap that closed, a hypothesis that gained evidence, a
        provider that has since been asked.

        Nothing runs. An approval is permission that execution may later be
        started against this exact plan by a separate action, and this creates
        the permission without using it.
        """
        if self._authorization_service is None:
            return self._response_composer.curiosity_rejected(
                request,
                "Research plan approval is unavailable.",
            )
        expected = self._required_text(
            request,
            "expected_plan_digest",
            "expected plan digest",
        )
        if not is_plan_digest(expected):
            return self._response_composer.curiosity_rejected(
                request,
                "That is not a research plan digest, so nothing was approved.",
            )
        derived = self._derive_proposal(request)
        if isinstance(derived, BrainResponse):
            return derived
        proposal, run = derived
        if proposal.digest != expected:
            return self._response_composer.curiosity_rejected(
                request,
                "Proposal changed since preview. Prepare a new preview before "
                "authorizing.",
            )
        try:
            chosen = budget_from(request.metadata)
        except ResearchError as error:
            return self._response_composer.curiosity_rejected(request, str(error))
        authorization = self._authorization_service.record_for_plan(
            proposal.plan,
            run.run_id,
            budget=chosen,
        )
        if authorization is None:
            return self._response_composer.curiosity_rejected(
                request,
                "The approval could not be written durably, so it was not " "recorded.",
            )
        return self._response_composer.curiosity_proposal_authorized(
            request,
            proposal,
            authorization,
        )

    def process_start_authorized_proposal(
        self,
        request: BrainRequest,
    ) -> BrainResponse:
        """Spend one exact approval on a zero-step foreground start.

        The request carries only identities the operator was shown. The plan
        itself is rebuilt from the accepted question and current run state,
        then checked against the displayed digest before the existing approval
        consumer sees it. A successful start creates RUNNING execution state;
        it never advances that state, so every authored step remains pending.
        """
        if self._execution_starter is None:
            return self._response_composer.curiosity_rejected(
                request,
                "Research plan execution is unavailable.",
            )
        expected = self._required_text(
            request,
            "expected_plan_digest",
            "expected plan digest",
        )
        if not is_plan_digest(expected):
            return self._response_composer.curiosity_rejected(
                request,
                "That is not a research plan digest, so nothing was started.",
            )
        authorization_id = self._required_text(
            request,
            "authorization_id",
            "authorization",
        )
        derived = self._derive_proposal(request)
        if isinstance(derived, BrainResponse):
            return derived
        proposal, run = derived
        if proposal.digest != expected:
            return self._response_composer.curiosity_rejected(
                request,
                "Proposal changed since preview. Prepare and authorize a new "
                "preview before starting.",
            )
        started = self._execution_starter.start_for_plan(
            proposal.plan,
            run.run_id,
            authorization_id,
        )
        if isinstance(started, ResearchPlanExecutionStartRefusal):
            return self._response_composer.curiosity_rejected(
                request,
                started.reason,
            )
        return self._response_composer.curiosity_proposal_execution_started(
            request,
            proposal,
            authorization_id,
            started,
        )

    def process_resume_execution(self, request: BrainRequest) -> BrainResponse:
        """Make one durable execution advanceable again in this process.

        The operator names an exact execution. What permits it is the approval
        that was already spent on that execution: this looks that approval up,
        rebuilds the plan, and requires the rebuilt digest to equal the one the
        approval named. A restart therefore cannot create authority, because no
        approval is created, consulted for permission, or un-spent here — the
        only question asked is whether this is provably the same plan.

        Deliberately absent is the gap-currency check that gates previewing and
        approving. That check asks whether new research is worth proposing, and
        this is not a proposal; the work was approved and begun before the
        restart. Re-asking it here would let a closed gap quietly revoke an
        approval that was already given and spent, which is a decision for the
        operator to make by cancelling, not for a process restart to make.
        """
        if self._execution_starter is None:
            return self._response_composer.curiosity_rejected(
                request,
                "Research plan execution is unavailable.",
            )
        if self._authorization_service is None:
            return self._response_composer.curiosity_rejected(
                request,
                "Research plan approval records are unavailable, so no "
                "execution can be shown to have been approved.",
            )
        execution_id = self._required_text(
            request,
            "research_plan_id",
            "execution",
        )
        authorization = self._authorization_service.authorization_for_execution(
            execution_id,
        )
        if authorization is None:
            return self._response_composer.curiosity_rejected(
                request,
                "No used approval names that execution, so it cannot be "
                "shown to have been authorized and was not resumed.",
            )
        rebuilt = self._rebuild_proposal(request)
        if isinstance(rebuilt, BrainResponse):
            return rebuilt
        proposal, run = rebuilt
        if proposal.digest != authorization.plan_digest:
            return self._response_composer.curiosity_rejected(
                request,
                "The plan no longer matches the approved digest, so this "
                "execution was not resumed.",
            )
        restored = self._execution_starter.rebind_restored(
            proposal.plan,
            run.run_id,
            execution_id,
        )
        if isinstance(restored, ResearchPlanExecutionStartRefusal):
            return self._response_composer.curiosity_rejected(
                request,
                restored.reason,
            )
        return self._response_composer.curiosity_proposal_execution_resumed(
            request,
            proposal,
            authorization.authorization_id,
            restored,
        )

    def _rebuild_proposal(
        self,
        request: BrainRequest,
    ) -> tuple[CuriosityResearchProposal, ResearchRun] | BrainResponse:
        """Build the proposal for one question again, judging nothing new.

        The same canonical builder previewing uses, so the plan it returns is
        the plan that was digested. It asks only what is needed to rebuild:
        that the question and its run still exist. Whether the plan is the
        approved one is settled afterwards by the digest, which is a stronger
        answer than any check made here could be.
        """
        question_id = self._required_text(request, "curiosity_question_id", "question")
        question = self._questions.get(question_id)
        if question is None:
            return self._response_composer.curiosity_question_missing(
                request,
                question_id,
            )
        try:
            run = self._run_manager.get(question.run_id)
            proposal = CuriosityProposalBuilder().build(
                question,
                run,
                self._draft_service,
                self._hypotheses_for(question.run_id),
            )
        except ResearchError as error:
            return self._response_composer.curiosity_rejected(request, str(error))
        return proposal, run

    def process_prepare_proposal(self, request: BrainRequest) -> BrainResponse:
        """Draft an inert plan for one accepted question, starting nothing.

        A second, separate operator decision. Accepting a question says it is
        worth keeping; this says a proposal for it is worth reading, and neither
        says anything may run. Nothing here reaches a provider, a source, a tool
        or a model — the plan describes future discovery and performs none of it.

        The gap is re-derived from current state rather than trusted from the
        stored question, because an accepted question outlives the situation
        that produced it. Somebody may have recorded the very evidence the gap
        was about between accepting and asking, and drafting research for a gap
        that has since closed would propose work nobody needs.
        """
        derived = self._derive_proposal(request)
        if isinstance(derived, BrainResponse):
            return derived
        proposal, _run = derived
        self._events.proposal_previewed(proposal)
        return self._response_composer.curiosity_proposal(request, proposal)

    def _derive_proposal(
        self,
        request: BrainRequest,
    ) -> tuple[CuriosityResearchProposal, ResearchRun] | BrainResponse:
        """Build the current proposal for one exact question, or say why not.

        Shared by previewing and approving on purpose. Approving has to see the
        proposal the same way previewing does, and the surest way to guarantee
        that is for there to be one derivation rather than two that agree today.
        """
        question_id = self._required_text(request, "curiosity_question_id", "question")
        question = self._questions.get(question_id)
        if question is None:
            return self._response_composer.curiosity_question_missing(
                request,
                question_id,
            )
        if question.status is not CuriosityQuestionStatus.ACCEPTED:
            return self._response_composer.curiosity_rejected(
                request,
                "A research proposal needs an accepted curiosity question; this "
                f"one is {question.status.value}.",
            )
        try:
            run = self._run_manager.get(question.run_id)
        except ResearchError as error:
            return self._response_composer.curiosity_rejected(request, str(error))
        hypotheses = self._hypotheses_for(run.run_id)
        current = {
            gap.gap_id for gap in self._detector.detect(run, self._clock(), hypotheses)
        }
        if question.gap_id not in current:
            return self._response_composer.curiosity_rejected(
                request,
                "Research proposal not prepared: the originating knowledge gap "
                "is no longer current for this run.",
            )
        try:
            proposal = CuriosityProposalBuilder().build(
                question,
                run,
                self._draft_service,
                hypotheses,
            )
        except ResearchError as error:
            return self._response_composer.curiosity_rejected(request, str(error))
        return proposal, run

    def process_question_accept(self, request: BrainRequest) -> BrainResponse:
        return self._decide(request, accept=True)

    def process_question_dismiss(self, request: BrainRequest) -> BrainResponse:
        return self._decide(request, accept=False)

    def _decide(self, request: BrainRequest, accept: bool) -> BrainResponse:
        """Record a human ruling on one proposal, starting no research."""
        question_id = self._required_text(request, "curiosity_question_id", "question")
        question = self._questions.get(question_id)
        if question is None:
            return self._response_composer.curiosity_question_missing(
                request,
                question_id,
            )
        now = self._clock()
        try:
            updated = question.accepted(now) if accept else question.dismissed(now)
        except ResearchError as error:
            return self._response_composer.curiosity_rejected(request, str(error))
        self._questions[question_id] = updated
        if accept:
            self._events.question_accepted(updated)
        else:
            self._events.question_dismissed(updated)
        if not self._persist():
            return self._response_composer.curiosity_persistence_failed(
                request,
                f"the ruling on {question_id}",
            )
        return self._response_composer.curiosity_question_decided(request, updated)

    def _detect(
        self,
        request: BrainRequest,
        generate: bool,
    ) -> ResearchCuriosityPreview:
        run_id = self._required_text(request, "research_run_id", "run")
        run = self._run_manager.get(run_id)
        hypotheses = self._hypotheses_for(run.run_id)
        gaps = self._detector.detect(run, self._clock(), hypotheses)
        questions = self._generator.generate(run, gaps, hypotheses) if generate else ()
        return ResearchCuriosityPreview(
            run_id=run.run_id,
            gaps=gaps,
            questions=questions,
        )

    def _hypotheses_for(self, run_id: str) -> tuple[ResearchHypothesis, ...]:
        """Return this run's own hypotheses, or none when there is no store.

        Composing the two aggregates is this layer's job precisely because it
        is the only one that knows a store exists. The detector stays a pure
        reading of what it is handed, and curiosity keeps working unchanged
        wherever no hypothesis store is configured.

        A store that cannot be read is not a reason to fail a read-only report
        about a run. The gaps the run itself exposes are still true, so they
        are still reported, and the hypothesis half is simply absent.
        """
        if self._hypothesis_store is None:
            return ()
        try:
            stored = self._hypothesis_store.load()
        except ResearchError:
            return ()
        return tuple(hypothesis for hypothesis in stored if hypothesis.run_id == run_id)

    def _store(
        self,
        questions: tuple[ResearchCuriosityQuestion, ...],
    ) -> tuple[int, bool]:
        """Add proposals that are new, never overwriting a decided one."""
        stored = 0
        for question in questions:
            existing = self._questions.get(question.question_id)
            if existing is not None:
                continue
            if len(self._questions) >= MAX_CURIOSITY_STORE_QUESTIONS:
                break
            self._questions[question.question_id] = question
            stored += 1
        return stored, self._persist() if stored else True

    def _restore(self) -> None:
        if self._question_store is None:
            return
        for question in self._question_store.load():
            self._questions[question.question_id] = question

    def _persist(self) -> bool:
        """Write durable proposals, reporting rather than swallowing a failure.

        True with no store configured is not a false claim: this runtime keeps
        no proposals, and the desktop offers the surface only where it does.
        """
        if self._question_store is None:
            return True
        try:
            self._question_store.save(list(self._questions.values()))
        except ResearchError:
            return False
        return True

    @staticmethod
    def _required_text(request: BrainRequest, key: str, label: str) -> str:
        value = request.metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"Curiosity {label} ID cannot be empty.")
        return value.strip()
