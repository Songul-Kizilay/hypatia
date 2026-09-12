"""A tentative model interpretation with two mechanically checked quotations."""

from dataclasses import dataclass, field
from enum import StrEnum

from core.Exceptions import ResearchError
from research.SemanticComparisonRequest import SemanticComparisonRequest


class SemanticComparisonRelation(StrEnum):
    POSSIBLE_AGREEMENT = "possible_agreement"
    POSSIBLE_CONFLICT = "possible_conflict"
    NOT_COMPARABLE = "not_comparable"


@dataclass(frozen=True, slots=True)
class SemanticComparisonCandidate:
    request: SemanticComparisonRequest = field(repr=False)
    relation: SemanticComparisonRelation
    left_quote: str = field(repr=False)
    right_quote: str = field(repr=False)
    rationale: str = field(repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.request, SemanticComparisonRequest)
            or not isinstance(self.relation, SemanticComparisonRelation)
            or not isinstance(self.rationale, str)
            or not self.rationale.strip()
            or len(self.rationale) > 500
        ):
            raise ResearchError("Invalid tentative comparison candidate.")
        for quote, record in zip(
            (self.left_quote, self.right_quote), self.request.evidence, strict=True
        ):
            if not isinstance(quote, str) or not quote.strip() or len(quote) > 800:
                raise ResearchError("Invalid comparison quotation.")
            start = record.excerpt.find(quote)
            if start < 0 or record.excerpt.find(quote, start + 1) >= 0:
                raise ResearchError("Comparison quotation is absent or ambiguous.")
        try:
            self.rationale.encode("utf-8")
        except ValueError:
            raise ResearchError("Invalid comparison rationale encoding.") from None

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(e.evidence_id for e in self.request.evidence)
