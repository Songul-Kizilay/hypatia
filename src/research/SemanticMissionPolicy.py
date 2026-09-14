"""Digest-bound envelope for later-selected evidence from this mission only."""

from dataclasses import dataclass

from core.Exceptions import ResearchError
from llm.LLMEndpointPolicy import is_loopback_llm_endpoint
from research.ResearchDisclosure import ResearchDisclosure
from research.SemanticEvidenceStepBinding import SemanticEvidenceStepBinding


@dataclass(frozen=True, slots=True)
class SemanticMissionPolicy:
    endpoint: str
    model: str
    disclosure: ResearchDisclosure
    max_input_bytes: int = 8192
    input_scope: str = "own_recorded_evidence_from_selected_provider"
    selection: str = "first_two_then_first_and_one_new_source"
    retention: str = "source_backed_evidence_tentative_notes_and_opted_in_lessons"

    def __post_init__(self) -> None:
        SemanticEvidenceStepBinding("0" * 64, self.endpoint, self.model)
        if (
            not isinstance(self.disclosure, ResearchDisclosure)
            or not self.disclosure.permits_model_call
            or (
                not is_loopback_llm_endpoint(self.endpoint)
                and not self.disclosure.permits_remote_endpoint
            )
            or type(self.max_input_bytes) is not int
            or not 1 <= self.max_input_bytes <= 8192
            or self.input_scope != "own_recorded_evidence_from_selected_provider"
            or self.selection != "first_two_then_first_and_one_new_source"
            or self.retention
            != "source_backed_evidence_tentative_notes_and_opted_in_lessons"
        ):
            raise ResearchError("Invalid bounded semantic mission policy.")

    def lines(self) -> tuple[str, ...]:
        return (
            f"Approved model: {self.endpoint}; {self.model}; {self.disclosure.value}.",
            "Disclosure: question and two mission-owned recorded excerpts per call; "
            f"maximum {self.max_input_bytes} UTF-8 bytes; maximum two calls.",
            "Only selected-provider public HTTPS sources; maximum three sources; "
            "one optional follow-up, no retries or dynamic authority expansion.",
            "Retain source-backed evidence and labelled tentative comparison notes; "
            "retain/recall advisory research lessons only if failure memory "
            "is enabled. "
            "No model interpretation becomes a verified fact.",
        )
