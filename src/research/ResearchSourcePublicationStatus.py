"""What the operator found out about the standing of the publication itself.

The value that matters here is `RETRACTED`, and what matters about it is what
recording it does *not* do. It deletes no source, removes no evidence, rewrites
no claim, and lowers no confidence. A retraction discovered today is a fact
about the document, not a licence to quietly edit the record of what was
believed last month and why.

Deleting the evidence would be the tempting move and the wrong one. A run whose
history silently loses the retracted paper reads as though nothing ever rested
on it, which is exactly backwards: the point of knowing about a retraction is
being able to see what was built on top of it. So the status is recorded, stays
visible next to the source, and leaves the consequences to a person — or to a
review layer that a later milestone may teach to raise its hand.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSourcePublicationStatus(StrEnum):
    """Say what the operator found out about the publication's standing."""

    UNKNOWN = "unknown"
    NORMAL = "normal"
    RETRACTED = "retracted"
    WITHDRAWN = "withdrawn"
    CORRECTED = "corrected"
