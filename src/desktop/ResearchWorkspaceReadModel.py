"""Immutable Tkinter-independent projections for the Research workspace."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchSourceAssessmentRecord import ResearchSourceAssessmentRecord
from research.ResearchSourceRecord import ResearchSourceRecord


class ResearchRunSort(StrEnum):
    """User-facing deterministic orders for the loaded run presentation."""

    UPDATED_NEWEST = "Updated — newest first"
    UPDATED_OLDEST = "Updated — oldest first"
    CREATED_NEWEST = "Created — newest first"
    QUESTION = "Question — A to Z"


class ResearchRunStatusFacet(StrEnum):
    """User-facing local status views for the loaded run catalog."""

    ALL = "All statuses"
    COLLECTING = "Collecting"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class ResearchSourceCoverageFacet(StrEnum):
    """User-facing local coverage views for accepted research sources."""

    ALL = "All sources"
    WITHOUT_EVIDENCE = "Without evidence"
    WITHOUT_CURRENT_ASSESSMENT = "Without current assessment"


@dataclass(frozen=True, slots=True)
class ResearchRunReadView:
    """Complete presentation-only projection of one immutable research run."""

    label: str
    context: str
    summary: str
    progress: str
    workflow_snapshot: str
    evidence_coverage: str
    assessment_coverage: str
    metadata: str


@dataclass(frozen=True, slots=True)
class ResearchSourceReadView:
    """Safe presentation-only projection of one accepted-source candidate."""

    label: str
    summary: str
    details: str | None
    canonical: bool


@dataclass(frozen=True, slots=True)
class ResearchWorkspaceReadModel:
    """Project already loaded research snapshots without opening runtime paths."""

    runs: tuple[ResearchRun, ...]

    def catalog_summary_text(self) -> str:
        """Summarize complete immutable catalog membership by lifecycle."""
        status_counts = " · ".join(
            f"{status.value.title()} "
            f"{sum(run.status is status for run in self.runs)}"
            for status in ResearchRunStatus
        )
        return f"Loaded catalog: All {len(self.runs)} · {status_counts}"

    def filter_runs(self, query: str) -> tuple[ResearchRun, ...]:
        """Match bounded question text, exact status, or exact run ID locally."""
        normalized_query = query.strip().casefold()
        if not normalized_query:
            return self.runs
        return tuple(
            run
            for run in self.runs
            if normalized_query in run.question.casefold()
            or normalized_query == run.status.value.casefold()
            or normalized_query == run.run_id.casefold()
        )

    def filter_runs_by_status(
        self,
        status_filter: ResearchRunStatus | None,
    ) -> tuple[ResearchRun, ...]:
        """Restrict the loaded tuple to one exact lifecycle status."""
        if status_filter is None:
            return self.runs
        return tuple(run for run in self.runs if run.status is status_filter)

    def sort_runs(self, mode: ResearchRunSort) -> tuple[ResearchRun, ...]:
        """Sort the loaded tuple with deterministic ascending ID ties."""
        id_ordered = tuple(
            sorted(
                self.runs,
                key=lambda run: (run.run_id.casefold(), run.run_id),
            )
        )
        if mode is ResearchRunSort.UPDATED_NEWEST:
            return tuple(
                sorted(id_ordered, key=lambda run: run.updated_at, reverse=True)
            )
        if mode is ResearchRunSort.UPDATED_OLDEST:
            return tuple(sorted(id_ordered, key=lambda run: run.updated_at))
        if mode is ResearchRunSort.CREATED_NEWEST:
            return tuple(
                sorted(id_ordered, key=lambda run: run.created_at, reverse=True)
            )
        return tuple(
            sorted(
                id_ordered,
                key=lambda run: (
                    run.question.casefold(),
                    run.run_id.casefold(),
                    run.run_id,
                ),
            )
        )

    @classmethod
    def run_view(cls, run: ResearchRun) -> ResearchRunReadView:
        """Build every current run-level presentation value in one projection."""
        label = cls.run_label(run)
        progress = cls.run_progress_text(run)
        return ResearchRunReadView(
            label=label,
            context=cls.run_context_text(run),
            summary=cls.run_summary_text(run),
            progress=progress,
            workflow_snapshot=cls.workflow_snapshot_text(run),
            evidence_coverage=cls.evidence_coverage_text(run),
            assessment_coverage=cls.assessment_coverage_text(run),
            metadata=cls.run_metadata_text(run),
        )

    @staticmethod
    def run_label(run: ResearchRun) -> str:
        """Keep exact run identity beside one bounded question."""
        question = run.question
        if len(question) > 80:
            question = f"{question[:77]}..."
        return f"{question} [{run.status.value}] — {run.run_id}"

    @classmethod
    def run_context_text(cls, run: ResearchRun) -> str:
        """Identify the exact immutable run snapshot used by later views."""
        return f"Working on: {cls.run_label(run)}"

    @classmethod
    def run_summary_text(cls, run: ResearchRun) -> str:
        """Combine lifecycle status with complete selected-run counts."""
        return f"Status: {run.status.value} · {cls.run_progress_text(run)}"

    @staticmethod
    def run_progress_text(run: ResearchRun) -> str:
        """Show complete selected-snapshot counts in each workflow tab."""
        return (
            f"Sources: {len(run.sources)} · "
            f"Evidence: {len(run.evidence)} · Claims: {len(run.claims)}"
        )

    @staticmethod
    def workflow_snapshot_text(run: ResearchRun) -> str:
        """Describe existing stage records without readiness or truth inference."""
        return (
            f"Sources & evidence — Sources: {len(run.sources)} · "
            f"Evidence: {len(run.evidence)} | Authored analysis — "
            f"Assessments: {len(run.assessments)} · "
            f"Comparison notes: {len(run.comparison_notes)} · "
            f"Claims: {len(run.claims)} · "
            f"Contradictions: {len(run.claim_contradictions)} | "
            f"Review & export — Status: {run.status.value}"
        )

    @staticmethod
    def evidence_coverage_text(run: ResearchRun) -> str:
        """Count accepted sources represented by evidence without inference."""
        accepted_source_ids = {source.document_id for source in run.sources}
        represented_source_ids = {
            record.source_document_id for record in run.evidence
        } & accepted_source_ids
        accepted_count = len(accepted_source_ids)
        represented_count = len(represented_source_ids)
        return (
            f"Evidence coverage — Accepted sources: {accepted_count} · "
            f"With evidence: {represented_count} · "
            f"Without evidence: {accepted_count - represented_count}"
        )

    @classmethod
    def assessment_coverage_text(cls, run: ResearchRun) -> str:
        """Count accepted sources with a current authored assessment."""
        accepted_source_ids = frozenset(source.document_id for source in run.sources)
        current_source_ids = cls.current_assessment_source_ids(
            run.sources,
            run.assessments,
        )
        accepted_count = len(accepted_source_ids)
        current_count = len(current_source_ids)
        return (
            f"Assessment coverage — Accepted sources: {accepted_count} · "
            f"With current assessment: {current_count} · "
            f"Without current assessment: {accepted_count - current_count}"
        )

    @staticmethod
    def current_assessment_source_ids(
        sources: tuple[ResearchSourceRecord, ...],
        assessments: tuple[ResearchSourceAssessmentRecord, ...],
    ) -> frozenset[str]:
        """Return accepted source IDs represented by current assessments."""
        accepted_source_ids = frozenset(source.document_id for source in sources)
        superseded_assessment_ids = {
            record.supersedes_assessment_id
            for record in assessments
            if record.supersedes_assessment_id is not None
        }
        return frozenset(
            record.source_document_id
            for record in assessments
            if record.assessment_id not in superseded_assessment_ids
            and record.source_document_id in accepted_source_ids
        )

    @staticmethod
    def run_metadata_text(run: ResearchRun) -> str:
        """Expose bounded audit timing and a count without failure details."""
        created = run.created_at.isoformat(timespec="seconds")
        updated = run.updated_at.isoformat(timespec="seconds")
        return (
            f"Run metadata — Created: {created} · Updated: {updated} · "
            f"Safe failures: {len(run.failures)}"
        )

    @classmethod
    def filter_sources_by_coverage(
        cls,
        sources: tuple[ResearchSourceRecord, ...],
        evidence: tuple[ResearchEvidenceRecord, ...],
        assessments: tuple[ResearchSourceAssessmentRecord, ...],
        facet: ResearchSourceCoverageFacet,
    ) -> tuple[ResearchSourceRecord, ...]:
        """Return stable source membership for one exact local coverage facet."""
        if facet is ResearchSourceCoverageFacet.ALL:
            return sources
        if facet is ResearchSourceCoverageFacet.WITHOUT_EVIDENCE:
            represented_source_ids = frozenset(
                record.source_document_id for record in evidence
            )
        else:
            represented_source_ids = cls.current_assessment_source_ids(
                sources,
                assessments,
            )
        return tuple(
            source
            for source in sources
            if source.document_id not in represented_source_ids
        )

    @staticmethod
    def revalidation_eligible_sources(
        sources: tuple[ResearchSourceRecord, ...],
    ) -> tuple[ResearchSourceRecord, ...]:
        """Keep only sources a revalidation binding could actually name.

        A legacy record without a recorded observation identity or requested
        URL predates that provenance and is never inferred here: offering it
        would only surface an opaque refusal from
        `SourceRevalidationStepBinding`'s own validation later.
        """
        return tuple(
            source
            for source in sources
            if source.observation_id is not None and source.requested_url is not None
        )

    @classmethod
    def source_catalog_summary_text(cls, run: ResearchRun) -> str:
        """Summarize complete source coverage independent of the local view."""
        without_evidence_count = len(
            cls.filter_sources_by_coverage(
                run.sources,
                run.evidence,
                run.assessments,
                ResearchSourceCoverageFacet.WITHOUT_EVIDENCE,
            )
        )
        without_current_assessment_count = len(
            cls.filter_sources_by_coverage(
                run.sources,
                run.evidence,
                run.assessments,
                ResearchSourceCoverageFacet.WITHOUT_CURRENT_ASSESSMENT,
            )
        )
        return (
            f"Accepted-source coverage — All: {len(run.sources)} · "
            f"Without evidence: {without_evidence_count} · "
            "Without current assessment: "
            f"{without_current_assessment_count}"
        )

    @classmethod
    def source_view(
        cls,
        run: ResearchRun,
        source: ResearchSourceRecord,
    ) -> ResearchSourceReadView:
        """Project safe source details only after exact canonical membership."""
        label = cls.source_label(source)
        canonical_source = next(
            (candidate for candidate in run.sources if candidate == source),
            None,
        )
        if canonical_source is None:
            return ResearchSourceReadView(
                label=label,
                summary=(
                    "Selected-source records unavailable until an accepted source "
                    "is selected."
                ),
                details=None,
                canonical=False,
            )
        source_evidence_ids = frozenset(
            record.evidence_id
            for record in run.evidence
            if record.source_document_id == canonical_source.document_id
        )
        assessment_records = tuple(
            record
            for record in run.assessments
            if record.source_document_id == canonical_source.document_id
        )
        superseded_ids = {
            record.supersedes_assessment_id
            for record in run.assessments
            if record.supersedes_assessment_id is not None
        }
        current_assessment_records = tuple(
            record
            for record in assessment_records
            if record.assessment_id not in superseded_ids
        )
        current_assessment_evidence_ids = frozenset(
            evidence_id
            for record in current_assessment_records
            for evidence_id in record.evidence_ids
            if evidence_id in source_evidence_ids
        )
        information_trust_counts = {
            trust: sum(
                record.information_trust is trust
                for record in current_assessment_records
            )
            for trust in ResearchInformationTrust
        }
        title = cls.bounded_source_title(canonical_source)
        summary = (
            f"Selected source — {title} · "
            f"Source ID: {canonical_source.document_id} · "
            f"Run ID: {run.run_id}\nSafety boundary — "
            f"Data taint: {canonical_source.taint_label} · "
            "Instruction authority: "
            f"{canonical_source.instruction_authority}\nRecords — "
            f"Evidence: {len(source_evidence_ids)} · "
            f"Assessments: {len(assessment_records)} history / "
            f"{len(current_assessment_records)} current · "
            "Evidence cited by current: "
            f"{len(current_assessment_evidence_ids)} of {len(source_evidence_ids)}\n"
            "Current information trust — "
            "Unassessed: "
            f"{information_trust_counts[ResearchInformationTrust.UNASSESSED]} · "
            f"Low: {information_trust_counts[ResearchInformationTrust.LOW]} · "
            f"Medium: {information_trust_counts[ResearchInformationTrust.MEDIUM]} · "
            f"High: {information_trust_counts[ResearchInformationTrust.HIGH]}"
        )
        details = cls.source_details_text(run, canonical_source)
        return ResearchSourceReadView(
            label=label,
            summary=summary,
            details=details,
            canonical=True,
        )

    @classmethod
    def source_details_text(
        cls,
        run: ResearchRun,
        source: ResearchSourceRecord,
    ) -> str | None:
        """Render safe provenance only after exact canonical membership."""
        canonical_source = next(
            (candidate for candidate in run.sources if candidate == source),
            None,
        )
        if canonical_source is None:
            return None
        title = cls.bounded_source_title(canonical_source)
        fetched = canonical_source.fetched_at.isoformat(timespec="seconds")
        accepted = canonical_source.added_at.isoformat(timespec="seconds")
        return (
            f"Title: {title}\n"
            f"Document ID: {canonical_source.document_id}\n"
            f"Run ID: {run.run_id}\n"
            f"Content type: {canonical_source.content_type}\n"
            f"Fetched: {fetched}\n"
            f"Accepted: {accepted}"
        )

    @staticmethod
    def bounded_source_title(source: ResearchSourceRecord) -> str:
        """Normalize and bound untrusted title text for compact presentation."""
        title = " ".join(source.title.split())
        if len(title) > 80:
            title = f"{title[:77]}..."
        return title

    @classmethod
    def source_label(cls, source: ResearchSourceRecord) -> str:
        """Keep exact document identity beside one bounded source title."""
        return f"{cls.bounded_source_title(source)} — {source.document_id}"
