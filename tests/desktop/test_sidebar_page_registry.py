"""Unit coverage for the sidebar's page/group layout -- no Tkinter involved.

`build_sidebar_groups` is the one place that decides which conditional pages
appear and where; every assertion here is about that decision, never about
rendering.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from desktop.SidebarPageRegistry import (
    SidebarEnabledSurfaces,
    build_sidebar_groups,
)


def _page_ids(groups: tuple) -> list[str]:
    return [page.page_id for group in groups for page in group.pages]


def _group_ids(groups: tuple) -> list[str]:
    return [group.group_id for group in groups]


class BaselineLayoutTests(unittest.TestCase):
    def test_every_installation_gets_home_and_system(self) -> None:
        groups = build_sidebar_groups(SidebarEnabledSurfaces())

        self.assertEqual(_group_ids(groups), ["home", "research", "system"])
        self.assertEqual(
            _page_ids(groups),
            [
                "chat",
                "knowledge",
                "research_simple",
                "research_advanced",
                "source_previews",
                "review",
                "appearance",
            ],
        )

    def test_the_security_group_is_absent_with_no_qualifying_surface(self) -> None:
        groups = build_sidebar_groups(SidebarEnabledSurfaces())

        self.assertNotIn("security", _group_ids(groups))

    def test_the_tools_page_is_absent_without_a_console(self) -> None:
        groups = build_sidebar_groups(SidebarEnabledSurfaces())

        self.assertNotIn("tools", _page_ids(groups))

    def test_a_console_alone_adds_only_the_tools_page(self) -> None:
        groups = build_sidebar_groups(SidebarEnabledSurfaces(tool_console=True))

        self.assertNotIn("security", _group_ids(groups))
        system = next(g for g in groups if g.group_id == "system")
        self.assertEqual(
            [p.page_id for p in system.pages], ["tools", "review", "appearance"]
        )


class ProgramScopeSurfaceTests(unittest.TestCase):
    def test_program_scope_adds_session_contexts_to_research(self) -> None:
        groups = build_sidebar_groups(SidebarEnabledSurfaces(program_scope=True))

        research = next(g for g in groups if g.group_id == "research")
        self.assertEqual(
            [p.page_id for p in research.pages],
            [
                "research_simple",
                "research_advanced",
                "source_previews",
                "session_contexts",
            ],
        )

    def test_program_scope_opens_the_bug_bounty_group_in_order(self) -> None:
        groups = build_sidebar_groups(SidebarEnabledSurfaces(program_scope=True))

        security = next(g for g in groups if g.group_id == "security")
        self.assertEqual(security.title, "Web Security & Bug Bounty")
        self.assertEqual(
            [p.page_id for p in security.pages],
            [
                "asset_inventory",
                "kali_tools",
                "security_hypotheses",
                "findings",
                "validation_recipes",
            ],
        )

    def test_without_program_scope_none_of_its_pages_appear(self) -> None:
        groups = build_sidebar_groups(SidebarEnabledSurfaces())

        for page_id in (
            "session_contexts",
            "asset_inventory",
            "kali_tools",
            "security_hypotheses",
            "findings",
            "validation_recipes",
        ):
            self.assertNotIn(page_id, _page_ids(groups))


class ConditionalSecurityPagesTests(unittest.TestCase):
    def test_the_vulnerability_graph_alone_still_earns_its_own_group(self) -> None:
        groups = build_sidebar_groups(SidebarEnabledSurfaces(vulnerability_graph=True))

        security = next(g for g in groups if g.group_id == "security")
        self.assertEqual([p.page_id for p in security.pages], ["vulnerability_graph"])

    def test_security_learning_alone_still_earns_its_own_group(self) -> None:
        groups = build_sidebar_groups(SidebarEnabledSurfaces(security_learning=True))

        security = next(g for g in groups if g.group_id == "security")
        self.assertEqual([p.page_id for p in security.pages], ["security_learning"])

    def test_every_surface_together_keeps_the_fixed_order(self) -> None:
        groups = build_sidebar_groups(
            SidebarEnabledSurfaces(
                program_scope=True,
                tool_console=True,
                vulnerability_graph=True,
                security_learning=True,
            )
        )

        security = next(g for g in groups if g.group_id == "security")
        self.assertEqual(
            [p.page_id for p in security.pages],
            [
                "asset_inventory",
                "kali_tools",
                "security_hypotheses",
                "findings",
                "validation_recipes",
                "vulnerability_graph",
                "security_learning",
            ],
        )
        system = next(g for g in groups if g.group_id == "system")
        self.assertEqual(
            [p.page_id for p in system.pages], ["tools", "review", "appearance"]
        )


if __name__ == "__main__":
    unittest.main()
