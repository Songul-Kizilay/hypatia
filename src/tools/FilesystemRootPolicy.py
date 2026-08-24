"""Decide which directory, if any, the filesystem capability may see inside.

This is the one place a real path becomes filesystem authority, so it is the one
place worth being suspicious in. The root never comes from a model, a chat
message, research text, or a tool argument. It comes from operator
configuration: an environment variable the operator set, or the workspace
Hypatia already owns.

The default is Hypatia's own local data directory. That is not a guess at a
useful path — it is the directory the desktop already created for memory,
sessions, and research snapshots, so listing it shows the operator what Hypatia
has actually stored about them. It is also the smallest interesting root
available: nothing in it belongs to anyone but Hypatia.

Some roots are refused even when configured deliberately. A drive root, a
filesystem root, and the home directory itself are not scopes, they are the
absence of one, and a capability granted over them would be a filesystem tool
wearing a boundary rather than having one. An operator who genuinely wants that
has to say so somewhere this code cannot reach, which is the point.

When no usable root resolves, the answer is None and no filesystem tool is
registered at all. A registered tool that refuses everything is one
configuration mistake away from working; an absent capability is not.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from core.Exceptions import ResearchError
from tools.FilesystemRoot import FilesystemRoot

FILESYSTEM_ROOT_OVERRIDE = "HYPATIA_FILESYSTEM_ROOT"

DEFAULT_ROOT_ID = "workspace"


def resolve_filesystem_root(
    default_root: Path | None = None,
    environment: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> FilesystemRoot | None:
    """Return the configured root, or None when none is usable.

    None is a normal answer rather than an error. A desktop started before its
    data directory exists should run without a filesystem capability, not fail
    to start, and it should gain the capability when the directory appears
    rather than by someone relaxing a check.
    """
    values = os.environ if environment is None else environment
    configured = values.get(FILESYSTEM_ROOT_OVERRIDE, "").strip()
    candidate = Path(configured).expanduser() if configured else default_root
    if candidate is None:
        return None
    if configured and not candidate.is_absolute():
        raise ResearchError(f"{FILESYSTEM_ROOT_OVERRIDE} must be an absolute path.")
    if not candidate.is_dir():
        return None
    if is_too_broad(candidate, home=home):
        raise ResearchError(
            "A filesystem root that wide is not a scope. Configure a directory "
            "inside the area Hypatia should be able to see."
        )
    try:
        return FilesystemRoot(candidate, root_id=DEFAULT_ROOT_ID)
    except ResearchError:
        return None


def is_too_broad(candidate: Path, home: Path | None = None) -> bool:
    """Return whether this directory is an absence of scope rather than a scope.

    The home directory is refused as well as the drive root. It reads as
    modest next to `C:\\`, and it is where nearly everything personal on a
    single-user machine actually lives.
    """
    try:
        resolved = candidate.expanduser().resolve()
    except OSError:
        return True
    if resolved.parent == resolved:
        return True
    resolved_home = (Path.home() if home is None else home).expanduser()
    try:
        resolved_home = resolved_home.resolve()
    except OSError:
        return False
    return resolved == resolved_home or resolved in resolved_home.parents
