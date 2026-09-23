"""What kind of witness the operator judged this source to be.

The question is not how good the source is. It is how far the source stands
from the thing it describes: whether it is the original account, a report of
that account, or a summary built on reports. A primary source can still be
wrong, and a tertiary one can still be useful — this dimension says nothing
about either. It says where the source sits in the chain between an event and
what the operator is reading about it.

`UNKNOWN` is the default and stays the honest answer for every source nobody
has classified. It is not read as "probably primary" or "probably secondary";
a build that guessed either from a domain name, a publication date, or the
source's own text would be inventing a judgement nobody made.

This is a citation, not a corroboration signal. `independence` already answers
whether two accepted sources are one witness or two, and this field must not
be folded into that question: a primary source that happens to be the only
source recording something is still exactly one source, and naming it
`PRIMARY` says nothing about whether anything else corroborates it.
"""

from __future__ import annotations

from enum import StrEnum


class ResearchSourceEvidenceType(StrEnum):
    """Say how far the operator judged this source to stand from its subject."""

    UNKNOWN = "unknown"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
