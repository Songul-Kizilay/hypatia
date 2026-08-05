"""Immutable model for a registered Hypatia session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """Represents a session registered by the runtime."""

    session_id: str
    created_at: datetime
