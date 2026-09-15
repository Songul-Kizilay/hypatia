"""
Hypatia AI Operating System

Application.py

Main application controller responsible for managing the
complete lifecycle of the Hypatia runtime.
"""

from __future__ import annotations

from pathlib import Path

from core.Bootstrap import Bootstrap


class HypatiaApplication:
    """
    Main application class.

    This class represents the running Hypatia instance.
    """

    def __init__(self, bootstrap: Bootstrap | None = None) -> None:
        self.bootstrap = bootstrap or Bootstrap()

    @classmethod
    def from_process_environment(
        cls,
        *,
        memory_path: Path | None = None,
        session_path: Path | None = None,
        knowledge_relation_path: Path | None = None,
        research_run_path: Path | None = None,
        research_source_content_path: Path | None = None,
        research_program_scope_revision_path: Path | None = None,
        defer_mission_recovery: bool = False,
    ) -> HypatiaApplication:
        """Create an application with optional caller-owned local data paths."""
        if (
            memory_path is None
            and session_path is None
            and knowledge_relation_path is None
            and research_run_path is None
            and research_source_content_path is None
            and research_program_scope_revision_path is None
        ):
            bootstrap = Bootstrap.from_process_environment(
                defer_mission_recovery=defer_mission_recovery
            )
        else:
            bootstrap = Bootstrap.from_process_environment(
                memory_path=memory_path,
                session_path=session_path,
                knowledge_relation_path=knowledge_relation_path,
                research_run_path=research_run_path,
                research_source_content_path=research_source_content_path,
                research_program_scope_revision_path=(
                    research_program_scope_revision_path
                ),
                defer_mission_recovery=defer_mission_recovery,
            )
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
