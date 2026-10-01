"""A collapsible, scrollable left sidebar for the desktop shell.

Renders the groups `SidebarPageRegistry` already decided exist as a column
of collapsible sections, each holding page buttons. Selecting one only ever
calls back into `on_select` with that page's stable id -- this widget reads
no controller, store or feature flag, and starts no request of its own; it
is purely a navigation surface over pages the caller already built.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from functools import partial
from tkinter import ttk

from desktop.SidebarPageRegistry import SidebarGroup

_EXPANDED_WIDTH = 220
_COLLAPSED_WIDTH = 36
_EXPANDED_MARKER = "▾"
_COLLAPSED_MARKER = "▸"
_COLLAPSE_GLYPH = "«"
_EXPAND_GLYPH = "»"


class SidebarNavigationView:
    """Owns the sidebar's own widgets; the caller owns what they navigate to."""

    def __init__(
        self,
        parent: tk.Misc,
        groups: tuple[SidebarGroup, ...],
        on_select: Callable[[str], None],
    ) -> None:
        self._on_select = on_select
        self._groups = groups
        self._collapsed = False
        self._active_page_id: str | None = None
        self._page_buttons: dict[str, ttk.Button] = {}
        self._group_bodies: dict[str, ttk.Frame] = {}
        self._group_headers: dict[str, ttk.Button] = {}
        self._group_expanded: dict[str, bool] = {
            group.group_id: True for group in groups
        }

        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        header_bar = ttk.Frame(self.frame)
        header_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        header_bar.columnconfigure(0, weight=1)
        self._collapse_button = ttk.Button(
            header_bar,
            text=_COLLAPSE_GLYPH,
            width=3,
            command=self.toggle_collapsed,
        )
        self._collapse_button.grid(row=0, column=1, sticky="e", padx=4, pady=4)

        self._canvas = tk.Canvas(self.frame, highlightthickness=0, bd=0)
        self._canvas.grid(row=1, column=0, sticky="nsew")
        self._scrollbar = ttk.Scrollbar(
            self.frame, orient="vertical", command=self._canvas.yview
        )
        self._scrollbar.grid(row=1, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._body = ttk.Frame(self._canvas)
        self._body_id = self._canvas.create_window(
            (0, 0), window=self._body, anchor="nw"
        )
        self._body.bind("<Configure>", self._on_body_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        for group in groups:
            self._build_group(group)
        self._canvas.configure(width=_EXPANDED_WIDTH)

    def set_canvas_background(self, color: str) -> None:
        """Match the classic `tk.Canvas` to the themed palette's background.

        `tk.Canvas` predates ttk and ignores `ttk.Style` entirely, unlike
        every other widget here, so this is the one color the caller must
        push in directly whenever the accessibility theme changes.
        """
        self._canvas.configure(background=color)

    # -- scroll-region plumbing ---------------------------------------------

    def _on_body_configure(self, _event: tk.Event[ttk.Frame]) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event[tk.Canvas]) -> None:
        self._canvas.itemconfigure(self._body_id, width=event.width)

    # -- group construction ---------------------------------------------------

    def _build_group(self, group: SidebarGroup) -> None:
        header = ttk.Button(
            self._body,
            text=self._group_header_text(group),
            command=lambda: self._toggle_group(group.group_id),
            style="SidebarGroup.TButton",
        )
        header.pack(fill="x", pady=(8, 0), padx=2)
        self._group_headers[group.group_id] = header

        body = ttk.Frame(self._body)
        body.pack(fill="x")
        self._group_bodies[group.group_id] = body

        for page in group.pages:
            button = ttk.Button(
                body,
                text=page.label,
                command=partial(self._on_select, page.page_id),
                style="SidebarPage.TButton",
            )
            button.pack(fill="x", padx=(16, 2), pady=1)
            self._page_buttons[page.page_id] = button

    def _group_header_text(self, group: SidebarGroup) -> str:
        marker = (
            _EXPANDED_MARKER
            if self._group_expanded[group.group_id]
            else (_COLLAPSED_MARKER)
        )
        return f"{marker} {group.title}"

    def _toggle_group(self, group_id: str) -> None:
        expanded = not self._group_expanded[group_id]
        self._group_expanded[group_id] = expanded
        body = self._group_bodies[group_id]
        if expanded:
            body.pack(fill="x")
        else:
            body.pack_forget()
        group = next(g for g in self._groups if g.group_id == group_id)
        self._group_headers[group_id].configure(text=self._group_header_text(group))

    # -- active-page highlighting ---------------------------------------------

    def set_active_page(self, page_id: str) -> None:
        """Mark exactly one page button as active; never starts a request."""
        if self._active_page_id is not None:
            previous = self._page_buttons.get(self._active_page_id)
            if previous is not None:
                previous.configure(style="SidebarPage.TButton")
        current = self._page_buttons.get(page_id)
        if current is not None:
            current.configure(style="SidebarPageActive.TButton")
        self._active_page_id = page_id

    # -- whole-sidebar collapse / expand ---------------------------------------

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def toggle_collapsed(self) -> None:
        if self._collapsed:
            self.expand()
        else:
            self.collapse()

    def collapse(self) -> None:
        """Hide the page list down to a thin strip, for a narrower screen."""
        self._collapsed = True
        for body in self._group_bodies.values():
            body.pack_forget()
        for header in self._group_headers.values():
            header.pack_forget()
        self._canvas.configure(width=_COLLAPSED_WIDTH)
        self._scrollbar.grid_remove()
        self._collapse_button.configure(text=_EXPAND_GLYPH)

    def expand(self) -> None:
        """Restore every group header, and each group's own expanded state."""
        self._collapsed = False
        for group in self._groups:
            self._group_headers[group.group_id].pack(fill="x", pady=(8, 0), padx=2)
            if self._group_expanded[group.group_id]:
                self._group_bodies[group.group_id].pack(fill="x")
        self._canvas.configure(width=_EXPANDED_WIDTH)
        self._scrollbar.grid()
        self._collapse_button.configure(text=_COLLAPSE_GLYPH)
