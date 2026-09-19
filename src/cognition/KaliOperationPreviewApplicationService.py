"""Brain-facing boundary for inert Kali operation previews."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from brain.BrainRequest import BrainRequest
from brain.BrainResponse import BrainResponse
from core.Exceptions import ResearchError
from research.PublicHttpsUrlValidator import PublicHttpsUrlValidator
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
    ResearchKaliOperationPreview,
)
from research.ResearchProgramScopeExecutionPolicy import (
    ResearchProgramScopeCheckClass,
)
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from research.ResearchProgramScopeRevisionStore import ResearchProgramScopeRevisionStore
from response.ResponseComposer import ResponseComposer

KALI_OPERATION_PREVIEW_INTENT = "kali_operation_preview"


class KaliOperationPreviewApplicationService:
    """Preview one reviewed operation without process or execution effects.

    DNS_RECORD_LOOKUP previews perform no DNS lookup or network effect.
    HTTPS_HEADER_LOOKUP previews resolve and validate the target hostname's
    address so the previewed and later-authorized command plan can be pinned
    to it; that resolution is the only network effect a preview performs.
    """

    def __init__(
        self,
        response_composer: ResponseComposer,
        program_scope_revision_store: ResearchProgramScopeRevisionStore,
        *,
        clock: Callable[[], datetime] | None = None,
        https_url_validator: PublicHttpsUrlValidator | None = None,
    ) -> None:
        self._response_composer = response_composer
        self._program_scope_revision_store = program_scope_revision_store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._https_url_validator = https_url_validator or PublicHttpsUrlValidator()

    @staticmethod
    def is_preview_request(request: BrainRequest) -> bool:
        """Recognize only the explicit structured preview intent."""
        return request.metadata.get("intent") == KALI_OPERATION_PREVIEW_INTENT

    def process_preview(self, request: BrainRequest) -> BrainResponse:
        """Build one operation preview, or a bounded refusal, without a process."""
        try:
            preview = self.preview_for_request(request)
        except ResearchError as error:
            return self._response_composer.kali_operation_preview_failure(
                request, str(error)
            )
        return self._response_composer.kali_operation_preview(request, preview)

    def preview_for_request(
        self, request: BrainRequest
    ) -> ResearchKaliOperationPreview:
        """Rebuild the exact inert operation preview from structured metadata."""
        kind = self._operation_kind(request.metadata.get("kali_operation_kind"))
        hostname = cast(str, request.metadata.get("hostname"))
        revision = self._active_revision(
            program_id=cast(str, request.metadata.get("program_id")),
            revision_id=cast(str, request.metadata.get("scope_revision_id")),
            revision_digest=cast(str, request.metadata.get("scope_revision_digest")),
        )
        revision.scope.require_hostname(hostname)
        policy = revision.execution_policy
        check_class = self._check_class_for_kind(kind)
        if check_class not in policy.permitted_check_classes:
            raise ResearchError(
                f"Program scope policy does not permit {check_class.value}."
            )
        if (
            kind is ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP
            and 443 not in policy.permitted_ports
        ):
            raise ResearchError("Program scope policy does not permit HTTPS port 443.")
        resolved_address: str | None = None
        if kind is ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP:
            normalized_hostname = hostname.strip().lower().removesuffix(".")
            destination = self._https_url_validator.validate_and_resolve(
                f"https://{normalized_hostname}/"
            )
            revision.scope.require_addresses(destination.addresses)
            resolved_address = destination.addresses[0]
        return ResearchKaliOperationPreview(
            program_id=revision.program_id,
            scope_revision_id=revision.revision_id,
            scope_revision_digest=revision.revision_digest,
            execution_policy_digest=revision.execution_policy_digest,
            operation_kind=kind,
            check_class=check_class,
            hostname=hostname,
            dns_record_type=(
                self._dns_record_type(request.metadata.get("dns_record_type"))
                if kind is ResearchKaliOperationKind.DNS_RECORD_LOOKUP
                else None
            ),
            resolved_address=resolved_address,
            permitted_ports=policy.permitted_ports,
            max_request_count=policy.max_request_count,
            max_requests_per_minute=policy.max_requests_per_minute,
            max_seconds=policy.max_seconds,
            created_at=self._clock(),
        )

    @staticmethod
    def _operation_kind(value: object) -> ResearchKaliOperationKind:
        if not isinstance(value, str):
            raise ResearchError("Kali operation preview kind is invalid.")
        try:
            return ResearchKaliOperationKind(value)
        except ValueError as error:
            raise ResearchError("Kali operation preview kind is invalid.") from error

    @staticmethod
    def _check_class_for_kind(
        kind: ResearchKaliOperationKind,
    ) -> ResearchProgramScopeCheckClass:
        if kind is ResearchKaliOperationKind.DNS_RECORD_LOOKUP:
            return ResearchProgramScopeCheckClass.DNS_RECORD_LOOKUP
        if kind is ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP:
            return ResearchProgramScopeCheckClass.PUBLIC_HTTPS_CONTENT
        raise ResearchError("Kali operation preview kind is not supported.")

    @staticmethod
    def _dns_record_type(value: object) -> ResearchDnsRecordType:
        if not isinstance(value, str):
            raise ResearchError("Kali operation preview DNS record type is invalid.")
        try:
            return ResearchDnsRecordType(value)
        except ValueError as error:
            raise ResearchError(
                "Kali operation preview DNS record type is invalid."
            ) from error

    def _active_revision(
        self,
        *,
        program_id: str,
        revision_id: str,
        revision_digest: str,
    ) -> ResearchProgramScopeRevision:
        for value, label in (
            (program_id, "program ID"),
            (revision_id, "scope revision ID"),
            (revision_digest, "scope revision digest"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResearchError(f"Kali operation preview {label} cannot be empty.")
        matches = tuple(
            revision
            for revision in self._program_scope_revision_store.load()
            if revision.program_id == program_id.strip()
            and revision.revision_id == revision_id.strip()
            and revision.revision_digest == revision_digest.strip()
        )
        if len(matches) != 1:
            raise ResearchError(
                "Kali operation preview requires the exact active scope revision."
            )
        revision = matches[0]
        if not revision.valid_at(self._clock()):
            raise ResearchError("Kali operation preview scope revision is not active.")
        return revision
