"""Pure, dependency-free derived reads over persisted reproduction records.

Reproductions are already immutable, flat facts — no separate sublist to
fold in — so there is no projection to build, only deterministic filters
over persisted append order. "Most recent" means the most recently
*appended* reproduction for a subject, never the one with the latest
`recorded_at`, the same no-timestamp-as-authority-ordering discipline
`ResearchSecurityValidationRecipe`'s own derivation already follows.
"""

from __future__ import annotations

from research.ResearchReproductionRecord import ResearchReproductionRecord
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)


def reproductions_for_recipe(
    program_id: str,
    recipe_id: str,
    reproductions: tuple[ResearchReproductionRecord, ...],
) -> tuple[ResearchReproductionRecord, ...]:
    """Every reproduction recorded for one program's recipe, in append order."""
    return tuple(
        reproduction
        for reproduction in reproductions
        if reproduction.program_id == program_id and reproduction.recipe_id == recipe_id
    )


def reproductions_for_subject(
    program_id: str,
    subject_kind: ResearchSecurityValidationRecipeSubjectKind,
    subject_id: str,
    reproductions: tuple[ResearchReproductionRecord, ...],
) -> tuple[ResearchReproductionRecord, ...]:
    """Every reproduction for one program's subject, across every recipe
    that names it, in persisted append order.
    """
    return tuple(
        reproduction
        for reproduction in reproductions
        if reproduction.program_id == program_id
        and reproduction.subject_kind is subject_kind
        and reproduction.subject_id == subject_id
    )


def current_reproduction_for_recipe(
    program_id: str,
    recipe_id: str,
    reproductions: tuple[ResearchReproductionRecord, ...],
) -> ResearchReproductionRecord | None:
    """The most recently appended reproduction for one recipe, or `None`."""
    matching = reproductions_for_recipe(program_id, recipe_id, reproductions)
    return matching[-1] if matching else None
