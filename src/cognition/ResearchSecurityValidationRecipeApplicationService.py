"""Brain-facing boundary for operator-authored security validation recipes.

This service performs no active validation, no fetch, no process, and no
model call: it only records an operator's own plain-text description of how
they intend to (or did) validate an already-recorded `ResearchSecurityHypothesis`
or `ResearchSecurityFinding`, and reads those recipes back. A recipe is
descriptive strategy text, exactly like `ResearchSecurityFindingRecord.
required_followup` — it is never itself permission to fetch, run, or
authorize anything, and recording one changes no other record's status.

The subject (a hypothesis or a finding) must already exist for the exact
`program_id` given, verified via one of two narrow, structurally-satisfied
reader Protocols — `SecurityHypothesisReader`/`SecurityFindingReader` —
mirroring exactly how `ResearchSecurityFindingApplicationService` verifies
`source_hypothesis_id` through its own injected `SecurityHypothesisReader`:
no import cycle, no modification to either existing service.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.JsonFileResearchSecurityValidationRecipeStore import (
    ResearchSecurityValidationRecipeDocument,
)
from research.ResearchSecurityFinding import ResearchSecurityFinding
from research.ResearchSecurityHypothesis import ResearchSecurityHypothesis
from research.ResearchSecurityValidationRecipe import (
    current_validation_recipe_for as _derive_current_validation_recipe_for,
)
from research.ResearchSecurityValidationRecipe import (
    validation_recipes_for as _derive_validation_recipes_for,
)
from research.ResearchSecurityValidationRecipeRecord import (
    ResearchSecurityValidationRecipeRecord,
)
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)
from response.ResponseComposer import ResponseComposer

RESEARCH_SECURITY_VALIDATION_RECIPE_RECORD_INTENT = (
    "research_security_validation_recipe_record"
)
RESEARCH_SECURITY_VALIDATION_RECIPE_PREVIEW_INTENT = (
    "research_security_validation_recipe_preview"
)

MAX_SECURITY_VALIDATION_RECIPE_PROGRAM_ID_CHARACTERS = 200


class ResearchSecurityValidationRecipeStore(Protocol):
    def load(self) -> ResearchSecurityValidationRecipeDocument: ...

    def save(self, document: ResearchSecurityValidationRecipeDocument) -> None: ...


class SecurityHypothesisReader(Protocol):
    """The one hypothesis-side lookup this service needs, satisfied structurally.

    `ResearchSecurityHypothesisApplicationService` already exposes exactly
    this method signature, so it satisfies this Protocol with no import
    cycle and no modification to that file. Deliberately the same shape as
    `ResearchSecurityFindingApplicationService.SecurityHypothesisReader`.
    """

    def hypothesis_by_id(
        self, hypothesis_id: str, program_id: str
    ) -> ResearchSecurityHypothesis | None: ...


class SecurityFindingReader(Protocol):
    """The one finding-side lookup this service needs, satisfied structurally.

    `ResearchSecurityFindingApplicationService.finding_by_id` already exposes
    exactly this signature.
    """

    def finding_by_id(
        self, finding_id: str, program_id: str
    ) -> ResearchSecurityFinding | None: ...


class ResearchSecurityValidationRecipeApplicationService:
    """Record and read operator-authored security validation recipes."""

    def __init__(
        self,
        store: ResearchSecurityValidationRecipeStore,
        security_hypothesis_reader: SecurityHypothesisReader,
        security_finding_reader: SecurityFindingReader,
        response_composer: ResponseComposer,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._security_hypothesis_reader = security_hypothesis_reader
        self._security_finding_reader = security_finding_reader
        self._response_composer = response_composer
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))

    # -- durable writes ------------------------------------------------------

    def record_validation_recipe(
        self,
        program_id: str,
        subject_kind: ResearchSecurityValidationRecipeSubjectKind,
        subject_id: str,
        steps: tuple[str, ...],
        notes: str,
    ) -> ResearchSecurityValidationRecipeRecord:
        """Append one new validation recipe for an already-recorded subject.

        Fails closed if `subject_kind`/`subject_id` does not name a real
        hypothesis or finding recorded for this exact `program_id`. Never
        mutates or reads the subject again afterward, and never touches its
        status: recording a recipe is inert history, not a transition.
        """
        normalized_program_id = self._normalize_program_id(program_id)
        if not isinstance(subject_kind, ResearchSecurityValidationRecipeSubjectKind):
            raise ResearchError("Security validation recipe subject kind is invalid.")
        normalized_subject_id = self._normalize_id(
            subject_id, "Security validation recipe subject ID"
        )
        self._require_subject_exists(
            normalized_program_id, subject_kind, normalized_subject_id
        )
        record = ResearchSecurityValidationRecipeRecord(
            recipe_id=self._new_id(),
            program_id=normalized_program_id,
            subject_kind=subject_kind,
            subject_id=normalized_subject_id,
            steps=steps,
            notes=notes,
            created_at=self._now(),
        )
        document = self._load()
        if any(existing.recipe_id == record.recipe_id for existing in document.recipes):
            raise ResearchError("Security validation recipe identity already exists.")
        self._save(
            ResearchSecurityValidationRecipeDocument(
                recipes=(*document.recipes, record)
            )
        )
        return record

    # -- derived read models --------------------------------------------------

    def validation_recipes_for(
        self,
        program_id: str,
        subject_kind: ResearchSecurityValidationRecipeSubjectKind,
        subject_id: str,
    ) -> tuple[ResearchSecurityValidationRecipeRecord, ...]:
        """Recompute one subject's recipes fresh from the persisted log."""
        normalized_program_id = self._normalize_program_id(program_id)
        if not isinstance(subject_kind, ResearchSecurityValidationRecipeSubjectKind):
            raise ResearchError("Security validation recipe subject kind is invalid.")
        normalized_subject_id = self._normalize_id(
            subject_id, "Security validation recipe subject ID"
        )
        document = self._load()
        return _derive_validation_recipes_for(
            normalized_program_id,
            subject_kind,
            normalized_subject_id,
            document.recipes,
        )

    def current_validation_recipe_for(
        self,
        program_id: str,
        subject_kind: ResearchSecurityValidationRecipeSubjectKind,
        subject_id: str,
    ) -> ResearchSecurityValidationRecipeRecord | None:
        """The most recently appended recipe for one subject, or `None`."""
        normalized_program_id = self._normalize_program_id(program_id)
        if not isinstance(subject_kind, ResearchSecurityValidationRecipeSubjectKind):
            raise ResearchError("Security validation recipe subject kind is invalid.")
        normalized_subject_id = self._normalize_id(
            subject_id, "Security validation recipe subject ID"
        )
        document = self._load()
        return _derive_current_validation_recipe_for(
            normalized_program_id,
            subject_kind,
            normalized_subject_id,
            document.recipes,
        )

    # -- Brain intents ---------------------------------------------------------

    @staticmethod
    def is_validation_recipe_record_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent")
            == RESEARCH_SECURITY_VALIDATION_RECIPE_RECORD_INTENT
        )

    @staticmethod
    def is_validation_recipe_preview_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent")
            == RESEARCH_SECURITY_VALIDATION_RECIPE_PREVIEW_INTENT
        )

    def process_validation_recipe_record(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            subject_kind = request.metadata.get("subject_kind")
            subject_id = request.metadata.get("subject_id")
            steps = request.metadata.get("steps")
            notes = request.metadata.get("notes", "")
            if not isinstance(program_id, str):
                raise ResearchError("Security validation recipe requires a program ID.")
            if not isinstance(
                subject_kind, ResearchSecurityValidationRecipeSubjectKind
            ):
                raise ResearchError(
                    "Security validation recipe subject kind is invalid."
                )
            if not isinstance(subject_id, str):
                raise ResearchError("Security validation recipe requires a subject ID.")
            if not isinstance(steps, tuple) or any(
                not isinstance(step, str) for step in steps
            ):
                raise ResearchError(
                    "Security validation recipe steps must be a tuple of text."
                )
            if not isinstance(notes, str):
                raise ResearchError("Security validation recipe notes are invalid.")
            record = self.record_validation_recipe(
                program_id, subject_kind, subject_id, steps, notes
            )
        except ResearchError as error:
            composer = self._response_composer
            fail = composer.research_security_validation_recipe_record_failure
            return fail(request, str(error))
        return self._response_composer.research_security_validation_recipe_record(
            request, record
        )

    def process_validation_recipe_preview(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            subject_kind = request.metadata.get("subject_kind")
            subject_id = request.metadata.get("subject_id")
            if not isinstance(program_id, str):
                raise ResearchError(
                    "Security validation recipe preview requires a program ID."
                )
            if not isinstance(
                subject_kind, ResearchSecurityValidationRecipeSubjectKind
            ):
                raise ResearchError(
                    "Security validation recipe subject kind is invalid."
                )
            if not isinstance(subject_id, str):
                raise ResearchError(
                    "Security validation recipe preview requires a subject ID."
                )
            recipes = self.validation_recipes_for(program_id, subject_kind, subject_id)
        except ResearchError as error:
            composer = self._response_composer
            fail = composer.research_security_validation_recipe_preview_failure
            return fail(request, str(error))
        return self._response_composer.research_security_validation_recipe_preview(
            request, recipes
        )

    # -- internals ---------------------------------------------------------

    def _require_subject_exists(
        self,
        program_id: str,
        subject_kind: ResearchSecurityValidationRecipeSubjectKind,
        subject_id: str,
    ) -> None:
        if subject_kind is ResearchSecurityValidationRecipeSubjectKind.HYPOTHESIS:
            hypothesis = self._security_hypothesis_reader.hypothesis_by_id(
                subject_id, program_id
            )
            if hypothesis is None:
                raise ResearchError(
                    "Security validation recipe subject hypothesis was not"
                    " found for this program."
                )
            return
        finding = self._security_finding_reader.finding_by_id(subject_id, program_id)
        if finding is None:
            raise ResearchError(
                "Security validation recipe subject finding was not found for"
                " this program."
            )

    def _load(self) -> ResearchSecurityValidationRecipeDocument:
        try:
            return self._store.load()
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError(
                "Unable to restore the security validation recipe store."
            ) from error

    def _save(self, document: ResearchSecurityValidationRecipeDocument) -> None:
        try:
            self._store.save(document)
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError(
                "Unable to persist the security validation recipe store."
            ) from error

    def _new_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(
                "Security validation recipe identifier cannot be empty."
            )
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError(
                "Security validation recipe clock must be timezone-aware."
            )
        return value.astimezone(UTC)

    @staticmethod
    def _normalize_program_id(program_id: str) -> str:
        if (
            not isinstance(program_id, str)
            or not program_id.strip()
            or len(program_id.strip())
            > MAX_SECURITY_VALIDATION_RECIPE_PROGRAM_ID_CHARACTERS
        ):
            raise ResearchError("Security validation recipe program ID is invalid.")
        return program_id.strip()

    @staticmethod
    def _normalize_id(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{label} is invalid.")
        return value.strip()
