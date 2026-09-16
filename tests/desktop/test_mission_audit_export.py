"""Desktop mission audit export previews, confirms, then saves exactly once."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from brain.BrainResponse import BrainResponse
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from research.ResearchMissionAuditExport import (
    ResearchMissionAuditExportPreview,
    mission_audit_filenames,
)


class Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


def preview(plan_id: str = "plan-1") -> ResearchMissionAuditExportPreview:
    markdown, document = mission_audit_filenames(plan_id)
    return ResearchMissionAuditExportPreview(
        plan_id=plan_id,
        research_run_id="run-1",
        markdown_filename=markdown,
        json_filename=document,
        markdown_sha256="a" * 64,
        json_sha256="b" * 64,
        summary="Mission audit for plan plan-1 (run run-1).",
        markdown_preview="# Mission Audit",
        total_markdown_characters=15,
    )


def previewed(value: ResearchMissionAuditExportPreview | None) -> BrainResponse:
    return BrainResponse(
        message="preview",
        request_id="preview",
        intent="research_mission_audit_export_preview",
        memory_count=0,
        success=value is not None,
        research_mission_audit_export_preview=value,
    )


class MissionAuditExportWindowTests(unittest.TestCase):
    def window(self, plan_id: str = "plan-1") -> SimpleNamespace:
        window = SimpleNamespace(
            _controller=Mock(),
            _status=Mock(),
            _append_response=Mock(),
            _root=None,
            _mission_plan_id="",
            _execution_id=Var(plan_id),
            _mission_audit_preview=None,
            _research_plan_preview=Mock(),
        )
        window._audit_plan_id = lambda: TkinterDesktopWindow._audit_plan_id(window)
        return window

    def test_preview_shows_files_and_calls_no_save(self):
        window = self.window()
        window._controller.preview_mission_audit_export.return_value = previewed(
            preview()
        )

        TkinterDesktopWindow._preview_mission_audit_export(window)

        window._controller.preview_mission_audit_export.assert_called_once_with(
            "plan-1"
        )
        window._controller.save_mission_audit_export.assert_not_called()
        shown = window._research_plan_preview.insert.call_args.args[1]
        self.assertIn("mission-audit-plan-1.md", shown)
        self.assertIn("mission-audit-plan-1.json", shown)

    def test_save_requires_a_preview_of_the_named_mission(self):
        window = self.window("plan-2")
        window._mission_audit_preview = preview("plan-1")

        with patch("desktop.TkinterDesktopWindow.filedialog.askdirectory") as ask:
            TkinterDesktopWindow._save_mission_audit_export(window)

        ask.assert_not_called()
        window._controller.save_mission_audit_export.assert_not_called()

    def test_cancelled_directory_or_declined_confirmation_writes_nothing(self):
        for directory, confirmed in (("", True), ("C:/exports", False)):
            with self.subTest(directory=directory, confirmed=confirmed):
                window = self.window()
                window._mission_audit_preview = preview()
                with (
                    patch(
                        "desktop.TkinterDesktopWindow.filedialog.askdirectory",
                        return_value=directory,
                    ),
                    patch(
                        "desktop.TkinterDesktopWindow.messagebox.askyesno",
                        return_value=confirmed,
                    ),
                ):
                    TkinterDesktopWindow._save_mission_audit_export(window)

                window._controller.save_mission_audit_export.assert_not_called()

    def test_confirmed_save_sends_exactly_the_preview(self):
        window = self.window()
        value = preview()
        window._mission_audit_preview = value
        window._controller.save_mission_audit_export.return_value = BrainResponse(
            message="saved",
            request_id="save",
            intent="research_mission_audit_export_save",
            memory_count=0,
        )

        with (
            patch(
                "desktop.TkinterDesktopWindow.filedialog.askdirectory",
                return_value="C:/exports",
            ),
            patch(
                "desktop.TkinterDesktopWindow.messagebox.askyesno", return_value=True
            ) as confirm,
        ):
            TkinterDesktopWindow._save_mission_audit_export(window)

        text = confirm.call_args.args[1]
        self.assertIn("mission-audit-plan-1.md", text)
        self.assertIn("b" * 64, text)
        window._controller.save_mission_audit_export.assert_called_once_with(
            value, "C:/exports"
        )


if __name__ == "__main__":
    unittest.main()
