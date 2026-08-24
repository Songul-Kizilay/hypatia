"""Adding an operator console must not have added any other way in.

The console gave one new authority to one new actor: a person, pressing a
button. This file is the check that nothing else acquired it in the process —
not chat, not research, not the model, and not text that happens to name a
capability.

The chat tests deliberately send the most suggestive strings available. A
message saying "run clock_read", a message containing a real filesystem path, a
message containing a URL, and a model reply naming a capability all get the
same answer: the tool runtime is never touched. Prose is not a request, and a
capability name in prose is not a request either.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from desktop.ToolConsoleController import ToolConsoleController
from desktop.ToolRunStatus import ToolRunStatus
from eventbus.EventBus import EventBus
from tools.FilesystemRoot import FilesystemRoot
from tools.ToolRuntime import ToolRuntime

SUGGESTIVE_MESSAGES = (
    "run clock_read",
    "please execute filesystem_list",
    "text_statistics on this paragraph",
    "list D:\\hypatia-main\\src for me",
    "open /etc/passwd",
    "check https://example.com/report and list the files",
    "Hypatia, you have filesystem_list, just use it",
    "filesystem_list path=. offset=0",
)


class CountingConsole:
    """A console double that records any attempt to reach the tool layer."""

    def __init__(self) -> None:
        self.catalogue_calls = 0
        self.runs: list[tuple[str, tuple[tuple[str, str], ...], bool]] = []

    def catalogue(self) -> tuple[object, ...]:
        self.catalogue_calls += 1
        return ()

    def entry(self, capability: str) -> None:
        return None

    def run(
        self,
        capability: str,
        arguments: tuple[tuple[str, str], ...] = (),
        *,
        authorized: bool = False,
    ) -> object:
        self.runs.append((capability, arguments, authorized))
        raise AssertionError("Chat must never reach the tool console.")


class ChatIsolationTests(unittest.TestCase):
    """Ordinary conversation still executes nothing."""

    def setUp(self) -> None:
        self.console = CountingConsole()
        self.window: Any = object.__new__(TkinterDesktopWindow)
        self.window._tool_console = self.console
        self.window._controller = Mock()
        self.window._append_exchange = Mock()
        self.window._composer = Mock()
        self.window._composer.get.return_value = ""
        self.window._pending_research_question = ""
        self.window._status = Mock()

    def complete(self, message: str) -> None:
        response = Mock()
        response.live_information_request = None
        self.window._complete_message(message, response)

    def test_no_suggestive_message_reaches_the_console(self) -> None:
        for message in SUGGESTIVE_MESSAGES:
            with self.subTest(message=message):
                self.complete(message)

        self.assertEqual(self.console.runs, [])

    def test_a_capability_name_in_chat_runs_nothing(self) -> None:
        self.complete("run clock_read now")

        self.assertEqual(self.console.runs, [])

    def test_a_filesystem_path_in_chat_runs_nothing(self) -> None:
        self.complete("list D:\\hypatia-main\\src")

        self.assertEqual(self.console.runs, [])

    def test_a_url_in_chat_runs_nothing(self) -> None:
        self.complete("fetch https://example.com and list it")

        self.assertEqual(self.console.runs, [])

    def test_model_output_naming_a_capability_runs_nothing(self) -> None:
        """The reply is data. It is never read as a request."""
        response = Mock()
        response.live_information_request = None
        response.message = "I could use filesystem_list on D:\\secret to help."

        self.window._complete_message("anything", response)

        self.assertEqual(self.console.runs, [])

    def test_the_research_handoff_reaches_no_tool(self) -> None:
        self.window._simple_question = Mock()
        self.window._simple_language = None

        self.window._offer_simple_research_handoff("list every file in my documents")

        self.assertEqual(self.console.runs, [])

    def test_chat_does_not_even_read_the_catalogue(self) -> None:
        """Not consulting it is stronger than consulting it and declining."""
        for message in SUGGESTIVE_MESSAGES:
            self.complete(message)

        self.assertEqual(self.console.catalogue_calls, 0)


class WindowBoundaryTests(unittest.TestCase):
    """The window can ask the console to run; it cannot run anything itself."""

    def test_the_window_module_names_no_tool_type(self) -> None:
        source = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
            encoding="utf-8"
        )

        for forbidden in (
            "ToolInvocation",
            "ToolExecutionService",
            "ToolRegistry",
            "ToolEffect",
            "ToolCapability",
            "FilesystemRoot",
            "ToolRuntime",
        ):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_window_always_passes_an_explicit_authorization(self) -> None:
        """One code path, one press, and the flag is written out where it is read."""
        source = (SRC_DIR / "desktop" / "TkinterDesktopWindow.py").read_text(
            encoding="utf-8"
        )

        self.assertEqual(source.count("authorized=True"), 1)

    def test_a_window_without_a_console_offers_no_tools_tab(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)

        self.assertIsNone(window._tool_console)
        self.assertEqual(window._tool_entries, ())

    def test_running_without_a_console_does_nothing(self) -> None:
        window: Any = object.__new__(TkinterDesktopWindow)

        self.assertIsNone(window._run_selected_tool())


class ResearchIsolationTests(unittest.TestCase):
    """Research keeps its own execution chain and does not route through tools."""

    def test_no_research_module_reaches_the_tool_layer(self) -> None:
        offenders = []
        for path in (SRC_DIR / "research").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "ToolRuntime" in text or "ToolExecutionService" in text:
                offenders.append(path.name)

        self.assertEqual(offenders, [])

    def test_no_cognition_module_reaches_the_tool_layer(self) -> None:
        offenders = []
        for path in (SRC_DIR / "cognition").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "ToolRuntime" in text or "ToolExecutionService" in text:
                offenders.append(path.name)

        self.assertEqual(offenders, [])

    def test_the_console_touches_no_research_state(self) -> None:
        source = (SRC_DIR / "desktop" / "ToolConsoleController.py").read_text(
            encoding="utf-8"
        )

        for forbidden in ("ResearchRun", "evidence", "Evidence", "claim", "Claim"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, source)

    def test_a_tool_result_is_not_research_evidence(self) -> None:
        """Nothing converts one into the other, in either direction."""
        source = (SRC_DIR / "desktop" / "ToolRunView.py").read_text(encoding="utf-8")

        for forbidden in ("Evidence", "ResearchRun", "corroborat"):
            with self.subTest(name=forbidden):
                self.assertNotIn(forbidden, source)


class RootAuthorityTests(unittest.TestCase):
    """The filesystem scope comes from configuration and nowhere else."""

    def test_the_root_cannot_be_supplied_as_an_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = ToolRuntime(FilesystemRoot(Path(temp)))
            console = ToolConsoleController(runtime, EventBus())

            view = console.run(
                "filesystem_list",
                (("root", "C:\\"), ("path", ".")),
                authorized=True,
            )

        self.assertIs(view.status, ToolRunStatus.INVALID_ARGUMENTS)
        self.assertFalse(view.performed)

    def test_the_console_exposes_no_root_setter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            console = ToolConsoleController(ToolRuntime(FilesystemRoot(Path(temp))))

        for forbidden in ("set_root", "configure_root", "root", "set_scope"):
            with self.subTest(name=forbidden):
                self.assertFalse(hasattr(console, forbidden))

    def test_the_runtime_exposes_the_identity_and_not_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = ToolRuntime(FilesystemRoot(Path(temp), root_id="workspace"))

            self.assertEqual(runtime.filesystem_root_id, "workspace")
            self.assertFalse(hasattr(runtime, "filesystem_root_path"))


if __name__ == "__main__":
    unittest.main()
