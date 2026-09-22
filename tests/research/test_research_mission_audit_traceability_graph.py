"""`traceability_graph_for` must be a strict, content-identical re-shaping of
`ResearchMissionAudit._traceability()`'s already-computed output.

Every fixture below is fed through the real `build_mission_audit(...)` entry
point so the traceability dict under test is exactly what production code
produces -- never a hand-built stand-in for the common, fully-resolved
paths.  A separate, explicitly-labelled test exercises the two unresolved
branches `_traceability()` defends against but that a validated
`ResearchRun` cannot itself produce (evidence and discovery-candidate
references that fail to resolve): it feeds `traceability_graph_for` a
hand-built dict that copies `_traceability()`'s own documented shape for
those branches verbatim, to prove the re-shaping still reports them as
unresolved rather than dropping or guessing them.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimContradictionRecord import (
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchComparisonReviewRecord import (
    ResearchComparisonReviewDecision,
    ResearchComparisonReviewRecord,
)
from research.ResearchDisclosure import ResearchDisclosure
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchMissionAudit import build_mission_audit
from research.ResearchMissionAuditTraceabilityGraph import (
    TraceabilityNodeKind,
    traceability_graph_for,
)
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint
from research.ResearchMissionScope import SEMANTIC_POLICY, ResearchMissionScope
from research.ResearchPlanExecutionSnapshot import (
    ResearchPlanExecutionSnapshot,
    ResearchPlanExecutionStepSnapshot,
)
from research.ResearchPlanExecutionStatus import ResearchPlanExecutionStatus
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepStatus import ResearchPlanStepStatus
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRecord import ResearchSourceRecord
from research.ResearchSourceRevalidationOutcome import (
    ResearchSourceRevalidationOutcome,
)
from research.ResearchSourceRevalidationRecord import (
    ResearchSourceRevalidationInspection,
    ResearchSourceRevalidationRecord,
)

STARTED = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
PLAN_DIGEST = sha256(b"mission-plan-content").hexdigest()


def _scope() -> ResearchMissionScope:
    from research.SemanticMissionPolicy import SemanticMissionPolicy

    return ResearchMissionScope(
        ResearchDiscoveryProviderName.CROSSREF,
        source_policy=SEMANTIC_POLICY,
        max_sources=3,
        semantic_policy=SemanticMissionPolicy(
            "http://127.0.0.1:11434/v1/chat/completions",
            "fixture",
            ResearchDisclosure.LOCAL_ONLY,
        ),
    )


def _snapshot(
    *,
    plan_id: str = "plan-1",
    research_run_id: str | None = "run-1",
    checkpoint: ResearchMissionRecoveryCheckpoint | None = None,
) -> ResearchPlanExecutionSnapshot:
    return ResearchPlanExecutionSnapshot(
        plan_id=plan_id,
        question="What do the recorded sources support?",
        status=ResearchPlanExecutionStatus.INTERRUPTED,
        steps=(
            ResearchPlanExecutionStepSnapshot(
                step_id="step-1",
                capability=ResearchPlanStepCapability.SOURCE_DISCOVERY,
                status=ResearchPlanStepStatus.COMPLETED,
            ),
        ),
        recorded_at=STARTED,
        research_run_id=research_run_id,
        mission_plan_digest=PLAN_DIGEST,
        mission_scope=_scope(),
        mission_disclosure=ResearchDisclosure.LOCAL_ONLY,
        mission_checkpoint=checkpoint,
    )


def _agreement_checkpoint(**changes: object) -> ResearchMissionRecoveryCheckpoint:
    values: dict[str, object] = {
        "semantic_note_id": "note-1",
        "semantic_input_fingerprint": "a" * 64,
        "semantic_relation": "possible_agreement",
    }
    values.update(changes)
    return ResearchMissionRecoveryCheckpoint(**values)  # type: ignore[arg-type]


def _full_run() -> ResearchRun:
    """A validated run exercising every resolvable traceability relation."""
    candidate = ResearchSourceCandidate(
        url="https://example.com/one",
        title="Source One",
        snippet="A discovered candidate.",
    )
    discovery = ResearchSourceDiscoveryRecord(
        discovery_id="discovery-1",
        query="defenses",
        provider="crossref",
        candidates=(candidate,),
        discovered_at=STARTED,
        candidate_ids=("candidate-1",),
    )
    source_one = ResearchSourceRecord(
        document_id="document-1",
        url="https://example.com/one",
        title="Source One",
        content_type="text/plain",
        fetched_at=STARTED,
        added_at=STARTED + timedelta(minutes=1),
        content_sha256="c" * 64,
        requested_url="https://example.com/one",
        discovery_candidate_id="candidate-1",
        observation_id="observation-1",
    )
    source_two = ResearchSourceRecord(
        document_id="document-2",
        url="https://example.com/two",
        title="Source Two",
        content_type="text/plain",
        fetched_at=STARTED,
        added_at=STARTED + timedelta(minutes=2),
        observation_id="observation-2",
    )
    evidence_one = ResearchEvidenceRecord(
        evidence_id="evidence-1",
        source_document_id="document-1",
        chunk_id="chunk-1",
        chunk_index=0,
        excerpt="First excerpt",
        excerpt_truncated=False,
        chunk_sha256=sha256(b"First excerpt").hexdigest(),
        note="Grounded excerpt only.",
        recorded_at=STARTED + timedelta(minutes=3),
    )
    evidence_two = ResearchEvidenceRecord(
        evidence_id="evidence-2",
        source_document_id="document-2",
        chunk_id="chunk-2",
        chunk_index=0,
        excerpt="Second excerpt",
        excerpt_truncated=False,
        chunk_sha256=sha256(b"Second excerpt").hexdigest(),
        note="Grounded excerpt only.",
        recorded_at=STARTED + timedelta(minutes=4),
    )
    assessment_one = ResearchSourceAssessmentRecord(
        assessment_id="assessment-1",
        source_document_id="document-1",
        evidence_ids=("evidence-1",),
        text="Assessment one.",
        recorded_at=STARTED + timedelta(minutes=5),
    )
    assessment_two = ResearchSourceAssessmentRecord(
        assessment_id="assessment-2",
        source_document_id="document-2",
        evidence_ids=("evidence-2",),
        text="Assessment two.",
        recorded_at=STARTED + timedelta(minutes=6),
    )
    note = ResearchSourceComparisonNoteRecord(
        note_id="note-1",
        source_document_ids=("document-1", "document-2"),
        evidence_ids=("evidence-1", "evidence-2"),
        assessment_ids=("assessment-1", "assessment-2"),
        text="Comparison note.",
        recorded_at=STARTED + timedelta(minutes=7),
    )
    claim_one = ResearchClaimRecord(
        claim_id="claim-1",
        text="The finding may affect the target.",
        epistemic_state=ResearchEpistemicState.HYPOTHESIS,
        confidence=ResearchClaimConfidence.LOW,
        source_document_ids=("document-1",),
        evidence_ids=("evidence-1",),
        recorded_at=STARTED + timedelta(minutes=8),
    )
    claim_two = ResearchClaimRecord(
        claim_id="claim-2",
        text="The persisted evidence contradicts the original claim.",
        epistemic_state=ResearchEpistemicState.CONTRADICTED,
        confidence=ResearchClaimConfidence.HIGH,
        source_document_ids=("document-2",),
        evidence_ids=("evidence-2",),
        recorded_at=STARTED + timedelta(minutes=9),
        supersedes_claim_id="claim-1",
    )
    contradiction = ResearchClaimContradictionRecord(
        contradiction_id="contradiction-1",
        claim_ids=("claim-1", "claim-2"),
        evidence_ids=("evidence-1", "evidence-2"),
        note="These disagree.",
        recorded_at=STARTED + timedelta(minutes=10),
    )
    review_one = ResearchComparisonReviewRecord(
        review_id="review-1",
        note_id="note-1",
        evidence_ids=("evidence-1", "evidence-2"),
        decision=ResearchComparisonReviewDecision.SUPPORTED,
        note="Both excerpts address the question.",
        recorded_at=STARTED + timedelta(minutes=9),
    )
    review_two = ResearchComparisonReviewRecord(
        review_id="review-2",
        note_id="note-1",
        evidence_ids=("evidence-1", "evidence-2"),
        decision=ResearchComparisonReviewDecision.NOT_SUPPORTED,
        note="Withdrawn after rereading.",
        recorded_at=STARTED + timedelta(minutes=10),
        supersedes_review_id="review-1",
    )
    return ResearchRun(
        run_id="run-1",
        question="What do the recorded sources support?",
        status=ResearchRunStatus.COLLECTING,
        sources=(source_one, source_two),
        failures=(),
        created_at=STARTED,
        updated_at=STARTED + timedelta(minutes=10),
        evidence=(evidence_one, evidence_two),
        discoveries=(discovery,),
        assessments=(assessment_one, assessment_two),
        comparison_notes=(note,),
        claims=(claim_one, claim_two),
        claim_contradictions=(contradiction,),
        comparison_reviews=(review_one, review_two),
    )


def _minimal_valid_traceability_dict() -> dict[str, Any]:
    """The smallest dict `traceability_graph_for` accepts as valid: every key
    `_require` demands is present, each with an empty/absent value -- the
    same shape `_traceability()` itself produces for a mission with no
    recorded material (see `TraceabilityGraphEmptyCaseTests`). Callers that
    want to prove a required key is enforced start from a fresh copy of this
    and delete exactly the key under test.
    """
    return {
        "mission_comparison_note_id": None,
        "mission_comparison_review_id": None,
        "goal_basis": {
            "comparison_notes": [],
            "contradiction_outcome": None,
            "evidence_gap_outcome": None,
            "supporting_review_id": None,
        },
        "source_observations": [],
        "source_revalidations": [],
        "comparison_reviews": [],
        "claims": [],
        "claim_contradictions": [],
    }


def _revalidation(run_id: str) -> ResearchSourceRevalidationInspection:
    earlier = ResearchSourceRecord(
        document_id="document-1",
        url="https://example.com/one",
        title="Source One",
        content_type="text/plain",
        fetched_at=STARTED,
        added_at=STARTED + timedelta(minutes=1),
        observation_id="observation-1",
    )
    later = ResearchSourceRecord(
        document_id="document-1",
        url="https://example.com/one",
        title="Source One",
        content_type="text/plain",
        fetched_at=STARTED + timedelta(days=1),
        added_at=STARTED + timedelta(days=1, minutes=1),
        observation_id="observation-1-revalidated",
    )
    record = ResearchSourceRevalidationRecord(
        revalidation_id="revalidation-1",
        earlier_run_id=run_id,
        earlier_observation_id="observation-1",
        later_run_id=run_id,
        later_observation_id="observation-1-revalidated",
        outcome=ResearchSourceRevalidationOutcome.CONTENT_UNCHANGED,
        recorded_at=STARTED + timedelta(days=1, minutes=2),
    )
    return ResearchSourceRevalidationInspection(record, earlier, later)


class TraceabilityGraphResolvedFidelityTests(unittest.TestCase):
    """Every node/edge in the graph must trace back to the real audit dict."""

    def setUp(self) -> None:
        run = _full_run()
        checkpoint = _agreement_checkpoint()
        snapshot = _snapshot(checkpoint=checkpoint)
        audit = build_mission_audit(
            snapshot,
            run,
            None,
            hypatia_version="test",
            source_revalidations=(_revalidation(run.run_id),),
        )
        self.traceability = audit["traceability"]
        self.graph = traceability_graph_for(self.traceability)

    def test_source_observations_are_reshaped_without_loss(self) -> None:
        expected = self.traceability["source_observations"]
        self.assertEqual(len(self.graph.source_observations), len(expected))
        for node, source in zip(self.graph.source_observations, expected, strict=True):
            self.assertEqual(node.node_id, source["observation_id"])
            self.assertEqual(node.observation_id, source["observation_id"])
            self.assertEqual(node.document_id, source["document_id"])
            self.assertEqual(node.requested_url, source["requested_url"])
            self.assertEqual(node.url, source["url"])
            self.assertEqual(node.content_sha256, source["content_sha256"])
            self.assertEqual(node.fetched_at, source["fetched_at"])
            self.assertEqual(node.added_at, source["added_at"])

    def test_a_legacy_source_without_an_observation_id_keys_by_document_id(
        self,
    ) -> None:
        # Sources accepted before observation identity existed never had one
        # backfilled; node identity must still be a real ID already present
        # in the dict (the document ID), never invented.
        base_run = _full_run()
        legacy_sources = tuple(
            (
                replace(source, observation_id=None)
                if source.document_id == "document-2"
                else source
            )
            for source in base_run.sources
        )
        run = replace(base_run, sources=legacy_sources)
        snapshot = _snapshot(checkpoint=_agreement_checkpoint())
        audit = build_mission_audit(snapshot, run, None, hypatia_version="test")
        traceability = audit["traceability"]

        graph = traceability_graph_for(traceability)

        source_dicts = traceability["source_observations"]
        legacy = next(s for s in source_dicts if s["document_id"] == "document-2")
        self.assertIsNone(legacy["observation_id"])
        (node,) = [
            n for n in graph.source_observations if n.document_id == "document-2"
        ]
        self.assertEqual(node.node_id, "document-2")
        self.assertIsNone(node.observation_id)
        # Evidence-2's evidence_source edge must resolve to that same node_id.
        (edge,) = [
            e
            for e in graph.edges
            if e.relation == "evidence_source" and e.source.node_id == "evidence-2"
        ]
        self.assertEqual(edge.target.node_id, "document-2")

    def test_resolved_discovery_candidate_is_a_node_with_a_resolved_edge(self) -> None:
        expected = next(
            s
            for s in self.traceability["source_observations"]
            if s["document_id"] == "document-1"
        )
        candidate = expected["discovery_candidate"]
        self.assertIsNotNone(candidate)
        self.assertTrue(candidate["resolved"])
        (node,) = [
            n
            for n in self.graph.discovery_candidates
            if n.candidate_id == "candidate-1"
        ]
        self.assertEqual(node.discovery_id, candidate["discovery_id"])
        self.assertEqual(node.url, candidate["url"])
        self.assertEqual(node.title, candidate["title"])
        (edge,) = [
            e
            for e in self.graph.edges
            if e.relation == "source_discovery_candidate"
            and e.target.node_id == "candidate-1"
        ]
        self.assertTrue(edge.resolved)
        self.assertEqual(edge.source.kind, TraceabilityNodeKind.SOURCE_OBSERVATION)
        self.assertEqual(edge.source.node_id, "observation-1")
        # Source two never selected a discovery candidate: no edge for it.
        self.assertFalse(
            any(
                e.relation == "source_discovery_candidate"
                and e.source.node_id == "observation-2"
                for e in self.graph.edges
            )
        )

    def test_claims_are_reshaped_with_current_and_supersession_state(self) -> None:
        expected = {c["claim_id"]: c for c in self.traceability["claims"]}
        self.assertEqual({n.claim_id for n in self.graph.claims}, set(expected))
        for node in self.graph.claims:
            source = expected[node.claim_id]
            self.assertEqual(node.epistemic_state, source["epistemic_state"])
            self.assertEqual(node.current, source["current"])
            self.assertEqual(node.supersedes_claim_id, source["supersedes_claim_id"])
            self.assertEqual(
                node.source_document_ids, tuple(source["source_document_ids"])
            )
            self.assertEqual(
                node.unrecorded_evidence_ids,
                tuple(source["unrecorded_evidence_ids"]),
            )
        claim_one = expected["claim-1"]
        claim_two = expected["claim-2"]
        self.assertFalse(claim_one["current"])
        self.assertTrue(claim_two["current"])
        (edge,) = [
            e
            for e in self.graph.edges
            if e.relation == "claim_supersession" and e.source.node_id == "claim-2"
        ]
        self.assertTrue(edge.resolved)
        self.assertEqual(edge.target.node_id, "claim-1")

    def test_claim_evidence_edges_match_and_reach_a_resolved_source(self) -> None:
        for claim_id, evidence_id, document_id in (
            ("claim-1", "evidence-1", "document-1"),
            ("claim-2", "evidence-2", "document-2"),
        ):
            (evidence_edge,) = [
                e
                for e in self.graph.edges
                if e.relation == "claim_evidence"
                and e.source.node_id == claim_id
                and e.target.node_id == evidence_id
            ]
            self.assertTrue(evidence_edge.resolved)
            (node,) = [n for n in self.graph.evidence if n.evidence_id == evidence_id]
            self.assertTrue(node.source_resolved)
            (source_edge,) = [
                e
                for e in self.graph.edges
                if e.relation == "evidence_source" and e.source.node_id == evidence_id
            ]
            self.assertTrue(source_edge.resolved)
            source_node = next(
                s
                for s in self.graph.source_observations
                if s.document_id == document_id
            )
            self.assertEqual(source_edge.target.node_id, source_node.node_id)

    def test_evidence_shared_by_multiple_relations_is_a_single_node(self) -> None:
        # evidence-1 and evidence-2 are each cited by a claim, both reviews,
        # the contradiction and the mission comparison note: exactly one
        # EvidenceNode per evidence_id, many edges pointing at it.
        self.assertEqual(
            {n.evidence_id for n in self.graph.evidence},
            {
                "evidence-1",
                "evidence-2",
            },
        )
        for evidence_id in ("evidence-1", "evidence-2"):
            matching = [n for n in self.graph.evidence if n.evidence_id == evidence_id]
            self.assertEqual(len(matching), 1)
            edges_in = [
                e
                for e in self.graph.edges
                if e.target.node_id == evidence_id
                and e.target.kind == TraceabilityNodeKind.EVIDENCE
            ]
            self.assertGreaterEqual(len(edges_in), 3)

    def test_comparison_reviews_are_reshaped_with_supersession(self) -> None:
        expected = {r["review_id"]: r for r in self.traceability["comparison_reviews"]}
        self.assertEqual(
            {n.review_id for n in self.graph.comparison_reviews}, set(expected)
        )
        for node in self.graph.comparison_reviews:
            source = expected[node.review_id]
            self.assertEqual(node.note_id, source["note_id"])
            self.assertEqual(node.decision, source["decision"])
            self.assertEqual(node.current, source["current"])
            self.assertEqual(node.supersedes_review_id, source["supersedes_review_id"])
            self.assertEqual(
                node.source_document_ids, tuple(source["source_document_ids"])
            )
        (edge,) = [
            e
            for e in self.graph.edges
            if e.relation == "review_supersession" and e.source.node_id == "review-2"
        ]
        self.assertTrue(edge.resolved)
        self.assertEqual(edge.target.node_id, "review-1")
        for review_id in ("review-1", "review-2"):
            review_evidence_edges = [
                e
                for e in self.graph.edges
                if e.relation == "review_evidence" and e.source.node_id == review_id
            ]
            self.assertEqual(
                {e.target.node_id for e in review_evidence_edges},
                {"evidence-1", "evidence-2"},
            )
            self.assertTrue(all(e.resolved for e in review_evidence_edges))

    def test_contradiction_is_reshaped_with_claim_summaries_and_edges(self) -> None:
        (expected,) = self.traceability["claim_contradictions"]
        (node,) = self.graph.claim_contradictions
        self.assertEqual(node.contradiction_id, expected["contradiction_id"])
        self.assertEqual(node.recorded_at, expected["recorded_at"])
        self.assertEqual(
            [
                (s.claim_id, s.resolved, s.epistemic_state, s.current)
                for s in node.claims
            ],
            [
                (c["claim_id"], c["resolved"], c["epistemic_state"], c["current"])
                for c in expected["claims"]
            ],
        )
        claim_edges = [
            e
            for e in self.graph.edges
            if e.relation == "contradiction_claim"
            and e.source.node_id == "contradiction-1"
        ]
        self.assertEqual(
            {(e.target.node_id, e.resolved) for e in claim_edges},
            {("claim-1", True), ("claim-2", True)},
        )
        evidence_edges = [
            e
            for e in self.graph.edges
            if e.relation == "contradiction_evidence"
            and e.source.node_id == "contradiction-1"
        ]
        self.assertEqual(
            {e.target.node_id for e in evidence_edges}, {"evidence-1", "evidence-2"}
        )

    def test_goal_basis_notes_and_mission_ids_pass_through_raw(self) -> None:
        self.assertEqual(
            self.graph.mission_comparison_note_id,
            self.traceability["mission_comparison_note_id"],
        )
        self.assertEqual(
            self.graph.mission_comparison_review_id,
            self.traceability["mission_comparison_review_id"],
        )
        self.assertIsNotNone(self.graph.mission_comparison_note_id)
        basis = self.traceability["goal_basis"]
        self.assertEqual(
            self.graph.goal_basis.contradiction_outcome, basis["contradiction_outcome"]
        )
        self.assertEqual(
            self.graph.goal_basis.evidence_gap_outcome, basis["evidence_gap_outcome"]
        )
        self.assertEqual(
            self.graph.goal_basis.supporting_review_id, basis["supporting_review_id"]
        )
        self.assertEqual(
            len(self.graph.goal_basis.notes), len(basis["comparison_notes"])
        )
        for node, source in zip(
            self.graph.goal_basis.notes, basis["comparison_notes"], strict=True
        ):
            self.assertEqual(node.role, source["role"])
            self.assertEqual(node.note_id, source["note_id"])
            self.assertEqual(node.recorded_relation, source["recorded_relation"])
            self.assertEqual(node.resolved, source["resolved"])
            self.assertTrue(node.resolved)

    def test_revalidation_is_reshaped_with_both_endpoints_as_edges(self) -> None:
        (expected,) = self.traceability["source_revalidations"]
        (node,) = self.graph.source_revalidations
        self.assertEqual(node.revalidation_id, expected["revalidation_id"])
        self.assertEqual(node.outcome, expected["outcome"])
        self.assertEqual(node.recorded_at, expected["recorded_at"])
        for role, relation in (
            ("earlier", "revalidation_earlier_observation"),
            ("later", "revalidation_later_observation"),
        ):
            endpoint = expected[role]
            expected_node_id = f"{endpoint['run_id']}:{endpoint['observation_id']}"
            (edge,) = [
                e
                for e in self.graph.edges
                if e.relation == relation and e.source.node_id == "revalidation-1"
            ]
            self.assertTrue(edge.resolved)
            self.assertEqual(edge.target.node_id, expected_node_id)
            (obs_node,) = [
                n
                for n in self.graph.revalidation_observations
                if n.node_id == expected_node_id
            ]
            self.assertEqual(obs_node.run_id, endpoint["run_id"])
            self.assertEqual(obs_node.observation_id, endpoint["observation_id"])
            self.assertEqual(obs_node.document_id, endpoint["document_id"])
            self.assertEqual(obs_node.requested_url, endpoint["requested_url"])
            self.assertEqual(obs_node.url, endpoint["url"])
            self.assertEqual(obs_node.content_sha256, endpoint["content_sha256"])
            self.assertEqual(obs_node.fetched_at, endpoint["fetched_at"])
            self.assertEqual(obs_node.added_at, endpoint["added_at"])

    def test_graph_is_deterministic_for_the_same_audit_dict(self) -> None:
        second = traceability_graph_for(self.traceability)
        self.assertEqual(self.graph, second)


class TraceabilityGraphEmptyCaseTests(unittest.TestCase):
    def test_a_run_with_no_recorded_material_produces_an_empty_valid_graph(
        self,
    ) -> None:
        run = ResearchRun(
            run_id="run-empty",
            question="No sources selected",
            status=ResearchRunStatus.CANCELLED,
            sources=(),
            failures=(),
            created_at=STARTED,
            updated_at=STARTED,
        )
        snapshot = _snapshot(
            plan_id="plan-empty", research_run_id="run-empty", checkpoint=None
        )
        audit = build_mission_audit(snapshot, run, None, hypatia_version="test")
        traceability = audit["traceability"]

        graph = traceability_graph_for(traceability)

        self.assertIsNone(graph.mission_comparison_note_id)
        self.assertIsNone(graph.mission_comparison_review_id)
        self.assertEqual(graph.goal_basis.notes, ())
        self.assertIsNone(graph.goal_basis.contradiction_outcome)
        self.assertIsNone(graph.goal_basis.evidence_gap_outcome)
        self.assertIsNone(graph.goal_basis.supporting_review_id)
        self.assertEqual(graph.source_observations, ())
        self.assertEqual(graph.discovery_candidates, ())
        self.assertEqual(graph.evidence, ())
        self.assertEqual(graph.comparison_reviews, ())
        self.assertEqual(graph.claims, ())
        self.assertEqual(graph.claim_contradictions, ())
        self.assertEqual(graph.source_revalidations, ())
        self.assertEqual(graph.revalidation_observations, ())
        self.assertEqual(graph.edges, ())


class TraceabilityGraphUnresolvedReferenceTests(unittest.TestCase):
    """Unresolved references reported by real code must survive re-shaping."""

    def test_a_mission_note_id_that_does_not_resolve_stays_unresolved(self) -> None:
        run = _full_run()
        tampered_checkpoint = _agreement_checkpoint(
            semantic_note_id="note-that-does-not-exist",
            semantic_input_fingerprint="f" * 64,
        )
        snapshot = _snapshot(checkpoint=tampered_checkpoint)

        audit = build_mission_audit(snapshot, run, None, hypatia_version="test")
        traceability = audit["traceability"]
        graph = traceability_graph_for(traceability)

        (source_note,) = traceability["goal_basis"]["comparison_notes"]
        self.assertFalse(source_note["resolved"])
        self.assertEqual(source_note["evidence"], [])
        (node,) = graph.goal_basis.notes
        self.assertEqual(node.note_id, "note-that-does-not-exist")
        self.assertFalse(node.resolved)
        # An unresolved note cites no evidence: no goal_basis_evidence edges.
        self.assertFalse(
            any(
                e.relation == "goal_basis_evidence" and e.source.node_id == node.node_id
                for e in graph.edges
            )
        )

    def test_synthetic_unresolved_evidence_and_candidate_traces_are_not_dropped(
        self,
    ) -> None:
        """Exercise the two defensive branches a valid `ResearchRun` cannot reach.

        `ResearchRun.__post_init__` requires every claim/review/contradiction
        evidence ID to already exist in `run.evidence`, and every selected
        discovery candidate ID to already exist in `run.discoveries` -- so a
        validated run can never produce `_traceability()`'s unresolved-evidence
        or unresolved-candidate branches directly.  `_traceability()` still
        defends against them (`evidence_trace`'s `if record is None` branch;
        `candidate_trace`'s `if found is None` branch), for example for
        legacy-loaded documents.  This dict is built to match those two
        branches' exact, source-verified shape so the re-shaping is proven not
        to silently drop or guess at what they report.
        """
        traceability = {
            "mission_comparison_note_id": None,
            "mission_comparison_review_id": None,
            "goal_basis": {
                "comparison_notes": [],
                "contradiction_outcome": None,
                "evidence_gap_outcome": None,
                "supporting_review_id": None,
            },
            "source_observations": [
                {
                    "observation_id": "observation-1",
                    "document_id": "document-1",
                    "requested_url": "https://example.com/one",
                    "url": "https://example.com/one",
                    "content_sha256": "a" * 64,
                    "fetched_at": "2026-08-21T10:00:00+00:00",
                    "added_at": "2026-08-21T10:01:00+00:00",
                    # candidate_trace()'s own unresolved shape: no discovery_id/
                    # url/title keys at all.
                    "discovery_candidate": {
                        "candidate_id": "candidate-missing",
                        "resolved": False,
                    },
                }
            ],
            "source_revalidations": [],
            "comparison_reviews": [],
            "claims": [
                {
                    "claim_id": "claim-1",
                    "epistemic_state": "hypothesis",
                    "current": True,
                    "supersedes_claim_id": None,
                    "evidence_ids": ["evidence-missing"],
                    "source_document_ids": ["document-1"],
                    "unrecorded_evidence_ids": ["evidence-missing"],
                    # evidence_trace()'s own unresolved shape: only evidence_id
                    # and resolved, no chunk_id/chunk_sha256/source keys.
                    "evidence": [
                        {"evidence_id": "evidence-missing", "resolved": False}
                    ],
                }
            ],
            "claim_contradictions": [],
        }

        graph = traceability_graph_for(traceability)

        self.assertEqual(graph.evidence, ())
        (claim_edge,) = [e for e in graph.edges if e.relation == "claim_evidence"]
        self.assertEqual(claim_edge.source.node_id, "claim-1")
        self.assertEqual(claim_edge.target.node_id, "evidence-missing")
        self.assertEqual(claim_edge.target.kind, TraceabilityNodeKind.EVIDENCE)
        self.assertFalse(claim_edge.resolved)
        self.assertEqual(graph.discovery_candidates, ())
        (candidate_edge,) = [
            e for e in graph.edges if e.relation == "source_discovery_candidate"
        ]
        self.assertEqual(candidate_edge.target.node_id, "candidate-missing")
        self.assertFalse(candidate_edge.resolved)
        (claim_node,) = graph.claims
        self.assertEqual(claim_node.unrecorded_evidence_ids, ("evidence-missing",))

    def test_contradiction_claim_summary_reports_an_unresolved_claim_verbatim(
        self,
    ) -> None:
        """Exercise the one branch of `_traceability()`'s contradiction-claims
        list a valid `ResearchRun` cannot itself produce.

        Production only sets `resolved=False`/`epistemic_state=None` for a
        contradiction's claim entry when that claim ID is absent from
        `claims_by_id` (`ResearchMissionAudit.py` lines 848-869). A validated
        `ResearchRun` can never reach that path directly, because
        `ResearchRun.__post_init__` raises `ResearchError` if a contradiction
        cites a claim ID that is not also in `run.claims`
        (`ResearchRun.py:284-293`) -- for example for legacy-loaded runs.
        This dict copies that branch's exact, source-verified shape for one
        claim entry, alongside a normal resolved entry for another claim in
        the same contradiction, to prove the re-shaping keeps both cases
        distinct instead of dropping the unresolved one or defaulting it to
        the resolved one's values.
        """
        traceability = _minimal_valid_traceability_dict()
        traceability["claim_contradictions"] = [
            {
                "contradiction_id": "contradiction-1",
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "resolved": True,
                        "epistemic_state": "hypothesis",
                        "current": True,
                    },
                    {
                        "claim_id": "claim-missing",
                        "resolved": False,
                        "epistemic_state": None,
                        "current": True,
                    },
                ],
                "evidence_ids": [],
                "evidence": [],
                "recorded_at": "2026-08-21T10:10:00+00:00",
            }
        ]

        graph = traceability_graph_for(traceability)

        (node,) = graph.claim_contradictions
        resolved_summary, unresolved_summary = node.claims
        self.assertEqual(resolved_summary.claim_id, "claim-1")
        self.assertTrue(resolved_summary.resolved)
        self.assertEqual(resolved_summary.epistemic_state, "hypothesis")
        self.assertTrue(resolved_summary.current)
        self.assertEqual(unresolved_summary.claim_id, "claim-missing")
        self.assertFalse(unresolved_summary.resolved)
        self.assertIsNone(unresolved_summary.epistemic_state)
        self.assertTrue(unresolved_summary.current)
        claim_edges = [
            e
            for e in graph.edges
            if e.relation == "contradiction_claim"
            and e.source.node_id == "contradiction-1"
        ]
        self.assertEqual(
            {(e.target.node_id, e.resolved) for e in claim_edges},
            {("claim-1", True), ("claim-missing", False)},
        )

    def test_rejects_a_non_dict_input(self) -> None:
        with self.assertRaises(ResearchError):
            traceability_graph_for(["not", "a", "dict"])  # type: ignore[arg-type]


class TraceabilityGraphRequiredKeyTests(unittest.TestCase):
    """`_require` must raise, not silently omit, when a top-level key the
    graph depends on is absent from the input dict -- a documented
    fail-closed guarantee that stays untested unless proven per key.
    """

    def test_missing_source_observations_raises(self) -> None:
        traceability = _minimal_valid_traceability_dict()
        del traceability["source_observations"]
        with self.assertRaises(ResearchError):
            traceability_graph_for(traceability)

    def test_missing_goal_basis_raises(self) -> None:
        traceability = _minimal_valid_traceability_dict()
        del traceability["goal_basis"]
        with self.assertRaises(ResearchError):
            traceability_graph_for(traceability)

    def test_missing_comparison_reviews_raises(self) -> None:
        traceability = _minimal_valid_traceability_dict()
        del traceability["comparison_reviews"]
        with self.assertRaises(ResearchError):
            traceability_graph_for(traceability)

    def test_missing_claims_raises(self) -> None:
        traceability = _minimal_valid_traceability_dict()
        del traceability["claims"]
        with self.assertRaises(ResearchError):
            traceability_graph_for(traceability)

    def test_missing_claim_contradictions_raises(self) -> None:
        traceability = _minimal_valid_traceability_dict()
        del traceability["claim_contradictions"]
        with self.assertRaises(ResearchError):
            traceability_graph_for(traceability)

    def test_missing_source_revalidations_raises(self) -> None:
        traceability = _minimal_valid_traceability_dict()
        del traceability["source_revalidations"]
        with self.assertRaises(ResearchError):
            traceability_graph_for(traceability)


if __name__ == "__main__":
    unittest.main()
