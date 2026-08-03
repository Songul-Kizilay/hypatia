"""Immutable record model used by the MemoryManager."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """An immutable item kept in Hypatia's in-memory store."""

    memory_id: str
    content: str
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    tags: frozenset[str] = field(default_factory=frozenset)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None
