"""Immutable message value object for LLM conversation history."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LLMConversationMessage:
    role: Literal["user", "assistant"]
    content: str
