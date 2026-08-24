"""Launch the local Tkinter desktop shell over the existing Hypatia runtime."""

from __future__ import annotations

from brain.Brain import Brain
from core.Application import HypatiaApplication
from desktop.DesktopController import DesktopController
from desktop.DesktopDataPaths import DesktopDataPaths
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from desktop.ToolConsoleController import ToolConsoleController
from eventbus.EventBus import EventBus
from tools.FilesystemRootPolicy import resolve_filesystem_root
from tools.ToolRuntime import ToolRuntime


def _verify_inert_platform_boundary_imports() -> None:
    """Keep inert platform modules importable in the packaged desktop."""
    from tools.WindowsRootedOpen import WindowsRootedOpen

    if WindowsRootedOpen.__module__ != "tools.WindowsRootedOpen":
        raise RuntimeError("A required platform boundary could not be imported.")


def main() -> None:
    """Start Hypatia's runtime, then hand its Brain to the desktop adapter."""
    # The module import binds no native API and registers no capability. Running
    # it before ordinary startup makes the existing packaged-desktop smoke test
    # prove that PyInstaller included the production-owned inert boundary.
    _verify_inert_platform_boundary_imports()
    data_paths = DesktopDataPaths.from_process_environment()
    app = HypatiaApplication.from_process_environment(
        memory_path=data_paths.memory_path,
        session_path=data_paths.session_path,
        knowledge_relation_path=data_paths.knowledge_relation_path,
        research_run_path=data_paths.research_run_path,
        research_source_content_path=data_paths.research_source_content_path,
    )
    app.start()

    try:
        brain = app.bootstrap.container.resolve(Brain)
        event_bus = app.bootstrap.container.resolve(EventBus)
        # The tool runtime is composed here, in the same place that already
        # decides where this installation keeps its data. Its filesystem scope
        # defaults to that directory and can only be widened by an operator
        # environment variable — never by a model, a message, or an argument.
        tool_runtime = ToolRuntime(
            resolve_filesystem_root(default_root=data_paths.root),
            event_bus=event_bus,
        )
        TkinterDesktopWindow(
            DesktopController(brain),
            event_bus=event_bus,
            tool_console=ToolConsoleController(tool_runtime, event_bus),
        ).run()
    finally:
        app.stop()


if __name__ == "__main__":
    main()
