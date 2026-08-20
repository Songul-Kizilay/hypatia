"""Desktop entry-point coverage without creating a real window."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import desktop_main
from brain.Brain import Brain
from desktop.DesktopDataPaths import DesktopDataPaths


class DesktopMainTests(unittest.TestCase):
    def test_main_uses_desktop_owned_paths_and_stops_after_window_closes(self) -> None:
        paths = DesktopDataPaths(Path("C:/Users/Songul/AppData/Local/Hypatia"))
        brain = Mock(spec=Brain)
        container = Mock()
        container.resolve.return_value = brain
        application = Mock()
        application.bootstrap.container = container
        window = Mock()

        with (
            patch(
                "desktop_main.DesktopDataPaths.from_process_environment",
                return_value=paths,
            ) as path_factory,
            patch(
                "desktop_main.HypatiaApplication.from_process_environment",
                return_value=application,
            ) as application_factory,
            patch(
                "desktop_main.TkinterDesktopWindow", return_value=window
            ) as window_type,
        ):
            desktop_main.main()

        path_factory.assert_called_once_with()
        application_factory.assert_called_once_with(
            memory_path=paths.memory_path,
            session_path=paths.session_path,
            knowledge_relation_path=paths.knowledge_relation_path,
            research_run_path=paths.research_run_path,
        )
        application.start.assert_called_once_with()
        container.resolve.assert_called_once_with(Brain)
        window_type.assert_called_once()
        window.run.assert_called_once_with()
        application.stop.assert_called_once_with()
