"""Every active claim in one run, compared against its own support.

The report is derived, never stored. Anything it says can be recomputed from
canonical state at any moment, so persisting it would only create a second copy
that could drift from the first and then be believed.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.AssessmentWarningKind import AssessmentWarningKind
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

    @property
    def warned(self) -> tuple[ResearchClaimCalibration, ...]:
        """Return the claims whose sources carry a recorded concern.

        Separate from `needing_attention`, which is about the fit between a
        claim and its support. A claim can sit comfortably inside what its
        record can carry and still rest entirely on a paper the person who read
        it later found retracted, and collapsing the two would hide exactly that
        case.
        """
        return tuple(entry for entry in self.calibrations if entry.warnings)

    @property
    def warning_count(self) -> int:
        """Return how many warnings this report raised in total."""
        return sum(len(entry.warnings) for entry in self.calibrations)

    def warning_kind_counts(self) -> dict[str, int]:
        """Return bounded per-kind counts suitable for an event payload."""
        counts: dict[str, int] = {}
        for entry in self.calibrations:
            for warning in entry.warnings:
                counts[warning.kind.value] = counts.get(warning.kind.value, 0) + 1
        return {
            kind.value: counts[kind.value]
            for kind in AssessmentWarningKind
            if kind.value in counts
        }

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
