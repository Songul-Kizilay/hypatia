"""Pure, dependency-free derived reads over persisted validation recipes.

Recipes are already immutable, flat facts (unlike hypotheses/findings, a
recipe carries no separate evidence-link/status-transition sublist to fold
in), so there is no projection to build — only two small, deterministic
filters over persisted append order. "Current" means the most recently
*appended* recipe for a subject, never the one with the latest `created_at`
— the same no-timestamp-as-authority-ordering discipline
`ResearchSecurityFinding`'s own status derivation already follows.
"""

from __future__ import annotations

from research.ResearchSecurityValidationRecipeRecord import (
    ResearchSecurityValidationRecipeRecord,
)
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)


def validation_recipes_for(
    program_id: str,
    subject_kind: ResearchSecurityValidationRecipeSubjectKind,
    subject_id: str,
    recipes: tuple[ResearchSecurityValidationRecipeRecord, ...],
) -> tuple[ResearchSecurityValidationRecipeRecord, ...]:
    """Every recipe recorded for one program's subject, in persisted append order."""
    return tuple(
        recipe
        for recipe in recipes
        if recipe.program_id == program_id
        and recipe.subject_kind is subject_kind
        and recipe.subject_id == subject_id
    )


def current_validation_recipe_for(
    program_id: str,
    subject_kind: ResearchSecurityValidationRecipeSubjectKind,
    subject_id: str,
    recipes: tuple[ResearchSecurityValidationRecipeRecord, ...],
) -> ResearchSecurityValidationRecipeRecord | None:
    """The most recently appended recipe for one program's subject, or `None`."""
    matching = validation_recipes_for(program_id, subject_kind, subject_id, recipes)
    return matching[-1] if matching else None
