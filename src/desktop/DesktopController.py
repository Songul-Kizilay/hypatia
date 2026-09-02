"""Testable desktop actions delegated to the existing Brain boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.CancellationSignal import CancellationToken
from research.DeferredExecutionControlView import DeferredExecutionControlView
from research.OneShotDeferredExecutionSchedule import OneShotDeferredExecutionSchedule
from research.OneShotDeferredExecutionScheduleView import (
    OneShotDeferredExecutionScheduleView,
)
from research.ProviderComparisonRequest import ProviderComparisonRequest
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRunMarkdownExportPreview import (
    ResearchRunMarkdownExportPreview,
)
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceUsefulness import ResearchSourceUsefulness


class TrustedDeferredExecutionController(Protocol):
    """Narrow desktop-only authority, deliberately not a Brain processor."""

    def preview(self, task_id: str) -> DeferredExecutionControlView: ...

    def grant(self, task_id: str) -> DeferredExecutionControlView: ...

    def revoke(self, task_id: str) -> DeferredExecutionControlView: ...


class TrustedOneShotDeferredExecutionController(Protocol):
    """Narrow non-Brain port for one exact future attempt."""

    def preview(
        self, task_id: str, run_at: datetime
    ) -> OneShotDeferredExecutionScheduleView: ...

    def schedule(
        self, task_id: str, run_at: datetime
    ) -> OneShotDeferredExecutionScheduleView: ...

    def cancel(self, task_id: str) -> OneShotDeferredExecutionSchedule: ...

    def status(self, task_id: str) -> OneShotDeferredExecutionSchedule | None: ...

    def next_pending(self) -> OneShotDeferredExecutionSchedule | None: ...

    def fire(
        self,
        schedule_id: str,
        cancellation_token: CancellationToken | None = None,
    ) -> OneShotDeferredExecutionSchedule: ...

    def skip_due_to_busy(
        self, schedule_id: str
    ) -> OneShotDeferredExecutionSchedule: ...


def _plan_step_drafts(
    instruction_lines: str,
    source_id_lines: str,
) -> tuple[tuple[object, ...], ...]:
    """Shape typed plan rows into the positional drafts the runtime accepts.

    Shared by plan preview and approval so both send byte-identical steps. Two
    copies of this shaping would eventually disagree, and a plan that digests
    differently depending on which button produced it would make an approval
    refuse the plan it was given for.
    """
    instructions = instruction_lines.splitlines()
    source_rows = source_id_lines.splitlines()
    row_count = max(len(instructions), len(source_rows))
    return tuple(
        (
            instructions[index].strip() if index < len(instructions) else "",
            tuple(
                source_id.strip()
                for source_id in (
                    source_rows[index].split(",") if index < len(source_rows) else ()
                )
                if source_id.strip()
            ),
        )
        for index in range(row_count)
    )


def _evidence_id_list(value: str) -> tuple[str, ...]:
    """Read one typed field as the evidence IDs it names.

    Commas and whitespace both separate, because a person copying identifiers
    out of a list will produce either and should not have to care which. Empty
    fragments are dropped rather than sent on as blank IDs the runtime would
    have to refuse.
    """
    entries = tuple(
        fragment.strip()
        for fragment in value.replace(",", " ").split()
        if fragment.strip()
    )
    if not entries:
        raise ValueError("At least one recorded evidence ID is required.")
    return entries


class BrainProcessor(Protocol):
    """Minimum existing runtime capability needed by the desktop adapter."""

    def process(self, request: BrainRequest | str) -> BrainResponse:
        """Process a user request through the established Brain boundary."""


class DesktopController:
    """Keep UI actions small, explicit, and free of duplicate state."""

    def __init__(
        self,
        brain: BrainProcessor,
        deferred_execution_control: TrustedDeferredExecutionController | None = None,
        one_shot_deferred_execution_control: (
            TrustedOneShotDeferredExecutionController | None
        ) = None,
    ) -> None:
        self._brain = brain
        self._deferred_execution_control = deferred_execution_control
        self._one_shot_deferred_execution_control = one_shot_deferred_execution_control

    @property
    def deferred_execution_control_available(self) -> bool:
        return self._deferred_execution_control is not None

    def deferred_execution_status(self, task_id: str) -> DeferredExecutionControlView:
        return self._deferred_control().preview(task_id.strip())

    def allow_deferred_execution(self, task_id: str) -> DeferredExecutionControlView:
        return self._deferred_control().grant(task_id.strip())

    def revoke_deferred_execution(self, task_id: str) -> DeferredExecutionControlView:
        return self._deferred_control().revoke(task_id.strip())

    def _deferred_control(self) -> TrustedDeferredExecutionController:
        if self._deferred_execution_control is None:
            raise ValueError("Deferred execution control is unavailable.")
        return self._deferred_execution_control

    @property
    def one_shot_deferred_execution_available(self) -> bool:
        return self._one_shot_deferred_execution_control is not None

    def preview_one_shot_deferred_execution(
        self, task_id: str, run_at: datetime
    ) -> OneShotDeferredExecutionScheduleView:
        return self._one_shot_control().preview(task_id.strip(), run_at)

    def schedule_one_shot_deferred_execution(
        self, task_id: str, run_at: datetime
    ) -> OneShotDeferredExecutionScheduleView:
        return self._one_shot_control().schedule(task_id.strip(), run_at)

    def cancel_one_shot_deferred_execution(
        self, task_id: str
    ) -> OneShotDeferredExecutionSchedule:
        return self._one_shot_control().cancel(task_id.strip())

    def one_shot_deferred_execution_status(
        self, task_id: str
    ) -> OneShotDeferredExecutionSchedule | None:
        return self._one_shot_control().status(task_id.strip())

    def next_one_shot_deferred_execution(
        self,
    ) -> OneShotDeferredExecutionSchedule | None:
        return self._one_shot_control().next_pending()

    def fire_one_shot_deferred_execution(
        self,
        schedule_id: str,
        cancellation_token: CancellationToken | None = None,
    ) -> OneShotDeferredExecutionSchedule:
        return self._one_shot_control().fire(schedule_id.strip(), cancellation_token)

    def skip_busy_one_shot_deferred_execution(
        self, schedule_id: str
    ) -> OneShotDeferredExecutionSchedule:
        return self._one_shot_control().skip_due_to_busy(schedule_id.strip())

    def _one_shot_control(self) -> TrustedOneShotDeferredExecutionController:
        if self._one_shot_deferred_execution_control is None:
            raise ValueError("One-shot deferred execution control is unavailable.")
        return self._one_shot_deferred_execution_control

    def submit_message(self, message: str) -> BrainResponse:
        """Send non-empty composer text unchanged to the existing Brain."""
        if not message.strip():
            raise ValueError("A desktop message cannot be empty.")
        return self._brain.process(message)

    def select_session(self, session_id: str) -> BrainResponse:
        """Activate an existing session through its explicit Brain command."""
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            raise ValueError("A session ID cannot be empty.")
        return self._brain.process(f"use session {normalized_session_id}")

    def session_overview(self) -> BrainResponse:
        """Request existing read-only session facts for desktop presentation."""
        return self._brain.process("session overview")

    def session_details(self, session_id: str) -> BrainResponse:
        """Request read-only details for the explicitly selected session."""
        return self._selected_session_command("session details", session_id)

    def session_recent(self, session_id: str) -> BrainResponse:
        """Request the selected session's read-only recent conversation view."""
        return self._selected_session_command("session recent", session_id)

    def session_activity(self, session_id: str) -> BrainResponse:
        """Request read-only first and last activity for the selected session."""
        return self._selected_session_command("session activity", session_id)

    def session_search(self, session_id: str, query: str) -> BrainResponse:
        """Search only the explicitly selected session without changing it."""
        normalized_session_id = session_id.strip()
        normalized_query = query.strip()
        if not normalized_session_id:
            raise ValueError("A session ID cannot be empty.")
        if not normalized_query:
            raise ValueError("A session search query cannot be empty.")
        return self._brain.process(
            f"session search {normalized_session_id} -- {normalized_query}"
        )

    def preview_session_rename(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        """Validate a requested session rename without changing either store."""
        return self._session_rename_command(
            "preview rename session",
            source_session_id,
            target_session_id,
        )

    def rename_session(
        self,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        """Rename only after the desktop has shown the runtime preview."""
        return self._session_rename_command(
            "rename session",
            source_session_id,
            target_session_id,
        )

    def preview_session_delete(self, session_id: str) -> BrainResponse:
        """Request the existing read-only delete decision for one session."""
        return self._selected_session_command("preview delete session", session_id)

    def delete_session(self, session_id: str) -> BrainResponse:
        """Send the existing guarded delete command after an allowed preview."""
        return self._selected_session_command("delete session", session_id)

    def recall(self, query: str) -> BrainResponse:
        """Request explicit lexical recall without changing conversation memory."""
        return self._recall_command("recall", query)

    def semantic_recall(self, query: str) -> BrainResponse:
        """Request explicit semantic recall through the existing opt-in path."""
        return self._recall_command("semantic recall", query)

    def knowledge_context(self, query: str) -> BrainResponse:
        """Request bounded cited local knowledge context without an LLM call."""
        return self._knowledge_command("knowledge context", query)

    def knowledge_graph(self, query: str) -> BrainResponse:
        """Request a bounded cited local source-structure view without an LLM."""
        return self._knowledge_command("knowledge graph", query)

    def ask_knowledge(self, query: str) -> BrainResponse:
        """Ask the enabled runtime using only bounded cited local knowledge."""
        return self._knowledge_command("ask knowledge", query)

    def load_knowledge(self, path: str) -> BrainResponse:
        """Load one explicitly selected local text or Markdown source through Brain."""
        normalized_path = path.strip()
        if not normalized_path:
            raise ValueError("A local knowledge source path cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Load selected local knowledge source",
                source="desktop",
                metadata={
                    "intent": "knowledge_load",
                    "knowledge_path": normalized_path,
                },
            )
        )

    def create_research_run(self, question: str) -> BrainResponse:
        """Create one explicit, persistent research run through Brain."""
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("A research question cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Create internet research run",
                source="desktop",
                metadata={
                    "intent": "research_run_create",
                    "research_question": normalized_question,
                },
            )
        )

    def preview_research_plan_draft(
        self,
        question: str,
        instruction_lines: str,
        source_id_lines: str,
    ) -> BrainResponse:
        """Preview one explicit ordered plan without saving or executing it."""
        if not all(
            isinstance(value, str)
            for value in (question, instruction_lines, source_id_lines)
        ):
            raise ValueError("Research plan draft fields must be text.")
        return self._brain.process(
            BrainRequest(
                message="Preview explicit authored research plan",
                source="desktop",
                metadata={
                    "intent": "research_plan_draft_preview",
                    "research_plan_question": question.strip(),
                    "research_plan_steps": _plan_step_drafts(
                        instruction_lines,
                        source_id_lines,
                    ),
                },
            )
        )

    def preview_plan_authorization(
        self,
        question: str,
        instruction_lines: str,
        source_id_lines: str,
        research_run_id: str,
        disclosure: str = "none",
        max_step_advances: str = "",
        max_network_operations: str = "",
        max_seconds: str = "",
    ) -> BrainResponse:
        """Show the approval this plan would record. Records nothing.

        The budget fields are passed through exactly as typed, blanks included.
        A blank means the operator left that bound alone; nothing here fills one
        in for them, and nothing here reads an unusable value as a number.
        """
        return self._plan_authorization_request(
            "research_plan_authorization_preview",
            "Preview research plan approval",
            question,
            instruction_lines,
            source_id_lines,
            research_run_id,
            extra={
                "research_disclosure": disclosure.strip() or "none",
                **self._budget_metadata(
                    max_step_advances,
                    max_network_operations,
                    max_seconds,
                ),
            },
        )

    @staticmethod
    def _budget_metadata(
        max_step_advances: str,
        max_network_operations: str,
        max_seconds: str,
    ) -> dict[str, str]:
        """Return only the bounds the operator actually filled in.

        Empty fields are omitted rather than sent as zero. Zero is a real and
        very restrictive answer, and a blank box must never be read as one.
        """
        chosen = {
            "max_step_advances": max_step_advances,
            "max_network_operations": max_network_operations,
            "max_seconds": max_seconds,
        }
        return {name: value for name, value in chosen.items() if value.strip()}

    def confirm_plan_authorization(
        self,
        authorization_id: str,
        question: str,
        instruction_lines: str,
        source_id_lines: str,
        research_run_id: str,
        max_step_advances: str = "",
        max_network_operations: str = "",
        max_seconds: str = "",
    ) -> BrainResponse:
        """Record exactly one previewed approval. Starts no research.

        The plan is re-sent rather than remembered here, so the runtime checks
        the approval against the plan as it stands now instead of trusting what
        this surface last displayed.
        """
        normalized_id = authorization_id.strip()
        if not normalized_id:
            raise ValueError("A previewed approval ID is required.")
        return self._plan_authorization_request(
            "research_plan_authorization_confirm",
            "Confirm research plan approval",
            question,
            instruction_lines,
            source_id_lines,
            research_run_id,
            extra={
                "authorization_id": normalized_id,
                **self._budget_metadata(
                    max_step_advances,
                    max_network_operations,
                    max_seconds,
                ),
            },
        )

    def start_authorized_execution(
        self,
        authorization_id: str,
        question: str,
        instruction_lines: str,
        source_id_lines: str,
        research_run_id: str,
    ) -> BrainResponse:
        """Spend one recorded approval on one foreground execution start.

        Sends no budget and no disclosure. Starting spends neither, and a field
        the surface could widen is a field somebody eventually widens; the
        approved bounds stand as recorded.
        """
        normalized_id = authorization_id.strip()
        if not normalized_id:
            raise ValueError("A recorded approval ID is required.")
        return self._plan_authorization_request(
            "research_plan_execution_start",
            "Start one authorized research plan execution",
            question,
            instruction_lines,
            source_id_lines,
            research_run_id,
            extra={"authorization_id": normalized_id},
        )

    def research_execution_status(self, execution_id: str) -> BrainResponse:
        """Read one execution's canonical state. Advances nothing."""
        return self._execution_request(
            "research_plan_execution_status",
            "Report research plan execution status",
            execution_id,
        )

    def advance_research_execution(self, execution_id: str) -> BrainResponse:
        """Attempt exactly one step. Never two, and never a loop.

        One call, one attempt. The operator asks again for the next step,
        which is the difference between stepping and autonomy.
        """
        return self._execution_request(
            "research_plan_execution_advance",
            "Advance one research plan execution step",
            execution_id,
        )

    def resolve_interrupted_attempt(
        self,
        execution_id: str,
        step_id: str,
        resolution: str,
    ) -> BrainResponse:
        """Record what the operator knows about an interrupted attempt.

        Reaches no provider and spends no budget. All three identities are
        required: a ruling that did not name exactly what it ruled on would be
        a guess wearing a decision's clothes.
        """
        normalized_execution = execution_id.strip()
        normalized_step = step_id.strip()
        normalized_resolution = resolution.strip()
        if not normalized_execution:
            raise ValueError("An execution ID cannot be empty.")
        if not normalized_step:
            raise ValueError("A step ID cannot be empty.")
        if not normalized_resolution:
            raise ValueError("A ruling cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Resolve interrupted research attempt",
                source="desktop",
                metadata={
                    "intent": "research_plan_execution_resolve",
                    "research_plan_id": normalized_execution,
                    "step_id": normalized_step,
                    "resolution": normalized_resolution,
                },
            )
        )

    def recover_interrupted_attempt(
        self,
        execution_id: str,
        step_id: str,
        decision: str,
        summary: str = "",
        claimed_operation: str = "",
    ) -> BrainResponse:
        """Record what the operator did about an attempt that ran unseen.

        Carries only the decision and the operator's own account of it. There is
        deliberately nowhere here to pass a capability, an approval or a budget:
        recovering an outcome is not a way to acquire permission.
        """
        normalized_execution = execution_id.strip()
        normalized_step = step_id.strip()
        normalized_decision = decision.strip()
        if not normalized_execution:
            raise ValueError("An execution ID cannot be empty.")
        if not normalized_step:
            raise ValueError("A step ID cannot be empty.")
        if not normalized_decision:
            raise ValueError("A recovery decision cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Recover research attempt outcome",
                source="desktop",
                metadata={
                    "intent": "research_plan_execution_recover",
                    "research_plan_id": normalized_execution,
                    "step_id": normalized_step,
                    "decision": normalized_decision,
                    "summary": summary.strip(),
                    "claimed_operation": claimed_operation.strip(),
                },
            )
        )

    def continue_research_execution(
        self,
        execution_id: str,
        max_steps: str,
    ) -> BrainResponse:
        """Run the ordinary one-step advance, at most this many times.

        Both the execution and the bound come from the operator. There is no
        reading of a missing bound as "as many as it takes": an unusable one is
        passed through and refused rather than replaced with a guess.
        """
        normalized_execution = execution_id.strip()
        normalized_steps = str(max_steps).strip()
        if not normalized_execution:
            raise ValueError("An execution ID cannot be empty.")
        if not normalized_steps:
            raise ValueError("A step count cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Continue research plan execution within a bound",
                source="desktop",
                metadata={
                    "intent": "research_plan_execution_continue",
                    "research_plan_id": normalized_execution,
                    "max_steps": normalized_steps,
                },
            )
        )

    def create_background_task(self, execution_id: str) -> BrainResponse:
        """Queue one exact execution for the scheduler. Runs nothing.

        No budget is sent, so the scheduler applies its own default per-run
        bound. That bound is not authority in any case: what the task may
        actually spend stays the allowance the execution was already granted,
        and queueing cannot raise it. The approval panel's budget fields are
        deliberately not reused here — they belong to an authorization.
        """
        normalized = execution_id.strip()
        if not normalized:
            raise ValueError("An execution ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Queue one background research task",
                source="desktop",
                metadata={
                    "intent": "background_research_task_create",
                    "research_plan_id": normalized,
                },
            )
        )

    def list_background_tasks(self) -> BrainResponse:
        """Read the durable queue. Selects nothing and runs nothing."""
        return self._brain.process(
            BrainRequest(
                message="List background research tasks",
                source="desktop",
                metadata={"intent": "background_research_task_list"},
            )
        )

    def pause_background_task(self, task_id: str) -> BrainResponse:
        """Stop the scheduler choosing this task until somebody resumes it."""
        return self._background_task_ruling(
            "background_research_task_pause",
            "Pause one background research task",
            task_id,
        )

    def resume_background_task(self, task_id: str) -> BrainResponse:
        """Make this task selectable again. Runs no cycle."""
        return self._background_task_ruling(
            "background_research_task_resume",
            "Resume one background research task",
            task_id,
        )

    def cancel_background_task(self, task_id: str) -> BrainResponse:
        """Stop the scheduler choosing this task, for good.

        The queue entry only. The research execution it names is untouched and
        keeps whatever state it already had; stopping that is a separate,
        explicit action on the execution itself.
        """
        return self._background_task_ruling(
            "background_research_task_cancel",
            "Cancel one background research task",
            task_id,
        )

    def _background_task_ruling(
        self,
        intent: str,
        message: str,
        task_id: str,
    ) -> BrainResponse:
        """Send one exact task identity to one existing scheduler intent."""
        normalized = task_id.strip()
        if not normalized:
            raise ValueError("A background task ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message=message,
                source="desktop",
                metadata={"intent": intent, "background_task_id": normalized},
            )
        )

    def run_background_scheduler_cycle(self) -> BrainResponse:
        """Run exactly one bounded scheduler cycle. Schedules nothing further.

        The scheduler decides which task, if any, is runnable and how much work
        one cycle covers. Nothing here selects a task, advances a step or grants
        authority; it asks the existing service to take one turn and reports
        what it did.
        """
        return self._brain.process(
            BrainRequest(
                message="Run one background research worker cycle",
                source="desktop",
                metadata={"intent": "background_research_worker_cycle"},
            )
        )

    def cancel_research_execution(self, execution_id: str) -> BrainResponse:
        """Stop one execution. Refunds neither approval nor spent budget."""
        return self._execution_request(
            "research_plan_execution_cancel",
            "Cancel one research plan execution",
            execution_id,
        )

    def _execution_request(
        self,
        intent: str,
        message: str,
        execution_id: str,
    ) -> BrainResponse:
        normalized_id = execution_id.strip()
        if not normalized_id:
            raise ValueError("An execution ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message=message,
                source="desktop",
                metadata={
                    "intent": intent,
                    "research_plan_id": normalized_id,
                },
            )
        )

    def list_plan_authorizations(self) -> BrainResponse:
        """Report recorded approvals without approving or running anything."""
        return self._intent_only_request(
            "research_plan_authorization_list",
            "List research plan approvals",
        )

    def _plan_authorization_request(
        self,
        intent: str,
        message: str,
        question: str,
        instruction_lines: str,
        source_id_lines: str,
        research_run_id: str,
        *,
        extra: dict[str, object],
    ) -> BrainResponse:
        if not all(
            isinstance(value, str)
            for value in (question, instruction_lines, source_id_lines)
        ):
            raise ValueError("Research plan approval fields must be text.")
        normalized_question = question.strip()
        normalized_run_id = research_run_id.strip()
        if not normalized_question:
            raise ValueError("A research question cannot be empty.")
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        metadata: dict[str, object] = {
            "intent": intent,
            "research_run_id": normalized_run_id,
            "research_plan_question": normalized_question,
            "research_plan_steps": _plan_step_drafts(
                instruction_lines,
                source_id_lines,
            ),
        }
        metadata.update(extra)
        return self._brain.process(
            BrainRequest(message=message, source="desktop", metadata=metadata)
        )

    def preview_provider_comparison_plan(self, question: str) -> BrainResponse:
        """Preview the two-step plan a comparison asks for. Contact nobody.

        This is the ordinary plan preview with the two discovery steps a
        comparison needs. It reaches no provider: approval and two explicit
        advances still stand between this and any request.
        """
        if not isinstance(question, str) or not question.strip():
            raise ValueError("A research question cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Preview provider comparison plan",
                source="desktop",
                metadata={
                    "intent": "research_plan_draft_preview",
                    "research_plan_question": question.strip(),
                    "research_plan_steps": ProviderComparisonRequest().step_drafts(),
                },
            )
        )

    def report_provider_comparison(self, research_run_id: str) -> BrainResponse:
        """Show one run's two provider result sets side by side."""
        return self._run_only_request(
            "provider_comparison_report",
            "Report provider comparison",
            research_run_id,
        )

    def report_provider_quality(self) -> BrainResponse:
        """Describe how assessed provider samples performed, across every run."""
        return self._brain.process(
            BrainRequest(
                message="Report provider quality",
                source="desktop",
                metadata={"intent": "provider_quality_report"},
            )
        )

    def report_paired_provider_quality(self) -> BrainResponse:
        """Compare only runs where both providers answered the same question."""
        return self._brain.process(
            BrainRequest(
                message="Report paired provider quality",
                source="desktop",
                metadata={"intent": "paired_provider_quality_report"},
            )
        )

    def report_claim_calibration(self, research_run_id: str) -> BrainResponse:
        """Report how far each claim outruns its evidence, adjusting none."""
        return self._run_only_request(
            "research_calibration_report",
            "Report claim calibration",
            research_run_id,
        )

    def prepare_claim_revision_review(
        self,
        research_run_id: str,
        claim_id: str,
    ) -> BrainResponse:
        """Show an inert, exact handoff for one calibrated current claim."""
        normalized_run_id = research_run_id.strip()
        normalized_claim_id = claim_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not normalized_claim_id:
            raise ValueError("A research claim ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Prepare calibrated claim review",
                source="desktop",
                metadata={
                    "intent": "research_calibration_revision_prepare",
                    "research_run_id": normalized_run_id,
                    "research_claim_id": normalized_claim_id,
                },
            )
        )

    def preview_reflection(self, research_run_id: str) -> BrainResponse:
        """Report how one run went without storing the account."""
        return self._run_only_request(
            "research_reflection_preview",
            "Preview research reflection",
            research_run_id,
        )

    def store_reflection(self, research_run_id: str) -> BrainResponse:
        """Keep one account of how a run went, changing nothing about the run."""
        return self._run_only_request(
            "research_reflection_store",
            "Store research reflection",
            research_run_id,
        )

    def list_reflections(self) -> BrainResponse:
        """Report stored reflections without producing a new one."""
        return self._intent_only_request(
            "research_reflection_list",
            "List research reflections",
        )

    def detect_curiosity_gaps(self, research_run_id: str) -> BrainResponse:
        """Report where one run's own record is thin, proposing nothing."""
        return self._run_only_request(
            "curiosity_gap_detect",
            "Detect research gaps",
            research_run_id,
        )

    def preview_curiosity_questions(self, research_run_id: str) -> BrainResponse:
        """Draft and rank questions for one run without storing any."""
        return self._run_only_request(
            "curiosity_question_preview",
            "Preview curiosity questions",
            research_run_id,
        )

    def store_curiosity_questions(self, research_run_id: str) -> BrainResponse:
        """Keep the ranked proposals for one run, deciding nothing."""
        return self._run_only_request(
            "curiosity_question_store",
            "Store curiosity questions",
            research_run_id,
        )

    def list_curiosity_questions(self) -> BrainResponse:
        """Report every stored proposal without running anything."""
        return self._intent_only_request(
            "curiosity_question_list",
            "List curiosity questions",
        )

    def accept_curiosity_question(self, question_id: str) -> BrainResponse:
        """Record that one proposal is worth pursuing. Starts no research."""
        return self._curiosity_ruling(
            "curiosity_question_accept",
            "Accept curiosity question",
            question_id,
        )

    def prepare_curiosity_research_proposal(
        self,
        question_id: str,
        max_step_advances: str = "",
        max_network_operations: str = "",
        max_seconds: str = "",
    ) -> BrainResponse:
        """Draft an inert research proposal for one accepted question.

        A second explicit decision, separate from accepting the question. It
        reads what would be researched and authorizes none of it: no provider is
        contacted, no source is loaded, and no approval is created or implied.

        The budget fields ride along so the preview can show what the plan needs
        beside what would be granted. Carrying them approves nothing.
        """
        return self._curiosity_ruling(
            "curiosity_prepare_proposal",
            "Prepare research proposal for curiosity question",
            question_id,
            extra=self._budget_metadata(
                max_step_advances,
                max_network_operations,
                max_seconds,
            ),
        )

    def authorize_curiosity_research_proposal(
        self,
        question_id: str,
        expected_plan_digest: str,
        max_step_advances: str = "",
        max_network_operations: str = "",
        max_seconds: str = "",
    ) -> BrainResponse:
        """Approve one exact previewed proposal, starting nothing.

        Carries the digest the operator was shown so the application can refuse
        anything else. The plan itself is never sent from here: it is derived
        again from canonical state, and this only says which one was read.
        """
        normalized_question = question_id.strip()
        normalized_digest = expected_plan_digest.strip()
        if not normalized_question:
            raise ValueError("A curiosity question ID cannot be empty.")
        if not normalized_digest:
            raise ValueError("An expected plan digest cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Authorize curiosity research proposal",
                source="desktop",
                metadata={
                    **self._budget_metadata(
                        max_step_advances,
                        max_network_operations,
                        max_seconds,
                    ),
                    "intent": "curiosity_authorize_proposal",
                    "curiosity_question_id": normalized_question,
                    "expected_plan_digest": normalized_digest,
                },
            )
        )

    def start_authorized_curiosity_research_proposal(
        self,
        question_id: str,
        expected_plan_digest: str,
        authorization_id: str,
    ) -> BrainResponse:
        """Spend one approval on a zero-step foreground execution start."""
        normalized_question = question_id.strip()
        normalized_digest = expected_plan_digest.strip()
        normalized_authorization = authorization_id.strip()
        if not normalized_question:
            raise ValueError("A curiosity question ID cannot be empty.")
        if not normalized_digest:
            raise ValueError("An expected plan digest cannot be empty.")
        if not normalized_authorization:
            raise ValueError("A recorded approval ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Start authorized curiosity research proposal",
                source="desktop",
                metadata={
                    "intent": "curiosity_start_authorized_proposal",
                    "curiosity_question_id": normalized_question,
                    "expected_plan_digest": normalized_digest,
                    "authorization_id": normalized_authorization,
                },
            )
        )

    def resume_research_execution(
        self,
        question_id: str,
        execution_id: str,
    ) -> BrainResponse:
        """Make one durable execution reachable again. Runs no step.

        Both identities are required and neither is guessed. There is no
        "resume the latest" here on purpose: the operator names the exact
        execution, and naming nothing resumes nothing.
        """
        normalized_question = question_id.strip()
        normalized_execution = execution_id.strip()
        if not normalized_question:
            raise ValueError("A curiosity question ID cannot be empty.")
        if not normalized_execution:
            raise ValueError("An execution ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Resume durable research plan execution",
                source="desktop",
                metadata={
                    "intent": "curiosity_resume_execution",
                    "curiosity_question_id": normalized_question,
                    "research_plan_id": normalized_execution,
                },
            )
        )

    def dismiss_curiosity_question(self, question_id: str) -> BrainResponse:
        """Record that one proposal is not worth pursuing."""
        return self._curiosity_ruling(
            "curiosity_question_dismiss",
            "Dismiss curiosity question",
            question_id,
        )

    def _curiosity_ruling(
        self,
        intent: str,
        message: str,
        question_id: str,
        extra: dict[str, str] | None = None,
    ) -> BrainResponse:
        normalized_id = question_id.strip()
        if not normalized_id:
            raise ValueError("A curiosity question ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message=message,
                source="desktop",
                metadata={
                    **(extra or {}),
                    "intent": intent,
                    "curiosity_question_id": normalized_id,
                },
            )
        )

    def _run_only_request(
        self,
        intent: str,
        message: str,
        research_run_id: str,
    ) -> BrainResponse:
        normalized_run_id = research_run_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message=message,
                source="desktop",
                metadata={"intent": intent, "research_run_id": normalized_run_id},
            )
        )

    def _intent_only_request(self, intent: str, message: str) -> BrainResponse:
        return self._brain.process(
            BrainRequest(
                message=message,
                source="desktop",
                metadata={"intent": intent},
            )
        )

    def propose_hypothesis(
        self,
        research_run_id: str,
        statement: str,
        discriminating_test: str,
    ) -> BrainResponse:
        """Propose one conjecture together with what would count against it.

        The discriminating test is required here, not optional, because the
        runtime requires it. A conjecture that names nothing capable of
        counting against it survives any amount of evidence.
        """
        values = {
            "research_run_id": research_run_id.strip(),
            "hypothesis_statement": statement.strip(),
            "hypothesis_discriminating_test": discriminating_test.strip(),
        }
        if not all(values.values()):
            raise ValueError(
                "A hypothesis needs a research run, a statement, and an "
                "observation that would count against it."
            )
        return self._brain.process(
            BrainRequest(
                message="Propose research hypothesis",
                source="desktop",
                metadata={"intent": "research_hypothesis_propose", **values},
            )
        )

    def support_hypothesis(
        self,
        hypothesis_id: str,
        evidence_ids: str,
    ) -> BrainResponse:
        """Attach already-recorded evidence to the supporting side."""
        return self._hypothesis_evidence_request(
            "research_hypothesis_support",
            "Support research hypothesis",
            hypothesis_id,
            evidence_ids,
        )

    def associate_hypothesis_test_evidence(
        self,
        hypothesis_id: str,
        evidence_ids: str,
    ) -> BrainResponse:
        """Record that this evidence addresses the discriminating test.

        A different statement from supporting or opposing, and deliberately a
        separate control: evidence can bear on a hypothesis without touching
        the question it was built around, and only a person can say which did.
        Nothing is executed — the test is prose describing an observation, and
        this records that one was made.
        """
        return self._hypothesis_evidence_request(
            "research_hypothesis_test_evidence",
            "Record evidence addressing the hypothesis test",
            hypothesis_id,
            evidence_ids,
        )

    def hypothesis_history(self, hypothesis_id: str) -> BrainResponse:
        """Read one hypothesis's standing and withdrawn statements.

        A read, and only a read: it records nothing, decides nothing, and the
        controls that change a hypothesis stay where they were.
        """
        normalized = hypothesis_id.strip()
        if not normalized:
            raise ValueError("A hypothesis ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Read hypothesis history",
                source="desktop",
                metadata={
                    "intent": "research_hypothesis_history",
                    "hypothesis_id": normalized,
                },
            )
        )

    def retract_hypothesis_evidence_relation(
        self,
        hypothesis_id: str,
        evidence_id: str,
        relation: str,
    ) -> BrainResponse:
        """Take back one authored statement about evidence and a hypothesis.

        One operation for all three relations, taking identifiers and a named
        relation. It withdraws a statement; it does not delete the evidence, the
        hypothesis, or anything else, and it decides nothing about which way the
        evidence cuts.
        """
        normalized_hypothesis = hypothesis_id.strip()
        normalized_evidence = evidence_id.strip()
        normalized_relation = relation.strip()
        if not normalized_hypothesis:
            raise ValueError("A hypothesis ID cannot be empty.")
        if not normalized_evidence:
            raise ValueError("An evidence ID cannot be empty.")
        if not normalized_relation:
            raise ValueError("A relation cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Retract hypothesis evidence relation",
                source="desktop",
                metadata={
                    "intent": "research_hypothesis_retract_relation",
                    "hypothesis_id": normalized_hypothesis,
                    "evidence_id": normalized_evidence,
                    "relation": normalized_relation,
                },
            )
        )

    def oppose_hypothesis(
        self,
        hypothesis_id: str,
        evidence_ids: str,
    ) -> BrainResponse:
        """Attach already-recorded evidence to the opposing side."""
        return self._hypothesis_evidence_request(
            "research_hypothesis_oppose",
            "Oppose research hypothesis",
            hypothesis_id,
            evidence_ids,
        )

    def withdraw_hypothesis(self, hypothesis_id: str) -> BrainResponse:
        """Stop working on one hypothesis without deleting what it recorded."""
        normalized_id = hypothesis_id.strip()
        if not normalized_id:
            raise ValueError("A hypothesis ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Withdraw research hypothesis",
                source="desktop",
                metadata={
                    "intent": "research_hypothesis_withdraw",
                    "hypothesis_id": normalized_id,
                },
            )
        )

    def list_hypotheses(self) -> BrainResponse:
        """Report every hypothesis with the standing derived from its evidence."""
        return self._brain.process(
            BrainRequest(
                message="List research hypotheses",
                source="desktop",
                metadata={"intent": "research_hypothesis_list"},
            )
        )

    def preview_failure_lessons(self, research_run_id: str) -> BrainResponse:
        """Show what would be remembered from one run, remembering nothing."""
        return self._run_only_request(
            "failure_memory_preview",
            "Preview failure lessons",
            research_run_id,
        )

    def store_failure_lessons(self, research_run_id: str) -> BrainResponse:
        """Remember the lessons one run's own record supports."""
        return self._run_only_request(
            "failure_memory_store",
            "Remember failure lessons",
            research_run_id,
        )

    def remember_hypothesis_outcomes(self, research_run_id: str) -> BrainResponse:
        """Remember the durable weakened and contradicted hypotheses of one run."""
        return self._run_only_request(
            "failure_memory_hypothesis_store",
            "Remember hypothesis outcomes",
            research_run_id,
        )

    def recall_failure_lessons(self, research_question: str) -> BrainResponse:
        """Ask which remembered lessons overlap a question. Advisory only."""
        normalized_question = research_question.strip()
        if not normalized_question:
            raise ValueError("A research question cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Recall failure lessons",
                source="desktop",
                metadata={
                    "intent": "failure_memory_recall",
                    "research_question": normalized_question,
                },
            )
        )

    def list_failure_lessons(self) -> BrainResponse:
        """Report everything remembered, deriving nothing new."""
        return self._brain.process(
            BrainRequest(
                message="List failure lessons",
                source="desktop",
                metadata={"intent": "failure_memory_list"},
            )
        )

    def _hypothesis_evidence_request(
        self,
        intent: str,
        message: str,
        hypothesis_id: str,
        evidence_ids: str,
    ) -> BrainResponse:
        normalized_id = hypothesis_id.strip()
        if not normalized_id:
            raise ValueError("A hypothesis ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message=message,
                source="desktop",
                metadata={
                    "intent": intent,
                    "hypothesis_id": normalized_id,
                    "evidence_ids": _evidence_id_list(evidence_ids),
                },
            )
        )

    def record_vulnerability_family(
        self,
        family_id: str,
        name: str,
        summary: str,
        prevention: str,
    ) -> BrainResponse:
        """Record one class of weakness, asserting nothing about any system.

        There is deliberately no argument for a host, a product, a version, or
        a payload. The domain type has nowhere to put them, and this adapter
        does not invent a place.
        """
        values = {
            "family_id": family_id.strip(),
            "family_name": name.strip(),
            "family_summary": summary.strip(),
            "family_prevention": prevention.strip(),
        }
        if not all(values.values()):
            raise ValueError(
                "A weakness class needs an ID, a name, a summary, and a "
                "prevention note."
            )
        return self._brain.process(
            BrainRequest(
                message="Record vulnerability family",
                source="desktop",
                metadata={"intent": "vulnerability_family_record", **values},
            )
        )

    def record_vulnerability_relation(
        self,
        from_family_id: str,
        to_family_id: str,
        relation_kind: str,
        rationale: str,
    ) -> BrainResponse:
        """Relate two weakness classes, with the reason recorded alongside.

        The rationale is required here rather than optional. An edge nobody
        explained is the kind a later reader trusts without being able to
        check it.
        """
        values = {
            "from_family_id": from_family_id.strip(),
            "to_family_id": to_family_id.strip(),
            "relation_kind": relation_kind.strip(),
            "relation_rationale": rationale.strip(),
        }
        if not all(values.values()):
            raise ValueError(
                "A relation needs both weakness classes, a kind, and a reason."
            )
        return self._brain.process(
            BrainRequest(
                message="Record vulnerability relation",
                source="desktop",
                metadata={"intent": "vulnerability_relation_record", **values},
            )
        )

    def vulnerability_neighbourhood(
        self,
        family_id: str,
        max_depth: int = 1,
    ) -> BrainResponse:
        """Ask what else is worth reading about near one weakness class."""
        normalized_id = family_id.strip()
        if not normalized_id:
            raise ValueError("A weakness class ID cannot be empty.")
        if isinstance(max_depth, bool) or not isinstance(max_depth, int):
            raise ValueError("Traversal depth must be a whole number.")
        return self._brain.process(
            BrainRequest(
                message="Report vulnerability neighbourhood",
                source="desktop",
                metadata={
                    "intent": "vulnerability_family_neighbourhood",
                    "family_id": normalized_id,
                    "max_depth": max_depth,
                },
            )
        )

    def list_vulnerability_families(self) -> BrainResponse:
        """List every recorded weakness class without traversing anything."""
        return self._brain.process(
            BrainRequest(
                message="List vulnerability families",
                source="desktop",
                metadata={"intent": "vulnerability_family_list"},
            )
        )

    def audit_learned_memory(self) -> BrainResponse:
        """Request the read-only learned-memory health report without writing."""
        return self._brain.process(
            BrainRequest(
                message="Audit learned memory",
                source="desktop",
                metadata={"intent": "learned_memory_audit"},
            )
        )

    def list_research_runs(self) -> BrainResponse:
        """List persistent research runs without fetching a network source."""
        return self._brain.process(
            BrainRequest(
                message="List internet research runs",
                source="desktop",
                metadata={"intent": "research_run_list"},
            )
        )

    def preview_research_run_markdown_export(
        self,
        research_run_id: str,
    ) -> BrainResponse:
        """Preview one terminal run as Markdown without writing a file."""
        normalized_run_id = research_run_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Preview terminal research run as Markdown",
                source="desktop",
                metadata={
                    "intent": "research_run_markdown_export_preview",
                    "research_run_id": normalized_run_id,
                },
            )
        )

    def save_research_run_markdown_export(
        self,
        preview: ResearchRunMarkdownExportPreview,
        destination_path: str,
    ) -> BrainResponse:
        """Request one exact preview be saved to an explicitly selected new file."""
        if not isinstance(preview, ResearchRunMarkdownExportPreview):
            raise ValueError("A research Markdown export preview is required.")
        normalized_destination = destination_path.strip()
        if not normalized_destination:
            raise ValueError("A research export destination cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Save previewed research run as Markdown",
                source="desktop",
                metadata={
                    "intent": "research_run_markdown_export_save",
                    "research_run_id": preview.run_id,
                    "research_export_snapshot_updated_at": (
                        preview.snapshot_updated_at.isoformat()
                    ),
                    "research_export_content_sha256": preview.content_sha256,
                    "research_export_destination_path": normalized_destination,
                },
            )
        )

    def verify_research_run_markdown_export(
        self,
        research_run_id: str,
        source_path: str,
    ) -> BrainResponse:
        """Compare one selected Markdown file with the current terminal run."""
        normalized_run_id = research_run_id.strip()
        normalized_source = source_path.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not normalized_source:
            raise ValueError("A research export verification file cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Verify existing research Markdown export",
                source="desktop",
                metadata={
                    "intent": "research_run_markdown_export_verify",
                    "research_run_id": normalized_run_id,
                    "research_export_source_path": normalized_source,
                },
            )
        )

    def discover_research_sources(
        self,
        research_run_id: str,
        provider: str = "",
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> BrainResponse:
        """Discover candidate metadata for one run without loading content."""
        normalized_run_id = research_run_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        metadata: dict[str, object] = {
            "intent": "research_source_discover",
            "research_run_id": normalized_run_id,
        }
        # Resolved here so a name that is not a provider never reaches the
        # request at all. Anything outside the closed vocabulary is refused
        # rather than passed along to be interpreted somewhere else.
        if provider.strip():
            try:
                metadata["research_discovery_provider"] = ResearchDiscoveryProviderName(
                    provider.strip()
                ).value
            except ValueError as error:
                raise ValueError("Research discovery provider is unknown.") from error
        return self._brain.process(
            BrainRequest(
                message="Discover candidate research sources",
                source="desktop",
                metadata=metadata,
                cancellation_token=cancellation_token,
            )
        )

    def record_research_evidence(
        self,
        research_run_id: str,
        chunk_id: str,
        note: str,
    ) -> BrainResponse:
        """Record one explicit indexed paragraph as research evidence."""
        normalized_run_id = research_run_id.strip()
        normalized_chunk_id = chunk_id.strip()
        normalized_note = note.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not normalized_chunk_id:
            raise ValueError("A research chunk ID cannot be empty.")
        if not normalized_note:
            raise ValueError("A research evidence note cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Record selected research evidence",
                source="desktop",
                metadata={
                    "intent": "research_evidence_record",
                    "research_run_id": normalized_run_id,
                    "research_chunk_id": normalized_chunk_id,
                    "research_evidence_note": normalized_note,
                },
            )
        )

    def list_research_evidence(self, research_run_id: str) -> BrainResponse:
        """List persisted bounded evidence for one explicitly selected run."""
        normalized_run_id = research_run_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="List selected research evidence",
                source="desktop",
                metadata={
                    "intent": "research_evidence_list",
                    "research_run_id": normalized_run_id,
                },
            )
        )

    def preview_research_claims(self, research_run_id: str) -> BrainResponse:
        """Show persisted claim history for one exact research run."""
        normalized_run_id = research_run_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="View evidence-linked research claims",
                source="desktop",
                metadata={
                    "intent": "research_claim_preview",
                    "research_run_id": normalized_run_id,
                },
            )
        )

    def preview_research_claim_write(
        self,
        research_run_id: str,
        evidence_ids: str,
        claim_text: str,
        epistemic_state: str,
        confidence: str = ResearchClaimConfidence.UNASSESSED.value,
        supersedes_claim_id: str = "",
    ) -> BrainResponse:
        """Preview one explicit evidence-linked claim without writing it."""
        metadata = self._research_claim_write_metadata(
            research_run_id,
            evidence_ids,
            claim_text,
            epistemic_state,
            confidence,
            supersedes_claim_id,
        )
        return self._brain.process(
            BrainRequest(
                message="Preview user-authored research claim",
                source="desktop",
                metadata={"intent": "research_claim_write_preview", **metadata},
            )
        )

    def record_research_claim(
        self,
        research_run_id: str,
        evidence_ids: str,
        claim_text: str,
        epistemic_state: str,
        confidence: str = ResearchClaimConfidence.UNASSESSED.value,
        supersedes_claim_id: str = "",
    ) -> BrainResponse:
        """Submit one claim only after desktop confirmation."""
        metadata = self._research_claim_write_metadata(
            research_run_id,
            evidence_ids,
            claim_text,
            epistemic_state,
            confidence,
            supersedes_claim_id,
        )
        return self._brain.process(
            BrainRequest(
                message="Record user-authored research claim",
                source="desktop",
                metadata={"intent": "research_claim_record", **metadata},
            )
        )

    @staticmethod
    def _research_claim_write_metadata(
        research_run_id: str,
        evidence_ids: str,
        claim_text: str,
        epistemic_state: str,
        confidence: str = ResearchClaimConfidence.UNASSESSED.value,
        supersedes_claim_id: str = "",
    ) -> dict[str, object]:
        normalized_run_id = research_run_id.strip()
        normalized_text = claim_text.strip()
        normalized_superseded_id = supersedes_claim_id.strip()
        normalized_evidence_ids = [
            value.strip() for value in evidence_ids.split(",") if value.strip()
        ]
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not normalized_evidence_ids:
            raise ValueError("Research claim evidence IDs cannot be empty.")
        if len(normalized_evidence_ids) != len(set(normalized_evidence_ids)):
            raise ValueError("Research claim evidence IDs cannot be duplicated.")
        if not normalized_text:
            raise ValueError("Research claim text cannot be empty.")
        try:
            normalized_state = ResearchEpistemicState(epistemic_state.strip())
        except (AttributeError, ValueError) as error:
            raise ValueError("Research claim epistemic state is invalid.") from error
        try:
            normalized_confidence = ResearchClaimConfidence(confidence.strip())
        except (AttributeError, ValueError) as error:
            raise ValueError("Research claim confidence is invalid.") from error
        metadata: dict[str, object] = {
            "research_run_id": normalized_run_id,
            "research_claim_evidence_ids": normalized_evidence_ids,
            "research_claim_text": normalized_text,
            "research_claim_epistemic_state": normalized_state.value,
            "research_claim_confidence": normalized_confidence.value,
        }
        if normalized_superseded_id:
            metadata["research_claim_supersedes_id"] = normalized_superseded_id
        return metadata

    def preview_research_claim_contradictions(
        self,
        research_run_id: str,
    ) -> BrainResponse:
        """Show persisted user-reviewed claim contradictions for one run."""
        normalized_run_id = research_run_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="View user-reviewed research claim contradictions",
                source="desktop",
                metadata={
                    "intent": "research_claim_contradiction_preview",
                    "research_run_id": normalized_run_id,
                },
            )
        )

    def suggest_research_claim_contradictions(
        self,
        research_run_id: str,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> BrainResponse:
        """Request read-only candidates without recording a relationship."""
        normalized_run_id = research_run_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="suggest research claim contradictions",
                metadata={
                    "intent": "research_claim_contradiction_proposal",
                    "research_run_id": normalized_run_id,
                },
                cancellation_token=cancellation_token,
            )
        )

    def preview_research_claim_contradiction_write(
        self,
        research_run_id: str,
        claim_ids: str,
        note: str,
    ) -> BrainResponse:
        """Preview one exact user-authored contradiction relationship."""
        metadata = self._research_claim_contradiction_metadata(
            research_run_id,
            claim_ids,
            note,
        )
        return self._brain.process(
            BrainRequest(
                message="Preview user-reviewed research claim contradiction",
                source="desktop",
                metadata={
                    "intent": "research_claim_contradiction_write_preview",
                    **metadata,
                },
            )
        )

    def record_research_claim_contradiction(
        self,
        research_run_id: str,
        claim_ids: str,
        note: str,
    ) -> BrainResponse:
        """Submit one contradiction only after desktop confirmation."""
        metadata = self._research_claim_contradiction_metadata(
            research_run_id,
            claim_ids,
            note,
        )
        return self._brain.process(
            BrainRequest(
                message="Record user-reviewed research claim contradiction",
                source="desktop",
                metadata={
                    "intent": "research_claim_contradiction_record",
                    **metadata,
                },
            )
        )

    @staticmethod
    def _research_claim_contradiction_metadata(
        research_run_id: str,
        claim_ids: str,
        note: str,
    ) -> dict[str, object]:
        normalized_run_id = research_run_id.strip()
        normalized_claim_ids = [
            value.strip() for value in claim_ids.split(",") if value.strip()
        ]
        normalized_note = note.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if len(normalized_claim_ids) != 2:
            raise ValueError(
                "Research claim contradiction requires exactly two claim IDs."
            )
        if normalized_claim_ids[0] == normalized_claim_ids[1]:
            raise ValueError(
                "Research claim contradiction requires two distinct claims."
            )
        if not normalized_note:
            raise ValueError("Research claim contradiction note cannot be empty.")
        return {
            "research_run_id": normalized_run_id,
            "research_claim_contradiction_claim_ids": normalized_claim_ids,
            "research_claim_contradiction_note": normalized_note,
        }

    def preview_research_source_assessment(
        self,
        research_run_id: str,
        source_document_id: str,
    ) -> BrainResponse:
        """Preview accepted provenance and user-selected evidence only."""
        normalized_run_id = research_run_id.strip()
        normalized_document_id = source_document_id.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not normalized_document_id:
            raise ValueError("A research source document ID cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message="Preview accepted research source assessment",
                source="desktop",
                metadata={
                    "intent": "research_source_assessment_preview",
                    "research_run_id": normalized_run_id,
                    "research_source_document_id": normalized_document_id,
                },
            )
        )

    def preview_research_source_comparison(
        self,
        research_run_id: str,
        source_document_ids: str,
    ) -> BrainResponse:
        """Preview 2-5 explicitly selected accepted sources side by side."""
        normalized_run_id = research_run_id.strip()
        normalized_document_ids = [
            value.strip() for value in source_document_ids.split(",") if value.strip()
        ]
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not 2 <= len(normalized_document_ids) <= 5:
            raise ValueError("Enter 2 to 5 research source document IDs.")
        if len(normalized_document_ids) != len(set(normalized_document_ids)):
            raise ValueError("Research source document IDs must be unique.")
        return self._brain.process(
            BrainRequest(
                message="Preview selected research sources side by side",
                source="desktop",
                metadata={
                    "intent": "research_source_comparison_preview",
                    "research_run_id": normalized_run_id,
                    "research_source_document_ids": normalized_document_ids,
                },
            )
        )

    def preview_research_source_comparison_note_write(
        self,
        research_run_id: str,
        source_document_ids: str,
        evidence_ids: str,
        assessment_ids: str,
        note_text: str,
    ) -> BrainResponse:
        """Preview one authored comparison note and its exact references."""
        metadata = self._research_source_comparison_note_metadata(
            research_run_id,
            source_document_ids,
            evidence_ids,
            assessment_ids,
            note_text,
        )
        return self._brain.process(
            BrainRequest(
                message="Preview user-authored research comparison note",
                source="desktop",
                metadata={
                    "intent": "research_source_comparison_note_write_preview",
                    **metadata,
                },
            )
        )

    def record_research_source_comparison_note(
        self,
        research_run_id: str,
        source_document_ids: str,
        evidence_ids: str,
        assessment_ids: str,
        note_text: str,
    ) -> BrainResponse:
        """Submit one comparison note only after desktop confirmation."""
        metadata = self._research_source_comparison_note_metadata(
            research_run_id,
            source_document_ids,
            evidence_ids,
            assessment_ids,
            note_text,
        )
        return self._brain.process(
            BrainRequest(
                message="Record user-authored research comparison note",
                source="desktop",
                metadata={
                    "intent": "research_source_comparison_note_record",
                    **metadata,
                },
            )
        )

    @staticmethod
    def _research_source_comparison_note_metadata(
        research_run_id: str,
        source_document_ids: str,
        evidence_ids: str,
        assessment_ids: str,
        note_text: str,
    ) -> dict[str, object]:
        normalized_run_id = research_run_id.strip()
        normalized_text = note_text.strip()
        normalized_document_ids = [
            value.strip() for value in source_document_ids.split(",") if value.strip()
        ]
        normalized_evidence_ids = [
            value.strip() for value in evidence_ids.split(",") if value.strip()
        ]
        normalized_assessment_ids = [
            value.strip() for value in assessment_ids.split(",") if value.strip()
        ]
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not 2 <= len(normalized_document_ids) <= 5:
            raise ValueError("Enter 2 to 5 research source document IDs.")
        for values, label in (
            (normalized_document_ids, "Research source document IDs"),
            (normalized_evidence_ids, "Research comparison evidence IDs"),
            (normalized_assessment_ids, "Research comparison assessment IDs"),
        ):
            if not values:
                raise ValueError(f"{label} cannot be empty.")
            if len(values) != len(set(values)):
                raise ValueError(f"{label} cannot be duplicated.")
        if not normalized_text:
            raise ValueError("Research comparison note text cannot be empty.")
        return {
            "research_run_id": normalized_run_id,
            "research_source_document_ids": normalized_document_ids,
            "research_comparison_evidence_ids": normalized_evidence_ids,
            "research_comparison_assessment_ids": normalized_assessment_ids,
            "research_comparison_note_text": normalized_text,
        }

    def preview_research_source_assessment_write(
        self,
        research_run_id: str,
        source_document_id: str,
        evidence_ids: str,
        assessment_text: str,
        supersedes_assessment_id: str = "",
        information_trust: str = ResearchInformationTrust.UNASSESSED.value,
        usefulness: str = ResearchSourceUsefulness.UNKNOWN.value,
        applicability: str = ResearchSourceApplicability.UNKNOWN.value,
        independence: str = ResearchSourceIndependence.UNKNOWN.value,
        publication_status: str = ResearchSourcePublicationStatus.UNKNOWN.value,
    ) -> BrainResponse:
        """Preview an authored assessment with explicit evidence references."""
        metadata = self._research_source_assessment_write_metadata(
            research_run_id,
            source_document_id,
            evidence_ids,
            assessment_text,
            supersedes_assessment_id,
            information_trust,
            usefulness,
            applicability,
            independence,
            publication_status,
        )
        return self._brain.process(
            BrainRequest(
                message="Preview user-authored research source assessment",
                source="desktop",
                metadata={
                    "intent": "research_source_assessment_write_preview",
                    **metadata,
                },
            )
        )

    def record_research_source_assessment(
        self,
        research_run_id: str,
        source_document_id: str,
        evidence_ids: str,
        assessment_text: str,
        supersedes_assessment_id: str = "",
        information_trust: str = ResearchInformationTrust.UNASSESSED.value,
        usefulness: str = ResearchSourceUsefulness.UNKNOWN.value,
        applicability: str = ResearchSourceApplicability.UNKNOWN.value,
        independence: str = ResearchSourceIndependence.UNKNOWN.value,
        publication_status: str = ResearchSourcePublicationStatus.UNKNOWN.value,
    ) -> BrainResponse:
        """Submit one assessment only after the desktop confirmation step."""
        metadata = self._research_source_assessment_write_metadata(
            research_run_id,
            source_document_id,
            evidence_ids,
            assessment_text,
            supersedes_assessment_id,
            information_trust,
            usefulness,
            applicability,
            independence,
            publication_status,
        )
        return self._brain.process(
            BrainRequest(
                message="Record user-authored research source assessment",
                source="desktop",
                metadata={
                    "intent": "research_source_assessment_record",
                    **metadata,
                },
            )
        )

    @staticmethod
    def _research_source_assessment_write_metadata(
        research_run_id: str,
        source_document_id: str,
        evidence_ids: str,
        assessment_text: str,
        supersedes_assessment_id: str = "",
        information_trust: str = ResearchInformationTrust.UNASSESSED.value,
        usefulness: str = ResearchSourceUsefulness.UNKNOWN.value,
        applicability: str = ResearchSourceApplicability.UNKNOWN.value,
        independence: str = ResearchSourceIndependence.UNKNOWN.value,
        publication_status: str = ResearchSourcePublicationStatus.UNKNOWN.value,
    ) -> dict[str, object]:
        normalized_run_id = research_run_id.strip()
        normalized_document_id = source_document_id.strip()
        normalized_text = assessment_text.strip()
        normalized_superseded_id = supersedes_assessment_id.strip()
        try:
            normalized_information_trust = ResearchInformationTrust(
                information_trust.strip()
            )
        except (AttributeError, ValueError) as error:
            raise ValueError("Research source information trust is invalid.") from error
        try:
            normalized_judgement = {
                "research_source_usefulness": ResearchSourceUsefulness(
                    usefulness.strip()
                ).value,
                "research_source_applicability": ResearchSourceApplicability(
                    applicability.strip()
                ).value,
                "research_source_independence": ResearchSourceIndependence(
                    independence.strip()
                ).value,
                "research_source_publication_status": ResearchSourcePublicationStatus(
                    publication_status.strip()
                ).value,
            }
        except (AttributeError, ValueError) as error:
            raise ValueError("Research source judgement is invalid.") from error
        normalized_evidence_ids = [
            value.strip() for value in evidence_ids.split(",") if value.strip()
        ]
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not normalized_document_id:
            raise ValueError("A research source document ID cannot be empty.")
        if not normalized_evidence_ids:
            raise ValueError("Research assessment evidence IDs cannot be empty.")
        if len(normalized_evidence_ids) != len(set(normalized_evidence_ids)):
            raise ValueError("Research assessment evidence IDs cannot be duplicated.")
        if not normalized_text:
            raise ValueError("Research source assessment text cannot be empty.")
        metadata: dict[str, object] = {
            "research_run_id": normalized_run_id,
            "research_source_document_id": normalized_document_id,
            "research_assessment_evidence_ids": normalized_evidence_ids,
            "research_assessment_text": normalized_text,
            "research_information_trust": normalized_information_trust.value,
            **normalized_judgement,
        }
        if normalized_superseded_id:
            metadata["research_assessment_supersedes_id"] = normalized_superseded_id
        return metadata

    def preview_research_run_status(
        self,
        research_run_id: str,
        target_status: str,
    ) -> BrainResponse:
        """Preview one requested terminal research status without mutation."""
        return self._research_status_request(
            "research_run_status_preview",
            "Preview selected research status",
            research_run_id,
            target_status,
        )

    def update_research_run_status(
        self,
        research_run_id: str,
        target_status: str,
    ) -> BrainResponse:
        """Apply one terminal status only after the desktop preview."""
        return self._research_status_request(
            "research_run_status_update",
            "Update selected research status",
            research_run_id,
            target_status,
        )

    def load_research_source(
        self,
        url: str,
        research_run_id: str = "",
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> BrainResponse:
        """Load one explicit HTTPS source, optionally attaching it to a run."""
        normalized_url = url.strip()
        if not normalized_url:
            raise ValueError("A research source URL cannot be empty.")
        normalized_run_id = research_run_id.strip()
        metadata = {
            "intent": "research_source_load",
            "research_url": normalized_url,
        }
        if normalized_run_id:
            metadata["research_run_id"] = normalized_run_id
        return self._brain.process(
            BrainRequest(
                message="Load selected internet research source",
                source="desktop",
                metadata=metadata,
                cancellation_token=cancellation_token,
            )
        )

    def preview_research_source_candidate_acceptance(
        self,
        research_run_id: str,
        discovery_id: str,
        candidate_url: str,
    ) -> BrainResponse:
        """Preview one persisted discovery candidate without loading it."""
        return self._research_candidate_request(
            "research_source_candidate_acceptance_preview",
            "Preview selected research source candidate",
            research_run_id,
            discovery_id,
            candidate_url,
        )

    def accept_research_source_candidate(
        self,
        research_run_id: str,
        discovery_id: str,
        candidate_url: str,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> BrainResponse:
        """Accept one confirmed candidate through the guarded source loader."""
        return self._research_candidate_request(
            "research_source_candidate_accept",
            "Accept selected research source candidate",
            research_run_id,
            discovery_id,
            candidate_url,
            cancellation_token=cancellation_token,
        )

    def _research_candidate_request(
        self,
        intent: str,
        message: str,
        research_run_id: str,
        discovery_id: str,
        candidate_url: str,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> BrainResponse:
        normalized_run_id = research_run_id.strip()
        normalized_discovery_id = discovery_id.strip()
        normalized_url = candidate_url.strip()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if not normalized_discovery_id:
            raise ValueError("A research source discovery ID cannot be empty.")
        if not normalized_url:
            raise ValueError("A research source candidate URL cannot be empty.")
        return self._brain.process(
            BrainRequest(
                message=message,
                source="desktop",
                metadata={
                    "intent": intent,
                    "research_run_id": normalized_run_id,
                    "research_discovery_id": normalized_discovery_id,
                    "research_url": normalized_url,
                },
                cancellation_token=cancellation_token,
            )
        )

    def preview_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Validate a requested local document relation without changing it."""
        return self._knowledge_relation_command(
            "preview knowledge relation",
            source_document_id,
            target_document_id,
        )

    def apply_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Apply a relation only after the desktop has shown its preview."""
        return self._knowledge_relation_command(
            "apply knowledge relation",
            source_document_id,
            target_document_id,
        )

    def preview_knowledge_relation_removal(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Validate removal of an existing relation without changing it."""
        return self._knowledge_relation_command(
            "preview remove knowledge relation",
            source_document_id,
            target_document_id,
        )

    def remove_knowledge_relation(
        self,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Remove a relation only after its desktop preview is confirmed."""
        return self._knowledge_relation_command(
            "remove knowledge relation",
            source_document_id,
            target_document_id,
        )

    def list_knowledge(self) -> BrainResponse:
        """Request the existing read-only catalog of loaded local sources."""
        return self._brain.process("list knowledge")

    def list_knowledge_relations(self) -> BrainResponse:
        """Request the read-only catalog of active local source relations."""
        return self._brain.process("list knowledge relations")

    def semantic_status(self) -> BrainResponse:
        """Request the read-only semantic runtime status without a query."""
        return self._brain.process("semantic recall status")

    def research_content_status(self) -> BrainResponse:
        """Request the captured accepted-content startup restoration status."""
        return self._brain.process("research content status")

    def research_evidence_status(self) -> BrainResponse:
        """Request the read-only evidence-to-restored-content integrity audit."""
        return self._brain.process("research evidence status")

    def _selected_session_command(
        self,
        command: str,
        session_id: str,
    ) -> BrainResponse:
        """Keep session-specific desktop actions explicit and side-effect free."""
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            raise ValueError("A session ID cannot be empty.")
        return self._brain.process(f"{command} {normalized_session_id}")

    def _recall_command(self, command: str, query: str) -> BrainResponse:
        """Keep memory retrieval user-initiated and reject empty queries locally."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("A recall query cannot be empty.")
        return self._brain.process(f"{command} {normalized_query}")

    def _session_rename_command(
        self,
        command: str,
        source_session_id: str,
        target_session_id: str,
    ) -> BrainResponse:
        """Keep desktop rename input explicit before the transactional runtime path."""
        source_id = source_session_id.strip()
        target_id = target_session_id.strip()
        if not source_id or not target_id:
            raise ValueError("Both session IDs are required for a rename.")
        return self._brain.process(f"{command} {source_id} -- {target_id}")

    def _knowledge_command(self, command: str, query: str) -> BrainResponse:
        """Keep local knowledge retrieval explicit and query-bounded."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("A knowledge query cannot be empty.")
        return self._brain.process(f"{command} {normalized_query}")

    def _knowledge_relation_command(
        self,
        command: str,
        source_document_id: str,
        target_document_id: str,
    ) -> BrainResponse:
        """Send two explicit document IDs through the existing relation boundary."""
        source_id = source_document_id.strip()
        target_id = target_document_id.strip()
        if not source_id or not target_id:
            raise ValueError("Both knowledge source IDs are required.")
        return self._brain.process(f"{command} {source_id} -- {target_id}")

    def _research_status_request(
        self,
        intent: str,
        message: str,
        research_run_id: str,
        target_status: str,
    ) -> BrainResponse:
        normalized_run_id = research_run_id.strip()
        normalized_status = target_status.strip().casefold()
        if not normalized_run_id:
            raise ValueError("A research run ID cannot be empty.")
        if normalized_status not in {"completed", "failed", "cancelled"}:
            raise ValueError("A valid terminal research status is required.")
        return self._brain.process(
            BrainRequest(
                message=message,
                source="desktop",
                metadata={
                    "intent": intent,
                    "research_run_id": normalized_run_id,
                    "research_target_status": normalized_status,
                },
            )
        )
