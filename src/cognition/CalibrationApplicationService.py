"""Report how far each claim outruns its evidence. Never adjust one.

Calibration is read-only by construction. There is no store, no write path, and
no intent that changes a claim: the report is derived from canonical state on
every request, so it cannot drift from the record it describes and there is no
second copy for anyone to trust by mistake.

The refusal to edit is deliberate rather than incidental. An epistemic state is
someone's judgement about what they are willing to assert, and a system that
quietly downgraded it would be overruling that judgement while presenting the
change as bookkeeping. Reporting the mismatch leaves the decision where it
belongs.
"""

from __future__ import annotations

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.CalibrationEvents import CalibrationEvents
from core.Exceptions import ResearchError
from eventbus.EventBus import EventBus
from research.ResearchCalibrationReport import ResearchCalibrationReport
from research.ResearchClaimCalibrator import ResearchClaimCalibrator
from research.ResearchRunManager import ResearchRunManager
from response.ResponseComposer import ResponseComposer

CALIBRATION_REPORT_INTENT = "research_calibration_report"


class CalibrationApplicationService:
    """Derive and report claim calibration, changing nothing."""

    def __init__(
        self,
        run_manager: ResearchRunManager,
        response_composer: ResponseComposer,
        *,
        calibrator: ResearchClaimCalibrator | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._run_manager = run_manager
        self._response_composer = response_composer
        self._calibrator = calibrator or ResearchClaimCalibrator()
        self._events = CalibrationEvents(event_bus)

    @staticmethod
    def is_report_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == CALIBRATION_REPORT_INTENT

    def process_report(self, request: BrainRequest) -> BrainResponse:
        """Report the fit of every active claim against its own support."""
        run_id = request.metadata.get("research_run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            raise ResearchError("Calibration requires a research run ID.")
        run = self._run_manager.get(run_id.strip())
        report = ResearchCalibrationReport(
            run_id=run.run_id,
            calibrations=self._calibrator.calibrate(run),
        )
        self._events.reported(report)
        return self._response_composer.research_calibration(request, report)
