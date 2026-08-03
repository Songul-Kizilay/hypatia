"""Standard request model for the Hypatia Brain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class BrainRequest:
    """A single user message entering the Brain."""

    message: str
    source: str = "user"
    metadata: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid4()))
