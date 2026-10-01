"""Direct coverage for the sidebar widget's own interactive logic.

`test_research_command_bindings.py` already proves `SidebarNavigationView`
participates correctly inside the real desktop shell by driving the real
`_build_layout`. This file drives the widget itself, directly, with the real
Tk widget classes it constructs replaced by permissive recorders -- the one
piece of genuinely new interactive logic this milestone adds (selection,
active-page highlighting, per-group collapse, whole-sidebar collapse) that
nothing else exercises.
"""

from __future__ import annotations

import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from desktop.SidebarNavigationView import SidebarNavigationView
from desktop.SidebarPageRegistry import SidebarEnabledSurfaces, build_sidebar_groups


class RecordingWidget:
    """Accept anything Tk accepts; remember only configuration and geometry.

    Deliberately permissive, in the same spirit as the recorder in
    `test_research_command_bindings.py`: the point is to let the widget's
    own construction and layout calls run unchanged, not to model Tk.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.parent = args[0] if args else None
        self.kwargs: dict[str, Any] = dict(kwargs)
        self.packed = False
        self.gridded = False

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        def call(*args: Any, **kwargs: Any) -> Any:
            return None

        return call

    def configure(self, **kwargs: Any) -> None:
        self.kwargs.update(kwargs)

    def pack(self, *args: Any, **kwargs: Any) -> None:
        self.packed = True

    def pack_forget(self) -> None:
        self.packed = False

    def grid(self, *args: Any, **kwargs: Any) -> None:
        self.gridded = True

    def grid_remove(self) -> None:
        self.gridded = False

    @property
    def style(self) -> Any:
        return self.kwargs.get("style")

    @property
    def text(self) -> Any:
        return self.kwargs.get("text")

    @property
    def command(self) -> Any:
        return self.kwargs.get("command")


class RecordingCanvas(RecordingWidget):
    def create_window(self, *args: Any, **kwargs: Any) -> int:
        return 1

    def itemconfigure(self, *args: Any, **kwargs: Any) -> None:
        return None

    def bbox(self, *args: Any, **kwargs: Any) -> tuple[int, int, int, int]:
        return (0, 0, 0, 0)


def _build_sidebar(
    on_select: Any, *, program_scope: bool = True
) -> SidebarNavigationView:
    """Construct a real `SidebarNavigationView` with recorder widgets.

    `program_scope=True` by default so the sidebar has more than one
    group's worth of pages to exercise cross-group independence.
    """
    groups = build_sidebar_groups(SidebarEnabledSurfaces(program_scope=program_scope))
    module = "desktop.SidebarNavigationView"
    with ExitStack() as stack:
        stack.enter_context(patch(f"{module}.ttk.Frame", RecordingWidget))
        stack.enter_context(patch(f"{module}.ttk.Button", RecordingWidget))
        stack.enter_context(patch(f"{module}.ttk.Scrollbar", RecordingWidget))
        stack.enter_context(patch(f"{module}.tk.Canvas", RecordingCanvas))
        return SidebarNavigationView(RecordingWidget(), groups, on_select=on_select)


class SelectionTests(unittest.TestCase):
    def test_clicking_a_page_button_selects_that_exact_page_id(self) -> None:
        selected: list[str] = []
        sidebar = _build_sidebar(selected.append)

        sidebar._page_buttons["knowledge"].command()

        self.assertEqual(selected, ["knowledge"])

    def test_each_page_button_is_bound_to_its_own_id_not_a_shared_one(self) -> None:
        selected: list[str] = []
        sidebar = _build_sidebar(selected.append)

        sidebar._page_buttons["chat"].command()
        sidebar._page_buttons["kali_tools"].command()

        self.assertEqual(selected, ["chat", "kali_tools"])


class ActivePageHighlightingTests(unittest.TestCase):
    def test_the_first_activated_page_is_marked_active(self) -> None:
        sidebar = _build_sidebar(lambda _page_id: None)

        sidebar.set_active_page("chat")

        self.assertEqual(
            sidebar._page_buttons["chat"].style, "SidebarPageActive.TButton"
        )

    def test_activating_a_new_page_restores_the_previous_one(self) -> None:
        sidebar = _build_sidebar(lambda _page_id: None)

        sidebar.set_active_page("chat")
        sidebar.set_active_page("knowledge")

        self.assertEqual(sidebar._page_buttons["chat"].style, "SidebarPage.TButton")
        self.assertEqual(
            sidebar._page_buttons["knowledge"].style, "SidebarPageActive.TButton"
        )

    def test_never_more_than_one_page_is_active_at_once(self) -> None:
        sidebar = _build_sidebar(lambda _page_id: None)

        for page_id in ("chat", "knowledge", "research_simple", "kali_tools"):
            sidebar.set_active_page(page_id)

        active = [
            page_id
            for page_id, button in sidebar._page_buttons.items()
            if button.style == "SidebarPageActive.TButton"
        ]
        self.assertEqual(active, ["kali_tools"])


class GroupCollapseTests(unittest.TestCase):
    def test_toggling_one_group_does_not_affect_another(self) -> None:
        sidebar = _build_sidebar(lambda _page_id: None)

        sidebar._toggle_group("home")

        self.assertFalse(sidebar._group_bodies["home"].packed)
        self.assertTrue(sidebar._group_bodies["research"].packed)

    def test_toggling_a_group_flips_its_header_marker(self) -> None:
        sidebar = _build_sidebar(lambda _page_id: None)
        collapsed_marker = "▸"

        sidebar._toggle_group("home")

        self.assertIn(collapsed_marker, sidebar._group_headers["home"].text)

    def test_toggling_twice_restores_the_group(self) -> None:
        sidebar = _build_sidebar(lambda _page_id: None)

        sidebar._toggle_group("home")
        sidebar._toggle_group("home")

        self.assertTrue(sidebar._group_bodies["home"].packed)


class WholeSidebarCollapseTests(unittest.TestCase):
    def test_collapse_hides_every_group_header_and_body(self) -> None:
        sidebar = _build_sidebar(lambda _page_id: None)

        sidebar.collapse()

        self.assertTrue(sidebar.collapsed)
        self.assertFalse(sidebar._group_bodies["home"].packed)
        self.assertFalse(sidebar._group_headers["home"].packed)

    def test_expand_restores_a_group_the_user_never_touched(self) -> None:
        sidebar = _build_sidebar(lambda _page_id: None)

        sidebar.collapse()
        sidebar.expand()

        self.assertFalse(sidebar.collapsed)
        self.assertTrue(sidebar._group_bodies["home"].packed)
        self.assertTrue(sidebar._group_headers["home"].packed)

    def test_expand_does_not_resurrect_a_group_the_user_manually_collapsed(
        self,
    ) -> None:
        """A manual per-group collapse must survive a whole-sidebar cycle.

        `collapse()` hides every body unconditionally; `expand()` only
        re-shows a body that was still expanded beforehand. A user who
        collapsed "research" by hand should not have it silently reopened
        just because they collapsed and re-expanded the whole sidebar.
        """
        sidebar = _build_sidebar(lambda _page_id: None)
        sidebar._toggle_group("research")

        sidebar.collapse()
        sidebar.expand()

        self.assertFalse(sidebar._group_bodies["research"].packed)
        self.assertTrue(sidebar._group_bodies["home"].packed)

    def test_toggle_collapsed_alternates_between_collapse_and_expand(self) -> None:
        sidebar = _build_sidebar(lambda _page_id: None)

        sidebar.toggle_collapsed()
        self.assertTrue(sidebar.collapsed)

        sidebar.toggle_collapsed()
        self.assertFalse(sidebar.collapsed)


if __name__ == "__main__":
    unittest.main()
