"""Launch the local Tkinter desktop shell over the existing Hypatia runtime."""

from __future__ import annotations

from brain.Brain import Brain
from core.Application import HypatiaApplication
from desktop.DesktopController import DesktopController
from desktop.DesktopDataPaths import DesktopDataPaths
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from eventbus.EventBus import EventBus


def main() -> None:
    """Start Hypatia's runtime, then hand its Brain to the desktop adapter."""
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
        TkinterDesktopWindow(
            DesktopController(brain),
            event_bus=event_bus,
        ).run()
    finally:
        app.stop()


if __name__ == "__main__":
    main()
