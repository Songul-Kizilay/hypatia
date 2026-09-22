"""No-write exact-observation revalidation planning over a recorded run source."""

from __future__ import annotations

from core.Exceptions import ResearchError
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchRun import ResearchRun
from research.SourceRevalidationStepBinding import SourceRevalidationStepBinding


def preview_source_revalidation(
    run: ResearchRun,
    prior_observation_id: str,
    *,
    draft_service: ResearchPlanDraftService | None = None,
) -> ResearchPlanDraftPreview:
    """Bind one re-fetch to one recorded source observation of this same run.

    The prior observation and its requested URL are resolved from the run's
    own current source records, never from caller-supplied fields. A legacy
    record that predates observation identity (``observation_id`` or
    ``requested_url`` is ``None``) can never be named here, so the resulting
    binding can never smuggle in a URL that does not belong to the named
    observation, and can never name a run other than this one.
    """
    try:
        if not isinstance(run, ResearchRun) or run.status.terminal:
            raise ResearchError("Select an open research run for revalidation.")
        if (
            not isinstance(prior_observation_id, str)
            or not prior_observation_id.strip()
        ):
            raise ResearchError("An exact prior observation ID is required.")
        source = next(
            (
                item
                for item in run.sources
                if item.observation_id == prior_observation_id
            ),
            None,
        )
        if (
            source is None
            or source.observation_id is None
            or source.requested_url is None
        ):
            raise ResearchError(
                "The prior observation does not belong to this research run."
            )
        binding = SourceRevalidationStepBinding(
            run.run_id,
            source.observation_id,
            source.requested_url,
            len(run.sources) + 1,
        )
        return (draft_service or ResearchPlanDraftService()).preview(
            run.question,
            (
                ResearchPlanStepDraftInput(
                    instruction=(
                        "Re-fetch the exact recorded prior observation once. "
                        f"Prior observation: {source.observation_id}."
                    ),
                    capability="source_revalidation",
                    source_revalidation_binding=binding,
                ),
            ),
        )
    except ResearchError as error:
        return ResearchPlanDraftPreview.rejected(str(error))
