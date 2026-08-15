"""Headless unit coverage for desktop-only presentation helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from desktop.TkinterDesktopWindow import _format_citations
from knowledge.KnowledgeCitation import KnowledgeCitation


class CitationFormattingTests(unittest.TestCase):
    def test_formats_existing_citations_in_response_order(self) -> None:
        citations = [
            KnowledgeCitation(
                document_id="project-notes",
                document_title="Project Notes",
                source="C:/knowledge/project.md",
                chunk_index=2,
                chunk_id="project-notes:2",
            ),
            KnowledgeCitation(
                document_id="ideas",
                document_title="Ideas",
                source="C:/knowledge/ideas.txt",
                chunk_index=0,
                chunk_id="ideas:0",
            ),
        ]

        rendered = _format_citations(citations)

        self.assertEqual(
            rendered,
            "1. Project Notes — C:/knowledge/project.md "
            "(paragraph 3; project-notes:2)\n"
            "2. Ideas — C:/knowledge/ideas.txt (paragraph 1; ideas:0)",
        )

    def test_uses_a_safe_source_fallback_and_keeps_empty_responses_empty(self) -> None:
        citation = KnowledgeCitation(
            document_id="untitled",
            document_title="(untitled)",
            source="",
            chunk_index=0,
            chunk_id="untitled:0",
        )

        self.assertEqual(_format_citations([]), "")
        self.assertEqual(
            _format_citations([citation]),
            "1. (untitled) — local source unavailable (paragraph 1; untitled:0)",
        )
