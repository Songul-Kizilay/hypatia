"""Bounded read-only preview of a deterministic research Markdown export."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchRunStatus import ResearchRunStatus

MAX_MARKDOWN_EXPORT_PREVIEW_CHARACTERS = 24_000


@dataclass(frozen=True, slots=True)
class ResearchRunMarkdownExportPreview:
    """Carry a bounded display plus the exact immutable snapshot identity."""

    run_id: str
    run_status: ResearchRunStatus
    snapshot_updated_at: datetime
    suggested_filename: str
    markdown_preview: str
    total_character_count: int
    omitted_character_count: int
    content_sha256: str

    def __post_init__(self) -> None:
        for text_value, field_name in (
            (self.run_id, "Research export run ID"),
            (self.suggested_filename, "Research export filename"),
            (self.markdown_preview, "Research export Markdown preview"),
        ):
            if not isinstance(text_value, str) or not text_value.strip():
                raise ResearchError(f"{field_name} cannot be empty.")
        if not isinstance(self.run_status, ResearchRunStatus):
            raise ResearchError("Research export run status is invalid.")
        if not self.run_status.terminal:
            raise ResearchError("Research export preview requires a terminal run.")
        if (
            not isinstance(self.snapshot_updated_at, datetime)
            or self.snapshot_updated_at.utcoffset() is None
        ):
            raise ResearchError("Research export snapshot time must be timezone-aware.")
        for count, field_name in (
            (self.total_character_count, "Research export total character count"),
            (self.omitted_character_count, "Research export omitted character count"),
        ):
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ResearchError(f"{field_name} cannot be negative.")
        if self.total_character_count < self.omitted_character_count:
            raise ResearchError("Research export preview counts are inconsistent.")
        visible_character_count = (
            self.total_character_count - self.omitted_character_count
        )
        if self.omitted_character_count:
            truncation_marker = (
                "\n\n> Preview truncated: "
                f"{self.omitted_character_count} characters omitted.\n"
            )
            if (
                visible_character_count != MAX_MARKDOWN_EXPORT_PREVIEW_CHARACTERS
                or not self.markdown_preview.endswith(truncation_marker)
                or len(self.markdown_preview) - len(truncation_marker)
                != visible_character_count
            ):
                raise ResearchError("Research export truncation metadata is invalid.")
        elif (
            self.total_character_count > MAX_MARKDOWN_EXPORT_PREVIEW_CHARACTERS
            or len(self.markdown_preview) != self.total_character_count
        ):
            raise ResearchError("Research export preview counts are inconsistent.")
        if (
            not isinstance(self.content_sha256, str)
            or len(self.content_sha256) != 64
            or any(
                character not in "0123456789abcdef" for character in self.content_sha256
            )
        ):
            raise ResearchError("Research export content fingerprint is invalid.")
        normalized_filename = self.suggested_filename.strip()
        if not normalized_filename.endswith(".md"):
            raise ResearchError("Research export filename must end with .md.")
        if "/" in normalized_filename or "\\" in normalized_filename:
            raise ResearchError("Research export filename cannot contain a path.")
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(
            self,
            "suggested_filename",
            normalized_filename,
        )
        object.__setattr__(self, "content_sha256", self.content_sha256.casefold())
