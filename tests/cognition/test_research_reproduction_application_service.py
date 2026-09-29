"""The Bug Bounty reproduction service: recipe-gated, never authority.

`record_reproduction` requires `recipe_id` to already exist for the exact
same program, verified through `SecurityValidationRecipeReader` (satisfied
structurally by the real
`ResearchSecurityValidationRecipeApplicationService.recipe_by_id`).
`subject_kind`/`subject_id` are always copied from that recipe, never
caller-supplied. Any cited evidence ID must exist for the same program and
describe the exact same subject as the recipe's own hypothesis/finding.
Recording a reproduction never mutates the recipe, its subject, or that
subject's status -- REPRODUCTION RECORD != EXECUTION AUTHORITY, even when
the recorded outcome is REPRODUCED.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from brain.BrainRequest import BrainRequest
from cognition.ResearchReproductionApplicationService import (
    RESEARCH_REPRODUCTION_PREVIEW_INTENT,
    RESEARCH_REPRODUCTION_RECORD_INTENT,
    ResearchReproductionApplicationService,
)
from cognition.ResearchSecurityFindingApplicationService import (
    ResearchSecurityFindingApplicationService,
)
from cognition.ResearchSecurityHypothesisApplicationService import (
    ResearchSecurityHypothesisApplicationService,
)
from cognition.ResearchSecurityValidationRecipeApplicationService import (
    ResearchSecurityValidationRecipeApplicationService,
)
from core.Exceptions import ResearchError
from research.JsonFileResearchHttpEvidenceStore import ResearchHttpEvidenceDocument
from research.JsonFileResearchReproductionStore import (
    JsonFileResearchReproductionStore,
    ResearchReproductionDocument,
)
from research.JsonFileResearchSecurityFindingStore import (
    ResearchSecurityFindingDocument,
)
from research.JsonFileResearchSecurityHypothesisStore import (
    ResearchSecurityHypothesisDocument,
)
from research.JsonFileResearchSecurityValidationRecipeStore import (
    ResearchSecurityValidationRecipeDocument,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchHttpEvidenceProvenanceKind import (
    ResearchHttpEvidenceProvenanceKind,
)
from research.ResearchHttpEvidenceRecord import ResearchHttpEvidenceRecord
from research.ResearchReproductionOutcome import ResearchReproductionOutcome
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityHypothesisStatus import ResearchSecurityHypothesisStatus
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)
from response.ResponseComposer import ResponseComposer

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


class InMemoryHttpEvidenceStore:
    def __init__(self, records: tuple[ResearchHttpEvidenceRecord, ...] = ()) -> None:
        self._document = ResearchHttpEvidenceDocument(records=records)

    def load(self) -> ResearchHttpEvidenceDocument:
        return self._document


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


class InMemoryRecipeStore:
    def __init__(self) -> None:
        self._document = ResearchSecurityValidationRecipeDocument()

    def load(self) -> ResearchSecurityValidationRecipeDocument:
        return self._document

    def save(self, document: ResearchSecurityValidationRecipeDocument) -> None:
        self._document = document


class InMemoryReproductionStore:
    def __init__(self) -> None:
        self._document = ResearchReproductionDocument()

    def load(self) -> ResearchReproductionDocument:
        return self._document

    def save(self, document: ResearchReproductionDocument) -> None:
        self._document = document


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
        recorded_at=NOW,
    )


def make_hypothesis_service(
    http_evidence_store: InMemoryHttpEvidenceStore,
) -> ResearchSecurityHypothesisApplicationService:
    return ResearchSecurityHypothesisApplicationService(
        InMemoryHypothesisStore(),
        http_evidence_store,
        ResponseComposer(),
        clock=lambda: NOW,
        id_factory=lambda: str(uuid4()),
    )


def ready_hypothesis(
    hypothesis_service: ResearchSecurityHypothesisApplicationService,
    program_id: str = "program-a",
    subject_value: str = "example.test",
):
    record = hypothesis_service.create_hypothesis(
        program_id,
        ResearchSecurityHypothesisKind.AUTHORIZATION,
        ResearchAssetKind.HOSTNAME,
        subject_value,
        "The order endpoint may accept a client-controlled order ID.",
        "Observed HTTP evidence targets the same host.",
        "Request the same order ID as a different account.",
        ("a" * 64,),
    )
    hypothesis_service.transition_status(
        record.hypothesis_id,
        program_id,
        ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION,
    )
    return record


def make_finding_service(
    hypothesis_service: ResearchSecurityHypothesisApplicationService,
    http_evidence_store: InMemoryHttpEvidenceStore,
) -> ResearchSecurityFindingApplicationService:
    return ResearchSecurityFindingApplicationService(
        InMemoryFindingStore(),
        http_evidence_store,
        hypothesis_service,
        ResponseComposer(),
        clock=lambda: NOW,
        id_factory=lambda: str(uuid4()),
    )


def make_recipe_service(
    hypothesis_service: ResearchSecurityHypothesisApplicationService,
    finding_service: ResearchSecurityFindingApplicationService,
) -> ResearchSecurityValidationRecipeApplicationService:
    return ResearchSecurityValidationRecipeApplicationService(
        InMemoryRecipeStore(),
        hypothesis_service,
        finding_service,
        ResponseComposer(),
        clock=lambda: NOW,
        id_factory=lambda: str(uuid4()),
    )


def make_reproduction_service(
    recipe_service: ResearchSecurityValidationRecipeApplicationService,
    hypothesis_service: ResearchSecurityHypothesisApplicationService,
    finding_service: ResearchSecurityFindingApplicationService,
    http_evidence_store: InMemoryHttpEvidenceStore,
) -> ResearchReproductionApplicationService:
    return ResearchReproductionApplicationService(
        InMemoryReproductionStore(),
        recipe_service,
        hypothesis_service,
        finding_service,
        http_evidence_store,
        ResponseComposer(),
        clock=lambda: NOW,
        id_factory=lambda: str(uuid4()),
    )


class _Rig:
    """One fully wired hypothesis+finding+recipe+reproduction chain."""

    def __init__(self) -> None:
        self.http_evidence_store = InMemoryHttpEvidenceStore((http_evidence(),))
        self.hypothesis_service = make_hypothesis_service(self.http_evidence_store)
        self.hypothesis = ready_hypothesis(self.hypothesis_service)
        self.finding_service = make_finding_service(
            self.hypothesis_service, self.http_evidence_store
        )
        self.finding = self.finding_service.create_finding(
            "program-a",
            self.hypothesis.hypothesis_id,
            "title",
            "description",
            "required followup",
        )
        self.recipe_service = make_recipe_service(
            self.hypothesis_service, self.finding_service
        )
        self.recipe = self.recipe_service.record_validation_recipe(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            self.finding.finding_id,
            ("Replay the request with a different account.",),
            "",
        )
        self.reproduction_service = make_reproduction_service(
            self.recipe_service,
            self.hypothesis_service,
            self.finding_service,
            self.http_evidence_store,
        )


class RecordReproductionTests(unittest.TestCase):
    def test_a_reproduction_can_be_recorded_for_a_recipe(self) -> None:
        rig = _Rig()

        reproduction = rig.reproduction_service.record_reproduction(
            "program-a",
            rig.recipe.recipe_id,
            ResearchReproductionOutcome.REPRODUCED,
            "Observed the same order ID was accepted.",
            (),
        )

        self.assertEqual(reproduction.recipe_id, rig.recipe.recipe_id)
        self.assertIs(
            reproduction.subject_kind,
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
        )
        self.assertEqual(reproduction.subject_id, rig.finding.finding_id)

    def test_subject_fields_are_copied_from_the_recipe_not_caller_supplied(
        self,
    ) -> None:
        rig = _Rig()

        reproduction = rig.reproduction_service.record_reproduction(
            "program-a",
            rig.recipe.recipe_id,
            ResearchReproductionOutcome.NOT_RUN,
            "",
            (),
        )

        self.assertEqual(reproduction.subject_id, rig.finding.finding_id)

    def test_an_unknown_recipe_id_fails_closed(self) -> None:
        rig = _Rig()

        with self.assertRaisesRegex(ResearchError, "was not found for this program"):
            rig.reproduction_service.record_reproduction(
                "program-a",
                "no-such-recipe",
                ResearchReproductionOutcome.REPRODUCED,
                "",
                (),
            )

    def test_a_cross_program_recipe_reference_fails_closed(self) -> None:
        rig = _Rig()

        with self.assertRaisesRegex(ResearchError, "was not found for this program"):
            rig.reproduction_service.record_reproduction(
                "program-b",
                rig.recipe.recipe_id,
                ResearchReproductionOutcome.REPRODUCED,
                "",
                (),
            )

    def test_an_invalid_outcome_fails_closed(self) -> None:
        rig = _Rig()

        with self.assertRaisesRegex(ResearchError, "outcome is invalid"):
            rig.reproduction_service.record_reproduction(
                "program-a",
                rig.recipe.recipe_id,
                "reproduced",  # type: ignore[arg-type]
                "",
                (),
            )

    def test_matching_evidence_is_accepted(self) -> None:
        rig = _Rig()

        reproduction = rig.reproduction_service.record_reproduction(
            "program-a",
            rig.recipe.recipe_id,
            ResearchReproductionOutcome.REPRODUCED,
            "",
            ("a" * 64,),
        )

        self.assertEqual(reproduction.evidence_ids, ("a" * 64,))

    def test_an_unknown_evidence_id_fails_closed(self) -> None:
        rig = _Rig()

        with self.assertRaisesRegex(ResearchError, "not recorded for this program"):
            rig.reproduction_service.record_reproduction(
                "program-a",
                rig.recipe.recipe_id,
                ResearchReproductionOutcome.REPRODUCED,
                "",
                ("b" * 64,),
            )

    def test_evidence_naming_a_different_subject_fails_closed(self) -> None:
        rig = _Rig()
        rig.http_evidence_store = InMemoryHttpEvidenceStore(
            (
                http_evidence(),
                http_evidence(evidence_id="c" * 64, target_value="other.test"),
            )
        )
        rig.reproduction_service = make_reproduction_service(
            rig.recipe_service,
            rig.hypothesis_service,
            rig.finding_service,
            rig.http_evidence_store,
        )

        with self.assertRaisesRegex(ResearchError, "does not match the recipe's own"):
            rig.reproduction_service.record_reproduction(
                "program-a",
                rig.recipe.recipe_id,
                ResearchReproductionOutcome.REPRODUCED,
                "",
                ("c" * 64,),
            )

    def test_a_hypothesis_subject_recipe_also_gates_evidence_correctly(self) -> None:
        rig = _Rig()
        hypothesis_recipe = rig.recipe_service.record_validation_recipe(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS,
            rig.hypothesis.hypothesis_id,
            ("Confirm the same host is reachable.",),
            "",
        )

        reproduction = rig.reproduction_service.record_reproduction(
            "program-a",
            hypothesis_recipe.recipe_id,
            ResearchReproductionOutcome.NOT_REPRODUCED,
            "",
            ("a" * 64,),
        )

        self.assertIs(
            reproduction.subject_kind,
            ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS,
        )
        self.assertEqual(reproduction.subject_id, rig.hypothesis.hypothesis_id)

    def test_recording_a_reproduction_never_mutates_the_recipe(self) -> None:
        rig = _Rig()
        before = rig.recipe_service.current_validation_recipe_for(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
        )

        rig.reproduction_service.record_reproduction(
            "program-a",
            rig.recipe.recipe_id,
            ResearchReproductionOutcome.REPRODUCED,
            "",
            (),
        )

        after = rig.recipe_service.current_validation_recipe_for(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
        )
        self.assertEqual(before, after)

    def test_recording_a_reproduction_never_mutates_the_findings_status(self) -> None:
        rig = _Rig()
        before = rig.finding_service.finding_by_id(rig.finding.finding_id, "program-a")
        assert before is not None

        rig.reproduction_service.record_reproduction(
            "program-a",
            rig.recipe.recipe_id,
            ResearchReproductionOutcome.REPRODUCED,
            "",
            (),
        )

        after = rig.finding_service.finding_by_id(rig.finding.finding_id, "program-a")
        assert after is not None
        self.assertEqual(before.status, after.status)


class DerivedReadTests(unittest.TestCase):
    def test_reproductions_for_an_unrecorded_recipe_are_empty(self) -> None:
        rig = _Rig()

        self.assertEqual(
            rig.reproduction_service.reproductions_for_recipe(
                "program-a", rig.recipe.recipe_id
            ),
            (),
        )
        self.assertIsNone(
            rig.reproduction_service.current_reproduction_for_recipe(
                "program-a", rig.recipe.recipe_id
            )
        )

    def test_current_reproduction_is_the_most_recently_appended_one(self) -> None:
        rig = _Rig()
        first = rig.reproduction_service.record_reproduction(
            "program-a",
            rig.recipe.recipe_id,
            ResearchReproductionOutcome.NOT_REPRODUCED,
            "First attempt.",
            (),
        )
        second = rig.reproduction_service.record_reproduction(
            "program-a",
            rig.recipe.recipe_id,
            ResearchReproductionOutcome.REPRODUCED,
            "Second attempt.",
            (),
        )

        all_reproductions = rig.reproduction_service.reproductions_for_recipe(
            "program-a", rig.recipe.recipe_id
        )
        current = rig.reproduction_service.current_reproduction_for_recipe(
            "program-a", rig.recipe.recipe_id
        )

        self.assertEqual(all_reproductions, (first, second))
        self.assertEqual(current, second)

    def test_reproductions_for_subject_gathers_across_every_recipe(self) -> None:
        rig = _Rig()
        second_recipe = rig.recipe_service.record_validation_recipe(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
            ("Alternate steps.",),
            "",
        )
        first = rig.reproduction_service.record_reproduction(
            "program-a",
            rig.recipe.recipe_id,
            ResearchReproductionOutcome.NOT_REPRODUCED,
            "",
            (),
        )
        second = rig.reproduction_service.record_reproduction(
            "program-a",
            second_recipe.recipe_id,
            ResearchReproductionOutcome.REPRODUCED,
            "",
            (),
        )

        result = rig.reproduction_service.reproductions_for_subject(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
        )

        self.assertEqual(result, (first, second))


class ProgramIsolationTests(unittest.TestCase):
    def test_a_reproduction_is_never_visible_under_a_different_program_id(
        self,
    ) -> None:
        rig = _Rig()
        rig.reproduction_service.record_reproduction(
            "program-a",
            rig.recipe.recipe_id,
            ResearchReproductionOutcome.REPRODUCED,
            "",
            (),
        )

        self.assertEqual(
            rig.reproduction_service.reproductions_for_recipe(
                "program-b", rig.recipe.recipe_id
            ),
            (),
        )


class RestartReloadTests(unittest.TestCase):
    def test_a_reproduction_survives_a_fresh_store_instance_over_the_same_file(
        self,
    ) -> None:
        rig = _Rig()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reproductions.json"
            persistent_store = JsonFileResearchReproductionStore(path)
            rig.reproduction_service = ResearchReproductionApplicationService(
                persistent_store,
                rig.recipe_service,
                rig.hypothesis_service,
                rig.finding_service,
                rig.http_evidence_store,
                ResponseComposer(),
                clock=lambda: NOW,
                id_factory=lambda: str(uuid4()),
            )

            recorded = rig.reproduction_service.record_reproduction(
                "program-a",
                rig.recipe.recipe_id,
                ResearchReproductionOutcome.REPRODUCED,
                "",
                (),
            )

            reloaded_service = ResearchReproductionApplicationService(
                JsonFileResearchReproductionStore(path),
                rig.recipe_service,
                rig.hypothesis_service,
                rig.finding_service,
                rig.http_evidence_store,
                ResponseComposer(),
                clock=lambda: NOW,
                id_factory=lambda: str(uuid4()),
            )
            current = reloaded_service.current_reproduction_for_recipe(
                "program-a", rig.recipe.recipe_id
            )

            self.assertEqual(current, recorded)


class BrainIntentTests(unittest.TestCase):
    def test_is_reproduction_record_request_matches_only_its_own_intent(self) -> None:
        service = ResearchReproductionApplicationService
        self.assertTrue(
            service.is_reproduction_record_request(
                BrainRequest(
                    message="",
                    metadata={"intent": RESEARCH_REPRODUCTION_RECORD_INTENT},
                )
            )
        )
        self.assertFalse(
            service.is_reproduction_record_request(
                BrainRequest(message="", metadata={"intent": "something_else"})
            )
        )

    def test_is_reproduction_preview_request_matches_only_its_own_intent(
        self,
    ) -> None:
        service = ResearchReproductionApplicationService
        self.assertTrue(
            service.is_reproduction_preview_request(
                BrainRequest(
                    message="",
                    metadata={"intent": RESEARCH_REPRODUCTION_PREVIEW_INTENT},
                )
            )
        )

    def test_process_reproduction_record_succeeds_end_to_end(self) -> None:
        rig = _Rig()

        response = rig.reproduction_service.process_reproduction_record(
            BrainRequest(
                message="",
                metadata={
                    "intent": RESEARCH_REPRODUCTION_RECORD_INTENT,
                    "program_id": "program-a",
                    "recipe_id": rig.recipe.recipe_id,
                    "outcome": ResearchReproductionOutcome.REPRODUCED,
                    "notes": "",
                    "evidence_ids": (),
                },
            )
        )

        self.assertTrue(response.success, response.message)
        self.assertIsNotNone(response.research_reproduction)
        self.assertIn("does not grant authority to act", response.message)

    def test_process_reproduction_record_fails_closed_on_bad_recipe(self) -> None:
        rig = _Rig()

        response = rig.reproduction_service.process_reproduction_record(
            BrainRequest(
                message="",
                metadata={
                    "intent": RESEARCH_REPRODUCTION_RECORD_INTENT,
                    "program_id": "program-a",
                    "recipe_id": "no-such-recipe",
                    "outcome": ResearchReproductionOutcome.REPRODUCED,
                    "notes": "",
                    "evidence_ids": (),
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("rejected", response.message)

    def test_process_reproduction_preview_reports_recorded_reproductions(
        self,
    ) -> None:
        rig = _Rig()
        rig.reproduction_service.record_reproduction(
            "program-a",
            rig.recipe.recipe_id,
            ResearchReproductionOutcome.REPRODUCED,
            "",
            (),
        )

        response = rig.reproduction_service.process_reproduction_preview(
            BrainRequest(
                message="",
                metadata={
                    "intent": RESEARCH_REPRODUCTION_PREVIEW_INTENT,
                    "program_id": "program-a",
                    "recipe_id": rig.recipe.recipe_id,
                },
            )
        )

        self.assertTrue(response.success, response.message)
        self.assertEqual(len(response.research_reproductions), 1)

    def test_process_reproduction_preview_fails_closed_on_missing_program_id(
        self,
    ) -> None:
        rig = _Rig()

        response = rig.reproduction_service.process_reproduction_preview(
            BrainRequest(
                message="",
                metadata={
                    "intent": RESEARCH_REPRODUCTION_PREVIEW_INTENT,
                    "recipe_id": "recipe-1",
                },
            )
        )

        self.assertFalse(response.success)


if __name__ == "__main__":
    unittest.main()
