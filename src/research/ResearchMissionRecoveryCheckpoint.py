"""Durable, non-content checkpoint for a bounded semantic research mission.

The checkpoint names only canonical predecessor records and accounting facts.  It
never persists an inspected preview, model proposal, or source body: those are
either already owned by their canonical stores or cannot safely be replayed.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError


@dataclass(frozen=True, slots=True)
class ResearchMissionRecoveryCheckpoint:
    """The persisted observations that can be re-derived without new authority."""

    discovery_id: str = ""
    acquired_urls: tuple[str, ...] = ()
    body_hashes: tuple[str, ...] = ()
    inspected_bytes: int = 0
    evidence_ids: tuple[str, ...] = ()
    assessment_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (
            self.acquired_urls,
            self.body_hashes,
            self.evidence_ids,
            self.assessment_ids,
        )
        if (
            not isinstance(self.discovery_id, str)
            or type(self.inspected_bytes) is not int
            or self.inspected_bytes < 0
            or not all(isinstance(value, tuple) for value in values)
            or any(
                not isinstance(item, str) or not item.strip()
                for value in values
                for item in value
            )
            or len(self.acquired_urls) != len(self.body_hashes)
            or len(self.acquired_urls) != len(set(self.acquired_urls))
            or len(self.evidence_ids) != len(set(self.evidence_ids))
            or len(self.assessment_ids) != len(set(self.assessment_ids))
            or any(
                len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in self.body_hashes
            )
        ):
            raise ResearchError("Mission recovery checkpoint is invalid.")
        object.__setattr__(self, "discovery_id", self.discovery_id.strip())
        for field in ("acquired_urls", "body_hashes", "evidence_ids", "assessment_ids"):
            object.__setattr__(
                self,
                field,
                tuple(value.strip() for value in getattr(self, field)),
            )
