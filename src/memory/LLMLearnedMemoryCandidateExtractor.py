"""Provider-backed learned-memory candidate extraction boundary."""

from llm.LLMProvider import LLMError, LLMProvider
from memory.LearnedMemoryCandidate import LearnedMemoryCandidateBatch
from memory.LearnedMemoryCandidateExtractionError import (
    LearnedMemoryCandidateExtractionError,
)
from memory.LearnedMemoryCandidateParser import (
    parse_learned_memory_candidate_batch,
)
from memory.LearnedMemoryCandidatePrompt import (
    build_learned_memory_candidate_prompt,
)


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
            payload = self._provider.generate(prompt, ())
            return parse_learned_memory_candidate_batch(
                source_text=source_text,
                payload=payload,
            )
        except (LLMError, ValueError) as error:
            raise LearnedMemoryCandidateExtractionError(
                "Learned memory candidate extraction failed."
            ) from error
