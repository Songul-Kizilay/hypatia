"""An unaccepted semantic proposal with an exact, source-bound quotation."""

from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from research.ResearchSourcePreview import ResearchSourcePreview


@dataclass(frozen=True, slots=True)
class SemanticEvidenceCandidate:
    preview: ResearchSourcePreview = field(repr=False)
    start: int
    end: int
    rationale: str = field(repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.preview, ResearchSourcePreview)
            or type(self.start) is not int
            or type(self.end) is not int
            or not 0 <= self.start < self.end <= len(self.preview.source.content)
            or self.end - self.start > 800
            or not isinstance(self.rationale, str)
            or not self.rationale.strip()
            or len(self.rationale) > 500
        ):
            raise ResearchError("Semantic evidence candidate is invalid.")
        try:
            self.rationale.encode("utf-8")
        except UnicodeError:
            raise ResearchError("Semantic evidence candidate is invalid.") from None

    @property
    def quote(self) -> str:
        return self.preview.source.content[self.start : self.end]
