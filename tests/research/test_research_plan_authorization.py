"""An approval must identify exactly what was approved.

Three things are proven here. A plan has a content identity that survives being
previewed twice and changes when anything that would be attempted changes. An
approval binds to that identity, to one run, to one budget, and to a bounded
window. And a pure function answers whether the approval covers this exact plan
right now, without doing anything else at all.

The digest tests carry most of the weight, and the adversarial ones matter more
than the obvious ones: a length-prefixed encoding is only worth having if it is
tested against the inputs that would break a delimited one.

Nothing here executes a plan, queues a task, or reaches any of the eleven
autonomy intents. That is asserted at the end rather than assumed.
"""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

from core.Exceptions import ResearchError
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanAuthorization import (
    MAX_AUTHORIZATION_VALIDITY_SECONDS,
    ResearchPlanAuthorization,
    capabilities_of,
)
from research.ResearchPlanAuthorizationVerdict import (
    ResearchPlanAuthorizationVerdict,
)
from research.ResearchPlanAuthorizationVerifier import verify_plan_authorization
from research.ResearchPlanDigest import (
    UNDIGESTED_PLAN_FIELDS,
    canonical_plan_bytes,
    is_plan_digest,
    plan_digest,
)
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput

QUESTION = "Does the Saturn ring system have a measured age?"
RUN_ID = "run-1"
AUTHORIZED = datetime(2026, 8, 26, 9, 0, tzinfo=UTC)
EXPIRES = AUTHORIZED + timedelta(minutes=30)


class PlanFixture(unittest.TestCase):
    """Build real plans through the real draft service."""

    def plan(
        self,
        question: str = QUESTION,
        steps: tuple[object, ...] | None = None,
        plan_id: str = "plan-1",
        created_at: datetime = AUTHORIZED,
    ) -> ResearchPlan:
        drafts = steps if steps is not None else self.default_steps()
        service = ResearchPlanDraftService(
            clock=lambda: created_at,
            id_factory=lambda: plan_id,
        )
        preview = service.preview(question, drafts)
        assert preview.plan is not None, preview.reason
        return preview.plan

    @staticmethod
    def default_steps() -> tuple[object, ...]:
        return (
            ResearchPlanStepDraftInput(
                instruction="Search the local knowledge base.",
                capability="local_knowledge_search",
            ),
            ResearchPlanStepDraftInput(
                instruction="Find candidate sources.", capability="source_discovery"
            ),
        )

    def authorization(
        self,
        plan: ResearchPlan | None = None,
        **overrides: object,
    ) -> ResearchPlanAuthorization:
        arguments: dict[str, object] = {
            "authorization_id": "authorization-1",
            "plan": plan if plan is not None else self.plan(),
            "research_run_id": RUN_ID,
            "budget": ResearchAutonomyBudget(),
            "authorized_at": AUTHORIZED,
            "expires_at": EXPIRES,
        }
        arguments.update(overrides)
        return ResearchPlanAuthorization.for_plan(**arguments)  # type: ignore[arg-type]


class PlanDigestTests(PlanFixture):
    def test_two_independent_previews_of_one_plan_digest_identically(self) -> None:
        first = self.plan(plan_id="plan-a", created_at=AUTHORIZED)
        second = self.plan(
            plan_id="plan-b",
            created_at=AUTHORIZED + timedelta(days=3),
        )

        self.assertNotEqual(first.plan_id, second.plan_id)
        self.assertNotEqual(first.created_at, second.created_at)
        self.assertEqual(plan_digest(first), plan_digest(second))

    def test_instance_bookkeeping_is_deliberately_outside_the_digest(self) -> None:
        self.assertEqual(UNDIGESTED_PLAN_FIELDS, frozenset({"plan_id", "created_at"}))

    def test_a_digest_is_lowercase_sha256_hex(self) -> None:
        digest = plan_digest(self.plan())

        self.assertTrue(is_plan_digest(digest))
        self.assertEqual(len(digest), 64)

    def test_a_changed_question_changes_the_digest(self) -> None:
        self.assertNotEqual(
            plan_digest(self.plan()),
            plan_digest(self.plan(question="A different question entirely?")),
        )

    def test_a_changed_instruction_changes_the_digest(self) -> None:
        edited = (
            ResearchPlanStepDraftInput(
                instruction="Search the local knowledge base thoroughly.",
                capability="local_knowledge_search",
            ),
            ResearchPlanStepDraftInput(
                instruction="Find candidate sources.", capability="source_discovery"
            ),
        )

        self.assertNotEqual(
            plan_digest(self.plan()), plan_digest(self.plan(steps=edited))
        )

    def test_a_changed_capability_changes_the_digest(self) -> None:
        """The capability is what a step may actually do."""
        widened = (
            ResearchPlanStepDraftInput(
                instruction="Search the local knowledge base.",
                capability="local_knowledge_search",
            ),
            ResearchPlanStepDraftInput(
                instruction="Find candidate sources.", capability="source_fetch"
            ),
        )

        self.assertNotEqual(
            plan_digest(self.plan()),
            plan_digest(self.plan(steps=widened)),
        )

    def test_reordering_steps_changes_the_digest(self) -> None:
        reversed_steps = tuple(reversed(self.default_steps()))

        self.assertNotEqual(
            plan_digest(self.plan()),
            plan_digest(self.plan(steps=reversed_steps)),
        )

    def test_adding_a_step_changes_the_digest(self) -> None:
        longer = self.default_steps() + (
            ResearchPlanStepDraftInput(
                instruction="List the accepted sources.", capability="none"
            ),
        )

        self.assertNotEqual(
            plan_digest(self.plan()),
            plan_digest(self.plan(steps=longer)),
        )

    def test_removing_a_step_changes_the_digest(self) -> None:
        shorter = self.default_steps()[:1]

        self.assertNotEqual(
            plan_digest(self.plan()),
            plan_digest(self.plan(steps=shorter)),
        )

    def test_a_changed_authorized_source_url_changes_the_digest(self) -> None:
        """The one exact source a step may acquire is approved content."""
        first = (
            ResearchPlanStepDraftInput(
                instruction="Load the authorized source.",
                capability="source_fetch",
                authorized_source_url="https://example.test/a",
            ),
        )
        second = (
            ResearchPlanStepDraftInput(
                instruction="Load the authorized source.",
                capability="source_fetch",
                authorized_source_url="https://example.test/b",
            ),
        )

        self.assertNotEqual(
            plan_digest(self.plan(steps=first)),
            plan_digest(self.plan(steps=second)),
        )

    def test_a_changed_selected_source_changes_the_digest(self) -> None:
        first = (
            ResearchPlanStepDraftInput(
                instruction="Read the selected source.",
                capability="none",
                selected_source_document_ids=("document-1",),
            ),
        )
        second = (
            ResearchPlanStepDraftInput(
                instruction="Read the selected source.",
                capability="none",
                selected_source_document_ids=("document-2",),
            ),
        )

        self.assertNotEqual(
            plan_digest(self.plan(steps=first)),
            plan_digest(self.plan(steps=second)),
        )


class AdversarialEncodingTests(PlanFixture):
    """A length-prefixed encoding earns its keep only against these."""

    def digest_of_instructions(self, *instructions: str) -> str:
        steps = tuple(
            ResearchPlanStepDraftInput(instruction=text, capability="none")
            for text in instructions
        )
        return plan_digest(self.plan(steps=steps))

    def test_authored_text_cannot_imitate_a_field_separator(self) -> None:
        """Two steps must never encode as one step containing a separator."""
        for separator in (":", "|", "\x00", "::", "s:1:", "d:2:"):
            with self.subTest(separator=separator):
                self.assertNotEqual(
                    self.digest_of_instructions("alpha", "beta"),
                    self.digest_of_instructions(f"alpha{separator}beta"),
                )

    def test_a_newline_cannot_split_one_step_into_two(self) -> None:
        self.assertNotEqual(
            self.digest_of_instructions("alpha", "beta"),
            self.digest_of_instructions("alpha\nbeta"),
        )

    def test_shifting_a_character_between_neighbours_changes_the_digest(self) -> None:
        """The classic aliasing failure of naive concatenation."""
        self.assertNotEqual(
            self.digest_of_instructions("abc", "def"),
            self.digest_of_instructions("ab", "cdef"),
        )

    def test_turkish_and_unicode_text_digests_deterministically(self) -> None:
        for text in (
            "Satürn halkalarının yaşı ölçüldü mü?",
            "İstanbul'da ölçüm yapıldı",
            "ünïcode ✅ 漢字 عربى",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    self.digest_of_instructions(text),
                    self.digest_of_instructions(text),
                )

    def test_text_differing_only_in_unicode_changes_the_digest(self) -> None:
        """Turkish dotted and dotless i are different characters."""
        self.assertNotEqual(
            self.digest_of_instructions("ilk adım"),
            self.digest_of_instructions("ılk adım"),
        )

    def test_repeated_instructions_under_different_capabilities_differ(self) -> None:
        same_text = "Do the thing."
        first = (
            ResearchPlanStepDraftInput(instruction=same_text, capability="none"),
            ResearchPlanStepDraftInput(
                instruction=same_text, capability="local_knowledge_search"
            ),
        )
        second = (
            ResearchPlanStepDraftInput(
                instruction=same_text, capability="local_knowledge_search"
            ),
            ResearchPlanStepDraftInput(instruction=same_text, capability="none"),
        )

        self.assertNotEqual(
            plan_digest(self.plan(steps=first)),
            plan_digest(self.plan(steps=second)),
        )

    def test_the_canonical_form_carries_a_schema_marker(self) -> None:
        """A future encoding change must not collide with this one.

        The marker moved to v2 when a step gained the discovery provider, and
        the old marker has to be gone rather than merely joined: an approval
        recorded under v1 described a plan that could not name a network
        provider, so it must fail to verify against a plan that can. Failing
        closed is the point — the alternative is a stored approval for a
        scholarly search quietly matching a plan aimed somewhere else.
        """
        canonical = canonical_plan_bytes(self.plan())

        self.assertIn(b"hypatia:research-plan-digest:v2", canonical)
        self.assertNotIn(b"hypatia:research-plan-digest:v1", canonical)

    def test_the_encoding_names_every_field_it_covers(self) -> None:
        canonical = canonical_plan_bytes(self.plan())

        for expected in (b"question", b"steps", b"instruction", b"capability"):
            with self.subTest(field=expected):
                self.assertIn(expected, canonical)
        for absent in (b"plan_id", b"created_at"):
            with self.subTest(field=absent):
                self.assertNotIn(absent, canonical)

    def test_a_digest_requires_a_validated_plan(self) -> None:
        for value in (None, "plan", 7, object()):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    plan_digest(value)  # type: ignore[arg-type]


class AuthorizationTests(PlanFixture):
    def test_an_authorization_is_immutable(self) -> None:
        authorization = self.authorization()

        with self.assertRaises(FrozenInstanceError):
            authorization.plan_digest = "0" * 64  # type: ignore[misc]

    def test_capabilities_are_derived_exactly_from_the_plan(self) -> None:
        plan = self.plan()

        self.assertEqual(
            self.authorization(plan).capabilities,
            frozenset(
                {
                    ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH,
                    ResearchPlanStepCapability.SOURCE_DISCOVERY,
                }
            ),
        )
        self.assertEqual(capabilities_of(plan), self.authorization(plan).capabilities)

    def test_the_approval_constructor_accepts_no_capability_argument(self) -> None:
        """A set that can be typed is a set that can be typed wider."""
        import inspect

        parameters = inspect.signature(ResearchPlanAuthorization.for_plan).parameters

        self.assertNotIn("capabilities", parameters)

    def test_a_widened_capability_set_cannot_pass_verification(self) -> None:
        """The record stores its set, so the plan is where widening is caught."""
        plan = self.plan()
        widened = ResearchPlanAuthorization(
            authorization_id="authorization-1",
            plan_digest=plan_digest(plan),
            research_run_id=RUN_ID,
            capabilities=capabilities_of(plan)
            | {
                ResearchPlanStepCapability.SOURCE_FETCH,
                ResearchPlanStepCapability.SOURCE_ACCEPT,
            },
            budget=ResearchAutonomyBudget(),
            authorized_at=AUTHORIZED,
            expires_at=EXPIRES,
        )

        self.assertIs(
            verify_plan_authorization(widened, plan, RUN_ID, AUTHORIZED),
            ResearchPlanAuthorizationVerdict.CAPABILITY_MISMATCH,
        )

    def test_the_budget_is_preserved_exactly(self) -> None:
        budget = ResearchAutonomyBudget(
            max_step_advances=2,
            max_network_operations=1,
            max_llm_operations=0,
            max_seconds=30.0,
        )

        self.assertEqual(self.authorization(budget=budget).budget, budget)

    def test_the_default_budget_still_permits_no_model_call(self) -> None:
        self.assertEqual(self.authorization().budget.max_llm_operations, 0)

    def test_disclosure_defaults_to_none(self) -> None:
        authorization = self.authorization()

        self.assertIs(authorization.disclosure, ResearchDisclosure.NONE)
        self.assertFalse(authorization.disclosure.permits_model_call)
        self.assertFalse(authorization.disclosure.permits_remote_endpoint)

    def test_remote_disclosure_is_a_separate_explicit_decision(self) -> None:
        remote = self.authorization(disclosure=ResearchDisclosure.REMOTE_PERMITTED)
        local = self.authorization(disclosure=ResearchDisclosure.LOCAL_ONLY)

        self.assertTrue(remote.disclosure.permits_remote_endpoint)
        self.assertFalse(local.disclosure.permits_remote_endpoint)
        self.assertTrue(local.disclosure.permits_model_call)

    def test_the_only_authorizer_that_can_be_represented_is_a_human(self) -> None:
        self.assertEqual(
            tuple(ResearchAuthorizer),
            (ResearchAuthorizer.HUMAN,),
        )
        self.assertIs(self.authorization().authorized_by, ResearchAuthorizer.HUMAN)
        self.assertTrue(self.authorization().authorized_by.is_human)

    def test_an_expiry_at_or_before_the_approval_is_refused(self) -> None:
        for expires_at in (AUTHORIZED, AUTHORIZED - timedelta(seconds=1)):
            with self.subTest(expires_at=expires_at):
                with self.assertRaises(ResearchError):
                    self.authorization(expires_at=expires_at)

    def test_a_naive_timestamp_fails_closed(self) -> None:
        for field, value in (
            ("authorized_at", datetime(2026, 8, 26, 9, 0)),
            ("expires_at", datetime(2026, 8, 26, 9, 30)),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ResearchError):
                    self.authorization(**{field: value})

    def test_validity_may_not_exceed_the_autonomy_ceiling(self) -> None:
        self.assertEqual(MAX_AUTHORIZATION_VALIDITY_SECONDS, 3_600.0)
        with self.assertRaises(ResearchError):
            self.authorization(
                expires_at=AUTHORIZED
                + timedelta(seconds=MAX_AUTHORIZATION_VALIDITY_SECONDS + 1)
            )

    def test_a_malformed_digest_is_refused(self) -> None:
        plan = self.plan()
        for digest in ("", "not-a-digest", "A" * 64, "0" * 63):
            with self.subTest(digest=digest):
                with self.assertRaises(ResearchError):
                    ResearchPlanAuthorization(
                        authorization_id="authorization-1",
                        plan_digest=digest,
                        research_run_id=RUN_ID,
                        capabilities=capabilities_of(plan),
                        budget=ResearchAutonomyBudget(),
                        authorized_at=AUTHORIZED,
                        expires_at=EXPIRES,
                    )

    def test_an_empty_capability_set_is_refused(self) -> None:
        plan = self.plan()
        with self.assertRaises(ResearchError):
            ResearchPlanAuthorization(
                authorization_id="authorization-1",
                plan_digest=plan_digest(plan),
                research_run_id=RUN_ID,
                capabilities=frozenset(),
                budget=ResearchAutonomyBudget(),
                authorized_at=AUTHORIZED,
                expires_at=EXPIRES,
            )

    def test_an_approval_records_no_consumption_state(self) -> None:
        """Single use is execution-bound future work, not a decoration here.

        A `consumed` flag that nothing ever set would read as a guarantee. Its
        absence is asserted so adding one is a deliberate act.
        """
        authorization = self.authorization()

        for absent in ("consumed", "used", "consume", "mark_used", "revoke"):
            with self.subTest(name=absent):
                self.assertFalse(hasattr(authorization, absent))


class VerificationTests(PlanFixture):
    def test_the_exact_plan_run_and_moment_verify(self) -> None:
        plan = self.plan()

        self.assertIs(
            verify_plan_authorization(
                self.authorization(plan), plan, RUN_ID, AUTHORIZED
            ),
            ResearchPlanAuthorizationVerdict.VALID,
        )

    def test_only_the_valid_verdict_authorizes(self) -> None:
        for verdict in ResearchPlanAuthorizationVerdict:
            with self.subTest(verdict=verdict):
                self.assertEqual(
                    verdict.authorizes,
                    verdict is ResearchPlanAuthorizationVerdict.VALID,
                )

    def test_a_modified_plan_does_not_inherit_the_approval(self) -> None:
        authorization = self.authorization(self.plan())
        edited = self.plan(question="Something else entirely?")

        self.assertIs(
            verify_plan_authorization(authorization, edited, RUN_ID, AUTHORIZED),
            ResearchPlanAuthorizationVerdict.DIGEST_MISMATCH,
        )

    def test_another_run_does_not_inherit_the_approval(self) -> None:
        plan = self.plan()

        self.assertIs(
            verify_plan_authorization(
                self.authorization(plan), plan, "run-2", AUTHORIZED
            ),
            ResearchPlanAuthorizationVerdict.RUN_MISMATCH,
        )

    def test_an_expired_approval_is_refused(self) -> None:
        plan = self.plan()

        self.assertIs(
            verify_plan_authorization(self.authorization(plan), plan, RUN_ID, EXPIRES),
            ResearchPlanAuthorizationVerdict.EXPIRED,
        )

    def test_expiry_is_inclusive_at_the_boundary(self) -> None:
        plan = self.plan()
        authorization = self.authorization(plan)
        moment = EXPIRES - timedelta(microseconds=1)

        self.assertIs(
            verify_plan_authorization(authorization, plan, RUN_ID, moment),
            ResearchPlanAuthorizationVerdict.VALID,
        )

    def test_identity_is_reported_before_validity(self) -> None:
        """Told once, an operator should hear the more useful problem."""
        authorization = self.authorization(self.plan())
        edited = self.plan(question="Something else entirely?")

        self.assertIs(
            verify_plan_authorization(authorization, edited, "run-2", EXPIRES),
            ResearchPlanAuthorizationVerdict.DIGEST_MISMATCH,
        )

    def test_verification_mutates_nothing(self) -> None:
        plan = self.plan()
        authorization = self.authorization(plan)
        before = (
            authorization.plan_digest,
            authorization.research_run_id,
            authorization.capabilities,
            authorization.budget,
            authorization.disclosure,
            authorization.authorized_by,
            plan.plan_id,
            plan.steps,
            canonical_plan_bytes(plan),
        )

        verify_plan_authorization(authorization, plan, RUN_ID, AUTHORIZED)

        self.assertEqual(
            before,
            (
                authorization.plan_digest,
                authorization.research_run_id,
                authorization.capabilities,
                authorization.budget,
                authorization.disclosure,
                authorization.authorized_by,
                plan.plan_id,
                plan.steps,
                canonical_plan_bytes(plan),
            ),
        )

    def test_verification_refuses_malformed_input_rather_than_guessing(self) -> None:
        plan = self.plan()
        authorization = self.authorization(plan)

        with self.assertRaises(ResearchError):
            verify_plan_authorization(None, plan, RUN_ID, AUTHORIZED)  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            verify_plan_authorization(authorization, None, RUN_ID, AUTHORIZED)  # type: ignore[arg-type]
        with self.assertRaises(ResearchError):
            verify_plan_authorization(authorization, plan, "  ", AUTHORIZED)
        with self.assertRaises(ResearchError):
            verify_plan_authorization(
                authorization, plan, RUN_ID, datetime(2026, 8, 26, 9, 0)
            )


class VerifierIsInertTests(PlanFixture):
    """It answers a question. It does not do anything."""

    def source(self) -> str:
        from pathlib import Path

        module = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "research"
            / "ResearchPlanAuthorizationVerifier.py"
        )
        return module.read_text(encoding="utf-8")

    def test_the_verifier_reaches_no_side_effecting_machinery(self) -> None:
        source = self.source()

        for forbidden in (
            "import os",
            "open(",
            "urllib",
            "requests",
            "socket",
            "Store",
            "Manager",
            "ToolRuntime",
            "llm",
            "Evidence",
            "BackgroundResearchTask",
            "process_advance",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_verifier_does_not_reuse_tool_execution_vocabulary(self) -> None:
        """Nothing ran, so nothing may describe itself with a disposition."""
        self.assertNotIn("ToolDisposition", self.source())
        self.assertNotIn(
            "ToolDisposition", ResearchPlanAuthorizationVerdict.__doc__ or ""
        )


class BoundaryRegressionTests(PlanFixture):
    """What this milestone must not have changed."""

    #: The four foreground execution intents are deliberately absent. All of
    #: them are reachable, and every one of them is an act the operator has to
    #: perform: start spends an approval, advance attempts exactly one step,
    #: status reads, cancel stops. The seven below are the ones that would run
    #: research without anybody asking each time, and none of them can reach an
    #: approval at all.
    AUTONOMY_INTENTS = (
        "research_autonomy_run",
        "background_research_task_create",
        "background_research_task_list",
        "background_research_task_pause",
        "background_research_task_resume",
        "background_research_task_cancel",
    )

    def desktop_source(self) -> str:
        from pathlib import Path

        desktop = Path(__file__).resolve().parents[2] / "src" / "desktop"
        return "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(desktop.rglob("*.py"))
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
        ):
            with self.subTest(reachable=intent):
                self.assertIn(intent, source)
        for intent in self.AUTONOMY_INTENTS:
            with self.subTest(unreachable=intent):
                self.assertNotIn(intent, source)

    def test_only_execution_start_consults_an_authorization(self) -> None:
        """Enforcement arrived, and it arrived in exactly one place.

        This narrowed twice. It began as "nothing anywhere references an
        approval", true while none could be made. It then became "no execution
        path reads one", true while none could be spent. Now one path does, and
        the invariant worth keeping is that it is the only one: autonomy and
        the scheduler still cannot reach an approval, so neither can grant
        itself permission by looping over a path that can.
        """
        from pathlib import Path

        root = Path(__file__).resolve().parents[2] / "src"
        must_not_read = (
            "ResearchAutonomyApplicationService.py",
            "BackgroundResearchSchedulerApplicationService.py",
            "ResearchPlanExecutionState.py",
            "BackgroundResearchTask.py",
        )
        consumers = [
            path.name
            for path in root.rglob("*.py")
            if path.name in must_not_read
            and "Authorization" in path.read_text(encoding="utf-8")
        ]

        self.assertEqual(consumers, [])

    def test_execution_reaches_approval_only_through_the_narrow_port(self) -> None:
        """It may spend an approval. It may not preview, list, or create one."""
        from pathlib import Path

        execution = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "cognition"
            / "ResearchPlanExecutionApplicationService.py"
        ).read_text(encoding="utf-8")

        self.assertIn("ResearchPlanAuthorizationConsumer", execution)
        self.assertNotIn("ResearchPlanAuthorizationApplicationService", execution)
        self.assertNotIn("ResearchPlanAuthorizationStore", execution)
        self.assertNotIn("process_preview", execution)
        self.assertNotIn("process_confirm", execution)

    def test_the_approval_service_cannot_reach_execution(self) -> None:
        """The other direction of the same boundary."""
        from pathlib import Path

        service = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "cognition"
            / "ResearchPlanAuthorizationApplicationService.py"
        ).read_text(encoding="utf-8")

        for forbidden in (
            "ResearchPlanExecutionApplicationService",
            "ResearchAutonomyApplicationService",
            "BackgroundResearchSchedulerApplicationService",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, service)

    def test_plan_identity_remains_a_per_preview_value(self) -> None:
        """The digest is a second identity, not a replacement for the first."""
        first = self.plan(plan_id="plan-a")
        second = self.plan(plan_id="plan-b")

        self.assertNotEqual(first.plan_id, second.plan_id)
        self.assertEqual(plan_digest(first), plan_digest(second))

    def test_the_draft_preview_contract_is_unchanged(self) -> None:
        service = ResearchPlanDraftService()

        ready = service.preview(QUESTION, self.default_steps())
        rejected = service.preview("", self.default_steps())

        self.assertTrue(ready.allowed)
        self.assertIsNotNone(ready.plan)
        self.assertFalse(rejected.allowed)
        self.assertIsNone(rejected.plan)

    def test_no_dangerous_capability_was_added(self) -> None:
        values = {capability.value for capability in ResearchPlanStepCapability}

        for forbidden in ("filesystem", "shell", "process", "tool", "command"):
            with self.subTest(name=forbidden):
                self.assertEqual(
                    [value for value in values if forbidden in value],
                    [],
                )


if __name__ == "__main__":
    unittest.main()
