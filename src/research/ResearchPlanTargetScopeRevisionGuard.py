"""Validate target plans against exact active program-scope revisions."""

from __future__ import annotations

from datetime import datetime

from research.ResearchPlanTargetBinding import ResearchPlanTargetBinding
from research.ResearchProgramScopeRevisionStore import ResearchProgramScopeRevisionStore


def target_scope_revision_refusal(
    binding: ResearchPlanTargetBinding | None,
    store: ResearchProgramScopeRevisionStore | None,
    moment: datetime,
) -> str | None:
    """Return a refusal reason when a target binding lacks its live revision."""
    if binding is None:
        return None
    if not binding.has_scope_revision:
        return "Target-bound research requires an exact active saved scope revision."
    if store is None:
        return "Program scope revisions are unavailable in this runtime."
    matches = tuple(
        revision
        for revision in store.load()
        if revision.revision_id == binding.scope_revision_id
        and revision.revision_digest == binding.scope_revision_digest
    )
    if len(matches) != 1:
        return "Target scope revision is not the exact active saved revision."
    revision = matches[0]
    if not revision.valid_at(moment):
        return "Target scope revision is not active at this time."
    if revision.program_id != binding.program_id or revision.scope != binding.scope:
        return "Target binding does not match the exact saved scope revision."
    return None
