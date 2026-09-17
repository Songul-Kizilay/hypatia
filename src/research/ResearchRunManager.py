"""Transactional owner of persisted research-run audit state."""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import RLock
from uuid import uuid4

from core.Exceptions import ResearchError
from knowledge.Chunk import Chunk
from research.ResearchClaimConfidence import ResearchClaimConfidence
from research.ResearchClaimContradictionPreview import (
    ResearchClaimContradictionPreview,
)
from research.ResearchClaimContradictionRecord import (
    MAX_CLAIM_CONTRADICTION_NOTE_CHARACTERS,
    ResearchClaimContradictionRecord,
)
from research.ResearchClaimContradictionWritePreview import (
    ResearchClaimContradictionWritePreview,
)
from research.ResearchClaimPreview import ResearchClaimPreview
from research.ResearchClaimRecord import (
    MAX_RESEARCH_CLAIM_CHARACTERS,
    MAX_RESEARCH_CLAIM_EVIDENCE,
    ResearchClaimRecord,
)
from research.ResearchClaimWritePreview import ResearchClaimWritePreview
from research.ResearchComparisonReviewRecord import (
    MAX_COMPARISON_REVIEW_NOTE_CHARACTERS,
    ResearchComparisonReviewDecision,
    ResearchComparisonReviewRecord,
    current_comparison_review,
)
from research.ResearchEpistemicState import ResearchEpistemicState
from research.ResearchEvidenceRecord import ResearchEvidenceRecord
from research.ResearchExportPublisher import publish_new_export_file
from research.ResearchFailureRecord import ResearchFailureRecord
from research.ResearchInformationTrust import ResearchInformationTrust
from research.ResearchRun import ResearchRun
from research.ResearchRunMarkdownExportPreview import (
    MAX_MARKDOWN_EXPORT_PREVIEW_CHARACTERS,
    ResearchRunMarkdownExportPreview,
)
from research.ResearchRunMarkdownExportResult import (
    ResearchRunMarkdownExportResult,
)
from research.ResearchRunMarkdownExportVerification import (
    MAX_MARKDOWN_EXPORT_VERIFICATION_BYTES,
    ResearchRunMarkdownExportVerification,
)
from research.ResearchRunMarkdownRenderer import render_research_run_markdown
from research.ResearchRunStatus import ResearchRunStatus
from research.ResearchRunStatusTransitionPreview import (
    ResearchRunStatusTransitionPreview,
)
from research.ResearchRunStore import ResearchRunStore
from research.ResearchSource import ResearchSource
from research.ResearchSourceApplicability import ResearchSourceApplicability
from research.ResearchSourceAssessmentPreview import ResearchSourceAssessmentPreview
from research.ResearchSourceAssessmentRecord import (
    MAX_SOURCE_ASSESSMENT_CHARACTERS,
    ResearchSourceAssessmentRecord,
)
from research.ResearchSourceAssessmentWritePreview import (
    ResearchSourceAssessmentWritePreview,
)
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceCandidateAcceptancePreview import (
    ResearchSourceCandidateAcceptancePreview,
)
from research.ResearchSourceComparisonItem import (
    MAX_COMPARISON_ASSESSMENTS_PER_SOURCE,
    MAX_COMPARISON_EVIDENCE_PER_SOURCE,
    ResearchSourceComparisonItem,
)
from research.ResearchSourceComparisonNoteRecord import (
    MAX_COMPARISON_NOTE_ASSESSMENTS,
    MAX_COMPARISON_NOTE_CHARACTERS,
    MAX_COMPARISON_NOTE_EVIDENCE,
    ResearchSourceComparisonNoteRecord,
)
from research.ResearchSourceComparisonNoteWritePreview import (
    ResearchSourceComparisonNoteWritePreview,
)
from research.ResearchSourceComparisonPreview import (
    MAX_COMPARISON_NOTES,
    MAX_COMPARISON_SOURCES,
    MIN_COMPARISON_SOURCES,
    ResearchSourceComparisonPreview,
)
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceIndependence import ResearchSourceIndependence
from research.ResearchSourcePublicationStatus import ResearchSourcePublicationStatus
from research.ResearchSourceRecord import ResearchSourceRecord
from research.ResearchSourceUsefulness import ResearchSourceUsefulness


class ResearchRunManager:
    """Create and update research runs only after snapshot persistence succeeds."""

    def __init__(
        self,
        store: ResearchRunStore | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        evidence_id_factory: Callable[[], str] | None = None,
        discovery_id_factory: Callable[[], str] | None = None,
        assessment_id_factory: Callable[[], str] | None = None,
        comparison_note_id_factory: Callable[[], str] | None = None,
        claim_id_factory: Callable[[], str] | None = None,
        claim_contradiction_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._evidence_id_factory = evidence_id_factory or (lambda: str(uuid4()))
        self._discovery_id_factory = discovery_id_factory or (lambda: str(uuid4()))
        self._assessment_id_factory = assessment_id_factory or (lambda: str(uuid4()))
        self._comparison_note_id_factory = comparison_note_id_factory or (
            lambda: str(uuid4())
        )
        self._claim_id_factory = claim_id_factory or (lambda: str(uuid4()))
        self._claim_contradiction_id_factory = claim_contradiction_id_factory or (
            lambda: str(uuid4())
        )
        self._runs: tuple[ResearchRun, ...] = ()
        self._lock = RLock()

    def load(self) -> None:
        """Load and atomically replace the current in-memory snapshot."""
        if self._store is None:
            return
        runs = self._store.load()
        with self._lock:
            self._runs = tuple(runs)

    def create(self, question: str) -> ResearchRun:
        """Create a collecting run for one explicit research question."""
        normalized_question = self._normalize_question(question)
        with self._lock:
            now = self._now()
            run = ResearchRun(
                run_id=self._new_run_id(),
                question=normalized_question,
                status=ResearchRunStatus.COLLECTING,
                sources=(),
                failures=(),
                created_at=now,
                updated_at=now,
                discoveries=(),
                assessments=(),
                comparison_notes=(),
                claims=(),
                claim_contradictions=(),
                comparison_reviews=(),
            )
            candidate = (*self._runs, run)
            self._persist(candidate)
            self._runs = candidate
        return run

    def list(self) -> list[ResearchRun]:
        """Return runs in deterministic creation order."""
        with self._lock:
            return list(self._runs)

    def get(self, run_id: str) -> ResearchRun:
        """Return one run or raise a controlled unknown-run error."""
        normalized_id = self._normalize_run_id(run_id)
        with self._lock:
            run = next(
                (item for item in self._runs if item.run_id == normalized_id), None
            )
        if run is None:
            raise ResearchError(f"Research run was not found: {normalized_id}")
        return run

    def preview_claims(self, run_id: str) -> ResearchClaimPreview:
        """Return persisted claim history without inference or mutation."""
        normalized_id = self._normalize_run_id(run_id)
        with self._lock:
            _, run = self._find_with_index(normalized_id)
            count = len(run.claims)
            return ResearchClaimPreview(
                run_id=run.run_id,
                question=run.question,
                run_status=run.status,
                claims=run.claims,
                reason=(
                    f"Run has {count} user-authored evidence-linked claim"
                    f"{'s' if count != 1 else ''}."
                    if count
                    else "Run has no user-authored evidence-linked claims."
                ),
            )

    def preview_claim_contradictions(
        self,
        run_id: str,
    ) -> ResearchClaimContradictionPreview:
        """Return persisted user-reviewed contradiction history without inference."""
        normalized_id = self._normalize_run_id(run_id)
        with self._lock:
            _, run = self._find_with_index(normalized_id)
            count = len(run.claim_contradictions)
            return ResearchClaimContradictionPreview(
                run_id=run.run_id,
                question=run.question,
                run_status=run.status,
                claims=run.claims,
                contradictions=run.claim_contradictions,
                reason=(
                    f"Run has {count} user-reviewed claim contradiction"
                    f"{'s' if count != 1 else ''}."
                    if count
                    else "Run has no user-reviewed claim contradictions."
                ),
            )

    def preview_markdown_export(
        self,
        run_id: str,
    ) -> ResearchRunMarkdownExportPreview:
        """Render one terminal immutable snapshot without writing or live lookups."""
        normalized_id = self._normalize_run_id(run_id)
        with self._lock:
            _, run = self._find_with_index(normalized_id)
            if not run.status.terminal:
                raise ResearchError("A collecting research run cannot be exported yet.")
            markdown = render_research_run_markdown(run)
            visible_markdown = markdown[:MAX_MARKDOWN_EXPORT_PREVIEW_CHARACTERS]
            omitted_character_count = len(markdown) - len(visible_markdown)
            if omitted_character_count:
                visible_markdown += (
                    "\n\n> Preview truncated: "
                    f"{omitted_character_count} characters omitted.\n"
                )
            content_sha256 = sha256(markdown.encode("utf-8")).hexdigest()
            return ResearchRunMarkdownExportPreview(
                run_id=run.run_id,
                run_status=run.status,
                snapshot_updated_at=run.updated_at,
                suggested_filename=self._markdown_export_filename(run.run_id),
                markdown_preview=visible_markdown,
                total_character_count=len(markdown),
                omitted_character_count=omitted_character_count,
                content_sha256=content_sha256,
            )

    def save_markdown_export(
        self,
        run_id: str,
        destination_path: str | Path,
        *,
        expected_snapshot_updated_at: datetime,
        expected_content_sha256: str,
    ) -> ResearchRunMarkdownExportResult:
        """Revalidate a preview and atomically publish one new Markdown file."""
        normalized_id = self._normalize_run_id(run_id)
        destination = self._normalize_markdown_export_destination(destination_path)
        expected_updated_at = self._normalize_export_snapshot_time(
            expected_snapshot_updated_at
        )
        expected_sha256 = self._normalize_export_sha256(expected_content_sha256)
        with self._lock:
            _, run = self._find_with_index(normalized_id)
            if not run.status.terminal:
                raise ResearchError("A collecting research run cannot be exported yet.")
            if run.updated_at != expected_updated_at:
                raise ResearchError("Research export preview is stale.")
            markdown = render_research_run_markdown(run)
            encoded = markdown.encode("utf-8")
            content_sha256 = sha256(encoded).hexdigest()
            if content_sha256 != expected_sha256:
                raise ResearchError("Research export preview fingerprint is stale.")
            self._publish_new_export(destination, encoded)
            return ResearchRunMarkdownExportResult(
                run_id=run.run_id,
                snapshot_updated_at=run.updated_at,
                destination_path=str(destination),
                content_sha256=content_sha256,
                byte_count=len(encoded),
            )

    def verify_markdown_export(
        self,
        run_id: str,
        source_path: str | Path,
    ) -> ResearchRunMarkdownExportVerification:
        """Hash one stable existing file and compare it with a terminal run."""
        normalized_id = self._normalize_run_id(run_id)
        source = self._normalize_markdown_export_source(source_path)
        with self._lock:
            _, run = self._find_with_index(normalized_id)
            if not run.status.terminal:
                raise ResearchError(
                    "A collecting research run cannot verify an export yet."
                )
            expected_content = render_research_run_markdown(run).encode("utf-8")
            expected_hash = sha256(expected_content).hexdigest()
            allowed_bytes = max(
                len(expected_content),
                MAX_MARKDOWN_EXPORT_VERIFICATION_BYTES,
            )
            observed_hash, observed_bytes = self._hash_stable_export_file(
                source,
                max_bytes=allowed_bytes,
            )
            expected_bytes = len(expected_content)
            matches = (
                expected_hash == observed_hash and expected_bytes == observed_bytes
            )
            return ResearchRunMarkdownExportVerification(
                run_id=run.run_id,
                snapshot_updated_at=run.updated_at,
                source_path=str(source),
                expected_content_sha256=expected_hash,
                observed_content_sha256=observed_hash,
                expected_byte_count=expected_bytes,
                observed_byte_count=observed_bytes,
                matches=matches,
            )

    def has_source(self, run_id: str, document_id: str) -> bool:
        """Return whether the run already records a source document."""
        run = self.get(run_id)
        normalized_document_id = self._normalize_document_id(document_id)
        return any(
            source.document_id == normalized_document_id for source in run.sources
        )

    def add_source(
        self,
        run_id: str,
        source: ResearchSource,
        document_id: str,
        requested_url: str | None = None,
    ) -> ResearchRun:
        """Persist source provenance after successful local knowledge indexing."""
        normalized_id = self._normalize_run_id(run_id)
        normalized_document_id = self._normalize_document_id(document_id)
        with self._lock:
            index, run = self._find_with_index(normalized_id)
            self._require_collecting(run)
            if any(
                record.document_id == normalized_document_id for record in run.sources
            ):
                raise ResearchError("Research source is already attached to this run.")
            now = self._now()
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=(
                    *run.sources,
                    ResearchSourceRecord.from_source(
                        source,
                        normalized_document_id,
                        now,
                        requested_url=requested_url,
                    ),
                ),
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=run.assessments,
                comparison_notes=run.comparison_notes,
                claims=run.claims,
                claim_contradictions=run.claim_contradictions,
                comparison_reviews=run.comparison_reviews,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def record_failure(
        self,
        run_id: str,
        stage: str,
        reason: str,
        *,
        provider: str | None = None,
    ) -> ResearchRun:
        """Persist a safe bounded failure without retaining rejected URL input."""
        normalized_id = self._normalize_run_id(run_id)
        with self._lock:
            index, run = self._find_with_index(normalized_id)
            self._require_collecting(run)
            now = self._now()
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=(
                    *run.failures,
                    ResearchFailureRecord(stage, reason, now, provider),
                ),
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=run.assessments,
                comparison_notes=run.comparison_notes,
                claims=run.claims,
                claim_contradictions=run.claim_contradictions,
                comparison_reviews=run.comparison_reviews,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def add_evidence(self, run_id: str, chunk: Chunk, note: str) -> ResearchRun:
        """Persist one explicit evidence record from an accepted source chunk."""
        normalized_id = self._normalize_run_id(run_id)
        if not isinstance(chunk, Chunk):
            raise ResearchError("Research evidence expects a knowledge chunk.")
        normalized_note = self._normalize_evidence_note(note)
        with self._lock:
            index, run = self._find_with_index(normalized_id)
            self._require_collecting(run)
            if not any(
                source.document_id == chunk.document_id for source in run.sources
            ):
                raise ResearchError(
                    "Research evidence must come from a source attached to this run."
                )
            self._refuse_duplicate(
                "evidence",
                self._identical_evidence(run, chunk, normalized_note),
            )
            now = self._now()
            evidence = ResearchEvidenceRecord.from_chunk(
                self._new_evidence_id(),
                chunk,
                normalized_note,
                now,
            )
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=(*run.evidence, evidence),
                discoveries=run.discoveries,
                assessments=run.assessments,
                comparison_notes=run.comparison_notes,
                claims=run.claims,
                claim_contradictions=run.claim_contradictions,
                comparison_reviews=run.comparison_reviews,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def add_discovery(
        self,
        run_id: str,
        query: str,
        provider: str,
        candidates: Sequence[ResearchSourceCandidate],
    ) -> ResearchRun:
        """Atomically persist one ordered, unaccepted discovery result."""
        normalized_id = self._normalize_run_id(run_id)
        normalized_query = self._normalize_question(query)
        normalized_provider = self._normalize_provider(provider)
        if not isinstance(candidates, list):
            raise ResearchError("Research source discovery candidates must be a list.")
        candidate_tuple: tuple[ResearchSourceCandidate, ...] = tuple(candidates)
        if len(candidate_tuple) > 10:
            raise ResearchError(
                "Research source discovery cannot contain more than 10 candidates."
            )
        if not all(
            isinstance(candidate, ResearchSourceCandidate)
            for candidate in candidate_tuple
        ):
            raise ResearchError(
                "Research source discovery contains an invalid candidate."
            )
        with self._lock:
            index, run = self._find_with_index(normalized_id)
            self._require_collecting(run)
            now = self._now()
            discovery = ResearchSourceDiscoveryRecord(
                discovery_id=self._new_discovery_id(),
                query=normalized_query,
                provider=normalized_provider,
                candidates=candidate_tuple,
                discovered_at=now,
            )
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=(*run.discoveries, discovery),
                assessments=run.assessments,
                comparison_notes=run.comparison_notes,
                claims=run.claims,
                claim_contradictions=run.claim_contradictions,
                comparison_reviews=run.comparison_reviews,
            )
            candidate_runs = list(self._runs)
            candidate_runs[index] = updated
            candidate_snapshot = tuple(candidate_runs)
            self._persist(candidate_snapshot)
            self._runs = candidate_snapshot
        return updated

    def preview_status_transition(
        self,
        run_id: str,
        target_status: ResearchRunStatus,
    ) -> ResearchRunStatusTransitionPreview:
        """Return a no-side-effect decision for one terminal transition."""
        normalized_id = self._normalize_run_id(run_id)
        if not isinstance(target_status, ResearchRunStatus):
            raise ResearchError("Research run target status is invalid.")
        with self._lock:
            _, run = self._find_with_index(normalized_id)
            return self._status_transition_preview(run, target_status)

    def preview_candidate_acceptance(
        self,
        run_id: str,
        discovery_id: str,
        candidate_url: str,
    ) -> ResearchSourceCandidateAcceptancePreview:
        """Revalidate one persisted candidate without network or mutation."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_discovery_id = self._normalize_discovery_id(discovery_id)
        normalized_url = self._normalize_candidate_url(candidate_url)
        with self._lock:
            _, run = self._find_with_index(normalized_run_id)
            discovery = next(
                (
                    item
                    for item in run.discoveries
                    if item.discovery_id == normalized_discovery_id
                ),
                None,
            )
            if discovery is None:
                raise ResearchError("Research source discovery was not found.")
            candidate = next(
                (item for item in discovery.candidates if item.url == normalized_url),
                None,
            )
            if candidate is None:
                raise ResearchError(
                    "Research source candidate was not found in this discovery."
                )
            if run.status.terminal:
                return ResearchSourceCandidateAcceptancePreview(
                    run.run_id,
                    discovery.discovery_id,
                    candidate,
                    False,
                    "A closed research run cannot accept new sources.",
                )
            return ResearchSourceCandidateAcceptancePreview(
                run.run_id,
                discovery.discovery_id,
                candidate,
                True,
                _acceptance_disclosure(candidate),
            )

    def preview_source_assessment(
        self,
        run_id: str,
        document_id: str,
    ) -> ResearchSourceAssessmentPreview:
        """Return accepted provenance and explicit evidence without mutation."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_document_id = self._normalize_document_id(document_id)
        with self._lock:
            _, run = self._find_with_index(normalized_run_id)
            source = next(
                (
                    record
                    for record in run.sources
                    if record.document_id == normalized_document_id
                ),
                None,
            )
            if source is None:
                raise ResearchError(
                    "Research source was not found among this run's accepted sources."
                )
            evidence = tuple(
                record
                for record in run.evidence
                if record.source_document_id == source.document_id
            )
            evidence_count = len(evidence)
            reason = (
                f"Source has {evidence_count} user-selected evidence record"
                f"{'s' if evidence_count != 1 else ''} for manual assessment."
                if evidence
                else (
                    "Source has no user-selected evidence records; no quality or "
                    "support conclusion can be drawn."
                )
            )
            return ResearchSourceAssessmentPreview(
                run_id=run.run_id,
                run_status=run.status,
                source=source,
                evidence=evidence,
                has_recorded_evidence=bool(evidence),
                reason=reason,
                assessments=tuple(
                    record
                    for record in run.assessments
                    if record.source_document_id == source.document_id
                ),
            )

    def preview_source_comparison(
        self,
        run_id: str,
        document_ids: Sequence[str],
    ) -> ResearchSourceComparisonPreview:
        """Return ordered manual evidence columns without live work or mutation."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_document_ids = self._normalize_comparison_document_ids(document_ids)
        with self._lock:
            _, run = self._find_with_index(normalized_run_id)
            sources_by_id = {source.document_id: source for source in run.sources}
            if any(
                document_id not in sources_by_id
                for document_id in normalized_document_ids
            ):
                raise ResearchError(
                    "A research comparison source was not found among this run's "
                    "accepted sources."
                )
            superseded_assessment_ids = {
                record.supersedes_assessment_id
                for record in run.assessments
                if record.supersedes_assessment_id is not None
            }
            items = tuple(
                self._comparison_item(
                    run,
                    sources_by_id[document_id],
                    superseded_assessment_ids,
                )
                for document_id in normalized_document_ids
            )
            matching_notes = tuple(
                note
                for note in run.comparison_notes
                if note.source_document_ids == normalized_document_ids
            )
            return ResearchSourceComparisonPreview(
                run_id=run.run_id,
                question=run.question,
                run_status=run.status,
                sources=items,
                reason=(
                    f"{len(items)} explicitly selected accepted sources are shown "
                    "side by side for manual review."
                ),
                comparison_notes=matching_notes[:MAX_COMPARISON_NOTES],
                omitted_comparison_note_count=max(
                    0,
                    len(matching_notes) - MAX_COMPARISON_NOTES,
                ),
            )

    @staticmethod
    def _comparison_item(
        run: ResearchRun,
        source: ResearchSourceRecord,
        superseded_assessment_ids: set[str],
    ) -> ResearchSourceComparisonItem:
        """Collect bounded display records while retaining honest total counts."""
        evidence: list[ResearchEvidenceRecord] = []
        total_evidence_count = 0
        for evidence_record in run.evidence:
            if evidence_record.source_document_id != source.document_id:
                continue
            total_evidence_count += 1
            if len(evidence) < MAX_COMPARISON_EVIDENCE_PER_SOURCE:
                evidence.append(evidence_record)

        current_assessments: list[ResearchSourceAssessmentRecord] = []
        total_current_assessment_count = 0
        for assessment_record in run.assessments:
            if (
                assessment_record.source_document_id != source.document_id
                or assessment_record.assessment_id in superseded_assessment_ids
            ):
                continue
            total_current_assessment_count += 1
            if len(current_assessments) < MAX_COMPARISON_ASSESSMENTS_PER_SOURCE:
                current_assessments.append(assessment_record)

        return ResearchSourceComparisonItem(
            source=source,
            evidence=tuple(evidence),
            current_assessments=tuple(current_assessments),
            omitted_evidence_count=total_evidence_count - len(evidence),
            omitted_current_assessment_count=(
                total_current_assessment_count - len(current_assessments)
            ),
        )

    def preview_source_assessment_write(
        self,
        run_id: str,
        document_id: str,
        evidence_ids: Sequence[str],
        text: str,
        supersedes_assessment_id: str | None = None,
        information_trust: ResearchInformationTrust | str = (
            ResearchInformationTrust.UNASSESSED
        ),
        usefulness: ResearchSourceUsefulness | str = ResearchSourceUsefulness.UNKNOWN,
        applicability: ResearchSourceApplicability | str = (
            ResearchSourceApplicability.UNKNOWN
        ),
        independence: ResearchSourceIndependence | str = (
            ResearchSourceIndependence.UNKNOWN
        ),
        publication_status: ResearchSourcePublicationStatus | str = (
            ResearchSourcePublicationStatus.UNKNOWN
        ),
    ) -> ResearchSourceAssessmentWritePreview:
        """Validate one authored assessment without mutating persisted state."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_document_id = self._normalize_document_id(document_id)
        normalized_evidence_ids = self._normalize_assessment_evidence_ids(evidence_ids)
        normalized_text = self._normalize_assessment_text(text)
        normalized_superseded_id = self._normalize_optional_assessment_id(
            supersedes_assessment_id
        )
        normalized_information_trust = self._normalize_information_trust(
            information_trust
        )
        normalized_judgement = self._normalize_source_judgement(
            usefulness,
            applicability,
            independence,
            publication_status,
        )
        with self._lock:
            _, run = self._find_with_index(normalized_run_id)
            source, evidence = self._source_and_evidence_for_assessment(
                run,
                normalized_document_id,
                normalized_evidence_ids,
            )
            superseded_assessment = self._superseded_assessment_for_write(
                run,
                source.document_id,
                normalized_superseded_id,
            )
            duplicate = (
                None
                if superseded_assessment is not None
                else self._identical_assessment(
                    run,
                    source.document_id,
                    tuple(record.evidence_id for record in evidence),
                    normalized_text,
                    normalized_information_trust,
                    normalized_judgement,
                )
            )
            allowed = not run.status.terminal and duplicate is None
            reason = (
                self._duplicate_reason("assessment", duplicate)
                if duplicate is not None
                else (
                    (
                        "Research source assessment correction can be recorded after "
                        "confirmation."
                        if superseded_assessment is not None
                        else (
                            "Research source assessment can be recorded after "
                            "confirmation."
                        )
                    )
                    if allowed
                    else "A closed research run cannot accept new assessments."
                )
            )
            return ResearchSourceAssessmentWritePreview(
                run_id=run.run_id,
                run_status=run.status,
                source=source,
                evidence=evidence,
                text=normalized_text,
                allowed=allowed,
                reason=reason,
                supersedes_assessment=superseded_assessment,
                information_trust=normalized_information_trust,
                usefulness=normalized_judgement[0],
                applicability=normalized_judgement[1],
                independence=normalized_judgement[2],
                publication_status=normalized_judgement[3],
            )

    def preview_claim_write(
        self,
        run_id: str,
        evidence_ids: Sequence[str],
        text: str,
        epistemic_state: ResearchEpistemicState | str,
        confidence: ResearchClaimConfidence | str = ResearchClaimConfidence.UNASSESSED,
        supersedes_claim_id: str | None = None,
    ) -> ResearchClaimWritePreview:
        """Validate one authored evidence-linked claim without mutation."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_evidence_ids = self._normalize_claim_evidence_ids(evidence_ids)
        normalized_text = self._normalize_claim_text(text)
        normalized_state = self._normalize_epistemic_state(epistemic_state)
        normalized_confidence = self._normalize_claim_confidence(confidence)
        normalized_superseded_id = self._normalize_optional_claim_id(
            supersedes_claim_id
        )
        with self._lock:
            _, run = self._find_with_index(normalized_run_id)
            sources, evidence = self._claim_sources_and_evidence(
                run,
                normalized_evidence_ids,
            )
            superseded_claim = self._superseded_claim_for_write(
                run,
                normalized_superseded_id,
            )
            duplicate_claim = (
                None
                if superseded_claim is not None
                else self._identical_claim(
                    run,
                    tuple(record.evidence_id for record in evidence),
                    normalized_text,
                    normalized_state,
                    normalized_confidence,
                )
            )
            allowed = not run.status.terminal and duplicate_claim is None
            reason = (
                self._duplicate_reason("claim", duplicate_claim)
                if duplicate_claim is not None
                else (
                    (
                        "Research claim correction can be recorded after confirmation."
                        if superseded_claim is not None
                        else "Research claim can be recorded after confirmation."
                    )
                    if allowed
                    else "A closed research run cannot accept new claims."
                )
            )
            return ResearchClaimWritePreview(
                run_id=run.run_id,
                run_status=run.status,
                sources=sources,
                evidence=evidence,
                text=normalized_text,
                epistemic_state=normalized_state,
                confidence=normalized_confidence,
                allowed=allowed,
                reason=reason,
                supersedes_claim=superseded_claim,
            )

    def record_claim(
        self,
        run_id: str,
        evidence_ids: Sequence[str],
        text: str,
        epistemic_state: ResearchEpistemicState | str,
        confidence: ResearchClaimConfidence | str = ResearchClaimConfidence.UNASSESSED,
        supersedes_claim_id: str | None = None,
    ) -> ResearchRun:
        """Revalidate and atomically append one user-authored research claim."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_evidence_ids = self._normalize_claim_evidence_ids(evidence_ids)
        normalized_text = self._normalize_claim_text(text)
        normalized_state = self._normalize_epistemic_state(epistemic_state)
        normalized_confidence = self._normalize_claim_confidence(confidence)
        normalized_superseded_id = self._normalize_optional_claim_id(
            supersedes_claim_id
        )
        with self._lock:
            index, run = self._find_with_index(normalized_run_id)
            sources, evidence = self._claim_sources_and_evidence(
                run,
                normalized_evidence_ids,
            )
            superseded_claim = self._superseded_claim_for_write(
                run,
                normalized_superseded_id,
            )
            if superseded_claim is None:
                self._refuse_duplicate(
                    "claim",
                    self._identical_claim(
                        run,
                        tuple(record.evidence_id for record in evidence),
                        normalized_text,
                        normalized_state,
                        normalized_confidence,
                    ),
                )
            self._require_collecting(run)
            now = self._now()
            claim = ResearchClaimRecord(
                claim_id=self._new_claim_id(),
                text=normalized_text,
                epistemic_state=normalized_state,
                confidence=normalized_confidence,
                source_document_ids=tuple(source.document_id for source in sources),
                evidence_ids=tuple(record.evidence_id for record in evidence),
                recorded_at=now,
                supersedes_claim_id=(
                    None if superseded_claim is None else superseded_claim.claim_id
                ),
            )
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=run.assessments,
                comparison_notes=run.comparison_notes,
                claims=(*run.claims, claim),
                claim_contradictions=run.claim_contradictions,
                comparison_reviews=run.comparison_reviews,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def preview_claim_contradiction_write(
        self,
        run_id: str,
        claim_ids: Sequence[str],
        note: str,
    ) -> ResearchClaimContradictionWritePreview:
        """Validate one authored contradiction relationship without mutation."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_claim_ids = self._normalize_claim_contradiction_claim_ids(claim_ids)
        normalized_note = self._normalize_claim_contradiction_note(note)
        with self._lock:
            _, run = self._find_with_index(normalized_run_id)
            claims, evidence = self._claim_contradiction_references(
                run,
                normalized_claim_ids,
            )
            duplicate = self._claim_contradiction_exists(
                run,
                normalized_claim_ids,
            )
            allowed = not run.status.terminal and not duplicate
            if run.status.terminal:
                reason = "A closed research run cannot accept claim contradictions."
            elif duplicate:
                reason = "A contradiction relationship already exists for these claims."
            else:
                reason = (
                    "Research claim contradiction can be recorded after confirmation."
                )
            return ResearchClaimContradictionWritePreview(
                run_id=run.run_id,
                run_status=run.status,
                claims=claims,
                evidence=evidence,
                note=normalized_note,
                allowed=allowed,
                reason=reason,
            )

    def record_claim_contradiction(
        self,
        run_id: str,
        claim_ids: Sequence[str],
        note: str,
    ) -> ResearchRun:
        """Revalidate and append one separately confirmed claim contradiction."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_claim_ids = self._normalize_claim_contradiction_claim_ids(claim_ids)
        normalized_note = self._normalize_claim_contradiction_note(note)
        with self._lock:
            index, run = self._find_with_index(normalized_run_id)
            claims, evidence = self._claim_contradiction_references(
                run,
                normalized_claim_ids,
            )
            if self._claim_contradiction_exists(run, normalized_claim_ids):
                raise ResearchError(
                    "A contradiction relationship already exists for these claims."
                )
            self._require_collecting(run)
            now = self._now()
            contradiction = ResearchClaimContradictionRecord(
                contradiction_id=self._new_claim_contradiction_id(),
                claim_ids=(claims[0].claim_id, claims[1].claim_id),
                evidence_ids=tuple(record.evidence_id for record in evidence),
                note=normalized_note,
                recorded_at=now,
            )
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=run.assessments,
                comparison_notes=run.comparison_notes,
                claims=run.claims,
                claim_contradictions=(*run.claim_contradictions, contradiction),
                comparison_reviews=run.comparison_reviews,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def record_comparison_review(
        self,
        run_id: str,
        note_id: str,
        decision: ResearchComparisonReviewDecision | str,
        note: str,
        supersedes_review_id: str | None = None,
    ) -> ResearchRun:
        """Revalidate and append one operator review of one exact comparison note.

        The review copies the note's evidence identities.  A note that already
        has a current review can only be reviewed again by superseding exactly
        that review, so a stale operator view cannot overwrite a newer decision
        and support can be withdrawn without deleting history.
        """
        normalized_run_id = self._normalize_run_id(run_id)
        if not isinstance(note_id, str) or not note_id.strip():
            raise ResearchError("Research comparison review note ID cannot be empty.")
        normalized_note_id = note_id.strip()
        try:
            normalized_decision = ResearchComparisonReviewDecision(
                decision.strip() if isinstance(decision, str) else decision
            )
        except (TypeError, ValueError) as error:
            raise ResearchError(
                "Research comparison review decision is invalid."
            ) from error
        if not isinstance(note, str) or not note.strip():
            raise ResearchError("Research comparison review note cannot be empty.")
        normalized_note = note.strip()
        if len(normalized_note) > MAX_COMPARISON_REVIEW_NOTE_CHARACTERS:
            raise ResearchError("Research comparison review note is too long.")
        if supersedes_review_id is not None and not isinstance(
            supersedes_review_id, str
        ):
            raise ResearchError("Superseded comparison review ID is invalid.")
        normalized_superseded = (supersedes_review_id or "").strip() or None
        with self._lock:
            index, run = self._find_with_index(normalized_run_id)
            target = next(
                (
                    value
                    for value in run.comparison_notes
                    if value.note_id == normalized_note_id
                ),
                None,
            )
            if target is None:
                raise ResearchError(
                    "Research comparison note was not found in this run."
                )
            current = current_comparison_review(run.comparison_reviews, target.note_id)
            if (current.review_id if current else None) != normalized_superseded:
                raise ResearchError(
                    "A comparison review must supersede exactly the current review "
                    "of its note."
                )
            self._require_collecting(run)
            now = self._now()
            review = ResearchComparisonReviewRecord(
                review_id=self._new_comparison_review_id(),
                note_id=target.note_id,
                evidence_ids=target.evidence_ids,
                decision=normalized_decision,
                note=normalized_note,
                recorded_at=now,
                supersedes_review_id=normalized_superseded,
            )
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=run.assessments,
                comparison_notes=run.comparison_notes,
                claims=run.claims,
                claim_contradictions=run.claim_contradictions,
                comparison_reviews=(*run.comparison_reviews, review),
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def _new_comparison_review_id(self) -> str:
        review_id = str(uuid4())
        if any(
            record.review_id == review_id
            for run in self._runs
            for record in run.comparison_reviews
        ):
            raise ResearchError("Research comparison review ID already exists.")
        return review_id

    def record_source_assessment(
        self,
        run_id: str,
        document_id: str,
        evidence_ids: Sequence[str],
        text: str,
        supersedes_assessment_id: str | None = None,
        information_trust: ResearchInformationTrust | str = (
            ResearchInformationTrust.UNASSESSED
        ),
        usefulness: ResearchSourceUsefulness | str = ResearchSourceUsefulness.UNKNOWN,
        applicability: ResearchSourceApplicability | str = (
            ResearchSourceApplicability.UNKNOWN
        ),
        independence: ResearchSourceIndependence | str = (
            ResearchSourceIndependence.UNKNOWN
        ),
        publication_status: ResearchSourcePublicationStatus | str = (
            ResearchSourcePublicationStatus.UNKNOWN
        ),
    ) -> ResearchRun:
        """Revalidate and atomically append one user-authored assessment."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_document_id = self._normalize_document_id(document_id)
        normalized_evidence_ids = self._normalize_assessment_evidence_ids(evidence_ids)
        normalized_text = self._normalize_assessment_text(text)
        normalized_superseded_id = self._normalize_optional_assessment_id(
            supersedes_assessment_id
        )
        normalized_information_trust = self._normalize_information_trust(
            information_trust
        )
        normalized_judgement = self._normalize_source_judgement(
            usefulness,
            applicability,
            independence,
            publication_status,
        )
        with self._lock:
            index, run = self._find_with_index(normalized_run_id)
            source, evidence = self._source_and_evidence_for_assessment(
                run,
                normalized_document_id,
                normalized_evidence_ids,
            )
            superseded_assessment = self._superseded_assessment_for_write(
                run,
                source.document_id,
                normalized_superseded_id,
            )
            if superseded_assessment is None:
                self._refuse_duplicate(
                    "assessment",
                    self._identical_assessment(
                        run,
                        source.document_id,
                        tuple(record.evidence_id for record in evidence),
                        normalized_text,
                        normalized_information_trust,
                        normalized_judgement,
                    ),
                )
            self._require_collecting(run)
            now = self._now()
            assessment = ResearchSourceAssessmentRecord(
                assessment_id=self._new_assessment_id(),
                source_document_id=source.document_id,
                evidence_ids=tuple(record.evidence_id for record in evidence),
                text=normalized_text,
                recorded_at=now,
                supersedes_assessment_id=(
                    None
                    if superseded_assessment is None
                    else superseded_assessment.assessment_id
                ),
                information_trust=normalized_information_trust,
                usefulness=normalized_judgement[0],
                applicability=normalized_judgement[1],
                independence=normalized_judgement[2],
                publication_status=normalized_judgement[3],
            )
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=(*run.assessments, assessment),
                comparison_notes=run.comparison_notes,
                claims=run.claims,
                claim_contradictions=run.claim_contradictions,
                comparison_reviews=run.comparison_reviews,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def preview_source_comparison_note_write(
        self,
        run_id: str,
        document_ids: Sequence[str],
        evidence_ids: Sequence[str],
        assessment_ids: Sequence[str],
        text: str,
    ) -> ResearchSourceComparisonNoteWritePreview:
        """Validate exact authored comparison references without mutation."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_document_ids = self._normalize_comparison_document_ids(document_ids)
        normalized_evidence_ids = self._normalize_comparison_note_evidence_ids(
            evidence_ids
        )
        normalized_assessment_ids = self._normalize_comparison_note_assessment_ids(
            assessment_ids
        )
        normalized_text = self._normalize_comparison_note_text(text)
        with self._lock:
            _, run = self._find_with_index(normalized_run_id)
            comparison = self.preview_source_comparison(
                normalized_run_id,
                normalized_document_ids,
            )
            evidence, assessments = self._comparison_note_references(
                run,
                normalized_document_ids,
                normalized_evidence_ids,
                normalized_assessment_ids,
            )
            duplicate = self._identical_comparison_note(
                run,
                normalized_document_ids,
                tuple(record.evidence_id for record in evidence),
                tuple(record.assessment_id for record in assessments),
                normalized_text,
            )
            allowed = not run.status.terminal and duplicate is None
            return ResearchSourceComparisonNoteWritePreview(
                comparison=comparison,
                evidence=evidence,
                assessments=assessments,
                text=normalized_text,
                allowed=allowed,
                reason=(
                    self._duplicate_reason("comparison note", duplicate)
                    if duplicate is not None
                    else (
                        "Research comparison note can be recorded after confirmation."
                        if allowed
                        else "A closed research run cannot accept comparison notes."
                    )
                ),
            )

    def record_source_comparison_note(
        self,
        run_id: str,
        document_ids: Sequence[str],
        evidence_ids: Sequence[str],
        assessment_ids: Sequence[str],
        text: str,
    ) -> ResearchRun:
        """Revalidate and atomically append one authored comparison note."""
        normalized_run_id = self._normalize_run_id(run_id)
        normalized_document_ids = self._normalize_comparison_document_ids(document_ids)
        normalized_evidence_ids = self._normalize_comparison_note_evidence_ids(
            evidence_ids
        )
        normalized_assessment_ids = self._normalize_comparison_note_assessment_ids(
            assessment_ids
        )
        normalized_text = self._normalize_comparison_note_text(text)
        with self._lock:
            index, run = self._find_with_index(normalized_run_id)
            self.preview_source_comparison(
                normalized_run_id,
                normalized_document_ids,
            )
            evidence, assessments = self._comparison_note_references(
                run,
                normalized_document_ids,
                normalized_evidence_ids,
                normalized_assessment_ids,
            )
            self._refuse_duplicate(
                "comparison note",
                self._identical_comparison_note(
                    run,
                    normalized_document_ids,
                    tuple(record.evidence_id for record in evidence),
                    tuple(record.assessment_id for record in assessments),
                    normalized_text,
                ),
            )
            self._require_collecting(run)
            now = self._now()
            note = ResearchSourceComparisonNoteRecord(
                note_id=self._new_comparison_note_id(),
                source_document_ids=normalized_document_ids,
                evidence_ids=tuple(record.evidence_id for record in evidence),
                assessment_ids=tuple(record.assessment_id for record in assessments),
                text=normalized_text,
                recorded_at=now,
            )
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=run.status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=run.assessments,
                comparison_notes=(*run.comparison_notes, note),
                claims=run.claims,
                claim_contradictions=run.claim_contradictions,
                comparison_reviews=run.comparison_reviews,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    def transition_status(
        self,
        run_id: str,
        target_status: ResearchRunStatus,
    ) -> ResearchRun:
        """Revalidate and atomically persist one terminal status transition."""
        normalized_id = self._normalize_run_id(run_id)
        if not isinstance(target_status, ResearchRunStatus):
            raise ResearchError("Research run target status is invalid.")
        with self._lock:
            index, run = self._find_with_index(normalized_id)
            preview = self._status_transition_preview(run, target_status)
            if not preview.allowed:
                raise ResearchError(preview.reason)
            now = self._now()
            updated = ResearchRun(
                run_id=run.run_id,
                question=run.question,
                status=target_status,
                sources=run.sources,
                failures=run.failures,
                created_at=run.created_at,
                updated_at=now,
                evidence=run.evidence,
                discoveries=run.discoveries,
                assessments=run.assessments,
                comparison_notes=run.comparison_notes,
                claims=run.claims,
                claim_contradictions=run.claim_contradictions,
                comparison_reviews=run.comparison_reviews,
            )
            candidate = list(self._runs)
            candidate[index] = updated
            candidate_tuple = tuple(candidate)
            self._persist(candidate_tuple)
            self._runs = candidate_tuple
        return updated

    @staticmethod
    def _status_transition_preview(
        run: ResearchRun,
        target_status: ResearchRunStatus,
    ) -> ResearchRunStatusTransitionPreview:
        if target_status is ResearchRunStatus.COLLECTING:
            return ResearchRunStatusTransitionPreview(
                run.run_id,
                run.status,
                target_status,
                False,
                "A research run can transition only to a terminal status.",
            )
        if run.status.terminal:
            return ResearchRunStatusTransitionPreview(
                run.run_id,
                run.status,
                target_status,
                False,
                "A closed research run cannot change status.",
            )
        if target_status is ResearchRunStatus.COMPLETED and not run.sources:
            return ResearchRunStatusTransitionPreview(
                run.run_id,
                run.status,
                target_status,
                False,
                "A completed research run requires at least one accepted source.",
            )
        if target_status is ResearchRunStatus.COMPLETED and not run.evidence:
            return ResearchRunStatusTransitionPreview(
                run.run_id,
                run.status,
                target_status,
                False,
                "A completed research run requires at least one evidence record.",
            )
        if target_status is ResearchRunStatus.FAILED and not run.failures:
            return ResearchRunStatusTransitionPreview(
                run.run_id,
                run.status,
                target_status,
                False,
                "A failed research run requires at least one failure record.",
            )
        return ResearchRunStatusTransitionPreview(
            run.run_id,
            run.status,
            target_status,
            True,
            f"Research run can be marked {target_status.value}.",
        )

    @staticmethod
    def _require_collecting(run: ResearchRun) -> None:
        if run.status.terminal:
            raise ResearchError("A closed research run cannot be changed.")

    def _find_with_index(self, run_id: str) -> tuple[int, ResearchRun]:
        for index, run in enumerate(self._runs):
            if run.run_id == run_id:
                return index, run
        raise ResearchError(f"Research run was not found: {run_id}")

    def _persist(self, runs: tuple[ResearchRun, ...]) -> None:
        if self._store is not None:
            self._store.save(list(runs))

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ResearchError("Research run clock must return a timezone-aware time.")
        return now

    def _new_run_id(self) -> str:
        run_id = self._normalize_run_id(self._id_factory())
        if any(run.run_id == run_id for run in self._runs):
            raise ResearchError("Research run ID already exists.")
        return run_id

    def _new_evidence_id(self) -> str:
        evidence_id = self._normalize_evidence_id(self._evidence_id_factory())
        if any(
            record.evidence_id == evidence_id
            for run in self._runs
            for record in run.evidence
        ):
            raise ResearchError("Research evidence ID already exists.")
        return evidence_id

    def _new_discovery_id(self) -> str:
        discovery_id = self._normalize_discovery_id(self._discovery_id_factory())
        if any(
            record.discovery_id == discovery_id
            for run in self._runs
            for record in run.discoveries
        ):
            raise ResearchError("Research source discovery ID already exists.")
        return discovery_id

    def _new_assessment_id(self) -> str:
        assessment_id = self._normalize_assessment_id(self._assessment_id_factory())
        if any(
            record.assessment_id == assessment_id
            for run in self._runs
            for record in run.assessments
        ):
            raise ResearchError("Research source assessment ID already exists.")
        return assessment_id

    def _new_comparison_note_id(self) -> str:
        note_id = self._normalize_comparison_note_id(self._comparison_note_id_factory())
        if any(
            record.note_id == note_id
            for run in self._runs
            for record in run.comparison_notes
        ):
            raise ResearchError("Research comparison note ID already exists.")
        return note_id

    def _new_claim_id(self) -> str:
        claim_id = self._normalize_claim_id(self._claim_id_factory())
        if any(
            record.claim_id == claim_id for run in self._runs for record in run.claims
        ):
            raise ResearchError("Research claim ID already exists.")
        return claim_id

    def _new_claim_contradiction_id(self) -> str:
        contradiction_id = self._normalize_claim_contradiction_id(
            self._claim_contradiction_id_factory()
        )
        if any(
            record.contradiction_id == contradiction_id
            for run in self._runs
            for record in run.claim_contradictions
        ):
            raise ResearchError("Research claim contradiction ID already exists.")
        return contradiction_id

    @staticmethod
    def _comparison_note_references(
        run: ResearchRun,
        document_ids: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        assessment_ids: tuple[str, ...],
    ) -> tuple[
        tuple[ResearchEvidenceRecord, ...],
        tuple[ResearchSourceAssessmentRecord, ...],
    ]:
        selected_source_ids = set(document_ids)
        evidence_by_id = {record.evidence_id: record for record in run.evidence}
        assessments_by_id = {record.assessment_id: record for record in run.assessments}
        try:
            evidence = tuple(
                evidence_by_id[evidence_id] for evidence_id in evidence_ids
            )
            assessments = tuple(
                assessments_by_id[assessment_id] for assessment_id in assessment_ids
            )
        except KeyError as error:
            raise ResearchError(
                "Research comparison note references were not found in this run."
            ) from error
        if {record.source_document_id for record in evidence} != selected_source_ids:
            raise ResearchError(
                "Research comparison note evidence must cover every selected source."
            )
        if {record.source_document_id for record in assessments} != selected_source_ids:
            raise ResearchError(
                "Research comparison note assessments must cover every selected source."
            )
        superseded_ids = {
            record.supersedes_assessment_id
            for record in run.assessments
            if record.supersedes_assessment_id is not None
        }
        if any(record.assessment_id in superseded_ids for record in assessments):
            raise ResearchError("Research comparison note assessments must be current.")
        selected_evidence_ids = set(evidence_ids)
        if any(
            not set(assessment.evidence_ids).issubset(selected_evidence_ids)
            for assessment in assessments
        ):
            raise ResearchError(
                "Research comparison note must cite each assessment's evidence."
            )
        return evidence, assessments

    @staticmethod
    def _source_and_evidence_for_assessment(
        run: ResearchRun,
        document_id: str,
        evidence_ids: tuple[str, ...],
    ) -> tuple[ResearchSourceRecord, tuple[ResearchEvidenceRecord, ...]]:
        source = next(
            (record for record in run.sources if record.document_id == document_id),
            None,
        )
        if source is None:
            raise ResearchError(
                "Research source was not found among this run's accepted sources."
            )
        evidence_by_id = {record.evidence_id: record for record in run.evidence}
        try:
            evidence = tuple(
                evidence_by_id[evidence_id] for evidence_id in evidence_ids
            )
        except KeyError as error:
            raise ResearchError(
                "Research assessment evidence was not found in this run."
            ) from error
        if any(record.source_document_id != source.document_id for record in evidence):
            raise ResearchError(
                "Research assessment evidence must belong to the selected source."
            )
        return source, evidence

    @staticmethod
    def _superseded_assessment_for_write(
        run: ResearchRun,
        document_id: str,
        supersedes_assessment_id: str | None,
    ) -> ResearchSourceAssessmentRecord | None:
        if supersedes_assessment_id is None:
            return None
        assessment = next(
            (
                record
                for record in run.assessments
                if record.assessment_id == supersedes_assessment_id
            ),
            None,
        )
        if assessment is None:
            raise ResearchError(
                "Superseded research assessment was not found in this run."
            )
        if assessment.source_document_id != document_id:
            raise ResearchError(
                "Superseded research assessment must belong to the selected source."
            )
        if any(
            record.supersedes_assessment_id == assessment.assessment_id
            for record in run.assessments
        ):
            raise ResearchError(
                "Research source assessment has already been superseded."
            )
        return assessment

    @staticmethod
    def _claim_sources_and_evidence(
        run: ResearchRun,
        evidence_ids: tuple[str, ...],
    ) -> tuple[
        tuple[ResearchSourceRecord, ...],
        tuple[ResearchEvidenceRecord, ...],
    ]:
        evidence_by_id = {record.evidence_id: record for record in run.evidence}
        try:
            evidence = tuple(
                evidence_by_id[evidence_id] for evidence_id in evidence_ids
            )
        except KeyError as error:
            raise ResearchError(
                "Research claim evidence was not found in this run."
            ) from error
        source_ids = tuple(
            dict.fromkeys(record.source_document_id for record in evidence)
        )
        sources_by_id = {record.document_id: record for record in run.sources}
        try:
            sources = tuple(sources_by_id[source_id] for source_id in source_ids)
        except KeyError as error:
            raise ResearchError(
                "Research claim evidence must belong to accepted sources."
            ) from error
        return sources, evidence

    @staticmethod
    def _claim_contradiction_references(
        run: ResearchRun,
        claim_ids: tuple[str, str],
    ) -> tuple[
        tuple[ResearchClaimRecord, ResearchClaimRecord],
        tuple[ResearchEvidenceRecord, ...],
    ]:
        claims_by_id = {record.claim_id: record for record in run.claims}
        try:
            claims = (claims_by_id[claim_ids[0]], claims_by_id[claim_ids[1]])
        except KeyError as error:
            raise ResearchError(
                "Research claim contradiction requires claims from this run."
            ) from error
        expected_evidence_ids = tuple(
            dict.fromkeys(
                evidence_id for claim in claims for evidence_id in claim.evidence_ids
            )
        )
        evidence_by_id = {record.evidence_id: record for record in run.evidence}
        try:
            evidence = tuple(
                evidence_by_id[evidence_id] for evidence_id in expected_evidence_ids
            )
        except KeyError as error:
            raise ResearchError(
                "Research claim contradiction evidence was not found in this run."
            ) from error
        return claims, evidence

    @staticmethod
    def _claim_contradiction_exists(
        run: ResearchRun,
        claim_ids: tuple[str, str],
    ) -> bool:
        selected_pair = frozenset(claim_ids)
        return any(
            frozenset(record.claim_ids) == selected_pair
            for record in run.claim_contradictions
        )

    @staticmethod
    def _superseded_claim_for_write(
        run: ResearchRun,
        supersedes_claim_id: str | None,
    ) -> ResearchClaimRecord | None:
        if supersedes_claim_id is None:
            return None
        claim = next(
            (record for record in run.claims if record.claim_id == supersedes_claim_id),
            None,
        )
        if claim is None:
            raise ResearchError("Superseded research claim was not found in this run.")
        if any(record.supersedes_claim_id == claim.claim_id for record in run.claims):
            raise ResearchError("Research claim has already been superseded.")
        return claim

    @staticmethod
    def _normalize_question(question: str) -> str:
        if not isinstance(question, str) or not question.strip():
            raise ResearchError("Research question cannot be empty.")
        normalized = question.strip()
        if len(normalized) > 2_000:
            raise ResearchError("Research question is too long.")
        return normalized

    @staticmethod
    def _duplicate_reason(label: str, record: object) -> str:
        identity = next(
            getattr(record, name)
            for name in ("evidence_id", "assessment_id", "claim_id", "note_id")
            if hasattr(record, name)
        )
        return (
            f"This exact {label} is already recorded as {identity} in this run; "
            "it was not recorded again."
        )

    @classmethod
    def _refuse_duplicate(cls, label: str, record: object | None) -> None:
        """Refuse an exact repeat of an existing first record, naming it.

        Recording one observation twice would count it twice, whether the
        repeat comes from a retried plan step or a re-confirmed manual entry.
        """
        if record is not None:
            raise ResearchError(cls._duplicate_reason(label, record))

    @staticmethod
    def _identical_evidence(
        run: ResearchRun, chunk: Chunk, note: str
    ) -> ResearchEvidenceRecord | None:
        chunk_sha256 = sha256(chunk.content.strip().encode("utf-8")).hexdigest()
        return next(
            (
                record
                for record in run.evidence
                if record.source_document_id == chunk.document_id
                and record.chunk_index == chunk.index
                and record.chunk_sha256 == chunk_sha256
                and record.note == note
            ),
            None,
        )

    @staticmethod
    def _identical_assessment(
        run: ResearchRun,
        document_id: str,
        evidence_ids: tuple[str, ...],
        text: str,
        information_trust: ResearchInformationTrust,
        judgement: tuple[
            ResearchSourceUsefulness,
            ResearchSourceApplicability,
            ResearchSourceIndependence,
            ResearchSourcePublicationStatus,
        ],
    ) -> ResearchSourceAssessmentRecord | None:
        return next(
            (
                record
                for record in run.assessments
                if record.supersedes_assessment_id is None
                and record.source_document_id == document_id
                and set(record.evidence_ids) == set(evidence_ids)
                and record.text == text
                and record.information_trust is information_trust
                and (
                    record.usefulness,
                    record.applicability,
                    record.independence,
                    record.publication_status,
                )
                == judgement
            ),
            None,
        )

    @staticmethod
    def _identical_claim(
        run: ResearchRun,
        evidence_ids: tuple[str, ...],
        text: str,
        epistemic_state: ResearchEpistemicState,
        confidence: ResearchClaimConfidence,
    ) -> ResearchClaimRecord | None:
        return next(
            (
                record
                for record in run.claims
                if record.supersedes_claim_id is None
                and set(record.evidence_ids) == set(evidence_ids)
                and record.text == text
                and record.epistemic_state is epistemic_state
                and record.confidence is confidence
            ),
            None,
        )

    @staticmethod
    def _identical_comparison_note(
        run: ResearchRun,
        document_ids: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        assessment_ids: tuple[str, ...],
        text: str,
    ) -> ResearchSourceComparisonNoteRecord | None:
        return next(
            (
                record
                for record in run.comparison_notes
                if set(record.source_document_ids) == set(document_ids)
                and set(record.evidence_ids) == set(evidence_ids)
                and set(record.assessment_ids) == set(assessment_ids)
                and record.text == text
            ),
            None,
        )

    @staticmethod
    def _normalize_run_id(run_id: str) -> str:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ResearchError("Research run ID cannot be empty.")
        return run_id.strip()

    @staticmethod
    def _markdown_export_filename(run_id: str) -> str:
        safe_run_id = re.sub(r"[^A-Za-z0-9._-]+", "-", run_id).strip("-.")
        if not safe_run_id:
            safe_run_id = "research"
        return f"hypatia-research-{safe_run_id[:80]}.md"

    @staticmethod
    def _normalize_markdown_export_destination(destination_path: str | Path) -> Path:
        if not isinstance(destination_path, (str, Path)):
            raise ResearchError("Research export destination is invalid.")
        raw_destination = str(destination_path).strip()
        if (
            not raw_destination
            or len(raw_destination) > 4_096
            or "\x00" in raw_destination
        ):
            raise ResearchError("Research export destination is invalid.")
        destination = Path(raw_destination)
        if not destination.is_absolute():
            raise ResearchError("Research export destination must be absolute.")
        if destination.suffix.casefold() != ".md":
            raise ResearchError("Research export destination must end with .md.")
        parent = destination.parent
        try:
            parent_exists = parent.is_dir()
        except OSError as error:
            raise ResearchError("Research export destination is invalid.") from error
        if not parent_exists:
            raise ResearchError("Research export destination directory was not found.")
        return destination

    @staticmethod
    def _normalize_markdown_export_source(source_path: str | Path) -> Path:
        if not isinstance(source_path, (str, Path)):
            raise ResearchError("Research export verification source is invalid.")
        raw_source = str(source_path).strip()
        if not raw_source or len(raw_source) > 4_096 or "\x00" in raw_source:
            raise ResearchError("Research export verification source is invalid.")
        source = Path(raw_source)
        if not source.is_absolute():
            raise ResearchError("Research export verification source must be absolute.")
        if source.suffix.casefold() != ".md":
            raise ResearchError(
                "Research export verification source must end with .md."
            )
        return source

    @staticmethod
    def _hash_stable_export_file(
        source: Path,
        *,
        max_bytes: int,
    ) -> tuple[str, int]:
        """Hash one regular descriptor and reject replacement or mid-read changes."""
        try:
            with source.open("rb") as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise ResearchError(
                        "Research export verification source must be a regular file."
                    )
                if before.st_size > max_bytes:
                    raise ResearchError(
                        "Research export verification source is too large."
                    )
                digest = sha256()
                byte_count = 0
                while chunk := stream.read(64 * 1024):
                    byte_count += len(chunk)
                    if byte_count > max_bytes:
                        raise ResearchError(
                            "Research export verification source is too large."
                        )
                    digest.update(chunk)
                after = os.fstat(stream.fileno())
                current = source.stat()
        except ResearchError:
            raise
        except OSError as error:
            raise ResearchError(
                "Research export verification source could not be read."
            ) from error
        stable_metadata = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        if stable_metadata != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) or (after.st_dev, after.st_ino) != (current.st_dev, current.st_ino):
            raise ResearchError(
                "Research export verification source changed while it was read."
            )
        if byte_count != before.st_size:
            raise ResearchError(
                "Research export verification source changed while it was read."
            )
        return digest.hexdigest(), byte_count

    @staticmethod
    def _normalize_export_snapshot_time(value: datetime) -> datetime:
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError("Research export snapshot time must be timezone-aware.")
        return value

    @staticmethod
    def _normalize_export_sha256(value: str) -> str:
        if not isinstance(value, str):
            raise ResearchError("Research export fingerprint is invalid.")
        normalized = value.strip().casefold()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ResearchError("Research export fingerprint is invalid.")
        return normalized

    @staticmethod
    def _publish_new_export(destination: Path, content: bytes) -> None:
        """Publish complete bytes atomically without replacing an existing path."""
        publish_new_export_file(destination, content)

    @staticmethod
    def _normalize_document_id(document_id: str) -> str:
        if not isinstance(document_id, str) or not document_id.strip():
            raise ResearchError("Research source document ID cannot be empty.")
        return document_id.strip()

    @staticmethod
    def _normalize_comparison_document_ids(
        document_ids: Sequence[str],
    ) -> tuple[str, ...]:
        if isinstance(document_ids, (str, bytes)) or not isinstance(
            document_ids, Sequence
        ):
            raise ResearchError("Research comparison source IDs must be a list.")
        normalized = tuple(
            ResearchRunManager._normalize_document_id(value) for value in document_ids
        )
        if not MIN_COMPARISON_SOURCES <= len(normalized) <= MAX_COMPARISON_SOURCES:
            raise ResearchError("Research source comparison requires 2 to 5 sources.")
        if len(normalized) != len(set(normalized)):
            raise ResearchError(
                "Research source comparison contains duplicate sources."
            )
        return normalized

    @staticmethod
    def _normalize_evidence_id(evidence_id: str) -> str:
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise ResearchError("Research evidence ID cannot be empty.")
        return evidence_id.strip()

    @staticmethod
    def _normalize_evidence_note(note: str) -> str:
        if not isinstance(note, str) or not note.strip():
            raise ResearchError("Research evidence note cannot be empty.")
        normalized = note.strip()
        if len(normalized) > 1_000:
            raise ResearchError("Research evidence note is too long.")
        return normalized

    @staticmethod
    def _normalize_claim_id(claim_id: str) -> str:
        if not isinstance(claim_id, str) or not claim_id.strip():
            raise ResearchError("Research claim ID cannot be empty.")
        normalized = claim_id.strip()
        if len(normalized) > 200:
            raise ResearchError("Research claim ID is too long.")
        return normalized

    @staticmethod
    def _normalize_claim_contradiction_id(contradiction_id: str) -> str:
        if not isinstance(contradiction_id, str) or not contradiction_id.strip():
            raise ResearchError("Research claim contradiction ID cannot be empty.")
        normalized = contradiction_id.strip()
        if len(normalized) > 200:
            raise ResearchError("Research claim contradiction ID is too long.")
        return normalized

    @staticmethod
    def _normalize_claim_contradiction_claim_ids(
        claim_ids: Sequence[str],
    ) -> tuple[str, str]:
        if isinstance(claim_ids, (str, bytes)) or not isinstance(
            claim_ids,
            Sequence,
        ):
            raise ResearchError("Research claim contradiction IDs must be a list.")
        normalized = tuple(
            ResearchRunManager._normalize_claim_id(value) for value in claim_ids
        )
        if len(normalized) != 2:
            raise ResearchError(
                "Research claim contradiction requires exactly two claim IDs."
            )
        if normalized[0] == normalized[1]:
            raise ResearchError(
                "Research claim contradiction requires two distinct claims."
            )
        return normalized[0], normalized[1]

    @staticmethod
    def _normalize_claim_contradiction_note(note: str) -> str:
        if not isinstance(note, str) or not note.strip():
            raise ResearchError("Research claim contradiction note cannot be empty.")
        normalized = note.strip()
        if len(normalized) > MAX_CLAIM_CONTRADICTION_NOTE_CHARACTERS:
            raise ResearchError("Research claim contradiction note is too long.")
        return normalized

    @staticmethod
    def _normalize_optional_claim_id(claim_id: str | None) -> str | None:
        if claim_id is None:
            return None
        return ResearchRunManager._normalize_claim_id(claim_id)

    @staticmethod
    def _normalize_claim_evidence_ids(
        evidence_ids: Sequence[str],
    ) -> tuple[str, ...]:
        if isinstance(evidence_ids, (str, bytes)) or not isinstance(
            evidence_ids,
            Sequence,
        ):
            raise ResearchError("Research claim evidence IDs must be a list.")
        normalized = tuple(
            ResearchRunManager._normalize_evidence_id(value) for value in evidence_ids
        )
        if not normalized:
            raise ResearchError("Research claim requires explicit evidence IDs.")
        if len(normalized) != len(set(normalized)):
            raise ResearchError("Research claim contains duplicate evidence IDs.")
        if len(normalized) > MAX_RESEARCH_CLAIM_EVIDENCE:
            raise ResearchError("Research claim cites too many evidence records.")
        return normalized

    @staticmethod
    def _normalize_claim_text(text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            raise ResearchError("Research claim text cannot be empty.")
        normalized = text.strip()
        if len(normalized) > MAX_RESEARCH_CLAIM_CHARACTERS:
            raise ResearchError("Research claim text is too long.")
        return normalized

    @staticmethod
    def _normalize_epistemic_state(
        value: ResearchEpistemicState | str,
    ) -> ResearchEpistemicState:
        try:
            return ResearchEpistemicState(value)
        except (TypeError, ValueError) as error:
            raise ResearchError("Research claim epistemic state is invalid.") from error

    @staticmethod
    def _normalize_claim_confidence(
        value: ResearchClaimConfidence | str,
    ) -> ResearchClaimConfidence:
        try:
            return ResearchClaimConfidence(value)
        except (TypeError, ValueError) as error:
            raise ResearchError("Research claim confidence is invalid.") from error

    @staticmethod
    def _normalize_assessment_id(assessment_id: str) -> str:
        if not isinstance(assessment_id, str) or not assessment_id.strip():
            raise ResearchError("Research source assessment ID cannot be empty.")
        normalized = assessment_id.strip()
        if len(normalized) > 200:
            raise ResearchError("Research source assessment ID is too long.")
        return normalized

    @staticmethod
    def _normalize_optional_assessment_id(
        assessment_id: str | None,
    ) -> str | None:
        if assessment_id is None:
            return None
        return ResearchRunManager._normalize_assessment_id(assessment_id)

    @staticmethod
    def _normalize_source_judgement(
        usefulness: ResearchSourceUsefulness | str,
        applicability: ResearchSourceApplicability | str,
        independence: ResearchSourceIndependence | str,
        publication_status: ResearchSourcePublicationStatus | str,
    ) -> tuple[
        ResearchSourceUsefulness,
        ResearchSourceApplicability,
        ResearchSourceIndependence,
        ResearchSourcePublicationStatus,
    ]:
        """Return the four structured judgements, refusing anything unlisted.

        An unrecognised value is refused rather than folded into `unknown`. A
        typo that silently became `unknown` would read as an appraisal somebody
        declined to make, when in fact one was made and lost.
        """
        try:
            return (
                ResearchSourceUsefulness(usefulness),
                ResearchSourceApplicability(applicability),
                ResearchSourceIndependence(independence),
                ResearchSourcePublicationStatus(publication_status),
            )
        except (TypeError, ValueError) as error:
            raise ResearchError("Research source judgement is invalid.") from error

    @staticmethod
    def _normalize_information_trust(
        value: ResearchInformationTrust | str,
    ) -> ResearchInformationTrust:
        try:
            return ResearchInformationTrust(value)
        except (TypeError, ValueError) as error:
            raise ResearchError(
                "Research source information trust is invalid."
            ) from error

    @staticmethod
    def _normalize_assessment_evidence_ids(
        evidence_ids: Sequence[str],
    ) -> tuple[str, ...]:
        if isinstance(evidence_ids, (str, bytes)) or not isinstance(
            evidence_ids, Sequence
        ):
            raise ResearchError("Research assessment evidence IDs must be a list.")
        normalized = tuple(
            ResearchRunManager._normalize_evidence_id(value) for value in evidence_ids
        )
        if not normalized:
            raise ResearchError(
                "Research source assessment requires explicit evidence IDs."
            )
        if len(normalized) != len(set(normalized)):
            raise ResearchError(
                "Research source assessment contains duplicate evidence IDs."
            )
        if len(normalized) > 20:
            raise ResearchError(
                "Research source assessment cannot cite more than 20 evidence records."
            )
        return normalized

    @staticmethod
    def _normalize_assessment_text(text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            raise ResearchError("Research source assessment text cannot be empty.")
        normalized = text.strip()
        if len(normalized) > MAX_SOURCE_ASSESSMENT_CHARACTERS:
            raise ResearchError("Research source assessment text is too long.")
        return normalized

    @staticmethod
    def _normalize_comparison_note_id(note_id: str) -> str:
        if not isinstance(note_id, str) or not note_id.strip():
            raise ResearchError("Research comparison note ID cannot be empty.")
        normalized = note_id.strip()
        if len(normalized) > 200:
            raise ResearchError("Research comparison note ID is too long.")
        return normalized

    @staticmethod
    def _normalize_comparison_note_evidence_ids(
        evidence_ids: Sequence[str],
    ) -> tuple[str, ...]:
        if isinstance(evidence_ids, (str, bytes)) or not isinstance(
            evidence_ids, Sequence
        ):
            raise ResearchError("Research comparison note evidence IDs must be a list.")
        normalized = tuple(
            ResearchRunManager._normalize_evidence_id(value) for value in evidence_ids
        )
        if not normalized:
            raise ResearchError(
                "Research comparison note requires explicit evidence IDs."
            )
        if len(normalized) != len(set(normalized)):
            raise ResearchError(
                "Research comparison note contains duplicate evidence IDs."
            )
        if len(normalized) > MAX_COMPARISON_NOTE_EVIDENCE:
            raise ResearchError(
                "Research comparison note cites too many evidence records."
            )
        return normalized

    @staticmethod
    def _normalize_comparison_note_assessment_ids(
        assessment_ids: Sequence[str],
    ) -> tuple[str, ...]:
        if isinstance(assessment_ids, (str, bytes)) or not isinstance(
            assessment_ids, Sequence
        ):
            raise ResearchError(
                "Research comparison note assessment IDs must be a list."
            )
        normalized = tuple(
            ResearchRunManager._normalize_assessment_id(value)
            for value in assessment_ids
        )
        if not normalized:
            raise ResearchError(
                "Research comparison note requires current assessment IDs."
            )
        if len(normalized) != len(set(normalized)):
            raise ResearchError(
                "Research comparison note contains duplicate assessment IDs."
            )
        if len(normalized) > MAX_COMPARISON_NOTE_ASSESSMENTS:
            raise ResearchError("Research comparison note cites too many assessments.")
        return normalized

    @staticmethod
    def _normalize_comparison_note_text(text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            raise ResearchError("Research comparison note text cannot be empty.")
        normalized = text.strip()
        if len(normalized) > MAX_COMPARISON_NOTE_CHARACTERS:
            raise ResearchError("Research comparison note text is too long.")
        return normalized

    @staticmethod
    def _normalize_discovery_id(discovery_id: str) -> str:
        if not isinstance(discovery_id, str) or not discovery_id.strip():
            raise ResearchError("Research source discovery ID cannot be empty.")
        normalized = discovery_id.strip()
        if len(normalized) > 200:
            raise ResearchError("Research source discovery ID is too long.")
        return normalized

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        if not isinstance(provider, str) or not provider.strip():
            raise ResearchError("Research source discovery provider cannot be empty.")
        normalized = provider.strip()
        if len(normalized) > 200:
            raise ResearchError("Research source discovery provider is too long.")
        if any(character in normalized for character in ("\r", "\n", "\t")):
            raise ResearchError("Research source discovery provider is invalid.")
        return normalized

    @staticmethod
    def _normalize_candidate_url(candidate_url: str) -> str:
        if not isinstance(candidate_url, str) or not candidate_url.strip():
            raise ResearchError("Research source candidate URL cannot be empty.")
        return candidate_url.strip()


def _acceptance_disclosure(candidate: ResearchSourceCandidate) -> str:
    """Say what loading this candidate will actually do, before it is confirmed.

    A vulnerability candidate is named by a page that does not contain it, and
    its record is read from the API instead. Telling an operator that Hypatia
    will load the page they can see would describe something that never happens
    and, worse, would misdescribe where the content they end up citing came
    from. The confirmation is only meaningful if it names the real operation.
    """
    if candidate.vulnerability is not None:
        return (
            "Research source candidate can be loaded and attached to this run. "
            "Its record will be retrieved from the NVD CVE API 2.0 — the "
            "linked page is an application shell and is not read — and the "
            "references it lists will be stored as text without being fetched."
        )
    return "Research source candidate can be loaded and attached to this run."
