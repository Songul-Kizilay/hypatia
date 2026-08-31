"""What Hypatia would research next, and the fact that it is not doing it.

A proposal is a preview and nothing else. It holds an ordinary research plan —
the same model an approved plan uses, built by the same draft service, carrying
the same content digest — together with the curiosity provenance explaining why
this plan is being shown at all. What it does not hold is permission.

That distinction is the whole point, so it is stated in the structure rather
than left to the reader: `authorized` and `started` are properties that return
False and cannot be set, because a proposal that could describe itself as
authorized would be one keystroke from being believed. Authorization is a
separate human act against the plan's digest, and the digest here is exactly the
one that act would name.

Provenance is carried, never reconstructed. Every identifier below was read out
of canonical state — the question the operator accepted, the gap it came from,
the run it belongs to, and where the gap is about a hypothesis, that hypothesis
and the test it named. Nothing is inferred from the wording of anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchKnowledgeGapKind import ResearchKnowledgeGapKind
from research.ResearchPlan import ResearchPlan
from research.ResearchPlanDigest import plan_digest

MAX_PROPOSAL_TEXT_LENGTH = 400

NOT_AUTHORIZED_NOTICE = (
    "This is a preview. Nothing has been authorized and nothing is running. "
    "Execution requires a separate explicit authorization against this plan's "
    "digest, which this preview does not create, request, or imply."
)

NO_CONCLUSION_NOTICE = (
    "A proposal says what would be looked into, never what is true. The gap "
    "that prompted it is a statement about the state of our own record."
)


@dataclass(frozen=True, slots=True)
class CuriosityResearchProposal:
    """Present one accepted curiosity question as an inert research plan."""

    curiosity_question_id: str
    knowledge_gap_id: str
    run_id: str
    gap_kind: ResearchKnowledgeGapKind
    question: str
    objective: str
    plan: ResearchPlan
    hypothesis_id: str = ""
    discriminating_test: str = ""

    def __post_init__(self) -> None:
        for name in (
            "curiosity_question_id",
            "knowledge_gap_id",
            "run_id",
            "question",
            "objective",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"A research proposal needs a {name}.")
        if not isinstance(self.gap_kind, ResearchKnowledgeGapKind):
            raise ResearchError("A research proposal needs a known gap kind.")
        if not isinstance(self.plan, ResearchPlan):
            raise ResearchError("A research proposal needs a validated plan.")
        for name in ("hypothesis_id", "discriminating_test"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise ResearchError(f"A research proposal {name} must be text.")
            object.__setattr__(
                self, name, " ".join(value.split())[:MAX_PROPOSAL_TEXT_LENGTH]
            )

    @property
    def authorized(self) -> bool:
        """Say whether this is authorized. It is not, and cannot become so here.

        A property rather than a field, so nothing can construct a proposal that
        claims otherwise. Authorization lives in its own record, created by a
        person against the digest below.
        """
        return False

    @property
    def started(self) -> bool:
        """Say whether anything is running. Nothing is."""
        return False

    @property
    def digest(self) -> str:
        """Return the content identity a later authorization would name."""
        return plan_digest(self.plan)

    @property
    def step_count(self) -> int:
        """Return how many steps the proposed plan describes."""
        return len(self.plan.steps)

    def lines(self) -> tuple[str, ...]:
        """Render the proposal so its state cannot be misread."""
        rendered = [
            "RESEARCH PROPOSAL — preview only, not authorized, not running",
            f"Curiosity question: {self.question}",
            f"Question ID: {self.curiosity_question_id}",
            f"Prompted by gap: {self.gap_kind.value} ({self.knowledge_gap_id})",
            f"Research run: {self.run_id}",
        ]
        if self.hypothesis_id:
            rendered.append(f"Hypothesis: {self.hypothesis_id}")
        if self.discriminating_test:
            rendered.append(f"Its discriminating test: {self.discriminating_test}")
        rendered.extend(
            (
                "",
                f"Objective: {self.objective}",
                f"Proposed steps ({self.step_count}), none performed:",
            )
        )
        rendered.extend(
            f"- {step.capability.value}: {step.instruction}" for step in self.plan.steps
        )
        rendered.extend(
            (
                "",
                f"Completion: {_completion_text(self.gap_kind)}",
                f"Plan digest: {self.digest}",
                f"Authorized: {'yes' if self.authorized else 'no'}",
                f"Running: {'yes' if self.started else 'no'}",
                "",
                NOT_AUTHORIZED_NOTICE,
                "",
                NO_CONCLUSION_NOTICE,
            )
        )
        return tuple(rendered)


def _completion_text(kind: ResearchKnowledgeGapKind) -> str:
    """Say what would make this proposal's gap stop being a gap.

    Stated as the gap closing rather than as a question being answered, because
    the gap is the thing this milestone can actually observe. Whether the answer
    is satisfying is a person's judgement and is not something a plan can
    promise.
    """
    return _COMPLETION.get(kind, _DEFAULT_COMPLETION)


_DEFAULT_COMPLETION = (
    "This proposal is finished when the gap that prompted it is no longer "
    "reported for this run."
)

_COMPLETION: dict[ResearchKnowledgeGapKind, str] = {
    ResearchKnowledgeGapKind.HYPOTHESIS_EVIDENCE_GAP: (
        "This proposal is finished when an operator has recorded evidence "
        "addressing the hypothesis's discriminating test. Recording that "
        "evidence says the test was examined, never that it passed."
    ),
    ResearchKnowledgeGapKind.PROVIDER_COVERAGE_GAP: (
        "This proposal is finished when the remaining provider has been asked "
        "this run's question. Asking it says nothing about which provider "
        "answers better."
    ),
    ResearchKnowledgeGapKind.FAILED_ACQUISITION: (
        "This proposal is finished when the information the failed acquisition "
        "would have supplied is obtained from some source, which need not be "
        "the one that failed."
    ),
}
