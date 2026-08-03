"""
Core event model for Hypatia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Event:
    """Immutable event transported through the Event Bus."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "hypatia"
    event_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
