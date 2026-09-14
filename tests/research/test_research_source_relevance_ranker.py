"""Deterministic relevance ranking, and the six things it must never become.

The ranking is the easy part to test and the wrong part to trust. What matters
more is the list of things ranking is not allowed to do on the way to producing
a better order: accept a source, fetch one, consult a model, turn a match into
evidence, mangle an identifier, or quietly merge two results because their
titles look alike. Those six are named below as regressions A to F, because each
of them is a way this feature could turn into a different and more dangerous
feature without anybody deciding to.
"""

from __future__ import annotations

import ast
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
for entry in (SRC_DIR, ROOT_DIR):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from core.Exceptions import ResearchError
from research.RankedResearchSourceDiscovery import ranked_candidates, unranked
from research.ResearchRelevanceCategory import ResearchRelevanceCategory
from research.ResearchRelevanceReason import ResearchRelevanceReason
from research.ResearchRelevanceWeights import ResearchRelevanceWeights
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.ResearchSourceDiscoveryRecord import ResearchSourceDiscoveryRecord
from research.ResearchSourceRelevanceRanker import ResearchSourceRelevanceRanker
from tests.SourceVocabulary import mentions, working_vocabulary

RANKER_SOURCE = (SRC_DIR / "research" / "ResearchSourceRelevanceRanker.py").read_text(
    encoding="utf-8"
)
TERMS_SOURCE = (SRC_DIR / "research" / "ResearchQueryTerms.py").read_text(
    encoding="utf-8"
)


def candidate(
    title: str,
    *,
    doi: str = "",
    year: int | None = None,
    venue: str = "",
) -> ResearchSourceCandidate:
    return ResearchSourceCandidate(
        url=f"https://doi.org/10.1000/{doi or abs(hash(title)) % 1_000_000}",
        title=title,
        snippet="",
        container=venue,
        published_year=year,
    )


def titles(ranked: tuple) -> list[str]:
    return [entry.candidate.title for entry in ranked]


class RelevanceRankingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ranker = ResearchSourceRelevanceRanker()

    def test_a_specific_match_outranks_a_generic_survey(self) -> None:
        results = self.ranker.rank(
            "request smuggling in Next.js",
            [
                candidate("A general survey of software analysis methods"),
                candidate("Request smuggling in Next.js middleware"),
            ],
        )

        self.assertEqual(
            results[0].candidate.title, "Request smuggling in Next.js middleware"
        )
        self.assertEqual(results[0].provider_rank, 2)
        self.assertEqual(results[0].relevance_rank, 1)

    def test_the_provider_position_survives_being_reordered(self) -> None:
        """A fault in ranking must stay distinguishable from a fault upstream."""
        results = self.ranker.rank(
            "sql injection",
            [candidate("Unrelated work"), candidate("SQL injection defences")],
        )

        self.assertEqual(sorted(entry.provider_rank for entry in results), [1, 2])
        self.assertEqual([entry.relevance_rank for entry in results], [1, 2])

    def test_matching_a_technical_identifier_beats_matching_common_words(self) -> None:
        results = self.ranker.rank(
            "CVE-2026-12345 remote code execution",
            [
                candidate("Remote code execution: a broad review"),
                candidate("Analysis of CVE-2026-12345"),
            ],
        )

        self.assertEqual(results[0].candidate.title, "Analysis of CVE-2026-12345")
        self.assertIn(
            ResearchRelevanceReason.TECHNICAL_IDENTIFIER_MATCHED,
            results[0].relevance.reasons,
        )
        self.assertIn(
            ResearchRelevanceReason.TECHNICAL_IDENTIFIER_MISSING,
            results[1].relevance.reasons,
        )

    def test_adjacent_query_words_score_above_scattered_ones(self) -> None:
        together, apart = self.ranker.rank(
            "request smuggling",
            [
                candidate("A request for better smuggling of goods across borders"),
                candidate("Request smuggling"),
            ],
        )

        self.assertEqual(together.candidate.title, "Request smuggling")
        self.assertIn(
            ResearchRelevanceReason.QUERY_PHRASE_IN_TITLE, together.relevance.reasons
        )
        self.assertNotIn(
            ResearchRelevanceReason.QUERY_PHRASE_IN_TITLE, apart.relevance.reasons
        )

    def test_a_matching_venue_helps_but_does_not_decide(self) -> None:
        results = self.ranker.rank(
            "phishing detection",
            [
                candidate("Phishing detection with heuristics", venue="Nature"),
                candidate("An unrelated study", venue="Journal of Phishing Detection"),
            ],
        )

        self.assertEqual(
            results[0].candidate.title, "Phishing detection with heuristics"
        )
        self.assertIn(
            ResearchRelevanceReason.QUERY_TERM_IN_VENUE, results[1].relevance.reasons
        )

    def test_a_missing_venue_is_unknown_rather_than_a_penalty(self) -> None:
        with_venue, without_venue = self.ranker.rank(
            "phishing detection",
            [
                candidate("Phishing detection", venue="Journal of Security"),
                candidate("Phishing detection", venue=""),
            ],
        )

        self.assertEqual(with_venue.relevance.score, without_venue.relevance.score)
        self.assertFalse(without_venue.relevance.component("venue_terms").applicable)

    def test_newer_is_not_rewarded_when_recency_was_not_asked_for(self) -> None:
        """The paper that first described an attack is usually the oldest one."""
        results = self.ranker.rank(
            "request smuggling",
            [
                candidate("Request smuggling", doi="old", year=2005),
                candidate("Request smuggling", doi="new", year=2026),
            ],
        )

        self.assertEqual([entry.provider_rank for entry in results], [1, 2])
        for entry in results:
            with self.subTest(year=entry.candidate.published_year):
                self.assertFalse(entry.relevance.component("recency").applicable)
                self.assertIn(
                    ResearchRelevanceReason.RECENCY_NOT_REQUESTED,
                    entry.relevance.reasons,
                )

    def test_recency_applies_only_once_the_question_asks_for_it(self) -> None:
        results = self.ranker.rank(
            "latest request smuggling",
            [
                candidate("Request smuggling", doi="old", year=2005),
                candidate("Request smuggling", doi="new", year=2026),
            ],
        )

        self.assertEqual(results[0].candidate.published_year, 2026)
        self.assertIn(
            ResearchRelevanceReason.NEWER_THAN_OTHER_RESULTS,
            results[0].relevance.reasons,
        )
        self.assertIn(
            ResearchRelevanceReason.OLDER_THAN_OTHER_RESULTS,
            results[1].relevance.reasons,
        )

    def test_recency_says_so_when_the_year_is_unknown(self) -> None:
        results = self.ranker.rank(
            "latest phishing",
            [candidate("Phishing", doi="a", year=2026), candidate("Phishing", doi="b")],
        )

        self.assertIn(
            ResearchRelevanceReason.PUBLICATION_YEAR_UNKNOWN,
            results[-1].relevance.reasons,
        )
        self.assertFalse(results[-1].relevance.component("recency").applicable)

    def test_recency_compares_within_the_results_and_needs_no_clock(self) -> None:
        """Ranking the same inputs must give the same answer next year."""
        vocabulary = working_vocabulary(RANKER_SOURCE, "_recency", "rank", "_measure")

        # Whole words, not substrings: `publication_year_unknown` contains
        # `now`, and a guard that reads that as a clock call is a guard that
        # fails for the wrong reason and gets loosened by the next person.
        for forbidden in (
            "now",
            "utcnow",
            "today",
            "datetime",
            "date",
            "time",
            "clock",
            "monotonic",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, vocabulary)

    def test_one_year_shared_by_every_result_discriminates_nothing(self) -> None:
        results = self.ranker.rank(
            "latest phishing",
            [
                candidate("Phishing", doi="a", year=2026),
                candidate("Phishing", doi="b", year=2026),
            ],
        )

        for entry in results:
            with self.subTest(rank=entry.relevance_rank):
                self.assertFalse(entry.relevance.component("recency").applicable)

    def test_ties_fall_back_to_the_order_the_provider_chose(self) -> None:
        results = self.ranker.rank(
            "phishing",
            [candidate("Phishing", doi="a"), candidate("Phishing", doi="b")],
        )

        self.assertEqual([entry.provider_rank for entry in results], [1, 2])

    def test_ranking_the_same_inputs_twice_gives_the_same_order(self) -> None:
        candidates = [
            candidate("Request smuggling in Next.js", doi="a", year=2024),
            candidate("A survey of proxies", doi="b", year=2019),
            candidate("Smuggling requests through HTTP/2", doi="c", year=2021),
        ]

        first = titles(self.ranker.rank("request smuggling", candidates))
        second = titles(self.ranker.rank("request smuggling", candidates))

        self.assertEqual(first, second)

    def test_a_query_matching_nothing_still_returns_every_candidate(self) -> None:
        results = self.ranker.rank(
            "quantum gravity",
            [candidate("Phishing"), candidate("Smuggling")],
        )

        self.assertEqual(len(results), 2)
        for entry in results:
            with self.subTest(title=entry.candidate.title):
                self.assertEqual(
                    entry.relevance.category, ResearchRelevanceCategory.UNRELATED
                )
                self.assertIn(
                    ResearchRelevanceReason.NO_QUERY_TERM_IN_TITLE,
                    entry.relevance.reasons,
                )

    def test_nothing_discovered_ranks_to_nothing(self) -> None:
        self.assertEqual(self.ranker.rank("phishing", []), ())

    def test_more_candidates_than_a_discovery_can_hold_are_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.ranker.rank(
                "phishing", [candidate(f"P{n}", doi=str(n)) for n in range(11)]
            )

    def test_an_unusable_query_is_refused_rather_than_scored_as_zero(self) -> None:
        with self.assertRaises(ResearchError):
            self.ranker.rank("   ", [candidate("Phishing")])

    def test_specificity_is_what_decides_between_one_identifier_and_three_words(
        self,
    ) -> None:
        """Set identifiers level with common words and the generic title wins."""
        query = "CVE-2026-12345 remote code execution"
        candidates = [
            candidate("Remote code execution: a broad review", doi="a"),
            candidate("Analysis of CVE-2026-12345", doi="b"),
        ]

        specific = ResearchSourceRelevanceRanker().rank(query, candidates)
        flattened = ResearchSourceRelevanceRanker(
            ResearchRelevanceWeights(technical_term_specificity=1.0)
        ).rank(query, candidates)

        self.assertEqual(specific[0].candidate.title, "Analysis of CVE-2026-12345")
        self.assertEqual(
            flattened[0].candidate.title, "Remote code execution: a broad review"
        )

    def test_invalid_weights_are_refused_at_construction(self) -> None:
        with self.assertRaises(ResearchError):
            ResearchSourceRelevanceRanker("heavier on titles")  # type: ignore[arg-type]

    def test_a_plural_matches_its_singular_but_a_root_is_never_taken(self) -> None:
        matched, unmatched = self.ranker.rank(
            "injection attack",
            [
                candidate("Injections and attacks", doi="a"),
                candidate("Injector attaching", doi="b"),
            ],
        )

        self.assertEqual(matched.candidate.title, "Injections and attacks")
        self.assertIn(
            ResearchRelevanceReason.ALL_QUERY_TERMS_IN_TITLE, matched.relevance.reasons
        )
        self.assertIn(
            ResearchRelevanceReason.NO_QUERY_TERM_IN_TITLE, unmatched.relevance.reasons
        )


class RelevanceSecurityRegressionTests(unittest.TestCase):
    """The six ways this feature could become a different feature."""

    def setUp(self) -> None:
        self.ranker = ResearchSourceRelevanceRanker()

    def test_case_a_ranking_never_accepts_a_source(self) -> None:
        vocabulary = working_vocabulary(RANKER_SOURCE, "rank", "_measure")

        for forbidden in ("accept", "fetch", "load", "evidence", "claim", "store"):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])

    def test_case_b_ranking_reaches_no_network(self) -> None:
        tree = ast.parse(RANKER_SOURCE)
        imported = {
            name.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for name in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }

        for forbidden in ("urllib", "http", "socket", "requests", "ssl"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, imported)

    def test_case_c_ranking_consults_no_model(self) -> None:
        """Ranking that needed a model would be ranking that could be skipped."""
        for name, source in (("ranker", RANKER_SOURCE), ("terms", TERMS_SOURCE)):
            vocabulary = working_vocabulary(source, *_function_names(source))
            for forbidden in ("llm", "model", "prompt", "completion", "temperature"):
                with self.subTest(source=name, forbidden=forbidden):
                    self.assertEqual(mentions(vocabulary, forbidden), [])

    def test_case_d_relevance_never_becomes_reputation_or_truth(self) -> None:
        vocabulary = working_vocabulary(RANKER_SOURCE, "rank", "_measure")

        for forbidden in (
            "reputation",
            "trust",
            "confidence",
            "verified",
            "corroborat",
            "reliab",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertEqual(mentions(vocabulary, forbidden), [])

    def test_case_d_ranking_returns_the_candidate_it_was_given(self) -> None:
        """A score is an annotation. It is not a new version of the source."""
        original = candidate("Request smuggling", doi="a", year=2024, venue="Journal")
        [ranked] = self.ranker.rank("request smuggling", [original])

        self.assertIs(ranked.candidate, original)
        self.assertEqual(ranked.candidate.url, original.url)
        self.assertEqual(ranked.candidate.title, original.title)
        self.assertEqual(ranked.candidate.snippet, original.snippet)

    def test_case_e_identifiers_survive_being_ranked(self) -> None:
        for identifier in (
            "CVE-2026-12345",
            "Next.js",
            "ASP.NET",
            "HTTP/2",
            "log4j",
        ):
            with self.subTest(identifier=identifier):
                [hit, miss] = self.ranker.rank(
                    identifier,
                    [
                        candidate(f"A study of {identifier}", doi="a"),
                        candidate("A study of something else", doi="b"),
                    ],
                )
                self.assertIn(identifier.casefold(), hit.candidate.title.casefold())
                self.assertGreater(hit.relevance.score, miss.relevance.score)

    def test_case_f_similar_titles_are_never_merged(self) -> None:
        """Two papers can share a title and still be two papers."""
        results = self.ranker.rank(
            "request smuggling",
            [
                candidate("Request smuggling", doi="first"),
                candidate("Request smuggling", doi="second"),
            ],
        )

        self.assertEqual(len(results), 2)
        for entry in results:
            with self.subTest(url=entry.candidate.url):
                self.assertFalse(entry.is_duplicate)

    def test_case_f_the_same_resource_is_marked_and_still_listed(self) -> None:
        results = self.ranker.rank(
            "request smuggling",
            [
                ResearchSourceCandidate(
                    url="https://doi.org/10.1000/same",
                    title="Request smuggling",
                    snippet="",
                ),
                ResearchSourceCandidate(
                    url="https://DOI.org/10.1000/same/",
                    title="Something unrelated",
                    snippet="",
                ),
            ],
        )

        self.assertEqual(len(results), 2)
        duplicates = [entry for entry in results if entry.is_duplicate]
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0].duplicate_of_rank, 1)
        self.assertIn(
            ResearchRelevanceReason.SAME_RESOURCE_AS_EARLIER_RESULT,
            duplicates[0].relevance.reasons,
        )

    def test_case_f_a_duplicate_never_outranks_something_new(self) -> None:
        results = self.ranker.rank(
            "request smuggling",
            [
                ResearchSourceCandidate(
                    url="https://doi.org/10.1000/same",
                    title="Request smuggling",
                    snippet="",
                ),
                ResearchSourceCandidate(
                    url="https://doi.org/10.1000/other",
                    title="Unrelated survey",
                    snippet="",
                ),
                ResearchSourceCandidate(
                    url="https://doi.org/10.1000/same",
                    title="Request smuggling",
                    snippet="",
                ),
            ],
        )

        self.assertTrue(results[-1].is_duplicate)
        self.assertGreater(results[-1].relevance.score, results[-2].relevance.score)


class RankedDiscoveryTests(unittest.TestCase):
    def _discovery(self, query: str, candidates: list) -> ResearchSourceDiscoveryRecord:
        return ResearchSourceDiscoveryRecord(
            discovery_id="discovery-1",
            query=query,
            provider="crossref",
            candidates=tuple(candidates),
            discovered_at=datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
        )

    def test_both_views_rank_a_discovery_the_same_way(self) -> None:
        discovery = self._discovery(
            "request smuggling",
            [candidate("A survey", doi="a"), candidate("Request smuggling", doi="b")],
        )

        self.assertEqual(
            titles(ranked_candidates(discovery)),
            titles(
                ResearchSourceRelevanceRanker().rank(
                    discovery.query, discovery.candidates
                )
            ),
        )

    def test_a_stored_discovery_can_never_carry_an_unrankable_query(self) -> None:
        """The fallback is defensive, and this is why it stays defensive.

        A discovery record refuses a blank query at construction, so no stored
        discovery can reach the fallback path. That is worth asserting rather
        than assuming: if the record ever loosened, the fallback would become
        reachable and the panel would start showing unranked lists silently.
        """
        with self.assertRaises(ResearchError):
            self._discovery("   ", [candidate("First", doi="a")])

    def test_the_fallback_keeps_provider_order_and_says_nothing_was_compared(
        self,
    ) -> None:
        discovery = self._discovery(
            "request smuggling",
            [candidate("First", doi="a"), candidate("Second", doi="b")],
        )

        results = unranked(discovery)

        self.assertEqual(titles(results), ["First", "Second"])
        for entry in results:
            with self.subTest(title=entry.candidate.title):
                self.assertEqual(
                    entry.relevance.category, ResearchRelevanceCategory.UNMEASURED
                )
                self.assertEqual(entry.provider_rank, entry.relevance_rank)

    def test_unranked_results_are_never_called_unrelated(self) -> None:
        discovery = self._discovery("anything", [candidate("First", doi="a")])

        self.assertEqual(
            unranked(discovery)[0].relevance.category,
            ResearchRelevanceCategory.UNMEASURED,
        )

    def test_something_other_than_a_discovery_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            ranked_candidates("a discovery")  # type: ignore[arg-type]


class RelevanceEvaluationSetTests(unittest.TestCase):
    """One fixed set of results, judged by hand, ranked by the code.

    The individual behaviours are asserted above. This asks the only question
    that matters to a person using it: given a realistic set of Crossref-shaped
    results for a real question, does the thing worth reading come first, and
    does the thing that merely shares vocabulary sink?
    """

    QUERY = "HTTP request smuggling in Next.js middleware"

    #: Provider order, deliberately unhelpful: the vague survey came back first.
    RESULTS = (
        ("A survey of web application security", 2011, "ACM Computing Surveys"),
        ("Smuggling contraband: a criminological review", 2018, "Crime Studies"),
        ("HTTP request smuggling in Next.js middleware", 2025, "USENIX Security"),
        ("Middleware architectures for distributed systems", 2003, "IEEE Software"),
        ("Request smuggling through HTTP/2 downgrades", 2021, "Black Hat Briefings"),
        ("Next.js performance patterns", 2024, "Web Engineering"),
        ("Detecting HTTP desynchronisation attacks", 2022, "NDSS"),
        ("An introduction to middleware testing", 2016, "Software Testing"),
        ("Smuggling requests past reverse proxies", 2020, "USENIX Security"),
        ("A history of the request-response model", 1999, "Computing History"),
    )

    #: Judged before the code was run, by reading the titles as a person would.
    MUST_BE_TOP_THREE = frozenset(
        {
            "HTTP request smuggling in Next.js middleware",
            "Request smuggling through HTTP/2 downgrades",
            "Smuggling requests past reverse proxies",
        }
    )
    MUST_NOT_BE_TOP_HALF = frozenset(
        {
            "Smuggling contraband: a criminological review",
            "A history of the request-response model",
            "An introduction to middleware testing",
        }
    )

    def setUp(self) -> None:
        self.candidates = [
            candidate(title, doi=str(index), year=year, venue=venue)
            for index, (title, year, venue) in enumerate(self.RESULTS)
        ]
        self.ranked = titles(
            ResearchSourceRelevanceRanker().rank(self.QUERY, self.candidates)
        )

    def test_the_exact_answer_comes_first(self) -> None:
        self.assertEqual(self.ranked[0], "HTTP request smuggling in Next.js middleware")

    def test_every_paper_on_the_attack_beats_every_paper_that_shares_only_words(
        self,
    ) -> None:
        for relevant in self.MUST_BE_TOP_THREE:
            for irrelevant in self.MUST_NOT_BE_TOP_HALF:
                with self.subTest(relevant=relevant, irrelevant=irrelevant):
                    self.assertLess(
                        self.ranked.index(relevant), self.ranked.index(irrelevant)
                    )

    def test_a_known_miss_of_lexical_ranking_is_recorded_rather_than_hidden(
        self,
    ) -> None:
        """A paper sharing only the framework name still reaches second place.

        Hand-judging this set put the three request-smuggling papers in the top
        three, and the ranker does not agree. `Next.js performance patterns`
        matches the most distinctive token in the question and nothing else,
        which is a strong lexical match and a useless result. Reweighting does
        not fix it: the difference between a Next.js paper about performance and
        one about smuggling is meaning, and nothing in this path reads meaning.

        So the disagreement is recorded rather than quietly relaxed. If ranking
        ever becomes able to tell these apart, this test fails and somebody gets
        to delete it, which is the correct way for it to end.
        """
        self.assertEqual(self.ranked[1], "Next.js performance patterns")
        self.assertNotIn(self.ranked[1], self.MUST_BE_TOP_THREE)

    def test_shared_vocabulary_alone_does_not_reach_the_top_half(self) -> None:
        """`Smuggling contraband` is the trap: the right word, the wrong field."""
        for title in self.MUST_NOT_BE_TOP_HALF:
            with self.subTest(title=title):
                self.assertGreaterEqual(self.ranked.index(title), 4)

    def test_ranking_improved_on_the_order_the_provider_returned(self) -> None:
        provider_order = [title for title, _, _ in self.RESULTS]

        self.assertNotEqual(self.ranked, provider_order)
        self.assertLess(
            self.ranked.index("HTTP request smuggling in Next.js middleware"),
            provider_order.index("HTTP request smuggling in Next.js middleware"),
        )

    def test_nothing_was_dropped_on_the_way(self) -> None:
        self.assertEqual(
            sorted(self.ranked), sorted(title for title, _, _ in self.RESULTS)
        )

    def test_asking_for_recent_work_reorders_without_discarding_the_specific(
        self,
    ) -> None:
        recent = titles(
            ResearchSourceRelevanceRanker().rank(
                f"latest {self.QUERY}", self.candidates
            )
        )

        self.assertEqual(recent[0], "HTTP request smuggling in Next.js middleware")
        self.assertLess(
            recent.index("Detecting HTTP desynchronisation attacks"),
            recent.index("A history of the request-response model"),
        )


def _function_names(source: str) -> tuple[str, ...]:
    return tuple(
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


if __name__ == "__main__":
    unittest.main()
