"""Tests for deterministic, non-executing research HTML extraction."""

from __future__ import annotations

import unittest

from core.Exceptions import ResearchError
from research.ResearchHtmlExtractor import ResearchHtmlExtractor


class ResearchHtmlExtractorTests(unittest.TestCase):
    def test_extracts_title_and_readable_blocks_without_active_content(self) -> None:
        parser = ResearchHtmlExtractor()
        parser.feed(
            "<html><head><title> Hypatia Research </title>"
            "<style>hidden style</style><script>hidden script</script></head>"
            "<body><main><h1>Finding</h1><p>Evidence <b>matters</b>.</p>"
            "<noscript>hidden fallback</noscript></main></body></html>"
        )
        parser.close()

        title, content = parser.extracted()

        self.assertEqual(title, "Hypatia Research")
        self.assertEqual(content, "Finding\n\nEvidence matters.")
        self.assertNotIn("hidden", content)

    def test_rejects_html_without_readable_text(self) -> None:
        parser = ResearchHtmlExtractor()
        parser.feed("<html><head><title>Only title</title></head></html>")

        with self.assertRaisesRegex(ResearchError, "readable text"):
            parser.extracted()


if __name__ == "__main__":
    unittest.main()
