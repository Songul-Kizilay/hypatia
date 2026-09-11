"""Immutable, transient model-input review. A fingerprint is not permission.

This request neither authorizes disclosure nor chooses an endpoint. A future
execution integration must bind its fingerprint into the ordinary approved plan
and check disclosure and budget separately. No body is persisted by this type.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

from core.Exceptions import ResearchError
from research.ResearchSourcePreview import ResearchSourcePreview

MAX_SEMANTIC_SOURCE_BYTES = 16_384


def _date(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError("Unsupported request value.")


@dataclass(frozen=True, slots=True)
class SemanticEvidenceRequest:
    """Preserve the exact question, ordered source snapshot and proposal limit."""

    question: str = field(repr=False)
    previews: tuple[ResearchSourcePreview, ...] = field(repr=False)
    limit: int = 5
    content_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.question, str)
            or not self.question.strip()
            or len(self.question) > 2000
            or type(self.limit) is not int
            or not 1 <= self.limit <= 5
            or not isinstance(self.previews, tuple)
            or not 1 <= len(self.previews) <= 3
            or any(not isinstance(p, ResearchSourcePreview) for p in self.previews)
            or len({(p.execution_id, p.run_id) for p in self.previews}) != 1
            or len({p.step_id for p in self.previews}) != len(self.previews)
            or self.source_byte_count > MAX_SEMANTIC_SOURCE_BYTES
        ):
            raise ResearchError("Semantic proposal input exceeds its bounded contract.")
        try:
            self.question.encode("utf-8")
            # Include all preview fields, including acquisition provenance, not
            # just the displayed URL. This is not the ResearchPlan digest.
            encoded = json.dumps(
                {
                    "schema": "hypatia:semantic-evidence-input:v1",
                    "question": self.question,
                    "limit": self.limit,
                    "previews": [asdict(p) for p in self.previews],
                },
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                default=_date,
            ).encode("utf-8")
        except ValueError, TypeError:
            raise ResearchError("Semantic proposal input is invalid.") from None
        object.__setattr__(
            self, "content_fingerprint", hashlib.sha256(encoded).hexdigest()
        )

    @property
    def source_byte_count(self) -> int:
        return sum(p.content_byte_count for p in self.previews)

    def model_input_json(self) -> str:
        """Exact user-data payload only; provenance stays outside the model."""
        return json.dumps(
            {
                "question": self.question,
                "sources": [
                    {"source": str(index), "text": p.source.content}
                    for index, p in enumerate(self.previews)
                ],
            },
            ensure_ascii=True,
        )
