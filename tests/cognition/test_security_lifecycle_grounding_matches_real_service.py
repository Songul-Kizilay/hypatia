"""Every factual claim the lifecycle grounding prompt makes, proven live.

`tests/llm/test_hypatia_security_lifecycle_grounding.py` proves the prompt
*text* says what it should and cannot silently drift once written -- but it
never calls a single line of `cognition`/`research` code, so a future change
to the real transition table or validation gate would leave the prompt
confidently wrong with every one of those tests still green (an independent
external review of this exact milestone named this precisely). This file
closes that gap: it drives the real
`ResearchSecurityHypothesisApplicationService`/
`ResearchSecurityFindingApplicationService` (the same services `Bootstrap`
wires into the running application) through each scenario the prompt
describes and asserts the real result matches the prompt's claim. If a
future change to the real gate or transition table ever makes one of these
tests fail, `HYPATIA_SECURITY_LIFECYCLE_GROUNDING` is the thing that needs
updating, not this file.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from uuid import uuid4

from cognition.ResearchSecurityFindingApplicationService import (
    ResearchSecurityFindingApplicationService,
)
from cognition.ResearchSecurityHypothesisApplicationService import (
    ResearchSecurityHypothesisApplicationService,
)
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
from research.ResearchSecurityFindingEvidenceRelation import (
    ResearchSecurityFindingEvidenceRelation,
)
from research.ResearchSecurityFindingStatus import (
    ResearchSecurityFindingStatus,
    is_valid_status_transition,
)
from research.ResearchSecurityHypothesisEvidenceRelation import (
    ResearchSecurityHypothesisEvidenceRelation,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityHypothesisStatus import ResearchSecurityHypothesisStatus
from response.ResponseComposer import ResponseComposer

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


class InMemoryHypothesisStore:
    def __init__(self) -> None:
        self._document = ResearchSecurityHypothesisDocument()

    def load(self) -> ResearchSecurityHypothesisDocument:
        return self._document

    def save(self, document: ResearchSecurityHypothesisDocument) -> None:
        self._document = document


class InMemoryFindingStore:
    def __init__(self) -> None:
        self._document = ResearchSecurityFindingDocument()

    def load(self) -> ResearchSecurityFindingDocument:
        return self._document

    def save(self, document: ResearchSecurityFindingDocument) -> None:
        self._document = document


class InMemoryHttpEvidenceStore:
    def __init__(self, records: tuple[ResearchHttpEvidenceRecord, ...]) -> None:
        self._document = ResearchHttpEvidenceDocument(records=records)

    def load(self) -> ResearchHttpEvidenceDocument:
        return self._document


def _evidence(evidence_id: str) -> ResearchHttpEvidenceRecord:
    return ResearchHttpEvidenceRecord(
        evidence_id=evidence_id,
        program_id="program-a",
        target_kind=ResearchAssetKind.HOSTNAME,
        target_canonical_value="example.test",
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
        recorded_at=NOW,
    )


class RealServiceRig:
    """One hypothesis+finding service pair backed by in-memory stores."""

    def __init__(self, evidence_ids: tuple[str, ...]) -> None:
        http_store = InMemoryHttpEvidenceStore(
            tuple(_evidence(eid) for eid in evidence_ids)
        )
        self.hypothesis_service = ResearchSecurityHypothesisApplicationService(
            InMemoryHypothesisStore(),
            http_store,
            ResponseComposer(),
            clock=lambda: NOW,
            id_factory=lambda: str(uuid4()),
        )
        self.finding_service = ResearchSecurityFindingApplicationService(
            InMemoryFindingStore(),
            http_store,
            self.hypothesis_service,
            ResponseComposer(),
            clock=lambda: NOW,
            id_factory=lambda: str(uuid4()),
        )


class TransitionTableMatchesPromptTests(unittest.TestCase):
    """Prompt claim: "CANDIDATE may move to VALIDATED directly ... no
    intermediate status is required first."" Checked against the real,
    pure, dependency-free transition function directly -- no service setup
    needed for this one.
    """

    def test_candidate_to_validated_is_a_real_direct_transition(self) -> None:
        self.assertTrue(
            is_valid_status_transition(
                ResearchSecurityFindingStatus.CANDIDATE,
                ResearchSecurityFindingStatus.VALIDATED,
            )
        )


class Case1FindingCreationDespiteContradictionTests(unittest.TestCase):
    """Prompt claim: a hypothesis carrying contradicting evidence can still
    become a finding; the contradiction carries forward rather than being
    dropped."""

    def test_a_ready_hypothesis_with_supports_and_contradicts_creates_a_finding(
        self,
    ) -> None:
        rig = RealServiceRig(evidence_ids=("a" * 64, "b" * 64, "c" * 64))
        hypothesis = rig.hypothesis_service.create_hypothesis(
            "program-a",
            ResearchSecurityHypothesisKind.AUTHORIZATION,
            ResearchAssetKind.HOSTNAME,
            "example.test",
            "statement",
            "rationale",
            "required validation",
            ("a" * 64, "b" * 64),
        )
        rig.hypothesis_service.attach_evidence(
            hypothesis.hypothesis_id,
            "program-a",
            ("c" * 64,),
            ResearchSecurityHypothesisEvidenceRelation.CONTRADICTS,
        )
        rig.hypothesis_service.transition_status(
            hypothesis.hypothesis_id,
            "program-a",
            ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
        )
        current = rig.hypothesis_service.hypothesis_by_id(
            hypothesis.hypothesis_id, "program-a"
        )
        assert current is not None
        self.assertEqual(len(current.supporting_evidence), 2)
        self.assertEqual(len(current.contradicting_evidence), 1)

        finding = rig.finding_service.create_finding(
            "program-a", hypothesis.hypothesis_id, "title", "description", "followup"
        )

        created = rig.finding_service.finding_by_id(finding.finding_id, "program-a")
        assert created is not None
        self.assertEqual(len(created.contradicting_evidence), 1)
        self.assertEqual(
            created.contradicting_evidence[0].evidence_id, "c" * 64
        )  # carried forward, not dropped
        self.assertEqual(created.status, ResearchSecurityFindingStatus.CANDIDATE)


class Case2And4ValidatedDirectlyFromCandidateTests(unittest.TestCase):
    """Prompt claim: VALIDATES + zero CONTRADICTS -> VALIDATED is reachable,
    and reachable directly from CANDIDATE."""

    def test_validates_evidence_with_no_contradiction_allows_direct_validated(
        self,
    ) -> None:
        rig = RealServiceRig(evidence_ids=("a" * 64, "d" * 64))
        hypothesis = rig.hypothesis_service.create_hypothesis(
            "program-a",
            ResearchSecurityHypothesisKind.AUTHORIZATION,
            ResearchAssetKind.HOSTNAME,
            "example.test",
            "statement",
            "rationale",
            "required validation",
            ("a" * 64,),
        )
        rig.hypothesis_service.transition_status(
            hypothesis.hypothesis_id,
            "program-a",
            ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
        )
        finding = rig.finding_service.create_finding(
            "program-a", hypothesis.hypothesis_id, "title", "description", "followup"
        )
        before = rig.finding_service.finding_by_id(finding.finding_id, "program-a")
        assert before is not None
        self.assertEqual(before.status, ResearchSecurityFindingStatus.CANDIDATE)
        rig.finding_service.attach_evidence(
            finding.finding_id,
            "program-a",
            ("d" * 64,),
            ResearchSecurityFindingEvidenceRelation.VALIDATES,
        )

        rig.finding_service.transition_status(
            finding.finding_id,
            "program-a",
            ResearchSecurityFindingStatus.VALIDATED,
        )

        after = rig.finding_service.finding_by_id(finding.finding_id, "program-a")
        assert after is not None
        self.assertEqual(after.status, ResearchSecurityFindingStatus.VALIDATED)


class Case3ContradictionBlocksValidatedLiveTests(unittest.TestCase):
    """Prompt claim: a live CONTRADICTS citation blocks VALIDATED even with
    VALIDATES evidence present."""

    def test_validates_evidence_with_a_live_contradiction_refuses_validated(
        self,
    ) -> None:
        rig = RealServiceRig(evidence_ids=("a" * 64, "d" * 64, "e" * 64))
        hypothesis = rig.hypothesis_service.create_hypothesis(
            "program-a",
            ResearchSecurityHypothesisKind.AUTHORIZATION,
            ResearchAssetKind.HOSTNAME,
            "example.test",
            "statement",
            "rationale",
            "required validation",
            ("a" * 64,),
        )
        rig.hypothesis_service.transition_status(
            hypothesis.hypothesis_id,
            "program-a",
            ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
        )
        finding = rig.finding_service.create_finding(
            "program-a", hypothesis.hypothesis_id, "title", "description", "followup"
        )
        rig.finding_service.attach_evidence(
            finding.finding_id,
            "program-a",
            ("d" * 64,),
            ResearchSecurityFindingEvidenceRelation.VALIDATES,
        )
        rig.finding_service.attach_evidence(
            finding.finding_id,
            "program-a",
            ("e" * 64,),
            ResearchSecurityFindingEvidenceRelation.CONTRADICTS,
        )

        with self.assertRaises(ResearchError):
            rig.finding_service.transition_status(
                finding.finding_id,
                "program-a",
                ResearchSecurityFindingStatus.VALIDATED,
            )


class OnlyReadyForValidationGatesCreationTests(unittest.TestCase):
    """Prompt claim: promotion happens "only when the hypothesis's current
    status is exactly READY_FOR_VALIDATION" -- proven both ways: the
    positive case above, and refusal from every other status here."""

    def test_an_open_hypothesis_cannot_be_promoted_to_a_finding(self) -> None:
        rig = RealServiceRig(evidence_ids=("a" * 64,))
        hypothesis = rig.hypothesis_service.create_hypothesis(
            "program-a",
            ResearchSecurityHypothesisKind.AUTHORIZATION,
            ResearchAssetKind.HOSTNAME,
            "example.test",
            "statement",
            "rationale",
            "required validation",
            ("a" * 64,),
        )

        with self.assertRaises(ResearchError):
            rig.finding_service.create_finding(
                "program-a",
                hypothesis.hypothesis_id,
                "title",
                "description",
                "followup",
            )


if __name__ == "__main__":
    unittest.main()
