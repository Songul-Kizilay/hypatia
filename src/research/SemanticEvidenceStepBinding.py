"""Non-secret exact model destination and reviewed input bound into a plan."""

from dataclasses import dataclass

from core.Exceptions import ResearchError
from llm.LLMEndpointPolicy import validate_llm_endpoint


@dataclass(frozen=True, slots=True)
class SemanticEvidenceStepBinding:
    input_fingerprint: str
    endpoint: str
    model: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.input_fingerprint, str)
            or len(self.input_fingerprint) != 64
            or any(c not in "0123456789abcdef" for c in self.input_fingerprint)
            or not isinstance(self.endpoint, str)
            or len(self.endpoint) > 2048
            or any(c.isspace() for c in self.endpoint)
            or not isinstance(self.model, str)
            or not self.model.strip()
            or self.model != self.model.strip()
            or len(self.model) > 200
            or any(ord(c) < 32 for c in self.model)
        ):
            raise ResearchError("Semantic model binding is invalid.")
        try:
            validate_llm_endpoint(self.endpoint)
            self.endpoint.encode("utf-8")
            self.model.encode("utf-8")
        except ValueError:
            raise ResearchError("Semantic model destination is invalid.") from None

    def lines(self) -> tuple[str, ...]:
        return (
            f"Semantic model endpoint: {self.endpoint}",
            f"Semantic model: {self.model}",
            f"Reviewed input fingerprint: {self.input_fingerprint}",
            "One model/network attempt; proposals are not accepted evidence.",
        )
