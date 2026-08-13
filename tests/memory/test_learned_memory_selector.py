from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from memory.LearnedMemory import LearnedMemory
from memory.LearnedMemorySelector import LearnedMemorySelector


class RecordingLearnedMemorySelector:
    def __init__(self, result: tuple[LearnedMemory, ...]) -> None:
        self.result = result
        self.calls: list[tuple[str, tuple[LearnedMemory, ...]]] = []

    def select(
        self,
        *,
        source_text: str,
        memories: tuple[LearnedMemory, ...],
    ) -> tuple[LearnedMemory, ...]:
        self.calls.append((source_text, memories))
        return self.result


class LearnedMemorySelectorTests(unittest.TestCase):
    def test_structural_selector_preserves_exact_inputs_and_selected_identity(
        self,
    ) -> None:
        first = LearnedMemory(
            kind="preference",
            key="preferred_language",
            value="Python",
        )
        second = LearnedMemory(
            kind="goal",
            key="current_learning_goal",
            value="Kali Linux",
        )
        third = LearnedMemory(
            kind="project_fact",
            key="active_project",
            value="Hypatia",
        )
        memories = (first, second, third)
        selected = (third, first)
        recording_selector = RecordingLearnedMemorySelector(selected)
        selector: LearnedMemorySelector = recording_selector
        source_text = "  What should I work on?  \n"

        result = selector.select(source_text=source_text, memories=memories)

        self.assertEqual(recording_selector.calls, [(source_text, memories)])
        self.assertIs(recording_selector.calls[0][1], memories)
        self.assertIs(result, selected)
        self.assertIs(result[0], third)
        self.assertIs(result[1], first)

    def test_structural_selector_may_return_exact_empty_tuple(self) -> None:
        memory = LearnedMemory(
            kind="self_fact",
            key="note",
            value="  Preserve exact whitespace.  ",
        )
        memories = (memory,)
        empty_result: tuple[LearnedMemory, ...] = ()
        recording_selector = RecordingLearnedMemorySelector(empty_result)
        selector: LearnedMemorySelector = recording_selector
        source_text = "\tExact source text\t"

        result = selector.select(source_text=source_text, memories=memories)

        self.assertIs(result, empty_result)
        self.assertEqual(recording_selector.calls, [(source_text, memories)])
        self.assertIs(recording_selector.calls[0][1], memories)
        self.assertIs(recording_selector.calls[0][1][0], memory)


if __name__ == "__main__":
    unittest.main()
