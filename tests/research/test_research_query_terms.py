"""Tests that query normalisation keeps the parts of a question worth matching.

The failure these guard against is the ordinary one: a normaliser tuned for
prose meets a security question and destroys precisely the tokens that made it
specific. Every identifier below is one a person would actually type.
"""

from __future__ import annotations

import unittest

from core.Exceptions import ResearchError
from research.ResearchQueryTerms import (
    MAX_QUERY_TERMS,
    ResearchQueryTerms,
    is_technical_term,
    normalized_terms,
)


class ResearchQueryTermTests(unittest.TestCase):
    def test_keeps_a_cve_identifier_as_one_term(self) -> None:
        terms = ResearchQueryTerms.of("CVE-2026-12345 exploitation")

        self.assertIn("cve-2026-12345", terms.terms)
        self.assertNotIn("cve", terms.terms)
        self.assertNotIn("2026", terms.terms)

    def test_keeps_dotted_framework_names_whole(self) -> None:
        terms = ResearchQueryTerms.of("Next.js and ASP.NET request handling")

        self.assertIn("next.js", terms.terms)
        self.assertIn("asp.net", terms.terms)
        for fragment in ("next", "js", "asp", "net"):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, terms.terms)

    def test_keeps_version_numbers_and_slashed_protocols(self) -> None:
        terms = ResearchQueryTerms.of("OAuth 2.0 over HTTP/2")

        self.assertIn("2.0", terms.terms)
        self.assertIn("http/2", terms.terms)

    def test_classifies_acronyms_from_how_they_were_written(self) -> None:
        terms = ResearchQueryTerms.of("JWT and SQL injection in a service")

        self.assertIn("jwt", terms.technical_terms)
        self.assertIn("sql", terms.technical_terms)
        self.assertNotIn("injection", terms.technical_terms)

    def test_a_lowercase_acronym_is_still_a_matchable_term(self) -> None:
        """Folding decides matching; the written form decides specificity."""
        terms = ResearchQueryTerms.of("jwt replay")

        self.assertIn("jwt", terms.terms)
        self.assertNotIn("jwt", terms.technical_terms)

    def test_identifiers_are_technical_and_ordinary_words_are_not(self) -> None:
        for term in ("CVE-2026-1", "Next.js", "log4j", "C++", "XSS", "HTTP/2"):
            with self.subTest(technical=term):
                self.assertTrue(is_technical_term(term))
        for term in ("injection", "analysis", "the", "a", "attacks"):
            with self.subTest(ordinary=term):
                self.assertFalse(is_technical_term(term))

    def test_removes_function_words_that_carry_no_subject(self) -> None:
        terms = ResearchQueryTerms.of("the impact of caching on the web")

        for word in ("the", "of", "on"):
            with self.subTest(word=word):
                self.assertNotIn(word, terms.terms)
        self.assertIn("caching", terms.terms)

    def test_a_query_of_only_function_words_keeps_them(self) -> None:
        """Ranking against nothing would be worse than ranking against this."""
        terms = ResearchQueryTerms.of("the of in")

        self.assertEqual(terms.terms, ("the", "of", "in"))

    def test_freshness_words_state_intent_rather_than_subject(self) -> None:
        terms = ResearchQueryTerms.of("latest request smuggling research")

        self.assertTrue(terms.freshness_intent)
        self.assertNotIn("latest", terms.terms)
        self.assertIn("smuggling", terms.terms)

    def test_a_bare_year_states_freshness_and_leaves_the_subject(self) -> None:
        terms = ResearchQueryTerms.of("prototype pollution 2026")

        self.assertTrue(terms.freshness_intent)
        self.assertEqual(terms.freshness_year, 2026)
        self.assertNotIn("2026", terms.terms)

    def test_a_year_inside_an_identifier_is_not_a_freshness_year(self) -> None:
        terms = ResearchQueryTerms.of("CVE-2026-12345 analysis")

        self.assertFalse(terms.freshness_intent)
        self.assertIsNone(terms.freshness_year)

    def test_ambiguous_words_do_not_claim_freshness(self) -> None:
        """`new` and `modern` name subjects at least as often as they ask for news."""
        for query in ("new york phishing", "modern cryptography"):
            with self.subTest(query=query):
                self.assertFalse(ResearchQueryTerms.of(query).freshness_intent)

    def test_no_freshness_intent_by_default(self) -> None:
        self.assertFalse(ResearchQueryTerms.of("sql injection").freshness_intent)

    def test_nothing_is_stemmed_to_a_root(self) -> None:
        terms = ResearchQueryTerms.of("injections injector injecting")

        self.assertEqual(terms.terms, ("injections", "injector", "injecting"))

    def test_repeated_terms_collapse_and_keep_their_order(self) -> None:
        terms = ResearchQueryTerms.of("smuggling request smuggling")

        self.assertEqual(terms.terms, ("smuggling", "request"))

    def test_phrases_are_the_adjacent_pairs_of_the_question(self) -> None:
        terms = ResearchQueryTerms.of("http request smuggling")

        self.assertEqual(
            terms.phrases, (("http", "request"), ("request", "smuggling"))
        )

    def test_surrounding_punctuation_is_trimmed_but_interior_is_kept(self) -> None:
        terms = ResearchQueryTerms.of('"Next.js", (CVE-2026-12345);')

        self.assertEqual(terms.terms, ("next.js", "cve-2026-12345"))

    def test_a_very_long_question_is_bounded(self) -> None:
        terms = ResearchQueryTerms.of(" ".join(f"term{index}" for index in range(80)))

        self.assertEqual(len(terms.terms), MAX_QUERY_TERMS)

    def test_an_empty_question_is_refused_rather_than_ranked(self) -> None:
        for query in ("", "   ", None, 5):
            with self.subTest(query=query):
                with self.assertRaises(ResearchError):
                    ResearchQueryTerms.of(query)  # type: ignore[arg-type]

    def test_record_terms_are_folded_the_same_way_as_query_terms(self) -> None:
        self.assertEqual(
            normalized_terms('  "CVE-2026-12345":  Next.js  '),
            ("cve-2026-12345", "next.js"),
        )

    def test_a_technical_term_must_also_be_a_query_term(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchQueryTerms(
                terms=("smuggling",),
                technical_terms=frozenset({"cve-2026-12345"}),
                phrases=(),
                freshness_intent=False,
                freshness_year=None,
            )


if __name__ == "__main__":
    unittest.main()
