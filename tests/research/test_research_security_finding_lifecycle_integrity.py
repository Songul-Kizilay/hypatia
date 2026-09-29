"""Adversarial tests for cross-store security finding lifecycle replay.

Every negative test constructs its three documents directly (bypassing both
application services entirely, the same technique every existing
dangling-reference test in this codebase already uses) to prove
`verify_finding_lifecycle_integrity` actually rejects a hand-tampered state
the live write path could never produce. Every positive test proves a
legitimately-producible history -- including the two edge cases this module's
own docstring says are deliberately NOT checked -- continues to pass.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from core.Exceptions import ResearchError
from research.JsonFileResearchHttpEvidenceStore import ResearchHttpEvidenceDocument
from research.JsonFileResearchSecurityFindingStore import (
    ResearchSecurityFindingDocument,
)
from research.JsonFileResearchSecurityHypothesisStore import (
    ResearchSecurityHypothesisDocument,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchHttpEvidenceProvenanceKind import (
    ResearchHttpEvidenceProvenanceKind,
)
from research.ResearchHttpEvidenceRecord import ResearchHttpEvidenceRecord
from research.ResearchSecurityFindingEvidenceKind import (
    ResearchSecurityFindingEvidenceKind,
)
from research.ResearchSecurityFindingEvidenceLinkRecord import (
    ResearchSecurityFindingEvidenceLinkRecord,
)
from research.ResearchSecurityFindingEvidenceRelation import (
    ResearchSecurityFindingEvidenceRelation,
)
from research.ResearchSecurityFindingLifecycleIntegrity import (
    verify_finding_lifecycle_integrity,
)
from research.ResearchSecurityFindingOrigin import ResearchSecurityFindingOrigin
from research.ResearchSecurityFindingRecord import ResearchSecurityFindingRecord
from research.ResearchSecurityFindingStatus import ResearchSecurityFindingStatus
from research.ResearchSecurityFindingStatusTransitionRecord import (
    ResearchSecurityFindingStatusTransitionRecord,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityHypothesisOrigin import ResearchSecurityHypothesisOrigin
from research.ResearchSecurityHypothesisRecord import ResearchSecurityHypothesisRecord

RECORDED = datetime(2026, 9, 29, 12, tzinfo=UTC)


def hypothesis_record(
    hypothesis_id: str = "hypothesis-1",
    program_id: str = "program-a",
    hypothesis_kind: ResearchSecurityHypothesisKind = (
        ResearchSecurityHypothesisKind.AUTHORIZATION
    ),
    subject_value: str = "example.test",
) -> ResearchSecurityHypothesisRecord:
    return ResearchSecurityHypothesisRecord(
        hypothesis_id=hypothesis_id,
        program_id=program_id,
        hypothesis_kind=hypothesis_kind,
        subject_kind=ResearchAssetKind.HOSTNAME,
        subject_canonical_value=subject_value,
        statement="statement",
        rationale="rationale",
        required_validation="required validation",
        origin=ResearchSecurityHypothesisOrigin.OPERATOR_AUTHORED,
        created_at=RECORDED,
    )


def finding_record(
    finding_id: str = "finding-1",
    program_id: str = "program-a",
    source_hypothesis_id: str = "hypothesis-1",
    finding_kind: ResearchSecurityHypothesisKind = (
        ResearchSecurityHypothesisKind.AUTHORIZATION
    ),
    subject_value: str = "example.test",
) -> ResearchSecurityFindingRecord:
    return ResearchSecurityFindingRecord(
        finding_id=finding_id,
        program_id=program_id,
        source_hypothesis_id=source_hypothesis_id,
        finding_kind=finding_kind,
        subject_kind=ResearchAssetKind.HOSTNAME,
        subject_canonical_value=subject_value,
        title="title",
        description="description",
        required_followup="required followup",
        origin=ResearchSecurityFindingOrigin.OPERATOR_AUTHORED,
        created_at=RECORDED,
    )


def evidence_link(
    link_id: str = "link-1",
    finding_id: str = "finding-1",
    program_id: str = "program-a",
    evidence_id: str = "a" * 64,
    relation: ResearchSecurityFindingEvidenceRelation = (
        ResearchSecurityFindingEvidenceRelation.SUPPORTS
    ),
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


def status_transition(
    transition_id: str = "transition-1",
    finding_id: str = "finding-1",
    program_id: str = "program-a",
    status: ResearchSecurityFindingStatus = ResearchSecurityFindingStatus.VALIDATED,
) -> ResearchSecurityFindingStatusTransitionRecord:
    return ResearchSecurityFindingStatusTransitionRecord(
        transition_id=transition_id,
        finding_id=finding_id,
        program_id=program_id,
        status=status,
        reason="",
        duplicate_of_finding_id=None,
        superseded_by_finding_id=None,
        recorded_at=RECORDED,
    )


def http_evidence(
    evidence_id: str = "a" * 64,
    program_id: str = "program-a",
    target_value: str = "example.test",
) -> ResearchHttpEvidenceRecord:
    return ResearchHttpEvidenceRecord(
        evidence_id=evidence_id,
        program_id=program_id,
        target_kind=ResearchAssetKind.HOSTNAME,
        target_canonical_value=target_value,
        scheme="https",
        port=443,
        path="/",
        request_method="HEAD",
        request_headers_observed=False,
        response_status_code=200,
        response_headers=(),
        response_body_observed=False,
        provenance=ResearchHttpEvidenceProvenanceKind.KALI_OPERATION_RESULT,
        source_operation_digest="f" * 64,
        recorded_at=RECORDED,
    )


class BaselineTests(unittest.TestCase):
    def test_empty_documents_are_trivially_consistent(self) -> None:
        verify_finding_lifecycle_integrity(
            ResearchSecurityFindingDocument(),
            ResearchSecurityHypothesisDocument(),
            ResearchHttpEvidenceDocument(),
        )

    def test_a_realistic_legitimate_history_passes(self) -> None:
        verify_finding_lifecycle_integrity(
            ResearchSecurityFindingDocument(
                findings=(finding_record(),),
                evidence_links=(
                    evidence_link(
                        relation=ResearchSecurityFindingEvidenceRelation.VALIDATES
                    ),
                ),
                status_transitions=(status_transition(),),
            ),
            ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
            ResearchHttpEvidenceDocument(records=(http_evidence(),)),
        )


class SourceHypothesisBindingTests(unittest.TestCase):
    def test_a_dangling_source_hypothesis_fails_closed(self) -> None:
        with self.assertRaisesRegex(ResearchError, "source hypothesis was not found"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(findings=(finding_record(),)),
                ResearchSecurityHypothesisDocument(),
                ResearchHttpEvidenceDocument(),
            )

    def test_a_cross_program_source_hypothesis_fails_closed(self) -> None:
        with self.assertRaisesRegex(ResearchError, "source hypothesis was not found"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(findings=(finding_record(),)),
                ResearchSecurityHypothesisDocument(
                    hypotheses=(hypothesis_record(program_id="program-b"),)
                ),
                ResearchHttpEvidenceDocument(),
            )

    def test_a_finding_kind_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(ResearchError, "kind does not match"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(
                        finding_record(
                            finding_kind=(ResearchSecurityHypothesisKind.INPUT_HANDLING)
                        ),
                    )
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(),
            )

    def test_a_subject_kind_or_value_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(ResearchError, "subject does not match"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(finding_record(subject_value="other.test"),)
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(),
            )


class EvidenceLinkBindingTests(unittest.TestCase):
    def test_a_dangling_evidence_reference_fails_closed(self) -> None:
        with self.assertRaisesRegex(ResearchError, "not recorded for its program"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(finding_record(),),
                    evidence_links=(evidence_link(),),
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(),
            )

    def test_a_cross_program_evidence_reference_fails_closed(self) -> None:
        with self.assertRaisesRegex(ResearchError, "not recorded for its program"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(finding_record(),),
                    evidence_links=(evidence_link(),),
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(
                    records=(http_evidence(program_id="program-b"),)
                ),
            )

    def test_an_evidence_subject_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(ResearchError, "does not match the finding"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(finding_record(),),
                    evidence_links=(evidence_link(),),
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(
                    records=(http_evidence(target_value="other.test"),)
                ),
            )

    def test_evidence_matching_a_different_findings_subject_still_fails_closed(
        self,
    ) -> None:
        """The cited evidence record is real, in the same program, and even
        matches *some* finding's subject in the document -- just not the
        subject of the finding whose link actually cites it. Proves the
        comparison binds each link to its own citing finding via
        `link.finding_id`, not to any finding sharing the program, which a
        single-finding fixture could never distinguish from a correct
        implementation.
        """
        with self.assertRaisesRegex(ResearchError, "does not match the finding"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(
                        finding_record(
                            finding_id="finding-1",
                            source_hypothesis_id="hypothesis-1",
                            subject_value="alpha.test",
                        ),
                        finding_record(
                            finding_id="finding-2",
                            source_hypothesis_id="hypothesis-2",
                            subject_value="beta.test",
                        ),
                    ),
                    evidence_links=(
                        evidence_link(
                            link_id="link-2",
                            finding_id="finding-2",
                            evidence_id="a" * 64,
                        ),
                    ),
                ),
                ResearchSecurityHypothesisDocument(
                    hypotheses=(
                        hypothesis_record(
                            hypothesis_id="hypothesis-1", subject_value="alpha.test"
                        ),
                        hypothesis_record(
                            hypothesis_id="hypothesis-2", subject_value="beta.test"
                        ),
                    )
                ),
                ResearchHttpEvidenceDocument(
                    records=(
                        http_evidence(evidence_id="a" * 64, target_value="alpha.test"),
                    )
                ),
            )


class OneFindingPerSourceHypothesisTests(unittest.TestCase):
    def test_two_findings_for_the_same_hypothesis_fail_closed(self) -> None:
        with self.assertRaisesRegex(
            ResearchError, "More than one security finding exists"
        ):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(
                        finding_record(finding_id="finding-1"),
                        finding_record(finding_id="finding-2"),
                    )
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(),
            )

    def test_duplicate_check_is_scoped_by_program(self) -> None:
        """Two different programs may each independently cite the same
        `source_hypothesis_id` string with no collision -- `program_id` is
        always part of the identity, matching every other check in this
        module.
        """
        verify_finding_lifecycle_integrity(
            ResearchSecurityFindingDocument(
                findings=(
                    finding_record(
                        finding_id="finding-1",
                        program_id="program-a",
                        source_hypothesis_id="hypothesis-a",
                    ),
                    finding_record(
                        finding_id="finding-2",
                        program_id="program-b",
                        source_hypothesis_id="hypothesis-b",
                    ),
                )
            ),
            ResearchSecurityHypothesisDocument(
                hypotheses=(
                    hypothesis_record(
                        hypothesis_id="hypothesis-a", program_id="program-a"
                    ),
                    hypothesis_record(
                        hypothesis_id="hypothesis-b", program_id="program-b"
                    ),
                )
            ),
            ResearchHttpEvidenceDocument(),
        )

    def test_a_finding_later_marked_duplicate_still_blocks_a_second_finding(
        self,
    ) -> None:
        """`create_finding`'s own dedup check refuses a second finding for a
        hypothesis regardless of the first finding's current status -- this
        replay check must not carve out an exception for `DUPLICATE`/
        `SUPERSEDED` either.
        """
        with self.assertRaisesRegex(
            ResearchError, "More than one security finding exists"
        ):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(
                        finding_record(finding_id="finding-1"),
                        finding_record(finding_id="finding-2"),
                    ),
                    status_transitions=(
                        ResearchSecurityFindingStatusTransitionRecord(
                            transition_id="transition-1",
                            finding_id="finding-1",
                            program_id="program-a",
                            status=ResearchSecurityFindingStatus.DUPLICATE,
                            reason="",
                            duplicate_of_finding_id="finding-2",
                            superseded_by_finding_id=None,
                            recorded_at=RECORDED,
                        ),
                    ),
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(),
            )


class ValidatedRequiresValidatesEvidenceTests(unittest.TestCase):
    def test_validated_with_zero_evidence_links_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ResearchError, "without ever recording validating evidence"
        ):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(finding_record(),),
                    status_transitions=(status_transition(),),
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(),
            )

    def test_validated_with_only_supports_evidence_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ResearchError, "without ever recording validating evidence"
        ):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(finding_record(),),
                    evidence_links=(
                        evidence_link(
                            relation=ResearchSecurityFindingEvidenceRelation.SUPPORTS
                        ),
                    ),
                    status_transitions=(status_transition(),),
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(records=(http_evidence(),)),
            )

    def test_validated_with_a_validates_link_passes(self) -> None:
        verify_finding_lifecycle_integrity(
            ResearchSecurityFindingDocument(
                findings=(finding_record(),),
                evidence_links=(
                    evidence_link(
                        relation=ResearchSecurityFindingEvidenceRelation.VALIDATES
                    ),
                ),
                status_transitions=(status_transition(),),
            ),
            ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
            ResearchHttpEvidenceDocument(records=(http_evidence(),)),
        )

    def test_a_contradicts_link_added_after_validated_is_not_rejected(self) -> None:
        """Deliberately NOT checked: `attach_evidence` has no gate of its
        own, so a legitimate history can attach `CONTRADICTS` evidence after
        an already-recorded `VALIDATED` transition. Rejecting this would
        reject a real, legitimately-producible history, not just a tampered
        one -- proving this module does not overreach into the unprovable
        half of the gate.
        """
        verify_finding_lifecycle_integrity(
            ResearchSecurityFindingDocument(
                findings=(finding_record(),),
                evidence_links=(
                    evidence_link(
                        link_id="link-1",
                        relation=ResearchSecurityFindingEvidenceRelation.VALIDATES,
                    ),
                    evidence_link(
                        link_id="link-2",
                        evidence_id="b" * 64,
                        relation=ResearchSecurityFindingEvidenceRelation.CONTRADICTS,
                    ),
                ),
                status_transitions=(status_transition(),),
            ),
            ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
            ResearchHttpEvidenceDocument(
                records=(http_evidence(), http_evidence(evidence_id="b" * 64))
            ),
        )

    def test_direct_candidate_to_validated_is_not_rejected(self) -> None:
        """The closed status-transition table already permits a direct
        `CANDIDATE` -> `VALIDATED` hop when its evidence gate is satisfied;
        this module must not reintroduce a "no skipped steps" rule.
        """
        verify_finding_lifecycle_integrity(
            ResearchSecurityFindingDocument(
                findings=(finding_record(),),
                evidence_links=(
                    evidence_link(
                        relation=ResearchSecurityFindingEvidenceRelation.VALIDATES
                    ),
                ),
                status_transitions=(
                    status_transition(status=ResearchSecurityFindingStatus.VALIDATED),
                ),
            ),
            ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
            ResearchHttpEvidenceDocument(records=(http_evidence(),)),
        )


class MutationTests(unittest.TestCase):
    """Prove each check is load-bearing: with it monkeypatched to a no-op,
    the exact document its own test constructs must stop raising.
    """

    _MODULE = "research.ResearchSecurityFindingLifecycleIntegrity"

    def test_removing_the_hypothesis_binding_check_lets_a_dangling_reference_through(
        self,
    ) -> None:
        with patch(f"{self._MODULE}._verify_source_hypothesis_binding"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(findings=(finding_record(),)),
                ResearchSecurityHypothesisDocument(),
                ResearchHttpEvidenceDocument(),
            )

    def test_removing_the_evidence_link_binding_check_lets_a_dangling_reference_through(
        self,
    ) -> None:
        with patch(f"{self._MODULE}._verify_evidence_link_binding"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(finding_record(),),
                    evidence_links=(evidence_link(),),
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(),
            )

    def test_removing_the_dedup_check_lets_two_findings_for_one_hypothesis_through(
        self,
    ) -> None:
        with patch(f"{self._MODULE}._verify_one_finding_per_source_hypothesis"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(
                        finding_record(finding_id="finding-1"),
                        finding_record(finding_id="finding-2"),
                    )
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(),
            )

    def test_removing_the_validated_gate_replay_lets_zero_evidence_through(
        self,
    ) -> None:
        with patch(f"{self._MODULE}._verify_validated_requires_validates_evidence"):
            verify_finding_lifecycle_integrity(
                ResearchSecurityFindingDocument(
                    findings=(finding_record(),),
                    status_transitions=(status_transition(),),
                ),
                ResearchSecurityHypothesisDocument(hypotheses=(hypothesis_record(),)),
                ResearchHttpEvidenceDocument(),
            )


if __name__ == "__main__":
    unittest.main()
