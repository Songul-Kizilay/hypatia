"""Propose hypotheses, enter evidence on either side, and never conclude.

There is no confirm intent, and its absence is the design. Propose, support,
oppose, withdraw, and list are the whole vocabulary: a system that could mark a
hypothesis confirmed would be asked to, and once something is filed as confirmed
nobody goes looking for the observation that would have undone it.

Every hypothesis must name that observation before any evidence exists — while
it is still cheap to be honest about what would change your mind. Evidence must
already be recorded in the run, so nothing can be supported by a passage nobody
read, and the same evidence cannot be entered on both sides.

Supporting and opposing evidence are never netted. Both counts are reported
separately, because which side wins is a judgement someone makes after reading
both, and this service exists to keep both visible when they do.

Positive support also carries the active authored source-trust coverage into
the appraisal. The appraiser will not call a hypothesis supported until more
than one independent source is present and every supporting source is assessed
at medium trust or better. This is an evidence boundary, never a truth claim.

Durable-write failure never masquerades as success. The changed hypothesis is
kept in this process and returned with an unsuccessful response that warns about
restart loss; store paths and exception text never enter the response.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.HypothesisEvents import HypothesisEvents
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.HypothesisAppraisal import HypothesisAppraisal
from research.HypothesisStore import HypothesisStore
from research.JsonFileHypothesisStore import MAX_HYPOTHESIS_STORE_ENTRIES
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchHypothesisAppraiser import ResearchHypothesisAppraiser
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

HYPOTHESIS_PROPOSE_INTENT = "research_hypothesis_propose"
HYPOTHESIS_SUPPORT_INTENT = "research_hypothesis_support"
HYPOTHESIS_OPPOSE_INTENT = "research_hypothesis_oppose"
HYPOTHESIS_WITHDRAW_INTENT = "research_hypothesis_withdraw"
HYPOTHESIS_LIST_INTENT = "research_hypothesis_list"


class HypothesisApplicationService:
    """Manage authored hypotheses without ever settling one."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        appraiser: ResearchHypothesisAppraiser | None = None,
        hypothesis_store: HypothesisStore | None = None,
        event_bus: EventBus | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._appraiser = appraiser or ResearchHypothesisAppraiser()
        self._hypothesis_store = hypothesis_store
        self._events = HypothesisEvents(event_bus)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: f"hypothesis-{uuid4()}")
        self._hypotheses: dict[str, ResearchHypothesis] = {}
        self._restore()

    @staticmethod
    def is_propose_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == HYPOTHESIS_PROPOSE_INTENT

    @staticmethod
    def is_support_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == HYPOTHESIS_SUPPORT_INTENT

    @staticmethod
    def is_oppose_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == HYPOTHESIS_OPPOSE_INTENT

    @staticmethod
    def is_withdraw_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == HYPOTHESIS_WITHDRAW_INTENT

    @staticmethod
    def is_list_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == HYPOTHESIS_LIST_INTENT

    def hypotheses(self) -> tuple[ResearchHypothesis, ...]:
        """Return every known hypothesis in stable creation order."""
        return tuple(
            sorted(
                self._hypotheses.values(),
                key=lambda entry: (entry.created_at, entry.hypothesis_id),
            )
        )

    def process_propose(self, request: BrainRequest) -> BrainResponse:
        """Record one conjecture together with what would count against it."""
        run = self._run(request)
        statement = self._required_text(request, "hypothesis_statement", "statement")
        test = self._required_text(
            request,
            "hypothesis_discriminating_test",
            "discriminating test",
        )
        if len(self._hypotheses) >= MAX_HYPOTHESIS_STORE_ENTRIES:
            return self._response_composer.hypothesis_rejected(
                request,
                "Hypothesis capacity is full.",
            )
        hypothesis_id = self._id_factory()
        if hypothesis_id in self._hypotheses:
            raise ResearchError("A hypothesis with that identifier already exists.")
        now = self._clock()
        hypothesis = ResearchHypothesis(
            hypothesis_id=hypothesis_id,
            run_id=run.run_id,
            statement=statement,
            discriminating_test=test,
            created_at=now,
            updated_at=now,
        )
        self._hypotheses[hypothesis.hypothesis_id] = hypothesis
        appraisal = self._appraiser.appraise(hypothesis, run)
        self._events.proposed(appraisal)
        return self._response_after_persist(request, appraisal)

    def process_support(self, request: BrainRequest) -> BrainResponse:
        return self._enter_evidence(request, supporting=True)

    def process_oppose(self, request: BrainRequest) -> BrainResponse:
        return self._enter_evidence(request, supporting=False)

    def process_withdraw(self, request: BrainRequest) -> BrainResponse:
        """Stop working on one hypothesis without deleting what it recorded."""
        run, hypothesis = self._existing(request)
        updated = hypothesis.withdrawn_at(self._clock())
        self._hypotheses[updated.hypothesis_id] = updated
        appraisal = self._appraiser.appraise(updated, run)
        self._events.withdrawn(appraisal)
        return self._response_after_persist(request, appraisal)

    def process_list(self, request: BrainRequest) -> BrainResponse:
        """Report every hypothesis with its derived standing."""
        appraisals: list[HypothesisAppraisal] = []
        for hypothesis in self.hypotheses():
            try:
                run = self._run_manager.get(hypothesis.run_id)
            except ResearchError:
                continue
            appraisals.append(self._appraiser.appraise(hypothesis, run))
        return self._response_composer.hypothesis_list(request, tuple(appraisals))

    def _enter_evidence(
        self,
        request: BrainRequest,
        *,
        supporting: bool,
    ) -> BrainResponse:
        """Attach recorded evidence to one side, never to both."""
        run, hypothesis = self._existing(request)
        evidence_ids = self._evidence_ids(request, run)
        now = self._clock()
        updated = (
            hypothesis.supported_by(evidence_ids, now)
            if supporting
            else hypothesis.opposed_by(evidence_ids, now)
        )
        self._hypotheses[updated.hypothesis_id] = updated
        appraisal = self._appraiser.appraise(updated, run)
        self._events.evidence_entered(appraisal, supporting)
        return self._response_after_persist(request, appraisal)

    def _response_after_persist(
        self,
        request: BrainRequest,
        appraisal: HypothesisAppraisal,
    ) -> BrainResponse:
        """Report the in-memory change honestly when its durable write fails."""
        if not self._persist():
            return self._response_composer.hypothesis_persistence_failed(
                request,
                appraisal,
            )
        return self._response_composer.hypothesis_appraisal(request, appraisal)

    def _existing(
        self,
        request: BrainRequest,
    ) -> tuple[ResearchRun, ResearchHypothesis]:
        hypothesis_id = self._required_text(request, "hypothesis_id", "ID")
        hypothesis = self._hypotheses.get(hypothesis_id)
        if hypothesis is None:
            raise ResearchError("No hypothesis with that identifier is known.")
        return self._run_manager.get(hypothesis.run_id), hypothesis

    def _run(self, request: BrainRequest) -> ResearchRun:
        run_id = self._required_text(request, "research_run_id", "run ID")
        return self._run_manager.get(run_id)

    @staticmethod
    def _evidence_ids(request: BrainRequest, run: ResearchRun) -> tuple[str, ...]:
        """Require evidence that the run actually recorded."""
        value = request.metadata.get("evidence_ids")
        if not isinstance(value, (list, tuple)) or not value:
            raise ResearchError("At least one evidence ID is required.")
        if not all(isinstance(entry, str) and entry.strip() for entry in value):
            raise ResearchError("An evidence ID cannot be empty.")
        recorded = {record.evidence_id for record in run.evidence}
        requested = tuple(entry.strip() for entry in value)
        missing = [entry for entry in requested if entry not in recorded]
        if missing:
            raise ResearchError(
                "Hypothesis evidence must already be recorded in this run."
            )
        return requested

    @staticmethod
    def _required_text(request: BrainRequest, key: str, label: str) -> str:
        value = request.metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"Hypothesis {label} cannot be empty.")
        return value.strip()

    def _restore(self) -> None:
        if self._hypothesis_store is None:
            return
        for hypothesis in self._hypothesis_store.load():
            self._hypotheses[hypothesis.hypothesis_id] = hypothesis

    def _persist(self) -> bool:
        """Write hypotheses, never erasing them silently on failure."""
        if self._hypothesis_store is None:
            return True
        try:
            self._hypothesis_store.save(list(self._hypotheses.values()))
        except ResearchError:
            return False
        return True
