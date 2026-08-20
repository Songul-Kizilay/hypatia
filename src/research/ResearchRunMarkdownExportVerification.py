"""Read-only integrity result for one existing research Markdown export."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.Exceptions import ResearchError

MAX_MARKDOWN_EXPORT_VERIFICATION_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ResearchRunMarkdownExportVerification:
    """Compare one stable local file with the current deterministic run export."""

    run_id: str
    snapshot_updated_at: datetime
    source_path: str
    expected_content_sha256: str
    observed_content_sha256: str
    expected_byte_count: int
    observed_byte_count: int
    matches: bool

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ResearchError("Research export verification run ID cannot be empty.")
        if (
            not isinstance(self.snapshot_updated_at, datetime)
            or self.snapshot_updated_at.utcoffset() is None
        ):
            raise ResearchError(
                "Research export verification snapshot time must be timezone-aware."
            )
        if (
            not isinstance(self.source_path, str)
            or not self.source_path.strip()
            or "\x00" in self.source_path
        ):
            raise ResearchError("Research export verification source is invalid.")
        source = Path(self.source_path.strip())
        if not source.is_absolute():
            raise ResearchError("Research export verification source must be absolute.")
        if source.suffix.casefold() != ".md":
            raise ResearchError(
                "Research export verification source must end with .md."
            )
        expected_hash = self._normalize_sha256(
            self.expected_content_sha256,
            "expected",
        )
        observed_hash = self._normalize_sha256(
            self.observed_content_sha256,
            "observed",
        )
        if (
            isinstance(self.expected_byte_count, bool)
            or not isinstance(self.expected_byte_count, int)
            or self.expected_byte_count <= 0
        ):
            raise ResearchError(
                "Research export verification expected byte count must be positive."
            )
        if (
            isinstance(self.observed_byte_count, bool)
            or not isinstance(self.observed_byte_count, int)
            or self.observed_byte_count < 0
        ):
            raise ResearchError(
                "Research export verification observed byte count cannot be negative."
            )
        if not isinstance(self.matches, bool):
            raise ResearchError("Research export verification match state is invalid.")
        exact_match = (
            expected_hash == observed_hash
            and self.expected_byte_count == self.observed_byte_count
        )
        if self.matches is not exact_match:
            raise ResearchError("Research export verification result is inconsistent.")
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "source_path", str(source))
        object.__setattr__(self, "expected_content_sha256", expected_hash)
        object.__setattr__(self, "observed_content_sha256", observed_hash)

    @staticmethod
    def _normalize_sha256(value: str, label: str) -> str:
        if not isinstance(value, str):
            raise ResearchError(
                f"Research export verification {label} fingerprint is invalid."
            )
        normalized = value.strip().casefold()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ResearchError(
                f"Research export verification {label} fingerprint is invalid."
            )
        return normalized
