"""Verified result of publishing one research Markdown export."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.Exceptions import ResearchError


@dataclass(frozen=True, slots=True)
class ResearchRunMarkdownExportResult:
    """Describe the exact new file created from a revalidated run snapshot."""

    run_id: str
    snapshot_updated_at: datetime
    destination_path: str
    content_sha256: str
    byte_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ResearchError("Research export run ID cannot be empty.")
        if (
            not isinstance(self.snapshot_updated_at, datetime)
            or self.snapshot_updated_at.utcoffset() is None
        ):
            raise ResearchError("Research export snapshot time must be timezone-aware.")
        if (
            not isinstance(self.destination_path, str)
            or not self.destination_path.strip()
            or "\x00" in self.destination_path
        ):
            raise ResearchError("Research export destination cannot be empty.")
        destination = Path(self.destination_path.strip())
        if not destination.is_absolute():
            raise ResearchError("Research export destination must be absolute.")
        if destination.suffix.casefold() != ".md":
            raise ResearchError("Research export destination must end with .md.")
        if (
            not isinstance(self.content_sha256, str)
            or len(self.content_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.content_sha256.casefold()
            )
        ):
            raise ResearchError("Research export content fingerprint is invalid.")
        if (
            isinstance(self.byte_count, bool)
            or not isinstance(self.byte_count, int)
            or self.byte_count <= 0
        ):
            raise ResearchError("Research export byte count must be positive.")
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "destination_path", str(destination))
        object.__setattr__(self, "content_sha256", self.content_sha256.casefold())
