"""Validation tests for unaccepted research source candidates."""

from __future__ import annotations

import unittest

from core.Exceptions import ResearchError
from research.ResearchSourceCandidate import ResearchSourceCandidate


class ResearchSourceCandidateTests(unittest.TestCase):
    def test_normalizes_bounded_https_metadata(self) -> None:
        candidate = ResearchSourceCandidate(
            url="  https://example.com/paper?q=security  ",
            title="  Example\n paper  ",
            snippet="  Relevant\t summary.  ",
        )

        self.assertEqual(candidate.url, "https://example.com/paper?q=security")
        self.assertEqual(candidate.title, "Example paper")
        self.assertEqual(candidate.snippet, "Relevant summary.")

    def test_allows_an_empty_snippet_but_rejects_unsafe_urls(self) -> None:
        candidate = ResearchSourceCandidate(
            url="https://example.com",
            title="Example",
            snippet="   ",
        )
        self.assertEqual(candidate.snippet, "")

        for url in (
            "http://example.com",
            "https://user:secret@example.com",
            "https://example.com:8443",
            "https://example.com/path\nInjected",
            "https://",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ResearchError):
                    ResearchSourceCandidate(url=url, title="Example", snippet="")

    def test_rejects_oversized_metadata(self) -> None:
        values = (
            {
                "url": f"https://example.com/{'a' * 2_100}",
                "title": "Title",
                "snippet": "",
            },
            {"url": "https://example.com", "title": "a" * 501, "snippet": ""},
            {"url": "https://example.com", "title": "Title", "snippet": "a" * 1_001},
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ResearchError, "too long"):
                    ResearchSourceCandidate(**value)


if __name__ == "__main__":
    unittest.main()
