"""The curated catalog returns only its own fixed URLs, never a guess.

No network, no mock transport, and no opener seam exist for this provider at
all, unlike Crossref or NVD: `discover` cannot make a request, so these tests
exercise the real class directly rather than a fixture standing in for a live
API. The one thing worth proving here is matching discipline — a recognized
topic returns exactly its catalog entries, and anything else returns nothing,
never a nearest guess.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from research.CuratedResearchSourceDiscoveryProvider import (
    CURATED_PROVIDER_NAME,
    CuratedResearchSourceDiscoveryProvider,
)
from research.JsonFileResearchRunStore import JsonFileResearchRunStore
from research.ResearchDiscoveryProviderName import (
    GENERAL_DISCOVERY_PROVIDERS,
    ResearchDiscoveryProviderName,
)
from research.ResearchPlanExecutionContext import ResearchPlanExecutionContext
from research.ResearchPlanStep import ResearchPlanStep
from research.ResearchPlanStepCapability import ResearchPlanStepCapability
from research.ResearchRunManager import ResearchRunManager
from research.ResearchSourceCandidate import ResearchSourceCandidate
from research.SourceDiscoveryStepOperation import SourceDiscoveryStepOperation

MODULE_SOURCE = (
    SRC_DIR / "research" / "CuratedResearchSourceDiscoveryProvider.py"
).read_text(encoding="utf-8")

_PORTSWIGGER_SQLI = "https://portswigger.net/web-security/sql-injection"
_PORTSWIGGER_CHEAT_SHEET = (
    "https://portswigger.net/web-security/sql-injection/cheat-sheet"
)
_OWASP_SQLI_PREVENTION = (
    "https://cheatsheetseries.owasp.org/cheatsheets/"
    "SQL_Injection_Prevention_Cheat_Sheet.html"
)
_PORTSWIGGER_XSS = "https://portswigger.net/web-security/cross-site-scripting"
_PORTSWIGGER_XSS_CHEAT_SHEET = (
    "https://portswigger.net/web-security/cross-site-scripting/cheat-sheet"
)
_OWASP_XSS_PREVENTION = (
    "https://cheatsheetseries.owasp.org/cheatsheets/"
    "Cross_Site_Scripting_Prevention_Cheat_Sheet.html"
)

_NMAP_MAN = "https://nmap.org/book/man.html"
_NMAP_BOOK_TOC = "https://nmap.org/book/toc.html"
_BURP_DOCS = "https://portswigger.net/burp/documentation"
_BURP_GETTING_STARTED = (
    "https://portswigger.net/burp/documentation/desktop/getting-started"
)
_CURL_MAN = "https://curl.se/docs/manpage.html"
_CURL_DOCS = "https://curl.se/docs/"
_FFUF_README = "https://github.com/ffuf/ffuf"
_FFUF_WIKI = "https://github.com/ffuf/ffuf/wiki"
_GOBUSTER_README = "https://github.com/OJ/gobuster"
_GOBUSTER_WIKI = "https://github.com/OJ/gobuster/wiki"
_WIRESHARK_GUIDE = "https://www.wireshark.org/docs/wsug_html_chunked/"
_WIRESHARK_MAN = "https://www.wireshark.org/docs/man-pages/wireshark.html"
_TCPDUMP_MAN = "https://www.tcpdump.org/manpages/tcpdump.1.html"
_TCPDUMP_HOME = "https://www.tcpdump.org/"
_SQLMAP_USAGE = "https://github.com/sqlmapproject/sqlmap/wiki/Usage"
_SQLMAP_README = "https://github.com/sqlmapproject/sqlmap"
_NUCLEI_OVERVIEW = "https://docs.projectdiscovery.io/tools/nuclei/overview"
_NUCLEI_README = "https://github.com/projectdiscovery/nuclei"
_NCAT_GUIDE = "https://nmap.org/ncat/guide/index.html"
_NCAT_HOME = "https://nmap.org/ncat/"
_OPENSSL_DOCS = "https://docs.openssl.org/master/man1/openssl/"
_OPENSSL_MAN = "https://www.openssl.org/docs/manmaster/man1/openssl.html"

#: (query, expected ordered candidate URLs) -- one row per Kali tool topic.
_KALI_TOOL_TOPICS = (
    ("Teach me how Nmap scans ports.", (_NMAP_MAN, _NMAP_BOOK_TOC)),
    ("How do I use Burp Suite's Repeater?", (_BURP_DOCS, _BURP_GETTING_STARTED)),
    ("What flags does curl support for following redirects?", (_CURL_MAN, _CURL_DOCS)),
    ("How does ffuf fuzz a wordlist?", (_FFUF_README, _FFUF_WIKI)),
    ("What scan modes does Gobuster support?", (_GOBUSTER_README, _GOBUSTER_WIKI)),
    ("How do I filter packets in Wireshark?", (_WIRESHARK_GUIDE, _WIRESHARK_MAN)),
    ("How do I capture traffic with tcpdump?", (_TCPDUMP_MAN, _TCPDUMP_HOME)),
    ("How does sqlmap detect injection?", (_SQLMAP_USAGE, _SQLMAP_README)),
    ("How do Nuclei templates work?", (_NUCLEI_OVERVIEW, _NUCLEI_README)),
    ("How do I set up a Netcat listener?", (_NCAT_GUIDE, _NCAT_HOME)),
    ("How do I generate a cert with OpenSSL?", (_OPENSSL_DOCS, _OPENSSL_MAN)),
)


class CuratedResearchSourceDiscoveryProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = CuratedResearchSourceDiscoveryProvider()

    def test_provider_name_is_the_enum_value(self) -> None:
        self.assertEqual(self.provider.provider_name, "curated")
        self.assertEqual(CURATED_PROVIDER_NAME, ResearchDiscoveryProviderName.CURATED)

    def test_sql_injection_question_returns_the_fixed_catalog(self) -> None:
        candidates = self.provider.discover(
            "Teach me about SQL Injection, like the BSCP exam covers.",
            limit=10,
        )

        self.assertEqual(
            [candidate.url for candidate in candidates],
            [_PORTSWIGGER_SQLI, _PORTSWIGGER_CHEAT_SHEET, _OWASP_SQLI_PREVENTION],
        )
        for candidate in candidates:
            self.assertIsInstance(candidate, ResearchSourceCandidate)
            self.assertTrue(candidate.url.startswith("https://"))
            self.assertNotIn("@", candidate.url)

    def test_every_candidate_is_credential_free_https_with_no_fabricated_prose(
        self,
    ) -> None:
        candidates = self.provider.discover("sql injection", limit=10)

        self.assertEqual(len(candidates), 3)
        for candidate in candidates:
            self.assertTrue(candidate.url.startswith("https://"))
            self.assertNotIn("@", candidate.url)
            self.assertTrue(candidate.title)
            self.assertIn(
                candidate.container,
                ("PortSwigger Web Security Academy", "OWASP Cheat Sheet Series"),
            )

    def test_the_short_alias_alone_also_matches(self) -> None:
        candidates = self.provider.discover("What is SQLi?", limit=10)
        self.assertEqual(len(candidates), 3)

    def test_case_and_punctuation_do_not_change_the_match(self) -> None:
        reference = [c.url for c in self.provider.discover("sql injection", limit=10)]
        shouted = [c.url for c in self.provider.discover("SQL INJECTION!!", limit=10)]
        self.assertEqual(shouted, reference)

    def test_an_uncovered_topic_returns_nothing_not_a_guess(self) -> None:
        self.assertEqual(
            self.provider.discover("quantum cryptography lattice schemes", limit=10),
            [],
        )
        self.assertEqual(
            self.provider.discover("server-side request forgery", limit=10),
            [],
        )

    def test_mentioning_only_one_required_term_does_not_match(self) -> None:
        self.assertEqual(self.provider.discover("injection", limit=10), [])
        self.assertEqual(self.provider.discover("sql server tuning", limit=10), [])

    def test_limit_narrows_the_result_without_changing_order(self) -> None:
        candidates = self.provider.discover("sql injection", limit=1)
        self.assertEqual([c.url for c in candidates], [_PORTSWIGGER_SQLI])

    def test_empty_query_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            self.provider.discover("", limit=5)
        with self.assertRaises(ResearchError):
            self.provider.discover("   ", limit=5)

    def test_limit_is_validated(self) -> None:
        for invalid in (0, -1, 11, True, 3.5):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ResearchError):
                    self.provider.discover("sql injection", limit=invalid)  # type: ignore[arg-type]

    def test_no_network_seam_exists_on_this_provider(self) -> None:
        """Neither the instance nor the module source can reach a network.

        Checks both ends: no network-shaped instance attribute (would matter
        if a future edit stored an opener/transport on `self`), and no
        network-capable import anywhere in the module's own source text
        (would matter if a future edit called one inline inside `discover`
        without storing it on `self` at all, which an instance-only check
        could never see).
        """
        forbidden = ("socket", "opener", "transport", "http", "urllib", "requests")
        attributes = {name.casefold() for name in vars(self.provider)}
        for word in forbidden:
            self.assertFalse(
                any(word in attribute for attribute in attributes),
                f"Unexpected network-shaped attribute containing {word!r}.",
            )
        forbidden_imports = (
            "socket",
            "urllib",
            "requests",
            "http.client",
            "subprocess",
            "os.system",
        )
        for word in forbidden_imports:
            with self.subTest(forbidden_import=word):
                self.assertNotIn(word, MODULE_SOURCE)

    def test_curated_is_excluded_from_the_general_provider_pair(self) -> None:
        self.assertNotIn(
            ResearchDiscoveryProviderName.CURATED, GENERAL_DISCOVERY_PROVIDERS
        )
        self.assertEqual(
            set(GENERAL_DISCOVERY_PROVIDERS),
            {ResearchDiscoveryProviderName.CROSSREF, ResearchDiscoveryProviderName.NVD},
        )


class CrossSiteScriptingTopicTests(unittest.TestCase):
    """The second catalog topic, proving the catalog genuinely generalizes."""

    def setUp(self) -> None:
        self.provider = CuratedResearchSourceDiscoveryProvider()

    def test_xss_acronym_returns_the_fixed_catalog(self) -> None:
        candidates = self.provider.discover("What is reflected XSS?", limit=10)

        self.assertEqual(
            [c.url for c in candidates],
            [_PORTSWIGGER_XSS, _PORTSWIGGER_XSS_CHEAT_SHEET, _OWASP_XSS_PREVENTION],
        )

    def test_hyphenated_phrasing_matches(self) -> None:
        candidates = self.provider.discover(
            "Teach me cross-site scripting for the BSCP exam.", limit=10
        )
        self.assertEqual(len(candidates), 3)

    def test_unhyphenated_three_word_phrasing_also_matches(self) -> None:
        """ "cross site scripting" tokenizes as three separate words, not one."""
        candidates = self.provider.discover("What is cross site scripting?", limit=10)
        self.assertEqual(len(candidates), 3)

    def test_mentioning_only_one_required_term_does_not_match(self) -> None:
        self.assertEqual(self.provider.discover("scripting language", limit=10), [])
        self.assertEqual(self.provider.discover("cross country running", limit=10), [])


class KaliToolTopicTests(unittest.TestCase):
    """The eleven Kali Linux tool catalog entries: LEARN-only knowledge, no
    execution authority. Each entry is checked for its own ordinary-phrasing
    match; aliases and negatives get their own dedicated tests below.
    """

    def setUp(self) -> None:
        self.provider = CuratedResearchSourceDiscoveryProvider()

    def test_each_tool_topic_returns_its_own_fixed_catalog(self) -> None:
        for query, expected_urls in _KALI_TOOL_TOPICS:
            with self.subTest(query=query):
                candidates = self.provider.discover(query, limit=10)
                self.assertEqual(tuple(c.url for c in candidates), expected_urls)
                for candidate in candidates:
                    self.assertTrue(candidate.url.startswith("https://"))
                    self.assertNotIn("@", candidate.url)
                    self.assertTrue(candidate.title)

    def test_network_mapper_alias_matches_nmap(self) -> None:
        candidates = self.provider.discover(
            "What is the Network Mapper tool used for?", limit=10
        )
        self.assertEqual(tuple(c.url for c in candidates), (_NMAP_MAN, _NMAP_BOOK_TOC))

    def test_burpsuite_single_token_alias_matches_burp(self) -> None:
        candidates = self.provider.discover(
            "How is BurpSuite used in a web app pentest?", limit=10
        )
        self.assertEqual(
            tuple(c.url for c in candidates), (_BURP_DOCS, _BURP_GETTING_STARTED)
        )

    def test_ncat_alias_matches_netcat(self) -> None:
        candidates = self.provider.discover(
            "What can I do with ncat that plain netcat can't?", limit=10
        )
        self.assertEqual(tuple(c.url for c in candidates), (_NCAT_GUIDE, _NCAT_HOME))

    def test_ordinary_english_words_that_are_also_tool_names_can_false_positive(
        self,
    ) -> None:
        """Documented, accepted tradeoff (see the module docstring): "burp",
        "curl" and "nuclei" are also common English words, unlike the other
        nine entries. An unrelated sentence containing one of them still
        returns that tool's catalog entry -- a harmless, still-pinned,
        still-official documentation citation, never a wrong URL or expanded
        authority -- rather than a narrower match that would also reject
        short, direct, entirely legitimate questions like "what is curl?".
        This test exists so that behavior is a proven, intentional choice,
        not a silent, undiscovered side effect.
        """
        self.assertEqual(
            tuple(
                c.url
                for c in self.provider.discover("I felt a burp after lunch.", limit=10)
            ),
            (_BURP_DOCS, _BURP_GETTING_STARTED),
        )
        self.assertEqual(
            tuple(
                c.url
                for c in self.provider.discover(
                    "Let's curl up on the couch and watch a movie.", limit=10
                )
            ),
            (_CURL_MAN, _CURL_DOCS),
        )
        self.assertEqual(
            tuple(
                c.url
                for c in self.provider.discover(
                    "The nuclei of a cell contain its DNA.", limit=10
                )
            ),
            (_NUCLEI_OVERVIEW, _NUCLEI_README),
        )

    def test_unrelated_tool_sounding_question_matches_nothing(self) -> None:
        self.assertEqual(
            self.provider.discover("What is a reverse proxy load balancer?", limit=10),
            [],
        )

    def test_comparing_two_kali_tools_discovers_both(self) -> None:
        candidates = self.provider.discover(
            "What is the difference between ffuf and Gobuster?", limit=10
        )
        self.assertEqual(
            {c.url for c in candidates},
            {_FFUF_README, _FFUF_WIKI, _GOBUSTER_README, _GOBUSTER_WIKI},
        )

    def test_a_web_vulnerability_and_a_kali_tool_can_be_discovered_together(
        self,
    ) -> None:
        """Requirement #5's distinguishing power extends across the two
        knowledge areas: a question naming a vulnerability class and a tool
        in the same breath still gets sources for both.
        """
        candidates = self.provider.discover(
            "How would sqlmap help test for SQL injection?", limit=10
        )
        self.assertEqual(
            {c.url for c in candidates},
            {
                _SQLMAP_USAGE,
                _SQLMAP_README,
                _PORTSWIGGER_SQLI,
                _PORTSWIGGER_CHEAT_SHEET,
                _OWASP_SQLI_PREVENTION,
            },
        )


class MultiTopicDiscoveryTests(unittest.TestCase):
    """A question naming two covered topics gets candidates for both.

    Directly supports "distinguish vulnerability classes that are easily
    confused": a single discovery step can gather sources for SQL injection
    and XSS together, so later evidence/teaching steps have material from
    both to actually compare.
    """

    def setUp(self) -> None:
        self.provider = CuratedResearchSourceDiscoveryProvider()

    def test_a_comparison_question_discovers_both_topics(self) -> None:
        candidates = self.provider.discover(
            "What is the difference between SQL injection and XSS?", limit=10
        )

        urls = {c.url for c in candidates}
        self.assertEqual(
            urls,
            {
                _PORTSWIGGER_SQLI,
                _PORTSWIGGER_CHEAT_SHEET,
                _OWASP_SQLI_PREVENTION,
                _PORTSWIGGER_XSS,
                _PORTSWIGGER_XSS_CHEAT_SHEET,
                _OWASP_XSS_PREVENTION,
            },
        )

    def test_a_comparison_question_respects_the_limit(self) -> None:
        candidates = self.provider.discover(
            "What is the difference between SQL injection and XSS?", limit=4
        )

        self.assertEqual(len(candidates), 4)

    def test_single_topic_question_still_returns_only_that_topic(self) -> None:
        candidates = self.provider.discover("sql injection", limit=10)

        self.assertEqual(
            {c.url for c in candidates},
            {_PORTSWIGGER_SQLI, _PORTSWIGGER_CHEAT_SHEET, _OWASP_SQLI_PREVENTION},
        )


class CuratedProviderComposesWithTheRealStepOperationTests(unittest.TestCase):
    """Full composition through the real, unmodified discovery step operation.

    Nothing here is mocked: the real provider answers a real plan step through
    the real `SourceDiscoveryStepOperation`, against a real on-disk run store.
    This is the same operation an approved desktop plan step calls; only the
    network-facing providers need a mock transport in their own tests, because
    only they can make a request at all.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manager = ResearchRunManager(
            JsonFileResearchRunStore(Path(self.temp.name) / "runs.json")
        )
        curated = CuratedResearchSourceDiscoveryProvider()
        self.operation = SourceDiscoveryStepOperation(
            curated,
            self.manager,
            providers={ResearchDiscoveryProviderName.CURATED: curated},
        )
        self.step = ResearchPlanStep(
            step_id="step-1",
            instruction="Discover candidate sources for the research question.",
            capability=ResearchPlanStepCapability.SOURCE_DISCOVERY,
            discovery_provider=ResearchDiscoveryProviderName.CURATED,
        )

    def test_the_sql_injection_question_discovers_the_real_catalog_urls(self) -> None:
        run = self.manager.create("Teach me SQL Injection for the BSCP exam.")

        result = self.operation.run(
            self.step, ResearchPlanExecutionContext(research_run_id=run.run_id)
        )

        self.assertTrue(result.performed)
        self.assertIn("'curated'", result.detail)
        self.assertIn("returned 3 candidate(s)", result.detail)
        updated = self.manager.get(run.run_id)
        self.assertEqual(len(updated.discoveries), 1)
        discovered_urls = {c.url for c in updated.discoveries[0].candidates}
        self.assertEqual(
            discovered_urls,
            {_PORTSWIGGER_SQLI, _PORTSWIGGER_CHEAT_SHEET, _OWASP_SQLI_PREVENTION},
        )
        # Discovery alone never accepts, fetches, or creates evidence.
        self.assertEqual(updated.sources, ())
        self.assertEqual(updated.evidence, ())

    def test_an_unrelated_question_discovers_nothing(self) -> None:
        run = self.manager.create("What is server-side request forgery?")

        result = self.operation.run(
            self.step, ResearchPlanExecutionContext(research_run_id=run.run_id)
        )

        self.assertTrue(result.performed)
        self.assertIn("returned 0 candidate(s)", result.detail)
        self.assertEqual(self.manager.get(run.run_id).discoveries[0].candidates, ())


if __name__ == "__main__":
    unittest.main()
