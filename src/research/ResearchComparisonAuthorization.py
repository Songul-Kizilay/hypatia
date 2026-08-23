"""Explicit authorization for one authored source comparison note.

Authorizes the exact accepted sources being compared, the evidence and
assessments the comparison rests on, and the authored comparison text.

A comparison is a description, not a verdict. It selects no winner, ranks
nothing, promotes no source's trust, and verifies no claim. The domain's
existing 2-to-5 source bound is preserved rather than replaced.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.Exceptions import ResearchError

MAX_COMPARISON_AUTHORIZATION_TEXT_CHARACTERS = 2_000
MAX_COMPARISON_AUTHORIZATION_REFERENCES = 50


@dataclass(frozen=True, slots=True)
class ResearchComparisonAuthorization:
    """Exact compared sources, their references, and the authored note."""

    document_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    assessment_ids: tuple[str, ...]
    text: str

    def __post_init__(self) -> None:
        for values, label in (
            (self.document_ids, "document"),
            (self.evidence_ids, "evidence"),
            (self.assessment_ids, "assessment"),
        ):
            if not isinstance(values, tuple):
                raise ResearchError(
                    f"Comparison authorization {label} IDs must be an "
                    "immutable tuple."
                )
            if not values:
                raise ResearchError(
                    f"Comparison authorization requires at least one {label} ID."
                )
            if len(values) > MAX_COMPARISON_AUTHORIZATION_REFERENCES:
                raise ResearchError(
                    f"Comparison authorization has too many {label} IDs."
                )
            if not all(isinstance(value, str) and value.strip() for value in values):
                raise ResearchError(
                    f"Comparison authorization {label} ID cannot be empty."
                )
        if not isinstance(self.text, str) or not self.text.strip():
            raise ResearchError("Comparison authorization text cannot be empty.")
        text = self.text.strip()
        if len(text) > MAX_COMPARISON_AUTHORIZATION_TEXT_CHARACTERS:
            raise ResearchError("Comparison authorization text is too long.")
        object.__setattr__(
            self,
            "document_ids",
            tuple(value.strip() for value in self.document_ids),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            tuple(value.strip() for value in self.evidence_ids),
        )
        object.__setattr__(
            self,
            "assessment_ids",
            tuple(value.strip() for value in self.assessment_ids),
        )
        object.__setattr__(self, "text", text)
