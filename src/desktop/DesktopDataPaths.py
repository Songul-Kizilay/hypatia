"""Local persistence paths reserved for the installed desktop application."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_DATA_DIRECTORY_OVERRIDE = "HYPATIA_DESKTOP_DATA_DIR"


@dataclass(frozen=True, slots=True)
class DesktopDataPaths:
    """Keep desktop-owned runtime state outside an installed application folder."""

    root: Path

    @property
    def memory_path(self) -> Path:
        """Return the primary local conversation-memory snapshot path."""
        return self.root / "memory" / "memory.json"

    @property
    def session_path(self) -> Path:
        """Return the local session-registry snapshot path."""
        return self.root / "sessions" / "sessions.json"

    @property
    def knowledge_relation_path(self) -> Path:
        """Return the local explicit-knowledge-relation snapshot path."""
        return self.root / "knowledge" / "relations.json"

    @property
    def research_run_path(self) -> Path:
        """Return the persistent research-run audit snapshot path."""
        return self.root / "research" / "runs.json"

    @classmethod
    def from_process_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        platform_name: str | None = None,
        home: Path | None = None,
    ) -> DesktopDataPaths:
        """Choose a user-writable local-data root without creating it eagerly."""
        values = os.environ if environment is None else environment
        configured_root = values.get(_DATA_DIRECTORY_OVERRIDE, "").strip()
        if configured_root:
            root = Path(configured_root).expanduser()
            if not root.is_absolute():
                raise ValueError(
                    f"{_DATA_DIRECTORY_OVERRIDE} must be an absolute path."
                )
            return cls(root)

        resolved_platform = os.name if platform_name is None else platform_name
        resolved_home = Path.home() if home is None else home
        if resolved_platform == "nt":
            local_app_data = values.get("LOCALAPPDATA", "").strip()
            if local_app_data:
                return cls(Path(local_app_data) / "Hypatia")
            return cls(resolved_home / "AppData" / "Local" / "Hypatia")

        xdg_data_home = values.get("XDG_DATA_HOME", "").strip()
        if xdg_data_home:
            candidate = Path(xdg_data_home).expanduser()
            if candidate.is_absolute():
                return cls(candidate / "hypatia")
        return cls(resolved_home / ".local" / "share" / "hypatia")
