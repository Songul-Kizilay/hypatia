"""Read-only evidence-integrity check for one research-plan step.

Runs the existing `ResearchEvidenceIntegrityAuditor` against the bound run. It
makes no network request, no LLM call, and no persistence mutation.

The result is deliberately narrow. A completed integrity check proves only that
the integrity operation ran and returned its result. It does not mean the
evidence is true, that any claim is verified, or that any source is
trustworthy. Those remain separate layers in the existing research pipeline.

What the check does report is whether recorded evidence still reconciles with
the current local content: matched, missing, or changed. A matched count is a
statement about structural and provenance consistency, never about truth.
"""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchEvidenceIntegrityAuditor import ResearchEvidenceIntegrityAuditor
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepOperationResult import ResearchPlanStepOperationResult
from research.ResearchRunManager import ResearchRunManager

_TRUTH_BOUNDARY = (
    "Integrity only; this does not establish truth, verify a claim, or make a "
    "source trustworthy."
)


class EvidenceIntegrityCheckStepOperation:
    """Reconcile recorded evidence with current local content for one run."""

    def __init__(
        self,
        integrity_auditor: ResearchEvidenceIntegrityAuditor,
        research_run_manager: ResearchRunManager,
    ) -> None:
        self._integrity_auditor = integrity_auditor
        self._research_run_manager = research_run_manager

    @property
    def operation_name(self) -> str:
        return "evidence_integrity_check"

    def run(
        self,
        step: ResearchPlanStep,
        context: ResearchPlanExecutionContext,
    ) -> ResearchPlanStepOperationResult:
        """Audit the bound run's evidence, or fail safely."""
        del step
        run_id = context.research_run_id
        if run_id is None:
            raise ResearchError(
                "Evidence integrity check requires a bound research run."
            )
        run = self._research_run_manager.get(run_id)
        status = self._integrity_auditor.audit([run])

        if not status.available:
            return ResearchPlanStepOperationResult(
                performed=True,
                detail=(
                    f"Evidence integrity audit ran for run {run.run_id} and "
                    f"reported state '{status.state}'; no counts could be "
                    f"produced. {_TRUTH_BOUNDARY}"
                ),
            )
        if status.recorded_evidence_count == 0:
            return ResearchPlanStepOperationResult(
                performed=True,
                detail=(
                    f"Evidence integrity audit ran for run {run.run_id}. No "
                    f"evidence records were available to inspect. "
                    f"{_TRUTH_BOUNDARY}"
                ),
            )
        return ResearchPlanStepOperationResult(
            performed=True,
            detail=(
                f"Evidence integrity audit ran for run {run.run_id}: "
                f"{status.recorded_evidence_count} record(s), "
                f"{status.matched_evidence_count} matched, "
                f"{status.missing_evidence_count} missing, "
                f"{status.changed_evidence_count} changed. {_TRUTH_BOUNDARY}"
            ),
        )
