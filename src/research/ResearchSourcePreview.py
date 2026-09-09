"""Bounded, transient acquired text. Never an accepted source or evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from core.Exceptions import ResearchError
from research.ResearchSource import ResearchSource

MAX_SOURCE_PREVIEW_UTF8_BYTES = 65_536


@dataclass(frozen=True, slots=True)
class ResearchSourcePreview:
    """Bind one untrusted source body to the exact acquisition attempt."""

    execution_id: str
    run_id: str
    step_id: str
    requested_url: str
    source: ResearchSource = field(repr=False)
    content_byte_count: int = field(init=False)
    content_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for value, maximum in (
            (self.execution_id, 200),
            (self.run_id, 200),
            (self.step_id, 200),
            (self.requested_url, 4096),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ResearchError("Source preview identity is invalid.")
        if not isinstance(self.source, ResearchSource):
            raise ResearchError("Source preview requires acquired text.")
        for value, maximum in (
            (self.source.url, 4096),
            (self.source.title, 1000),
            (self.source.content_resource, 4096),
            (self.source.content_type, 255),
            (self.source.acquisition, 100),
        ):
            if len(value) > maximum:
                raise ResearchError("Source preview metadata is too large.")
        # Check characters before allocating the UTF-8 copy. Never silently
        # truncate: downstream excerpts must refer to a complete reviewed body.
        if len(self.source.content) > MAX_SOURCE_PREVIEW_UTF8_BYTES:
            raise ResearchError("Source preview exceeds its UTF-8 byte limit.")
        try:
            encoded = self.source.content.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ResearchError("Source preview text is invalid Unicode.") from error
        if len(encoded) > MAX_SOURCE_PREVIEW_UTF8_BYTES:
            raise ResearchError("Source preview exceeds its UTF-8 byte limit.")
        object.__setattr__(self, "content_byte_count", len(encoded))
        object.__setattr__(self, "content_sha256", hashlib.sha256(encoded).hexdigest())
