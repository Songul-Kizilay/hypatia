"""Immutable outcome of one canonical source-acceptance transaction.

``transaction_attempted`` and ``accepted`` are deliberately separate. A
transaction can genuinely run and still not accept a source, and the two must
never be collapsed into one flag.

``accepted`` proved too coarse on its own. It is true both when a research run
canonically accepted the source and when the source was merely indexed into
local knowledge with no run bound — two outcomes a reader will not distinguish
unless told. ``stage`` says which one happened, and ``attached_to_run`` is the
question callers actually mean when they ask whether a source was accepted.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError
from research.ResearchRun import ResearchRun
from research.SourceLoadStage import SourceLoadStage

MAX_ACCEPTANCE_FAILURE_REASON_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class ResearchSourceAcceptanceResult:
    """Report exactly what the acceptance transaction did."""

    accepted: bool
    transaction_attempted: bool
    document_id: str | None = None
    run: ResearchRun | None = None
    failure_reason: str = ""
    stage: SourceLoadStage = SourceLoadStage.NOT_ATTEMPTED

    @property
    def attached_to_run(self) -> bool:
        """Return whether a research run canonically accepted this source.

        Callers asking "was the source accepted?" almost always mean this, not
        ``accepted``, which is also true for a knowledge-only index.
        """
        return self.stage.attached_to_run and self.run is not None

    @property
    def partial(self) -> bool:
        """Return whether local work happened without the run accepting it."""
        return self.stage.partial

    def __post_init__(self) -> None:
        if not isinstance(self.accepted, bool):
            raise ResearchError("Source acceptance decision must be boolean.")
        if not isinstance(self.transaction_attempted, bool):
            raise ResearchError("Source acceptance attempt flag must be boolean.")
        if self.accepted and not self.transaction_attempted:
            raise ResearchError("An accepted source requires an attempted transaction.")
        if not isinstance(self.failure_reason, str):
            raise ResearchError("Source acceptance failure reason must be text.")
        reason = self.failure_reason.strip()
        if len(reason) > MAX_ACCEPTANCE_FAILURE_REASON_CHARACTERS:
            raise ResearchError("Source acceptance failure reason is too long.")
        if self.accepted and reason:
            raise ResearchError("An accepted source cannot carry a failure reason.")
        if not self.accepted and not reason:
            raise ResearchError("A rejected source requires a failure reason.")
        object.__setattr__(self, "failure_reason", reason)
        self._validate_stage()

    def _validate_stage(self) -> None:
        """Refuse a stage that disagrees with the rest of the result."""
        if not isinstance(self.stage, SourceLoadStage):
            raise ResearchError("Source acceptance stage must be a bounded value.")
        if self.stage.attached_to_run and self.run is None:
            raise ResearchError(
                "A source cannot be reported as accepted into a run without one."
            )
        if self.run is not None and not self.stage.attached_to_run:
            raise ResearchError(
                "A result carrying a run must report the accepted-into-run stage."
            )
        if self.stage.created_local_document and not self.document_id:
            if not self.stage.rolled_back:
                raise ResearchError(
                    "A stage that indexed a document must name that document."
                )
