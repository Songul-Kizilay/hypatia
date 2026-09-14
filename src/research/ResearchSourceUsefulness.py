"""What the operator concluded a source was worth, after reading it.

Separate from whether the source matched the question's words, from what the
recorded evidence supports, and from whether anything is true. A source can
match a question perfectly and be worth nothing, which is the case this
vocabulary exists to let a person write down.

`UNKNOWN` is the default and it is a real answer rather than a placeholder for
one. Most sources are never appraised, and a system that quietly read silence as
`useful` — or as `not_useful` — would be inventing a judgement nobody made.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSourceUsefulness(StrEnum):
    """Say what a person concluded this source was worth to them."""

    UNKNOWN = "unknown"
    USEFUL = "useful"
    PARTIALLY_USEFUL = "partially_useful"
    NOT_USEFUL = "not_useful"
