"""Plain desktop projection of one bounded local-file content outcome.

The Tool Layer owns authority and payload validation.  This type is the narrow
presentation copy that lets Tkinter render the result without importing a Tool
type.  Text is excluded from ``repr``; callers must ask for it deliberately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from core.Exceptions import ResearchError


@dataclass(frozen=True, slots=True)
class FilesystemContentPreview:
    """Bind literal text to its code-owned invocation and local provenance."""

    request_id: str
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
    source_kind: str
    encoding: str
    taint_label: str
    instruction_authority: str
    disclosure_class: str
    text: str = field(repr=False)

    def __post_init__(self) -> None:
        for text_value, label in (
            (self.request_id, "request identifier"),
            (self.root_id, "root identifier"),
            (self.resource, "resource"),
            (self.source_kind, "source kind"),
            (self.encoding, "encoding"),
            (self.taint_label, "taint label"),
            (self.instruction_authority, "instruction authority"),
            (self.disclosure_class, "disclosure class"),
        ):
            if not isinstance(text_value, str) or not text_value.strip():
                raise ResearchError(f"A content preview needs a {label}.")
        for count_value, label in (
            (self.offset, "offset"),
            (self.bytes_requested, "requested byte count"),
            (self.bytes_returned, "returned byte count"),
            (self.file_size_bytes, "file size"),
        ):
            if (
                isinstance(count_value, bool)
                or not isinstance(count_value, int)
                or count_value < 0
            ):
                raise ResearchError(f"A content preview {label} is invalid.")
        if self.bytes_returned > self.bytes_requested:
            raise ResearchError("A content preview returned more than requested.")
        for flag_value, label in (
            (self.truncated, "truncation flag"),
            (self.bom_stripped, "BOM flag"),
        ):
            if not isinstance(flag_value, bool):
                raise ResearchError(f"A content preview {label} must be boolean.")
        for time_value, label in (
            (self.modified_utc, "modification time"),
            (self.read_at_utc, "read time"),
        ):
            if (
                not isinstance(time_value, datetime)
                or time_value.utcoffset() is None
                or time_value.utcoffset() != timedelta(0)
            ):
                raise ResearchError(f"A content preview {label} must be UTC.")
        if not isinstance(self.text, str):
            raise ResearchError("A content preview text must be text.")

    @property
    def completion_label(self) -> str:
        """Describe range completeness without claiming future freshness."""
        if self.truncated:
            return "truncated"
        return "complete for observed file size"

    def provenance_lines(self) -> tuple[str, ...]:
        """Return local presentation metadata; never include the text itself."""
        return (
            f"Request ID: {self.request_id}",
            f"Scope: {self.root_id}",
            f"Entry: {self.resource}",
            f"Offset: {self.offset}",
            f"Bytes requested: {self.bytes_requested}",
            f"Bytes returned: {self.bytes_returned}",
            f"Observed file size: {self.file_size_bytes}",
            f"Range state: {self.completion_label}",
            f"Modified UTC: {self.modified_utc.isoformat()}",
            f"Read UTC: {self.read_at_utc.isoformat()}",
            f"Encoding: {self.encoding}",
            f"BOM stripped: {'yes' if self.bom_stripped else 'no'}",
            f"Taint: {self.taint_label}",
            f"Instruction authority: {self.instruction_authority}",
            f"Disclosure: {self.disclosure_class}",
        )
