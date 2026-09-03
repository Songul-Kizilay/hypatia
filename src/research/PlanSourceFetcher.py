"""Select the enforced target transport, never an unscoped fallback.

Reference research keeps its existing injected routing (including NVD). A
target-bound execution uses only the canonical public HTTPS text fetcher with
its own approved immutable scope; redirects and pinned connections therefore
share the same scope. No provider-specific routing can substitute another host.
This is not a sandbox against hostile in-process Python collaborators.
"""

from research.HttpResearchSourceFetcher import HttpResearchSourceFetcher
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchSource import ResearchSource
from research.ResearchSourceFetcher import ResearchSourceFetcher
from research.ScopedPublicHttpsUrlValidator import ScopedPublicHttpsUrlValidator


def fetch_plan_source(
    url: str,
    context: ResearchPlanExecutionContext,
    reference_fetcher: ResearchSourceFetcher,
) -> ResearchSource:
    binding = context.target_binding
    if binding is None:
        return reference_fetcher.fetch(url)
    return HttpResearchSourceFetcher(
        validator=ScopedPublicHttpsUrlValidator(binding.scope)
    ).fetch(url)
