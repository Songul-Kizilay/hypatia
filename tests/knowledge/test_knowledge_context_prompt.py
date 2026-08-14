from __future__ import annotations

import unittest

from knowledge.Chunk import Chunk
from knowledge.KnowledgeCitation import KnowledgeCitation
from knowledge.KnowledgeContextPrompt import build_knowledge_context_prompt


class KnowledgeContextPromptTests(unittest.TestCase):
    def test_bounds_each_source_chunk_without_removing_its_citation(self) -> None:
        content = "x" * 650
        chunk = Chunk("document", 0, content, chunk_id="chunk")
        citation = KnowledgeCitation(
            document_id="document",
            document_title="Notes",
            source="C:/knowledge/notes.md",
            chunk_index=0,
            chunk_id="chunk",
        )

        prompt = build_knowledge_context_prompt("What is here?", [chunk], [citation])

        self.assertIn("Notes | C:/knowledge/notes.md | paragraph 1", prompt)
        self.assertIn("x" * 600 + "...", prompt)
        self.assertNotIn("x" * 601, prompt)
        self.assertIn("User question: What is here?", prompt)

    def test_rejects_mismatched_results_and_citations(self) -> None:
        with self.assertRaisesRegex(ValueError, "equal length"):
            build_knowledge_context_prompt("query", [Chunk("doc", 0, "text")], [])


if __name__ == "__main__":
    unittest.main()
