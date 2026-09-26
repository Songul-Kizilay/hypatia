"""Brain-facing boundary for operator-authored Bug Bounty security findings.

This service performs no active validation, no fetch, no process, and no
model call. It only promotes an operator-judged-ready security hypothesis
into a finding, records the HTTP evidence citations that support, contradict,
or validate it, and the operator's own status judgements about it —
reasoning over already-recorded evidence, never a new observation of the
world. Scope resolution is always a fresh, read-only call into the unchanged
`ResearchTargetScope.resolve_hostname`/`resolve_addresses` against a
caller-supplied *currently active* `ResearchProgramScopeRevision`; it is
never cached, never persisted, and plays no part in creating, attaching
evidence to, or transitioning a finding. A finding, an evidence citation, or
a status value is never by itself sufficient grounds for any authorization
or execution decision, and no status value this module can produce ever
asserts a confirmed vulnerability
(`ResearchSecurityFindingStatus.means_confirmed_vulnerability` is `False`
for every member, including `VALIDATED`).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from cognition.ResearchAssetInventoryApplicationService import (
    ActiveProgramScopeRevisionReader,
)
from core.Exceptions import ResearchError
from research.JsonFileResearchHttpEvidenceStore import ResearchHttpEvidenceDocument
from research.JsonFileResearchSecurityFindingStore import (
    ResearchSecurityFindingDocument,
)
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchHttpEvidenceRecord import ResearchHttpEvidenceRecord
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from research.ResearchSecurityFinding import ResearchSecurityFinding
from research.ResearchSecurityFinding import (
    findings_for_program as _derive_findings_for_program,
)
from research.ResearchSecurityFindingEntry import ResearchSecurityFindingEntry
from research.ResearchSecurityFindingEvidenceKind import (
    ResearchSecurityFindingEvidenceKind,
)
from research.ResearchSecurityFindingEvidenceLinkRecord import (
    ResearchSecurityFindingEvidenceLinkRecord,
)
from research.ResearchSecurityFindingEvidenceRelation import (
    ResearchSecurityFindingEvidenceRelation,
)
from research.ResearchSecurityFindingOrigin import ResearchSecurityFindingOrigin
from research.ResearchSecurityFindingRecord import ResearchSecurityFindingRecord
from research.ResearchSecurityFindingStatus import (
    ResearchSecurityFindingStatus,
    is_valid_status_transition,
)
from research.ResearchSecurityFindingStatusTransitionRecord import (
    ResearchSecurityFindingStatusTransitionRecord,
)
from research.ResearchSecurityHypothesis import ResearchSecurityHypothesis
from research.ResearchSecurityHypothesisEvidenceLinkRecord import (
    ResearchSecurityHypothesisEvidenceLinkRecord,
)
from research.ResearchSecurityHypothesisEvidenceRelation import (
    ResearchSecurityHypothesisEvidenceRelation,
)
from research.ResearchSecurityHypothesisStatus import ResearchSecurityHypothesisStatus
from response.ResponseComposer import ResponseComposer

RESEARCH_SECURITY_FINDING_CREATE_INTENT = "research_security_finding_create"
RESEARCH_SECURITY_FINDING_EVIDENCE_ATTACH_INTENT = (
    "research_security_finding_evidence_attach"
)
RESEARCH_SECURITY_FINDING_STATUS_TRANSITION_INTENT = (
    "research_security_finding_status_transition"
)
RESEARCH_SECURITY_FINDING_PREVIEW_INTENT = "research_security_finding_preview"

MAX_SECURITY_FINDING_PROGRAM_ID_CHARACTERS = 200


class ResearchSecurityFindingStore(Protocol):
    def load(self) -> ResearchSecurityFindingDocument: ...

    def save(self, document: ResearchSecurityFindingDocument) -> None: ...


class ResearchHttpEvidenceReader(Protocol):
    def load(self) -> ResearchHttpEvidenceDocument: ...


class SecurityHypothesisReader(Protocol):
    """The one hypothesis-side lookup this service needs, satisfied structurally.

    `ResearchSecurityHypothesisApplicationService` already exposes exactly
    this method signature, so it satisfies this Protocol with no import
    cycle and no modification to that file.
    """

    def hypothesis_by_id(
        self, hypothesis_id: str, program_id: str
    ) -> ResearchSecurityHypothesis | None: ...


class ResearchSecurityFindingApplicationService:
    """Record operator-authored security findings promoted from hypotheses."""

    def __init__(
        self,
        store: ResearchSecurityFindingStore,
        http_evidence_reader: ResearchHttpEvidenceReader,
        security_hypothesis_reader: SecurityHypothesisReader,
        response_composer: ResponseComposer,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        program_scope_revision_store: ActiveProgramScopeRevisionReader | None = None,
    ) -> None:
        self._store = store
        self._http_evidence_reader = http_evidence_reader
        self._security_hypothesis_reader = security_hypothesis_reader
        self._response_composer = response_composer
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._program_scope_revision_store = program_scope_revision_store

    # -- durable writes ----------------------------------------------------

    def create_finding(
        self,
        program_id: str,
        source_hypothesis_id: str,
        title: str,
        description: str,
        required_followup: str,
    ) -> ResearchSecurityFindingRecord:
        """Promote a `READY_FOR_VALIDATION` hypothesis into one new finding.

        Looks up the source hypothesis via the injected reader for this exact
        `program_id`; fails closed if it is not found there. Requires the
        hypothesis's current (derived) status to be exactly
        `READY_FOR_VALIDATION` — this rejects `OPEN`, `NEEDS_EVIDENCE`, and
        `REFUTED` hypotheses equally, since none of them is
        `READY_FOR_VALIDATION`. Copies `finding_kind`/`subject_kind`/
        `subject_canonical_value` directly from the hypothesis — never
        accepted as separate caller-supplied arguments that could diverge.
        Refuses a second finding for the same `source_hypothesis_id` (dedup).
        Carries the hypothesis's current supporting and contradicting
        evidence forward as the finding's own initial evidence links, in the
        same document write as the founding record.
        """
        normalized_program_id = self._normalize_program_id(program_id)
        normalized_source_hypothesis_id = self._normalize_finding_id(
            source_hypothesis_id, "Security finding source hypothesis ID"
        )
        hypothesis = self._security_hypothesis_reader.hypothesis_by_id(
            normalized_source_hypothesis_id, normalized_program_id
        )
        if hypothesis is None:
            raise ResearchError(
                "Security finding source hypothesis was not found for this program."
            )
        ready_status = ResearchSecurityHypothesisStatus.READY_FOR_VALIDATION
        if hypothesis.status is not ready_status:
            raise ResearchError(
                "Security finding can only be created from a hypothesis that is"
                " ready for validation."
            )
        document = self._load()
        if any(
            existing.source_hypothesis_id == normalized_source_hypothesis_id
            and existing.program_id == normalized_program_id
            for existing in document.findings
        ):
            raise ResearchError(
                "A security finding already exists for this hypothesis; attach"
                " evidence or transition the existing finding instead of"
                " creating a near-duplicate."
            )
        now = self._now()
        record = ResearchSecurityFindingRecord(
            finding_id=self._new_id(),
            program_id=normalized_program_id,
            source_hypothesis_id=normalized_source_hypothesis_id,
            finding_kind=hypothesis.hypothesis_kind,
            subject_kind=hypothesis.subject_kind,
            subject_canonical_value=hypothesis.subject_canonical_value,
            title=title,
            description=description,
            required_followup=required_followup,
            origin=ResearchSecurityFindingOrigin.OPERATOR_AUTHORED,
            created_at=now,
        )
        if any(
            existing.finding_id == record.finding_id for existing in document.findings
        ):
            raise ResearchError("Security finding identity already exists.")
        carried_links = tuple(
            ResearchSecurityFindingEvidenceLinkRecord(
                link_id=self._new_id(),
                finding_id=record.finding_id,
                program_id=normalized_program_id,
                evidence_kind=ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE,
                evidence_id=link.evidence_id,
                relation=self._carried_relation(link),
                recorded_at=now,
            )
            for link in (
                *hypothesis.supporting_evidence,
                *hypothesis.contradicting_evidence,
            )
        )
        self._save(
            ResearchSecurityFindingDocument(
                findings=(*document.findings, record),
                evidence_links=(*document.evidence_links, *carried_links),
                status_transitions=document.status_transitions,
            )
        )
        return record

    def attach_evidence(
        self,
        finding_id: str,
        program_id: str,
        evidence_ids: tuple[str, ...],
        relation: ResearchSecurityFindingEvidenceRelation,
    ) -> tuple[ResearchSecurityFindingEvidenceLinkRecord, ...]:
        """Append supporting, contradicting, or validating evidence links.

        The finding must already exist for this exact `program_id`, and every
        cited evidence ID must exist for that same program — fail closed on a
        cross-program reference or an unknown finding/evidence ID. Always
        allowed regardless of current status (append-only audit trail).
        """
        normalized_program_id = self._normalize_program_id(program_id)
        normalized_finding_id = self._normalize_finding_id(
            finding_id, "Security finding ID"
        )
        if not isinstance(relation, ResearchSecurityFindingEvidenceRelation):
            raise ResearchError("Security finding evidence relation is invalid.")
        if not isinstance(evidence_ids, tuple) or not evidence_ids:
            raise ResearchError(
                "Security finding evidence attachment requires at least one"
                " evidence ID."
            )
        document = self._load()
        if not any(
            existing.finding_id == normalized_finding_id
            and existing.program_id == normalized_program_id
            for existing in document.findings
        ):
            raise ResearchError("Security finding was not found for this program.")
        evidence_by_id = self._evidence_for_program(normalized_program_id)
        missing = tuple(
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in evidence_by_id
        )
        if missing:
            raise ResearchError(
                "Security finding cites HTTP evidence that is not recorded for"
                " this program."
            )
        now = self._now()
        links = tuple(
            ResearchSecurityFindingEvidenceLinkRecord(
                link_id=self._new_id(),
                finding_id=normalized_finding_id,
                program_id=normalized_program_id,
                evidence_kind=ResearchSecurityFindingEvidenceKind.HTTP_EVIDENCE,
                evidence_id=evidence_id,
                relation=relation,
                recorded_at=now,
            )
            for evidence_id in evidence_ids
        )
        self._save(
            ResearchSecurityFindingDocument(
                findings=document.findings,
                evidence_links=(*document.evidence_links, *links),
                status_transitions=document.status_transitions,
            )
        )
        return links

    def transition_status(
        self,
        finding_id: str,
        program_id: str,
        new_status: ResearchSecurityFindingStatus,
        reason: str = "",
        duplicate_of_finding_id: str | None = None,
        superseded_by_finding_id: str | None = None,
    ) -> ResearchSecurityFindingStatusTransitionRecord:
        """Append one status transition after validating the closed state machine.

        A transition to `VALIDATED` additionally requires at least one
        `VALIDATES`-relation evidence link and refuses if any
        `CONTRADICTS`-relation evidence link currently exists. A transition
        to `DUPLICATE` requires `duplicate_of_finding_id` to name a
        different, existing, same-program finding, and
        `superseded_by_finding_id` must be `None`; `SUPERSEDED` is the mirror
        image. Every other status requires both linkage fields to be `None`.
        """
        normalized_program_id = self._normalize_program_id(program_id)
        normalized_finding_id = self._normalize_finding_id(
            finding_id, "Security finding ID"
        )
        if not isinstance(new_status, ResearchSecurityFindingStatus):
            raise ResearchError("Security finding status is invalid.")
        document = self._load()
        if not any(
            existing.finding_id == normalized_finding_id
            and existing.program_id == normalized_program_id
            for existing in document.findings
        ):
            raise ResearchError("Security finding was not found for this program.")
        current_status = self._current_status(
            document, normalized_finding_id, normalized_program_id
        )
        if not is_valid_status_transition(current_status, new_status):
            raise ResearchError(
                "Security finding cannot move from "
                f"{current_status.value} to {new_status.value}."
            )
        if new_status is ResearchSecurityFindingStatus.VALIDATED:
            self._require_validation_gate(
                document, normalized_finding_id, normalized_program_id
            )
        normalized_duplicate, normalized_superseded = self._require_linkage(
            document,
            normalized_program_id,
            normalized_finding_id,
            new_status,
            duplicate_of_finding_id,
            superseded_by_finding_id,
        )
        transition = ResearchSecurityFindingStatusTransitionRecord(
            transition_id=self._new_id(),
            finding_id=normalized_finding_id,
            program_id=normalized_program_id,
            status=new_status,
            reason=reason,
            duplicate_of_finding_id=normalized_duplicate,
            superseded_by_finding_id=normalized_superseded,
            recorded_at=self._now(),
        )
        self._save(
            ResearchSecurityFindingDocument(
                findings=document.findings,
                evidence_links=document.evidence_links,
                status_transitions=(*document.status_transitions, transition),
            )
        )
        return transition

    # -- derived read models -------------------------------------------------

    def findings_for_program(
        self, program_id: str
    ) -> tuple[ResearchSecurityFinding, ...]:
        """Recompute this program's findings fresh from the persisted logs."""
        normalized = self._normalize_program_id(program_id)
        document = self._load()
        return _derive_findings_for_program(
            normalized,
            document.findings,
            document.evidence_links,
            document.status_transitions,
        )

    def finding_by_id(
        self, finding_id: str, program_id: str
    ) -> ResearchSecurityFinding | None:
        """Return one program's finding by ID, or `None` if not found.

        Fails closed on a wrong `program_id` by construction: the derived
        listing is already scoped to `program_id`, so a finding recorded
        under a different program can never be returned here.
        """
        normalized_finding_id = self._normalize_finding_id(
            finding_id, "Security finding ID"
        )
        for finding in self.findings_for_program(program_id):
            if finding.finding_id == normalized_finding_id:
                return finding
        return None

    @staticmethod
    def current_scope_resolution(
        finding: ResearchSecurityFinding,
        active_revision: ResearchProgramScopeRevision | None,
    ) -> ResearchAssetScopeResolutionView:
        """Dispatch to the unchanged live resolver; never persisted, never cached.

        Identical shape to
        `ResearchSecurityHypothesisApplicationService.current_scope_resolution`,
        reusing `ResearchAssetScopeResolutionView` unchanged.
        """
        if not isinstance(finding, ResearchSecurityFinding):
            raise ResearchError(
                "Security finding scope resolution requires a valid finding."
            )
        if active_revision is None:
            return ResearchAssetScopeResolutionView(
                has_active_scope_revision=False, resolution=None
            )
        if not isinstance(active_revision, ResearchProgramScopeRevision):
            raise ResearchError(
                "Security finding scope resolution requires a valid scope" " revision."
            )
        if active_revision.program_id != finding.program_id:
            raise ResearchError(
                "Security finding scope resolution requires a revision for the"
                " same program."
            )
        if finding.subject_kind is ResearchAssetKind.HOSTNAME:
            resolution = active_revision.scope.resolve_hostname(
                finding.subject_canonical_value
            )
        elif finding.subject_kind is ResearchAssetKind.IP_ADDRESS:
            # Named explicitly rather than as an `else`, so a future subject
            # kind fails closed here instead of silently inheriting address
            # rules.
            (resolution,) = active_revision.scope.resolve_addresses(
                (finding.subject_canonical_value,)
            )
        else:
            raise ResearchError(
                "Security finding subject kind is not resolvable against scope."
            )
        return ResearchAssetScopeResolutionView(
            has_active_scope_revision=True, resolution=resolution
        )

    # -- Brain intents -------------------------------------------------------

    @staticmethod
    def is_finding_create_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_SECURITY_FINDING_CREATE_INTENT

    @staticmethod
    def is_evidence_attach_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent")
            == RESEARCH_SECURITY_FINDING_EVIDENCE_ATTACH_INTENT
        )

    @staticmethod
    def is_status_transition_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent")
            == RESEARCH_SECURITY_FINDING_STATUS_TRANSITION_INTENT
        )

    @staticmethod
    def is_finding_preview_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent") == RESEARCH_SECURITY_FINDING_PREVIEW_INTENT
        )

    def process_finding_create(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            source_hypothesis_id = request.metadata.get("source_hypothesis_id")
            title = request.metadata.get("title")
            description = request.metadata.get("description")
            required_followup = request.metadata.get("required_followup")
            if not isinstance(program_id, str):
                raise ResearchError("Security finding requires a program ID.")
            if not isinstance(source_hypothesis_id, str):
                raise ResearchError("Security finding requires a source hypothesis ID.")
            if not isinstance(title, str):
                raise ResearchError("Security finding title is invalid.")
            if not isinstance(description, str):
                raise ResearchError("Security finding description is invalid.")
            if not isinstance(required_followup, str):
                raise ResearchError("Security finding required followup is invalid.")
            record = self.create_finding(
                program_id,
                source_hypothesis_id,
                title,
                description,
                required_followup,
            )
            finding = self.finding_by_id(record.finding_id, record.program_id)
            if finding is None:
                raise ResearchError("Security finding could not be re-derived.")
        except ResearchError as error:
            return self._response_composer.research_security_finding_create_failure(
                request, str(error)
            )
        return self._response_composer.research_security_finding_create(
            request, finding
        )

    def process_evidence_attach(self, request: BrainRequest) -> BrainResponse:
        try:
            finding_id = request.metadata.get("finding_id")
            program_id = request.metadata.get("program_id")
            evidence_ids = request.metadata.get("evidence_ids", ())
            relation = request.metadata.get("relation")
            if not isinstance(finding_id, str):
                raise ResearchError(
                    "Security finding evidence attachment requires a finding ID."
                )
            if not isinstance(program_id, str):
                raise ResearchError(
                    "Security finding evidence attachment requires a program ID."
                )
            if not isinstance(evidence_ids, tuple) or any(
                not isinstance(value, str) for value in evidence_ids
            ):
                raise ResearchError("Security finding evidence references are invalid.")
            if not isinstance(relation, ResearchSecurityFindingEvidenceRelation):
                raise ResearchError("Security finding evidence relation is invalid.")
            self.attach_evidence(finding_id, program_id, evidence_ids, relation)
            finding = self.finding_by_id(finding_id, program_id)
            if finding is None:
                raise ResearchError("Security finding could not be re-derived.")
        except ResearchError as error:
            composer = self._response_composer
            fail = composer.research_security_finding_evidence_attach_failure
            return fail(request, str(error))
        return self._response_composer.research_security_finding_evidence_attach(
            request, finding
        )

    def process_status_transition(self, request: BrainRequest) -> BrainResponse:
        try:
            finding_id = request.metadata.get("finding_id")
            program_id = request.metadata.get("program_id")
            new_status = request.metadata.get("status")
            reason = request.metadata.get("reason", "")
            duplicate_of_finding_id = request.metadata.get("duplicate_of_finding_id")
            superseded_by_finding_id = request.metadata.get("superseded_by_finding_id")
            if not isinstance(finding_id, str):
                raise ResearchError(
                    "Security finding status transition requires a finding ID."
                )
            if not isinstance(program_id, str):
                raise ResearchError(
                    "Security finding status transition requires a program ID."
                )
            if not isinstance(new_status, ResearchSecurityFindingStatus):
                raise ResearchError("Security finding status is invalid.")
            if not isinstance(reason, str):
                raise ResearchError(
                    "Security finding status transition reason is invalid."
                )
            if duplicate_of_finding_id is not None and not isinstance(
                duplicate_of_finding_id, str
            ):
                raise ResearchError(
                    "Security finding duplicate-of reference is invalid."
                )
            if superseded_by_finding_id is not None and not isinstance(
                superseded_by_finding_id, str
            ):
                raise ResearchError(
                    "Security finding superseded-by reference is invalid."
                )
            self.transition_status(
                finding_id,
                program_id,
                new_status,
                reason,
                duplicate_of_finding_id,
                superseded_by_finding_id,
            )
            finding = self.finding_by_id(finding_id, program_id)
            if finding is None:
                raise ResearchError("Security finding could not be re-derived.")
        except ResearchError as error:
            composer = self._response_composer
            fail = composer.research_security_finding_status_transition_failure
            return fail(request, str(error))
        return self._response_composer.research_security_finding_status_transition(
            request, finding
        )

    def process_finding_preview(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            if not isinstance(program_id, str) or not program_id.strip():
                raise ResearchError("Security finding preview requires a program ID.")
            active_revision = self._active_revision_for_program(program_id)
            findings = self.findings_for_program(program_id)
            entries = tuple(
                ResearchSecurityFindingEntry(
                    finding=finding,
                    scope=self.current_scope_resolution(finding, active_revision),
                )
                for finding in findings
            )
        except ResearchError as error:
            composer = self._response_composer
            fail = composer.research_security_finding_preview_failure
            return fail(request, str(error))
        return self._response_composer.research_security_finding_preview(
            request, entries
        )

    # -- internals -------------------------------------------------------

    def _load(self) -> ResearchSecurityFindingDocument:
        try:
            return self._store.load()
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError(
                "Unable to restore the security finding store."
            ) from error

    def _save(self, document: ResearchSecurityFindingDocument) -> None:
        try:
            self._store.save(document)
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError(
                "Unable to persist the security finding store."
            ) from error

    def _load_http_evidence(self) -> ResearchHttpEvidenceDocument:
        try:
            return self._http_evidence_reader.load()
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to restore HTTP evidence.") from error

    def _evidence_for_program(
        self, program_id: str
    ) -> dict[str, ResearchHttpEvidenceRecord]:
        document = self._load_http_evidence()
        return {
            value.evidence_id: value
            for value in document.records
            if value.program_id == program_id
        }

    @staticmethod
    def _carried_relation(
        link: ResearchSecurityHypothesisEvidenceLinkRecord,
    ) -> ResearchSecurityFindingEvidenceRelation:
        if link.relation is ResearchSecurityHypothesisEvidenceRelation.SUPPORTS:
            return ResearchSecurityFindingEvidenceRelation.SUPPORTS
        return ResearchSecurityFindingEvidenceRelation.CONTRADICTS

    def _current_status(
        self,
        document: ResearchSecurityFindingDocument,
        finding_id: str,
        program_id: str,
    ) -> ResearchSecurityFindingStatus:
        transitions = sorted(
            (
                transition
                for transition in document.status_transitions
                if transition.finding_id == finding_id
                and transition.program_id == program_id
            ),
            key=lambda entry: (entry.recorded_at, entry.transition_id),
        )
        if not transitions:
            return ResearchSecurityFindingStatus.CANDIDATE
        return transitions[-1].status

    def _require_validation_gate(
        self,
        document: ResearchSecurityFindingDocument,
        finding_id: str,
        program_id: str,
    ) -> None:
        links = tuple(
            link
            for link in document.evidence_links
            if link.finding_id == finding_id and link.program_id == program_id
        )
        has_validation = any(
            link.relation is ResearchSecurityFindingEvidenceRelation.VALIDATES
            for link in links
        )
        has_contradiction = any(
            link.relation is ResearchSecurityFindingEvidenceRelation.CONTRADICTS
            for link in links
        )
        if not has_validation:
            raise ResearchError(
                "Security finding cannot be validated without at least one"
                " validating evidence citation."
            )
        if has_contradiction:
            raise ResearchError(
                "Security finding cannot be validated while contradicting"
                " evidence remains recorded."
            )

    def _require_linkage(
        self,
        document: ResearchSecurityFindingDocument,
        program_id: str,
        finding_id: str,
        new_status: ResearchSecurityFindingStatus,
        duplicate_of_finding_id: str | None,
        superseded_by_finding_id: str | None,
    ) -> tuple[str | None, str | None]:
        if new_status is ResearchSecurityFindingStatus.DUPLICATE:
            if superseded_by_finding_id is not None:
                raise ResearchError(
                    "Security finding duplicate transition cannot carry a"
                    " superseded-by reference."
                )
            normalized = self._require_linked_finding(
                document,
                program_id,
                finding_id,
                duplicate_of_finding_id,
                "duplicate-of",
            )
            return normalized, None
        if new_status is ResearchSecurityFindingStatus.SUPERSEDED:
            if duplicate_of_finding_id is not None:
                raise ResearchError(
                    "Security finding superseded transition cannot carry a"
                    " duplicate-of reference."
                )
            normalized = self._require_linked_finding(
                document,
                program_id,
                finding_id,
                superseded_by_finding_id,
                "superseded-by",
            )
            return None, normalized
        if duplicate_of_finding_id is not None or superseded_by_finding_id is not None:
            raise ResearchError(
                "Security finding status transition linkage is only valid for a"
                " duplicate or superseded status."
            )
        return None, None

    def _require_linked_finding(
        self,
        document: ResearchSecurityFindingDocument,
        program_id: str,
        finding_id: str,
        linked_finding_id: str | None,
        label: str,
    ) -> str:
        if not isinstance(linked_finding_id, str) or not linked_finding_id.strip():
            raise ResearchError(f"Security finding {label} reference is required.")
        normalized = linked_finding_id.strip()
        if normalized == finding_id:
            raise ResearchError(
                f"Security finding {label} reference cannot name itself."
            )
        if not any(
            existing.finding_id == normalized and existing.program_id == program_id
            for existing in document.findings
        ):
            raise ResearchError(
                f"Security finding {label} reference was not found for this" " program."
            )
        return normalized

    def _new_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Security finding identifier cannot be empty.")
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError("Security finding clock must be timezone-aware.")
        return value.astimezone(UTC)

    def _active_revision_for_program(
        self, program_id: str
    ) -> ResearchProgramScopeRevision | None:
        """Look up the one currently-valid scope revision fresh, never cached.

        Returns `None` (never a fabricated or stale resolution) when no
        program-scope revision store is wired, or when this program has no
        revision that is confirmed, unexpired, and unrevoked right now.
        Mirrors `ResearchSecurityHypothesisApplicationService`'s own method
        exactly.
        """
        if self._program_scope_revision_store is None:
            return None
        normalized = self._normalize_program_id(program_id)
        now = self._now()
        matches = [
            revision
            for revision in self._program_scope_revision_store.load()
            if revision.program_id == normalized and revision.valid_at(now)
        ]
        if len(matches) > 1:
            raise ResearchError("Program scope revision history is contradictory.")
        return matches[0] if matches else None

    @staticmethod
    def _normalize_program_id(program_id: str) -> str:
        if (
            not isinstance(program_id, str)
            or not program_id.strip()
            or len(program_id.strip()) > MAX_SECURITY_FINDING_PROGRAM_ID_CHARACTERS
        ):
            raise ResearchError("Security finding program ID is invalid.")
        return program_id.strip()

    @staticmethod
    def _normalize_finding_id(finding_id: str, label: str) -> str:
        if not isinstance(finding_id, str) or not finding_id.strip():
            raise ResearchError(f"{label} is invalid.")
        return finding_id.strip()
