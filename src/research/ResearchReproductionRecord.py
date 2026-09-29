"""One immutable, operator-authored record of manually following a recipe.

A reproduction record answers one question: what did the operator observe
when they manually carried out an already-recorded
`ResearchSecurityValidationRecipeRecord`'s steps? It is a low-stakes,
repeatable observation — recording one never fetches, runs, or authorizes
anything, never mutates the recipe, hypothesis, or finding it references,
and never transitions any finding's status. `research.ResearchReproduction`
derives which reproduction is "most recent" for a subject purely from
persisted append order, never from `recorded_at`, the same
no-timestamp-as-authority-ordering discipline every other append-only
record in this codebase already follows.

`subject_kind`/`subject_id` are always copied from the referenced recipe at
creation time by `cognition.ResearchReproductionApplicationService`, never
accepted as separate caller-supplied arguments that could diverge —
mirroring exactly how `ResearchSecurityFindingRecord` copies its subject
fields from its source hypothesis rather than accepting them independently.

This record does not itself verify that `recipe_id` names a real,
same-program recipe, or that `evidence_ids` name real, same-program,
same-subject evidence — those cross-store reference checks belong to
`cognition.ResearchReproductionApplicationService`, exactly mirroring how
`ResearchSecurityValidationRecipeRecord` only validates shape while its own
application service verifies the reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchReproductionOutcome import ResearchReproductionOutcome
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)
from research.ResearchSensitiveInputPolicy import ResearchSensitiveInputPolicy

MAX_REPRODUCTION_ID_CHARACTERS = 200
MAX_REPRODUCTION_PROGRAM_ID_CHARACTERS = 200
MAX_REPRODUCTION_RECIPE_ID_CHARACTERS = 200
MAX_REPRODUCTION_SUBJECT_ID_CHARACTERS = 200
MAX_REPRODUCTION_NOTES_CHARACTERS = 2_000
MAX_REPRODUCTION_EVIDENCE_IDS = 20
MAX_REPRODUCTION_EVIDENCE_ID_CHARACTERS = 200

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
class ResearchReproductionRecord:
    """One operator-authored reproduction attempt for one program's recipe."""

    reproduction_id: str
    program_id: str
    recipe_id: str
    subject_kind: ResearchSecurityValidationRecipeSubjectKind
    subject_id: str
    outcome: ResearchReproductionOutcome
    notes: str
    evidence_ids: tuple[str, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        reproduction_id = _bounded_identifier(
            self.reproduction_id,
            "Reproduction ID",
            MAX_REPRODUCTION_ID_CHARACTERS,
        )
        program_id = _bounded_identifier(
            self.program_id,
            "Reproduction program ID",
            MAX_REPRODUCTION_PROGRAM_ID_CHARACTERS,
        )
        recipe_id = _bounded_identifier(
            self.recipe_id,
            "Reproduction recipe ID",
            MAX_REPRODUCTION_RECIPE_ID_CHARACTERS,
        )
        if not isinstance(
            self.subject_kind, ResearchSecurityValidationRecipeSubjectKind
        ):
            raise ResearchError("Reproduction subject kind is invalid.")
        subject_id = _bounded_identifier(
            self.subject_id,
            "Reproduction subject ID",
            MAX_REPRODUCTION_SUBJECT_ID_CHARACTERS,
        )
        if not isinstance(self.outcome, ResearchReproductionOutcome):
            raise ResearchError("Reproduction outcome is invalid.")
        notes = _bounded_notes(
            self.notes, "Reproduction notes", MAX_REPRODUCTION_NOTES_CHARACTERS
        )
        if not isinstance(self.evidence_ids, tuple):
            raise ResearchError("Reproduction evidence IDs are invalid.")
        if len(self.evidence_ids) > MAX_REPRODUCTION_EVIDENCE_IDS:
            raise ResearchError("Reproduction cites too many evidence IDs.")
        evidence_ids = tuple(
            _bounded_identifier(
                evidence_id,
                "Reproduction evidence ID",
                MAX_REPRODUCTION_EVIDENCE_ID_CHARACTERS,
            )
            for evidence_id in self.evidence_ids
        )
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ResearchError("Reproduction cites a duplicate evidence ID.")
        if (
            not isinstance(self.recorded_at, datetime)
            or self.recorded_at.utcoffset() is None
        ):
            raise ResearchError("Reproduction recording time must be timezone-aware.")
        object.__setattr__(self, "reproduction_id", reproduction_id)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "recipe_id", recipe_id)
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "notes", notes)
        object.__setattr__(self, "evidence_ids", evidence_ids)
