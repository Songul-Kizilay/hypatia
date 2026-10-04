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
            self.provider.discover("cross-site scripting", limit=10),
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
        run = self.manager.create("What is reflected XSS?")

        result = self.operation.run(
            self.step, ResearchPlanExecutionContext(research_run_id=run.run_id)
        )

        self.assertTrue(result.performed)
        self.assertIn("returned 0 candidate(s)", result.detail)
        self.assertEqual(self.manager.get(run.run_id).discoveries[0].candidates, ())


if __name__ == "__main__":
    unittest.main()
