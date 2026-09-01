"""One approval may authorize one attempt. It must never become ambient.

A plan may now start, and only because one exact human approval for that exact
plan and run was valid at the moment it began — and that approval is spent by
starting, once and permanently.

The ordering is the safety property and most of these tests are about it.
Everything is checked, then the approval is durably written as spent, and only a
successful write produces a runnable execution. The handoff is not atomic: the
approval store and the execution store are separate files with no transaction
across them. The direction of that gap is chosen deliberately, and asserted
below — a crash can leave an approval spent with no execution, and cannot leave
an execution running on an approval still available to spend again.
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
from brain.BrainResponse import BrainResponse
from cognition.ResearchPlanAuthorizationApplicationService import (
    ResearchPlanAuthorizationApplicationService,
)
from cognition.ResearchPlanExecutionApplicationService import (
    ResearchPlanExecutionApplicationService,
)
from core.Exceptions import ResearchError
from eventbus.Event import Event
from eventbus.EventBus import EventBus
from research.JsonFileResearchPlanAuthorizationStore import (
    JsonFileResearchPlanAuthorizationStore,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchPlanAuthorizationVerdict import ResearchPlanAuthorizationVerdict
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer
from tests.SourceVocabulary import mentions, working_vocabulary

QUESTION = "Does the Saturn ring system have a measured age?"
STEPS: tuple[tuple[object, ...], ...] = (
    ("Search the local knowledge base.", (), "local_knowledge_search"),
)
EDITED_STEPS: tuple[tuple[object, ...], ...] = (
    ("Search the local knowledge base thoroughly.", (), "local_knowledge_search"),
)
NOW = datetime(2026, 8, 26, 9, 0, tzinfo=UTC)


class StubClock:
    def __init__(self) -> None:
        self.moment = NOW

    def __call__(self) -> datetime:
        return self.moment


class FailingAuthorizationStore:
    """Refuses to write, so failing closed on consumption can be tested."""

    def __init__(self, records: list[object] | None = None) -> None:
        self.records = records or []

    def load(self) -> list[object]:
        return list(self.records)

    def save(self, authorizations: list[object]) -> None:
        raise ResearchError("PRIVATE-APPROVAL-PATH is unwritable.")


class AuthorizedStartFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.store_path = self.root / "authorizations.json"
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(self.root / "runs.json")
        )
        self.manager.load()
        self.run_id = self.manager.create(QUESTION).run_id
        self.clock = StubClock()
        self.event_bus = EventBus()
        self.events: list[Event] = []
        self.event_bus.subscribe("*", self.events.append)
        self.identities = iter(f"approval-{index}" for index in range(1, 100))
        self.approvals = self.authorization_service()
        self.addCleanup(self.temporary_directory.cleanup)

    def store(self) -> JsonFileResearchPlanAuthorizationStore:
        return JsonFileResearchPlanAuthorizationStore(self.store_path)

    def authorization_service(
        self,
        authorization_store: object | None = None,
    ) -> ResearchPlanAuthorizationApplicationService:
        return ResearchPlanAuthorizationApplicationService(
            self.manager,
            ResponseComposer(),
            authorization_store=(
                authorization_store if authorization_store is not None else self.store()
            ),  # type: ignore[arg-type]
            event_bus=self.event_bus,
            clock=self.clock,
            id_factory=lambda: next(self.identities),
        )

    def execution_service(
        self,
        consumer: object | None = None,
        plan_ids: list[str] | None = None,
    ) -> ResearchPlanExecutionApplicationService:
        names = iter(plan_ids or [f"execution-{index}" for index in range(1, 100)])
        return ResearchPlanExecutionApplicationService(
            ResponseComposer(),
            event_bus=self.event_bus,
            clock=self.clock,
            authorization_consumer=(
                consumer if consumer is not None else self.approvals
            ),  # type: ignore[arg-type]
            draft_service=ResearchPlanDraftService(
                clock=lambda: self.clock.moment,
                id_factory=lambda: next(names),
            ),
        )

    def request(self, intent: str, **metadata: object) -> BrainRequest:
        return BrainRequest(
            message="Authorized execution",
            metadata={"intent": intent, **metadata},
        )

    def approve(
        self,
        steps: tuple[tuple[object, ...], ...] = STEPS,
        disclosure: str = "none",
    ) -> str:
        previewed = self.approvals.process_preview(
            self.request(
                "research_plan_authorization_preview",
                research_run_id=self.run_id,
                research_plan_question=QUESTION,
                research_plan_steps=steps,
                research_disclosure=disclosure,
            )
        )
        assert previewed.research_plan_authorization is not None
        identity = previewed.research_plan_authorization.authorization_id
        confirmed = self.approvals.process_confirm(
            self.request(
                "research_plan_authorization_confirm",
                authorization_id=identity,
                research_run_id=self.run_id,
                research_plan_question=QUESTION,
                research_plan_steps=steps,
            )
        )
        assert confirmed.success, confirmed.message
        return identity

    def start(
        self,
        execution: ResearchPlanExecutionApplicationService,
        authorization_id: str | None = None,
        steps: tuple[tuple[object, ...], ...] = STEPS,
        run_id: str | None = None,
    ) -> BrainResponse:
        metadata: dict[str, object] = {
            "research_plan_question": QUESTION,
            "research_plan_steps": steps,
        }
        if authorization_id is not None:
            metadata["authorization_id"] = authorization_id
        chosen_run = self.run_id if run_id is None else run_id
        if chosen_run:
            metadata["research_run_id"] = chosen_run
        return execution.process_start(
            self.request("research_plan_execution_start", **metadata)
        )

    def recorded(self, authorization_id: str) -> object:
        return {
            entry.authorization_id: entry for entry in self.approvals.authorizations()
        }[authorization_id]


class AuthorizationRequiredTests(AuthorizedStartFixture):
    def test_an_exact_valid_approval_starts_one_execution(self) -> None:
        execution = self.execution_service()

        response = self.start(execution, self.approve())

        self.assertTrue(response.success)
        self.assertIs(
            response.research_plan_execution.status,
            ResearchPlanExecutionStatus.RUNNING,
        )

    def test_a_start_naming_no_approval_is_refused(self) -> None:
        execution = self.execution_service()
        self.approve()

        response = self.start(execution, authorization_id=None)

        self.assertFalse(response.success)
        self.assertIn("unknown", response.message)
        self.assertIsNone(response.research_plan_execution)

    def test_an_unknown_approval_is_refused(self) -> None:
        execution = self.execution_service()

        response = self.start(execution, "approval-never-given")

        self.assertFalse(response.success)
        self.assertIn("unknown", response.message)

    def test_an_edited_plan_is_refused(self) -> None:
        execution = self.execution_service()
        identity = self.approve()

        response = self.start(execution, identity, steps=EDITED_STEPS)

        self.assertFalse(response.success)
        self.assertIn("digest_mismatch", response.message)

    def test_a_changed_authorized_source_url_is_refused(self) -> None:
        approved = (("Load the source.", (), "source_fetch", "https://example.test/a"),)
        changed = (("Load the source.", (), "source_fetch", "https://example.test/b"),)
        identity = self.approve(steps=approved)
        execution = self.execution_service()

        response = self.start(execution, identity, steps=changed)

        self.assertFalse(response.success)
        self.assertIn("digest_mismatch", response.message)

    def test_a_changed_selected_source_is_refused(self) -> None:
        approved = (("Read it.", ("document-1",), "none"),)
        changed = (("Read it.", ("document-2",), "none"),)
        identity = self.approve(steps=approved)
        execution = self.execution_service()

        response = self.start(execution, identity, steps=changed)

        self.assertFalse(response.success)
        self.assertIn("digest_mismatch", response.message)

    def test_another_run_is_refused(self) -> None:
        identity = self.approve()
        other_run = self.manager.create("A different question?").run_id
        execution = self.execution_service()

        response = self.start(execution, identity, run_id=other_run)

        self.assertFalse(response.success)
        self.assertIn("run_mismatch", response.message)

    def test_a_start_naming_no_run_is_refused(self) -> None:
        """An approval names a run, so a start naming none can never match."""
        identity = self.approve()
        execution = self.execution_service()

        response = self.start(execution, identity, run_id="")

        self.assertFalse(response.success)
        self.assertIn("unknown", response.message)

    def test_an_expired_approval_is_refused(self) -> None:
        identity = self.approve()
        execution = self.execution_service()
        self.clock.moment = NOW + timedelta(hours=2)

        response = self.start(execution, identity)

        self.assertFalse(response.success)
        self.assertIn("expired", response.message)

    def test_a_refusal_creates_no_execution_and_spends_nothing(self) -> None:
        identity = self.approve()
        execution = self.execution_service()
        before = self.store_path.read_bytes()

        self.start(execution, identity, steps=EDITED_STEPS)

        self.assertEqual(execution.live_execution("execution-1"), None)
        self.assertEqual(self.store_path.read_bytes(), before)
        self.assertFalse(self.recorded(identity).is_consumed)  # type: ignore[attr-defined]

    def test_a_refusal_is_not_reached_rather_than_failed(self) -> None:
        execution = self.execution_service()

        response = self.start(execution, "approval-never-given")

        self.assertIn("not reached", response.message)
        self.assertNotIn("failed", response.message.casefold())


class SingleUseTests(AuthorizedStartFixture):
    def test_starting_spends_the_approval_exactly_once(self) -> None:
        identity = self.approve()
        execution = self.execution_service()

        self.start(execution, identity)
        spent = self.recorded(identity)

        self.assertTrue(spent.is_consumed)  # type: ignore[attr-defined]
        self.assertEqual(
            spent.consumption.execution_id,  # type: ignore[attr-defined]
            "execution-1",
        )
        self.assertEqual(spent.consumption.consumed_at, NOW)  # type: ignore[attr-defined]

    def test_one_approval_cannot_start_two_executions(self) -> None:
        identity = self.approve()
        execution = self.execution_service()

        first = self.start(execution, identity)
        second = self.start(execution, identity)

        self.assertTrue(first.success)
        self.assertFalse(second.success)
        self.assertIn("already_consumed", second.message)

    def test_a_spent_approval_stays_spent_across_a_restart(self) -> None:
        identity = self.approve()
        self.start(self.execution_service(), identity)

        reloaded = self.authorization_service()
        spent = [
            entry
            for entry in reloaded.authorizations()
            if entry.authorization_id == identity
        ][0]

        self.assertTrue(spent.is_consumed)
        self.assertEqual(spent.consumption is None, False)
        self.assertEqual(spent.consumption.execution_id, "execution-1")  # type: ignore[union-attr]

    def test_a_reloaded_spent_approval_cannot_start_anything(self) -> None:
        identity = self.approve()
        self.start(self.execution_service(), identity)
        reloaded = self.authorization_service()

        response = self.start(
            self.execution_service(consumer=reloaded, plan_ids=["execution-9"]),
            identity,
        )

        self.assertFalse(response.success)
        self.assertIn("already_consumed", response.message)

    def test_consumption_is_monotonic(self) -> None:
        identity = self.approve()
        self.start(self.execution_service(), identity)
        spent = self.recorded(identity)

        with self.assertRaises(ResearchError):
            spent.consumed_for("execution-2", NOW)  # type: ignore[attr-defined]

    def test_a_cancelled_execution_does_not_refund_the_approval(self) -> None:
        identity = self.approve()
        execution = self.execution_service()
        self.start(execution, identity)

        execution.process_cancel(
            self.request(
                "research_plan_execution_cancel",
                research_plan_id="execution-1",
            )
        )

        self.assertTrue(self.recorded(identity).is_consumed)  # type: ignore[attr-defined]

    def test_listing_reports_consumption_truthfully(self) -> None:
        identity = self.approve()
        listed_before = self.approvals.process_list(
            self.request("research_plan_authorization_list")
        )
        self.start(self.execution_service(), identity)
        listed_after = self.approvals.process_list(
            self.request("research_plan_authorization_list")
        )

        self.assertIn("unused", listed_before.message)
        self.assertIn("used by execution-1", listed_after.message)


class ConsumptionOrderingTests(AuthorizedStartFixture):
    """The handoff is not atomic. Its direction is deliberate."""

    def test_a_failed_consumption_write_prevents_the_start(self) -> None:
        identity = self.approve()
        loaded = self.store().load()
        failing = self.authorization_service(
            authorization_store=FailingAuthorizationStore(list(loaded))
        )
        execution = self.execution_service(consumer=failing)

        response = self.start(execution, identity)

        self.assertFalse(response.success)
        self.assertIn("not_recorded", response.message)
        self.assertIsNone(response.research_plan_execution)

    def test_a_failed_consumption_write_leaves_no_session_only_spend(self) -> None:
        """A spend that exists only in memory would be available again later."""
        identity = self.approve()
        loaded = self.store().load()
        failing = self.authorization_service(
            authorization_store=FailingAuthorizationStore(list(loaded))
        )
        execution = self.execution_service(consumer=failing)

        self.start(execution, identity)
        remaining = [
            entry
            for entry in failing.authorizations()
            if entry.authorization_id == identity
        ][0]

        self.assertFalse(remaining.is_consumed)

    def test_no_runnable_execution_exists_without_a_spent_approval(self) -> None:
        """The property that matters, checked over every refusal path."""
        execution = self.execution_service()
        identity = self.approve()

        for label, response in (
            ("unknown", self.start(execution, "approval-nope")),
            ("edited", self.start(execution, identity, steps=EDITED_STEPS)),
            ("no run", self.start(execution, identity, run_id="")),
        ):
            with self.subTest(case=label):
                self.assertFalse(response.success)
                self.assertIsNone(response.research_plan_execution)
        self.assertFalse(self.recorded(identity).is_consumed)  # type: ignore[attr-defined]

    def test_the_approval_is_spent_before_execution_state_exists(self) -> None:
        """Ordering, observed rather than argued.

        The consumed event must precede the started event. If starting came
        first, a crash between them would leave a runnable execution whose
        approval was still available to spend again.
        """
        identity = self.approve()
        execution = self.execution_service()

        self.start(execution, identity)

        names = [event.name for event in self.events]
        self.assertLess(
            names.index("research_plan_authorization.consumed"),
            names.index("research.plan.execution.started"),
        )


class BudgetAndDisclosureTests(AuthorizedStartFixture):
    """Both are recorded upper bounds. Neither may be exceeded."""

    def consume(
        self,
        identity: str,
        budget: ResearchAutonomyBudget | None = None,
        disclosure: ResearchDisclosure | None = None,
    ) -> ResearchPlanAuthorizationVerdict:
        preview = ResearchPlanDraftService(
            clock=lambda: NOW,
            id_factory=lambda: "execution-x",
        ).preview(QUESTION, STEPS)
        assert preview.plan is not None
        return self.approvals.consume_for_execution(
            identity,
            preview.plan,
            self.run_id,
            "execution-x",
            NOW,
            budget=budget,
            disclosure=disclosure,
        ).verdict

    def test_an_equal_budget_is_accepted(self) -> None:
        verdict = self.consume(self.approve(), budget=ResearchAutonomyBudget())

        self.assertIs(verdict, ResearchPlanAuthorizationVerdict.VALID)

    def test_a_narrower_budget_is_accepted(self) -> None:
        verdict = self.consume(
            self.approve(),
            budget=ResearchAutonomyBudget(
                max_step_advances=1,
                max_network_operations=0,
                max_llm_operations=0,
                max_seconds=5.0,
            ),
        )

        self.assertIs(verdict, ResearchPlanAuthorizationVerdict.VALID)

    def test_any_wider_budget_component_is_refused(self) -> None:
        default = ResearchAutonomyBudget()
        wider = (
            ResearchAutonomyBudget(max_step_advances=default.max_step_advances + 1),
            ResearchAutonomyBudget(
                max_network_operations=default.max_network_operations + 1
            ),
            ResearchAutonomyBudget(max_llm_operations=1),
            ResearchAutonomyBudget(max_seconds=default.max_seconds + 1),
        )

        for budget in wider:
            with self.subTest(budget=budget):
                identity = self.approve()
                self.assertIs(
                    self.consume(identity, budget=budget),
                    ResearchPlanAuthorizationVerdict.BUDGET_EXCEEDED,
                )

    def test_the_approved_default_still_permits_no_model_call(self) -> None:
        identity = self.approve()

        self.assertEqual(self.recorded(identity).budget.max_llm_operations, 0)  # type: ignore[attr-defined]

    def test_disclosure_none_refuses_any_model_disclosure(self) -> None:
        identity = self.approve(disclosure="none")

        for requested in (
            ResearchDisclosure.LOCAL_ONLY,
            ResearchDisclosure.REMOTE_PERMITTED,
        ):
            with self.subTest(requested=requested):
                self.assertIs(
                    self.consume(self.approve(), disclosure=requested),
                    ResearchPlanAuthorizationVerdict.DISCLOSURE_UNSATISFIED,
                )
        self.assertIs(
            self.consume(identity, disclosure=ResearchDisclosure.NONE),
            ResearchPlanAuthorizationVerdict.VALID,
        )

    def test_local_approval_does_not_permit_remote_disclosure(self) -> None:
        identity = self.approve(disclosure="local_only")

        self.assertIs(
            self.consume(identity, disclosure=ResearchDisclosure.REMOTE_PERMITTED),
            ResearchPlanAuthorizationVerdict.DISCLOSURE_UNSATISFIED,
        )

    def test_remote_approval_permits_less_than_it_approved(self) -> None:
        identity = self.approve(disclosure="remote_permitted")

        self.assertIs(
            self.consume(identity, disclosure=ResearchDisclosure.LOCAL_ONLY),
            ResearchPlanAuthorizationVerdict.VALID,
        )

    def test_starting_requests_neither_budget_nor_disclosure(self) -> None:
        """Starting spends neither, so the surface cannot widen either.

        Read as code rather than as text: the docstring on that method says it
        sends no budget, and a search would fail on the sentence promising the
        absence it is checking.
        """
        source = (SRC_DIR / "desktop" / "DesktopController.py").read_text(
            encoding="utf-8"
        )
        vocabulary = working_vocabulary(source, "start_authorized_execution")

        self.assertEqual(mentions(vocabulary, "budget"), [])
        self.assertEqual(mentions(vocabulary, "disclosure"), [])


class CompositionTests(AuthorizedStartFixture):
    """Enforcement is composed in, so the composition is the security claim."""

    def engine(self, store: object | None) -> object:
        from cognition.CognitiveEngine import CognitiveEngine
        from knowledge.KnowledgeEngine import KnowledgeEngine
        from memory.MemoryManager import MemoryManager
        from planner.Planner import Planner
        from session.SessionManager import SessionManager
        from session.SessionRenameTransactionService import (
            SessionRenameTransactionService,
        )

        document = self.root / "knowledge.md"
        document.write_text("Saturn\n\nSaturn has rings.", encoding="utf-8")
        knowledge_engine = KnowledgeEngine()
        knowledge_engine.load(document)
        event_bus = EventBus()
        memory_manager = MemoryManager(event_bus)
        session_manager = SessionManager(event_bus)
        return CognitiveEngine(
            knowledge_engine,
            memory_manager,
            Planner(),
            event_bus,
            ResponseComposer(),
            session_manager,
            SessionRenameTransactionService(
                session_manager=session_manager,
                memory_manager=memory_manager,
                event_bus=event_bus,
            ),
            research_run_manager=self.manager,
            plan_authorization_store=store,  # type: ignore[arg-type]
        )

    def test_keeping_approvals_makes_starting_require_one(self) -> None:
        engine = self.engine(self.store())

        response = engine.process(  # type: ignore[attr-defined]
            self.request(
                "research_plan_execution_start",
                research_run_id=self.run_id,
                research_plan_question=QUESTION,
                research_plan_steps=STEPS,
            )
        )

        self.assertFalse(response.success)
        self.assertIn("not reached", response.message)

    def test_the_consumer_is_attached_exactly_when_approvals_are_kept(self) -> None:
        """The one condition under which any start control exists."""
        with_store = self.engine(self.store())
        without_store = self.engine(None)

        self.assertIs(
            with_store._research_plan_execution_service._authorization_consumer,  # type: ignore[attr-defined]
            with_store._plan_authorization_service,  # type: ignore[attr-defined]
        )
        self.assertIsNone(
            without_store._research_plan_execution_service._authorization_consumer,  # type: ignore[attr-defined]
        )

    def test_the_start_control_and_the_enforcement_share_one_opt_in(self) -> None:
        """Reachable and enforced are gated by the same flag, not two."""
        entry = (SRC_DIR / "desktop_main.py").read_text(encoding="utf-8")
        bootstrap = (SRC_DIR / "core" / "Bootstrap.py").read_text(encoding="utf-8")

        self.assertIn("plan_authorization_enabled=plan_authorization_enabled", entry)
        self.assertIn("if not plan_authorization_enabled(os.environ):", bootstrap)


class BoundaryTests(AuthorizedStartFixture):
    #: The queue intents left this list in v0.3.278, when the operator got
    #: controls for them. They never belonged to it on their own merits: what
    #: this guards is research running without anybody asking each time, and
    #: creating, listing, pausing, resuming and cancelling a queued task reach
    #: no provider at all. Only two things run research — the autonomy run
    #: below, which stays unreachable, and the worker cycle, which is one press
    #: for one turn.
    AUTONOMY_INTENTS = ("research_autonomy_run",)

    def desktop_source(self) -> str:
        return "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((SRC_DIR / "desktop").rglob("*.py"))
            if "__pycache__" not in str(path)
        )

    def test_only_operator_driven_execution_became_reachable(self) -> None:
        """Every reachable execution intent is something a person has to press.

        This narrowed as each milestone earned it: first nothing was reachable,
        then start alone once it cost an approval, and now the three controls
        that let a person watch, step, and stop what they started. What has
        never crossed is anything that would advance research without being
        asked each time.
        """
        source = self.desktop_source()

        for intent in (
            "research_plan_execution_start",
            "research_plan_execution_status",
            "research_plan_execution_advance",
            "research_plan_execution_cancel",
            # One turn of the existing scheduler, asked for each time. It
            # advances nothing on its own: no timer, no recurrence, and no
            # second cycle without a second press.
            "background_research_worker_cycle",
            # The queue the cycle turns. Each of these is a press, none of them
            # reaches a provider, and none can start the cycle.
            "background_research_task_create",
            "background_research_task_list",
            "background_research_task_pause",
            "background_research_task_resume",
            "background_research_task_cancel",
        ):
            with self.subTest(reachable=intent):
                self.assertIn(intent, source)
        for intent in self.AUTONOMY_INTENTS:
            with self.subTest(unreachable=intent):
                self.assertNotIn(intent, source)

    def test_one_execution_cannot_start_another(self) -> None:
        """Starting takes a human-supplied approval identity and nothing else."""
        source = (
            SRC_DIR / "cognition" / "ResearchPlanExecutionApplicationService.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("process_preview", source)
        self.assertNotIn("process_confirm", source)
        self.assertNotIn("ResearchPlanAuthorization.for_plan", source)
        self.assertNotIn(".record_for_plan(", source)

    def test_the_scheduler_cannot_reach_an_approval(self) -> None:
        for name in (
            "BackgroundResearchSchedulerApplicationService.py",
            "ResearchAutonomyApplicationService.py",
        ):
            with self.subTest(module=name):
                source = (SRC_DIR / "cognition" / name).read_text(encoding="utf-8")
                self.assertNotIn("Authorization", source)

    def test_no_dangerous_capability_was_added(self) -> None:
        from research.ResearchPlanStepCapability import ResearchPlanStepCapability

        values = {member.value for member in ResearchPlanStepCapability}
        for forbidden in ("filesystem", "shell", "process", "tool", "command"):
            with self.subTest(name=forbidden):
                self.assertEqual([v for v in values if forbidden in v], [])

    def test_research_never_reaches_the_tool_layer(self) -> None:
        offenders = [
            path.name
            for package in ("research", "cognition")
            for path in (SRC_DIR / package).rglob("*.py")
            if "__pycache__" not in str(path)
            and (
                "ToolRuntime" in path.read_text(encoding="utf-8")
                or "ToolExecutionService" in path.read_text(encoding="utf-8")
            )
        ]

        self.assertEqual(offenders, [])

    def test_confirming_an_approval_still_starts_nothing(self) -> None:
        identity = self.approve()

        self.assertFalse(self.recorded(identity).is_consumed)  # type: ignore[attr-defined]
        self.assertEqual(
            [
                event.name
                for event in self.events
                if event.name.startswith("research_plan_execution.")
            ],
            [],
        )

    def test_telemetry_carries_no_plan_or_question_text(self) -> None:
        self.start(self.execution_service(), self.approve())

        for event in self.events:
            if not event.name.startswith("research_plan_authorization."):
                continue
            rendered = repr(event.payload)
            self.assertNotIn(QUESTION, rendered)
            self.assertNotIn("Search the local knowledge base", rendered)


if __name__ == "__main__":
    unittest.main()
