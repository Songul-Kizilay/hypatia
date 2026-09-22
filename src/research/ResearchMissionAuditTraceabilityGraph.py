"""Typed, frozen, Tkinter-independent node/edge view of one mission's already-
computed traceability structure.

`ResearchMissionAudit.build_mission_audit`'s internal `_traceability()`
helper already resolves every recorded ID to an exact claim, evidence,
source observation, comparison review, contradiction or revalidation record
-- or reports it unresolved when it does not resolve.  This module performs
no resolution of its own: `traceability_graph_for` takes exactly the dict
`_traceability()` already produced (the `"traceability"` value of a built
mission audit, when the audit has a run) and re-shapes it into explicit,
frozen node and edge objects for later in-app display.

Every ID on every node or edge here is copied verbatim from that input
dict.  Nothing is matched by URL, content hash, title or timestamp, nothing
is looked up in any store, and nothing is inferred that the input dict does
not already say explicitly.  A reference the input dict already reported as
unresolved is carried through as an unresolved edge -- naming the exact ID
it did not resolve to -- never silently dropped and never pointed at a
fabricated node.  This graph is derived fresh from the audit dict every time
it is built; it is never persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from core.Exceptions import ResearchError


class TraceabilityNodeKind(StrEnum):
    """Discriminates which node collection a `TraceabilityNodeRef` names."""

    SOURCE_OBSERVATION = "source_observation"
    DISCOVERY_CANDIDATE = "discovery_candidate"
    EVIDENCE = "evidence"
    COMPARISON_REVIEW = "comparison_review"
    CLAIM = "claim"
    CONTRADICTION = "contradiction"
    GOAL_BASIS_NOTE = "goal_basis_note"
    REVALIDATION = "revalidation"
    REVALIDATION_OBSERVATION = "revalidation_observation"


@dataclass(frozen=True, slots=True)
class TraceabilityNodeRef:
    """Names one node by its kind and the exact ID already in the input dict."""

    kind: TraceabilityNodeKind
    node_id: str


@dataclass(frozen=True, slots=True)
class TraceabilityEdge:
    """One directed relation the input dict already recorded between two IDs.

    `resolved` is copied from the input dict's own resolved/unresolved
    verdict for that exact reference (or, where the input dict only implies
    it by which fields are present, derived from that same presence -- never
    from matching URL, hash, title or time).  When `resolved` is `False`,
    `target` still names the unresolved ID; no node exists for it.
    """

    relation: str
    source: TraceabilityNodeRef
    target: TraceabilityNodeRef
    resolved: bool


@dataclass(frozen=True, slots=True)
class SourceObservationNode:
    """One resolved source observation, exactly as `observation_of()` reported."""

    node_id: str
    observation_id: str | None
    document_id: str
    requested_url: str | None
    url: str
    content_sha256: str | None
    fetched_at: str
    added_at: str


@dataclass(frozen=True, slots=True)
class DiscoveryCandidateNode:
    """One resolved discovery candidate, exactly as `candidate_trace()` reported.

    Only created when the input dict marked the candidate resolved; an
    unresolved candidate reference is carried as an edge naming its
    `candidate_id` with `resolved=False`, with no node fabricated for it.
    """

    node_id: str
    candidate_id: str
    discovery_id: str
    url: str
    title: str


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    """One resolved evidence record, exactly as `evidence_trace()` reported.

    Only created when the input dict's evidence trace entry included the
    record's own fields (`chunk_id`/`chunk_sha256`); an evidence reference the
    input dict could not resolve to a record at all is carried only as an
    unresolved edge, with no node fabricated for it.

    `source_resolved` copies that same trace entry's own `resolved` flag,
    which (once the evidence record itself resolved) states whether *its*
    source observation also resolved.  When it is `False`, the input dict
    carries no ID at all for the unresolved source, so no edge is added for
    it; this field is the only place that unresolved state is recorded, and
    it is copied verbatim, never dropped.
    """

    node_id: str
    evidence_id: str
    chunk_id: str
    chunk_sha256: str
    source_resolved: bool


@dataclass(frozen=True, slots=True)
class ComparisonReviewNode:
    """One recorded operator comparison review, exactly as `_traceability()` reports."""

    node_id: str
    review_id: str
    note_id: str
    decision: str
    current: bool
    supersedes_review_id: str | None
    source_document_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClaimNode:
    """One recorded claim, exactly as `_traceability()` reported."""

    node_id: str
    claim_id: str
    epistemic_state: str
    current: bool
    supersedes_claim_id: str | None
    source_document_ids: tuple[str, ...]
    unrecorded_evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContradictionClaimSummary:
    """One claim's contradiction-local summary, exactly as `_traceability()` reported.

    Distinct from -- and may be a separate copy of the same values as -- the
    matching top-level `ClaimNode`; both are already present verbatim in the
    input dict and neither is derived from the other.
    """

    claim_id: str
    resolved: bool
    epistemic_state: str | None
    current: bool


@dataclass(frozen=True, slots=True)
class ContradictionNode:
    """One recorded claim contradiction, exactly as `_traceability()` reported."""

    node_id: str
    contradiction_id: str
    recorded_at: str
    claims: tuple[ContradictionClaimSummary, ...]


@dataclass(frozen=True, slots=True)
class GoalBasisNoteNode:
    """One comparison note cited as basis for the mission's goal evaluation."""

    node_id: str
    role: str
    note_id: str
    recorded_relation: str | None
    resolved: bool


@dataclass(frozen=True, slots=True)
class RevalidationObservationNode:
    """One endpoint (earlier or later) of a recorded source revalidation."""

    node_id: str
    run_id: str
    observation_id: str
    document_id: str
    requested_url: str | None
    url: str
    content_sha256: str | None
    fetched_at: str
    added_at: str


@dataclass(frozen=True, slots=True)
class RevalidationNode:
    """One recorded source revalidation, exactly as `_traceability()` reported."""

    node_id: str
    revalidation_id: str
    outcome: str
    recorded_at: str


@dataclass(frozen=True, slots=True)
class GoalBasisGraph:
    """The recorded basis of the mission's goal evaluation, re-shaped."""

    notes: tuple[GoalBasisNoteNode, ...]
    contradiction_outcome: str | None
    evidence_gap_outcome: str | None
    supporting_review_id: str | None


@dataclass(frozen=True, slots=True)
class ResearchMissionAuditTraceabilityGraph:
    """A mission's already-computed traceability data, re-shaped as a graph.

    Every ID here traces back to an ID already present in the traceability
    dict this was built from.  Nothing is added, nothing already present is
    omitted, and no relation not already recorded there is introduced.
    """

    mission_comparison_note_id: str | None
    mission_comparison_review_id: str | None
    goal_basis: GoalBasisGraph
    source_observations: tuple[SourceObservationNode, ...]
    discovery_candidates: tuple[DiscoveryCandidateNode, ...]
    evidence: tuple[EvidenceNode, ...]
    comparison_reviews: tuple[ComparisonReviewNode, ...]
    claims: tuple[ClaimNode, ...]
    claim_contradictions: tuple[ContradictionNode, ...]
    source_revalidations: tuple[RevalidationNode, ...]
    revalidation_observations: tuple[RevalidationObservationNode, ...]
    edges: tuple[TraceabilityEdge, ...]


def _require(mapping: Any, key: str, context: str) -> Any:
    if not isinstance(mapping, dict) or key not in mapping:
        raise ResearchError(
            f"A mission audit traceability graph requires '{key}' in {context}."
        )
    return mapping[key]


def _source_node_id(source: dict[str, Any]) -> str:
    observation_id = source.get("observation_id")
    if isinstance(observation_id, str) and observation_id:
        return observation_id
    document_id = source["document_id"]
    if not isinstance(document_id, str) or not document_id:
        raise ResearchError(
            "A mission audit source observation is missing its document ID."
        )
    return document_id


def _source_observation_node(source: dict[str, Any]) -> SourceObservationNode:
    return SourceObservationNode(
        node_id=_source_node_id(source),
        observation_id=source.get("observation_id"),
        document_id=source["document_id"],
        requested_url=source.get("requested_url"),
        url=source["url"],
        content_sha256=source.get("content_sha256"),
        fetched_at=source["fetched_at"],
        added_at=source["added_at"],
    )


def _discovery_candidate_edges_and_nodes(
    source_ref: TraceabilityNodeRef, candidate: dict[str, Any] | None
) -> tuple[list[TraceabilityEdge], list[DiscoveryCandidateNode]]:
    if candidate is None:
        return [], []
    candidate_id = candidate["candidate_id"]
    resolved = bool(candidate["resolved"])
    edges = [
        TraceabilityEdge(
            relation="source_discovery_candidate",
            source=source_ref,
            target=TraceabilityNodeRef(
                TraceabilityNodeKind.DISCOVERY_CANDIDATE, candidate_id
            ),
            resolved=resolved,
        )
    ]
    if not resolved:
        return edges, []
    node = DiscoveryCandidateNode(
        node_id=candidate_id,
        candidate_id=candidate_id,
        discovery_id=candidate["discovery_id"],
        url=candidate["url"],
        title=candidate["title"],
    )
    return edges, [node]


def _evidence_edges_and_nodes(
    from_ref: TraceabilityNodeRef,
    relation: str,
    traces: list[dict[str, Any]],
) -> tuple[list[TraceabilityEdge], list[EvidenceNode]]:
    """Re-shape one `evidence_trace()` list into edges from `from_ref`.

    An entry with no `chunk_id` key is an evidence reference the input dict
    could not resolve to a record at all: carried as one unresolved edge,
    naming the evidence ID, with no `EvidenceNode` created for it.  An entry
    with a `chunk_id` key is a resolved evidence record: one resolved edge to
    a created `EvidenceNode`, plus -- only when its own source also
    resolved -- a further `evidence_source` edge to the source observation.
    """
    edges: list[TraceabilityEdge] = []
    nodes: list[EvidenceNode] = []
    for trace in traces:
        evidence_id = trace["evidence_id"]
        evidence_ref = TraceabilityNodeRef(TraceabilityNodeKind.EVIDENCE, evidence_id)
        if "chunk_id" not in trace:
            edges.append(
                TraceabilityEdge(
                    relation=relation,
                    source=from_ref,
                    target=evidence_ref,
                    resolved=False,
                )
            )
            continue
        source_resolved = bool(trace["resolved"])
        nodes.append(
            EvidenceNode(
                node_id=evidence_id,
                evidence_id=evidence_id,
                chunk_id=trace["chunk_id"],
                chunk_sha256=trace["chunk_sha256"],
                source_resolved=source_resolved,
            )
        )
        edges.append(
            TraceabilityEdge(
                relation=relation, source=from_ref, target=evidence_ref, resolved=True
            )
        )
        source = trace["source"]
        if source is not None:
            edges.append(
                TraceabilityEdge(
                    relation="evidence_source",
                    source=evidence_ref,
                    target=TraceabilityNodeRef(
                        TraceabilityNodeKind.SOURCE_OBSERVATION, _source_node_id(source)
                    ),
                    resolved=True,
                )
            )
    return edges, nodes


def traceability_graph_for(
    traceability: dict[str, Any],
) -> ResearchMissionAuditTraceabilityGraph:
    """Re-shape `_traceability()`'s already-computed output into a graph.

    `traceability` must be the exact dict `build_mission_audit(...)` already
    returns under its `"traceability"` key for a mission that has a run
    (that key is `None` when the mission has no run at all; there is nothing
    to re-shape in that case, and callers must not call this function then).
    This performs a pure re-projection: every node and edge names an ID
    already present in `traceability`, and no new relation is added.
    """
    if not isinstance(traceability, dict):
        raise ResearchError(
            "A mission audit traceability graph requires the traceability dict."
        )

    evidence_by_id: dict[str, EvidenceNode] = {}
    edges: list[TraceabilityEdge] = []

    def _absorb(
        new_edges: list[TraceabilityEdge], new_evidence: list[EvidenceNode]
    ) -> None:
        edges.extend(new_edges)
        for node in new_evidence:
            evidence_by_id.setdefault(node.node_id, node)

    source_observations = tuple(
        _source_observation_node(source)
        for source in _require(traceability, "source_observations", "traceability")
    )
    discovery_candidates: dict[str, DiscoveryCandidateNode] = {}
    for source, node in zip(
        traceability["source_observations"], source_observations, strict=True
    ):
        source_ref = TraceabilityNodeRef(
            TraceabilityNodeKind.SOURCE_OBSERVATION, node.node_id
        )
        new_edges, new_candidates = _discovery_candidate_edges_and_nodes(
            source_ref, source.get("discovery_candidate")
        )
        edges.extend(new_edges)
        for candidate in new_candidates:
            discovery_candidates.setdefault(candidate.node_id, candidate)

    goal_basis_dict = _require(traceability, "goal_basis", "traceability")
    goal_basis_notes = []
    for note in _require(goal_basis_dict, "comparison_notes", "goal_basis"):
        node_id = f"{note['role']}:{note['note_id']}"
        goal_basis_notes.append(
            GoalBasisNoteNode(
                node_id=node_id,
                role=note["role"],
                note_id=note["note_id"],
                recorded_relation=note.get("recorded_relation"),
                resolved=bool(note["resolved"]),
            )
        )
        note_ref = TraceabilityNodeRef(TraceabilityNodeKind.GOAL_BASIS_NOTE, node_id)
        _absorb(
            *_evidence_edges_and_nodes(
                note_ref, "goal_basis_evidence", note["evidence"]
            )
        )
    goal_basis = GoalBasisGraph(
        notes=tuple(goal_basis_notes),
        contradiction_outcome=goal_basis_dict.get("contradiction_outcome"),
        evidence_gap_outcome=goal_basis_dict.get("evidence_gap_outcome"),
        supporting_review_id=goal_basis_dict.get("supporting_review_id"),
    )

    comparison_review_dicts = list(
        _require(traceability, "comparison_reviews", "traceability")
    )
    review_ids = {review["review_id"] for review in comparison_review_dicts}
    comparison_reviews = []
    for review in comparison_review_dicts:
        comparison_reviews.append(
            ComparisonReviewNode(
                node_id=review["review_id"],
                review_id=review["review_id"],
                note_id=review["note_id"],
                decision=review["decision"],
                current=bool(review["current"]),
                supersedes_review_id=review.get("supersedes_review_id"),
                source_document_ids=tuple(review["source_document_ids"]),
            )
        )
        review_ref = TraceabilityNodeRef(
            TraceabilityNodeKind.COMPARISON_REVIEW, review["review_id"]
        )
        _absorb(
            *_evidence_edges_and_nodes(
                review_ref, "review_evidence", review["evidence"]
            )
        )
        supersedes = review.get("supersedes_review_id")
        if supersedes is not None:
            edges.append(
                TraceabilityEdge(
                    relation="review_supersession",
                    source=review_ref,
                    target=TraceabilityNodeRef(
                        TraceabilityNodeKind.COMPARISON_REVIEW, supersedes
                    ),
                    resolved=supersedes in review_ids,
                )
            )

    claim_dicts = list(_require(traceability, "claims", "traceability"))
    claim_ids = {claim["claim_id"] for claim in claim_dicts}
    claims = []
    for claim in claim_dicts:
        claims.append(
            ClaimNode(
                node_id=claim["claim_id"],
                claim_id=claim["claim_id"],
                epistemic_state=claim["epistemic_state"],
                current=bool(claim["current"]),
                supersedes_claim_id=claim.get("supersedes_claim_id"),
                source_document_ids=tuple(claim["source_document_ids"]),
                unrecorded_evidence_ids=tuple(claim["unrecorded_evidence_ids"]),
            )
        )
        claim_ref = TraceabilityNodeRef(TraceabilityNodeKind.CLAIM, claim["claim_id"])
        _absorb(
            *_evidence_edges_and_nodes(claim_ref, "claim_evidence", claim["evidence"])
        )
        supersedes = claim.get("supersedes_claim_id")
        if supersedes is not None:
            edges.append(
                TraceabilityEdge(
                    relation="claim_supersession",
                    source=claim_ref,
                    target=TraceabilityNodeRef(TraceabilityNodeKind.CLAIM, supersedes),
                    resolved=supersedes in claim_ids,
                )
            )

    contradiction_dicts = list(
        _require(traceability, "claim_contradictions", "traceability")
    )
    claim_contradictions = []
    for contradiction in contradiction_dicts:
        summaries = tuple(
            ContradictionClaimSummary(
                claim_id=entry["claim_id"],
                resolved=bool(entry["resolved"]),
                epistemic_state=entry.get("epistemic_state"),
                current=bool(entry["current"]),
            )
            for entry in contradiction["claims"]
        )
        claim_contradictions.append(
            ContradictionNode(
                node_id=contradiction["contradiction_id"],
                contradiction_id=contradiction["contradiction_id"],
                recorded_at=contradiction["recorded_at"],
                claims=summaries,
            )
        )
        contradiction_ref = TraceabilityNodeRef(
            TraceabilityNodeKind.CONTRADICTION, contradiction["contradiction_id"]
        )
        for entry in contradiction["claims"]:
            edges.append(
                TraceabilityEdge(
                    relation="contradiction_claim",
                    source=contradiction_ref,
                    target=TraceabilityNodeRef(
                        TraceabilityNodeKind.CLAIM, entry["claim_id"]
                    ),
                    resolved=bool(entry["resolved"]),
                )
            )
        _absorb(
            *_evidence_edges_and_nodes(
                contradiction_ref, "contradiction_evidence", contradiction["evidence"]
            )
        )

    revalidation_dicts = list(
        _require(traceability, "source_revalidations", "traceability")
    )
    source_revalidations = []
    revalidation_observations: dict[str, RevalidationObservationNode] = {}
    for revalidation in revalidation_dicts:
        source_revalidations.append(
            RevalidationNode(
                node_id=revalidation["revalidation_id"],
                revalidation_id=revalidation["revalidation_id"],
                outcome=revalidation["outcome"],
                recorded_at=revalidation["recorded_at"],
            )
        )
        revalidation_ref = TraceabilityNodeRef(
            TraceabilityNodeKind.REVALIDATION, revalidation["revalidation_id"]
        )
        for role, relation in (
            ("earlier", "revalidation_earlier_observation"),
            ("later", "revalidation_later_observation"),
        ):
            endpoint = revalidation[role]
            node_id = f"{endpoint['run_id']}:{endpoint['observation_id']}"
            revalidation_observations.setdefault(
                node_id,
                RevalidationObservationNode(
                    node_id=node_id,
                    run_id=endpoint["run_id"],
                    observation_id=endpoint["observation_id"],
                    document_id=endpoint["document_id"],
                    requested_url=endpoint.get("requested_url"),
                    url=endpoint["url"],
                    content_sha256=endpoint.get("content_sha256"),
                    fetched_at=endpoint["fetched_at"],
                    added_at=endpoint["added_at"],
                ),
            )
            edges.append(
                TraceabilityEdge(
                    relation=relation,
                    source=revalidation_ref,
                    target=TraceabilityNodeRef(
                        TraceabilityNodeKind.REVALIDATION_OBSERVATION, node_id
                    ),
                    resolved=True,
                )
            )

    # The same evidence_source (or other) edge can be computed once per citing
    # claim/review/contradiction/goal-basis note that shares the same
    # evidence_id; each computation reports the exact same
    # (relation, source, target, resolved) fact, since it always resolves
    # through the same evidence and source records.  Collapsing identical
    # duplicates keeps the graph one edge per distinct relation without
    # dropping any relation that differs in source, target or resolution.
    deduplicated_edges = tuple(dict.fromkeys(edges))

    return ResearchMissionAuditTraceabilityGraph(
        mission_comparison_note_id=traceability.get("mission_comparison_note_id"),
        mission_comparison_review_id=traceability.get("mission_comparison_review_id"),
        goal_basis=goal_basis,
        source_observations=source_observations,
        discovery_candidates=tuple(discovery_candidates.values()),
        evidence=tuple(evidence_by_id.values()),
        comparison_reviews=tuple(comparison_reviews),
        claims=tuple(claims),
        claim_contradictions=tuple(claim_contradictions),
        source_revalidations=tuple(source_revalidations),
        revalidation_observations=tuple(revalidation_observations.values()),
        edges=deduplicated_edges,
    )
