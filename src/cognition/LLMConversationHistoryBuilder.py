"""Build immutable LLM conversation history from structured memory records."""

from llm.LLMConversationMessage import LLMConversationMessage
from memory.MemoryRecord import MemoryRecord


def build_llm_conversation_history(
    records: tuple[MemoryRecord, ...],
    session_id: str,
) -> tuple[LLMConversationMessage, ...]:
    """Return ordered messages for valid conversations in the selected session."""

    history: list[LLMConversationMessage] = []
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

        history.extend(
            (
                LLMConversationMessage(role="user", content=user_message),
                LLMConversationMessage(
                    role="assistant",
                    content=assistant_message,
                ),
            )
        )

    return tuple(history)
