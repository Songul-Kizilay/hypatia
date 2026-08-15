"""Unit coverage for installed-desktop local persistence paths."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from desktop.DesktopDataPaths import DesktopDataPaths


class DesktopDataPathsTests(unittest.TestCase):
    def test_windows_defaults_to_local_app_data(self) -> None:
        paths = DesktopDataPaths.from_process_environment(
            {"LOCALAPPDATA": "C:/Users/Songul/AppData/Local"},
            platform_name="nt",
            home=Path("C:/Users/Songul"),
        )

        self.assertEqual(paths.root, Path("C:/Users/Songul/AppData/Local/Hypatia"))
        self.assertEqual(paths.memory_path, paths.root / "memory" / "memory.json")
        self.assertEqual(paths.session_path, paths.root / "sessions" / "sessions.json")
        self.assertEqual(
            paths.knowledge_relation_path,
            paths.root / "knowledge" / "relations.json",
        )

    def test_explicit_absolute_override_wins_over_platform_defaults(self) -> None:
        paths = DesktopDataPaths.from_process_environment(
            {"HYPATIA_DESKTOP_DATA_DIR": "C:/Hypatia Data"},
            platform_name="nt",
            home=Path("C:/Users/Songul"),
        )

        self.assertEqual(paths.root, Path("C:/Hypatia Data"))

    def test_relative_override_is_rejected_before_bootstrap(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be an absolute path"):
            DesktopDataPaths.from_process_environment(
                {"HYPATIA_DESKTOP_DATA_DIR": "relative-data"},
                platform_name="nt",
                home=Path("C:/Users/Songul"),
            )

    def test_windows_without_local_app_data_falls_back_to_user_profile(self) -> None:
        paths = DesktopDataPaths.from_process_environment(
            {},
            platform_name="nt",
            home=Path("C:/Users/Songul"),
        )

        self.assertEqual(paths.root, Path("C:/Users/Songul/AppData/Local/Hypatia"))
