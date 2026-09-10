"""No-write exact-candidate acquisition planning over recorded discoveries."""

from __future__ import annotations

import json

from core.Exceptions import ResearchError
from research.ResearchPlanDraftPreview import ResearchPlanDraftPreview
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchRun import ResearchRun
from research.SourceIdentity import identity_of


def preview_acquisition_batch(
    run: ResearchRun,
    discovery_id: str,
    selected_urls: tuple[str, ...],
    *,
    draft_service: ResearchPlanDraftService | None = None,
) -> ResearchPlanDraftPreview:
    """Use exact recorded URLs; source prose cannot choose steps or authority.

    The provenance receipt is literal instruction metadata already covered by
    the canonical plan digest. It is never parsed as an execution directive.
    No plan schema/digest encoding change or second authorization is introduced.
    """
    try:
        if not isinstance(run, ResearchRun) or run.status.terminal:
            raise ResearchError("Select an open research run for acquisition.")
        if not isinstance(discovery_id, str) or not discovery_id.strip():
            raise ResearchError("An exact discovery ID is required.")
        if (
            not isinstance(selected_urls, tuple)
            or not 1 <= len(selected_urls) <= 10
            or any(not isinstance(url, str) or not url for url in selected_urls)
        ):
            raise ResearchError("Select between one and ten exact candidate URLs.")
        discovery = next(
            (item for item in run.discoveries if item.discovery_id == discovery_id),
            None,
        )
        if discovery is None:
            raise ResearchError("The discovery does not belong to this research run.")
        available = {item.url for item in discovery.candidates}
        if any(url not in available for url in selected_urls):
            raise ResearchError(
                "Candidate selection changed or is not in this discovery."
            )
        if len({identity_of(url) for url in selected_urls}) != len(selected_urls):
            raise ResearchError("Select each source resource only once.")
        receipt = json.dumps(
            {
                "run_id": run.run_id,
                "discovery_id": discovery.discovery_id,
                "provider": discovery.provider,
                "discovered_at": discovery.discovered_at.isoformat(),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        return (draft_service or ResearchPlanDraftService()).preview(
            run.question,
            tuple(
                ResearchPlanStepDraftInput(
                    instruction="Acquire unaccepted reference text. Origin receipt: "
                    + receipt,
                    capability="source_fetch",
                    authorized_source_url=url,
                )
                for url in selected_urls
            ),
        )
    except ResearchError as error:
        return ResearchPlanDraftPreview.rejected(str(error))
