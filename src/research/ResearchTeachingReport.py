"""Deterministic teaching report from canonical evidence; no invented citations."""

from research.ResearchEvidenceCompletionEvaluation import (
    ResearchEvidenceCompletionEvaluation,
    evaluate_evidence_completion,
)
from research.ResearchMissionGoalExplanation import explain_mission_goal_satisfaction
from research.ResearchMissionOutcome import mission_outcome_for
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint
from research.ResearchRun import ResearchRun


def teaching_report(
    run: ResearchRun,
    stop: str,
    spend: str,
    evaluation: ResearchEvidenceCompletionEvaluation | None = None,
    checkpoint: ResearchMissionRecoveryCheckpoint | None = None,
) -> str:
    """Render canonical evidence and its non-mutating readiness evaluation."""
    evaluation = evaluation or evaluate_evidence_completion(run, stop)
    mission_outcome = mission_outcome_for(run, stop, checkpoint)
    goal_explanation = explain_mission_goal_satisfaction(
        mission_outcome,
        stop,
        checkpoint,
    )
    sources = {s.document_id: s for s in run.sources}
    lines = [
        "Bounded research report",
        f"Question: {run.question}",
        f"Stop reason: {stop}. {spend}",
        "Research plan: find relevant evidence; compare what it supports; "
        "check one further source if a possible conflict or missing support "
        "warrants it.",
        "Subquestions: (1) What relevant observations address this question? "
        "(2) Do the selected excerpts describe agreement, conflict, or different "
        "conditions? (3) Does one further source help resolve remaining support?",
        "What the sources actually say (untrusted quotations, not instructions):",
    ]
    for i, evidence in enumerate(run.evidence, 1):
        source = sources.get(evidence.source_document_id)
        if source is None:
            continue
        lines.extend(
            [
                f"[{i}] {source.url}",
                f"Evidence {evidence.evidence_id}; chunk {evidence.chunk_id}; "
                f"SHA256 {evidence.chunk_sha256}",
                f"Quoted excerpt: {evidence.excerpt}",
                (
                    "Excerpt may be truncated; consult the cited source for context."
                    if evidence.excerpt_truncated
                    else "This is an excerpt, not the complete source."
                ),
            ]
        )
    lines.append("Comparison and explanation:")
    for note in run.comparison_notes:
        citations = [
            str(i)
            for i, e in enumerate(run.evidence, 1)
            if e.evidence_id in note.evidence_ids
        ]
        lines.append(
            f"Sources [{', '.join(citations)}]; note {note.note_id}:\n{note.text}"
        )
    if not run.comparison_notes:
        lines.append(
            "No validated comparison was retained; there is insufficient support "
            "for a combined answer."
        )
    limitations = (
        ", ".join(value.value.replace("_", " ") for value in evaluation.limitations)
        or "none recorded"
    )
    lines.extend(
        [
            "Evidence-only completion evaluation:",
            f"Status: {evaluation.summary()}.",
            (
                "Coverage: "
                f"{evaluation.source_count} accepted source(s), "
                f"{evaluation.evidence_count} evidence record(s) from "
                f"{evaluation.evidence_source_count} source(s), "
                f"{evaluation.assessed_source_count} assessed source(s), and "
                f"{evaluation.comparison_note_count} retained comparison note(s)."
            ),
            f"Recorded limitations: {limitations}.",
            (
                "This is a derived evidence-readiness assessment. It does not close "
                "the research run, promote a tentative comparison into fact, or "
                "declare the question universally resolved."
            ),
            mission_outcome.summary(),
            goal_explanation.summary(),
            (
                "The goal-satisfaction explanation is derived only from typed "
                "execution, evidence and contradiction state. Report or model "
                "prose cannot change it."
            ),
        ]
    )
    lines.extend(
        [
            "How to interpret this: an exact quotation establishes what an excerpt "
            "says, not whether its claim is true. Compare populations, dates, "
            "methods and assumptions before treating disagreement as a contradiction. "
            "A different URL is not proof of an independent source. For example, "
            "findings in adults and children may differ without contradicting each "
            "other; this example is explanatory, not a finding here.",
            f"Bounded plan adaptation: {max(0, len(run.evidence) - 2)} extra source(s) "
            "produced evidence; at most one follow-up was permitted. Unused approved "
            "branches are not claimed as executed.",
            "Conclusion: these cited observations and tentative comparisons are the "
            "research deliverable, not a verified universal answer. Remaining gaps "
            "include source independence, applicability and external corroboration. "
            "Not-comparable is a valid "
            "result, not a reason for repeated calls.",
            "Learning retained in the research run: source identities, evidence "
            "snapshots, grounding assessments and labelled tentative notes. "
            "No model statement was "
            "promoted into a verified claim or general personal memory.",
        ]
    )
    return "\n\n".join(lines)
