"""Read-only security finding listing rows — always recomputed, never stored.

Kept in `research/`, not alongside the application service that builds them,
mirroring `ResearchSecurityHypothesisEntry`'s own placement (so
`brain.BrainResponse` can reference this type without a cognition-layer
import cycle). Reuses `ResearchAssetScopeResolutionView` unchanged: a
finding's subject is a `(ResearchAssetKind, str)` pair exactly like a
hypothesis's, so a second, near-identical scope-view type would be pure
duplication.

`reproductions` is the identical live-recomputed, never-stored discipline
`scope` already established, extended to one more already-existing store:
every `ResearchReproductionRecord` currently associated with this finding
through a recipe that currently names it (`subject_kind is FINDING`,
`subject_id == finding_id`), in persisted append order. It defaults to `()`
so every existing call site that builds an entry without reproduction data
keeps working unchanged; `with_reproductions` is the one seam a composing
caller uses to attach it after the fact, without re-deriving `finding`/
`scope`. Read-only visibility only: this field plays no part in `finding`'s
own `status`/`needs_attention` (both remain derived exclusively from
`ResearchSecurityFinding`'s own persisted facts) and this type never
persists what it carries.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchReproductionRecord import ResearchReproductionRecord
from research.ResearchSecurityFinding import ResearchSecurityFinding
from research.ResearchSecurityValidationRecipeSubjectKind import (
    ResearchSecurityValidationRecipeSubjectKind,
)


@dataclass(frozen=True, slots=True)
class ResearchSecurityFindingEntry:
    """One derived security finding paired with its live, never-stored scope
    and reproduction history."""

    finding: ResearchSecurityFinding
    scope: ResearchAssetScopeResolutionView
    reproductions: tuple[ResearchReproductionRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.finding, ResearchSecurityFinding):
            raise ResearchError("Security finding entry requires a valid finding.")
        if not isinstance(self.scope, ResearchAssetScopeResolutionView):
            raise ResearchError(
                "Security finding entry requires a valid scope resolution view."
            )
        if not isinstance(self.reproductions, tuple) or any(
            not isinstance(value, ResearchReproductionRecord)
            for value in self.reproductions
        ):
            raise ResearchError(
                "Security finding entry reproduction history is invalid."
            )
        identity = (self.finding.finding_id, self.finding.program_id)
        if any(
            reproduction.subject_kind
            is not ResearchSecurityValidationRecipeSubjectKind.FINDING
            or (reproduction.subject_id, reproduction.program_id) != identity
            for reproduction in self.reproductions
        ):
            raise ResearchError(
                "Security finding entry reproduction history does not belong"
                " to this finding."
            )

    def with_reproductions(
        self, reproductions: tuple[ResearchReproductionRecord, ...]
    ) -> ResearchSecurityFindingEntry:
        """Return a copy carrying the given reproduction history.

        Purely additive composition: `finding`/`scope` are untouched and
        re-validated unchanged; this never mutates `self` or anything it
        references.
        """
        return dataclasses.replace(self, reproductions=reproductions)
