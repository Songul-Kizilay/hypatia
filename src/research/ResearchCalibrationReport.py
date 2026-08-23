"""Every active claim in one run, compared against its own support.

The report is derived, never stored. Anything it says can be recomputed from
canonical state at any moment, so persisting it would only create a second copy
that could drift from the first and then be believed.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.CalibrationVerdict import CalibrationVerdict
from research.ResearchClaimCalibration import ResearchClaimCalibration


@dataclass(frozen=True, slots=True)
class ResearchCalibrationReport:
    """Report the fit between authored claims and recorded evidence."""

    run_id: str
    calibrations: tuple[ResearchClaimCalibration, ...]

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ResearchError("Calibration report requires a run ID.")
        if not all(
            isinstance(entry, ResearchClaimCalibration) for entry in self.calibrations
        ):
            raise ResearchError("Calibration report accepts only calibrations.")

    @property
    def needing_attention(self) -> tuple[ResearchClaimCalibration, ...]:
        """Return the claims a person should look at again."""
        return tuple(entry for entry in self.calibrations if entry.needs_attention)

    @property
    def overstated(self) -> tuple[ResearchClaimCalibration, ...]:
        """Return the claims asserting more than the record can carry."""
        return tuple(entry for entry in self.calibrations if entry.verdict.overstated)

    def counts(self) -> dict[str, int]:
        """Return bounded per-verdict counts suitable for an event payload."""
        counts: dict[str, int] = {}
        for entry in self.calibrations:
            counts[entry.verdict.value] = counts.get(entry.verdict.value, 0) + 1
        return dict(sorted(counts.items()))

    def of_verdict(
        self,
        verdict: CalibrationVerdict,
    ) -> tuple[ResearchClaimCalibration, ...]:
        """Return the calibrations carrying one bounded verdict."""
        return tuple(entry for entry in self.calibrations if entry.verdict is verdict)
