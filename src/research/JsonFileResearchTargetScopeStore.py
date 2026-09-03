"""Bounded atomic local storage for one explicit target-scope snapshot.

Like existing research stores this is a trusted single-writer boundary, not a
multiwriter registry. A missing snapshot means no configured scope, never an
unrestricted scope. Loading or saving never starts a request or grants authority.
"""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from core.Exceptions import ResearchError
from research.ResearchTargetScope import ResearchTargetScope
from research.ResearchTargetScopeCodec import (
    MAX_TARGET_SCOPE_BYTES,
    decode_target_scope,
    encode_target_scope,
)


class JsonFileResearchTargetScopeStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> ResearchTargetScope | None:
        """Return the exact validated scope, None for absence, or raise."""
        try:
            with self._path.open("rb") as stream:
                payload = stream.read(MAX_TARGET_SCOPE_BYTES + 1)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise ResearchError("Unable to read target scope snapshot.") from error
        return decode_target_scope(payload)

    def save(self, scope: ResearchTargetScope) -> None:
        """Replace the snapshot atomically only after complete validation."""
        payload = encode_target_scope(scope)
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
                    raise OSError("Incomplete target scope snapshot write.")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._path)
            temporary = None
        except OSError as error:
            raise ResearchError("Unable to write target scope snapshot.") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    # Best-effort cleanup must not mask the primary write error.
                    # A leftover temporary file is never loaded as the snapshot.
                    pass
