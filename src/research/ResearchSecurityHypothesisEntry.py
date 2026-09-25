"""Read-only security hypothesis listing rows — always recomputed, never stored.

Kept in `research/`, not alongside the application service that builds them,
mirroring `ResearchAssetInventoryEntry`'s own placement (so
`brain.BrainResponse` can reference this type without a cognition-layer
import cycle). Reuses `ResearchAssetScopeResolutionView` unchanged: a
hypothesis's subject is a `(ResearchAssetKind, str)` pair exactly like an
asset's identity, so a second, near-identical scope-view type would be pure
duplication.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchSecurityHypothesis import ResearchSecurityHypothesis


@dataclass(frozen=True, slots=True)
class ResearchSecurityHypothesisEntry:
    """One derived security hypothesis paired with its live, never-stored scope."""

    hypothesis: ResearchSecurityHypothesis
    scope: ResearchAssetScopeResolutionView

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis, ResearchSecurityHypothesis):
            raise ResearchError(
                "Security hypothesis entry requires a valid hypothesis."
            )
        if not isinstance(self.scope, ResearchAssetScopeResolutionView):
            raise ResearchError(
                "Security hypothesis entry requires a valid scope resolution view."
            )
