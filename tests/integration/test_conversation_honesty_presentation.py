"""The honesty statements must be true, consistent, and readable.

Three live findings meet here. A Turkish question got a wall of English that read
like a developer diagnostic. An evidence reply printed "Sources accepted: 0" and
then said "Sources exist but no evidence record does". And a message asking
whether Hypatia could reach a URL was answered by the model claiming the page was
not accessible — a statement about someone else's server, made without
contacting it.

The guarantee is unchanged and stays deterministic: these sentences are composed
in code, never phrased by a model, because "I did not research this" is one
rewrite away from "I could not find much on this". What changed is that the
sentences are looked up per language, the prose is derived from the same counters
it prints, and not fetching a page is reported as not fetching a page.

Nothing here touches a network.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from brain.BrainRequest import BrainRequest
from cognition.LiveInformationRequestDetector import LiveInformationRequestDetector
from cognition.LiveInformationRequestKind import LiveInformationRequestKind
from research.CanonicalResearchSummary import CanonicalResearchSummary
from response.HonestyPhrasebook import (
    phrase,
    phrase_keys,
    translated_languages,
)
from response.ResponseComposer import ResponseComposer
from response.ResponseLanguage import ResponseLanguage, detect_response_language

TURKISH_URL_QUESTION = (
    "https://portswigger.net/web-security/web-cache-deception "
    "bu siteye erişebiliyomusun"
)
FORBIDDEN_REACHABILITY_CLAIMS = (
    "inaccessible",
    "not accessible",
    "unavailable",
    "offline",
    "blocked",
    "erişilemez",
    "erisilemez",
    "kapalı",
)


class LanguageDetectionTests(unittest.TestCase):
    def test_the_real_turkish_url_question_is_detected_as_turkish(self) -> None:
        self.assertIs(
            detect_response_language(TURKISH_URL_QUESTION),
            ResponseLanguage.TURKISH,
        )

    def test_english_is_the_fallback(self) -> None:
        for message in (
            "Explain what a closure is in Python.",
            "What evidence did you collect?",
            "",
            "   ",
        ):
            with self.subTest(message=message):
                self.assertIs(
                    detect_response_language(message),
                    ResponseLanguage.ENGLISH,
                )

    def test_an_english_question_containing_a_shared_word_stays_english(self) -> None:
        """An earlier hint list fired on "site" and "var"."""
        for message in (
            "https://example.com/x can you access this site?",
            "var x = 1; can you explain this?",
        ):
            with self.subTest(message=message):
                self.assertIs(
                    detect_response_language(message),
                    ResponseLanguage.ENGLISH,
                )

    def test_a_turkish_diacritic_alone_is_enough(self) -> None:
        self.assertIs(detect_response_language("güncel"), ResponseLanguage.TURKISH)

    def test_transliterated_turkish_is_still_detected(self) -> None:
        self.assertIs(
            detect_response_language("Bu konuda hangi kanitlari topladin"),
            ResponseLanguage.TURKISH,
        )

    def test_a_non_string_falls_back(self) -> None:
        self.assertIs(
            detect_response_language(None),  # type: ignore[arg-type]
            ResponseLanguage.ENGLISH,
        )


class PhrasebookTests(unittest.TestCase):
    def test_every_language_translates_every_phrase(self) -> None:
        for language in translated_languages():
            for key in phrase_keys():
                with self.subTest(language=language, key=key):
                    self.assertTrue(phrase(key, language).strip())

    def test_an_unknown_phrase_key_is_refused(self) -> None:
        with self.assertRaises(KeyError):
            phrase("invented_key", ResponseLanguage.ENGLISH)

    def test_an_untranslated_language_falls_back_to_english(self) -> None:
        self.assertEqual(
            phrase("no_live_research", "xx"),  # type: ignore[arg-type]
            phrase("no_live_research", ResponseLanguage.ENGLISH),
        )

    def test_no_phrase_claims_a_site_is_unreachable(self) -> None:
        for language in translated_languages():
            for key in phrase_keys():
                rendered = phrase(key, language).casefold()
                for forbidden in FORBIDDEN_REACHABILITY_CLAIMS:
                    with self.subTest(language=language, key=key, claim=forbidden):
                        self.assertNotIn(forbidden, rendered)


class EvidenceStateConsistencyTests(unittest.TestCase):
    """The prose must be derived from the counters it prints."""

    CASES = (
        (0, 0, "evidence_none_at_all"),
        (1, 0, "evidence_sources_without_evidence"),
        (2, 0, "evidence_sources_without_evidence"),
        (1, 1, "evidence_recorded"),
        (3, 7, "evidence_recorded"),
    )

    def compose(self, sources: int, evidence: int, message: str = "x") -> str:
        summary = CanonicalResearchSummary(
            run_count=1,
            source_count=sources,
            evidence_count=evidence,
        )
        return (
            ResponseComposer()
            .research_evidence_provenance(
                BrainRequest(message=message),
                summary,
            )
            .message
        )

    def test_each_state_gets_its_own_sentence(self) -> None:
        for sources, evidence, key in self.CASES:
            with self.subTest(sources=sources, evidence=evidence):
                rendered = self.compose(sources, evidence)
                self.assertIn(phrase(key, ResponseLanguage.ENGLISH), rendered)

    def test_a_run_without_sources_does_not_claim_sources_exist(self) -> None:
        """The exact live contradiction: one run, zero sources."""
        rendered = self.compose(0, 0)

        self.assertIn("Sources accepted: 0", rendered)
        self.assertNotIn("Sources exist", rendered)
        self.assertNotIn("Accepted sources exist", rendered)

    def test_sources_without_evidence_says_exactly_that(self) -> None:
        rendered = self.compose(2, 0)

        self.assertIn("Sources accepted: 2", rendered)
        self.assertIn("Accepted sources exist, but no evidence record does", rendered)

    def test_the_counters_are_always_shown(self) -> None:
        for sources, evidence, _ in self.CASES:
            with self.subTest(sources=sources, evidence=evidence):
                rendered = self.compose(sources, evidence)
                self.assertIn(f"Sources accepted: {sources}", rendered)
                self.assertIn(f"Evidence records: {evidence}", rendered)

    def test_a_turkish_question_is_answered_in_turkish(self) -> None:
        rendered = self.compose(0, 0, "Bu konuda hangi kanıtları topladın?")

        self.assertIn(
            phrase("evidence_none_at_all", ResponseLanguage.TURKISH),
            rendered,
        )

    def test_the_statement_comes_before_the_counters(self) -> None:
        rendered = self.compose(0, 0)
        statement = phrase("evidence_none_at_all", ResponseLanguage.ENGLISH)

        self.assertLess(rendered.index(statement), rendered.index("Research runs:"))


class UrlAccessHonestyTests(unittest.TestCase):
    """Not fetching a page is not the same as the page being unreachable."""

    def setUp(self) -> None:
        self.detector = LiveInformationRequestDetector()
        self.composer = ResponseComposer()

    def compose(self, message: str) -> str:
        kind = self.detector.detect(message)
        return self.composer.live_research_not_performed(
            BrainRequest(message=message),
            kind,
            CanonicalResearchSummary(),
        ).message

    def test_the_real_turkish_question_is_classified_as_a_url_request(self) -> None:
        self.assertIs(
            self.detector.detect(TURKISH_URL_QUESTION),
            LiveInformationRequestKind.URL_ACCESS,
        )

    def test_english_and_turkish_access_questions_are_detected(self) -> None:
        for message in (
            "https://example.com/x can you access this site?",
            "https://example.com/x bu sayfayı okuyabilir misin?",
            "https://example.com/x sitesine erişebilir misin",
            "Can you open this link https://example.com/x",
        ):
            with self.subTest(message=message):
                self.assertIs(
                    self.detector.detect(message),
                    LiveInformationRequestKind.URL_ACCESS,
                )

    def test_a_pasted_url_used_as_context_is_not_hijacked(self) -> None:
        """A link is usually context for a question, not a request to open it."""
        for message in (
            "I read about it at https://example.com/x, what do you think?",
            "https://example.com/x explains closures well, summarise the idea.",
        ):
            with self.subTest(message=message):
                self.assertIs(
                    self.detector.detect(message),
                    LiveInformationRequestKind.NONE,
                )

    def test_the_reply_says_the_link_was_not_opened(self) -> None:
        rendered = self.compose(TURKISH_URL_QUESTION)

        self.assertIn(
            phrase("url_not_opened", ResponseLanguage.TURKISH),
            rendered,
        )

    def test_the_reply_refuses_to_judge_the_site(self) -> None:
        rendered = self.compose(TURKISH_URL_QUESTION).casefold()

        for forbidden in FORBIDDEN_REACHABILITY_CLAIMS:
            with self.subTest(claim=forbidden):
                self.assertNotIn(forbidden, rendered)

    def test_the_reply_states_reachability_is_unknown(self) -> None:
        rendered = self.compose(TURKISH_URL_QUESTION)

        self.assertIn(
            phrase("url_unknown_reachability", ResponseLanguage.TURKISH),
            rendered,
        )

    def test_the_reply_points_at_the_research_workflow(self) -> None:
        rendered = self.compose("https://example.com/x can you access this site?")

        self.assertIn(
            phrase("url_use_research", ResponseLanguage.ENGLISH),
            rendered,
        )

    def test_a_url_request_is_a_live_information_request(self) -> None:
        kind = LiveInformationRequestKind.URL_ACCESS

        self.assertTrue(kind.detected)
        self.assertTrue(kind.concerns_one_named_url)
        self.assertFalse(
            LiveInformationRequestKind.CURRENT_EVENTS.concerns_one_named_url
        )


class LiveResearchDeclinedPresentationTests(unittest.TestCase):
    def compose(self, message: str) -> str:
        detector = LiveInformationRequestDetector()
        kind = detector.detect(message)
        return (
            ResponseComposer()
            .live_research_not_performed(
                BrainRequest(message=message),
                kind,
                CanonicalResearchSummary(run_count=1),
            )
            .message
        )

    def test_the_turkish_news_request_is_answered_in_turkish(self) -> None:
        rendered = self.compose(
            "Bugün yayımlanan 3 siber güvenlik haberi bul. Kaynaklarını ver."
        )

        self.assertIn(
            phrase("no_live_research", ResponseLanguage.TURKISH),
            rendered,
        )
        self.assertNotIn("Live research was not performed", rendered)

    def test_the_plain_statement_comes_first(self) -> None:
        rendered = self.compose("Find me three recent papers on web security.")
        statement = phrase("no_live_research", ResponseLanguage.ENGLISH)

        self.assertTrue(rendered.startswith(statement))

    def test_the_counters_move_under_a_details_heading(self) -> None:
        rendered = self.compose("Find me three recent papers on web security.")

        self.assertIn(phrase("details_heading", ResponseLanguage.ENGLISH), rendered)
        self.assertLess(
            rendered.index(phrase("details_heading", ResponseLanguage.ENGLISH)),
            rendered.index("Research runs:"),
        )

    def test_the_request_kind_stays_available_in_the_details(self) -> None:
        rendered = self.compose("Please search the internet for me.")

        self.assertIn("request kind: web_search", rendered)


if __name__ == "__main__":
    unittest.main()
