"""Tkinter boundary tests for one confirmed, literal local-file preview."""

from __future__ import annotations

import sys
import unittest
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from desktop.DesktopRequestRunner import DesktopRequestCompletion
from desktop.FilesystemContentPreview import FilesystemContentPreview
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from desktop.ToolArgumentKind import ToolArgumentKind
from desktop.ToolArgumentSpec import ToolArgumentSpec
from desktop.ToolConsoleEntry import ToolConsoleEntry
from desktop.ToolRunStatus import ToolRunStatus
from desktop.ToolRunView import ToolRunView

SENTINEL_TEXT = "# literal\n[do not run](command://unsafe)"


class RecordingVariable:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class RecordingText:
    def __init__(self) -> None:
        self.value = ""
        self.states: list[object] = []

    def configure(self, **changes: object) -> None:
        if "state" in changes:
            self.states.append(changes["state"])

    def delete(self, _start: object, _end: object) -> None:
        self.value = ""

    def insert(self, _position: object, value: str) -> None:
        self.value += value


class RecordingConsole:
    def __init__(self, view: ToolRunView, problem: str | None = None) -> None:
        self.view = view
        self.problem = problem
        self.runs: list[tuple[str, tuple[tuple[str, str], ...], bool]] = []

    def validation_problem(
        self,
        capability: str,
        arguments: tuple[tuple[str, str], ...],
    ) -> str | None:
        del capability, arguments
        return self.problem

    def run(
        self,
        capability: str,
        arguments: tuple[tuple[str, str], ...],
        *,
        authorized: bool,
    ) -> ToolRunView:
        self.runs.append((capability, arguments, authorized))
        return self.view


class ImmediateRunner:
    def __init__(self) -> None:
        self.completions: list[DesktopRequestCompletion[object]] = []

    def start(
        self,
        action: Callable[[], object],
        *,
        cancel_callback: Callable[[], None] | None = None,
    ) -> Literal["started"]:
        del cancel_callback
        self.completions.append(DesktopRequestCompletion(value=action()))
        return "started"

    def drain(self) -> tuple[DesktopRequestCompletion[object], ...]:
        values = tuple(self.completions)
        self.completions.clear()
        return values

    def is_running(self) -> bool:
        return False

    def is_cancellation_requested(self) -> bool:
        return False


class RecordingRoot:
    def __init__(self) -> None:
        self.after_calls = 0

    def after(self, _delay: int, _callback: Callable[[], None]) -> None:
        self.after_calls += 1


def entry() -> ToolConsoleEntry:
    return ToolConsoleEntry(
        capability="filesystem_read",
        description="Read one bounded local range.",
        effects=("reads_filesystem_content",),
        read_only=True,
        reaches_outside=False,
        arguments=(
            ToolArgumentSpec(
                "path", "Entry", ToolArgumentKind.RELATIVE_PATH, required=True
            ),
            ToolArgumentSpec(
                "offset", "Byte offset", ToolArgumentKind.WHOLE_NUMBER, required=True
            ),
            ToolArgumentSpec(
                "max_bytes",
                "Maximum bytes",
                ToolArgumentKind.WHOLE_NUMBER,
                required=True,
            ),
        ),
        scope_label="Scope: workspace",
    )


def preview() -> FilesystemContentPreview:
    count = len(SENTINEL_TEXT.encode())
    return FilesystemContentPreview(
        request_id="request-1",
        root_id="workspace",
        resource="notes/readme.md",
        offset=0,
        bytes_requested=count,
        bytes_returned=count,
        truncated=False,
        file_size_bytes=count,
        modified_utc=datetime(2026, 8, 24, 20, 0, tzinfo=UTC),
        bom_stripped=False,
        read_at_utc=datetime(2026, 8, 24, 20, 1, tzinfo=UTC),
        source_kind="local_filesystem",
        encoding="utf-8",
        taint_label="external_untrusted_data",
        instruction_authority="none",
        disclosure_class="local_only",
        text=SENTINEL_TEXT,
    )


def run_view(*, content: FilesystemContentPreview | None = None) -> ToolRunView:
    return ToolRunView(
        capability="filesystem_read",
        status=ToolRunStatus.SUCCEEDED,
        performed=True,
        succeeded=True,
        detail="Read one bounded UTF-8 text range.",
        declared_effects=("reads_filesystem_content",),
        authorized_effects=("reads_filesystem_content",),
        request_id=content.request_id if content is not None else "request-1",
        content_preview=content,
    )


def configured_window(console: RecordingConsole) -> Any:
    window: Any = object.__new__(TkinterDesktopWindow)
    window._tool_console = console
    window._tool_entries = (entry(),)
    window._tool_choice = RecordingVariable("filesystem_read")
    window._tool_argument_texts = {}
    window._tool_argument_values = {
        "path": RecordingVariable("notes/readme.md"),
        "offset": RecordingVariable("0"),
        "max_bytes": RecordingVariable(str(len(SENTINEL_TEXT.encode()))),
    }
    window._tool_status = RecordingVariable()
    window._tool_output = RecordingText()
    window._tool_content_metadata = RecordingVariable()
    window._tool_content_output = RecordingText()
    window._root = object()
    return window


class FilesystemContentConfirmationTests(unittest.TestCase):
    def test_invalid_form_never_opens_confirmation_or_runs(self) -> None:
        console = RecordingConsole(run_view(), problem="Invalid range.")
        window = configured_window(console)

        with patch("desktop.TkinterDesktopWindow.messagebox.askyesno") as confirmation:
            window._run_selected_tool()

        confirmation.assert_not_called()
        self.assertEqual(console.runs, [])
        self.assertEqual(window._tool_status.value, "Invalid range.")

    def test_cancelled_confirmation_creates_no_invocation(self) -> None:
        console = RecordingConsole(run_view())
        window = configured_window(console)

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=False
        ) as confirmation:
            window._run_selected_tool()

        self.assertEqual(console.runs, [])
        shown = confirmation.call_args.args[1]
        for exact in (
            "Capability: filesystem_read",
            "Requires: reads_filesystem_content",
            "Scope: workspace",
            "Entry: notes/readme.md",
            "Offset: 0",
            f"Maximum: {len(SENTINEL_TEXT.encode())} bytes",
        ):
            self.assertIn(exact, shown)

    def test_acceptance_runs_the_exact_confirmed_tuple_once(self) -> None:
        value = run_view(content=preview())
        console = RecordingConsole(value)
        window = configured_window(console)
        window._start_tool_request = lambda action, on_success, _label: on_success(
            action()
        )

        with patch(
            "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
        ):
            window._run_selected_tool()

        self.assertEqual(
            console.runs,
            [
                (
                    "filesystem_read",
                    (
                        ("path", "notes/readme.md"),
                        ("offset", "0"),
                        ("max_bytes", str(len(SENTINEL_TEXT.encode()))),
                    ),
                    True,
                )
            ],
        )


class FilesystemContentPresentationTests(unittest.TestCase):
    def test_content_is_inserted_literally_and_provenance_is_separate(self) -> None:
        window = configured_window(RecordingConsole(run_view()))

        window._present_filesystem_content(preview())

        self.assertEqual(window._tool_content_output.value, SENTINEL_TEXT)
        self.assertIn(
            "Instruction authority: none", window._tool_content_metadata.value
        )
        self.assertNotIn(SENTINEL_TEXT, window._tool_content_metadata.value)

    def test_a_non_content_terminal_result_clears_stale_content(self) -> None:
        window = configured_window(RecordingConsole(run_view()))
        window._tool_content_output.value = SENTINEL_TEXT
        window._tool_content_metadata.value = "stale"

        window._present_tool_run(run_view())

        self.assertEqual(window._tool_content_output.value, "")
        self.assertEqual(window._tool_content_metadata.value, "")

    def test_tool_result_crosses_existing_single_flight_completion_boundary(
        self,
    ) -> None:
        window = configured_window(RecordingConsole(run_view()))
        window._request_runner = ImmediateRunner()
        window._request_completion_handler = None
        window._request_controls = []
        window._request_label = None
        window._request_started_at = None
        window._closing = False
        window._status = RecordingVariable()
        window._root = RecordingRoot()
        window._research_refresh_signal = None
        presented = Mock()

        window._start_tool_request(
            lambda: run_view(content=preview()), presented, "read"
        )
        window._poll_requests()

        presented.assert_called_once()
        self.assertIsInstance(presented.call_args.args[0], ToolRunView)
        self.assertEqual(window._root.after_calls, 1)

    def test_cancellation_clears_content_without_claiming_to_kill_io(self) -> None:
        window = configured_window(RecordingConsole(run_view()))
        window._tool_content_output.value = SENTINEL_TEXT
        window._tool_content_metadata.value = "stale"
        window._request_runner = Mock()
        window._request_runner.request_cancel.return_value = "requested"
        window._closing = False
        window._status = RecordingVariable()
        window._request_label = "Local file read"
        window._cancel_button = Mock()

        window._cancel_request()

        self.assertEqual(window._tool_content_output.value, "")
        self.assertEqual(window._tool_content_metadata.value, "")
        self.assertIn("waiting", window._status.value)

    def test_close_clears_content_and_discards_late_worker_result(self) -> None:
        window = configured_window(RecordingConsole(run_view()))
        window._tool_content_output.value = SENTINEL_TEXT
        window._tool_content_metadata.value = "stale"
        window._request_runner = Mock()
        window._request_completion_handler = Mock()
        window._closing = False
        window._root = Mock()

        window._close()

        self.assertEqual(window._tool_content_output.value, "")
        self.assertEqual(window._tool_content_metadata.value, "")
        self.assertIsNone(window._request_completion_handler)
        window._request_runner.stop.assert_called_once_with()
        window._root.destroy.assert_called_once_with()

    def test_source_contains_no_content_export_or_clipboard_write(self) -> None:
        source = (SRC_DIR / "desktop/TkinterDesktopWindow.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('"<<Copy>>"', source)
        for forbidden in (
            "clipboard_append",
            "clipboard_clear",
            "save_filesystem_content",
            "export_filesystem_content",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
