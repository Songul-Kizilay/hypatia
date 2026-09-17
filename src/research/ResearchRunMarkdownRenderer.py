"""Deterministic Markdown rendering for one immutable research-run snapshot."""

from __future__ import annotations

from research.ResearchRun import ResearchRun

_UNSAFE_DIRECTIONAL_CONTROLS = frozenset(
    {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)


def render_research_run_markdown(run: ResearchRun) -> str:
    """Render persisted research data without providers, live indexes, or writes."""
    if not isinstance(run, ResearchRun):
        raise TypeError("Research Markdown export expects a ResearchRun.")

    lines = [
        "# Hypatia Research Export",
        "",
        f"- **Run ID:** {_inline(run.run_id)}",
        f"- **Status:** {run.status.value}",
        f"- **Created:** {run.created_at.isoformat()}",
        f"- **Updated:** {run.updated_at.isoformat()}",
        f"- **Accepted sources:** {len(run.sources)}",
        f"- **Evidence records:** {len(run.evidence)}",
        f"- **Assessments:** {len(run.assessments)}",
        f"- **Comparison notes:** {len(run.comparison_notes)}",
        f"- **Comparison reviews:** {len(run.comparison_reviews)}",
        f"- **Claims:** {len(run.claims)}",
        f"- **Claim contradictions:** {len(run.claim_contradictions)}",
        f"- **Failures:** {len(run.failures)}",
        "",
        "## Research Question",
        "",
        *_quote(run.question),
        "",
        "## Accepted Sources",
        "",
    ]

    superseded_ids = {
        assessment.supersedes_assessment_id
        for assessment in run.assessments
        if assessment.supersedes_assessment_id is not None
    }
    if not run.sources:
        lines.extend(("_No accepted sources._", ""))
    for source_index, source in enumerate(run.sources, start=1):
        evidence = tuple(
            record
            for record in run.evidence
            if record.source_document_id == source.document_id
        )
        assessments = tuple(
            record
            for record in run.assessments
            if record.source_document_id == source.document_id
        )
        lines.extend(
            (
                f"### Source {source_index}: {_inline(source.title)}",
                "",
                f"- **Document ID:** {_inline(source.document_id)}",
                f"- **URL:** {_inline(source.url)}",
                (
                    f"- **Requested URL:** {_inline(source.requested_url)}"
                    if source.requested_url is not None
                    else "- **Requested URL:** unrecorded"
                ),
                (
                    "- **Discovery candidate:** "
                    f"{_inline(source.discovery_candidate_id)}"
                    if source.discovery_candidate_id is not None
                    else "- **Discovery candidate:** unrecorded"
                ),
                f"- **Content type:** {_inline(source.content_type)}",
                f"- **Data taint:** {_inline(source.taint_label)}",
                (
                    "- **Instruction authority:** "
                    f"{_inline(source.instruction_authority)}"
                ),
                f"- **Fetched:** {source.fetched_at.isoformat()}",
                f"- **Accepted:** {source.added_at.isoformat()}",
                (
                    f"- **Observed content SHA-256:** `{source.content_sha256}`"
                    if source.content_sha256 is not None
                    else "- **Observed content SHA-256:** unrecorded (accepted "
                    "before content versioning)"
                ),
                "",
                "#### Evidence",
                "",
            )
        )
        if not evidence:
            lines.extend(("_No evidence recorded for this source._", ""))
        for evidence_index, evidence_record in enumerate(evidence, start=1):
            truncation = "yes" if evidence_record.excerpt_truncated else "no"
            lines.extend(
                (
                    f"##### Evidence {evidence_index}",
                    "",
                    f"- **Evidence ID:** {_inline(evidence_record.evidence_id)}",
                    f"- **Chunk ID:** {_inline(evidence_record.chunk_id)}",
                    f"- **Paragraph:** {evidence_record.chunk_index + 1}",
                    f"- **Excerpt truncated:** {truncation}",
                    f"- **Chunk SHA-256:** `{evidence_record.chunk_sha256}`",
                    f"- **Recorded:** {evidence_record.recorded_at.isoformat()}",
                    "- **User note:**",
                    "",
                    *_quote(evidence_record.note),
                    "",
                    "- **Persisted excerpt:**",
                    "",
                    *_quote(evidence_record.excerpt),
                    "",
                )
            )
        lines.extend(("#### Assessments", ""))
        if not assessments:
            lines.extend(("_No assessments recorded for this source._", ""))
        for assessment_index, assessment_record in enumerate(assessments, start=1):
            audit_state = (
                "superseded"
                if assessment_record.assessment_id in superseded_ids
                else "current"
            )
            predecessor = assessment_record.supersedes_assessment_id or "none"
            lines.extend(
                (
                    f"##### Assessment {assessment_index}",
                    "",
                    f"- **Assessment ID:** {_inline(assessment_record.assessment_id)}",
                    f"- **Audit state:** {audit_state}",
                    (
                        "- **Information trust:** "
                        f"{assessment_record.information_trust.value}"
                    ),
                    f"- **Usefulness:** {assessment_record.usefulness.value}",
                    f"- **Applicability:** {assessment_record.applicability.value}",
                    f"- **Independence:** {assessment_record.independence.value}",
                    (
                        "- **Publication status:** "
                        f"{assessment_record.publication_status.value}"
                    ),
                    "- **Evidence IDs:** "
                    + ", ".join(
                        _inline(value) for value in assessment_record.evidence_ids
                    ),
                    f"- **Supersedes:** {_inline(predecessor)}",
                    f"- **Recorded:** {assessment_record.recorded_at.isoformat()}",
                    "- **User assessment:**",
                    "",
                    *_quote(assessment_record.text),
                    "",
                )
            )

    lines.extend(("## Comparison Notes", ""))
    if not run.comparison_notes:
        lines.extend(("_No comparison notes recorded._", ""))
    for note_index, note in enumerate(run.comparison_notes, start=1):
        lines.extend(
            (
                f"### Comparison Note {note_index}",
                "",
                f"- **Note ID:** {_inline(note.note_id)}",
                "- **Source document IDs:** "
                + ", ".join(_inline(value) for value in note.source_document_ids),
                "- **Evidence IDs:** "
                + ", ".join(_inline(value) for value in note.evidence_ids),
                "- **Assessment IDs:** "
                + ", ".join(_inline(value) for value in note.assessment_ids),
                f"- **Recorded:** {note.recorded_at.isoformat()}",
                "- **Recorded comparison note (tentative; not a verified result):**",
                "",
                *_quote(note.text),
                "",
            )
        )

    lines.extend(("## Operator Comparison Reviews", ""))
    superseded_review_ids = {
        review.supersedes_review_id
        for review in run.comparison_reviews
        if review.supersedes_review_id is not None
    }
    if not run.comparison_reviews:
        lines.extend(("_No comparison reviews recorded._", ""))
    else:
        lines.extend(
            (
                "_An operator review is a bounded judgement about one exact "
                "comparison note and its evidence, not model output or a "
                "factual-truth decision._",
                "",
            )
        )
    for review_index, review in enumerate(run.comparison_reviews, start=1):
        review_state = (
            "superseded" if review.review_id in superseded_review_ids else "current"
        )
        lines.extend(
            (
                f"### Comparison Review {review_index}",
                "",
                f"- **Review ID:** {_inline(review.review_id)}",
                f"- **Audit state:** {review_state}",
                f"- **Note ID:** {_inline(review.note_id)}",
                f"- **Decision:** {review.decision.value}",
                "- **Evidence IDs:** "
                + ", ".join(_inline(value) for value in review.evidence_ids),
                f"- **Supersedes:** {_inline(review.supersedes_review_id or 'none')}",
                f"- **Recorded:** {review.recorded_at.isoformat()}",
                "- **Operator reason:**",
                "",
                *_quote(review.note),
                "",
            )
        )

    lines.extend(("## Evidence-linked Claims", ""))
    superseded_claim_ids = {
        claim.supersedes_claim_id
        for claim in run.claims
        if claim.supersedes_claim_id is not None
    }
    if not run.claims:
        lines.extend(("_No claims recorded._", ""))
    for claim_index, claim in enumerate(run.claims, start=1):
        audit_state = (
            "superseded" if claim.claim_id in superseded_claim_ids else "current"
        )
        lines.extend(
            (
                f"### Claim {claim_index}",
                "",
                f"- **Claim ID:** {_inline(claim.claim_id)}",
                f"- **Audit state:** {audit_state}",
                f"- **Epistemic state:** {claim.epistemic_state.value}",
                f"- **Authored confidence:** {claim.confidence.value}",
                "- **Source document IDs:** "
                + ", ".join(_inline(value) for value in claim.source_document_ids),
                "- **Evidence IDs:** "
                + ", ".join(_inline(value) for value in claim.evidence_ids),
                f"- **Supersedes:** {_inline(claim.supersedes_claim_id or 'none')}",
                f"- **Recorded:** {claim.recorded_at.isoformat()}",
                "- **User-authored claim:**",
                "",
                *_quote(claim.text),
                "",
            )
        )

    lines.extend(("## User-reviewed Claim Contradictions", ""))
    if not run.claim_contradictions:
        lines.extend(("_No claim contradictions recorded._", ""))
    for contradiction_index, contradiction in enumerate(
        run.claim_contradictions,
        start=1,
    ):
        lines.extend(
            (
                f"### Claim Contradiction {contradiction_index}",
                "",
                (
                    "- **Contradiction ID:** "
                    f"{_inline(contradiction.contradiction_id)}"
                ),
                "- **Claim IDs:** "
                + ", ".join(_inline(value) for value in contradiction.claim_ids),
                "- **Evidence IDs:** "
                + ", ".join(_inline(value) for value in contradiction.evidence_ids),
                f"- **Recorded:** {contradiction.recorded_at.isoformat()}",
                "- **User-authored contradiction note:**",
                "",
                *_quote(contradiction.note),
                "",
            )
        )

    lines.extend(("## Recorded Failures", ""))
    if not run.failures:
        lines.extend(("_No failures recorded._", ""))
    for failure_index, failure in enumerate(run.failures, start=1):
        lines.extend(
            (
                f"### Failure {failure_index}",
                "",
                f"- **Stage:** {_inline(failure.stage)}",
                f"- **Occurred:** {failure.occurred_at.isoformat()}",
                "- **Safe reason:**",
                "",
                *_quote(failure.reason),
                "",
            )
        )

    lines.extend(
        (
            "---",
            "",
            "Generated locally from persisted Hypatia research records. "
            "No network, provider, or LLM was used.",
            "",
        )
    )
    return "\n".join(lines)


def _inline(value: str) -> str:
    normalized = " ".join(_clean_text(value).split())
    return _escape_markdown(normalized, escape_line_prefix=False)


def _quote(value: str) -> tuple[str, ...]:
    lines = _clean_text(value).split("\n")
    return tuple(
        ">" if not line else f"> {_escape_markdown(line, escape_line_prefix=True)}"
        for line in lines
    )


def _escape_markdown(value: str, *, escape_line_prefix: bool) -> str:
    escaped = value
    markers = [
        "\\",
        "`",
        "*",
        "_",
        "{",
        "}",
        "[",
        "]",
        "<",
        ">",
        "!",
        "|",
    ]
    if escape_line_prefix:
        markers.extend(("#", "+", "-"))
    for marker in markers:
        escaped = escaped.replace(marker, f"\\{marker}")
    return escaped


def _clean_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(
        (
            character
            if character not in _UNSAFE_DIRECTIONAL_CONTROLS
            and (character in {"\n", "\t"} or 32 <= ord(character) != 127)
            else "�"
        )
        for character in normalized
    ).replace("\t", "    ")
