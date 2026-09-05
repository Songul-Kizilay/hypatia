"""Atomic trusted-desktop storage for immutable program-scope history.

This is a bounded single-writer audit store.  It neither proves program
ownership nor grants execution authority, and loading it performs no I/O other
than reading the caller-selected local file.
"""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from core.Exceptions import ResearchError
from research.ResearchProgramScopeRevision import ResearchProgramScopeRevision
from research.ResearchProgramScopeRevisionCodec import (
    MAX_PROGRAM_SCOPE_REVISION_STORE_BYTES,
    decode_program_scope_revisions,
    encode_program_scope_revisions,
)


class JsonFileResearchProgramScopeRevisionStore:
    """Load and atomically replace one complete, monotonic revision history."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> list[ResearchProgramScopeRevision]:
        try:
            with self._path.open("rb") as stream:
                payload = stream.read(MAX_PROGRAM_SCOPE_REVISION_STORE_BYTES + 1)
        except FileNotFoundError:
            return []
        except OSError as error:
            raise ResearchError("Unable to read program scope revisions.") from error
        return decode_program_scope_revisions(payload)

    def save(self, revisions: list[ResearchProgramScopeRevision]) -> None:
        """Persist only an extension or an exact immutable revocation transition."""
        payload = encode_program_scope_revisions(revisions)
        existing = self.load()
        self._require_preserved_history(existing, revisions)

        temporary: Path | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                mode="wb",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                if stream.write(payload) != len(payload):
                    raise OSError("Incomplete program scope revision history write.")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._path)
            temporary = None
        except OSError as error:
            raise ResearchError("Unable to write program scope revisions.") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _require_preserved_history(
        existing: list[ResearchProgramScopeRevision],
        proposed: list[ResearchProgramScopeRevision],
    ) -> None:
        if len(proposed) < len(existing):
            raise ResearchError("Program scope revision history cannot be shortened.")
        for prior, candidate in zip(existing, proposed, strict=False):
            if candidate == prior:
                continue
            if (
                prior.active
                and candidate.revoked_at is not None
                and candidate.revoked_by is not None
                and candidate
                == prior.revoked(candidate.revoked_at, candidate.revoked_by)
            ):
                continue
            raise ResearchError("Program scope revision history is immutable.")
