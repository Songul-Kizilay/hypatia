"""Launch the local Tkinter desktop shell over the existing Hypatia runtime."""

from __future__ import annotations

import os

from brain.Brain import Brain
from cognition.ResearchProgramScopeEnrollmentService import (
    ResearchProgramScopeEnrollmentService,
)
from cognition.TrustedDeferredExecutionControlService import (
    TrustedDeferredExecutionControlService,
)
from cognition.TrustedOneShotDeferredExecutionScheduler import (
    TrustedOneShotDeferredExecutionScheduler,
)
from core.Application import HypatiaApplication
from core.RuntimeOptIn import (
    background_research_enabled,
    curiosity_enabled,
    failure_memory_enabled,
    hypothesis_engine_enabled,
    plan_authorization_enabled,
    reflection_enabled,
    vulnerability_graph_enabled,
)
from desktop.DesktopController import DesktopController
from desktop.DesktopDataPaths import DesktopDataPaths
from desktop.TkinterDesktopWindow import TkinterDesktopWindow
from desktop.ToolConsoleController import ToolConsoleController
from eventbus.EventBus import EventBus
from research.JsonFileResearchProgramScopeRevisionStore import (
    JsonFileResearchProgramScopeRevisionStore,
)
from tools.FilesystemReadTool import FilesystemReadTool
from tools.FilesystemRoot import FilesystemRoot
from tools.FilesystemRootPolicy import resolve_filesystem_root
from tools.ToolRuntime import ToolRuntime
from tools.WindowsRootedOpen import WindowsRootedOpen, WindowsRootedOpenError


def _verify_inert_platform_boundary_imports() -> None:
    """Keep inert platform modules importable in the packaged desktop."""
    from tools.WindowsRootedOpen import WindowsRootedOpen

    if WindowsRootedOpen.__module__ != "tools.WindowsRootedOpen":
        raise RuntimeError("A required platform boundary could not be imported.")


def _compose_filesystem_read_tool(
    filesystem_root: FilesystemRoot | None,
) -> FilesystemReadTool | None:
    """Build the exact Windows content tool or leave the capability absent."""
    if filesystem_root is None:
        return None
    try:
        reader = WindowsRootedOpen(filesystem_root)
    except WindowsRootedOpenError:
        return None
    return FilesystemReadTool(reader)


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
        research_program_scope_revision_path=(
            data_paths.research_program_scope_revision_path
        ),
    )
    app.start()

    try:
        brain = app.bootstrap.container.resolve(Brain)
        event_bus = app.bootstrap.container.resolve(EventBus)
        # The tool runtime is composed here, in the same place that already
        # decides where this installation keeps its data. Its filesystem scope
        # defaults to that directory and can only be widened by an operator
        # environment variable — never by a model, a message, or an argument.
        filesystem_root = resolve_filesystem_root(default_root=data_paths.root)
        tool_runtime = ToolRuntime(
            filesystem_root,
            filesystem_read_tool=_compose_filesystem_read_tool(filesystem_root),
            event_bus=event_bus,
        )
        background_enabled = background_research_enabled(os.environ)
        authorization_enabled = plan_authorization_enabled(os.environ)
        deferred_execution_control = (
            app.bootstrap.container.resolve(TrustedDeferredExecutionControlService)
            if background_enabled and authorization_enabled
            else None
        )
        one_shot_deferred_execution_control = (
            app.bootstrap.container.resolve(TrustedOneShotDeferredExecutionScheduler)
            if background_enabled and authorization_enabled
            else None
        )
        program_scope_enrollment_service = ResearchProgramScopeEnrollmentService(
            JsonFileResearchProgramScopeRevisionStore(
                data_paths.research_program_scope_revision_path
            )
        )
        TkinterDesktopWindow(
            DesktopController(
                brain,
                deferred_execution_control,
                one_shot_deferred_execution_control,
            ),
            event_bus=event_bus,
            tool_console=ToolConsoleController(tool_runtime, event_bus),
            # The same predicates the runtime used to decide whether each of
            # these is durable, so no panel can appear over a store that is
            # not there.
            weakness_graph_enabled=vulnerability_graph_enabled(os.environ),
            hypothesis_enabled=hypothesis_engine_enabled(os.environ),
            failure_memory_enabled=failure_memory_enabled(os.environ),
            reflection_enabled=reflection_enabled(os.environ),
            curiosity_enabled=curiosity_enabled(os.environ),
            plan_authorization_enabled=plan_authorization_enabled(os.environ),
            program_scope_enrollment_service=program_scope_enrollment_service,
        ).run()
    finally:
        app.stop()


if __name__ == "__main__":
    main()
