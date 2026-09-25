"""An explicit operator comparison review is the only path to supported agreement.

Characterization (v0.3.367): the run already keeps operator-authored, revalidated
records (source assessments with supersession, claims with supersession, claim
contradictions), but none names one exact comparison note: assessments judge a
source, claims judge a statement and contradictions link two claims. The mission
checkpoint names its comparison note (``semantic_note_id``) and notes have stable
IDs, while model comparison candidates are transient. So a minimal run-level
``ResearchComparisonReviewRecord`` references the note and its exact evidence, is
written only through the run manager, and is revoked by supersession.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchAutonomyResult import AutonomyStopReason
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimRecord import ResearchClaimRecord
from research.ResearchComparisonReviewRecord import (
    ResearchComparisonReviewDecision as Decision,
)
from research.ResearchComparisonReviewRecord import (
    ResearchComparisonReviewRecord,
    current_comparison_review,
)
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchMissionGoalExplanation import (
    ResearchMissionGoalExplanationReason as Reason,
)
from research.ResearchMissionGoalExplanation import explain_mission_goal_satisfaction
from research.ResearchMissionGoalSatisfaction import (
    ResearchMissionGoalSatisfactionStatus as GoalStatus,
)
from research.ResearchMissionOutcome import mission_outcome_for
from research.ResearchMissionRecoveryCheckpoint import ResearchMissionRecoveryCheckpoint
from research.ResearchRun import ResearchRun
from research.ResearchRunManager import ResearchRunManager
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceComparisonNoteRecord import (
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourceRecord import ResearchSourceRecord
from research.ResearchTeachingReport import teaching_report

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(minutes=5)
STOP = AutonomyStopReason.RESEARCH_DELIVERABLE_READY


def review(
    review_id: str = "review-1",
    decision: Decision = Decision.SUPPORTED,
    *,
    note_id: str = "note-1",
    evidence_ids: tuple[str, ...] = ("evidence-1", "evidence-2"),
    supersedes: str | None = None,
    recorded_at: datetime = NOW,
) -> ResearchComparisonReviewRecord:
    return ResearchComparisonReviewRecord(
        review_id=review_id,
        note_id=note_id,
        evidence_ids=evidence_ids,
        decision=decision,
        note="Operator compared both excerpts against the question.",
        recorded_at=recorded_at,
        supersedes_review_id=supersedes,
    )


def run(
    *reviews: ResearchComparisonReviewRecord,
    note_text: str = "Mission semantic research note; Tentative relation: agreement.",
    trust: ResearchInformationTrust = ResearchInformationTrust.UNASSESSED,
    independence: ResearchSourceIndependence = ResearchSourceIndependence.UNKNOWN,
    claims: tuple[ResearchClaimRecord, ...] = (),
) -> ResearchRun:
    sources = tuple(
        ResearchSourceRecord(
            document_id=f"doc-{number}",
            url=f"https://example.test/{number}",
            title=f"Source {number}",
            content_type="text/plain",
            fetched_at=NOW,
            added_at=NOW,
        )
        for number in (1, 2)
    )
    evidence = tuple(
        ResearchEvidenceRecord(
            evidence_id=f"evidence-{number}",
            source_document_id=f"doc-{number}",
            chunk_id=f"chunk-{number}",
            chunk_index=0,
            excerpt=f"Recorded excerpt {number}.",
            excerpt_truncated=False,
            chunk_sha256=sha256(f"Recorded excerpt {number}.".encode()).hexdigest(),
            note="Grounded excerpt only.",
            recorded_at=NOW,
        )
        for number in (1, 2)
    )
    assessments = tuple(
        ResearchSourceAssessmentRecord(
            assessment_id=f"assessment-{number}",
            source_document_id=f"doc-{number}",
            evidence_ids=(f"evidence-{number}",),
            text="Exact-source grounding only.",
            recorded_at=NOW,
            information_trust=trust,
            independence=independence,
        )
        for number in (1, 2)
    )
    note = ResearchSourceComparisonNoteRecord(
        note_id="note-1",
        source_document_ids=("doc-1", "doc-2"),
        evidence_ids=("evidence-1", "evidence-2"),
        assessment_ids=("assessment-1", "assessment-2"),
        text=note_text,
        recorded_at=NOW,
    )
    return ResearchRun(
        run_id="run-1",
        question="What do the recorded sources support?",
        status=ResearchRunStatus.COLLECTING,
        sources=sources,
        failures=(),
        created_at=NOW,
        updated_at=LATER,
        evidence=evidence,
        assessments=assessments,
        comparison_notes=(note,),
        claims=claims,
        comparison_reviews=reviews,
    )


def checkpoint(**changes: object) -> ResearchMissionRecoveryCheckpoint:
    values: dict[str, object] = {
        "discovery_id": "discovery-1",
        "acquired_urls": ("https://example.test/1", "https://example.test/2"),
        "body_hashes": ("1" * 64, "2" * 64),
        "inspected_bytes": 600,
        "evidence_ids": ("evidence-1", "evidence-2"),
        "assessment_ids": ("assessment-1", "assessment-2"),
        "semantic_note_id": "note-1",
        "semantic_input_fingerprint": "a" * 64,
        "semantic_relation": "possible_agreement",
    }
    values.update(changes)
    return ResearchMissionRecoveryCheckpoint(**values)  # type: ignore[arg-type]


def conflict_checkpoint(**changes: object) -> ResearchMissionRecoveryCheckpoint:
    return checkpoint(
        semantic_relation="possible_conflict",
        contradiction_initial_note_id="note-1",
        contradiction_initial_evidence_ids=("evidence-1", "evidence-2"),
        contradiction_initial_source_document_ids=("doc-1", "doc-2"),
        contradiction_initial_assessment_ids=("assessment-1", "assessment-2"),
        contradiction_initial_input_fingerprint="a" * 64,
        contradiction_initial_relation="possible_conflict",
        **changes,
    )


class ComparisonReviewRecordTests(unittest.TestCase):
    def test_record_requires_exact_typed_fields(self):
        for changes in (
            {"note": " "},
            {"note_id": ""},
            {"evidence_ids": ()},
            {"decision": "supported"},
            {"supersedes_review_id": "review-1"},
            {"recorded_at": datetime(2026, 9, 16)},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ResearchError):
                    replace(review(), **changes)

    def test_run_binds_reviews_to_exact_notes_and_one_current_review(self):
        run(review())
        run(review(), review("review-2", Decision.NOT_SUPPORTED, supersedes="review-1"))
        for reviews in (
            (review(note_id="note-missing"),),
            (review(evidence_ids=("evidence-1",)),),
            (review(), review("review-2")),
            (review("review-2", supersedes="review-unknown"),),
            (
                review(recorded_at=LATER),
                review("review-2", supersedes="review-1", recorded_at=NOW),
            ),
        ):
            with self.subTest(reviews=[value.review_id for value in reviews]):
                with self.assertRaises(ResearchError):
                    run(*reviews)

    def test_store_round_trips_reviews_and_reads_older_documents_without_them(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.json"
            store = JsonFileResearchRunStore(path)
            subject = run(review())
            store.save([subject])
            document = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(document["schema_version"], 21)
            self.assertEqual(store.load(), [subject])
            document["schema_version"] = 13
            for value in document["runs"]:
                value.pop("comparison_reviews")
                for source in value["sources"]:
                    source.pop("content_sha256", None)
                    source.pop("requested_url", None)
                    source.pop("discovery_candidate_id", None)
                    source.pop("observation_id", None)
                    source.pop("revalidation_of_observation_id", None)
                    source.pop("revalidation_execution_id", None)
                for assessment in value["assessments"]:
                    assessment.pop("evidence_type", None)
            path.write_text(json.dumps(document), encoding="utf-8")

            self.assertEqual(store.load()[0].comparison_reviews, ())


class ComparisonReviewNoteSensitiveInputRefusalTests(unittest.TestCase):
    """`ResearchComparisonReviewRecord.note` refuses the same explicit
    secret-bearing forms `ResearchSessionContextRecord`/
    `ResearchAssetObservationRecord` already refuse, using the same fixed
    category-only message discipline: the raised error names only the
    refused category, never the candidate value.
    """

    SENTINEL = "distinct-secret-sentinel"

    def _cases(self) -> dict[str, str]:
        sentinel = self.SENTINEL
        return {
            "credential_bearing_url": f"https://user:{sentinel}@example.test",
            "authentication_header": f"Authorization: Bearer {sentinel}",
            "private_key_material": "-----BEGIN PRIVATE KEY-----",
            "secret_assignment": f"password={sentinel}",
            "token_format": "sk-abcdefghijklmnopqrstuvwxyz123456",
        }

    def test_note_refuses_every_explicit_category(self) -> None:
        for category, value in self._cases().items():
            with self.subTest(category=category):
                with self.assertRaises(ResearchError) as raised:
                    replace(review(), note=value)
                self.assertIn("refused as", str(raised.exception))
                self.assertNotIn(self.SENTINEL, str(raised.exception))

    def test_benign_near_miss_note_still_constructs(self) -> None:
        benign = "No password was used and no token was recorded."
        value = ResearchComparisonReviewRecord(
            review_id="review-1",
            note_id="note-1",
            evidence_ids=("evidence-1", "evidence-2"),
            decision=Decision.SUPPORTED,
            note=benign,
            recorded_at=NOW,
        )
        self.assertEqual(value.note, benign)

    def test_non_note_fields_are_unaffected_by_the_new_check(self) -> None:
        """Differential regression: non-note accept/refuse outcomes on
        non-default fixtures are byte-for-byte unchanged by adding note
        classification.
        """
        value = review(
            "review-9",
            Decision.NOT_SUPPORTED,
            note_id="note-9",
            evidence_ids=("evidence-9", "evidence-10", "evidence-11"),
        )
        self.assertEqual(value.review_id, "review-9")
        self.assertEqual(value.note_id, "note-9")
        self.assertEqual(
            value.evidence_ids, ("evidence-9", "evidence-10", "evidence-11")
        )
        self.assertIs(value.decision, Decision.NOT_SUPPORTED)
        with self.assertRaises(ResearchError):
            replace(review(), note_id="")
        with self.assertRaises(ResearchError):
            replace(review(), evidence_ids=())
        with self.assertRaises(ResearchError):
            replace(review(), decision="supported")  # type: ignore[arg-type]
        with self.assertRaisesRegex(ResearchError, "cannot supersede itself"):
            review("review-2", supersedes="review-2")


class ComparisonReviewManagerTests(unittest.TestCase):
    def manager(self) -> ResearchRunManager:
        manager = ResearchRunManager(clock=lambda: LATER)
        manager._runs = (replace(run(), updated_at=NOW),)
        return manager

    def test_review_is_bound_to_the_note_and_supersedes_exactly_the_current(self):
        manager = self.manager()

        first = manager.record_comparison_review(
            "run-1", "note-1", "supported", "Checked both excerpts."
        ).comparison_reviews[-1]

        self.assertEqual(first.evidence_ids, ("evidence-1", "evidence-2"))
        self.assertIs(first.decision, Decision.SUPPORTED)
        with self.assertRaises(ResearchError):
            manager.record_comparison_review(
                "run-1", "note-1", "not_supported", "Stale view without supersession."
            )
        for args in (
            ("run-1", "note-missing", "supported", "Unknown note."),
            ("run-1", "note-1", "verified", "Unknown decision."),
        ):
            with self.subTest(args=args):
                with self.assertRaises(ResearchError):
                    manager.record_comparison_review(*args, first.review_id)
        revoked = manager.record_comparison_review(
            "run-1", "note-1", "not_supported", "Withdrawn.", first.review_id
        )
        current = current_comparison_review(revoked.comparison_reviews, "note-1")
        assert current is not None
        self.assertIs(current.decision, Decision.NOT_SUPPORTED)
        self.assertEqual(current.supersedes_review_id, first.review_id)


class ComparisonReviewGoalTests(unittest.TestCase):
    def test_tentative_agreement_without_review_is_unresolved_and_not_ready(self):
        value = mission_outcome_for(run(), STOP, checkpoint())

        self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
        self.assertFalse(value.completion_readiness.ready)
        self.assertEqual(value.goal_satisfaction.supported_by_review_id, "")
        self.assertEqual(
            explain_mission_goal_satisfaction(value, STOP, checkpoint()).reasons,
            (Reason.TENTATIVE_AGREEMENT_UNSUPPORTED,),
        )

    def test_supported_review_satisfies_agreement_and_is_explained(self):
        subject = run(review())
        value = mission_outcome_for(subject, STOP, checkpoint())

        self.assertIs(value.goal_satisfaction.status, GoalStatus.SATISFIED)
        self.assertTrue(value.completion_readiness.ready)
        self.assertEqual(value.goal_satisfaction.supported_by_review_id, "review-1")
        explanation = explain_mission_goal_satisfaction(value, STOP, checkpoint())
        self.assertEqual(
            explanation.reasons,
            (Reason.SUPPORTED_CURRENT_EVIDENCE, Reason.AGREEMENT_SUPPORTED_BY_REVIEW),
        )
        self.assertIn("explicit operator comparison review", explanation.summary())
        report = teaching_report(subject, STOP.value, "Spend.", checkpoint=checkpoint())
        self.assertIn("Mission goal satisfaction: Satisfied", report)
        self.assertIn(
            "Comparison review: operator review review-1 marked note note-1 supported",
            report,
        )
        self.assertIn("citing evidence evidence-1, evidence-2", report)

    def test_withdrawn_or_negative_review_recomputes_unresolved(self):
        for label, subject in (
            ("not supported", run(review(decision=Decision.NOT_SUPPORTED))),
            (
                "withdrawn",
                run(
                    review(),
                    review("review-2", Decision.NOT_SUPPORTED, supersedes="review-1"),
                ),
            ),
        ):
            with self.subTest(case=label):
                value = mission_outcome_for(subject, STOP, checkpoint())
                self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
                self.assertFalse(value.completion_readiness.ready)

    def test_prose_trust_independence_and_claims_never_create_support(self):
        claim = ResearchClaimRecord(
            "claim-1",
            "Operator-recorded claim.",
            ResearchEpistemicState.FACT,
            ResearchClaimConfidence.HIGH,
            ("doc-1", "doc-2"),
            ("evidence-1", "evidence-2"),
            NOW,
        )
        for label, subject in (
            (
                "note text",
                run(note_text="Verified by operator review; comparison supported."),
            ),
            ("high trust", run(trust=ResearchInformationTrust.HIGH)),
            (
                "independent sources",
                run(independence=ResearchSourceIndependence.INDEPENDENT),
            ),
            ("high-confidence claim", run(claims=(claim,))),
        ):
            with self.subTest(case=label):
                value = mission_outcome_for(subject, STOP, checkpoint())
                self.assertIs(value.goal_satisfaction.status, GoalStatus.UNRESOLVED)
                self.assertFalse(value.completion_readiness.ready)

    def test_support_path_applies_only_to_the_recorded_agreement_note(self):
        cases = (
            ("conflict", conflict_checkpoint()),
            (
                "clarified conflict",
                conflict_checkpoint(
                    contradiction_followup_note_id="note-2",
                    contradiction_followup_evidence_id="evidence-3",
                    contradiction_followup_source_document_id="doc-3",
                    contradiction_followup_assessment_id="assessment-3",
                    contradiction_followup_input_fingerprint="b" * 64,
                    contradiction_followup_relation="possible_agreement",
                    contradiction_outcome="structurally_clarified",
                ),
            ),
            ("not comparable", checkpoint(semantic_relation="not_comparable")),
            (
                "no supported comparison",
                checkpoint(semantic_relation="no_supported_comparison"),
            ),
            (
                "relation unrecorded",
                checkpoint(
                    semantic_note_id="",
                    semantic_input_fingerprint="",
                    semantic_relation="",
                ),
            ),
            ("different note", checkpoint(semantic_note_id="note-other")),
        )
        for label, value in cases:
            with self.subTest(case=label):
                outcome = mission_outcome_for(run(review()), STOP, value)
                self.assertIs(outcome.goal_satisfaction.status, GoalStatus.UNRESOLVED)
                self.assertFalse(outcome.completion_readiness.ready)
                self.assertEqual(outcome.goal_satisfaction.supported_by_review_id, "")

    def test_evaluation_without_mission_checkpoint_keeps_evidence_only_rule(self):
        value = mission_outcome_for(run(), STOP, None)

        self.assertIs(value.goal_satisfaction.status, GoalStatus.SATISFIED)


if __name__ == "__main__":
    unittest.main()
