"""Pure encode and decode for durable research-plan execution snapshots.

Stage 1 of execution persistence: a codec only. It performs no file access, no
mutation, and no restore policy; it converts between an in-memory execution
snapshot and its document form and refuses anything malformed.

What is persisted is deliberately narrow. Step identity, declared capability,
status, operation identity, `work_performed`, bounded detail, plus the plan
question and the bound run identity. Fetched page bodies, source excerpts,
authored notes, claim text, and authorization payloads are never written here:
those already live in the research run, and duplicating them would create a
second store of the same facts.

`work_performed` is never inferred at load time. A record claiming performed
work without naming its operation is invalid, exactly as in memory.

Version 2 adds the approved budget and what was spent against it. Version 1
records decode with no allowance, which is what they truthfully had: nothing
enforced a budget when they were written. Reading a missing allowance as a full
fresh budget would be the dangerous direction, because an old execution would
appear to have everything left.
"""

from __future__ import annotations

from typing import Any

from core.Exceptions import ResearchError
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchExecutionSpend import ResearchExecutionSpend
from research.ResearchPlanExecutionSnapshot import (
    MAX_SNAPSHOT_DETAIL_CHARACTERS,
    MAX_SNAPSHOT_STEPS,
    ResearchPlanExecutionSnapshot,
    ResearchPlanExecutionStepSnapshot,
)
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepStatus import ResearchPlanStepStatus

_EXECUTION_FIELDS = frozenset(
    {
        "plan_id",
        "question",
        "status",
        "detail",
        "research_run_id",
        "recorded_at",
        "steps",
        "allowance",
    }
)
#: Version 1 wrote every field above except the last.
_EXECUTION_FIELDS_V1 = _EXECUTION_FIELDS - {"allowance"}
_ALLOWANCE_FIELDS = frozenset({"budget", "spend"})
_BUDGET_FIELDS = frozenset(
    {
        "max_step_advances",
        "max_network_operations",
        "max_llm_operations",
        "max_seconds",
    }
)
_SPEND_FIELDS = frozenset(
    {
        "step_advances",
        "network_operations",
        "llm_operations",
        "active_seconds",
    }
)
_STEP_FIELDS = frozenset(
    {
        "step_id",
        "capability",
        "status",
        "detail",
        "operation",
        "work_performed",
    }
)


def encode_execution_snapshot(
    snapshot: ResearchPlanExecutionSnapshot,
) -> dict[str, Any]:
    """Return the document form of one execution snapshot."""
    if not isinstance(snapshot, ResearchPlanExecutionSnapshot):
        raise ResearchError("Execution snapshot is invalid.")
    return {
        "plan_id": snapshot.plan_id,
        "question": snapshot.question,
        "status": snapshot.status.value,
        "detail": snapshot.detail,
        "research_run_id": snapshot.research_run_id,
        "recorded_at": snapshot.recorded_at.isoformat(),
        "allowance": _encode_allowance(snapshot.allowance),
        "steps": [
            {
                "step_id": step.step_id,
                "capability": step.capability.value,
                "status": step.status.value,
                "detail": step.detail,
                "operation": step.operation,
                "work_performed": step.work_performed,
            }
            for step in snapshot.steps
        ],
    }


def decode_execution_snapshot(document: object) -> ResearchPlanExecutionSnapshot:
    """Return one validated snapshot, or refuse a malformed document."""
    if not isinstance(document, dict) or set(document) not in (
        _EXECUTION_FIELDS,
        _EXECUTION_FIELDS_V1,
    ):
        raise ResearchError("Execution snapshot document is invalid.")
    steps_value = document["steps"]
    if not isinstance(steps_value, list) or not steps_value:
        raise ResearchError("Execution snapshot requires step records.")
    if len(steps_value) > MAX_SNAPSHOT_STEPS:
        raise ResearchError("Execution snapshot has too many steps.")
    run_id = document["research_run_id"]
    if run_id is not None and not isinstance(run_id, str):
        raise ResearchError("Execution snapshot run ID is invalid.")
    return ResearchPlanExecutionSnapshot(
        plan_id=_text(document["plan_id"], "plan ID"),
        question=_text(document["question"], "question"),
        status=_enum(
            document["status"],
            ResearchPlanExecutionStatus,
            "execution status",
        ),
        detail=_detail(document["detail"]),
        research_run_id=run_id,
        recorded_at=_timestamp(document["recorded_at"]),
        allowance=_decode_allowance(document.get("allowance")),
        steps=tuple(_decode_step(value) for value in steps_value),
    )


def _encode_allowance(
    allowance: ResearchExecutionAllowance | None,
) -> dict[str, Any] | None:
    """Return the document form of one allowance, or null when unenforced."""
    if allowance is None:
        return None
    budget = allowance.budget
    spend = allowance.spend
    return {
        "budget": {
            "max_step_advances": budget.max_step_advances,
            "max_network_operations": budget.max_network_operations,
            "max_llm_operations": budget.max_llm_operations,
            "max_seconds": budget.max_seconds,
        },
        "spend": {
            "step_advances": spend.step_advances,
            "network_operations": spend.network_operations,
            "llm_operations": spend.llm_operations,
            "active_seconds": spend.active_seconds,
        },
    }


def _decode_allowance(value: object) -> ResearchExecutionAllowance | None:
    """Return one validated allowance, refusing a partial or unknown shape."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _ALLOWANCE_FIELDS:
        raise ResearchError("Execution snapshot allowance is invalid.")
    budget_value = value["budget"]
    spend_value = value["spend"]
    if not isinstance(budget_value, dict) or set(budget_value) != _BUDGET_FIELDS:
        raise ResearchError("Execution snapshot budget is invalid.")
    if not isinstance(spend_value, dict) or set(spend_value) != _SPEND_FIELDS:
        raise ResearchError("Execution snapshot spend is invalid.")
    return ResearchExecutionAllowance(
        budget=ResearchAutonomyBudget(
            max_step_advances=_count(budget_value["max_step_advances"]),
            max_network_operations=_count(budget_value["max_network_operations"]),
            max_llm_operations=_count(budget_value["max_llm_operations"]),
            max_seconds=_seconds(budget_value["max_seconds"]),
        ),
        spend=ResearchExecutionSpend(
            step_advances=_count(spend_value["step_advances"]),
            network_operations=_count(spend_value["network_operations"]),
            llm_operations=_count(spend_value["llm_operations"]),
            active_seconds=_seconds(spend_value["active_seconds"]),
        ),
    )


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResearchError("Execution snapshot budget value is invalid.")
    return value


def _seconds(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResearchError("Execution snapshot budget seconds are invalid.")
    return float(value)


def _decode_step(document: object) -> ResearchPlanExecutionStepSnapshot:
    if not isinstance(document, dict) or set(document) != _STEP_FIELDS:
        raise ResearchError("Execution snapshot step document is invalid.")
    work_performed = document["work_performed"]
    if not isinstance(work_performed, bool):
        raise ResearchError("Execution snapshot work flag is invalid.")
    return ResearchPlanExecutionStepSnapshot(
        step_id=_text(document["step_id"], "step ID"),
        capability=_enum(
            document["capability"],
            ResearchPlanStepCapability,
            "step capability",
        ),
        status=_enum(document["status"], ResearchPlanStepStatus, "step status"),
        detail=_detail(document["detail"]),
        operation=_operation(document["operation"]),
        work_performed=work_performed,
    )


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResearchError(f"Execution snapshot {label} cannot be empty.")
    return value.strip()


def _operation(value: object) -> str:
    if not isinstance(value, str):
        raise ResearchError("Execution snapshot operation is invalid.")
    return value.strip()


def _detail(value: object) -> str:
    if not isinstance(value, str):
        raise ResearchError("Execution snapshot detail is invalid.")
    detail = value.strip()
    if len(detail) > MAX_SNAPSHOT_DETAIL_CHARACTERS:
        raise ResearchError("Execution snapshot detail is too long.")
    return detail


def _enum(value: object, enum_type: type, label: str) -> Any:
    if not isinstance(value, str):
        raise ResearchError(f"Execution snapshot {label} is invalid.")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ResearchError(f"Execution snapshot {label} is invalid.") from error


def _timestamp(value: object) -> Any:
    from datetime import datetime

    if not isinstance(value, str):
        raise ResearchError("Execution snapshot timestamp is invalid.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ResearchError("Execution snapshot timestamp is invalid.") from error
    if parsed.utcoffset() is None:
        raise ResearchError("Execution snapshot timestamp must be timezone-aware.")
    return parsed
