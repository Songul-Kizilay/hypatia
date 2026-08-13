"""Immutable proposal for a learned memory and its exact source text."""

from dataclasses import dataclass

from memory.LearnedMemory import LearnedMemory


@dataclass(frozen=True)
class LearnedMemoryCandidate:
    memory: LearnedMemory
    source_text: str


@dataclass(frozen=True)
class LearnedMemoryCandidateBatch:
    source_text: str
    candidates: tuple[LearnedMemoryCandidate, ...]
