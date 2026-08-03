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

    def __init__(self) -> None:
        self.bootstrap = Bootstrap()

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
