"""How far a source load actually got.

This exists because of a real failure. A source was fetched and indexed into
local knowledge while no research run was bound to the request, and the response
said "Research source loaded" and printed a document ID. Nothing had failed, so
no safe failure was recorded, and the run's canonical state correctly showed zero
accepted sources. Every individual part was behaving; the report was still
wrong, because one word — loaded — was covering two very different outcomes.

A local document existing and a research run having accepted a source are
different facts. Indexing puts text where search can reach it. Acceptance is a
canonical, persisted statement that this run is built on this source, and it is
the thing evidence, assessments, and claims are allowed to rest on. Conflating
them lets a run look sourced when it is not.

So every load reports the stage it reached, including the successful ones. The
stages are ordered by how far the work got, and a caller can ask whether a
local document now exists without also being told the run accepted it.
"""

from __future__ import annotations

from enum import StrEnum


class SourceLoadStage(StrEnum):
    """Name exactly how far one source-load attempt progressed."""

    NOT_ATTEMPTED = "not_attempted"
    CANCELLED = "cancelled"
    FETCH_REFUSED = "fetch_refused"
    INDEX_FAILED = "index_failed"
    CONTENT_PERSIST_FAILED = "content_persist_failed"
    RUN_ATTACH_FAILED = "run_attach_failed"
    INDEXED_WITHOUT_RUN = "indexed_without_run"
    ACCEPTED_INTO_RUN = "accepted_into_run"

    @property
    def attached_to_run(self) -> bool:
        """Return whether a research run canonically accepted the source.

        This is the only stage evidence may be recorded from, and the only one
        that should ever be described to a person as an accepted source.
        """
        return self is SourceLoadStage.ACCEPTED_INTO_RUN

    @property
    def created_local_document(self) -> bool:
        """Return whether a local knowledge document now exists.

        True for the partial stage as well as the complete one, because the
        document is real either way and pretending otherwise would hide it.
        """
        return self in (
            SourceLoadStage.INDEXED_WITHOUT_RUN,
            SourceLoadStage.ACCEPTED_INTO_RUN,
            SourceLoadStage.CONTENT_PERSIST_FAILED,
            SourceLoadStage.RUN_ATTACH_FAILED,
        )

    @property
    def rolled_back(self) -> bool:
        """Return whether the load undid the local work it had already done."""
        return self in (
            SourceLoadStage.CONTENT_PERSIST_FAILED,
            SourceLoadStage.RUN_ATTACH_FAILED,
        )

    @property
    def partial(self) -> bool:
        """Return whether local work happened without the run accepting it.

        A partial stage is not a failure and not a success. It is the state a
        person most needs told plainly, because it is the one that looks like
        success from the outside.
        """
        return self.created_local_document and not self.attached_to_run

    @property
    def failed(self) -> bool:
        """Return whether the attempt ended without producing a usable source."""
        return self in (
            SourceLoadStage.CANCELLED,
            SourceLoadStage.FETCH_REFUSED,
            SourceLoadStage.INDEX_FAILED,
            SourceLoadStage.CONTENT_PERSIST_FAILED,
            SourceLoadStage.RUN_ATTACH_FAILED,
        )

    @property
    def summary(self) -> str:
        """Return one bounded sentence describing what this stage means."""
        return _SUMMARIES[self]


_SUMMARIES: dict[SourceLoadStage, str] = {
    SourceLoadStage.NOT_ATTEMPTED: "No source load was attempted.",
    SourceLoadStage.CANCELLED: "The source load was cancelled before it finished.",
    SourceLoadStage.FETCH_REFUSED: (
        "The source was not fetched. Nothing was indexed and no run changed."
    ),
    SourceLoadStage.INDEX_FAILED: (
        "The source was fetched but could not be indexed locally. No run changed."
    ),
    SourceLoadStage.CONTENT_PERSIST_FAILED: (
        "The source was fetched and indexed, but its content audit could not be "
        "saved, so the local document was rolled back and no run changed."
    ),
    SourceLoadStage.RUN_ATTACH_FAILED: (
        "The source was fetched and indexed, but the research run did not accept "
        "it, so the local work was rolled back and no run changed."
    ),
    SourceLoadStage.INDEXED_WITHOUT_RUN: (
        "The source was fetched and indexed into local knowledge, but no "
        "research run accepted it. It is not an accepted research source, and "
        "no evidence can be recorded from it."
    ),
    SourceLoadStage.ACCEPTED_INTO_RUN: (
        "The source was fetched, indexed, and accepted into the research run. "
        "Acceptance is not evidence."
    ),
}


def summary_for(stage: SourceLoadStage) -> str:
    """Return the declared summary, refusing an undescribed stage."""
    if stage not in _SUMMARIES:
        raise ValueError(f"Source load stage {stage} declares no summary.")
    return _SUMMARIES[stage]
