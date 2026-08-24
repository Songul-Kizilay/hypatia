"""How far a research question has actually got, read from canonical state.

Simple mode shows a progress ladder, and a progress ladder is the easiest place
in a user interface to tell a small lie. It is tempting to advance a step when a
button is pressed, because that is when the user expects movement. But the
button starting the work and the work having happened are different facts, and
the interface that conflates them is the interface that says a source was
accepted when the run has no sources.

So every step here is derived from a persisted `ResearchRun` and nothing else.
There is no setter. A step cannot be advanced by an intention, a return value,
or an optimistic guess — only by canonical state saying so on the next refresh.
Work that is currently in flight is a `SimpleResearchActivity`, which is
deliberately a separate type so it cannot be mistaken for progress.

The ladder stops at evidence recorded. There is no "research ready" step,
because nothing in the canonical state can support that claim: evidence is not a
verified claim, and a run with one accepted source and one evidence record is at
the beginning of research, not the end of it. Simple mode is allowed to be
simpler than the audit view; it is not allowed to say something the audit view
would contradict.
"""

from __future__ import annotations

from enum import StrEnum

from research.ResearchRun import ResearchRun


class SimpleResearchStep(StrEnum):
    """Name how far one research question has canonically progressed."""

    NOT_STARTED = "not_started"
    QUESTION_CREATED = "question_created"
    SOURCES_DISCOVERED = "sources_discovered"
    SOURCE_ACCEPTED = "source_accepted"
    EVIDENCE_RECORDED = "evidence_recorded"

    @property
    def order(self) -> int:
        """Return this step's position in the ladder, starting at zero."""
        return _ORDER.index(self)

    @property
    def reached_by(self) -> tuple[SimpleResearchStep, ...]:
        """Return every step at or before this one, for rendering the ladder."""
        return _ORDER[: self.order + 1]

    @property
    def has_run(self) -> bool:
        """Return whether a canonical run exists at this step."""
        return self is not SimpleResearchStep.NOT_STARTED

    @property
    def has_accepted_source(self) -> bool:
        """Return whether the run canonically accepted at least one source.

        Discovery does not count. A discovered candidate is a proposal that
        nothing has fetched, and the distance between those two is the whole
        reason this type reads canonical state instead of tracking clicks.
        """
        return self.order >= SimpleResearchStep.SOURCE_ACCEPTED.order

    @property
    def has_evidence(self) -> bool:
        """Return whether an evidence record exists. Not that a claim is true."""
        return self is SimpleResearchStep.EVIDENCE_RECORDED

    @classmethod
    def for_run(cls, run: ResearchRun | None) -> SimpleResearchStep:
        """Derive the reached step from one immutable run snapshot.

        Order matters: the checks run from the furthest state backwards, so a
        run holding evidence is reported at evidence even though it also holds
        sources and discoveries.
        """
        if run is None:
            return cls.NOT_STARTED
        if run.evidence:
            return cls.EVIDENCE_RECORDED
        if run.sources:
            return cls.SOURCE_ACCEPTED
        if any(discovery.candidates for discovery in run.discoveries):
            return cls.SOURCES_DISCOVERED
        return cls.QUESTION_CREATED

    @staticmethod
    def ladder() -> tuple[SimpleResearchStep, ...]:
        """Return the steps a person is shown, excluding the absent one."""
        return _ORDER[1:]


_ORDER: tuple[SimpleResearchStep, ...] = (
    SimpleResearchStep.NOT_STARTED,
    SimpleResearchStep.QUESTION_CREATED,
    SimpleResearchStep.SOURCES_DISCOVERED,
    SimpleResearchStep.SOURCE_ACCEPTED,
    SimpleResearchStep.EVIDENCE_RECORDED,
)
