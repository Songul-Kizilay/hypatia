"""Immutable value object for a single learned memory."""

from dataclasses import dataclass
from typing import Literal

LearnedMemoryKind = Literal[
    "user_fact",
    "preference",
    "project_fact",
    "goal",
    "self_fact",
]


@dataclass(frozen=True)
class LearnedMemory:
    kind: LearnedMemoryKind
    key: str
    value: str
