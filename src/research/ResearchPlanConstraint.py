"""One authored requirement that bounds a plan without being work in it.

Some of what a person writes into a plan is not an instruction to go and do
something. "Do not access external sources yet" is a condition on the whole
plan; it names no action, produces no evidence, and there is nothing for a step
to advance through. Until now the only place to put it was the ordered
instruction list, where it became step 11 of 11 — an executable step whose
instruction told the executor not to execute.

So a constraint is deliberately not a step. It carries no capability, no source
selection, no identity of its own to advance, and nothing in the execution
model can pick it up. What it does carry is exact authored text, and that text
is part of what the operator approves: the digest binds it, so an approval for
a plan that says "do not access external sources" can never be reused for the
same plan with that sentence removed.

What this does not do is enforce anything. Nothing here reads the words and
turns them into a capability restriction, and nothing interprets them at run
time. A constraint is an approved statement of intent that a human wrote and a
human can read back — the enforcement that exists is still the plan's declared
capabilities and the execution's allowance, exactly as before.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_RESEARCH_PLAN_CONSTRAINT_CHARACTERS = 2_000


@dataclass(frozen=True, slots=True)
class ResearchPlanConstraint:
    """Preserve one exact authored restriction that never becomes a step."""

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ResearchError("Research plan constraint cannot be empty.")
        normalized = self.text.strip()
        if len(normalized) > MAX_RESEARCH_PLAN_CONSTRAINT_CHARACTERS:
            raise ResearchError("Research plan constraint is too long.")
        object.__setattr__(self, "text", normalized)
