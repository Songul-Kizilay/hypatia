"""An inert, bounded contract for one local-file content range.

This type reads nothing and grants nothing. The isolated, unregistered
text-policy Tool may construct it after an authorized platform read; the
production runtime and product surfaces still do not register or present it.
Native handles, presentation, model integration, and downstream persistence
remain outside this contract.

The relative resource is a code-owned reference derived after
``FilesystemRoot`` admission. Validation here bounds and canonicalizes the
reference shape for provenance; it is not a second filesystem authorization
policy and never probes the path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from core.Exceptions import ResearchError
from tools.FilesystemRoot import (
    MAX_PATH_DEPTH,
    MAX_RELATIVE_PATH_LENGTH,
    MAX_ROOT_ID_LENGTH,
)

MAX_CONTENT_BYTES = 64 * 1024
MAX_CONTENT_OFFSET = (1 << 63) - 1

FILESYSTEM_CONTENT_SOURCE_KIND = "local_filesystem"
FILESYSTEM_CONTENT_KIND = "file"
FILESYSTEM_CONTENT_ENCODING = "utf-8"
FILESYSTEM_CONTENT_TAINT_LABEL = "external_untrusted_data"
FILESYSTEM_CONTENT_INSTRUCTION_AUTHORITY = "none"
FILESYSTEM_CONTENT_DISCLOSURE_CLASS = "local_only"

_UTF8_BOM_BYTE_COUNT = 3


@dataclass(frozen=True, slots=True)
class FilesystemContentPayload:
    """Bind bounded decoded text to local-only filesystem provenance."""

    root_id: str
    resource: str
    offset: int
    bytes_requested: int
    bytes_returned: int
    truncated: bool
    file_size_bytes: int
    modified_utc: datetime
    bom_stripped: bool
    read_at_utc: datetime
    text: str = field(repr=False)
    source_kind: str = field(default=FILESYSTEM_CONTENT_SOURCE_KIND, init=False)
    kind: str = field(default=FILESYSTEM_CONTENT_KIND, init=False)
    encoding: str = field(default=FILESYSTEM_CONTENT_ENCODING, init=False)
    taint_label: str = field(default=FILESYSTEM_CONTENT_TAINT_LABEL, init=False)
    instruction_authority: str = field(
        default=FILESYSTEM_CONTENT_INSTRUCTION_AUTHORITY,
        init=False,
    )
    disclosure_class: str = field(
        default=FILESYSTEM_CONTENT_DISCLOSURE_CLASS,
        init=False,
    )

    def __post_init__(self) -> None:
        self._validate_scope()
        self._validate_counts()
        self._validate_times()
        self._validate_text()

    def _validate_scope(self) -> None:
        if not isinstance(self.root_id, str) or not self.root_id.strip():
            raise ResearchError("Filesystem content needs a root identifier.")
        if len(self.root_id) > MAX_ROOT_ID_LENGTH:
            raise ResearchError("Filesystem content root identifier is too long.")
        self._require_valid_unicode(self.root_id, "root identifier")
        if not isinstance(self.resource, str) or not self.resource.strip():
            raise ResearchError("Filesystem content needs a resource reference.")
        if len(self.resource) > MAX_RELATIVE_PATH_LENGTH:
            raise ResearchError("Filesystem content resource reference is too long.")
        self._require_valid_unicode(self.resource, "resource reference")
        parts = self.resource.split("/")
        if (
            self.resource.startswith("/")
            or "\\" in self.resource
            or ":" in self.resource
            or any(part in ("", ".", "..") for part in parts)
            or len(parts) > MAX_PATH_DEPTH
        ):
            raise ResearchError(
                "Filesystem content resource reference is not canonical."
            )

    def _validate_counts(self) -> None:
        self._bounded_whole_number(
            self.offset,
            "offset",
            maximum=MAX_CONTENT_OFFSET,
        )
        self._bounded_whole_number(
            self.bytes_requested,
            "requested byte count",
            maximum=MAX_CONTENT_BYTES,
        )
        self._bounded_whole_number(
            self.bytes_returned,
            "returned byte count",
            maximum=self.bytes_requested,
        )
        self._bounded_whole_number(
            self.file_size_bytes,
            "file size",
            maximum=MAX_CONTENT_OFFSET,
        )
        if not isinstance(self.truncated, bool):
            raise ResearchError("Filesystem content truncation flag must be boolean.")
        observed_truncation = self.offset + self.bytes_returned < self.file_size_bytes
        if self.truncated is not observed_truncation:
            raise ResearchError(
                "Filesystem content truncation disagrees with observed size."
            )
        if not isinstance(self.bom_stripped, bool):
            raise ResearchError("Filesystem content BOM flag must be boolean.")
        if self.bom_stripped and (
            self.offset != 0 or self.bytes_returned < _UTF8_BOM_BYTE_COUNT
        ):
            raise ResearchError("Filesystem content BOM claim is invalid.")

    def _validate_times(self) -> None:
        for value, label in (
            (self.modified_utc, "modification time"),
            (self.read_at_utc, "read time"),
        ):
            if (
                not isinstance(value, datetime)
                or value.utcoffset() is None
                or value.utcoffset() != timedelta(0)
            ):
                raise ResearchError(f"Filesystem content {label} must be UTC.")

    def _validate_text(self) -> None:
        if not isinstance(self.text, str):
            raise ResearchError("Filesystem content text must be text.")
        try:
            encoded = self.text.encode(FILESYSTEM_CONTENT_ENCODING, errors="strict")
        except UnicodeEncodeError as error:
            raise ResearchError(
                "Filesystem content text is not valid Unicode."
            ) from error
        expected_text_bytes = self.bytes_returned - (
            _UTF8_BOM_BYTE_COUNT if self.bom_stripped else 0
        )
        if len(encoded) != expected_text_bytes:
            raise ResearchError("Filesystem content byte count is invalid.")
        if (
            self.offset == 0
            and not self.bom_stripped
            and self.text.startswith("\ufeff")
        ):
            raise ResearchError("Filesystem content leading BOM was not stripped.")

    @staticmethod
    def _bounded_whole_number(
        value: int,
        label: str,
        *,
        maximum: int,
    ) -> None:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value > maximum
        ):
            raise ResearchError(f"Filesystem content {label} is invalid.")

    @staticmethod
    def _require_valid_unicode(value: str, label: str) -> None:
        try:
            value.encode(FILESYSTEM_CONTENT_ENCODING, errors="strict")
        except UnicodeEncodeError as error:
            raise ResearchError(
                f"Filesystem content {label} is not valid Unicode."
            ) from error
