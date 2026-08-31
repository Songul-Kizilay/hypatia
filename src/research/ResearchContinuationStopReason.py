"""Why a bounded foreground continuation stopped when it did."""

from __future__ import annotations

from enum import Enum


class ResearchContinuationStopReason(Enum):
    """The bounded vocabulary for why stepping stopped.

    Every one of these is a stop, including `BOUND_REACHED`. There is no value
    meaning "still going", because a continuation has always finished by the
    time it is described: it runs in the foreground, in one call, and returns
    when it is over.

    They are kept distinct rather than collapsed into "refused" because the
    difference matters to whoever reads it. Running out of budget, hitting a
    step nothing can perform, and being cancelled all end the same run, and an
    operator deciding what to do next needs to know which one happened.
    """

    BOUND_REACHED = "bound_reached"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NO_PENDING_STEP = "no_pending_step"
    ADVANCE_REFUSED = "advance_refused"
