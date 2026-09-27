"""Read-only security finding listing rows — always recomputed, never stored.

Kept in `research/`, not alongside the application service that builds them,
mirroring `ResearchSecurityHypothesisEntry`'s own placement (so
`brain.BrainResponse` can reference this type without a cognition-layer
import cycle). Reuses `ResearchAssetScopeResolutionView` unchanged: a
finding's subject is a `(ResearchAssetKind, str)` pair exactly like a
hypothesis's, so a second, near-identical scope-view type would be pure
duplication.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchSecurityFinding import ResearchSecurityFinding


@dataclass(frozen=True, slots=True)
class ResearchSecurityFindingEntry:
    """One derived security finding paired with its live, never-stored scope."""

    finding: ResearchSecurityFinding
    scope: ResearchAssetScopeResolutionView

    def __post_init__(self) -> None:
        if not isinstance(self.finding, ResearchSecurityFinding):
            raise ResearchError("Security finding entry requires a valid finding.")
        if not isinstance(self.scope, ResearchAssetScopeResolutionView):
            raise ResearchError(
                "Security finding entry requires a valid scope resolution view."
            )
