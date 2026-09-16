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

from dataclasses import replace
from datetime import datetime
from typing import Any

from core.Exceptions import ResearchError
from research.ResearchAttemptRecovery import ResearchAttemptRecovery
from research.ResearchAttemptRecoveryDecision import (
    ResearchAttemptRecoveryDecision,
)
from research.ResearchAttemptResolution import ResearchAttemptResolution
from research.ResearchAuthorizer import ResearchAuthorizer
from research.ResearchAutonomyBudget import ResearchAutonomyBudget
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchExecutionAllowance import ResearchExecutionAllowance
from research.ResearchExecutionSpend import ResearchExecutionSpend
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint
from research.ResearchMissionScope import ResearchMissionScope
from research.ResearchPlanDigest import is_plan_digest
from research.ResearchPlanExecutionSnapshot import (
    MAX_SNAPSHOT_DETAIL_CHARACTERS,
    MAX_SNAPSHOT_STEPS,
    ResearchPlanExecutionSnapshot,
    ResearchPlanExecutionStepSnapshot,
)
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.SemanticMissionPolicy import SemanticMissionPolicy

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
_EXECUTION_FIELDS_WITH_TARGET = _EXECUTION_FIELDS | {"target_plan_digest"}
_EXECUTION_FIELDS_WITH_MISSION = _EXECUTION_FIELDS | {"mission_plan_digest"}
_EXECUTION_FIELDS_WITH_MISSION_RECOVERY = _EXECUTION_FIELDS_WITH_MISSION | {
    "mission_scope",
    "mission_disclosure",
    "mission_checkpoint",
}
_EXECUTION_FIELDS_WITH_MISSION_REQUEST = _EXECUTION_FIELDS_WITH_MISSION_RECOVERY | {
    "mission_request_id"
}
_EXECUTION_FIELDS_WITH_MISSION_REQUEST_ONLY = _EXECUTION_FIELDS_WITH_MISSION | {
    "mission_request_id"
}
_MISSION_CHECKPOINT_FIELDS_V1 = frozenset(
    {
        "discovery_id",
        "acquired_urls",
        "body_hashes",
        "inspected_bytes",
        "evidence_ids",
        "assessment_ids",
    }
)
_MISSION_CHECKPOINT_FIELDS = _MISSION_CHECKPOINT_FIELDS_V1 | {
    "semantic_note_id",
    "semantic_input_fingerprint",
    "semantic_relation",
}
_MISSION_CHECKPOINT_FIELDS_WITH_CONTRADICTION_OUTCOME = _MISSION_CHECKPOINT_FIELDS | {
    "contradiction_initial_note_id",
    "contradiction_initial_evidence_ids",
    "contradiction_initial_source_document_ids",
    "contradiction_initial_assessment_ids",
    "contradiction_initial_input_fingerprint",
    "contradiction_initial_relation",
    "contradiction_followup_note_id",
    "contradiction_followup_evidence_id",
    "contradiction_followup_source_document_id",
    "contradiction_followup_assessment_id",
    "contradiction_followup_input_fingerprint",
    "contradiction_followup_relation",
    "contradiction_outcome",
}
_MISSION_CHECKPOINT_FIELDS_WITH_EVIDENCE_GAP_OUTCOME = (
    _MISSION_CHECKPOINT_FIELDS_WITH_CONTRADICTION_OUTCOME
    | {
        "evidence_gap_followup_note_id",
        "evidence_gap_followup_input_fingerprint",
        "evidence_gap_followup_relation",
        "evidence_gap_outcome",
    }
)

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
#: Records written before rulings existed carry no resolution and decode as
#: unruled, which is what they truthfully were.
_STEP_FIELDS_WITH_RULING = _STEP_FIELDS | {"resolution"}
#: Records written before operators could recover an attempt carry no recovery
#: and decode without one, which is what they truthfully had.
_STEP_FIELDS_WITH_RECOVERY = _STEP_FIELDS_WITH_RULING | {"recovery"}
_RECOVERY_FIELDS = frozenset(
    {"decision", "recorded_at", "recorded_by", "summary", "claimed_operation"}
)


def encode_execution_snapshot(
    snapshot: ResearchPlanExecutionSnapshot,
) -> dict[str, Any]:
    """Return the document form of one execution snapshot."""
    if not isinstance(snapshot, ResearchPlanExecutionSnapshot):
        raise ResearchError("Execution snapshot is invalid.")
    document = {
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
                "resolution": step.resolution.value,
                "recovery": _encoded_recovery(step.recovery),
            }
            for step in snapshot.steps
        ],
    }
    if snapshot.target_plan_digest is not None:
        document["target_plan_digest"] = snapshot.target_plan_digest
    if snapshot.mission_plan_digest is not None:
        document["mission_plan_digest"] = snapshot.mission_plan_digest
    if snapshot.mission_scope is not None:
        document["mission_scope"] = _encode_mission_scope(snapshot.mission_scope)
        document["mission_disclosure"] = snapshot.mission_disclosure.value
        document["mission_checkpoint"] = _encode_mission_checkpoint(
            snapshot.mission_checkpoint
        )
    if snapshot.mission_request_id is not None:
        document["mission_request_id"] = snapshot.mission_request_id
    if snapshot.mission_stop_reason is not None:
        document["mission_stop_reason"] = snapshot.mission_stop_reason.value
    return document


def decode_execution_snapshot(document: object) -> ResearchPlanExecutionSnapshot:
    """Return one validated snapshot, or refuse a malformed document.

    ``mission_stop_reason`` is optional and only valid beside recorded mission
    recovery state.  Its absence decodes as no recorded stop, never as a guess.
    """
    if isinstance(document, dict) and "mission_stop_reason" in document:
        if set(document) - {"mission_stop_reason"} not in (
            _EXECUTION_FIELDS_WITH_MISSION_RECOVERY,
            _EXECUTION_FIELDS_WITH_MISSION_REQUEST,
        ):
            raise ResearchError("Execution snapshot document is invalid.")
        stop_reason = _enum(
            document["mission_stop_reason"],
            AutonomyStopReason,
            "mission stop reason",
        )
        base = {
            key: value
            for key, value in document.items()
            if key != "mission_stop_reason"
        }
        return replace(decode_execution_snapshot(base), mission_stop_reason=stop_reason)
    if not isinstance(document, dict) or set(document) not in (
        _EXECUTION_FIELDS,
        _EXECUTION_FIELDS_V1,
        _EXECUTION_FIELDS_WITH_TARGET,
        _EXECUTION_FIELDS_WITH_MISSION,
        _EXECUTION_FIELDS_WITH_MISSION_RECOVERY,
        _EXECUTION_FIELDS_WITH_MISSION_REQUEST,
        _EXECUTION_FIELDS_WITH_MISSION_REQUEST_ONLY,
    ):
        raise ResearchError("Execution snapshot document is invalid.")
    if "mission_plan_digest" in document and not is_plan_digest(
        document["mission_plan_digest"]
    ):
        raise ResearchError("Execution snapshot mission digest is invalid.")
    if "target_plan_digest" in document and not is_plan_digest(
        document["target_plan_digest"]
    ):
        raise ResearchError("Execution snapshot target plan digest is invalid.")
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
        target_plan_digest=document.get("target_plan_digest"),
        mission_plan_digest=document.get("mission_plan_digest"),
        mission_scope=(
            _decode_mission_scope(document["mission_scope"])
            if "mission_scope" in document
            else None
        ),
        mission_disclosure=(
            _enum(
                document["mission_disclosure"],
                ResearchDisclosure,
                "mission disclosure",
            )
            if "mission_disclosure" in document
            else ResearchDisclosure.NONE
        ),
        mission_checkpoint=(
            _decode_mission_checkpoint(document["mission_checkpoint"])
            if "mission_checkpoint" in document
            else None
        ),
        mission_request_id=document.get("mission_request_id"),
        steps=tuple(_decode_step(value) for value in steps_value),
    )


def _encode_mission_scope(scope: ResearchMissionScope) -> dict[str, Any]:
    """Encode the exact, digest-bound semantic scope without granting it."""
    policy = scope.semantic_policy
    assert policy is not None
    return {
        "provider": scope.provider.value,
        "source_policy": scope.source_policy,
        "max_source_bytes": scope.max_source_bytes,
        "max_sources": scope.max_sources,
        "semantic_policy": {
            "endpoint": policy.endpoint,
            "model": policy.model,
            "disclosure": policy.disclosure.value,
            "max_input_bytes": policy.max_input_bytes,
            "input_scope": policy.input_scope,
            "selection": policy.selection,
            "retention": policy.retention,
        },
    }


def _decode_mission_scope(value: object) -> ResearchMissionScope:
    fields = {
        "provider",
        "source_policy",
        "max_source_bytes",
        "max_sources",
        "semantic_policy",
    }
    policy_fields = {
        "endpoint",
        "model",
        "disclosure",
        "max_input_bytes",
        "input_scope",
        "selection",
        "retention",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ResearchError("Execution snapshot mission scope is invalid.")
    policy_value = value["semantic_policy"]
    if not isinstance(policy_value, dict) or set(policy_value) != policy_fields:
        raise ResearchError("Execution snapshot mission policy is invalid.")
    try:
        provider = ResearchDiscoveryProviderName(value["provider"])
    except (TypeError, ValueError) as error:
        raise ResearchError(
            "Execution snapshot mission provider is invalid."
        ) from error
    try:
        policy = SemanticMissionPolicy(
            endpoint=policy_value["endpoint"],
            model=policy_value["model"],
            disclosure=ResearchDisclosure(policy_value["disclosure"]),
            max_input_bytes=policy_value["max_input_bytes"],
            input_scope=policy_value["input_scope"],
            selection=policy_value["selection"],
            retention=policy_value["retention"],
        )
        return ResearchMissionScope(
            provider=provider,
            source_policy=value["source_policy"],
            max_source_bytes=value["max_source_bytes"],
            max_sources=value["max_sources"],
            semantic_policy=policy,
        )
    except (ResearchError, TypeError, ValueError) as error:
        raise ResearchError("Execution snapshot mission scope is invalid.") from error


def _encode_mission_checkpoint(
    checkpoint: ResearchMissionRecoveryCheckpoint | None,
) -> dict[str, Any] | None:
    if checkpoint is None:
        return None
    return {
        "discovery_id": checkpoint.discovery_id,
        "acquired_urls": list(checkpoint.acquired_urls),
        "body_hashes": list(checkpoint.body_hashes),
        "inspected_bytes": checkpoint.inspected_bytes,
        "evidence_ids": list(checkpoint.evidence_ids),
        "assessment_ids": list(checkpoint.assessment_ids),
        "semantic_note_id": checkpoint.semantic_note_id,
        "semantic_input_fingerprint": checkpoint.semantic_input_fingerprint,
        "semantic_relation": checkpoint.semantic_relation,
        "contradiction_initial_note_id": checkpoint.contradiction_initial_note_id,
        "contradiction_initial_evidence_ids": list(
            checkpoint.contradiction_initial_evidence_ids
        ),
        "contradiction_initial_source_document_ids": list(
            checkpoint.contradiction_initial_source_document_ids
        ),
        "contradiction_initial_assessment_ids": list(
            checkpoint.contradiction_initial_assessment_ids
        ),
        "contradiction_initial_input_fingerprint": (
            checkpoint.contradiction_initial_input_fingerprint
        ),
        "contradiction_initial_relation": checkpoint.contradiction_initial_relation,
        "contradiction_followup_note_id": checkpoint.contradiction_followup_note_id,
        "contradiction_followup_evidence_id": (
            checkpoint.contradiction_followup_evidence_id
        ),
        "contradiction_followup_source_document_id": (
            checkpoint.contradiction_followup_source_document_id
        ),
        "contradiction_followup_assessment_id": (
            checkpoint.contradiction_followup_assessment_id
        ),
        "contradiction_followup_input_fingerprint": (
            checkpoint.contradiction_followup_input_fingerprint
        ),
        "contradiction_followup_relation": checkpoint.contradiction_followup_relation,
        "contradiction_outcome": checkpoint.contradiction_outcome,
        "evidence_gap_followup_note_id": checkpoint.evidence_gap_followup_note_id,
        "evidence_gap_followup_input_fingerprint": (
            checkpoint.evidence_gap_followup_input_fingerprint
        ),
        "evidence_gap_followup_relation": checkpoint.evidence_gap_followup_relation,
        "evidence_gap_outcome": checkpoint.evidence_gap_outcome,
        "requested_urls": list(checkpoint.requested_urls),
    }


def _decode_mission_checkpoint(
    value: object,
) -> ResearchMissionRecoveryCheckpoint | None:
    if value is None:
        return None
    # ``requested_urls`` is independent of the relation fields, so it may
    # accompany any recognised checkpoint shape; its absence means unrecorded.
    if not isinstance(value, dict) or set(value) - {"requested_urls"} not in (
        _MISSION_CHECKPOINT_FIELDS_V1,
        _MISSION_CHECKPOINT_FIELDS,
        _MISSION_CHECKPOINT_FIELDS_WITH_CONTRADICTION_OUTCOME,
        _MISSION_CHECKPOINT_FIELDS_WITH_EVIDENCE_GAP_OUTCOME,
    ):
        raise ResearchError("Execution snapshot mission checkpoint is invalid.")
    if "requested_urls" in value and not isinstance(value["requested_urls"], list):
        raise ResearchError("Execution snapshot mission checkpoint is invalid.")
    sequences = (
        "acquired_urls",
        "body_hashes",
        "evidence_ids",
        "assessment_ids",
    )
    if any(not isinstance(value[name], list) for name in sequences):
        raise ResearchError("Execution snapshot mission checkpoint is invalid.")
    contradiction_sequences = (
        "contradiction_initial_evidence_ids",
        "contradiction_initial_source_document_ids",
        "contradiction_initial_assessment_ids",
    )
    if set(value) - {"requested_urls"} in (
        _MISSION_CHECKPOINT_FIELDS_WITH_CONTRADICTION_OUTCOME,
        _MISSION_CHECKPOINT_FIELDS_WITH_EVIDENCE_GAP_OUTCOME,
    ) and any(not isinstance(value[name], list) for name in contradiction_sequences):
        raise ResearchError("Execution snapshot mission checkpoint is invalid.")
    try:
        return ResearchMissionRecoveryCheckpoint(
            discovery_id=value["discovery_id"],
            acquired_urls=tuple(value["acquired_urls"]),
            body_hashes=tuple(value["body_hashes"]),
            inspected_bytes=value["inspected_bytes"],
            evidence_ids=tuple(value["evidence_ids"]),
            assessment_ids=tuple(value["assessment_ids"]),
            semantic_note_id=value.get("semantic_note_id", ""),
            semantic_input_fingerprint=value.get("semantic_input_fingerprint", ""),
            semantic_relation=value.get("semantic_relation", ""),
            contradiction_initial_note_id=value.get(
                "contradiction_initial_note_id", ""
            ),
            contradiction_initial_evidence_ids=tuple(
                value.get("contradiction_initial_evidence_ids", [])
            ),
            contradiction_initial_source_document_ids=tuple(
                value.get("contradiction_initial_source_document_ids", [])
            ),
            contradiction_initial_assessment_ids=tuple(
                value.get("contradiction_initial_assessment_ids", [])
            ),
            contradiction_initial_input_fingerprint=value.get(
                "contradiction_initial_input_fingerprint", ""
            ),
            contradiction_initial_relation=value.get(
                "contradiction_initial_relation", ""
            ),
            contradiction_followup_note_id=value.get(
                "contradiction_followup_note_id", ""
            ),
            contradiction_followup_evidence_id=value.get(
                "contradiction_followup_evidence_id", ""
            ),
            contradiction_followup_source_document_id=value.get(
                "contradiction_followup_source_document_id", ""
            ),
            contradiction_followup_assessment_id=value.get(
                "contradiction_followup_assessment_id", ""
            ),
            contradiction_followup_input_fingerprint=value.get(
                "contradiction_followup_input_fingerprint", ""
            ),
            contradiction_followup_relation=value.get(
                "contradiction_followup_relation", ""
            ),
            contradiction_outcome=value.get("contradiction_outcome", ""),
            # Absent in legacy checkpoints: decoded as "not recorded", never as
            # a supported or resolved follow-up.
            evidence_gap_followup_note_id=value.get(
                "evidence_gap_followup_note_id", ""
            ),
            evidence_gap_followup_input_fingerprint=value.get(
                "evidence_gap_followup_input_fingerprint", ""
            ),
            evidence_gap_followup_relation=value.get(
                "evidence_gap_followup_relation", ""
            ),
            evidence_gap_outcome=value.get("evidence_gap_outcome", ""),
            # Absent in legacy checkpoints: decoded as "not recorded".  Recovery
            # then refuses any further fetch rather than risk refetching a source.
            requested_urls=tuple(value.get("requested_urls", [])),
        )
    except ResearchError as error:
        raise ResearchError(
            "Execution snapshot mission checkpoint is invalid."
        ) from error


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
    if not isinstance(document, dict) or set(document) not in (
        _STEP_FIELDS,
        _STEP_FIELDS_WITH_RULING,
        _STEP_FIELDS_WITH_RECOVERY,
    ):
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
        resolution=_resolution(document.get("resolution", "none")),
        recovery=_decoded_recovery(document.get("recovery")),
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


def _resolution(value: Any) -> ResearchAttemptResolution:
    """Return one bounded ruling, refusing anything the vocabulary lacks."""
    try:
        return ResearchAttemptResolution(value)
    except ValueError as error:
        raise ResearchError("Execution snapshot step resolution is invalid.") from error


def _encoded_recovery(recovery: ResearchAttemptRecovery | None) -> Any:
    """Return one recovery as a document, or nothing when none was made."""
    if recovery is None:
        return None
    return {
        "decision": recovery.decision.value,
        "recorded_at": recovery.recorded_at.isoformat(),
        "recorded_by": recovery.recorded_by.value,
        "summary": recovery.summary,
        "claimed_operation": recovery.claimed_operation,
    }


def _decoded_recovery(document: Any) -> ResearchAttemptRecovery | None:
    """Return one recovery, refusing a document that is not exactly one."""
    if document is None:
        return None
    if not isinstance(document, dict) or set(document) != _RECOVERY_FIELDS:
        raise ResearchError("Execution snapshot step recovery is invalid.")
    try:
        return ResearchAttemptRecovery(
            decision=ResearchAttemptRecoveryDecision(document["decision"]),
            recorded_at=_recovery_moment(document["recorded_at"]),
            recorded_by=ResearchAuthorizer(document["recorded_by"]),
            summary=document["summary"],
            claimed_operation=document["claimed_operation"],
        )
    except (ValueError, TypeError) as error:
        raise ResearchError("Execution snapshot step recovery is invalid.") from error


def _recovery_moment(value: Any) -> datetime:
    """Parse one recorded moment, refusing anything that is not one."""
    if not isinstance(value, str):
        raise ResearchError("Execution snapshot step recovery is invalid.")
    return datetime.fromisoformat(value)
