"""
Hypatia AI Operating System

Application.py

Main application controller responsible for managing the
complete lifecycle of the Hypatia runtime.
"""

from __future__ import annotations

from core.Bootstrap import Bootstrap


class HypatiaApplication:
    """
    Main application class.

    This class represents the running Hypatia instance.
    """

    def __init__(self, bootstrap: Bootstrap | None = None) -> None:
        self.bootstrap = bootstrap or Bootstrap()

    @classmethod
    def from_process_environment(cls) -> HypatiaApplication:
        bootstrap = Bootstrap.from_process_environment()
        return cls(bootstrap=bootstrap)

    def start(self) -> None:
        """
        Starts the Hypatia runtime.
        """
        self.bootstrap.initialize()

    def stop(self) -> None:
        """
        Stops the Hypatia runtime.
        """
        self.bootstrap.shutdown()
