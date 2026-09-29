"""Brain-facing boundary for operator-authored reproduction records.

This service performs no active validation, no fetch, no process, and no
model call: it only records an operator's own plain-text observation of
what happened when they manually followed an already-recorded
`ResearchSecurityValidationRecipeRecord`'s steps, and reads those
observations back. A reproduction is descriptive, low-stakes strategy text
— REPRODUCTION RECORD != EXECUTION AUTHORITY. It is never itself permission
to fetch, run, or authorize anything, and recording one never mutates the
recipe it references, the hypothesis/finding that recipe names, or that
finding's status. In particular, this service never calls
`ResearchSecurityFindingApplicationService.transition_status`: an
operator-recorded `REPRODUCED` outcome, however confident, is not itself a
validation-gate evidence citation and never moves a finding toward
`VALIDATED` — that remains governed exclusively by the finding's own
application service.

The recipe named by `recipe_id` must already exist for the exact
`program_id` given, verified via a narrow `SecurityValidationRecipeReader`
Protocol satisfied structurally by
`ResearchSecurityValidationRecipeApplicationService.recipe_by_id` (added
alongside this service, mirroring `SecurityHypothesisReader`/
`SecurityFindingReader`'s own established shape). `subject_kind`/
`subject_id` are copied from that recipe, never caller-supplied. Any cited
evidence ID must exist for the same program and must describe the exact
same subject as the underlying hypothesis/finding the recipe names —
looked up via the same `SecurityHypothesisReader`/`SecurityFindingReader`
Protocols `ResearchSecurityValidationRecipeApplicationService` already
uses, reusing the identical target/subject comparison
`ResearchSecurityFindingApplicationService.attach_evidence`'s F1 check
already proved.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.JsonFileResearchHttpEvidenceStore import ResearchHttpEvidenceDocument
from research.JsonFileResearchReproductionStore import ResearchReproductionDocument
from research.ResearchHttpEvidenceRecord import ResearchHttpEvidenceRecord
from research.ResearchReproduction import (
    current_reproduction_for_recipe as _derive_current_reproduction_for_recipe,
)
from research.ResearchReproduction import (
    reproductions_for_recipe as _derive_reproductions_for_recipe,
)
from research.ResearchReproduction import (
    reproductions_for_subject as _derive_reproductions_for_subject,
)
from research.ResearchReproductionOutcome import ResearchReproductionOutcome
from research.ResearchReproductionRecord import ResearchReproductionRecord
from research.ResearchSecurityFinding import ResearchSecurityFinding
from research.ResearchSecurityHypothesis import ResearchSecurityHypothesis
from research.ResearchSecurityValidationRecipeRecord import (
    ResearchSecurityValidationRecipeRecord,
)
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)
from response.ResponseComposer import ResponseComposer

RESEARCH_REPRODUCTION_RECORD_INTENT = "research_reproduction_record"
RESEARCH_REPRODUCTION_PREVIEW_INTENT = "research_reproduction_preview"

MAX_REPRODUCTION_PROGRAM_ID_CHARACTERS = 200


class ResearchReproductionStore(Protocol):
    def load(self) -> ResearchReproductionDocument: ...

    def save(self, document: ResearchReproductionDocument) -> None: ...


class SecurityValidationRecipeReader(Protocol):
    """The one recipe-side lookup this service needs, satisfied structurally.

    `ResearchSecurityValidationRecipeApplicationService.recipe_by_id`
    already exposes exactly this signature.
    """

    def recipe_by_id(
        self, recipe_id: str, program_id: str
    ) -> ResearchSecurityValidationRecipeRecord | None: ...


class SecurityHypothesisReader(Protocol):
    """Satisfied structurally by `ResearchSecurityHypothesisApplicationService`,
    the same Protocol shape `ResearchSecurityFindingApplicationService`/
    `ResearchSecurityValidationRecipeApplicationService` already use.
    """

    def hypothesis_by_id(
        self, hypothesis_id: str, program_id: str
    ) -> ResearchSecurityHypothesis | None: ...


class SecurityFindingReader(Protocol):
    """Satisfied structurally by `ResearchSecurityFindingApplicationService`."""

    def finding_by_id(
        self, finding_id: str, program_id: str
    ) -> ResearchSecurityFinding | None: ...


class ResearchHttpEvidenceReader(Protocol):
    def load(self) -> ResearchHttpEvidenceDocument: ...


class ResearchReproductionApplicationService:
    """Record and read operator-authored reproduction observations."""

    def __init__(
        self,
        store: ResearchReproductionStore,
        security_validation_recipe_reader: SecurityValidationRecipeReader,
        security_hypothesis_reader: SecurityHypothesisReader,
        security_finding_reader: SecurityFindingReader,
        http_evidence_reader: ResearchHttpEvidenceReader,
        response_composer: ResponseComposer,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._security_validation_recipe_reader = security_validation_recipe_reader
        self._security_hypothesis_reader = security_hypothesis_reader
        self._security_finding_reader = security_finding_reader
        self._http_evidence_reader = http_evidence_reader
        self._response_composer = response_composer
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))

    # -- durable writes ------------------------------------------------------

    def record_reproduction(
        self,
        program_id: str,
        recipe_id: str,
        outcome: ResearchReproductionOutcome,
        notes: str,
        evidence_ids: tuple[str, ...],
    ) -> ResearchReproductionRecord:
        """Append one new reproduction observation for an already-recorded recipe.

        Fails closed if `recipe_id` does not name a real recipe recorded
        for this exact `program_id`, or if any cited evidence ID does not
        exist for this program and describe the recipe's own subject.
        Never reads or mutates the recipe again afterward, never touches
        the referenced hypothesis's or finding's status: recording a
        reproduction is inert history, not a transition, and it is never
        interpreted as automatic validation of anything.
        """
        normalized_program_id = self._normalize_program_id(program_id)
        normalized_recipe_id = self._normalize_id(recipe_id, "Reproduction recipe ID")
        if not isinstance(outcome, ResearchReproductionOutcome):
            raise ResearchError("Reproduction outcome is invalid.")
        recipe = self._security_validation_recipe_reader.recipe_by_id(
            normalized_recipe_id, normalized_program_id
        )
        if recipe is None:
            raise ResearchError("Reproduction recipe was not found for this program.")
        self._require_evidence_matches_subject(
            normalized_program_id, recipe, evidence_ids
        )
        record = ResearchReproductionRecord(
            reproduction_id=self._new_id(),
            program_id=normalized_program_id,
            recipe_id=normalized_recipe_id,
            subject_kind=recipe.subject_kind,
            subject_id=recipe.subject_id,
            outcome=outcome,
            notes=notes,
            evidence_ids=evidence_ids,
            recorded_at=self._now(),
        )
        document = self._load()
        if any(
            existing.reproduction_id == record.reproduction_id
            for existing in document.reproductions
        ):
            raise ResearchError("Reproduction identity already exists.")
        self._save(
            ResearchReproductionDocument(
                reproductions=(*document.reproductions, record)
            )
        )
        return record

    # -- derived read models --------------------------------------------------

    def reproductions_for_recipe(
        self, program_id: str, recipe_id: str
    ) -> tuple[ResearchReproductionRecord, ...]:
        """Recompute one recipe's reproductions fresh from the persisted log."""
        normalized_program_id = self._normalize_program_id(program_id)
        normalized_recipe_id = self._normalize_id(recipe_id, "Reproduction recipe ID")
        document = self._load()
        return _derive_reproductions_for_recipe(
            normalized_program_id, normalized_recipe_id, document.reproductions
        )

    def current_reproduction_for_recipe(
        self, program_id: str, recipe_id: str
    ) -> ResearchReproductionRecord | None:
        """The most recently appended reproduction for one recipe, or `None`."""
        normalized_program_id = self._normalize_program_id(program_id)
        normalized_recipe_id = self._normalize_id(recipe_id, "Reproduction recipe ID")
        document = self._load()
        return _derive_current_reproduction_for_recipe(
            normalized_program_id, normalized_recipe_id, document.reproductions
        )

    def reproductions_for_subject(
        self,
        program_id: str,
        subject_kind: ResearchSecurityValidationRecipeSubjectKind,
        subject_id: str,
    ) -> tuple[ResearchReproductionRecord, ...]:
        """Every reproduction for one subject, across every recipe naming it."""
        normalized_program_id = self._normalize_program_id(program_id)
        if not isinstance(subject_kind, ResearchSecurityValidationRecipeSubjectKind):
            raise ResearchError("Reproduction subject kind is invalid.")
        normalized_subject_id = self._normalize_id(
            subject_id, "Reproduction subject ID"
        )
        document = self._load()
        return _derive_reproductions_for_subject(
            normalized_program_id,
            subject_kind,
            normalized_subject_id,
            document.reproductions,
        )

    # -- Brain intents ---------------------------------------------------------

    @staticmethod
    def is_reproduction_record_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_REPRODUCTION_RECORD_INTENT

    @staticmethod
    def is_reproduction_preview_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_REPRODUCTION_PREVIEW_INTENT

    def process_reproduction_record(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            recipe_id = request.metadata.get("recipe_id")
            outcome = request.metadata.get("outcome")
            notes = request.metadata.get("notes", "")
            evidence_ids = request.metadata.get("evidence_ids", ())
            if not isinstance(program_id, str):
                raise ResearchError("Reproduction requires a program ID.")
            if not isinstance(recipe_id, str):
                raise ResearchError("Reproduction requires a recipe ID.")
            if not isinstance(outcome, ResearchReproductionOutcome):
                raise ResearchError("Reproduction outcome is invalid.")
            if not isinstance(notes, str):
                raise ResearchError("Reproduction notes are invalid.")
            if not isinstance(evidence_ids, tuple) or any(
                not isinstance(evidence_id, str) for evidence_id in evidence_ids
            ):
                raise ResearchError(
                    "Reproduction evidence IDs must be a tuple of text."
                )
            record = self.record_reproduction(
                program_id, recipe_id, outcome, notes, evidence_ids
            )
        except ResearchError as error:
            composer = self._response_composer
            fail = composer.research_reproduction_record_failure
            return fail(request, str(error))
        return self._response_composer.research_reproduction_record(request, record)

    def process_reproduction_preview(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            recipe_id = request.metadata.get("recipe_id")
            if not isinstance(program_id, str):
                raise ResearchError("Reproduction preview requires a program ID.")
            if not isinstance(recipe_id, str):
                raise ResearchError("Reproduction preview requires a recipe ID.")
            reproductions = self.reproductions_for_recipe(program_id, recipe_id)
        except ResearchError as error:
            composer = self._response_composer
            fail = composer.research_reproduction_preview_failure
            return fail(request, str(error))
        return self._response_composer.research_reproduction_preview(
            request, reproductions
        )

    # -- internals ---------------------------------------------------------

    def _require_evidence_matches_subject(
        self,
        program_id: str,
        recipe: ResearchSecurityValidationRecipeRecord,
        evidence_ids: tuple[str, ...],
    ) -> None:
        if not evidence_ids:
            return
        if (
            recipe.subject_kind
            is ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS
        ):
            hypothesis = self._security_hypothesis_reader.hypothesis_by_id(
                recipe.subject_id, program_id
            )
            if hypothesis is None:
                raise ResearchError(
                    "Reproduction recipe's hypothesis was not found for this"
                    " program."
                )
            subject_kind = hypothesis.subject_kind
            subject_canonical_value = hypothesis.subject_canonical_value
        else:
            finding = self._security_finding_reader.finding_by_id(
                recipe.subject_id, program_id
            )
            if finding is None:
                raise ResearchError(
                    "Reproduction recipe's finding was not found for this" " program."
                )
            subject_kind = finding.subject_kind
            subject_canonical_value = finding.subject_canonical_value
        evidence_by_id = self._evidence_for_program(program_id)
        missing = tuple(
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in evidence_by_id
        )
        if missing:
            raise ResearchError(
                "Reproduction cites HTTP evidence that is not recorded for"
                " this program."
            )
        mismatched = tuple(
            evidence_id
            for evidence_id in evidence_ids
            if evidence_by_id[evidence_id].target_kind != subject_kind
            or evidence_by_id[evidence_id].target_canonical_value
            != subject_canonical_value
        )
        if mismatched:
            raise ResearchError(
                "Reproduction evidence does not match the recipe's own subject."
            )

    def _evidence_for_program(
        self, program_id: str
    ) -> dict[str, ResearchHttpEvidenceRecord]:
        document = self._load_http_evidence()
        return {
            value.evidence_id: value
            for value in document.records
            if value.program_id == program_id
        }

    def _load_http_evidence(self) -> ResearchHttpEvidenceDocument:
        try:
            return self._http_evidence_reader.load()
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to restore HTTP evidence.") from error

    def _load(self) -> ResearchReproductionDocument:
        try:
            return self._store.load()
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to restore the reproduction store.") from error

    def _save(self, document: ResearchReproductionDocument) -> None:
        try:
            self._store.save(document)
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to persist the reproduction store.") from error

    def _new_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Reproduction identifier cannot be empty.")
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError("Reproduction clock must be timezone-aware.")
        return value.astimezone(UTC)

    @staticmethod
    def _normalize_program_id(program_id: str) -> str:
        if (
            not isinstance(program_id, str)
            or not program_id.strip()
            or len(program_id.strip()) > MAX_REPRODUCTION_PROGRAM_ID_CHARACTERS
        ):
            raise ResearchError("Reproduction program ID is invalid.")
        return program_id.strip()

    @staticmethod
    def _normalize_id(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} is invalid.")
        return value.strip()
