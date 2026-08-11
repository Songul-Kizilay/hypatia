from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import MappingProxyType

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cognition.LLMConversationHistoryBuilder import (
    build_llm_conversation_history,
)
from llm.LLMConversationMessage import LLMConversationMessage
from memory.MemoryRecord import MemoryRecord


class LLMConversationHistoryBuilderTests(unittest.TestCase):
    def test_builds_ordered_same_session_history_and_ignores_other_records(
        self,
    ) -> None:
        first = MemoryRecord(
            memory_id="first",
            content="content is not parsed",
            metadata=MappingProxyType(
                {
                    "session_id": "session-a",
                    "user_message": "  My name is Songül.  ",
                    "assistant_message": "  Nice to meet you.  ",
                }
            ),
            tags=frozenset({"brain", "conversation"}),
        )
        other_session = MemoryRecord(
            memory_id="other-session",
            content="unrelated",
            metadata=MappingProxyType(
                {
                    "session_id": "session-b",
                    "user_message": "Other user",
                    "assistant_message": "Other assistant",
                }
            ),
            tags=frozenset({"brain", "conversation"}),
        )
        missing_conversation_tag = MemoryRecord(
            memory_id="not-conversation",
            content="unrelated",
            metadata=MappingProxyType(
                {
                    "session_id": "session-a",
                    "user_message": "Not included",
                    "assistant_message": "Not included",
                }
            ),
            tags=frozenset({"brain"}),
        )
        legacy = MemoryRecord(
            memory_id="legacy",
            content="User: legacy\nHypatia: must not be parsed",
            metadata=MappingProxyType({"session_id": "session-a"}),
            tags=frozenset({"brain", "conversation"}),
        )
        second = MemoryRecord(
            memory_id="second",
            content="content is not parsed",
            metadata=MappingProxyType(
                {
                    "session_id": "session-a",
                    "user_message": "What is my name?",
                    "assistant_message": "Your name is Songül.",
                }
            ),
            tags=frozenset({"brain", "conversation", "extra"}),
        )
        records = (
            first,
            other_session,
            missing_conversation_tag,
            legacy,
            second,
        )

        history = build_llm_conversation_history(records, "session-a")

        self.assertEqual(
            history,
            (
                LLMConversationMessage(
                    role="user",
                    content="  My name is Songül.  ",
                ),
                LLMConversationMessage(
                    role="assistant",
                    content="  Nice to meet you.  ",
                ),
                LLMConversationMessage(
                    role="user",
                    content="What is my name?",
                ),
                LLMConversationMessage(
                    role="assistant",
                    content="Your name is Songül.",
                ),
            ),
        )
        self.assertEqual(
            records,
            (
                first,
                other_session,
                missing_conversation_tag,
                legacy,
                second,
            ),
        )

    def test_ignores_records_with_non_string_structured_messages(self) -> None:
        records = (
            MemoryRecord(
                memory_id="invalid-user",
                content="ignored",
                metadata=MappingProxyType(
                    {
                        "session_id": "session-a",
                        "user_message": 123,
                        "assistant_message": "assistant",
                    }
                ),
                tags=frozenset({"brain", "conversation"}),
            ),
            MemoryRecord(
                memory_id="invalid-assistant",
                content="ignored",
                metadata=MappingProxyType(
                    {
                        "session_id": "session-a",
                        "user_message": "user",
                        "assistant_message": None,
                    }
                ),
                tags=frozenset({"brain", "conversation"}),
            ),
        )

        self.assertEqual(
            build_llm_conversation_history(records, "session-a"),
            (),
        )


if __name__ == "__main__":
    unittest.main()
