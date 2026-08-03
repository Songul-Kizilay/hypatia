"""Unit tests for plain-text Search."""

from __future__ import annotations

import unittest

from core.Exceptions import KnowledgeError
from knowledge.Chunk import Chunk
from knowledge.Indexer import Indexer
from knowledge.Search import Search


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        indexer = Indexer()
        self.first = Chunk(document_id="document", index=0, content="Hello Hypatia")
        self.second = Chunk(document_id="document", index=1, content="Hypatia World")
        self.third = Chunk(document_id="document", index=2, content="Other content")
        for chunk in (self.first, self.second, self.third):
            indexer.add(chunk)
        self.search = Search(indexer)

    def test_find_is_case_insensitive_and_preserves_order(self) -> None:
        results = self.search.find("hYpAtIa")

        self.assertEqual(results, [self.first, self.second])

    def test_find_returns_empty_list_when_no_match_exists(self) -> None:
        self.assertEqual(self.search.find("missing"), [])

    def test_find_first_returns_first_match(self) -> None:
        self.assertIs(self.search.find_first("hypatia"), self.first)

    def test_find_first_returns_none_when_no_match_exists(self) -> None:
        self.assertIsNone(self.search.find_first("missing"))

    def test_exists_reports_matching_content(self) -> None:
        self.assertTrue(self.search.exists("world"))
        self.assertFalse(self.search.exists("missing"))

    def test_rejects_blank_or_none_query(self) -> None:
        with self.assertRaises(KnowledgeError):
            self.search.find(" ")
        with self.assertRaises(KnowledgeError):
            self.search.find(None)
