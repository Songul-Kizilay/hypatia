"""Why an execution cannot take another step, from its state alone.

This is the part of autonomy's stop decision that depends only on the execution
itself: a step that failed, blocked or was interrupted, an execution that has
already closed, or nothing left to do. The rest of that decision — budgets,
elapsed time, a cancellation token — belongs to a particular run and is not
answerable from state.

It lives on its own because two callers need the same answer at different
moments. Autonomy asks before each advance. The scheduler asks once, at
creation, so it does not queue a durable task against an execution that could
never move. Two hand-written copies of this would drift, and the copy that
drifted would be the one deciding what to refuse.

Pure: reads state, touches nothing, and can never make anything happen.
"""

from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchPlanExecutionState import ResearchPlanExecutionState
from research.ResearchPlanStepStatus import ResearchPlanStepStatus

#: Step outcomes that halt the loop, in the order autonomy reports them. Each
#: one is a fact about an attempt that already happened, so a step-level answer
#: comes before the execution-level one: "the execution is terminal" would be
#: true but would hide why it became terminal.
_HALTING_STEP_STATUSES = (
    (ResearchPlanStepStatus.FAILED, AutonomyStopReason.STEP_FAILED),
    (ResearchPlanStepStatus.BLOCKED, AutonomyStopReason.STEP_BLOCKED),
    (ResearchPlanStepStatus.INTERRUPTED, AutonomyStopReason.STEP_INTERRUPTED),
)


def progress_block(state: ResearchPlanExecutionState) -> AutonomyStopReason | None:
    """Return why this execution can take no step, or ``None`` if it can.

    ``None`` says only that the next step is not blocked by the execution's own
    state. It is not a promise the step will succeed, and not a promise the
    state will still allow it later.
    """
    for step_status, reason in _HALTING_STEP_STATUSES:
        if any(step.status is step_status for step in state.steps):
            return reason
    if state.status.terminal:
        return AutonomyStopReason.EXECUTION_TERMINAL
    if state.next_pending_step_id is None:
        return AutonomyStopReason.NO_PENDING_STEP
    return None
