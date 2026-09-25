"""Brain-facing boundary for operator-authored Bug Bounty security hypotheses.

This service performs no active validation, no fetch, no process, and no
model call. It only records an operator's stated conjecture about one
program's named subject, the HTTP evidence citations that ground or oppose
it, and the operator's own status judgements about it — reasoning over
already-recorded evidence, never a new observation of the world. Scope
resolution is always a fresh, read-only call into the unchanged
`ResearchTargetScope.resolve_hostname`/`resolve_addresses` against a
caller-supplied *currently active* `ResearchProgramScopeRevision`; it is
never cached, never persisted, and plays no part in creating, attaching
evidence to, or transitioning a hypothesis. A hypothesis, an evidence
citation, or a status value is never by itself sufficient grounds for any
authorization or execution decision, and no status value this module can
produce ever asserts a validated vulnerability
(`ResearchSecurityHypothesisStatus.means_validated_vulnerability` is `False`
for every member).
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
from research.JsonFileResearchSecurityHypothesisStore import (
    ResearchSecurityHypothesisDocument,
)
from research.ResearchAssetInventoryEntry import ResearchAssetScopeResolutionView
from research.ResearchAssetKind import ResearchAssetKind
from research.ResearchAssetObservationRecord import canonicalize_asset_value
from research.ResearchHttpEvidenceRecord import ResearchHttpEvidenceRecord
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from research.ResearchSecurityHypothesis import (
    ResearchSecurityHypothesis,
)
from research.ResearchSecurityHypothesis import (
    hypotheses_for_program as _derive_hypotheses_for_program,
)
from research.ResearchSecurityHypothesisEntry import ResearchSecurityHypothesisEntry
from research.ResearchSecurityHypothesisEvidenceKind import (
    ResearchSecurityHypothesisEvidenceKind,
)
from research.ResearchSecurityHypothesisEvidenceLinkRecord import (
    ResearchSecurityHypothesisEvidenceLinkRecord,
)
from research.ResearchSecurityHypothesisEvidenceRelation import (
    ResearchSecurityHypothesisEvidenceRelation,
)
from research.ResearchSecurityHypothesisKind import ResearchSecurityHypothesisKind
from research.ResearchSecurityHypothesisOrigin import ResearchSecurityHypothesisOrigin
from research.ResearchSecurityHypothesisRecord import ResearchSecurityHypothesisRecord
from research.ResearchSecurityHypothesisStatus import (
    ResearchSecurityHypothesisStatus,
    is_valid_status_transition,
)
from research.ResearchSecurityHypothesisStatusTransitionRecord import (
    ResearchSecurityHypothesisStatusTransitionRecord,
)
from response.ResponseComposer import ResponseComposer

RESEARCH_SECURITY_HYPOTHESIS_CREATE_INTENT = "research_security_hypothesis_create"
RESEARCH_SECURITY_HYPOTHESIS_EVIDENCE_ATTACH_INTENT = (
    "research_security_hypothesis_evidence_attach"
)
RESEARCH_SECURITY_HYPOTHESIS_STATUS_TRANSITION_INTENT = (
    "research_security_hypothesis_status_transition"
)
RESEARCH_SECURITY_HYPOTHESIS_PREVIEW_INTENT = "research_security_hypothesis_preview"

MAX_SECURITY_HYPOTHESIS_PROGRAM_ID_CHARACTERS = 200


class ResearchSecurityHypothesisStore(Protocol):
    def load(self) -> ResearchSecurityHypothesisDocument: ...

    def save(self, document: ResearchSecurityHypothesisDocument) -> None: ...


class ResearchHttpEvidenceReader(Protocol):
    def load(self) -> ResearchHttpEvidenceDocument: ...


def _normalized_statement(value: str) -> str:
    """Fold whitespace/case so a paraphrased near-duplicate is still caught."""
    return " ".join(value.split()).casefold()


class ResearchSecurityHypothesisApplicationService:
    """Record operator-authored security hypotheses; derive read models."""

    def __init__(
        self,
        store: ResearchSecurityHypothesisStore,
        http_evidence_reader: ResearchHttpEvidenceReader,
        response_composer: ResponseComposer,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        program_scope_revision_store: ActiveProgramScopeRevisionReader | None = None,
    ) -> None:
        self._store = store
        self._http_evidence_reader = http_evidence_reader
        self._response_composer = response_composer
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._program_scope_revision_store = program_scope_revision_store

    # -- durable writes ----------------------------------------------------

    def create_hypothesis(
        self,
        program_id: str,
        hypothesis_kind: ResearchSecurityHypothesisKind,
        subject_kind: ResearchAssetKind,
        subject_canonical_value: str,
        statement: str,
        rationale: str,
        required_validation: str,
        supporting_evidence_ids: tuple[str, ...],
    ) -> ResearchSecurityHypothesisRecord:
        """Append one hypothesis plus one supporting evidence link per citation.

        Requires at least one supporting evidence reference (the "evidence
        first" floor: with only `OPERATOR_AUTHORED` origin, a hypothesis with
        zero cited evidence would be an unfounded assertion this service has
        no honest way to distinguish from a guess). Every cited ID must exist
        for this exact program, and the hypothesis's own subject must match
        at least one cited evidence record's target — a hypothesis can never
        cite evidence about a different host than the one it names. Refuses
        an exact-identity duplicate (same program, subject, kind, and
        normalized statement), directing the caller to attach evidence to the
        existing hypothesis instead.
        """
        normalized_program_id = self._normalize_program_id(program_id)
        canonical_value = self._require_canonical_subject(
            subject_kind, subject_canonical_value
        )
        if (
            not isinstance(supporting_evidence_ids, tuple)
            or not supporting_evidence_ids
        ):
            raise ResearchError(
                "Security hypothesis requires at least one supporting evidence"
                " reference."
            )
        evidence_by_id = self._evidence_for_program(normalized_program_id)
        missing = tuple(
            evidence_id
            for evidence_id in supporting_evidence_ids
            if evidence_id not in evidence_by_id
        )
        if missing:
            raise ResearchError(
                "Security hypothesis cites HTTP evidence that is not recorded"
                " for this program."
            )
        if not any(
            evidence_by_id[evidence_id].target_kind == subject_kind
            and evidence_by_id[evidence_id].target_canonical_value == canonical_value
            for evidence_id in supporting_evidence_ids
        ):
            raise ResearchError(
                "Security hypothesis subject does not match any cited evidence"
                " target."
            )
        document = self._load()
        normalized_statement = _normalized_statement(
            statement if isinstance(statement, str) else ""
        )
        for existing in document.hypotheses:
            if (
                existing.program_id == normalized_program_id
                and existing.subject_kind == subject_kind
                and existing.subject_canonical_value == canonical_value
                and existing.hypothesis_kind == hypothesis_kind
                and _normalized_statement(existing.statement) == normalized_statement
            ):
                raise ResearchError(
                    "An equivalent security hypothesis already exists for this"
                    " subject; attach evidence to the existing hypothesis"
                    " instead of creating a near-duplicate."
                )
        now = self._now()
        record = ResearchSecurityHypothesisRecord(
            hypothesis_id=self._new_id(),
            program_id=normalized_program_id,
            hypothesis_kind=hypothesis_kind,
            subject_kind=subject_kind,
            subject_canonical_value=canonical_value,
            statement=statement,
            rationale=rationale,
            required_validation=required_validation,
            origin=ResearchSecurityHypothesisOrigin.OPERATOR_AUTHORED,
            created_at=now,
        )
        if any(
            existing.hypothesis_id == record.hypothesis_id
            for existing in document.hypotheses
        ):
            raise ResearchError("Security hypothesis identity already exists.")
        links = tuple(
            ResearchSecurityHypothesisEvidenceLinkRecord(
                link_id=self._new_id(),
                hypothesis_id=record.hypothesis_id,
                program_id=normalized_program_id,
                evidence_kind=ResearchSecurityHypothesisEvidenceKind.HTTP_EVIDENCE,
                evidence_id=evidence_id,
                relation=ResearchSecurityHypothesisEvidenceRelation.SUPPORTS,
                recorded_at=now,
            )
            for evidence_id in supporting_evidence_ids
        )
        self._save(
            ResearchSecurityHypothesisDocument(
                hypotheses=(*document.hypotheses, record),
                evidence_links=(*document.evidence_links, *links),
                status_transitions=document.status_transitions,
            )
        )
        return record

    def attach_evidence(
        self,
        hypothesis_id: str,
        program_id: str,
        evidence_ids: tuple[str, ...],
        relation: ResearchSecurityHypothesisEvidenceRelation,
    ) -> tuple[ResearchSecurityHypothesisEvidenceLinkRecord, ...]:
        """Append supporting or contradicting evidence links to one hypothesis.

        The hypothesis must already exist for this exact `program_id`, and
        every cited evidence ID must exist for that same program — fail
        closed on a cross-program reference or an unknown hypothesis/evidence
        ID.
        """
        normalized_program_id = self._normalize_program_id(program_id)
        normalized_hypothesis_id = self._normalize_hypothesis_id(hypothesis_id)
        if not isinstance(relation, ResearchSecurityHypothesisEvidenceRelation):
            raise ResearchError("Security hypothesis evidence relation is invalid.")
        if not isinstance(evidence_ids, tuple) or not evidence_ids:
            raise ResearchError(
                "Security hypothesis evidence attachment requires at least one"
                " evidence ID."
            )
        document = self._load()
        if not any(
            existing.hypothesis_id == normalized_hypothesis_id
            and existing.program_id == normalized_program_id
            for existing in document.hypotheses
        ):
            raise ResearchError("Security hypothesis was not found for this program.")
        evidence_by_id = self._evidence_for_program(normalized_program_id)
        missing = tuple(
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in evidence_by_id
        )
        if missing:
            raise ResearchError(
                "Security hypothesis cites HTTP evidence that is not recorded"
                " for this program."
            )
        now = self._now()
        links = tuple(
            ResearchSecurityHypothesisEvidenceLinkRecord(
                link_id=self._new_id(),
                hypothesis_id=normalized_hypothesis_id,
                program_id=normalized_program_id,
                evidence_kind=ResearchSecurityHypothesisEvidenceKind.HTTP_EVIDENCE,
                evidence_id=evidence_id,
                relation=relation,
                recorded_at=now,
            )
            for evidence_id in evidence_ids
        )
        self._save(
            ResearchSecurityHypothesisDocument(
                hypotheses=document.hypotheses,
                evidence_links=(*document.evidence_links, *links),
                status_transitions=document.status_transitions,
            )
        )
        return links

    def transition_status(
        self,
        hypothesis_id: str,
        program_id: str,
        new_status: ResearchSecurityHypothesisStatus,
        reason: str = "",
    ) -> ResearchSecurityHypothesisStatusTransitionRecord:
        """Append one status transition after validating the closed state machine.

        Refuses a self-transition (never a valid entry in the transition
        table) and any transition out of `REFUTED` (terminal).
        """
        normalized_program_id = self._normalize_program_id(program_id)
        normalized_hypothesis_id = self._normalize_hypothesis_id(hypothesis_id)
        if not isinstance(new_status, ResearchSecurityHypothesisStatus):
            raise ResearchError("Security hypothesis status is invalid.")
        document = self._load()
        if not any(
            existing.hypothesis_id == normalized_hypothesis_id
            and existing.program_id == normalized_program_id
            for existing in document.hypotheses
        ):
            raise ResearchError("Security hypothesis was not found for this program.")
        current_status = self._current_status(
            document, normalized_hypothesis_id, normalized_program_id
        )
        if not is_valid_status_transition(current_status, new_status):
            raise ResearchError(
                "Security hypothesis cannot move from "
                f"{current_status.value} to {new_status.value}."
            )
        transition = ResearchSecurityHypothesisStatusTransitionRecord(
            transition_id=self._new_id(),
            hypothesis_id=normalized_hypothesis_id,
            program_id=normalized_program_id,
            status=new_status,
            reason=reason,
            recorded_at=self._now(),
        )
        self._save(
            ResearchSecurityHypothesisDocument(
                hypotheses=document.hypotheses,
                evidence_links=document.evidence_links,
                status_transitions=(*document.status_transitions, transition),
            )
        )
        return transition

    # -- derived read models -------------------------------------------------

    def hypotheses_for_program(
        self, program_id: str
    ) -> tuple[ResearchSecurityHypothesis, ...]:
        """Recompute this program's hypotheses fresh from the persisted logs."""
        normalized = self._normalize_program_id(program_id)
        document = self._load()
        return _derive_hypotheses_for_program(
            normalized,
            document.hypotheses,
            document.evidence_links,
            document.status_transitions,
        )

    def hypothesis_by_id(
        self, hypothesis_id: str, program_id: str
    ) -> ResearchSecurityHypothesis | None:
        """Return one program's hypothesis by ID, or `None` if not found.

        Fails closed on a wrong `program_id` by construction: the derived
        listing is already scoped to `program_id`, so a hypothesis recorded
        under a different program can never be returned here.
        """
        normalized_hypothesis_id = self._normalize_hypothesis_id(hypothesis_id)
        for hypothesis in self.hypotheses_for_program(program_id):
            if hypothesis.hypothesis_id == normalized_hypothesis_id:
                return hypothesis
        return None

    @staticmethod
    def current_scope_resolution(
        hypothesis: ResearchSecurityHypothesis,
        active_revision: ResearchProgramScopeRevision | None,
    ) -> ResearchAssetScopeResolutionView:
        """Dispatch to the unchanged live resolver; never persisted, never cached.

        Reuses `ResearchAssetScopeResolutionView` unchanged — it already
        carries no dependency on asset inventory concepts beyond the tri-state
        resolution itself, so a second, near-identical view type would be
        pure duplication. Returns an explicit "no active scope revision for
        this program" signal when `active_revision` is `None`.
        """
        if not isinstance(hypothesis, ResearchSecurityHypothesis):
            raise ResearchError(
                "Security hypothesis scope resolution requires a valid hypothesis."
            )
        if active_revision is None:
            return ResearchAssetScopeResolutionView(
                has_active_scope_revision=False, resolution=None
            )
        if not isinstance(active_revision, ResearchProgramScopeRevision):
            raise ResearchError(
                "Security hypothesis scope resolution requires a valid scope"
                " revision."
            )
        if active_revision.program_id != hypothesis.program_id:
            raise ResearchError(
                "Security hypothesis scope resolution requires a revision for"
                " the same program."
            )
        if hypothesis.subject_kind is ResearchAssetKind.HOSTNAME:
            resolution = active_revision.scope.resolve_hostname(
                hypothesis.subject_canonical_value
            )
        elif hypothesis.subject_kind is ResearchAssetKind.IP_ADDRESS:
            # Named explicitly rather than as an `else`, so a future subject
            # kind fails closed here instead of silently inheriting address
            # rules.
            (resolution,) = active_revision.scope.resolve_addresses(
                (hypothesis.subject_canonical_value,)
            )
        else:
            raise ResearchError(
                "Security hypothesis subject kind is not resolvable against" " scope."
            )
        return ResearchAssetScopeResolutionView(
            has_active_scope_revision=True, resolution=resolution
        )

    # -- Brain intents -------------------------------------------------------

    @staticmethod
    def is_hypothesis_create_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent") == RESEARCH_SECURITY_HYPOTHESIS_CREATE_INTENT
        )

    @staticmethod
    def is_evidence_attach_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent")
            == RESEARCH_SECURITY_HYPOTHESIS_EVIDENCE_ATTACH_INTENT
        )

    @staticmethod
    def is_status_transition_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent")
            == RESEARCH_SECURITY_HYPOTHESIS_STATUS_TRANSITION_INTENT
        )

    @staticmethod
    def is_hypothesis_preview_request(request: BrainRequest) -> bool:
        return (
            request.metadata.get("intent")
            == RESEARCH_SECURITY_HYPOTHESIS_PREVIEW_INTENT
        )

    def process_hypothesis_create(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            hypothesis_kind = request.metadata.get("hypothesis_kind")
            subject_kind = request.metadata.get("subject_kind")
            subject_value = request.metadata.get("subject_canonical_value")
            statement = request.metadata.get("statement")
            rationale = request.metadata.get("rationale")
            required_validation = request.metadata.get("required_validation")
            supporting_evidence_ids = request.metadata.get(
                "supporting_evidence_ids", ()
            )
            if not isinstance(program_id, str):
                raise ResearchError("Security hypothesis requires a program ID.")
            if not isinstance(hypothesis_kind, ResearchSecurityHypothesisKind):
                raise ResearchError("Security hypothesis requires a valid kind.")
            if not isinstance(subject_kind, ResearchAssetKind):
                raise ResearchError(
                    "Security hypothesis requires a valid subject kind."
                )
            if not isinstance(subject_value, str):
                raise ResearchError(
                    "Security hypothesis requires an explicit subject value."
                )
            if not isinstance(statement, str):
                raise ResearchError("Security hypothesis statement is invalid.")
            if not isinstance(rationale, str):
                raise ResearchError("Security hypothesis rationale is invalid.")
            if not isinstance(required_validation, str):
                raise ResearchError(
                    "Security hypothesis required validation is invalid."
                )
            if not isinstance(supporting_evidence_ids, tuple) or any(
                not isinstance(value, str) for value in supporting_evidence_ids
            ):
                raise ResearchError(
                    "Security hypothesis supporting evidence references are" " invalid."
                )
            record = self.create_hypothesis(
                program_id,
                hypothesis_kind,
                subject_kind,
                subject_value,
                statement,
                rationale,
                required_validation,
                supporting_evidence_ids,
            )
            hypothesis = self.hypothesis_by_id(record.hypothesis_id, record.program_id)
            if hypothesis is None:
                raise ResearchError("Security hypothesis could not be re-derived.")
        except ResearchError as error:
            return self._response_composer.research_security_hypothesis_create_failure(
                request, str(error)
            )
        return self._response_composer.research_security_hypothesis_create(
            request, hypothesis
        )

    def process_evidence_attach(self, request: BrainRequest) -> BrainResponse:
        try:
            hypothesis_id = request.metadata.get("hypothesis_id")
            program_id = request.metadata.get("program_id")
            evidence_ids = request.metadata.get("evidence_ids", ())
            relation = request.metadata.get("relation")
            if not isinstance(hypothesis_id, str):
                raise ResearchError(
                    "Security hypothesis evidence attachment requires a"
                    " hypothesis ID."
                )
            if not isinstance(program_id, str):
                raise ResearchError(
                    "Security hypothesis evidence attachment requires a" " program ID."
                )
            if not isinstance(evidence_ids, tuple) or any(
                not isinstance(value, str) for value in evidence_ids
            ):
                raise ResearchError(
                    "Security hypothesis evidence references are invalid."
                )
            if not isinstance(relation, ResearchSecurityHypothesisEvidenceRelation):
                raise ResearchError("Security hypothesis evidence relation is invalid.")
            self.attach_evidence(hypothesis_id, program_id, evidence_ids, relation)
            hypothesis = self.hypothesis_by_id(hypothesis_id, program_id)
            if hypothesis is None:
                raise ResearchError("Security hypothesis could not be re-derived.")
        except ResearchError as error:
            composer = self._response_composer
            fail = composer.research_security_hypothesis_evidence_attach_failure
            return fail(request, str(error))
        return self._response_composer.research_security_hypothesis_evidence_attach(
            request, hypothesis
        )

    def process_status_transition(self, request: BrainRequest) -> BrainResponse:
        try:
            hypothesis_id = request.metadata.get("hypothesis_id")
            program_id = request.metadata.get("program_id")
            new_status = request.metadata.get("status")
            reason = request.metadata.get("reason", "")
            if not isinstance(hypothesis_id, str):
                raise ResearchError(
                    "Security hypothesis status transition requires a" " hypothesis ID."
                )
            if not isinstance(program_id, str):
                raise ResearchError(
                    "Security hypothesis status transition requires a" " program ID."
                )
            if not isinstance(new_status, ResearchSecurityHypothesisStatus):
                raise ResearchError("Security hypothesis status is invalid.")
            if not isinstance(reason, str):
                raise ResearchError(
                    "Security hypothesis status transition reason is invalid."
                )
            self.transition_status(hypothesis_id, program_id, new_status, reason)
            hypothesis = self.hypothesis_by_id(hypothesis_id, program_id)
            if hypothesis is None:
                raise ResearchError("Security hypothesis could not be re-derived.")
        except ResearchError as error:
            composer = self._response_composer
            fail = composer.research_security_hypothesis_status_transition_failure
            return fail(request, str(error))
        return self._response_composer.research_security_hypothesis_status_transition(
            request, hypothesis
        )

    def process_hypothesis_preview(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            if not isinstance(program_id, str) or not program_id.strip():
                raise ResearchError(
                    "Security hypothesis preview requires a program ID."
                )
            active_revision = self._active_revision_for_program(program_id)
            hypotheses = self.hypotheses_for_program(program_id)
            entries = tuple(
                ResearchSecurityHypothesisEntry(
                    hypothesis=hypothesis,
                    scope=self.current_scope_resolution(hypothesis, active_revision),
                )
                for hypothesis in hypotheses
            )
        except ResearchError as error:
            composer = self._response_composer
            fail = composer.research_security_hypothesis_preview_failure
            return fail(request, str(error))
        return self._response_composer.research_security_hypothesis_preview(
            request, entries
        )

    # -- internals -------------------------------------------------------

    def _load(self) -> ResearchSecurityHypothesisDocument:
        try:
            return self._store.load()
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError(
                "Unable to restore the security hypothesis store."
            ) from error

    def _save(self, document: ResearchSecurityHypothesisDocument) -> None:
        try:
            self._store.save(document)
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError(
                "Unable to persist the security hypothesis store."
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

    def _current_status(
        self,
        document: ResearchSecurityHypothesisDocument,
        hypothesis_id: str,
        program_id: str,
    ) -> ResearchSecurityHypothesisStatus:
        transitions = sorted(
            (
                transition
                for transition in document.status_transitions
                if transition.hypothesis_id == hypothesis_id
                and transition.program_id == program_id
            ),
            key=lambda entry: (entry.recorded_at, entry.transition_id),
        )
        if not transitions:
            return ResearchSecurityHypothesisStatus.OPEN
        return transitions[-1].status

    def _new_id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not value.strip():
            raise ResearchError("Security hypothesis identifier cannot be empty.")
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ResearchError("Security hypothesis clock must be timezone-aware.")
        return value.astimezone(UTC)

    def _active_revision_for_program(
        self, program_id: str
    ) -> ResearchProgramScopeRevision | None:
        """Look up the one currently-valid scope revision fresh, never cached.

        Returns `None` (never a fabricated or stale resolution) when no
        program-scope revision store is wired, or when this program has no
        revision that is confirmed, unexpired, and unrevoked right now.
        Mirrors `ResearchAssetInventoryApplicationService`'s own method
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
    def _require_canonical_subject(kind: ResearchAssetKind, value: str) -> str:
        if not isinstance(kind, ResearchAssetKind) or kind not in (
            ResearchAssetKind.HOSTNAME,
            ResearchAssetKind.IP_ADDRESS,
        ):
            raise ResearchError("Security hypothesis subject kind is invalid.")
        return canonicalize_asset_value(kind, value)

    @staticmethod
    def _normalize_program_id(program_id: str) -> str:
        if (
            not isinstance(program_id, str)
            or not program_id.strip()
            or len(program_id.strip()) > MAX_SECURITY_HYPOTHESIS_PROGRAM_ID_CHARACTERS
        ):
            raise ResearchError("Security hypothesis program ID is invalid.")
        return program_id.strip()

    @staticmethod
    def _normalize_hypothesis_id(hypothesis_id: str) -> str:
        if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
            raise ResearchError("Security hypothesis ID is invalid.")
        return hypothesis_id.strip()
