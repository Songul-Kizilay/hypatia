"""Deterministic teaching report from canonical evidence; no invented citations."""

from research.ResearchRun import ResearchRun


def teaching_report(run: ResearchRun, stop: str, spend: str) -> str:
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
