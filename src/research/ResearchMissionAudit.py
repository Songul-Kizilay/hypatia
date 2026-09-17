"""Deterministic, read-only audit bundle for one bounded research mission.

The bundle answers what the mission did, under which recorded authority and
allowance, what it spent, which evidence and operator reviews bear on its
result, and why its derived status is what it is.  Every value comes from an
existing canonical record: the durable-form execution snapshot, the linked
research run in its store document form, and the approval spent on the
execution.  Goal satisfaction, explanation, readiness and the teaching report
are recomputed by the existing functions; none of them is persisted here or
anywhere else.

Nothing is inferred.  A missing stop reason, checkpoint, approval or run is
reported as unavailable with a typed limitation, never reconstructed from
prose.  The JSON form is the canonical export; the Markdown form is rendered
from the same data plus the existing run export, and nothing parses Markdown.

An audit is not execution, verification, approval, closure or new evidence.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from core.Exceptions import ResearchError
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchComparisonReviewRecord import current_comparison_review
from research.ResearchMissionGoalExplanation import explain_mission_goal_satisfaction
from research.ResearchMissionOutcome import (
    mission_comparison_review,
    mission_outcome_for,
    supporting_comparison_review,
)
from research.ResearchPlanAuthorization import ResearchPlanAuthorization
from research.ResearchPlanExecutionCodec import encode_execution_snapshot
from research.ResearchPlanExecutionSnapshot import ResearchPlanExecutionSnapshot
from research.ResearchRun import ResearchRun
from research.ResearchRunMarkdownRenderer import (
    _inline,
    _quote,
    render_research_run_markdown,
)
from research.ResearchTeachingReport import teaching_report

MISSION_AUDIT_SCHEMA = "hypatia.mission_audit"
#: Version 2 resolves traces to evidence and source observations and names the
#: recorded basis of the goal evaluation.  Version 3 adds each source's selected
#: discovery candidate when recorded.
MISSION_AUDIT_SCHEMA_VERSION = 3


def build_mission_audit(
    snapshot: ResearchPlanExecutionSnapshot,
    run: ResearchRun | None,
    authorization: ResearchPlanAuthorization | None,
    *,
    hypatia_version: str,
) -> dict[str, Any]:
    """Return the canonical audit document for one mission. Mutates nothing."""
    if (
        not isinstance(snapshot, ResearchPlanExecutionSnapshot)
        or snapshot.mission_scope is None
    ):
        raise ResearchError("A mission audit requires a mission execution record.")
    if run is not None and (
        not isinstance(run, ResearchRun) or run.run_id != snapshot.research_run_id
    ):
        raise ResearchError("A mission audit run must be the mission's own run.")
    if authorization is not None and (
        not isinstance(authorization, ResearchPlanAuthorization)
        or authorization.consumption is None
        or authorization.consumption.execution_id != snapshot.plan_id
    ):
        raise ResearchError(
            "A mission audit approval must be the one spent on this execution."
        )
    if run is not None:
        _refuse_credentialed_urls(run)
    limitations: list[str] = [
        # A live execution has no durable write time of its own; omitting it
        # keeps live and restored audits of the same state identical.
        "snapshot_recorded_at_excluded",
    ]
    execution = encode_execution_snapshot(snapshot)
    execution.pop("recorded_at", None)
    checkpoint = snapshot.mission_checkpoint
    stop = snapshot.mission_stop_reason
    if checkpoint is None:
        limitations.append("mission_checkpoint_unavailable")
    if stop is None:
        limitations.append("stop_reason_unrecorded")
    if snapshot.allowance is None:
        limitations.append("allowance_unrecorded")
    if authorization is None:
        limitations.append("authorization_record_unavailable")
    if run is None:
        limitations.append("research_run_unavailable")
    if snapshot.mission_request_id is None:
        limitations.append("mission_request_id_unrecorded")

    run_document: dict[str, object] | None = None
    run_schema_version: int | None = None
    if run is not None:
        run_schema_version, run_document = JsonFileResearchRunStore.encode_run(run)

    evaluation: dict[str, Any] | None = None
    report: str | None = None
    if run is not None and stop is not None:
        outcome = mission_outcome_for(run, stop, checkpoint)
        explanation = explain_mission_goal_satisfaction(outcome, stop, checkpoint)
        evidence = outcome.evidence_evaluation
        goal = outcome.goal_satisfaction
        readiness = outcome.completion_readiness
        evaluation = {
            "stop_reason": stop.value,
            "execution_outcome": outcome.execution_outcome.value,
            "evidence_completion": {
                "status": evidence.status.value,
                "supports_bounded_teaching": evidence.supports_bounded_teaching,
                "source_count": evidence.source_count,
                "evidence_count": evidence.evidence_count,
                "evidence_source_count": evidence.evidence_source_count,
                "assessed_source_count": evidence.assessed_source_count,
                "comparison_note_count": evidence.comparison_note_count,
                "recorded_claim_contradiction_count": (
                    evidence.recorded_claim_contradiction_count
                ),
                "limitations": [value.value for value in evidence.limitations],
                "caveats": [value.value for value in evidence.caveats],
            },
            "goal_satisfaction": {
                "status": goal.status.value,
                "evidence_status": goal.evidence_status.value,
                "execution_outcome": goal.execution_outcome.value,
                "contradiction_outcome": goal.contradiction_outcome or None,
                "supported_by_review_id": goal.supported_by_review_id or None,
            },
            "goal_explanation": {
                "status": explanation.status.value,
                "reasons": [value.value for value in explanation.reasons],
                "caveats": [value.value for value in explanation.caveats],
            },
            "completion_readiness": {
                "status": readiness.status.value,
                "ready": readiness.ready,
                "goal_status": readiness.goal_status.value,
                "execution_outcome": readiness.execution_outcome.value,
                "contradiction_outcome": readiness.contradiction_outcome or None,
            },
        }
        allowance = snapshot.allowance
        spend = (
            "Cumulative spending: unrecorded."
            if allowance is None
            else (
                f"Cumulative spending: {allowance.spend.step_advances} advances, "
                f"{allowance.spend.network_operations} network and "
                f"{allowance.spend.llm_operations} model operations."
            )
        )
        report = teaching_report(run, stop.value, spend, checkpoint=checkpoint)
    else:
        limitations.append("mission_evaluation_unavailable")

    allowance = snapshot.allowance
    return {
        "schema": MISSION_AUDIT_SCHEMA,
        "schema_version": MISSION_AUDIT_SCHEMA_VERSION,
        "export": {
            "generator": "hypatia",
            "hypatia_version": hypatia_version,
            "execution_document_codec": "research_plan_execution_snapshot",
            "research_run_store_schema_version": run_schema_version,
            "read_only": True,
        },
        "identity": {
            "plan_id": snapshot.plan_id,
            "mission_request_id": snapshot.mission_request_id,
            "research_run_id": snapshot.research_run_id,
            "authorization_id": (
                authorization.authorization_id if authorization else None
            ),
            "question": snapshot.question,
        },
        "plan": {
            "mission_plan_digest": snapshot.mission_plan_digest,
            "capability_order": [
                {"step_id": step.step_id, "capability": step.capability.value}
                for step in snapshot.steps
            ],
            "mission_scope": execution.get("mission_scope"),
            "mission_disclosure": snapshot.mission_disclosure.value,
        },
        "authority": _authorization_document(authorization),
        "budget": (
            None
            if allowance is None
            else {
                "approved": {
                    "max_step_advances": allowance.budget.max_step_advances,
                    "max_network_operations": allowance.budget.max_network_operations,
                    "max_llm_operations": allowance.budget.max_llm_operations,
                    "max_seconds": allowance.budget.max_seconds,
                },
                "spent": {
                    "step_advances": allowance.spend.step_advances,
                    "network_operations": allowance.spend.network_operations,
                    "llm_operations": allowance.spend.llm_operations,
                    "active_seconds": allowance.spend.active_seconds,
                },
                "remaining": {
                    "step_advances": allowance.remaining_step_advances,
                    "network_operations": allowance.remaining_network_operations,
                    "llm_operations": allowance.remaining_llm_operations,
                    "seconds": allowance.remaining_seconds,
                },
            }
        ),
        "execution": {
            "status": snapshot.status.value,
            "stop_reason": stop.value if stop is not None else None,
            "snapshot": execution,
        },
        "research_run": run_document,
        "traceability": _traceability(run, snapshot),
        "evaluation": evaluation,
        "teaching_report": report,
        "limitations": sorted(set(limitations)),
    }


def mission_audit_json(audit: dict[str, Any]) -> str:
    """Serialize deterministically: sorted keys, stable indentation, UTF-8 text."""
    return json.dumps(audit, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def render_mission_audit_markdown(
    audit: dict[str, Any], run: ResearchRun | None
) -> str:
    """Render the human-readable audit from the canonical audit document."""
    identity = audit["identity"]
    plan = audit["plan"]
    execution = audit["execution"]
    evaluation = audit["evaluation"]
    lines = [
        "# Mission Audit",
        "",
        "_Read-only export of recorded mission state. Generating it executed, "
        "fetched, called, approved, reviewed and closed nothing. It is not "
        "verification and not new evidence._",
        "",
        f"- **Schema:** {audit['schema']} v{audit['schema_version']}",
        f"- **Hypatia version:** {_inline(audit['export']['hypatia_version'])}",
        "",
        "## Identity",
        "",
        f"- **Plan ID:** {_inline(identity['plan_id'])}",
        f"- **Mission request ID:** {_optional(identity['mission_request_id'])}",
        f"- **Research run ID:** {_optional(identity['research_run_id'])}",
        f"- **Authorization ID:** {_optional(identity['authorization_id'])}",
        "- **Question:**",
        "",
        *_quote(identity["question"]),
        "",
        "## Plan and Authority",
        "",
        f"- **Mission plan digest:** `{plan['mission_plan_digest']}`",
        f"- **Mission disclosure:** {plan['mission_disclosure']}",
        "- **Capability order:** "
        + ", ".join(
            f"{_inline(step['step_id'])} ({step['capability']})"
            for step in plan["capability_order"]
        ),
    ]
    scope = plan["mission_scope"]
    if scope is not None:
        policy = scope["semantic_policy"]
        lines.extend(
            (
                f"- **Discovery provider:** {_inline(scope['provider'])}",
                f"- **Source policy:** {_inline(scope['source_policy'])}",
                f"- **Maximum sources:** {scope['max_sources']}",
                f"- **Maximum source bytes:** {scope['max_source_bytes']}",
                f"- **Approved model endpoint:** {_inline(policy['endpoint'])}",
                f"- **Approved model:** {_inline(policy['model'])}",
                f"- **Model input limit (bytes):** {policy['max_input_bytes']}",
            )
        )
    authority = audit["authority"]
    if authority is None:
        lines.append(
            "- **Recorded approval:** unavailable; no approval record names this "
            "execution. None was inferred."
        )
    else:
        consumption = authority["consumption"]
        lines.extend(
            (
                f"- **Recorded approval:** {_inline(authority['authorization_id'])}",
                f"- **Authorized by:** {authority['authorized_by']}",
                f"- **Approved plan digest:** `{authority['plan_digest']}`",
                f"- **Approved run:** {_inline(authority['research_run_id'])}",
                "- **Approved capabilities:** " + ", ".join(authority["capabilities"]),
                "- **Approved restrictions:** "
                + (", ".join(authority["approved_restrictions"]) or "none recorded"),
                f"- **Approved disclosure:** {authority['disclosure']}",
                f"- **Authorized at:** {authority['authorized_at']}",
                f"- **Expires at:** {authority['expires_at']}",
                (
                    "- **Consumed by execution:** "
                    f"{_inline(consumption['execution_id'])} at "
                    f"{consumption['consumed_at']}"
                ),
            )
        )
    lines.extend(("", "## Budget and Spend", ""))
    budget = audit["budget"]
    if budget is None:
        lines.append("_No allowance was recorded for this execution._")
    else:
        approved, spent, remaining = (
            budget["approved"],
            budget["spent"],
            budget["remaining"],
        )
        lines.extend(
            (
                "| Measure | Approved | Spent | Remaining |",
                "| --- | --- | --- | --- |",
                f"| Step advances | {approved['max_step_advances']} | "
                f"{spent['step_advances']} | {remaining['step_advances']} |",
                f"| Network operations | {approved['max_network_operations']} | "
                f"{spent['network_operations']} | "
                f"{remaining['network_operations']} |",
                f"| Model operations | {approved['max_llm_operations']} | "
                f"{spent['llm_operations']} | {remaining['llm_operations']} |",
                f"| Seconds | {approved['max_seconds']:g} | "
                f"{spent['active_seconds']:.3f} | {remaining['seconds']:.3f} |",
            )
        )
    lines.extend(
        (
            "",
            "## Execution",
            "",
            f"- **Execution status:** {execution['status']}",
            f"- **Recorded stop reason:** {_typed(execution['stop_reason'])}",
            "",
            "| Step | Capability | Status | Work performed | Operation |",
            "| --- | --- | --- | --- | --- |",
        )
    )
    for step in execution["snapshot"]["steps"]:
        lines.append(
            f"| {_inline(step['step_id'])} | {step['capability']} | "
            f"{step['status']} | {'yes' if step['work_performed'] else 'no'} | "
            f"{_inline(step['operation']) or '-'} |"
        )
    checkpoint = execution["snapshot"].get("mission_checkpoint")
    lines.extend(("", "### Mission Checkpoint", ""))
    if checkpoint is None:
        lines.append("_No mission checkpoint was recorded._")
    else:
        for key in (
            "semantic_note_id",
            "semantic_relation",
            "contradiction_initial_note_id",
            "contradiction_initial_relation",
            "contradiction_followup_note_id",
            "contradiction_followup_relation",
            "contradiction_outcome",
            "evidence_gap_followup_note_id",
            "evidence_gap_followup_relation",
            "evidence_gap_outcome",
        ):
            if key in checkpoint:
                label = key.replace("_", " ").capitalize()
                value = (
                    _typed(checkpoint[key])
                    if key.endswith(("_relation", "_outcome"))
                    else _optional(checkpoint[key] or None)
                )
                lines.append(f"- **{label}:** {value}")
        lines.append(
            "- **Checkpoint evidence IDs:** "
            + (", ".join(_inline(v) for v in checkpoint["evidence_ids"]) or "none")
        )
        lines.append(
            "_Recorded relations are tentative model interpretations unless an "
            "operator review below says otherwise; none is a verified fact._"
        )

    lines.extend(("", "## Comparison Traceability", ""))
    traceability = audit["traceability"]
    if traceability is None:
        lines.append("_The research run is unavailable, so nothing can be traced._")
    else:
        lines.append(
            "- **Mission comparison note:** "
            + _optional(traceability["mission_comparison_note_id"])
        )
        lines.append(
            "- **Current mission comparison review:** "
            + _optional(traceability["mission_comparison_review_id"])
        )
        for entry in traceability["comparison_reviews"]:
            lines.append(
                f"- Review {_inline(entry['review_id'])} ({entry['decision']}, "
                f"{'current' if entry['current'] else 'superseded'}) → note "
                f"{_inline(entry['note_id'])} → evidence "
                + ", ".join(_inline(v) for v in entry["evidence_ids"])
                + " → sources "
                + (
                    ", ".join(_inline(v) for v in entry["source_document_ids"])
                    or "unavailable"
                )
            )
        for entry in traceability["claims"]:
            missing = entry["unrecorded_evidence_ids"]
            lines.append(
                f"- Claim {_inline(entry['claim_id'])} ({entry['epistemic_state']}) "
                "→ evidence "
                + ", ".join(_inline(v) for v in entry["evidence_ids"])
                + (
                    " (not in this run: " + ", ".join(_inline(v) for v in missing) + ")"
                    if missing
                    else ""
                )
            )
        basis = traceability["goal_basis"]
        lines.extend(("", "### Recorded Basis of the Goal Evaluation", ""))
        for note in basis["comparison_notes"]:
            lines.append(
                f"- {note['role'].replace('_', ' ').capitalize()}: "
                f"{_inline(note['note_id'])} (recorded relation "
                f"{_typed(note['recorded_relation'])}"
                + ("" if note["resolved"] else "; not found in this run")
                + ")"
            )
            for trace in note["evidence"]:
                lines.append("  - " + _evidence_trace_line(trace))
        if not basis["comparison_notes"]:
            lines.append("- No comparison note was recorded by the mission checkpoint.")
        lines.extend(
            (
                "- **Contradiction outcome:** "
                + _typed(basis["contradiction_outcome"]),
                "- **Evidence-gap outcome:** " + _typed(basis["evidence_gap_outcome"]),
                "- **Supporting operator review:** "
                + _optional(basis["supporting_review_id"]),
            )
        )
        lines.extend(("", "### Source Observations of This Run", ""))
        for source in traceability["source_observations"]:
            lines.append(
                f"- {_inline(source['document_id'])}: requested "
                + _optional(source["requested_url"])
                + " → fetched "
                + _inline(source["url"])
                + " at "
                + source["fetched_at"]
                + "; discovery candidate "
                + (
                    _inline(source["discovery_candidate"]["candidate_id"])
                    if source["discovery_candidate"]
                    else "unrecorded"
                )
                + "; observed content SHA-256 "
                + (
                    f"`{source['content_sha256']}`"
                    if source["content_sha256"]
                    else "unrecorded"
                )
            )
        if not traceability["source_observations"]:
            lines.append("- No source was accepted into this run.")
        lines.append(
            "_Each hop follows a recorded ID. Unrecorded or unresolved links are "
            "reported as such and never matched by URL, text or hash._"
        )
        lines.append(
            "_A supported operator review is a bounded judgement about one exact "
            "comparison and its evidence, not model output and not universal "
            "truth._"
        )

    lines.extend(("", "## Goal Evaluation", ""))
    if evaluation is None:
        lines.append(
            "_Unavailable: no recorded stop reason or research run; no goal status "
            "was inferred._"
        )
    else:
        goal = evaluation["goal_satisfaction"]
        evidence = evaluation["evidence_completion"]
        lines.extend(
            (
                f"- **Execution outcome:** {evaluation['execution_outcome']}",
                f"- **Evidence completion:** {evidence['status']}",
                "- **Evidence limitations:** "
                + (", ".join(evidence["limitations"]) or "none recorded"),
                f"- **Goal satisfaction:** {goal['status']}",
                "- **Contradiction outcome:** " + _typed(goal["contradiction_outcome"]),
                "- **Supported by operator review:** "
                + _optional(goal["supported_by_review_id"]),
                "- **Explanation reasons:** "
                + ", ".join(evaluation["goal_explanation"]["reasons"]),
                "- **Caveats:** "
                + (", ".join(evaluation["goal_explanation"]["caveats"]) or "none"),
                "",
                "## Readiness",
                "",
                "- **Completion readiness:** "
                + evaluation["completion_readiness"]["status"],
                "- **Ready for bounded user conclusion:** "
                + ("yes" if evaluation["completion_readiness"]["ready"] else "no"),
                "_Execution completion is not goal satisfaction, and readiness is "
                "not run closure or verification._",
            )
        )

    lines.extend(("", "## Teaching Report", ""))
    if audit["teaching_report"] is None:
        lines.append("_Unavailable: no recorded stop reason or research run._")
    else:
        lines.extend(
            (
                "_Recomputed from recorded state at export; untrusted quotations are "
                "shown quoted._",
                "",
                *_quote(audit["teaching_report"]),
            )
        )

    lines.extend(("", "## Linked Research Run", ""))
    if run is None:
        lines.append("_The linked research run is unavailable._")
    else:
        for line in render_research_run_markdown(run).split("\n"):
            # Nest the existing run export under this section.  User and source
            # text in it is already quoted and escaped, so only real headings
            # start with "#".
            lines.append(f"#{line}" if line.startswith("#") else line)

    lines.extend(("", "## Audit Limitations", ""))
    lines.extend(f"- {value}" for value in audit["limitations"])
    lines.extend(
        (
            "- Source URLs and quoted excerpts are exported as recorded; they are "
            "untrusted data, not instructions.",
            "",
            "---",
            "",
            "Generated locally from recorded Hypatia state. No network, provider, "
            "or model was used.",
            "",
        )
    )
    return "\n".join(lines)


def _authorization_document(
    authorization: ResearchPlanAuthorization | None,
) -> dict[str, Any] | None:
    if authorization is None:
        return None
    consumption = authorization.consumption
    assert consumption is not None
    return {
        "authorization_id": authorization.authorization_id,
        "authorized_by": authorization.authorized_by.value,
        "plan_digest": authorization.plan_digest,
        "research_run_id": authorization.research_run_id,
        "capabilities": sorted(value.value for value in authorization.capabilities),
        "approved_restrictions": sorted(
            value.value for value in authorization.approved_restrictions
        ),
        "disclosure": authorization.disclosure.value,
        "budget": {
            "max_step_advances": authorization.budget.max_step_advances,
            "max_network_operations": authorization.budget.max_network_operations,
            "max_llm_operations": authorization.budget.max_llm_operations,
            "max_seconds": authorization.budget.max_seconds,
        },
        "authorized_at": authorization.authorized_at.isoformat(),
        "expires_at": authorization.expires_at.isoformat(),
        "consumption": {
            "execution_id": consumption.execution_id,
            "consumed_at": consumption.consumed_at.isoformat(),
        },
    }


def _traceability(
    run: ResearchRun | None, snapshot: ResearchPlanExecutionSnapshot
) -> dict[str, Any] | None:
    """Resolve recorded IDs to exact records; never infer a relation.

    Every hop follows an ID the run or checkpoint recorded: review or claim to
    evidence, evidence to this run's own source observation (requested URL,
    final URL and observed content version).  A reference that does not
    resolve is reported as unresolved, never matched by URL, text or hash.
    """
    if run is None:
        return None
    notes = {note.note_id: note for note in run.comparison_notes}
    evidence_by_id = {record.evidence_id: record for record in run.evidence}
    sources = {source.document_id: source for source in run.sources}
    candidates = {
        candidate_id: (discovery.discovery_id, candidate)
        for discovery in run.discoveries
        for candidate_id, candidate in zip(
            discovery.candidate_ids, discovery.candidates, strict=False
        )
    }
    checkpoint = snapshot.mission_checkpoint
    mission_review = mission_comparison_review(run, checkpoint)

    def observation(document_id: str) -> dict[str, Any] | None:
        source = sources.get(document_id)
        if source is None:
            return None
        return {
            "document_id": source.document_id,
            "requested_url": source.requested_url,
            "url": source.url,
            "content_sha256": source.content_sha256,
            "fetched_at": source.fetched_at.isoformat(),
            "added_at": source.added_at.isoformat(),
            "discovery_candidate": candidate_trace(source.discovery_candidate_id),
        }

    def candidate_trace(candidate_id: str | None) -> dict[str, Any] | None:
        # Resolved only by the identity recorded at selection; never by URL.
        if candidate_id is None:
            return None
        found = candidates.get(candidate_id)
        if found is None:
            return {"candidate_id": candidate_id, "resolved": False}
        discovery_id, candidate = found
        return {
            "candidate_id": candidate_id,
            "resolved": True,
            "discovery_id": discovery_id,
            "url": candidate.url,
            "title": candidate.title,
        }

    def evidence_trace(evidence_ids: tuple[str, ...]) -> list[dict[str, Any]]:
        traces: list[dict[str, Any]] = []
        for evidence_id in evidence_ids:
            record = evidence_by_id.get(evidence_id)
            if record is None:
                traces.append({"evidence_id": evidence_id, "resolved": False})
                continue
            source = observation(record.source_document_id)
            traces.append(
                {
                    "evidence_id": record.evidence_id,
                    "resolved": source is not None,
                    "chunk_id": record.chunk_id,
                    "chunk_sha256": record.chunk_sha256,
                    "source": source,
                }
            )
        return traces

    reviews = []
    for review in run.comparison_reviews:
        note = notes.get(review.note_id)
        current = current_comparison_review(run.comparison_reviews, review.note_id)
        reviews.append(
            {
                "review_id": review.review_id,
                "note_id": review.note_id,
                "decision": review.decision.value,
                "current": current is not None
                and current.review_id == review.review_id,
                "supersedes_review_id": review.supersedes_review_id,
                "evidence_ids": list(review.evidence_ids),
                "source_document_ids": (
                    list(note.source_document_ids) if note is not None else []
                ),
                "evidence": evidence_trace(review.evidence_ids),
                "recorded_at": review.recorded_at.isoformat(),
            }
        )
    superseded_claims = {
        claim.supersedes_claim_id
        for claim in run.claims
        if claim.supersedes_claim_id is not None
    }
    claims = [
        {
            "claim_id": claim.claim_id,
            "epistemic_state": claim.epistemic_state.value,
            "current": claim.claim_id not in superseded_claims,
            "supersedes_claim_id": claim.supersedes_claim_id,
            "evidence_ids": list(claim.evidence_ids),
            "source_document_ids": list(claim.source_document_ids),
            "unrecorded_evidence_ids": sorted(
                set(claim.evidence_ids) - set(evidence_by_id)
            ),
            "evidence": evidence_trace(claim.evidence_ids),
        }
        for claim in run.claims
    ]
    goal_basis: list[dict[str, Any]] = []
    if checkpoint is not None:
        for role, note_id, relation in (
            (
                "mission_comparison_note",
                checkpoint.semantic_note_id,
                checkpoint.semantic_relation,
            ),
            (
                "contradiction_initial_note",
                checkpoint.contradiction_initial_note_id,
                checkpoint.contradiction_initial_relation,
            ),
            (
                "contradiction_followup_note",
                checkpoint.contradiction_followup_note_id,
                checkpoint.contradiction_followup_relation,
            ),
            (
                "evidence_gap_followup_note",
                checkpoint.evidence_gap_followup_note_id,
                checkpoint.evidence_gap_followup_relation,
            ),
        ):
            if not note_id:
                continue
            note = notes.get(note_id)
            goal_basis.append(
                {
                    "role": role,
                    "note_id": note_id,
                    "recorded_relation": relation or None,
                    "resolved": note is not None,
                    "evidence": (
                        evidence_trace(note.evidence_ids) if note is not None else []
                    ),
                }
            )
    support = supporting_comparison_review(run, checkpoint)
    return {
        "mission_comparison_note_id": (
            checkpoint.semantic_note_id or None if checkpoint is not None else None
        ),
        "mission_comparison_review_id": (
            mission_review.review_id if mission_review is not None else None
        ),
        "goal_basis": {
            "comparison_notes": goal_basis,
            "contradiction_outcome": (
                checkpoint.contradiction_outcome or None
                if checkpoint is not None
                else None
            ),
            "evidence_gap_outcome": (
                checkpoint.evidence_gap_outcome or None
                if checkpoint is not None
                else None
            ),
            "supporting_review_id": support.review_id if support else None,
        },
        "source_observations": [
            observation(source.document_id) for source in run.sources
        ],
        "comparison_reviews": reviews,
        "claims": claims,
    }


def _refuse_credentialed_urls(run: ResearchRun) -> None:
    """Fail closed rather than export a URL that carries credentials."""
    urls = [source.url for source in run.sources]
    urls.extend(
        candidate.url
        for discovery in run.discoveries
        for candidate in discovery.candidates
    )
    for url in urls:
        try:
            parsed = urlparse(url)
        except ValueError as error:
            raise ResearchError("A recorded URL could not be audited.") from error
        if parsed.username is not None or parsed.password is not None:
            raise ResearchError(
                "A recorded URL includes credentials; the mission audit was not "
                "generated."
            )


def _evidence_trace_line(trace: dict[str, Any]) -> str:
    if not trace["resolved"] or trace.get("source") is None:
        return f"evidence {_inline(trace['evidence_id'])}: not resolved in this run"
    source = trace["source"]
    content = (
        f"`{source['content_sha256']}`" if source["content_sha256"] else "unrecorded"
    )
    return (
        f"evidence {_inline(trace['evidence_id'])} → source "
        f"{_inline(source['document_id'])} ({_inline(source['url'])}; content "
        f"SHA-256 {content})"
    )


def _typed(value: object) -> str:
    """Show a typed enum value verbatim; it is never user or source text."""
    return str(value) if value else "unavailable"


def _optional(value: object) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return _inline(str(value))
