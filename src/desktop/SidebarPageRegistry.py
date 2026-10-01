"""Pure page/group layout for the desktop sidebar navigation.

This module decides nothing about the runtime. It only arranges pages that
the caller already knows exist into the fixed group structure the desktop
shell presents, and it omits a conditional page whenever the caller reports
its backing surface is not available -- the same rule the old per-tab
``if self._weakness_graph_enabled:`` guards enforced, just centralised so
one place answers "what pages exist right now" instead of the notebook
construction and the navigation widget each deciding separately.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SidebarPage:
    """One navigable page: a stable identifier and its display label."""

    page_id: str
    label: str


@dataclass(frozen=True)
class SidebarGroup:
    """One sidebar section: a stable identifier, a title, and its pages."""

    group_id: str
    title: str
    pages: tuple[SidebarPage, ...]


@dataclass(frozen=True)
class SidebarEnabledSurfaces:
    """Which conditional pages this running installation has somewhere to go.

    Each field mirrors an existing desktop construction guard. Setting one
    true here must never be the thing that enables the underlying surface --
    it only tells the sidebar whether that already-decided surface exists.
    """

    program_scope: bool = False
    tool_console: bool = False
    vulnerability_graph: bool = False
    security_learning: bool = False


def build_sidebar_groups(surfaces: SidebarEnabledSurfaces) -> tuple[SidebarGroup, ...]:
    """Return the fixed sidebar groups, omitting pages this build lacks."""
    groups: list[SidebarGroup] = [
        SidebarGroup(
            "home",
            "Home",
            (
                SidebarPage("chat", "Chat"),
                SidebarPage("knowledge", "Knowledge"),
            ),
        )
    ]

    research_pages: list[SidebarPage] = [
        SidebarPage("research_simple", "Research"),
        SidebarPage("research_advanced", "Advanced Research"),
        SidebarPage("source_previews", "Source Previews"),
    ]
    if surfaces.program_scope:
        research_pages.append(SidebarPage("session_contexts", "Session Contexts"))
    groups.append(SidebarGroup("research", "Research", tuple(research_pages)))

    security_pages: list[SidebarPage] = []
    if surfaces.program_scope:
        security_pages.extend(
            (
                SidebarPage("asset_inventory", "Asset Inventory"),
                SidebarPage("kali_tools", "Kali Tools"),
                SidebarPage("security_hypotheses", "Security Hypotheses"),
                SidebarPage("findings", "Findings"),
                SidebarPage("validation_recipes", "Validation Recipes"),
            )
        )
    if surfaces.vulnerability_graph:
        security_pages.append(SidebarPage("vulnerability_graph", "Vulnerability Graph"))
    if surfaces.security_learning:
        security_pages.append(SidebarPage("security_learning", "Security Learning"))
    if security_pages:
        groups.append(
            SidebarGroup(
                "security",
                "Web Security & Bug Bounty",
                tuple(security_pages),
            )
        )

    system_pages: list[SidebarPage] = []
    if surfaces.tool_console:
        system_pages.append(SidebarPage("tools", "Tools"))
    system_pages.append(SidebarPage("review", "Review"))
    system_pages.append(SidebarPage("appearance", "Appearance / Settings"))
    groups.append(SidebarGroup("system", "System", tuple(system_pages)))

    return tuple(groups)
