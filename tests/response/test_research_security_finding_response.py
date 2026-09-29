"""v0.3.426: the contradiction-attention notice is surfaced, and only when
`ResearchSecurityFinding.needs_attention` is `True`. Current-state visibility
only -- see the `ResearchSecurityFinding` docstring's `needs_attention`
paragraph for what this deliberately does not claim.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from brain.BrainRequest import BrainRequest
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchSecurityFinding import ResearchSecurityFinding
from research.ResearchSecurityFindingEntry import ResearchSecurityFindingEntry
from research.ResearchSecurityFindingEvidenceKind import (
    ResearchSecurityFindingEvidenceKind,
)
from research.ResearchSecurityFindingEvidenceLinkRecord import (
    ResearchSecurityFindingEvidenceLinkRecord,
)
from research.ResearchSecurityFindingEvidenceRelation import (
    ResearchSecurityFindingEvidenceRelation,
)
from research.ResearchSecurityFindingOrigin import ResearchSecurityFindingOrigin
from research.ResearchSecurityFindingStatus import ResearchSecurityFindingStatus
from research.ResearchSecurityFindingStatusTransitionRecord import (
    ResearchSecurityFindingStatusTransitionRecord,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from response.ResponseComposer import (
    SECURITY_FINDING_CONTRADICTION_ATTENTION_NOTICE,
    SECURITY_FINDING_NOT_AUTHORITY_NOTICE,
    ResponseComposer,
)

RECORDED = datetime(2026, 9, 26, 10, tzinfo=UTC)


def _link(
    link_id: str,
    evidence_id: str,
    relation: ResearchSecurityFindingEvidenceRelation,
    finding_id: str = "finding-1",
    program_id: str = "program-a",
) -> ResearchSecurityFindingEvidenceLinkRecord:
    return ResearchSecurityFindingEvidenceLinkRecord(
        link_id=link_id,
        finding_id=finding_id,
        program_id=program_id,
        evidence_kind=ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE,
        evidence_id=evidence_id,
        relation=relation,
        recorded_at=RECORDED,
    )


def _finding(
    finding_id: str = "finding-1",
    program_id: str = "program-a",
    status: ResearchSecurityFindingStatus = ResearchSecurityFindingStatus.CANDIDATE,
    contradicting_evidence: tuple[ResearchSecurityFindingEvidenceLinkRecord, ...] = (),
    validation_evidence: tuple[ResearchSecurityFindingEvidenceLinkRecord, ...] = (),
) -> ResearchSecurityFinding:
    status_history: tuple[ResearchSecurityFindingStatusTransitionRecord, ...] = ()
    if status is not ResearchSecurityFindingStatus.CANDIDATE:
        status_history = (
            ResearchSecurityFindingStatusTransitionRecord(
                transition_id="transition-1",
                finding_id=finding_id,
                program_id=program_id,
                status=status,
                reason="",
                duplicate_of_finding_id=None,
                superseded_by_finding_id=None,
                recorded_at=RECORDED,
            ),
        )
    return ResearchSecurityFinding(
        finding_id=finding_id,
        program_id=program_id,
        source_hypothesis_id="hypothesis-1",
        finding_kind=ResearchSecurityHypothesisKind.AUTHORIZATION,
        subject_kind=ResearchAssetKind.HOSTNAME,
        subject_canonical_value=canonicalize_asset_value(
            ResearchAssetKind.HOSTNAME, "example.test"
        ),
        title="title",
        description="description",
        required_followup="required followup",
        origin=ResearchSecurityFindingOrigin.OPERATOR_AUTHORED,
        created_at=RECORDED,
        supporting_evidence=(),
        contradicting_evidence=contradicting_evidence,
        validation_evidence=validation_evidence,
        status=status,
        status_history=status_history,
    )


def _validated_with_contradiction(
    finding_id: str = "finding-1", program_id: str = "program-a"
) -> ResearchSecurityFinding:
    return _finding(
        finding_id=finding_id,
        program_id=program_id,
        status=ResearchSecurityFindingStatus.VALIDATED,
        contradicting_evidence=(
            _link(
                "c1",
                "b" * 64,
                ResearchSecurityFindingEvidenceRelation.CONTRADICTS,
                finding_id=finding_id,
                program_id=program_id,
            ),
        ),
        validation_evidence=(
            _link(
                "v1",
                "a" * 64,
                ResearchSecurityFindingEvidenceRelation.VALIDATES,
                finding_id=finding_id,
                program_id=program_id,
            ),
        ),
    )


def _entry(
    finding_value: ResearchSecurityFinding,
) -> ResearchSecurityFindingEntry:
    return ResearchSecurityFindingEntry(
        finding=finding_value,
        scope=ResearchAssetScopeResolutionView(
            has_active_scope_revision=False, resolution=None
        ),
    )


class SecurityFindingAttentionSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.composer = ResponseComposer()
        self.request = BrainRequest(message="x")

    def test_a_candidate_finding_carries_no_attention_notice(self) -> None:
        response = self.composer.research_security_finding_create(
            self.request, _finding()
        )
        self.assertNotIn(
            SECURITY_FINDING_CONTRADICTION_ATTENTION_NOTICE, response.message
        )

    def test_a_validated_finding_with_no_contradiction_carries_no_attention_notice(
        self,
    ) -> None:
        finding = _finding(
            status=ResearchSecurityFindingStatus.VALIDATED,
            validation_evidence=(
                _link(
                    "v1", "a" * 64, ResearchSecurityFindingEvidenceRelation.VALIDATES
                ),
            ),
        )
        self.assertFalse(finding.needs_attention)
        response = self.composer.research_security_finding_status_transition(
            self.request, finding
        )
        self.assertNotIn(
            SECURITY_FINDING_CONTRADICTION_ATTENTION_NOTICE, response.message
        )

    def test_a_validated_finding_with_contradiction_carries_the_attention_notice(
        self,
    ) -> None:
        finding = _validated_with_contradiction()
        self.assertTrue(finding.needs_attention)
        response = self.composer.research_security_finding_status_transition(
            self.request, finding
        )
        self.assertIn(SECURITY_FINDING_CONTRADICTION_ATTENTION_NOTICE, response.message)
        # Not-authority notice is preserved unchanged alongside it.
        self.assertIn(SECURITY_FINDING_NOT_AUTHORITY_NOTICE, response.message)
        self.assertNotIn("validation failed", response.message.lower())
        self.assertNotIn("invalidated", response.message.lower())
        self.assertNotIn("disproven", response.message.lower())
        self.assertNotIn("confirmed", response.message.lower())

    def test_evidence_attach_response_carries_the_attention_notice_too(self) -> None:
        """Same shared summary helper as status_transition -- one canonical
        surface, not two independently-maintained copies."""
        finding = _validated_with_contradiction()
        response = self.composer.research_security_finding_evidence_attach(
            self.request, finding
        )
        self.assertIn(SECURITY_FINDING_CONTRADICTION_ATTENTION_NOTICE, response.message)

    def test_preview_marks_only_the_finding_that_needs_attention(self) -> None:
        calm = _finding(finding_id="finding-1")
        needs_attention = _validated_with_contradiction(finding_id="finding-2")
        response = self.composer.research_security_finding_preview(
            self.request, (_entry(calm), _entry(needs_attention))
        )
        lines = [line for line in response.message.splitlines() if line.startswith("-")]
        (calm_line,) = [line for line in lines if "(candidate," in line]
        (attention_line,) = [line for line in lines if "(validated," in line]
        self.assertNotIn("NEEDS ATTENTION", calm_line)
        self.assertIn("NEEDS ATTENTION", attention_line)
        self.assertIn(SECURITY_FINDING_CONTRADICTION_ATTENTION_NOTICE, response.message)

    def test_preview_with_no_attention_needed_omits_the_notice(self) -> None:
        calm = _finding()
        response = self.composer.research_security_finding_preview(
            self.request, (_entry(calm),)
        )
        self.assertNotIn(
            SECURITY_FINDING_CONTRADICTION_ATTENTION_NOTICE, response.message
        )
        self.assertNotIn("NEEDS ATTENTION", response.message)


if __name__ == "__main__":
    unittest.main()
