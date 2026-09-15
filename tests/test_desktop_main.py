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
from cognition.ResearchProgramScopeEnrollmentService import (
    ResearchProgramScopeEnrollmentService,
)
from desktop.DesktopDataPaths import DesktopDataPaths
from desktop.ToolConsoleController import ToolConsoleController
from eventbus.EventBus import EventBus
from research.JsonFileResearchProgramScopeRevisionStore import (
    JsonFileResearchProgramScopeRevisionStore,
)
from tools.FilesystemReadTool import FilesystemReadTool
from tools.FilesystemRoot import FilesystemRoot
from tools.WindowsRootedOpen import (
    WindowsRootedOpenError,
    WindowsRootedOpenFailure,
)


class DesktopMainTests(unittest.TestCase):
    def test_content_composition_requires_a_resolved_root(self) -> None:
        with patch("desktop_main.WindowsRootedOpen") as reader_type:
            tool = desktop_main._compose_filesystem_read_tool(None)

        self.assertIsNone(tool)
        reader_type.assert_not_called()

    def test_content_composition_builds_the_exact_tool_from_the_same_root(
        self,
    ) -> None:
        root = Mock(spec=FilesystemRoot)
        root.root_id = "workspace"
        reader = Mock()
        reader.root_id = "workspace"
        reader.read_range = Mock()

        with patch(
            "desktop_main.WindowsRootedOpen", return_value=reader
        ) as reader_type:
            tool = desktop_main._compose_filesystem_read_tool(root)

        self.assertIsInstance(tool, FilesystemReadTool)
        assert tool is not None
        reader_type.assert_called_once_with(root)
        self.assertEqual(tool.root_id, "workspace")

    def test_bounded_platform_failure_leaves_content_capability_absent(self) -> None:
        root = Mock(spec=FilesystemRoot)
        root.root_id = "workspace"

        with patch(
            "desktop_main.WindowsRootedOpen",
            side_effect=WindowsRootedOpenError(WindowsRootedOpenFailure.NOT_WINDOWS),
        ):
            tool = desktop_main._compose_filesystem_read_tool(root)

        self.assertIsNone(tool)

    def test_main_uses_desktop_owned_paths_and_stops_after_window_closes(self) -> None:
        paths = DesktopDataPaths(Path("C:/Users/Songul/AppData/Local/Hypatia"))
        brain = Mock(spec=Brain)
        # The tool console subscribes to the bus, so resolve must answer with
        # the right kind of object per type rather than one Mock for both.
        event_bus = EventBus()
        container = Mock()
        container.resolve.side_effect = lambda requested: (
            brain if requested is Brain else event_bus
        )
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
            patch(
                "desktop_main.resolve_filesystem_root", return_value=None
            ) as root_policy,
        ):
            desktop_main.main()

        path_factory.assert_called_once_with()
        application_factory.assert_called_once_with(
            memory_path=paths.memory_path,
            session_path=paths.session_path,
            knowledge_relation_path=paths.knowledge_relation_path,
            research_run_path=paths.research_run_path,
            research_source_content_path=paths.research_source_content_path,
            research_program_scope_revision_path=(
                paths.research_program_scope_revision_path
            ),
            # The desktop resumes restored missions on its worker after launch.
            defer_mission_recovery=True,
        )
        application.start.assert_called_once_with()
        # The desktop now also resolves the runtime event bus, so it can
        # refresh research state from canonical reads when a run changes.
        # The guarantee here is that both come from the same container,
        # not that exactly one thing is resolved.
        self.assertEqual(
            [call.args[0] for call in container.resolve.call_args_list],
            [Brain, EventBus],
        )
        window_type.assert_called_once()
        window.run.assert_called_once_with()
        application.stop.assert_called_once_with()
        # The filesystem scope is decided from the desktop's own data root, by
        # the policy, at composition time. Nothing later can widen it, and no
        # argument or message can supply one.
        root_policy.assert_called_once_with(default_root=paths.root)
        console = window_type.call_args.kwargs["tool_console"]
        self.assertIsInstance(console, ToolConsoleController)
        scope_service = window_type.call_args.kwargs["program_scope_enrollment_service"]
        self.assertIsInstance(scope_service, ResearchProgramScopeEnrollmentService)

    def test_main_composes_program_scope_enrollment_from_desktop_data_path(
        self,
    ) -> None:
        paths = DesktopDataPaths(Path("C:/Users/Songul/AppData/Local/Hypatia"))
        brain = Mock(spec=Brain)
        event_bus = EventBus()
        container = Mock()
        container.resolve.side_effect = lambda requested: (
            brain if requested is Brain else event_bus
        )
        application = Mock()
        application.bootstrap.container = container
        store = Mock(spec=JsonFileResearchProgramScopeRevisionStore)
        store.load.return_value = []

        with (
            patch(
                "desktop_main.DesktopDataPaths.from_process_environment",
                return_value=paths,
            ),
            patch(
                "desktop_main.HypatiaApplication.from_process_environment",
                return_value=application,
            ),
            patch("desktop_main.TkinterDesktopWindow", return_value=Mock()),
            patch("desktop_main.resolve_filesystem_root", return_value=None),
            patch(
                "desktop_main.JsonFileResearchProgramScopeRevisionStore",
                return_value=store,
            ) as store_type,
        ):
            desktop_main.main()

        store_type.assert_called_once_with(paths.research_program_scope_revision_path)

    def test_main_composes_a_console_that_runs_nothing_on_its_own(self) -> None:
        """Composition wires the console. It does not authorize anything."""
        paths = DesktopDataPaths(Path("C:/Users/Songul/AppData/Local/Hypatia"))
        brain = Mock(spec=Brain)
        event_bus = EventBus()
        container = Mock()
        container.resolve.side_effect = lambda requested: (
            brain if requested is Brain else event_bus
        )
        application = Mock()
        application.bootstrap.container = container

        with (
            patch(
                "desktop_main.DesktopDataPaths.from_process_environment",
                return_value=paths,
            ),
            patch(
                "desktop_main.HypatiaApplication.from_process_environment",
                return_value=application,
            ),
            patch(
                "desktop_main.TkinterDesktopWindow", return_value=Mock()
            ) as window_type,
            patch("desktop_main.resolve_filesystem_root", return_value=None),
        ):
            desktop_main.main()

        console = window_type.call_args.kwargs["tool_console"]
        view = console.run("clock_read")

        self.assertFalse(view.performed)

    def test_main_without_a_root_registers_no_filesystem_capability(self) -> None:
        paths = DesktopDataPaths(Path("C:/Users/Songul/AppData/Local/Hypatia"))
        brain = Mock(spec=Brain)
        event_bus = EventBus()
        container = Mock()
        container.resolve.side_effect = lambda requested: (
            brain if requested is Brain else event_bus
        )
        application = Mock()
        application.bootstrap.container = container

        with (
            patch(
                "desktop_main.DesktopDataPaths.from_process_environment",
                return_value=paths,
            ),
            patch(
                "desktop_main.HypatiaApplication.from_process_environment",
                return_value=application,
            ),
            patch(
                "desktop_main.TkinterDesktopWindow", return_value=Mock()
            ) as window_type,
            patch("desktop_main.resolve_filesystem_root", return_value=None),
        ):
            desktop_main.main()

        console = window_type.call_args.kwargs["tool_console"]
        names = [entry.capability for entry in console.catalogue()]

        self.assertEqual(names, ["clock_read", "text_statistics"])
