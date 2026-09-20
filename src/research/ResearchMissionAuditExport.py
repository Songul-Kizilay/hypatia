"""Preview and result of one confirmed mission audit export (Markdown + JSON)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_MISSION_AUDIT_PREVIEW_CHARACTERS = 24_000


def mission_audit_filenames(plan_id: str) -> tuple[str, str]:
    """Return the Markdown and JSON file names for one mission's audit."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", plan_id).strip("-.")[:80] or "mission"
    return f"mission-audit-{safe}.md", f"mission-audit-{safe}.json"


def _sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ResearchError(f"Mission audit {label} fingerprint is invalid.")
    return value


@dataclass(frozen=True, slots=True)
class ResearchMissionAuditExportPreview:
    """What confirming would write; nothing has been written."""

    plan_id: str
    research_run_id: str
    markdown_filename: str
    json_filename: str
    markdown_sha256: str
    json_sha256: str
    summary: str
    markdown_preview: str
    total_markdown_characters: int

    def __post_init__(self) -> None:
        if not isinstance(self.plan_id, str) or not self.plan_id.strip():
            raise ResearchError("Mission audit plan ID cannot be empty.")
        if (self.markdown_filename, self.json_filename) != mission_audit_filenames(
            self.plan_id
        ):
            raise ResearchError("Mission audit file names are invalid.")
        _sha256(self.markdown_sha256, "Markdown")
        _sha256(self.json_sha256, "JSON")


@dataclass(frozen=True, slots=True)
class ResearchMissionAuditExportResult:
    """The two new files created from one revalidated audit."""

    plan_id: str
    markdown_path: str
    json_path: str
    markdown_sha256: str
    json_sha256: str
    markdown_bytes: int
    json_bytes: int

    def __post_init__(self) -> None:
        _sha256(self.markdown_sha256, "Markdown")
        _sha256(self.json_sha256, "JSON")
        if self.markdown_bytes <= 0 or self.json_bytes <= 0:
            raise ResearchError("Mission audit export files cannot be empty.")
