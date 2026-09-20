"""Create-new, atomic publication of one local export file."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from core.Exceptions import ResearchError


def publish_new_export_file(destination: Path, content: bytes) -> None:
    """Publish complete bytes atomically without replacing an existing path."""
    temporary_path: Path | None = None
    try:
        descriptor, raw_temporary_path = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        temporary_path = Path(raw_temporary_path)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary_path, destination)
    except FileExistsError as error:
        raise ResearchError(
            "Research export destination already exists; no file was replaced."
        ) from error
    except OSError as error:
        raise ResearchError("Research export file could not be saved.") from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
