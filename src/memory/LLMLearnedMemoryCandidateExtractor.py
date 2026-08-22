"""Provider-backed learned-memory candidate extraction boundary."""

from typing import Protocol, runtime_checkable

from llm.LLMConversationMessage import LLMConversationMessage
from llm.LLMProvider import LLMError, LLMProvider
from memory.LearnedMemoryCandidate import LearnedMemoryCandidateBatch
from memory.LearnedMemoryCandidateExtractionError import (
    LearnedMemoryCandidateExtractionError,
)
from memory.LearnedMemoryCandidateParser import (
    parse_learned_memory_candidate_batch,
)
from memory.LearnedMemoryCandidatePrompt import (
    EXTRACTION_MAX_TOKENS,
    LEARNED_MEMORY_EXTRACTION_SYSTEM_INSTRUCTION,
    build_learned_memory_candidate_prompt,
    build_learned_memory_candidate_response_schema,
)


@runtime_checkable
class _StructuredJSONLLMProvider(Protocol):
    def generate_json(
        self,
        prompt: str,
        history: tuple[LLMConversationMessage, ...] = (),
        *,
        system_instruction: str | None = None,
        max_tokens: int = 512,
        response_schema: dict[str, object] | None = None,
    ) -> str: ...


class LLMLearnedMemoryCandidateExtractor:
    """Compose the learned-memory prompt, provider, and parser contracts."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def extract(
        self,
        source_text: str,
    ) -> LearnedMemoryCandidateBatch:
        prompt = build_learned_memory_candidate_prompt(source_text)
        try:
            if isinstance(self._provider, _StructuredJSONLLMProvider):
                payload = self._provider.generate_json(
                    prompt,
                    (),
                    system_instruction=LEARNED_MEMORY_EXTRACTION_SYSTEM_INSTRUCTION,
                    max_tokens=EXTRACTION_MAX_TOKENS,
                    response_schema=build_learned_memory_candidate_response_schema(),
                )
            else:
                payload = self._provider.generate(prompt, ())
            return parse_learned_memory_candidate_batch(
                source_text=source_text,
                payload=payload,
            )
        except (LLMError, ValueError) as error:
            raise LearnedMemoryCandidateExtractionError(
                "Learned memory candidate extraction failed."
            ) from error
