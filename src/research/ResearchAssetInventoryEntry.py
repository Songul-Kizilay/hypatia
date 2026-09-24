"""Read-only asset inventory listing rows — always recomputed, never stored.

Kept in `research/`, not alongside the application service that builds them,
so `brain.BrainResponse` can reference these types without a cognition-layer
import cycle (the service module itself needs `BrainResponse` for its own
return types).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchAsset import ResearchAsset
from research.ResearchTargetScopeResolution import ResearchTargetScopeResolution


@dataclass(frozen=True, slots=True)
class ResearchAssetScopeResolutionView:
    """One asset's current scope stance — always recomputed, never stored.

    `has_active_scope_revision` is `False` exactly when no active
    `ResearchProgramScopeRevision` exists for the asset's program right now;
    in that case `resolution` is `None` — an explicit "no active scope"
    signal, never a fabricated resolution. Otherwise `resolution` is always
    the live, freshly computed tri-state result.
    """

    has_active_scope_revision: bool
    resolution: ResearchTargetScopeResolution | None

    def __post_init__(self) -> None:
        if not isinstance(self.has_active_scope_revision, bool):
            raise ResearchError("Asset scope resolution view flag is invalid.")
        if self.has_active_scope_revision:
            if not isinstance(self.resolution, ResearchTargetScopeResolution):
                raise ResearchError(
                    "Asset scope resolution view requires a resolution."
                )
        elif self.resolution is not None:
            raise ResearchError(
                "Asset scope resolution view cannot cite a resolution without"
                " an active scope revision."
            )


@dataclass(frozen=True, slots=True)
class ResearchAssetInventoryEntry:
    """One derived asset paired with its live, never-stored scope reading."""

    asset: ResearchAsset
    scope: ResearchAssetScopeResolutionView

    def __post_init__(self) -> None:
        if not isinstance(self.asset, ResearchAsset):
            raise ResearchError("Asset inventory entry requires a valid asset.")
        if not isinstance(self.scope, ResearchAssetScopeResolutionView):
            raise ResearchError(
                "Asset inventory entry requires a valid scope resolution view."
            )
