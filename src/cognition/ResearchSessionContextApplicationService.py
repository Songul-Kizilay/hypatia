"""Brain boundary for inert, operator-authored research session contexts.

The service only labels already-recorded HTTP evidence. It never reads header
values, performs a request, establishes or reuses a login, or changes scope,
budget, target, or authorization state.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.JsonFileResearchHttpEvidenceStore import ResearchHttpEvidenceDocument
from research.JsonFileResearchSessionContextStore import (
    ResearchSessionContextDocument,
)
from research.ResearchAuthenticationState import ResearchAuthenticationState
from research.ResearchSessionContextRecord import (
    MAX_SESSION_CONTEXT_PROGRAM_ID_CHARACTERS,
    ResearchSessionContextRecord,
)
from response.ResponseComposer import ResponseComposer

RESEARCH_SESSION_CONTEXT_RECORD_INTENT = "research_session_context_record"
RESEARCH_SESSION_CONTEXT_PREVIEW_INTENT = "research_session_context_preview"


class ResearchSessionContextStore(Protocol):
    def load(self) -> ResearchSessionContextDocument: ...

    def save(self, document: ResearchSessionContextDocument) -> None: ...


class ResearchHttpEvidenceReader(Protocol):
    def load(self) -> ResearchHttpEvidenceDocument: ...


class ResearchSessionContextApplicationService:
    def __init__(
        self,
        store: ResearchSessionContextStore,
        http_evidence_reader: ResearchHttpEvidenceReader,
        response_composer: ResponseComposer,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._http_evidence_reader = http_evidence_reader
        self._response_composer = response_composer
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def record_session_context(
        self,
        program_id: str,
        authentication_state: ResearchAuthenticationState,
        identity_label: str,
        evidence_ids: tuple[str, ...],
        note: str = "",
    ) -> ResearchSessionContextRecord:
        record = ResearchSessionContextRecord(
            session_context_id=self._id_factory(),
            program_id=program_id,
            authentication_state=authentication_state,
            identity_label=identity_label,
            evidence_ids=evidence_ids,
            note=note,
            recorded_at=self._clock(),
        )
        evidence = self._load_http_evidence()
        available_ids = {
            value.evidence_id
            for value in evidence.records
            if value.program_id == record.program_id
        }
        missing = tuple(
            evidence_id
            for evidence_id in record.evidence_ids
            if evidence_id not in available_ids
        )
        if missing:
            raise ResearchError(
                "Research session context references HTTP evidence that is not"
                " recorded for this program."
            )
        document = self._load()
        if any(
            existing.session_context_id == record.session_context_id
            for existing in document.records
        ):
            raise ResearchError("Research session context identity already exists.")
        self._save(ResearchSessionContextDocument(records=(*document.records, record)))
        return record

    def contexts_for_program(
        self, program_id: str
    ) -> tuple[ResearchSessionContextRecord, ...]:
        normalized = self._normalize_program_id(program_id)
        return tuple(
            record for record in self._load().records if record.program_id == normalized
        )

    @staticmethod
    def is_record_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_SESSION_CONTEXT_RECORD_INTENT

    @staticmethod
    def is_preview_request(request: BrainRequest) -> bool:
        return request.metadata.get("intent") == RESEARCH_SESSION_CONTEXT_PREVIEW_INTENT

    def process_record(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            authentication_state = request.metadata.get("authentication_state")
            identity_label = request.metadata.get("identity_label", "")
            evidence_ids = request.metadata.get("evidence_ids", ())
            note = request.metadata.get("note", "")
            if not isinstance(program_id, str):
                raise ResearchError("Research session context requires a program ID.")
            if not isinstance(authentication_state, ResearchAuthenticationState):
                raise ResearchError(
                    "Research session context requires an authentication state."
                )
            if not isinstance(identity_label, str):
                raise ResearchError("Research session identity label is invalid.")
            if not isinstance(evidence_ids, tuple) or any(
                not isinstance(value, str) for value in evidence_ids
            ):
                raise ResearchError("Research session evidence references are invalid.")
            if not isinstance(note, str):
                raise ResearchError("Research session context note is invalid.")
            record = self.record_session_context(
                program_id,
                authentication_state,
                identity_label,
                evidence_ids,
                note,
            )
        except ResearchError as error:
            return self._response_composer.research_session_context_record_failure(
                request, str(error)
            )
        return self._response_composer.research_session_context_record(request, record)

    def process_preview(self, request: BrainRequest) -> BrainResponse:
        try:
            program_id = request.metadata.get("program_id")
            if not isinstance(program_id, str):
                raise ResearchError("Research session context requires a program ID.")
            normalized = self._normalize_program_id(program_id)
            contexts = self.contexts_for_program(normalized)
        except ResearchError as error:
            return self._response_composer.research_session_context_preview_failure(
                request, str(error)
            )
        return self._response_composer.research_session_context_preview(
            request, normalized, contexts
        )

    def _load(self) -> ResearchSessionContextDocument:
        try:
            return self._store.load()
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError(
                "Unable to restore research session contexts."
            ) from error

    def _save(self, document: ResearchSessionContextDocument) -> None:
        try:
            self._store.save(document)
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to save research session context.") from error

    def _load_http_evidence(self) -> ResearchHttpEvidenceDocument:
        try:
            return self._http_evidence_reader.load()
        except ResearchError:
            raise
        except Exception as error:
            raise ResearchError("Unable to restore HTTP evidence.") from error

    @staticmethod
    def _normalize_program_id(program_id: str) -> str:
        if (
            not isinstance(program_id, str)
            or not program_id.strip()
            or len(program_id.strip()) > MAX_SESSION_CONTEXT_PROGRAM_ID_CHARACTERS
        ):
            raise ResearchError("Research session context program ID is invalid.")
        normalized = program_id.strip()
        if any(
            ord(character) < 32 or ord(character) == 127 for character in normalized
        ):
            raise ResearchError(
                "Research session context program ID must be single-line text."
            )
        return normalized
