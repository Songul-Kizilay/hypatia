"""Build immutable LLM conversation history from structured memory records."""

from llm.LLMConversationMessage import LLMConversationMessage
from memory.MemoryRecord import MemoryRecord


def build_llm_conversation_history(
    records: tuple[MemoryRecord, ...],
    session_id: str,
    max_turns: int | None = None,
) -> tuple[LLMConversationMessage, ...]:
    """Return ordered messages for valid conversations in the selected session."""

    if max_turns is not None and (
        isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns <= 0
    ):
        raise ValueError("max_turns must be a positive integer or None.")

    turns: list[tuple[LLMConversationMessage, LLMConversationMessage]] = []
    required_tags = {"brain", "conversation"}

    for record in records:
        if not required_tags.issubset(record.tags):
            continue
        if record.metadata.get("session_id") != session_id:
            continue

        user_message = record.metadata.get("user_message")
        assistant_message = record.metadata.get("assistant_message")
        if not isinstance(user_message, str) or not isinstance(assistant_message, str):
            continue

        turns.append(
            (
                LLMConversationMessage(role="user", content=user_message),
                LLMConversationMessage(
                    role="assistant",
                    content=assistant_message,
                ),
            )
        )

    selected_turns = turns if max_turns is None else turns[-max_turns:]
    return tuple(message for turn in selected_turns for message in turn)
