"""Let a person approve one exact plan, durably, without starting anything.

Three commands: preview what approving would record, confirm that exact
approval, and read back what has been approved. None of them executes a plan,
advances a step, queues a task, fetches a source, or calls a model. This
service imports no execution service, no autonomy service, and no scheduler,
so it could not start work even if asked to.

Confirmation is bound to a preview rather than to a description. A preview
returns the exact immutable authorization that confirming would persist, held
in this process under its own identity; confirming names that identity and
re-supplies the plan, and the same pure verifier that any future execution
would use decides whether the two still agree. Rebuilding the approval at
confirmation time would mean the thing recorded was never the thing anyone
looked at.

Consumption lives here too, behind a narrow port. Execution asks one question —
may this exact execution begin — and the answer, if yes, is returned only after
the approval has been durably written as spent. Verifying and then consuming as
two steps would leave a window where an approval had been approved and not yet
spent, and a crash in that window turns one permission into two attempts.

The write happens before the caller is told yes, so the conservative direction
is chosen deliberately: a crash can leave an approval spent with no execution
behind it, and cannot leave an execution running on an approval still available
to spend again. Duplicate authority is the more dangerous failure, so the
harmless one is the one that stays possible.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.ResearchPlanAuthorizationEvents import ResearchPlanAuthorizationEvents
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.ResearchAuthorizationBudgetChoice import budget_from
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorization import (
    MAX_AUTHORIZATION_VALIDITY_SECONDS,
    ResearchPlanAuthorization,
)
from research.ResearchPlanAuthorizationDecision import (
    ResearchPlanAuthorizationDecision,
)
from research.ResearchPlanAuthorizationPreview import ResearchPlanAuthorizationPreview
from research.ResearchPlanAuthorizationStore import ResearchPlanAuthorizationStore
from research.ResearchPlanAuthorizationVerdict import ResearchPlanAuthorizationVerdict
from research.ResearchPlanAuthorizationVerifier import verify_plan_authorization
from research.ResearchPlanBudgetRequirement import ResearchPlanBudgetFit
from research.ResearchPlanDraftService import (
    ResearchPlanDraftService,
    ResearchPlanStepDraft,
)
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

AUTHORIZATION_PREVIEW_INTENT = "research_plan_authorization_preview"
AUTHORIZATION_CONFIRM_INTENT = "research_plan_authorization_confirm"
AUTHORIZATION_LIST_INTENT = "research_plan_authorization_list"

#: One approval may not outlive the longest single run it could ever permit.
DEFAULT_AUTHORIZATION_VALIDITY_SECONDS = MAX_AUTHORIZATION_VALIDITY_SECONDS

#: Pending previews are process-local and bounded. A preview is something a
#: person is currently looking at, not a queue, so a small number is the honest
#: size — and an unbounded map would be a way to grow memory by pressing one
#: button repeatedly.
MAX_PENDING_AUTHORIZATION_PREVIEWS = 20


class ResearchPlanAuthorizationApplicationService:
    """Preview, confirm, and list approvals. Start nothing."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        authorization_store: ResearchPlanAuthorizationStore | None = None,
        draft_service: ResearchPlanDraftService | None = None,
        event_bus: EventBus | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._authorization_store = authorization_store
        self._draft_service = draft_service or ResearchPlanDraftService()
        self._events = ResearchPlanAuthorizationEvents(event_bus)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._pending: dict[str, ResearchPlanAuthorization] = {}
        self._authorizations: dict[str, ResearchPlanAuthorization] = {}
        self._restore()

    @staticmethod
    def is_preview_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == AUTHORIZATION_PREVIEW_INTENT

    @staticmethod
    def is_confirm_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == AUTHORIZATION_CONFIRM_INTENT

    @staticmethod
    def is_list_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == AUTHORIZATION_LIST_INTENT

    def authorizations(self) -> tuple[ResearchPlanAuthorization, ...]:
        """Return every recorded approval, newest decision last."""
        return tuple(
            sorted(
                self._authorizations.values(),
                key=lambda entry: (entry.authorized_at, entry.authorization_id),
            )
        )

    def process_preview(self, request: BrainRequest) -> BrainResponse:
        """Show the exact approval confirming would record. Write nothing."""
        run_id = self._required_run_id(request)
        plan = self._plan(request)
        if plan is None:
            return self._response_composer.research_plan_authorization_preview(
                request,
                ResearchPlanAuthorizationPreview.rejected(
                    "unavailable",
                    "That research plan is not valid, so nothing can be approved.",
                ),
            )
        if len(self._pending) >= MAX_PENDING_AUTHORIZATION_PREVIEWS:
            return self._response_composer.research_plan_authorization_preview(
                request,
                ResearchPlanAuthorizationPreview.rejected(
                    plan.plan_id,
                    "Too many approvals are already awaiting confirmation.",
                ),
            )
        try:
            chosen = budget_from(request.metadata)
        except ResearchError as error:
            return self._response_composer.research_plan_authorization_preview(
                request,
                ResearchPlanAuthorizationPreview.rejected(plan.plan_id, str(error)),
            )
        fit = self.budget_fit_for(plan, chosen)
        if not fit.sufficient:
            # Refused before anything is built. Nothing is recorded, nothing is
            # spent, and the budget is not quietly raised to fit the plan.
            self._events.refused("insufficient_budget")
            return self._response_composer.research_plan_authorization_preview(
                request,
                ResearchPlanAuthorizationPreview.rejected(
                    plan.plan_id,
                    "The budget on offer does not cover one attempt at every "
                    "authored step, so approving it would promise work it "
                    "cannot pay for.",
                    budget_fit=fit,
                ),
            )
        authorized_at = self._clock()
        authorization = ResearchPlanAuthorization.for_plan(
            authorization_id=self._id_factory(),
            plan=plan,
            research_run_id=run_id,
            budget=fit.budget,
            authorized_at=authorized_at,
            expires_at=authorized_at
            + timedelta(seconds=DEFAULT_AUTHORIZATION_VALIDITY_SECONDS),
            disclosure=self._disclosure(request),
        )
        self._pending[authorization.authorization_id] = authorization
        self._events.previewed(authorization)
        return self._response_composer.research_plan_authorization_preview(
            request,
            ResearchPlanAuthorizationPreview.ready(
                plan.plan_id,
                authorization,
                # Named here rather than left inside the digest bytes. A person
                # approving a plan has to be able to see which host it will
                # contact; a digest they cannot read is not disclosure.
                tuple(
                    dict.fromkeys(
                        step.discovery_provider
                        for step in plan.steps
                        if step.discovery_provider is not None
                    )
                ),
            ),
        )

    def authorization_for_execution(
        self,
        execution_id: str,
    ) -> ResearchPlanAuthorization | None:
        """Return the approval spent on this exact execution, or nothing.

        An exact identity match on the recorded consumption. Nothing here
        un-spends anything; the approval comes back consumed, which is the only
        honest thing it could be.
        """
        wanted = execution_id.strip()
        if not wanted:
            return None
        for authorization in self._authorizations.values():
            consumption = authorization.consumption
            if consumption is not None and consumption.execution_id == wanted:
                return authorization
        return None

    def budget_fit_for(
        self,
        plan: ResearchPlan,
        budget: ResearchAutonomyBudget | None = None,
    ) -> ResearchPlanBudgetFit:
        """Return what this plan would cost against the budget being granted.

        The budget is the one somebody is offering, defaulting to the standing
        one when nobody chose. It is never derived from the plan: knowing what a
        plan needs does not become permission to have it, and that stays a
        decision a person makes by approving or not.
        """
        return ResearchPlanBudgetFit.of(plan, budget or ResearchAutonomyBudget())

    def record_for_plan(
        self,
        plan: ResearchPlan,
        research_run_id: str,
        disclosure: ResearchDisclosure = ResearchDisclosure.NONE,
        budget: ResearchAutonomyBudget | None = None,
    ) -> ResearchPlanAuthorization | None:
        """Record one human approval of an already-canonical plan.

        A port for callers that derive the plan themselves rather than carrying
        it in a request. The approval is built by the same constructor, gets the
        same identity, budget, expiry and store, and is announced on the same
        event as any other, so there is exactly one kind of approval in this
        system and one place it is written.

        What this does not do is decide anything. The caller has already
        established that a person asked for this exact plan; the checks that
        matter to *them* — whose question it was, whether it is still current,
        whether the digest is the one they were shown — belong where that
        context lives, not here.

        Returns None when the approval could not be made durable, so a caller
        never reports an approval that only ever existed in memory.
        """
        fit = self.budget_fit_for(plan, budget)
        if not fit.sufficient:
            self._events.refused("insufficient_budget")
            raise ResearchError(
                "The approved budget does not cover one attempt at every "
                "authored step of this plan, so it was not approved. "
                + " ".join(fit.lines()[1:])
            )
        authorized_at = self._clock()
        authorization = ResearchPlanAuthorization.for_plan(
            authorization_id=self._id_factory(),
            plan=plan,
            research_run_id=research_run_id,
            budget=fit.budget,
            authorized_at=authorized_at,
            expires_at=authorized_at
            + timedelta(seconds=DEFAULT_AUTHORIZATION_VALIDITY_SECONDS),
            disclosure=disclosure,
        )
        if authorization.authorization_id in self._authorizations:
            self._events.refused("duplicate_identity")
            return None
        self._authorizations[authorization.authorization_id] = authorization
        if not self._persist():
            self._events.confirmed(
                authorization,
                len(self._authorizations),
                False,
            )
            return None
        self._events.confirmed(authorization, len(self._authorizations), True)
        return authorization

    def process_confirm(self, request: BrainRequest) -> BrainResponse:
        """Record exactly the previewed approval, or refuse and record nothing."""
        authorization_id = self._required_text(
            request,
            "authorization_id",
            "authorization ID",
        )
        authorization = self._pending.get(authorization_id)
        if authorization is None:
            self._events.refused("unknown_preview")
            return self._response_composer.research_plan_authorization_rejected(
                request,
                "No previewed approval with that identity is awaiting confirmation.",
            )
        run_id = self._required_run_id(request)
        plan = self._plan(request)
        if plan is None:
            self._events.refused("invalid_plan")
            return self._response_composer.research_plan_authorization_rejected(
                request,
                "That research plan is no longer valid, so it cannot be approved.",
            )
        verdict = verify_plan_authorization(
            authorization,
            plan,
            run_id,
            self._clock(),
        )
        if verdict is not ResearchPlanAuthorizationVerdict.VALID:
            # The preview is discarded rather than kept for a second attempt.
            # A preview whose subject changed describes work nobody looked at.
            self._pending.pop(authorization_id, None)
            self._events.refused(verdict.value)
            return self._response_composer.research_plan_authorization_refused(
                request,
                verdict,
            )
        self._pending.pop(authorization_id, None)
        if authorization.authorization_id in self._authorizations:
            self._events.refused("duplicate_identity")
            return self._response_composer.research_plan_authorization_rejected(
                request,
                "An approval with that identity is already recorded.",
            )
        self._authorizations[authorization.authorization_id] = authorization
        persisted = self._persist()
        self._events.confirmed(
            authorization,
            len(self._authorizations),
            persisted,
        )
        if not persisted:
            return self._response_composer.research_plan_authorization_write_failed(
                request,
                authorization,
            )
        return self._response_composer.research_plan_authorization_confirmed(
            request,
            authorization,
        )

    def process_list(self, request: BrainRequest) -> BrainResponse:
        """Report recorded approvals and whether each is still valid."""
        return self._response_composer.research_plan_authorization_list(
            request,
            self.authorizations(),
            self._clock(),
        )

    def consume_for_execution(
        self,
        authorization_id: str,
        plan: ResearchPlan,
        research_run_id: str,
        execution_id: str,
        moment: datetime,
        *,
        budget: ResearchAutonomyBudget | None = None,
        disclosure: ResearchDisclosure | None = None,
    ) -> ResearchPlanAuthorizationDecision:
        """Spend one approval on one execution, or refuse and spend nothing.

        Ordering is the whole safety property. Everything is checked first,
        then the spent record is written, and only a successful write produces
        a permitting answer. A caller therefore cannot be told yes on the
        strength of a consumption that exists only in this process.
        """
        recorded = self._authorizations.get(authorization_id.strip())
        if recorded is None:
            return self._refuse(ResearchPlanAuthorizationVerdict.UNKNOWN)
        verdict = verify_plan_authorization(recorded, plan, research_run_id, moment)
        if verdict is not ResearchPlanAuthorizationVerdict.VALID:
            return self._refuse(verdict)
        if budget is not None and not _within(budget, recorded.budget):
            return self._refuse(ResearchPlanAuthorizationVerdict.BUDGET_EXCEEDED)
        if disclosure is not None and not _permitted_disclosure(
            disclosure,
            recorded.disclosure,
        ):
            return self._refuse(ResearchPlanAuthorizationVerdict.DISCLOSURE_UNSATISFIED)

        spent = recorded.consumed_for(execution_id, moment)
        previous = self._authorizations[recorded.authorization_id]
        self._authorizations[recorded.authorization_id] = spent
        self._events.consumption_attempted(spent)
        if not self._persist():
            # Fail closed. An approval that could not be written as spent is an
            # approval that would still be available after a restart, so the
            # in-process change is rolled back and nothing is permitted.
            self._authorizations[recorded.authorization_id] = previous
            return self._refuse(ResearchPlanAuthorizationVerdict.NOT_RECORDED)
        self._events.consumed(spent)
        return ResearchPlanAuthorizationDecision.permitted(spent)

    def _refuse(
        self,
        verdict: ResearchPlanAuthorizationVerdict,
    ) -> ResearchPlanAuthorizationDecision:
        self._events.consumption_refused(verdict.value)
        return ResearchPlanAuthorizationDecision.refused(verdict)

    def _plan(self, request: BrainRequest) -> ResearchPlan | None:
        """Rebuild the exact plan from the authored draft, or refuse it."""
        question = request.metadata.get("research_plan_question")
        step_drafts = request.metadata.get("research_plan_steps")
        preview = self._draft_service.preview(
            cast(str, question),
            cast(tuple[ResearchPlanStepDraft, ...], step_drafts),
        )
        return preview.plan if preview.allowed else None

    def _required_run_id(self, request: BrainRequest) -> str:
        """Require a run that actually exists, not merely a plausible ID."""
        run_id = self._required_text(request, "research_run_id", "run ID")
        return self._run_manager.get(run_id).run_id

    @staticmethod
    def _disclosure(request: BrainRequest) -> ResearchDisclosure:
        """Read the bounded disclosure decision, defaulting to none."""
        value = request.metadata.get("research_disclosure")
        if value is None:
            return ResearchDisclosure.NONE
        if isinstance(value, ResearchDisclosure):
            return value
        if not isinstance(value, str):
            raise ResearchError("That model-disclosure decision is not recognised.")
        try:
            return ResearchDisclosure(value)
        except ValueError as error:
            raise ResearchError(
                "That model-disclosure decision is not recognised."
            ) from error

    @staticmethod
    def _required_text(request: BrainRequest, key: str, label: str) -> str:
        value = request.metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"Research plan approval requires a {label}.")
        return value.strip()

    def _restore(self) -> None:
        """Load recorded approvals exactly as written, renewing nothing."""
        if self._authorization_store is None:
            return
        for authorization in self._authorization_store.load():
            self._authorizations[authorization.authorization_id] = authorization

    def _persist(self) -> bool:
        """Write approvals, reporting rather than swallowing a failed write."""
        if self._authorization_store is None:
            return True
        try:
            self._authorization_store.save(list(self._authorizations.values()))
        except ResearchError:
            return False
        return True


def _within(
    requested: ResearchAutonomyBudget,
    authorized: ResearchAutonomyBudget,
) -> bool:
    """Return whether every requested bound stays inside the approved one.

    Component-wise, never by union and never by total. A request that asked for
    fewer network calls and more model calls than approved has still asked for
    something nobody approved.
    """
    return (
        requested.max_step_advances <= authorized.max_step_advances
        and requested.max_network_operations <= authorized.max_network_operations
        and requested.max_llm_operations <= authorized.max_llm_operations
        and requested.max_seconds <= authorized.max_seconds
    )


def _permitted_disclosure(
    requested: ResearchDisclosure,
    authorized: ResearchDisclosure,
) -> bool:
    """Return whether the approved disclosure covers what is being asked for.

    Ordered rather than compared for equality, so an execution asking for less
    than was approved is fine and one asking for more never is. Nothing here
    consults the endpoint: an endpoint being local is a fact about deployment,
    not a decision anybody made about disclosure.
    """
    ranking = {
        ResearchDisclosure.NONE: 0,
        ResearchDisclosure.LOCAL_ONLY: 1,
        ResearchDisclosure.REMOTE_PERMITTED: 2,
    }
    return ranking[requested] <= ranking[authorized]
