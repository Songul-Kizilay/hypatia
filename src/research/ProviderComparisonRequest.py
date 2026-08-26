"""Asking both providers the same question, as two ordinary steps in one plan.

The provider-quality report can describe what happened and not much more, because
one provider is chosen per discovery and the two have therefore almost never been
asked the same thing. Every profile it produces is drawn from a different set of
questions, which makes comparing them a comparison of samples that were never
comparable.

This closes that gap without adding an execution path. A comparison is two
ordinary `source_discovery` steps in one previewed, approved plan — one naming
Crossref, one naming NVD — so everything that already governs a discovery step
governs both of these. Two steps mean two approvals covered by one digest, two
separate network operations charged separately, and two explicit advances,
because one advance has always attempted exactly one step.

The question does not need enforcing and is not carried here twice. A discovery
step asks the research run's own question, so two discovery steps in one run ask
the same question by construction — there is no arrangement in which one side
silently searches for something else.

What this is not: a comparison engine, a second authority path, or a button that
performs two requests under one charge. It builds two step drafts and hands them
to the ordinary planner. Nothing here contacts a provider.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput

#: A comparison is between exactly two providers. Not one, which is an ordinary
#: discovery, and not "all of them", which would turn a deliberate paired
#: question into a fan-out nobody sized.
COMPARISON_PROVIDER_COUNT = 2


@dataclass(frozen=True, slots=True)
class ProviderComparisonRequest:
    """Hold one operator's request to put the same question to two providers."""

    providers: tuple[ResearchDiscoveryProviderName, ...] = (
        ResearchDiscoveryProviderName.CROSSREF,
        ResearchDiscoveryProviderName.NVD,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.providers, tuple):
            raise ResearchError("A provider comparison needs a tuple of providers.")
        if len(self.providers) != COMPARISON_PROVIDER_COUNT:
            raise ResearchError("A provider comparison is between exactly two.")
        if not all(
            isinstance(provider, ResearchDiscoveryProviderName)
            for provider in self.providers
        ):
            raise ResearchError("A provider comparison names an unknown provider.")
        if len(set(self.providers)) != len(self.providers):
            raise ResearchError("A provider comparison needs two different providers.")

    def step_drafts(self) -> tuple[ResearchPlanStepDraftInput, ...]:
        """Return the two ordinary discovery steps this comparison asks for.

        Ordinary in every respect. They carry the same capability, the same
        validation and the same cost as any discovery step somebody wrote by
        hand, and the only thing that makes them a comparison is that a person
        put them in one plan and approved them together.
        """
        return tuple(
            ResearchPlanStepDraftInput(
                instruction=(
                    f"Discover candidate sources through {provider.label}, for "
                    "side-by-side comparison against the other provider."
                ),
                capability=ResearchPlanStepCapability.SOURCE_DISCOVERY.value,
                discovery_provider=provider.value,
            )
            for provider in self.providers
        )
