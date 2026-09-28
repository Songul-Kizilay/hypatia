"""One immutable, operator-authored validation recipe for a hypothesis or finding.

A validation recipe is a durable fact about how an operator plans to (or
did) attempt to validate one already-recorded `ResearchSecurityHypothesis`
or `ResearchSecurityFinding` — an ordered list of short, plain-text steps
plus free-text notes. It is descriptive strategy text only, exactly like
`ResearchSecurityFindingRecord.required_followup`: recording a recipe never
itself fetches, runs, or authorizes anything, and no field here can name a
command, URL, or tool to invoke. `research.ResearchSecurityValidationRecipe`
derives which recipe is "current" for a subject (the most recently appended
one) purely from persisted append order, never from `created_at` — the same
no-timestamp-as-authority-ordering discipline every other append-only record
in this codebase already follows.

This record does not itself verify that `subject_id` names a real,
same-program hypothesis or finding — that cross-store reference check
belongs to `cognition.ResearchSecurityValidationRecipeApplicationService`,
exactly mirroring how `ResearchSecurityFindingStatusTransitionRecord` only
validates shape while `ResearchSecurityFindingApplicationService` verifies
the reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)
from research.ResearchSensitiveInputPolicy import ResearchSensitiveInputPolicy

MAX_SECURITY_VALIDATION_RECIPE_ID_CHARACTERS = 200
MAX_SECURITY_VALIDATION_RECIPE_PROGRAM_ID_CHARACTERS = 200
MAX_SECURITY_VALIDATION_RECIPE_SUBJECT_ID_CHARACTERS = 200
MAX_SECURITY_VALIDATION_RECIPE_STEP_CHARACTERS = 300
MAX_SECURITY_VALIDATION_RECIPE_STEPS = 20
MAX_SECURITY_VALIDATION_RECIPE_NOTES_CHARACTERS = 1_000

_SENSITIVE_INPUT_POLICY = ResearchSensitiveInputPolicy()


def _refuse_sensitive_input(value: str, label: str) -> None:
    sensitive_class = _SENSITIVE_INPUT_POLICY.classify(value)
    if sensitive_class.refused:
        raise ResearchError(f"{label} was refused as {sensitive_class.operator_label}.")


def _bounded_identifier(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ResearchError(f"{label} is invalid.")
    normalized = value.strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ResearchError(f"{label} must be single-line text.")
    return normalized


def _bounded_step(value: object, label: str, maximum: int) -> str:
    normalized = _bounded_identifier(value, label, maximum)
    _refuse_sensitive_input(normalized, label)
    return normalized


def _bounded_notes(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ResearchError(f"{label} is invalid.")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ResearchError(f"{label} is too long.")
    if normalized:
        _refuse_sensitive_input(normalized, label)
    return normalized


@dataclass(frozen=True, slots=True)
class ResearchSecurityValidationRecipeRecord:
    """One operator-authored validation recipe for one program's subject."""

    recipe_id: str
    program_id: str
    subject_kind: ResearchSecurityValidationRecipeSubjectKind
    subject_id: str
    steps: tuple[str, ...]
    notes: str
    created_at: datetime

    def __post_init__(self) -> None:
        recipe_id = _bounded_identifier(
            self.recipe_id,
            "Security validation recipe ID",
            MAX_SECURITY_VALIDATION_RECIPE_ID_CHARACTERS,
        )
        program_id = _bounded_identifier(
            self.program_id,
            "Security validation recipe program ID",
            MAX_SECURITY_VALIDATION_RECIPE_PROGRAM_ID_CHARACTERS,
        )
        if not isinstance(
            self.subject_kind, ResearchSecurityValidationRecipeSubjectKind
        ):
            raise ResearchError("Security validation recipe subject kind is invalid.")
        subject_id = _bounded_identifier(
            self.subject_id,
            "Security validation recipe subject ID",
            MAX_SECURITY_VALIDATION_RECIPE_SUBJECT_ID_CHARACTERS,
        )
        if not isinstance(self.steps, tuple) or not self.steps:
            raise ResearchError(
                "Security validation recipe requires at least one step."
            )
        if len(self.steps) > MAX_SECURITY_VALIDATION_RECIPE_STEPS:
            raise ResearchError("Security validation recipe has too many steps.")
        steps = tuple(
            _bounded_step(
                step,
                "Security validation recipe step",
                MAX_SECURITY_VALIDATION_RECIPE_STEP_CHARACTERS,
            )
            for step in self.steps
        )
        notes = _bounded_notes(
            self.notes,
            "Security validation recipe notes",
            MAX_SECURITY_VALIDATION_RECIPE_NOTES_CHARACTERS,
        )
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.utcoffset() is None
        ):
            raise ResearchError(
                "Security validation recipe creation time must be timezone-aware."
            )
        object.__setattr__(self, "recipe_id", recipe_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "notes", notes)
