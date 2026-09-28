"""The Bug Bounty validation recipe service: subject-gated, never authority.

`record_validation_recipe` requires its subject (a hypothesis or a finding)
to already exist for the exact same program, verified through one of two
narrow reader Protocols satisfied structurally by the real
`ResearchSecurityHypothesisApplicationService`/`ResearchSecurityFindingApplicationService`.
Recording a recipe never mutates the subject and never grants authority to
fetch, run, or validate anything — it is inert, operator-authored strategy
text, exactly like `required_followup`.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from brain.BrainRequest import BrainRequest
from cognition.ResearchSecurityFindingApplicationService import (
    ResearchSecurityFindingApplicationService,
)
from cognition.ResearchSecurityHypothesisApplicationService import (
    ResearchSecurityHypothesisApplicationService,
)
from cognition.ResearchSecurityValidationRecipeApplicationService import (
    RESEARCH_SECURITY_VALIDATION_RECIPE_PREVIEW_INTENT,
    RESEARCH_SECURITY_VALIDATION_RECIPE_RECORD_INTENT,
    ResearchSecurityValidationRecipeApplicationService,
)
from core.Exceptions import ResearchError
from research.JsonFileResearchHttpEvidenceStore import ResearchHttpEvidenceDocument
from research.JsonFileResearchSecurityFindingStore import (
    ResearchSecurityFindingDocument,
)
from research.JsonFileResearchSecurityHypothesisStore import (
    ResearchSecurityHypothesisDocument,
)
from research.JsonFileResearchSecurityValidationRecipeStore import (
    JsonFileResearchSecurityValidationRecipeStore,
    ResearchSecurityValidationRecipeDocument,
)
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchHttpEvidenceProvenanceKind import (
    ResearchHttpEvidenceProvenanceKind,
)
from research.ResearchHttpEvidenceRecord import ResearchHttpEvidenceRecord
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityHypothesisRecord import ResearchSecurityHypothesisRecord
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
    store: InMemoryHypothesisStore | None = None,
    http_evidence_store: InMemoryHttpEvidenceStore | None = None,
) -> ResearchSecurityHypothesisApplicationService:
    return ResearchSecurityHypothesisApplicationService(
        store if store is not None else InMemoryHypothesisStore(),
        (
            http_evidence_store
            if http_evidence_store is not None
            else (InMemoryHttpEvidenceStore((http_evidence(),)))
        ),
        ResponseComposer(),
        clock=lambda: NOW,
        id_factory=lambda: str(uuid4()),
    )


def ready_hypothesis(
    hypothesis_service: ResearchSecurityHypothesisApplicationService,
    program_id: str = "program-a",
    subject_value: str = "example.test",
) -> ResearchSecurityHypothesisRecord:
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
    http_evidence_store: InMemoryHttpEvidenceStore | None = None,
    store: InMemoryFindingStore | None = None,
) -> ResearchSecurityFindingApplicationService:
    return ResearchSecurityFindingApplicationService(
        store if store is not None else InMemoryFindingStore(),
        (
            http_evidence_store
            if http_evidence_store is not None
            else (InMemoryHttpEvidenceStore((http_evidence(),)))
        ),
        hypothesis_service,
        ResponseComposer(),
        clock=lambda: NOW,
        id_factory=lambda: str(uuid4()),
    )


def make_recipe_service(
    hypothesis_service: ResearchSecurityHypothesisApplicationService,
    finding_service: ResearchSecurityFindingApplicationService,
    store: InMemoryRecipeStore | None = None,
) -> ResearchSecurityValidationRecipeApplicationService:
    return ResearchSecurityValidationRecipeApplicationService(
        store if store is not None else InMemoryRecipeStore(),
        hypothesis_service,
        finding_service,
        ResponseComposer(),
        clock=lambda: NOW,
        id_factory=lambda: str(uuid4()),
    )


class _Rig:
    """One fully wired hypothesis+finding+recipe chain for one test."""

    def __init__(self) -> None:
        self.http_evidence_store = InMemoryHttpEvidenceStore((http_evidence(),))
        self.hypothesis_service = make_hypothesis_service(
            http_evidence_store=self.http_evidence_store
        )
        self.hypothesis = ready_hypothesis(self.hypothesis_service)
        self.finding_service = make_finding_service(
            self.hypothesis_service, http_evidence_store=self.http_evidence_store
        )
        self.finding = self.finding_service.create_finding(
            "program-a",
            self.hypothesis.hypothesis_id,
            "title",
            "description",
            "required followup",
        )
        self.recipe_store = InMemoryRecipeStore()
        self.recipe_service = make_recipe_service(
            self.hypothesis_service, self.finding_service, store=self.recipe_store
        )


class RecordValidationRecipeTests(unittest.TestCase):
    def test_a_recipe_can_be_recorded_for_a_finding(self) -> None:
        rig = _Rig()

        recipe = rig.recipe_service.record_validation_recipe(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
            ("Replay the request with a different account.", "Observe the response."),
            "",
        )

        self.assertEqual(recipe.subject_id, rig.finding.finding_id)
        self.assertEqual(len(recipe.steps), 2)

    def test_a_recipe_can_be_recorded_for_a_hypothesis(self) -> None:
        rig = _Rig()

        recipe = rig.recipe_service.record_validation_recipe(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS,
            rig.hypothesis.hypothesis_id,
            ("Confirm the same host is reachable.",),
            "",
        )

        self.assertEqual(recipe.subject_id, rig.hypothesis.hypothesis_id)

    def test_an_unknown_finding_id_fails_closed(self) -> None:
        rig = _Rig()

        with self.assertRaisesRegex(ResearchError, "was not found for this program"):
            rig.recipe_service.record_validation_recipe(
                "program-a",
                ResearchSecurityValidationRecipeSubjectKind.FINDING,
                "no-such-finding",
                ("Step one",),
                "",
            )

    def test_an_unknown_hypothesis_id_fails_closed(self) -> None:
        rig = _Rig()

        with self.assertRaisesRegex(ResearchError, "was not found for this program"):
            rig.recipe_service.record_validation_recipe(
                "program-a",
                ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS,
                "no-such-hypothesis",
                ("Step one",),
                "",
            )

    def test_a_cross_program_finding_reference_fails_closed(self) -> None:
        rig = _Rig()

        with self.assertRaisesRegex(ResearchError, "was not found for this program"):
            rig.recipe_service.record_validation_recipe(
                "program-b",
                ResearchSecurityValidationRecipeSubjectKind.FINDING,
                rig.finding.finding_id,
                ("Step one",),
                "",
            )

    def test_an_invalid_subject_kind_fails_closed(self) -> None:
        rig = _Rig()

        with self.assertRaisesRegex(ResearchError, "subject kind is invalid"):
            rig.recipe_service.record_validation_recipe(
                "program-a",
                "finding",  # type: ignore[arg-type]
                rig.finding.finding_id,
                ("Step one",),
                "",
            )

    def test_an_invalid_program_id_fails_closed(self) -> None:
        rig = _Rig()

        with self.assertRaises(ResearchError):
            rig.recipe_service.record_validation_recipe(
                "",
                ResearchSecurityValidationRecipeSubjectKind.FINDING,
                rig.finding.finding_id,
                ("Step one",),
                "",
            )

    def test_recording_a_recipe_never_mutates_the_subject(self) -> None:
        rig = _Rig()
        before = rig.finding_service.finding_by_id(rig.finding.finding_id, "program-a")

        rig.recipe_service.record_validation_recipe(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
            ("Step one",),
            "",
        )

        after = rig.finding_service.finding_by_id(rig.finding.finding_id, "program-a")
        self.assertEqual(before, after)


class DerivedReadTests(unittest.TestCase):
    def test_recipes_for_an_unrecorded_subject_are_empty(self) -> None:
        rig = _Rig()

        self.assertEqual(
            rig.recipe_service.validation_recipes_for(
                "program-a",
                ResearchSecurityValidationRecipeSubjectKind.FINDING,
                rig.finding.finding_id,
            ),
            (),
        )
        self.assertIsNone(
            rig.recipe_service.current_validation_recipe_for(
                "program-a",
                ResearchSecurityValidationRecipeSubjectKind.FINDING,
                rig.finding.finding_id,
            )
        )

    def test_current_recipe_is_the_most_recently_appended_one(self) -> None:
        rig = _Rig()
        first = rig.recipe_service.record_validation_recipe(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
            ("First plan.",),
            "",
        )
        second = rig.recipe_service.record_validation_recipe(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
            ("Revised plan.",),
            "",
        )

        all_recipes = rig.recipe_service.validation_recipes_for(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
        )
        current = rig.recipe_service.current_validation_recipe_for(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
        )

        self.assertEqual(all_recipes, (first, second))
        self.assertEqual(current, second)

    def test_a_hypothesis_and_a_finding_recipe_never_collide(self) -> None:
        rig = _Rig()
        rig.recipe_service.record_validation_recipe(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS,
            rig.hypothesis.hypothesis_id,
            ("Hypothesis-side step.",),
            "",
        )

        finding_recipes = rig.recipe_service.validation_recipes_for(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
        )

        self.assertEqual(finding_recipes, ())


class ProgramIsolationTests(unittest.TestCase):
    def test_a_recipe_is_never_visible_under_a_different_program_id(self) -> None:
        rig = _Rig()
        recorded = rig.recipe_service.record_validation_recipe(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
            ("Step one.",),
            "",
        )

        # `subject_id` collides on purpose; only `program_id` differs.
        self.assertEqual(
            rig.recipe_service.validation_recipes_for(
                "program-b",
                ResearchSecurityValidationRecipeSubjectKind.FINDING,
                recorded.subject_id,
            ),
            (),
        )


class RestartReloadTests(unittest.TestCase):
    def test_a_recipe_survives_a_fresh_store_instance_over_the_same_file(self) -> None:
        rig = _Rig()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recipes.json"
            persistent_store = JsonFileResearchSecurityValidationRecipeStore(path)
            rig.recipe_service = make_recipe_service(
                rig.hypothesis_service, rig.finding_service, store=persistent_store
            )

            recorded = rig.recipe_service.record_validation_recipe(
                "program-a",
                ResearchSecurityValidationRecipeSubjectKind.FINDING,
                rig.finding.finding_id,
                ("Step one.",),
                "",
            )

            reloaded_service = make_recipe_service(
                rig.hypothesis_service,
                rig.finding_service,
                store=JsonFileResearchSecurityValidationRecipeStore(path),
            )
            current = reloaded_service.current_validation_recipe_for(
                "program-a",
                ResearchSecurityValidationRecipeSubjectKind.FINDING,
                rig.finding.finding_id,
            )

            self.assertEqual(current, recorded)


class BrainIntentTests(unittest.TestCase):
    def test_is_validation_recipe_record_request_matches_only_its_own_intent(
        self,
    ) -> None:
        service = ResearchSecurityValidationRecipeApplicationService
        self.assertTrue(
            service.is_validation_recipe_record_request(
                BrainRequest(
                    message="",
                    metadata={
                        "intent": RESEARCH_SECURITY_VALIDATION_RECIPE_RECORD_INTENT
                    },
                )
            )
        )
        self.assertFalse(
            service.is_validation_recipe_record_request(
                BrainRequest(message="", metadata={"intent": "something_else"})
            )
        )

    def test_is_validation_recipe_preview_request_matches_only_its_own_intent(
        self,
    ) -> None:
        service = ResearchSecurityValidationRecipeApplicationService
        self.assertTrue(
            service.is_validation_recipe_preview_request(
                BrainRequest(
                    message="",
                    metadata={
                        "intent": RESEARCH_SECURITY_VALIDATION_RECIPE_PREVIEW_INTENT
                    },
                )
            )
        )

    def test_process_validation_recipe_record_succeeds_end_to_end(self) -> None:
        rig = _Rig()

        response = rig.recipe_service.process_validation_recipe_record(
            BrainRequest(
                message="",
                metadata={
                    "intent": RESEARCH_SECURITY_VALIDATION_RECIPE_RECORD_INTENT,
                    "program_id": "program-a",
                    "subject_kind": ResearchSecurityValidationRecipeSubjectKind.FINDING,
                    "subject_id": rig.finding.finding_id,
                    "steps": ("Step one.",),
                    "notes": "",
                },
            )
        )

        self.assertTrue(response.success, response.message)
        self.assertIsNotNone(response.research_security_validation_recipe)

    def test_process_validation_recipe_record_fails_closed_on_bad_input(self) -> None:
        rig = _Rig()

        response = rig.recipe_service.process_validation_recipe_record(
            BrainRequest(
                message="",
                metadata={
                    "intent": RESEARCH_SECURITY_VALIDATION_RECIPE_RECORD_INTENT,
                    "program_id": "program-a",
                    "subject_kind": ResearchSecurityValidationRecipeSubjectKind.FINDING,
                    "subject_id": "no-such-finding",
                    "steps": ("Step one.",),
                    "notes": "",
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("rejected", response.message)

    def test_process_validation_recipe_preview_reports_recorded_recipes(self) -> None:
        rig = _Rig()
        rig.recipe_service.record_validation_recipe(
            "program-a",
            ResearchSecurityValidationRecipeSubjectKind.FINDING,
            rig.finding.finding_id,
            ("Step one.",),
            "",
        )

        response = rig.recipe_service.process_validation_recipe_preview(
            BrainRequest(
                message="",
                metadata={
                    "intent": RESEARCH_SECURITY_VALIDATION_RECIPE_PREVIEW_INTENT,
                    "program_id": "program-a",
                    "subject_kind": ResearchSecurityValidationRecipeSubjectKind.FINDING,
                    "subject_id": rig.finding.finding_id,
                },
            )
        )

        self.assertTrue(response.success, response.message)
        self.assertEqual(len(response.research_security_validation_recipes), 1)

    def test_process_validation_recipe_preview_fails_closed_on_missing_program_id(
        self,
    ) -> None:
        rig = _Rig()

        response = rig.recipe_service.process_validation_recipe_preview(
            BrainRequest(
                message="",
                metadata={
                    "intent": RESEARCH_SECURITY_VALIDATION_RECIPE_PREVIEW_INTENT,
                    "subject_kind": ResearchSecurityValidationRecipeSubjectKind.FINDING,
                    "subject_id": "finding-1",
                },
            )
        )

        self.assertFalse(response.success)


if __name__ == "__main__":
    unittest.main()
