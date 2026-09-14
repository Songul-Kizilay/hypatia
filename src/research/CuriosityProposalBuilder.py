"""Turn one accepted curiosity question into an inert plan, deterministically.

Templates, not generation. The gap kind chooses an objective and a shape of
step, every value that reaches either comes out of canonical state, and the same
state produces the same plan and therefore the same digest. No model is
consulted, and there is nothing here that could consult one.

The steps describe future work and perform none of it. They are ordinary
research plan steps built by the ordinary draft service, which means they are
also ordinary in the sense that matters: a person still has to authorize them
against the plan's digest before anything happens.

Two temptations are refused by name. A failed acquisition does not become "try
that again" — the failure said something is missing, and what to do about that
is a decision the operator makes with a plan in front of them. And a hypothesis
gap does not become a proposal to run the discriminating test; it becomes a
proposal to look for evidence that would address it, which is research rather
than an experiment on somebody's system.
"""

from __future__ import annotations

from collections.abc import Sequence

from core.Exceptions import ResearchError
from research.CuriosityResearchProposal import CuriosityResearchProposal
from research.ResearchCuriosityQuestion import ResearchCuriosityQuestion
from research.ResearchDiscoveryProviderName import ResearchDiscoveryProviderName
from research.ResearchHypothesis import ResearchHypothesis
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchPlanDraftService import ResearchPlanDraftService
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchPlanStepDraftInput import ResearchPlanStepDraftInput
from research.ResearchRun import ResearchRun

MAX_SUBJECT_LENGTH = 160


class CuriosityProposalBuilder:
    """Compose one inert proposal from canonical curiosity and run state."""

    def build(
        self,
        question: ResearchCuriosityQuestion,
        run: ResearchRun,
        draft_service: ResearchPlanDraftService,
        hypotheses: Sequence[ResearchHypothesis] = (),
    ) -> CuriosityResearchProposal:
        """Return the proposal, or raise when the plan itself is invalid."""
        if not isinstance(question, ResearchCuriosityQuestion):
            raise ResearchError("A research proposal requires a curiosity question.")
        if not isinstance(run, ResearchRun):
            raise ResearchError("A research proposal requires its research run.")
        hypothesis = _hypothesis_for(question, hypotheses)
        preview = draft_service.preview(run.question, _steps(question, run))
        if not preview.allowed or preview.plan is None:
            raise ResearchError(
                f"A research proposal could not be drafted: {preview.reason}"
            )
        return CuriosityResearchProposal(
            curiosity_question_id=question.question_id,
            knowledge_gap_id=question.gap_id,
            run_id=question.run_id,
            gap_kind=question.kind,
            question=question.text,
            objective=_objective(question, run),
            plan=preview.plan,
            hypothesis_id=hypothesis.hypothesis_id if hypothesis else "",
            discriminating_test=(hypothesis.discriminating_test if hypothesis else ""),
        )


def _hypothesis_for(
    question: ResearchCuriosityQuestion,
    hypotheses: Sequence[ResearchHypothesis],
) -> ResearchHypothesis | None:
    """Return the hypothesis this gap is about, matched by identifier alone.

    A hypothesis gap names its hypothesis in the gap's subject, so the match is
    an identifier comparison. Nothing here reads a statement or a test looking
    for a likely candidate.
    """
    if question.kind not in (
        ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP,
        ResearchKnowledgeGapKind.UNCONFIRMED_INDEPENDENCE_HYPOTHESIS,
    ):
        return None
    for hypothesis in hypotheses:
        if (
            hypothesis.hypothesis_id == question.subject_id
            and hypothesis.run_id == question.run_id
        ):
            return hypothesis
    return None


def _objective(question: ResearchCuriosityQuestion, run: ResearchRun) -> str:
    """State what the proposal is for, in terms of the record rather than truth."""
    match question.kind:
        case ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP:
            return (
                "Find sources that could supply evidence addressing the "
                "discriminating test of this hypothesis, so that an operator "
                "has something to judge. Whether the hypothesis holds is not "
                "decided here."
            )
        case ResearchKnowledgeGapKind.UNCONFIRMED_INDEPENDENCE_HYPOTHESIS:
            return (
                "Find independent sources bearing on this hypothesis so its "
                "apparent corroboration can be distinguished from repeated "
                "reporting. Whether the hypothesis holds is not decided here."
            )
        case ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP:
            missing = _unasked_providers(run)
            named = ", ".join(missing) if missing else "the remaining providers"
            return (
                f"Put this run's question to {named}, which has not been asked "
                "it, so the operator can see what a second source of results "
                "adds. Neither provider is preferred."
            )
        case ResearchKnowledgeGapKind.FAILED_ACQUISITION:
            return (
                "Find another source for the information the failed "
                "acquisition would have supplied. This does not propose "
                "repeating the attempt that failed."
            )
        case _:
            return (
                "Find sources bearing on this run's question, to fill the gap "
                "the curiosity question names."
            )


def _steps(
    question: ResearchCuriosityQuestion,
    run: ResearchRun,
) -> tuple[ResearchPlanStepDraftInput, ...]:
    """Return the future work this proposal describes, performing none of it.

    Looking inward, then outward. Every proposal begins by searching what is
    already known locally, because a gap is a claim about the record and the
    record is the cheapest place to check it: the search reaches no network,
    costs no part of the approved budget, and may well show that some of what
    was about to be looked for is already here.

    It stops at finding candidates. Everything past that point — loading a
    source, accepting one, recording evidence, judging it — is an explicit
    operator action elsewhere, and a plan that quietly included those steps
    would be asking approval for far more than it appears to. Those steps also
    need identifiers that do not exist yet: a source to accept is one a
    discovery has not run to find. Authoring them would mean binding to a
    result nobody has, which this refuses to do rather than guessing at run
    time.
    """
    return (_local_step(question),) + _discovery_steps(question, run)


def _local_step(
    question: ResearchCuriosityQuestion,
) -> ResearchPlanStepDraftInput:
    """Return the step that asks what is already known here, before going out."""
    return ResearchPlanStepDraftInput(
        instruction=(
            "Search local knowledge for material bearing on this curiosity "
            f"question before asking anyone outside: {question.text}"
        ),
        capability=ResearchPlanStepCapability.LOCAL_KNOWLEDGE_SEARCH.value,
    )


def _discovery_steps(
    question: ResearchCuriosityQuestion,
    run: ResearchRun,
) -> tuple[ResearchPlanStepDraftInput, ...]:
    """Return the outward-looking steps, each naming an exact provider or none."""
    if question.kind is ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP:
        providers = _unasked_providers(run) or [
            provider.value for provider in ResearchDiscoveryProviderName
        ]
        return tuple(
            ResearchPlanStepDraftInput(
                instruction=(
                    f"Discover candidate sources through {provider}, which has "
                    "not yet been asked this run's question."
                ),
                capability=ResearchPlanStepCapability.SOURCE_DISCOVERY.value,
                discovery_provider=provider,
            )
            for provider in providers
        )
    return (
        ResearchPlanStepDraftInput(
            instruction=_instruction(question),
            capability=ResearchPlanStepCapability.SOURCE_DISCOVERY.value,
        ),
    )


def _instruction(question: ResearchCuriosityQuestion) -> str:
    match question.kind:
        case ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP:
            return (
                "Discover candidate sources that could address this "
                "hypothesis's discriminating test. Finding a source is not "
                "performing the test."
            )
        case ResearchKnowledgeGapKind.UNCONFIRMED_INDEPENDENCE_HYPOTHESIS:
            return (
                "Discover candidate sources that could independently corroborate "
                "this hypothesis beyond its current support."
            )
        case ResearchKnowledgeGapKind.FAILED_ACQUISITION:
            return (
                "Discover candidate sources for the information that could "
                "not be acquired, without repeating the failed attempt."
            )
        case _:
            return "Discover candidate sources bearing on this run's question."


def _unasked_providers(run: ResearchRun) -> list[str]:
    """Return providers this run has not put its question to, in fixed order."""
    asked = {discovery.provider for discovery in run.discoveries}
    return [
        provider.value
        for provider in ResearchDiscoveryProviderName
        if provider.value not in asked
    ]
