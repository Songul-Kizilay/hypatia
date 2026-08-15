"""Launch the local Tkinter desktop shell over the existing Hypatia runtime."""

from __future__ import annotations

from brain.Brain import Brain
from core.Application import HypatiaApplication
from desktop.DesktopController import DesktopController
from desktop.TkinterDesktopWindow import TkinterDesktopWindow


def main() -> None:
    """Start Hypatia's runtime, then hand its Brain to the desktop adapter."""
    app = HypatiaApplication.from_process_environment()
    app.start()

    try:
        brain = app.bootstrap.container.resolve(Brain)
        TkinterDesktopWindow(DesktopController(brain)).run()
    finally:
        app.stop()


if __name__ == "__main__":
    main()
