"""Research fetches identify honestly, and cannot be made to lie.

A public site returning 403 to Hypatia is a site declining to serve this client,
and that is a legitimate answer. Wikimedia in particular asks non-browser clients
to name a contact, so the operator can append their own — inventing a contact
address on someone's behalf would be worse than the refusal.

What the override cannot do is impersonate a browser. Dressing up as Chrome to
get past a 403 is bypassing an anti-bot control, and the answer to a site saying
no is to identify honestly or accept the no.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from core.Exceptions import ResearchError
from core.Version import VERSION
from research.HttpResearchSourceFetcher import (
    DEFAULT_RESEARCH_USER_AGENT,
    research_user_agent,
)

BROWSER_STRINGS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Chrome/126.0.0.0",
    "AppleWebKit/537.36 (KHTML, like Gecko/20100101)",
    "Safari/537.36",
    "Edg/126.0",
    "OPR/110.0",
)


class ResearchUserAgentTests(unittest.TestCase):
    def test_the_default_names_hypatia_and_its_version(self) -> None:
        agent = research_user_agent({})

        self.assertEqual(agent, DEFAULT_RESEARCH_USER_AGENT)
        self.assertIn("Hypatia", agent)
        self.assertIn(VERSION.short, agent)

    def test_the_default_impersonates_nothing(self) -> None:
        lowered = research_user_agent({}).casefold()

        for marker in ("mozilla", "chrome", "safari", "gecko", "edg/", "opr/"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, lowered)

    def test_the_default_leaks_no_machine_or_user_identity(self) -> None:
        """It carries a product and a version, and nothing about who ran it."""
        agent = research_user_agent({})

        self.assertEqual(agent.count("("), 0)
        self.assertNotIn("@", agent)

    def test_an_operator_contact_is_appended(self) -> None:
        agent = research_user_agent(
            {"HYPATIA_RESEARCH_USER_AGENT_CONTACT": "https://example.org/hypatia"}
        )

        self.assertTrue(agent.startswith(DEFAULT_RESEARCH_USER_AGENT))
        self.assertIn("https://example.org/hypatia", agent)

    def test_a_blank_contact_changes_nothing(self) -> None:
        for value in ("", "   "):
            with self.subTest(value=value):
                self.assertEqual(
                    research_user_agent({"HYPATIA_RESEARCH_USER_AGENT_CONTACT": value}),
                    DEFAULT_RESEARCH_USER_AGENT,
                )

    def test_a_browser_impersonation_is_refused(self) -> None:
        for value in BROWSER_STRINGS:
            with self.subTest(value=value):
                with self.assertRaises(ResearchError) as raised:
                    research_user_agent({"HYPATIA_RESEARCH_USER_AGENT_CONTACT": value})
                self.assertIn("impersonate a browser", str(raised.exception))

    def test_an_overlong_contact_is_refused(self) -> None:
        with self.assertRaises(ResearchError):
            research_user_agent({"HYPATIA_RESEARCH_USER_AGENT_CONTACT": "x" * 200})

    def test_a_header_injection_attempt_is_refused(self) -> None:
        for value in ("a\rb", "a\nb", "a\r\nX-Injected: 1"):
            with self.subTest(value=value):
                with self.assertRaises(ResearchError):
                    research_user_agent({"HYPATIA_RESEARCH_USER_AGENT_CONTACT": value})


if __name__ == "__main__":
    unittest.main()
