"""Term-overlap ranking for ask_knowledge: no model, no I/O, pure comparison."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from cognition.KnowledgeRelevanceSearch import (
    rank_chunks_by_term_relevance,
    rank_chunks_for_conversation,
)
from knowledge.Chunk import Chunk


def chunk(content: str, document_id: str = "doc", index: int = 0) -> Chunk:
    return Chunk(
        document_id=document_id,
        index=index,
        content=content,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class RankChunksByTermRelevanceTests(unittest.TestCase):
    def test_a_natural_question_matches_a_chunk_that_never_quotes_it_back(self) -> None:
        """The exact problem this module exists to fix.

        `Search.find` would require the *entire* question to appear
        verbatim; a chunk that plainly answers it in different words never
        matches that way.
        """
        sqli_chunk = chunk(
            "SQL injection using the UNION keyword lets an attacker execute "
            "an additional SELECT statement."
        )

        result = rank_chunks_by_term_relevance(
            [sqli_chunk], "How does UNION-based SQL injection work?"
        )

        self.assertEqual(result, [sqli_chunk])

    def test_chunks_sharing_more_terms_rank_first(self) -> None:
        weak_match = chunk("SQL is a query language.", index=0)
        strong_match = chunk(
            "SQL injection via UNION appends an attacker SELECT.", index=1
        )

        result = rank_chunks_by_term_relevance(
            [weak_match, strong_match], "SQL injection UNION SELECT"
        )

        self.assertEqual(result, [strong_match, weak_match])

    def test_ties_preserve_original_relative_order(self) -> None:
        first = chunk("SQL injection basics.", index=0)
        second = chunk("SQL injection in depth.", index=1)

        result = rank_chunks_by_term_relevance([first, second], "SQL injection")

        self.assertEqual(result, [first, second])

    def test_a_chunk_sharing_no_terms_is_excluded(self) -> None:
        unrelated = chunk("The weather today is sunny and warm.")

        result = rank_chunks_by_term_relevance(
            [unrelated], "SQL injection UNION SELECT"
        )

        self.assertEqual(result, [])

    def test_technical_identifiers_survive_tokenization_intact(self) -> None:
        """ "UNION-based" is one token, not split into "union" and "based"."""
        hyphen_chunk = chunk("This is a UNION-based technique.")
        unrelated_but_split_words = chunk(
            "A union of workers voted, based on a prior agreement."
        )

        result = rank_chunks_by_term_relevance(
            [hyphen_chunk, unrelated_but_split_words], "UNION-based attacks"
        )

        self.assertEqual(result, [hyphen_chunk])

    def test_empty_chunk_list_returns_empty(self) -> None:
        self.assertEqual(rank_chunks_by_term_relevance([], "sql injection"), [])

    def test_unusable_query_matches_nothing_rather_than_raising(self) -> None:
        present = chunk("Anything at all.")

        self.assertEqual(rank_chunks_by_term_relevance([present], ""), [])
        self.assertEqual(rank_chunks_by_term_relevance([present], "   "), [])

    def test_case_differences_do_not_change_the_match(self) -> None:
        sqli_chunk = chunk("SQL INJECTION uses the UNION keyword.")

        result = rank_chunks_by_term_relevance([sqli_chunk], "sql injection union")

        self.assertEqual(result, [sqli_chunk])

    def test_a_stop_word_only_query_matches_nothing(self) -> None:
        """QA-confirmed gap: `ResearchQueryTerms.of()` falls back to a query's
        raw tokens when every token is a stop word, rather than an empty set
        (the right default for its own callers). Ranking by substring
        containment must not inherit that fallback: "is" and "it" are
        substrings of a huge fraction of ordinary prose, so without an
        explicit stop-word filter here, a content-free query like this would
        spuriously "match" and present unrelated content as grounded.
        """
        sqli_chunk = chunk(
            "SQL injection using the UNION keyword lets an attacker execute "
            "an additional SELECT statement."
        )
        unrelated = chunk("The weather today is sunny and warm.")

        result = rank_chunks_by_term_relevance([sqli_chunk, unrelated], "What is it?")

        self.assertEqual(result, [])

    def test_a_lone_short_non_technical_term_matches_nothing(self) -> None:
        """A two-character common acronym ("ip") is not a stop word, but it is
        a substring of huge numbers of unrelated words (e.g. "equip",
        "pipeline"); it must not count as a significant term by itself.
        """
        unrelated = chunk("The team will equip every pipeline with backups.")

        result = rank_chunks_by_term_relevance([unrelated], "ip")

        self.assertEqual(result, [])

    def test_one_significant_term_among_many_stop_words_still_matches(self) -> None:
        sqli_chunk = chunk(
            "SQL injection using the UNION keyword lets an attacker execute "
            "an additional SELECT statement."
        )

        result = rank_chunks_by_term_relevance(
            [sqli_chunk], "What is it that the UNION keyword does here?"
        )

        self.assertEqual(result, [sqli_chunk])


class ConversationRelevanceTests(unittest.TestCase):
    def test_subject_must_be_covered_even_when_a_generic_word_matches(self):
        source = chunk("You can find requests and keys in Burp Suite.")
        self.assertEqual(
            rank_chunks_for_conversation(
                [source], "Can you find my lost keys?", max_results=3
            ),
            [],
        )

    def test_substrings_are_not_topic_evidence(self):
        source = chunk("A family reunion and selection of food.")
        self.assertEqual(
            rank_chunks_for_conversation([source], "UNION SELECT", max_results=3), []
        )

    def test_empty_and_filler_queries_match_nothing(self):
        for query in ("", "   ", "What is it?", "YOU YOUR HELP FIND"):
            with self.subTest(query=query):
                self.assertEqual(
                    rank_chunks_for_conversation(
                        [chunk("You can find your SQL notes here.")],
                        query,
                        max_results=3,
                    ),
                    [],
                )

    def test_comparison_coverage_is_checked_after_result_limit(self):
        sql = chunk("SQL injection.")
        xss = chunk("XSS.")
        self.assertEqual(
            rank_chunks_for_conversation(
                [sql, xss], "SQL injection and XSS", max_results=1
            ),
            [],
        )
        self.assertEqual(
            rank_chunks_for_conversation(
                [sql, xss], "SQL injection and XSS", max_results=2
            ),
            [sql, xss],
        )

    def test_stable_ties_and_case_punctuation_preserve_identity(self):
        first = chunk("SQL injection via UNION SELECT.")
        second = chunk("SQL injection via UNION SELECT.")
        self.assertEqual(
            rank_chunks_for_conversation(
                [first, second], "Explain sql injection.", max_results=3
            ),
            [first],
        )

    def test_compound_identifiers_remain_intact(self):
        exact = chunk("ASP.NET and UNION-based SQL injection.")
        unrelated = chunk("An asp and a net, based on a union.")
        self.assertEqual(
            rank_chunks_for_conversation(
                [unrelated, exact], "ASP.NET UNION-based", max_results=3
            ),
            [exact],
        )

    def test_only_terms_in_the_excerpt_sent_to_the_model_can_match(self):
        hidden = chunk("ordinary text " * 50 + "SQL injection")
        visible = chunk("SQL injection " + "ordinary text " * 50)
        self.assertEqual(
            rank_chunks_for_conversation(
                [hidden, visible], "SQL injection", max_results=3
            ),
            [visible],
        )


if __name__ == "__main__":
    unittest.main()
